from celery import shared_task
import subprocess
import re

@shared_task
def discover_network():
    """Esegue network discovery con arp-scan"""
    from discovery.models import DiscoveredHost
    
    try:
        # Ottieni reti locali
        result = subprocess.run(['ip', 'route'], capture_output=True, text=True)
        networks = []
        
        for line in result.stdout.split('\n'):
            match = re.search(r'(\d+\.\d+\.\d+\.\d+/\d+)', line)
            if match and 'default' not in line:
                networks.append(match.group(1))
        
        discovered_count = 0
        
        # Scan ogni rete
        for network in networks:
            result = subprocess.run(
                ['sudo', 'arp-scan', '-l', '-I', 'eth0', network],
                capture_output=True,
                text=True
            )
            
            for line in result.stdout.split('\n'):
                match = re.match(r'(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f:]+)\s+(.*)', line, re.I)
                if match:
                    ip, mac, vendor = match.groups()
                    
                    host, created = DiscoveredHost.objects.get_or_create(
                        ip_address=ip,
                        defaults={
                            'mac_address': mac,
                            'vendor': vendor.strip(),
                            'network': network.split('/')[0]
                        }
                    )
                    
                    if not created:
                        host.increment_scan_count()
                    
                    discovered_count += 1
        
        return {'success': True, 'discovered': discovered_count}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}
