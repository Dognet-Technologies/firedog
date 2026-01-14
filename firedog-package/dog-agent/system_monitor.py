"""
System Monitor per Dog Agent
Raccoglie statistiche di sistema
"""
import psutil
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class SystemMonitor:
    """Monitora statistiche di sistema"""

    @staticmethod
    def get_system_stats() -> Dict:
        """Raccoglie statistiche sistema"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # Disk
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent

            # Network
            net_io = psutil.net_io_counters()
            bytes_sent = net_io.bytes_sent
            bytes_recv = net_io.bytes_recv

            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'disk_percent': disk_percent,
                'bytes_sent': bytes_sent,
                'bytes_recv': bytes_recv,
            }

        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {
                'cpu_percent': 0,
                'memory_percent': 0,
                'disk_percent': 0,
                'bytes_sent': 0,
                'bytes_recv': 0,
            }

    @staticmethod
    def get_network_info() -> Dict:
        """Ottiene informazioni di rete (IP, MAC, hostname)"""
        import socket
        import uuid

        hostname = socket.gethostname()

        # Get primary IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
        except:
            ip_address = "127.0.0.1"

        # Get MAC address
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                        for elements in range(0, 2*6, 2)][::-1])

        return {
            'ip_address': ip_address,
            'hostname': hostname,
            'mac_address': mac
        }
