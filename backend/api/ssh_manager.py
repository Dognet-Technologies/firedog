import paramiko
import os
from pathlib import Path
from scp import SCPClient
from typing import Optional, Tuple, Dict
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class SSHManager:
    """Gestione connessioni SSH ai target"""

    def __init__(self, target, timeout=30):
        self.target = target
        self.timeout = timeout
        self.client = None
        self.scp_client = None

    def connect(self) -> bool:
        """Connessione SSH al target"""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Carica chiave privata
            private_key = self._get_private_key()

            self.client.connect(
                hostname=self.target.ip_address,
                port=self.target.ssh_port,
                username="microcyber",
                pkey=private_key,
                timeout=self.timeout,
                banner_timeout=self.timeout,
                auth_timeout=self.timeout,
            )

            logger.info(f"SSH connected to {self.target.ip_address}")
            return True

        except Exception as e:
            logger.error(f"SSH connection failed to {self.target.ip_address}: {e}")
            return False

    def disconnect(self):
        """Chiudi connessione"""
        if self.scp_client:
            self.scp_client.close()
        if self.client:
            self.client.close()
        logger.info(f"SSH disconnected from {self.target.ip_address}")

    def execute_command(self, command: str) -> Tuple[int, str, str]:
        """Esegui comando remoto"""
        if not self.client:
            raise Exception("Not connected")

        try:
            stdin, stdout, stderr = self.client.exec_command(
                command, timeout=self.timeout
            )
            exit_code = stdout.channel.recv_exit_status()

            stdout_str = stdout.read().decode("utf-8")
            stderr_str = stderr.read().decode("utf-8")

            return exit_code, stdout_str, stderr_str

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise

    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload file via SCP"""
        if not self.client:
            raise Exception("Not connected")

        try:
            if not self.scp_client:
                self.scp_client = SCPClient(self.client.get_transport())

            self.scp_client.put(local_path, remote_path)
            logger.info(
                f"Uploaded {local_path} to {self.target.ip_address}:{remote_path}"
            )
            return True

        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return False

    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download file via SCP"""
        if not self.client:
            raise Exception("Not connected")

        try:
            if not self.scp_client:
                self.scp_client = SCPClient(self.client.get_transport())

            self.scp_client.get(remote_path, local_path)
            logger.info(f"Downloaded {remote_path} from {self.target.ip_address}")
            return True

        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False

    def upload_directory(self, local_dir: str, remote_dir: str) -> bool:
        """Upload intera directory"""
        if not self.client:
            raise Exception("Not connected")

        try:
            if not self.scp_client:
                self.scp_client = SCPClient(self.client.get_transport())

            self.scp_client.put(local_dir, remote_dir, recursive=True)
            logger.info(
                f"Uploaded directory {local_dir} to {self.target.ip_address}:{remote_dir}"
            )
            return True

        except Exception as e:
            logger.error(f"Directory upload failed: {e}")
            return False

    def check_user_exists(self) -> bool:
        """Verifica esistenza utente microcyber"""
        try:
            exit_code, stdout, stderr = self.execute_command("id microcyber")
            return exit_code == 0
        except:
            return False

    def install_firedog_package(self, package_path: str) -> Tuple[bool, str]:
        """Installa pacchetto firedog sul target"""
        try:
            # 1. Upload package
            remote_tmp = "/tmp/firedog-package"
            if not self.upload_directory(package_path, remote_tmp):
                return False, "Failed to upload package"

            # 2. Esegui install.sh
            install_cmd = f"cd {remote_tmp} && sudo bash install.sh"
            exit_code, stdout, stderr = self.execute_command(install_cmd)

            if exit_code != 0:
                return False, f"Installation failed: {stderr}"

            # 3. Verifica installazione
            verify_cmd = "test -f /usr/local/bin/firewall-manager && echo 'OK'"
            exit_code, stdout, stderr = self.execute_command(verify_cmd)

            if "OK" not in stdout:
                return False, "Installation verification failed"

            # 4. Get version
            version_cmd = "firewall-manager --version 2>/dev/null || echo '1.0'"
            exit_code, version, _ = self.execute_command(version_cmd)

            return True, version.strip()

        except Exception as e:
            return False, str(e)

    def install_cron_job(self, interval_minutes: int = 10) -> bool:
        """Installa cron job per traffic analyzer"""
        cron_line = (
            f"*/{interval_minutes} * * * * "
            f"/usr/local/bin/traffic-analyzer --json > /tmp/firedog-analysis.json 2>&1\n"
        )

        try:
            # Aggiungi a crontab
            cmd = f'(crontab -u microcyber -l 2>/dev/null; echo "{cron_line}") | crontab -u microcyber -'
            exit_code, stdout, stderr = self.execute_command(cmd)

            return exit_code == 0

        except Exception as e:
            logger.error(f"Cron installation failed: {e}")
            return False

    def fetch_analysis_results(self) -> Optional[Dict]:
        """Scarica risultati analysis JSON"""
        try:
            remote_file = "/tmp/firedog-analysis.json"
            local_file = f"/tmp/firedog-analysis-{self.target.id}.json"

            if self.download_file(remote_file, local_file):
                import json

                with open(local_file, "r") as f:
                    data = json.load(f)

                os.remove(local_file)
                return data

            return None

        except Exception as e:
            logger.error(f"Failed to fetch analysis: {e}")
            return None

    def get_firewall_rules(self, chain: str = None) -> Optional[str]:
        """Ottieni regole iptables"""
        try:
            if chain:
                cmd = f"sudo iptables -L {chain} -n -v --line-numbers"
            else:
                cmd = "sudo iptables -L -n -v --line-numbers"

            exit_code, stdout, stderr = self.execute_command(cmd)

            if exit_code == 0:
                return stdout

            return None

        except Exception as e:
            logger.error(f"Failed to get rules: {e}")
            return None

    def add_firewall_rule(
        self,
        chain: str,
        port: int,
        protocol: str = "tcp",
        source_ip: str = None,
        comment: str = "",
    ) -> Tuple[bool, str]:
        """Aggiungi regola firewall"""
        try:
            cmd_parts = [
                f"sudo firewall-manager --add-{chain.lower()} {port}",
                f"--protocol {protocol}",
            ]

            if source_ip:
                cmd_parts.append(f"--source {source_ip}")

            if comment:
                cmd_parts.append(f'--comment "{comment}"')

            cmd = " ".join(cmd_parts)
            exit_code, stdout, stderr = self.execute_command(cmd)

            if exit_code == 0:
                return True, stdout
            else:
                return False, stderr

        except Exception as e:
            return False, str(e)

    def remove_firewall_rule(self, chain: str, rule_number: int) -> Tuple[bool, str]:
        """Rimuovi regola firewall"""
        try:
            cmd = f"sudo firewall-manager --remove {chain} {rule_number}"
            exit_code, stdout, stderr = self.execute_command(cmd)

            if exit_code == 0:
                return True, stdout
            else:
                return False, stderr

        except Exception as e:
            return False, str(e)

    def get_statistics(self) -> Optional[Dict]:
        """Ottieni statistiche firewall"""
        try:
            cmd = "sudo firewall-manager --stats"
            exit_code, stdout, stderr = self.execute_command(cmd)

            if exit_code == 0:
                # Parse output (implementa parsing specifico)
                return {"raw_output": stdout}

            return None

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return None

    def _get_private_key(self):
        """Carica chiave privata SSH"""
        from .models import SSHKey

        try:
            ssh_key = SSHKey.objects.latest("created_at")
            return paramiko.Ed25519Key.from_private_key_file(
                io.StringIO(ssh_key.private_key)
            )
        except SSHKey.DoesNotExist:
            raise Exception("No SSH key found in database")

    def __enter__(self):
        """Context manager enter"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
