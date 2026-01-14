"""
Firewall Manager per Dog Agent
Wrapper per gestione iptables
"""
import subprocess
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class FirewallManager:
    """Gestisce operazioni firewall (iptables)"""

    @staticmethod
    def execute_iptables(command: List[str]) -> Dict:
        """
        Esegue comando iptables
        Args:
            command: Lista argomenti comando (es: ['-A', 'INPUT', '-p', 'tcp', '--dport', '22', '-j', 'ACCEPT'])
        Returns:
            Dict con status, output, error
        """
        try:
            full_command = ['iptables'] + command
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                logger.info(f"iptables command success: {' '.join(full_command)}")
                return {
                    'success': True,
                    'output': result.stdout,
                    'error': ''
                }
            else:
                logger.error(f"iptables command failed: {result.stderr}")
                return {
                    'success': False,
                    'output': result.stdout,
                    'error': result.stderr
                }

        except Exception as e:
            logger.error(f"Error executing iptables: {e}")
            return {
                'success': False,
                'output': '',
                'error': str(e)
            }

    def add_rule(self, payload: Dict) -> Dict:
        """
        Aggiunge regola firewall
        Args:
            payload: {
                'chain': 'INPUT',
                'protocol': 'tcp',
                'port': 22,
                'source_ip': '1.2.3.4',
                'action': 'ACCEPT'
            }
        """
        chain = payload.get('chain', 'INPUT')
        protocol = payload.get('protocol')
        port = payload.get('port')
        source_ip = payload.get('source_ip')
        action = payload.get('action', 'ACCEPT')

        command = ['-A', chain]

        if protocol:
            command.extend(['-p', protocol])

        if port:
            command.extend(['--dport', str(port)])

        if source_ip:
            command.extend(['-s', source_ip])

        command.extend(['-j', action])

        return self.execute_iptables(command)

    def remove_rule(self, payload: Dict) -> Dict:
        """Rimuove regola firewall"""
        # Simile ad add_rule ma usa -D invece di -A
        chain = payload.get('chain', 'INPUT')
        protocol = payload.get('protocol')
        port = payload.get('port')
        source_ip = payload.get('source_ip')
        action = payload.get('action', 'ACCEPT')

        command = ['-D', chain]

        if protocol:
            command.extend(['-p', protocol])

        if port:
            command.extend(['--dport', str(port)])

        if source_ip:
            command.extend(['-s', source_ip])

        command.extend(['-j', action])

        return self.execute_iptables(command)

    def block_ip(self, ip_address: str) -> Dict:
        """Blocca IP specifico"""
        command = ['-A', 'INPUT', '-s', ip_address, '-j', 'DROP']
        return self.execute_iptables(command)

    def unblock_ip(self, ip_address: str) -> Dict:
        """Sblocca IP specifico"""
        command = ['-D', 'INPUT', '-s', ip_address, '-j', 'DROP']
        return self.execute_iptables(command)

    def list_rules(self) -> List[str]:
        """Lista tutte le regole iptables"""
        try:
            result = subprocess.run(
                ['iptables', '-L', '-n', '-v'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.split('\n')
        except Exception as e:
            logger.error(f"Error listing rules: {e}")
            return []

    def get_stats(self) -> Dict:
        """Ottiene statistiche firewall"""
        rules = self.list_rules()
        return {
            'active_rules_count': len([r for r in rules if r.strip()]),
            'blocked_ips_count': len([r for r in rules if 'DROP' in r or 'REJECT' in r])
        }
