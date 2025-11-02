"""
Celery Tasks per l'app Targets
"""
from celery import shared_task
from django.conf import settings
from core.ssh_manager import SSHManager, SSHConnectionError
import logging

logger = logging.getLogger('firedog.tasks')


@shared_task
def install_firedog_on_target(target_id, user_id):
    """Installa pacchetto firedog su target"""
    from targets.models import Target
    from audit.models import AuditLog
    from django.contrib.auth.models import User
    
    try:
        target = Target.objects.get(id=target_id)
        user = User.objects.get(id=user_id)
        
        ssh = SSHManager(host=target.ip_address, port=target.ssh_port, username=target.ssh_user)
        ssh.connect()
        
        # Verifica utente
        if not ssh.check_user_exists(target.ssh_user):
            raise Exception(f"Utente {target.ssh_user} non esiste sul target")
        
        # Upload pacchetto
        package_path = settings.FIREDOG_PACKAGE_PATH
        remote_path = '/tmp/firedog-package'
        ssh.upload_directory(package_path, remote_path)
        
        # Esegui installer
        exit_code, stdout, stderr = ssh.execute_command(f'cd {remote_path} && sudo bash install.sh', sudo=False)
        
        if exit_code != 0:
            raise Exception(f"Installazione fallita: {stderr}")
        
        # Installa cron
        cron_cmd = f"*/10 * * * * /opt/firedog/traffic-analyzer.py"
        ssh.execute_command(f'(crontab -l 2>/dev/null; echo "{cron_cmd}") | crontab -', sudo=False)
        
        ssh.disconnect()
        
        target.status = 'online'
        target.firedog_version = '1.0.0'
        target.save()
        
        AuditLog.log_action('install', f'Firedog installato su {target.ip_address}', user, target)
        
        logger.info(f"Firedog installato con successo su {target.ip_address}")
        return {'success': True}
        
    except Exception as e:
        logger.error(f"Errore installazione firedog: {e}")
        target.mark_error(str(e))
        AuditLog.log_action('install', f'Errore installazione su {target.ip_address}', user, target, success=False, error_message=str(e))
        return {'success': False, 'error': str(e)}


@shared_task
def uninstall_firedog_from_target(target_id, user_id):
    """Disinstalla pacchetto firedog da target"""
    from targets.models import Target
    from audit.models import AuditLog
    from django.contrib.auth.models import User
    
    try:
        target = Target.objects.get(id=target_id)
        user = User.objects.get(id=user_id)
        
        ssh = SSHManager(host=target.ip_address, port=target.ssh_port, username=target.ssh_user)
        ssh.connect()
        
        # Rimuovi cron
        ssh.execute_command("crontab -l | grep -v 'traffic-analyzer' | crontab -", sudo=False)
        
        # Rimuovi directory
        ssh.execute_command("sudo rm -rf /opt/firedog", sudo=True)
        
        ssh.disconnect()
        
        target.status = 'pending'
        target.firedog_version = ''
        target.save()
        
        AuditLog.log_action('uninstall', f'Firedog disinstallato da {target.ip_address}', user, target)
        
        return {'success': True}
        
    except Exception as e:
        logger.error(f"Errore disinstallazione: {e}")
        return {'success': False, 'error': str(e)}


@shared_task
def fetch_target_data(target_id):
    """Fetch dati analisi da target"""
    from targets.models import Target
    import json
    
    try:
        target = Target.objects.get(id=target_id)
        
        if target.status != 'online':
            return {'success': False, 'reason': 'target not online'}
        
        ssh = SSHManager(host=target.ip_address, port=target.ssh_port, username=target.ssh_user)
        ssh.connect()
        
        # Download analysis results
        remote_file = '/tmp/firedog-analysis.json'
        local_file = f'/tmp/analysis_{target.id}.json'
        
        if not ssh.file_exists(remote_file):
            ssh.disconnect()
            return {'success': False, 'reason': 'analysis file not found'}
        
        ssh.download_file(remote_file, local_file)
        ssh.disconnect()
        
        # Parse e salva dati
        with open(local_file, 'r') as f:
            data = json.load(f)
        
        # Qui processeremo i dati e li salveremo nel DB
        # TODO: Implementare parsing e salvataggio threats
        
        target.last_fetch = timezone.now()
        target.mark_online()
        
        logger.info(f"Dati fetchati con successo da {target.ip_address}")
        return {'success': True}
        
    except Exception as e:
        logger.error(f"Errore fetch dati: {e}")
        target.mark_offline(str(e))
        return {'success': False, 'error': str(e)}


@shared_task
def fetch_all_targets_data():
    """Fetch dati da tutti i target online"""
    from targets.models import Target
    
    targets = Target.objects.filter(status='online')
    
    for target in targets:
        fetch_target_data.delay(target.id)
    
    return {'success': True, 'targets_count': targets.count()}
