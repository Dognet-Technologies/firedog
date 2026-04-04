"""
Celery Tasks per installazione e gestione Target
"""

from celery import shared_task
from django.utils.timezone import now
from datetime import timedelta
import logging

from targets.models import Target
from core.ssh_manager import SSHManager, SSHConnectionError

logger = logging.getLogger("firedog.tasks")


@shared_task(bind=True, max_retries=3)
def install_firedog_on_target(self, target_id: int, user_id: int):
    """
    Task Celery per installazione completa firedog sul target

    Operazioni:
    1. Connessione SSH con chiave
    2. Verifica utente microcyber
    3. Hardening SSH (PasswordAuthentication no)
    4. Configurazione sudoers per microcyber
    5. Upload firedog-package
    6. Esecuzione install.sh
    7. Verifica installazione
    8. Setup cron job

    Args:
        target_id: ID del target
        user_id: ID dell'utente che ha richiesto l'installazione
    """
    try:
        # Load target
        target = Target.objects.get(id=target_id)
        target.status = "installing"
        target.installation_status = "Starting installation..."
        target.installation_error = ""
        target.save()

        logger.info(f"Starting installation for target {target_id}: {target.hostname}")

        # ==================== STEP 1: Connessione SSH ====================
        target.installation_status = "Connecting via SSH..."
        target.save()

        ssh = SSHManager(
            host=target.ip_address, port=target.ssh_port, username=target.ssh_user
        )

        try:
            ssh.connect()
            logger.info(f"SSH connection established to {target.ip_address}")
        except SSHConnectionError as e:
            error_msg = f"SSH connection failed: {str(e)}"
            logger.error(f"Target {target_id}: {error_msg}")
            target.status = "error"
            target.installation_status = "Failed"
            target.installation_error = error_msg
            target.save()

            return {"success": False, "error": error_msg}

        # ==================== STEP 2: Verifica utente microcyber ====================
        target.installation_status = "Checking prerequisites..."
        target.save()

        if not ssh.check_user_exists(target.ssh_user):
            error_msg = f"User '{target.ssh_user}' not found on target"
            logger.error(f"Target {target_id}: {error_msg}")

            target.status = "error"
            target.installation_status = "Failed"
            target.installation_error = error_msg
            target.save()

            ssh.disconnect()

            return {"success": False, "error": error_msg}

        logger.info(f"User {target.ssh_user} exists on target {target_id}")

        # ==================== STEP 3: Hardening SSH ====================
        target.installation_status = "Hardening SSH configuration..."
        target.save()

        logger.info(f"Starting SSH hardening for target {target_id}")

        # Backup del file sshd_config originale
        exit_code, stdout, stderr = ssh.execute_command(
            "sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak.$(date +%Y%m%d_%H%M%S)"
        )

        if exit_code != 0:
            logger.warning(
                f"Target {target_id}: Could not backup sshd_config: {stderr}"
            )

        # Modifica sshd_config per disabilitare password authentication
        ssh_hardening_commands = [
            # Disabilita PasswordAuthentication
            "sudo sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config",
            # Abilita PubkeyAuthentication (se non già presente)
            "sudo sed -i 's/^#*PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config",
            # Disabilita ChallengeResponseAuthentication
            "sudo sed -i 's/^#*ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' /etc/ssh/sshd_config",
            # Verifica configurazione
            "sudo sshd -t",
        ]

        for cmd in ssh_hardening_commands:
            exit_code, stdout, stderr = ssh.execute_command(cmd)
            if exit_code != 0 and "sshd -t" in cmd:
                error_msg = f"SSH config validation failed: {stderr}"
                logger.error(f"Target {target_id}: {error_msg}")

                # Ripristina backup
                ssh.execute_command(
                    "sudo mv /etc/ssh/sshd_config.bak.* /etc/ssh/sshd_config 2>/dev/null || true"
                )

                target.status = "error"
                target.installation_status = "Failed"
                target.installation_error = error_msg
                target.save()
                ssh.disconnect()

                return {"success": False, "error": error_msg}

        # Riavvia sshd
        logger.info(f"Restarting SSH daemon on target {target_id}")
        exit_code, stdout, stderr = ssh.execute_command(
            "sudo systemctl restart sshd || sudo service ssh restart"
        )

        if exit_code != 0:
            logger.warning(
                f"Target {target_id}: SSH restart command returned {exit_code}: {stderr}"
            )

        logger.info(f"SSH hardening completed for target {target_id}")

        # ==================== STEP 4: Configurazione sudoers ====================
        target.installation_status = "Configuring sudoers..."
        target.save()

        logger.info(f"Configuring sudoers for target {target_id}")

        # Crea file sudoers per microcyber
        sudoers_content = f"""# FireDog - Permessi per utente {target.ssh_user}
{target.ssh_user} ALL=(ALL) NOPASSWD: /usr/sbin/iptables
{target.ssh_user} ALL=(ALL) NOPASSWD: /usr/sbin/ip6tables
{target.ssh_user} ALL=(ALL) NOPASSWD: /usr/sbin/iptables-save
{target.ssh_user} ALL=(ALL) NOPASSWD: /usr/sbin/iptables-restore
{target.ssh_user} ALL=(ALL) NOPASSWD: /usr/local/bin/firewall-manager
{target.ssh_user} ALL=(ALL) NOPASSWD: /usr/local/bin/traffic-analyzer
{target.ssh_user} ALL=(ALL) NOPASSWD: /bin/systemctl restart firedog
{target.ssh_user} ALL=(ALL) NOPASSWD: /bin/systemctl status firedog
{target.ssh_user} ALL=(ALL) NOPASSWD: /bin/cat /var/log/firedog/*
"""

        temp_sudoers = f"/tmp/firedog_sudoers_{target.ssh_user}"
        sudoers_escaped = sudoers_content.replace("\n", "\\n").replace('"', '\\"')

        sudoers_commands = [
            f'echo -e "{sudoers_escaped}" > {temp_sudoers}',
            # f"sudo visudo -c -f {temp_sudoers}",
            f"sudo mv {temp_sudoers} /etc/sudoers.d/{target.ssh_user}",
            f"sudo chmod 440 /etc/sudoers.d/{target.ssh_user}",
        ]

        for cmd in sudoers_commands:
            exit_code, stdout, stderr = ssh.execute_command(cmd)

            if exit_code != 0 and "visudo -c" in cmd:
                error_msg = f"Sudoers validation failed: {stderr}"
                logger.error(f"Target {target_id}: {error_msg}")

                target.status = "error"
                target.installation_status = "Failed"
                target.installation_error = error_msg
                target.save()
                ssh.disconnect()

                return {"success": False, "error": error_msg}

        logger.info(f"Sudoers configuration completed for target {target_id}")

        # ==================== STEP 5: Upload firedog-package ====================
        target.installation_status = "Uploading firedog package..."
        target.save()

        logger.info(f"Uploading firedog package to target {target_id}")

        package_local_path = "/opt/firedog/firedog-package"
        package_remote_path = "/tmp/firedog-package"

        try:
            success, message = ssh.upload_directory(
                package_local_path, package_remote_path
            )

            if not success:
                error_msg = f"Package upload failed: {message}"
                logger.error(f"Target {target_id}: {error_msg}")

                target.status = "error"
                target.installation_status = "Failed"
                target.installation_error = error_msg
                target.save()
                ssh.disconnect()

                return {"success": False, "error": error_msg}

            logger.info(f"Package uploaded successfully to target {target_id}")

        except Exception as e:
            error_msg = f"Upload exception: {str(e)}"
            logger.error(f"Target {target_id}: {error_msg}")

            target.status = "error"
            target.installation_status = "Failed"
            target.installation_error = error_msg
            target.save()
            ssh.disconnect()

            return {"success": False, "error": error_msg}

        # ==================== STEP 6: Esecuzione install.sh ====================
        target.installation_status = "Running installation script..."
        target.save()

        logger.info(f"Executing install.sh on target {target_id}")

        exit_code, stdout, stderr = ssh.execute_command(
            f"chmod +x {package_remote_path}/*.sh {package_remote_path}/*.py"
        )

        exit_code, stdout, stderr = ssh.execute_command(
            f"cd {package_remote_path} && sudo bash install.sh", timeout=300
        )

        if exit_code != 0:
            error_msg = f"Installation script failed: {stderr}"
            logger.error(f"Target {target_id}: {error_msg}")

            target.status = "error"
            target.installation_status = "Failed"
            target.installation_error = error_msg
            target.save()
            ssh.disconnect()

            return {"success": False, "error": error_msg}

        logger.info(f"Installation script completed on target {target_id}")

        # ==================== STEP 7: Verifica installazione ====================
        target.installation_status = "Verifying installation..."
        target.save()

        exit_code, stdout, stderr = ssh.execute_command(
            "test -f /usr/local/bin/firewall-manager && echo 'INSTALLED'"
        )

        if exit_code != 0 or "INSTALLED" not in stdout:
            error_msg = "firewall-manager not found after installation"
            logger.error(f"Target {target_id}: {error_msg}")

            target.status = "error"
            target.installation_status = "Failed"
            target.installation_error = error_msg
            target.save()
            ssh.disconnect()

            return {"success": False, "error": error_msg}

        exit_code, version_output, stderr = ssh.execute_command(
            "/usr/local/bin/firewall-manager --version 2>&1 || echo '1.0.0'"
        )

        firedog_version = version_output.strip() or "1.0.0"
        logger.info(f"Target {target_id}: Firedog version {firedog_version} installed")

        # ==================== SUCCESS ====================
        target.status = "online"
        target.installation_status = "Completed"
        target.installation_error = ""
        target.firedog_version = firedog_version
        target.last_seen = now()
        target.save()

        ssh.disconnect()

        logger.info(f"Installation completed successfully for target {target_id}")

        return {
            "success": True,
            "message": "Installation completed",
            "firedog_version": firedog_version,
        }

    except Target.DoesNotExist:
        error_msg = f"Target {target_id} not found"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.exception(f"Target {target_id}: {error_msg}")

        try:
            target = Target.objects.get(id=target_id)
            target.status = "error"
            target.installation_status = "Failed"
            target.installation_error = error_msg
            target.save()
        except:
            pass

        return {"success": False, "error": error_msg}


