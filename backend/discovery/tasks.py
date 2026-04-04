"""
Celery Tasks per Network Discovery
"""

from celery import shared_task
import subprocess
import re
import logging
from django.utils.timezone import now

from discovery.models import DiscoveredHost
from targets.models import Target

logger = logging.getLogger("firedog.discovery")


@shared_task(bind=True)
def discover_network_task(self):
    """
    Task Celery per network discovery con arp-scan

    Operazioni:
    1. Ottieni reti locali da 'ip route'
    2. Per ogni rete, esegui arp-scan
    3. Parsa output e salva host scoperti
    4. Aggiorna stato host esistenti

    Returns:
        {
            "success": True,
            "networks_scanned": ["192.168.1.0/24"],
            "hosts_found": 15,
            "hosts_new": 3,
            "hosts_updated": 12
        }
    """
    try:
        logger.info("Starting network discovery task")

        # ==================== STEP 1: Ottieni reti locali ====================
        networks = get_local_networks()

        if not networks:
            logger.warning("No local networks found")
            return {"success": False, "error": "No local networks found"}

        logger.info(f"Found {len(networks)} local networks: {networks}")

        # ==================== STEP 2: Scan ogni rete ====================
        all_discovered = []
        hosts_new = 0
        hosts_updated = 0

        for network in networks:
            try:
                logger.info(f"Scanning network: {network}")

                hosts = scan_network_arp(network)

                logger.info(f"Network {network}: found {len(hosts)} hosts")

                # Salva/aggiorna host nel database
                for host_data in hosts:
                    ip = host_data["ip"]

                    # Check if already target
                    is_target = Target.objects.filter(ip_address=ip).exists()

                    # Get or create discovered host
                    host, created = DiscoveredHost.objects.get_or_create(
                        ip_address=ip,
                        defaults={
                            "mac_address": host_data["mac"],
                            "hostname": host_data.get("hostname", ""),
                            "vendor": host_data.get("vendor", ""),
                            "network": network.split("/")[0],
                            "netmask": get_netmask_from_cidr(network),
                            "is_alive": True,
                            "is_imported": is_target,
                        },
                    )

                    if created:
                        hosts_new += 1
                        logger.debug(f"New host discovered: {ip} ({host_data['mac']})")
                    else:
                        # Update existing
                        host.mac_address = host_data["mac"]
                        host.vendor = host_data.get("vendor", host.vendor)
                        host.is_alive = True
                        host.last_seen = now()
                        host.scan_count += 1

                        # Update hostname if resolved and not set
                        if host_data.get("hostname") and not host.hostname:
                            host.hostname = host_data["hostname"]

                        host.save()
                        hosts_updated += 1

                    all_discovered.append(host.id)

            except Exception as e:
                logger.error(f"Error scanning network {network}: {e}")
                continue

        # ==================== STEP 3: Marca host non visti come offline ====================
        if all_discovered:
            DiscoveredHost.objects.exclude(id__in=all_discovered).update(is_alive=False)

        result = {
            "success": True,
            "networks_scanned": networks,
            "hosts_found": len(all_discovered),
            "hosts_new": hosts_new,
            "hosts_updated": hosts_updated,
        }

        logger.info(f"Network discovery completed: {result}")

        return result

    except Exception as e:
        logger.exception(f"Network discovery task failed: {e}")
        return {"success": False, "error": str(e)}


def get_local_networks():
    """
    Ottieni reti locali da 'ip route'

    Returns:
        ['192.168.1.0/24', '10.0.0.0/24', ...]
    """
    try:
        result = subprocess.run(
            ["ip", "route"], capture_output=True, text=True, check=True, timeout=10
        )

        networks = []

        for line in result.stdout.split("\n"):
            # Parse lines like: "192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.1"
            match = re.match(r"^(\d+\.\d+\.\d+\.\d+/\d+)\s", line)

            if match:
                network = match.group(1)

                # Skip default route, localhost, and link-local
                if (
                    not network.startswith("0.0.0.0")
                    and not network.startswith("127.")
                    and not network.startswith("169.254.")
                ):
                    networks.append(network)

        return networks

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get local networks: {e}")
        return []
    except Exception as e:
        logger.error(f"Error getting local networks: {e}")
        return []


def scan_network_arp(network):
    """
    Esegui arp-scan su una rete

    Args:
        network: CIDR notation (e.g., '192.168.1.0/24')

    Returns:
        [
            {
                'ip': '192.168.1.100',
                'mac': '00:11:22:33:44:55',
                'hostname': 'server01.local',
                'vendor': 'Dell Inc.'
            },
            ...
        ]
    """
    try:
        # Execute arp-scan
        # Note: richiede sudo, assicurati che sia configurato in sudoers
        result = subprocess.run(
            ["sudo", "arp-scan", "-l"],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )

        hosts = []

        for line in result.stdout.split("\n"):
            # Parse lines like: "192.168.1.100	00:11:22:33:44:55	Vendor Name"
            # arp-scan usa TAB come separatore
            match = re.match(r"^(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:]{17})\s+(.*)", line)

            if match:
                ip = match.group(1)
                mac = match.group(2).upper()
                vendor = match.group(3).strip()

                # Try to resolve hostname
                hostname = resolve_hostname(ip)

                hosts.append(
                    {"ip": ip, "mac": mac, "vendor": vendor, "hostname": hostname or ""}
                )

        return hosts

    except subprocess.CalledProcessError as e:
        logger.error(f"arp-scan failed for {network}: {e.stderr}")
        raise Exception(f"arp-scan failed: {e.stderr}")
    except subprocess.TimeoutExpired:
        logger.error(f"arp-scan timeout for {network}")
        raise Exception("arp-scan timeout")
    except Exception as e:
        logger.error(f"Error scanning network {network}: {e}")
        raise


def resolve_hostname(ip):
    """
    Risolvi hostname da IP usando 'host' command

    Args:
        ip: IP address

    Returns:
        hostname string or None
    """
    try:
        result = subprocess.run(["host", ip], capture_output=True, text=True, timeout=2)

        if result.returncode == 0:
            # Parse output like: "100.1.168.192.in-addr.arpa domain name pointer server01.local."
            match = re.search(r"pointer\s+(.+?)\.?\s*$", result.stdout, re.MULTILINE)
            if match:
                hostname = match.group(1).rstrip(".")
                return hostname

        return None

    except subprocess.TimeoutExpired:
        return None
    except Exception as e:
        logger.debug(f"Could not resolve hostname for {ip}: {e}")
        return None


def get_netmask_from_cidr(network):
    """
    Converti CIDR in netmask

    Args:
        network: '192.168.1.0/24'

    Returns:
        '255.255.255.0'
    """
    import ipaddress

    try:
        net = ipaddress.ip_network(network, strict=False)
        return str(net.netmask)
    except:
        return ""
