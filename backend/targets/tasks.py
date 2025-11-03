""" 
Celery Tasks per l'app Targets
"""
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from core.ssh_manager import SSHManager, SSHConnectionError
from datetime import timedelta
import logging

logger = logging.getLogger('firedog.tasks')


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
    """
    Fetch dati completi da un target
    
    Args:
        target_id: ID del target da cui fetchare
        
    Returns:
        dict con risultati:
        {
            'success': bool,
            'threats_count': int,
            'new_threats': int,
            'stats': dict,
            'error': str (se success=False)
        }
    """
    from targets.models import Target, Statistics, Alert
    from threats.models import ThreatLog
    from rules.models import FirewallRule
    
    try:
        target = Target.objects.get(id=target_id)
        logger.info(f"Starting fetch for target {target.hostname} ({target.ip_address})")
        
        # Verifica che il target sia online
        if target.status != 'online':
            logger.warning(f"Target {target.hostname} not online, skipping fetch")
            return {
                'success': False,
                'reason': 'target not online'
            }
        
        # Connessione SSH
        try:
            ssh = SSHManager(
                host=target.ip_address,
                port=target.ssh_port,
                username=target.ssh_user
            )
            ssh.connect()
        except SSHConnectionError as e:
            logger.error(f"SSH connection failed: {e}")
            target.mark_offline(str(e))
            return {
                'success': False,
                'error': f'SSH connection failed: {e}'
            }
        
        result = {
            'success': True,
            'threats_count': 0,
            'new_threats': 0,
            'stats': None,
            'rules_synced': 0
        }
        
        try:
            # ============================================
            # 1. FETCH STATISTICS
            # ============================================
            logger.debug("Fetching statistics...")
            stats_data = ssh.get_statistics()
            
            if stats_data:
                # Salva statistics nel DB
                Statistics.objects.create(
                    target=target,
                    input_packets=stats_data.get('input_packets', 0),
                    output_packets=stats_data.get('output_packets', 0),
                    input_dropped=stats_data.get('input_dropped', 0),
                    output_dropped=stats_data.get('output_dropped', 0),
                    pcap_input_size=stats_data.get('pcap_input_size', 0),
                    pcap_output_size=stats_data.get('pcap_output_size', 0),
                    collected_at=timezone.now()
                )
                result['stats'] = stats_data
                logger.info(f"Statistics saved: {stats_data['input_packets']} input packets")
            else:
                logger.warning("No statistics data received")
            
            # ============================================
            # 2. FETCH THREATS
            # ============================================
            logger.debug("Fetching threats...")
            threats_data = ssh.get_threats(min_score=30)  # Score minimo 30
            
            new_threats_count = 0
            critical_threats_count = 0
            
            with transaction.atomic():
                for threat_data in threats_data:
                    # Verifica se minaccia già esiste (stesso IP nelle ultime 24h)
                    existing = ThreatLog.objects.filter(
                        target=target,
                        source_ip=threat_data['source_ip'],
                        detected_at__gte=timezone.now() - timedelta(hours=24)
                    ).first()
                    
                    if not existing:
                        # Nuova minaccia - crea record
                        ThreatLog.objects.create(
                            target=target,
                            source_ip=threat_data['source_ip'],
                            threat_score=threat_data['threat_score'],
                            packets=threat_data.get('packets', 0),
                            ports_count=threat_data.get('ports_count', 0),
                            protocols=threat_data.get('protocols', 'tcp'),
                            threat_type=threat_data.get('threat_type', 'Unknown'),
                            classification=threat_data['classification'],
                            detected_at=timezone.now(),
                            acknowledged=False
                        )
                        new_threats_count += 1
                        
                        if threat_data['classification'] == 'CRITICAL':
                            critical_threats_count += 1
                    else:
                        # Minaccia già registrata, aggiorna se score aumentato
                        if threat_data['threat_score'] > existing.threat_score:
                            existing.threat_score = threat_data['threat_score']
                            existing.packets = threat_data.get('packets', existing.packets)
                            existing.detected_at = timezone.now()
                            existing.save()
            
            result['threats_count'] = len(threats_data)
            result['new_threats'] = new_threats_count
            
            logger.info(f"Threats processed: {len(threats_data)} total, {new_threats_count} new")
            
            # ============================================
            # 3. FETCH FIREWALL RULES
            # ============================================
            logger.debug("Fetching firewall rules...")
            rules_data = ssh.get_firewall_rules()  # Tutte le chain
            
            with transaction.atomic():
                # Rimuovi regole obsolete
                FirewallRule.objects.filter(target=target).delete()
                
                # Inserisci regole aggiornate
                for rule_data in rules_data:
                    FirewallRule.objects.create(
                        target=target,
                        chain=rule_data['chain'],
                        rule_number=rule_data['rule_number'],
                        protocol=rule_data.get('protocol', 'all'),
                        port=rule_data.get('port'),
                        source_ip=rule_data.get('source'),
                        dest_ip=rule_data.get('destination'),
                        action=rule_data.get('target', 'ACCEPT'),
                        comment=rule_data.get('comment', ''),
                        packets=rule_data.get('packets', 0),
                        bytes=rule_data.get('bytes', 0),
                        synced_at=timezone.now()
                    )
            
            result['rules_synced'] = len(rules_data)
            logger.info(f"Firewall rules synced: {len(rules_data)}")
            
            # ============================================
            # 4. AGGIORNA TARGET
            # ============================================
            target.last_fetch = timezone.now()
            target.last_seen = timezone.now()
            target.mark_online()
            
            # ============================================
            # 5. CREA ALERT SE MINACCE CRITICHE
            # ============================================
            if critical_threats_count > 0:
                # Verifica se alert già inviato nell'ultima ora
                recent_alert = Alert.objects.filter(
                    target=target,
                    severity='critical',
                    created_at__gte=timezone.now() - timedelta(hours=1)
                ).exists()
                
                if not recent_alert:
                    Alert.objects.create(
                        target=target,
                        severity='critical',
                        title='Critical Threats Detected',
                        message=f'{critical_threats_count} critical threats detected on {target.hostname}',
                        acknowledged=False
                    )
                    logger.warning(f"Created critical alert for {target.hostname}")
            
            logger.info(f"Fetch completed for {target.hostname}")
            return result
            
        finally:
            ssh.disconnect()
    
    except Target.DoesNotExist:
        logger.error(f"Target {target_id} not found")
        return {
            'success': False,
            'error': 'Target not found'
        }
    
    except Exception as e:
        logger.error(f"Unexpected error fetching target {target_id}: {e}", exc_info=True)
        
        try:
            target.mark_offline(str(e))
        except:
            pass
        
        return {
            'success': False,
            'error': str(e)
        }

@shared_task
def fetch_all_targets_data():
    """
    Task schedulato per fetch dati da tutti i target online
    
    Eseguito periodicamente da Celery Beat (default ogni 10 minuti)
    """
    from targets.models import Target
    
    logger.info("Starting scheduled fetch for all targets")
    
    # Ottieni tutti i target online
    targets = Target.objects.filter(status='online')
    
    results = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'skipped': 0
    }
    
    for target in targets:
        # Verifica se è tempo di fetchare (rispetta fetch_interval_minutes)
        if target.last_fetch:
            next_fetch = target.last_fetch + timedelta(minutes=target.fetch_interval_minutes)
            if timezone.now() < next_fetch:
                logger.debug(f"Skipping {target.hostname} - not yet time to fetch")
                results['skipped'] += 1
                continue
        
        # Esegui fetch async
        fetch_target_data.delay(target.id)
        results['total'] += 1
    
    logger.info(f"Scheduled fetch for {results['total']} targets")
    return results