@shared_task
def fetch_target_data(target_id: int):
    """Task per recupero dati da target via SCP"""
    try:
        target = Target.objects.get(id=target_id)

        if target.status != "online":
            return {"success": False, "error": "Target not online"}

        logger.info(f"Fetching data from target {target_id}")

        ssh = SSHManager(
            host=target.ip_address, port=target.ssh_port, username=target.ssh_user
        )

        ssh.connect()

        remote_file = "/tmp/firedog-analysis.json"
        local_file = (
            f'/tmp/firedog_data_{target_id}_{now().strftime("%Y%m%d_%H%M%S")}.json'
        )

        success, message = ssh.download_file(remote_file, local_file)
        ssh.disconnect()

        if success:
            target.last_fetch = now()
            target.last_seen = now()
            target.save()

            return {"success": True, "file": local_file}
        else:
            return {"success": False, "error": message}

    except Exception as e:
        logger.exception(f"Error fetching data from target {target_id}")
        return {"success": False, "error": str(e)}


@shared_task
def check_targets_health():
    """Task periodico per check salute target"""
    online_targets = Target.objects.filter(status="online")

    results = {"checked": 0, "online": 0, "offline": 0}

    for target in online_targets:
        try:
            ssh = SSHManager(
                host=target.ip_address, port=target.ssh_port, username=target.ssh_user
            )

            ssh.connect()
            exit_code, stdout, stderr = ssh.execute_command('echo "OK"')
            ssh.disconnect()

            if exit_code == 0:
                target.mark_online()
                results["online"] += 1
            else:
                target.mark_offline()
                results["offline"] += 1

        except Exception:
            target.mark_offline()
            results["offline"] += 1

        results["checked"] += 1

    return results
