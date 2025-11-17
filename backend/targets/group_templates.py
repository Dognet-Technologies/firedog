"""
Utility per Target Groups - Template Predefiniti
CREA QUESTO FILE: backend/targets/group_templates.py

Questo file contiene template predefiniti di regole firewall
per gruppi comuni (Web, DNS, Database, Storage)
"""
from .models import TargetGroup, GroupRuleTemplate


# Template di regole predefiniti - 10 gruppi
PREDEFINED_TEMPLATES = {
    'web': {
        'name': 'Web Server',
        'description': 'Server web con HTTP/HTTPS',
        'color': '#3b82f6',  # Blue
        'icon': 'globe',
        'rules': [
            {
                'name': 'HTTP Traffic',
                'protocol': 'tcp',
                'port': 80,
                'action': 'ACCEPT',
                'comment': 'Allow HTTP connections',
                'priority': 10,
            },
            {
                'name': 'HTTPS Traffic',
                'protocol': 'tcp',
                'port': 443,
                'action': 'ACCEPT',
                'comment': 'Allow HTTPS connections',
                'priority': 10,
            },
            {
                'name': 'SSH Access',
                'protocol': 'tcp',
                'port': 22,
                'action': 'ACCEPT',
                'comment': 'Allow SSH for management',
                'priority': 20,
            },
        ],
    },
    'firewall': {
        'name': 'Firewall',
        'description': 'Firewall e gateway di sicurezza',
        'color': '#ef4444',  # Red
        'icon': 'shield',
        'rules': [
            {
                'name': 'SSH Management',
                'protocol': 'tcp',
                'port': 22,
                'action': 'ACCEPT',
                'comment': 'SSH for firewall management',
                'priority': 10,
            },
            {
                'name': 'HTTPS Management',
                'protocol': 'tcp',
                'port': 443,
                'action': 'ACCEPT',
                'comment': 'Web management interface',
                'priority': 10,
            },
        ],
    },
    'database': {
        'name': 'Database',
        'description': 'Server database (MySQL, PostgreSQL, MongoDB)',
        'color': '#f59e0b',  # Orange
        'icon': 'database',
        'rules': [
            {
                'name': 'MySQL/MariaDB',
                'protocol': 'tcp',
                'port': 3306,
                'action': 'ACCEPT',
                'comment': 'MySQL/MariaDB connections',
                'priority': 10,
            },
            {
                'name': 'PostgreSQL',
                'protocol': 'tcp',
                'port': 5432,
                'action': 'ACCEPT',
                'comment': 'PostgreSQL connections',
                'priority': 10,
            },
            {
                'name': 'MongoDB',
                'protocol': 'tcp',
                'port': 27017,
                'action': 'ACCEPT',
                'comment': 'MongoDB connections',
                'priority': 10,
            },
            {
                'name': 'SSH Access',
                'protocol': 'tcp',
                'port': 22,
                'action': 'ACCEPT',
                'comment': 'Allow SSH for management',
                'priority': 20,
            },
        ],
    },
    'vpn': {
        'name': 'VPN',
        'description': 'Server VPN (OpenVPN, WireGuard)',
        'color': '#10b981',  # Green
        'icon': 'shield',
        'rules': [
            {
                'name': 'OpenVPN UDP',
                'protocol': 'udp',
                'port': 1194,
                'action': 'ACCEPT',
                'comment': 'OpenVPN default port',
                'priority': 10,
            },
            {
                'name': 'WireGuard',
                'protocol': 'udp',
                'port': 51820,
                'action': 'ACCEPT',
                'comment': 'WireGuard default port',
                'priority': 10,
            },
            {
                'name': 'SSH Access',
                'protocol': 'tcp',
                'port': 22,
                'action': 'ACCEPT',
                'comment': 'Allow SSH for management',
                'priority': 20,
            },
        ],
    },
    'ssh-bastions': {
        'name': 'SSH Bastions',
        'description': 'SSH bastion/jump host per accesso sicuro',
        'color': '#06b6d4',  # Cyan
        'icon': 'server',
        'rules': [
            {
                'name': 'SSH Access',
                'protocol': 'tcp',
                'port': 22,
                'action': 'ACCEPT',
                'comment': 'SSH for bastion access',
                'priority': 10,
            },
        ],
    },
    'proxy': {
        'name': 'Proxy',
        'description': 'Proxy e load balancer (HAProxy, Nginx)',
        'color': '#8b5cf6',  # Purple
        'icon': 'layers',
        'rules': [
            {
                'name': 'HTTP Traffic',
                'protocol': 'tcp',
                'port': 80,
                'action': 'ACCEPT',
                'comment': 'HTTP proxy',
                'priority': 10,
            },
            {
                'name': 'HTTPS Traffic',
                'protocol': 'tcp',
                'port': 443,
                'action': 'ACCEPT',
                'comment': 'HTTPS proxy',
                'priority': 10,
            },
            {
                'name': 'Proxy Alt Port',
                'protocol': 'tcp',
                'port': 8080,
                'action': 'ACCEPT',
                'comment': 'Alternative proxy port',
                'priority': 15,
            },
            {
                'name': 'SSH Access',
                'protocol': 'tcp',
                'port': 22,
                'action': 'ACCEPT',
                'comment': 'Allow SSH for management',
                'priority': 20,
            },
        ],
    },
    'storage': {
        'name': 'Storage',
        'description': 'Server di storage (SMB, NFS)',
        'color': '#ec4899',  # Pink
        'icon': 'hard-drive',
        'rules': [
            {
                'name': 'SMB/CIFS',
                'protocol': 'tcp',
                'port': 445,
                'action': 'ACCEPT',
                'comment': 'Windows file sharing',
                'priority': 10,
            },
            {
                'name': 'NFS',
                'protocol': 'tcp',
                'port': 2049,
                'action': 'ACCEPT',
                'comment': 'Network File System',
                'priority': 10,
            },
            {
                'name': 'FTP Data',
                'protocol': 'tcp',
                'port': 20,
                'action': 'ACCEPT',
                'comment': 'FTP data transfer',
                'priority': 15,
            },
            {
                'name': 'FTP Control',
                'protocol': 'tcp',
                'port': 21,
                'action': 'ACCEPT',
                'comment': 'FTP control',
                'priority': 15,
            },
            {
                'name': 'SSH/SFTP',
                'protocol': 'tcp',
                'port': 22,
                'action': 'ACCEPT',
                'comment': 'SSH and SFTP access',
                'priority': 20,
            },
        ],
    },
    'dns': {
        'name': 'DNS',
        'description': 'Server DNS per risoluzione nomi',
        'color': '#14b8a6',  # Teal
        'icon': 'globe',
        'rules': [
            {
                'name': 'DNS TCP',
                'protocol': 'tcp',
                'port': 53,
                'action': 'ACCEPT',
                'comment': 'DNS queries (TCP)',
                'priority': 10,
            },
            {
                'name': 'DNS UDP',
                'protocol': 'udp',
                'port': 53,
                'action': 'ACCEPT',
                'comment': 'DNS queries (UDP)',
                'priority': 10,
            },
            {
                'name': 'SSH Access',
                'protocol': 'tcp',
                'port': 22,
                'action': 'ACCEPT',
                'comment': 'Allow SSH for management',
                'priority': 20,
            },
        ],
    },
    'cache': {
        'name': 'Cache',
        'description': 'Server cache (Redis, Memcached)',
        'color': '#f97316',  # Orange-red
        'icon': 'layers',
        'rules': [
            {
                'name': 'Redis',
                'protocol': 'tcp',
                'port': 6379,
                'action': 'ACCEPT',
                'comment': 'Redis cache server',
                'priority': 10,
            },
            {
                'name': 'Memcached',
                'protocol': 'tcp',
                'port': 11211,
                'action': 'ACCEPT',
                'comment': 'Memcached server',
                'priority': 10,
            },
            {
                'name': 'SSH Access',
                'protocol': 'tcp',
                'port': 22,
                'action': 'ACCEPT',
                'comment': 'Allow SSH for management',
                'priority': 20,
            },
        ],
    },
    'ldap': {
        'name': 'LDAP',
        'description': 'Server LDAP/Active Directory',
        'color': '#a855f7',  # Purple-light
        'icon': 'server',
        'rules': [
            {
                'name': 'LDAP',
                'protocol': 'tcp',
                'port': 389,
                'action': 'ACCEPT',
                'comment': 'LDAP directory service',
                'priority': 10,
            },
            {
                'name': 'LDAPS',
                'protocol': 'tcp',
                'port': 636,
                'action': 'ACCEPT',
                'comment': 'LDAP over SSL',
                'priority': 10,
            },
            {
                'name': 'Kerberos',
                'protocol': 'tcp',
                'port': 88,
                'action': 'ACCEPT',
                'comment': 'Kerberos authentication',
                'priority': 15,
            },
            {
                'name': 'SSH Access',
                'protocol': 'tcp',
                'port': 22,
                'action': 'ACCEPT',
                'comment': 'Allow SSH for management',
                'priority': 20,
            },
        ],
    },
}


def create_predefined_group(template_key):
    """
    Crea un gruppo predefinito con le sue regole

    Args:
        template_key: Chiave del template ('web', 'dns', 'database', etc)

    Returns:
        TargetGroup: Il gruppo creato

    Raises:
        ValueError: Se il template non esiste
    """
    if template_key not in PREDEFINED_TEMPLATES:
        raise ValueError(f"Template '{template_key}' not found")

    template = PREDEFINED_TEMPLATES[template_key]

    # Crea il gruppo (se non esiste già)
    group, created = TargetGroup.objects.get_or_create(
        name=template['name'],
        defaults={
            'description': template['description'],
            'color': template['color'],
            'icon': template['icon'],
        }
    )

    if created:
        # Crea le regole template
        for rule_data in template['rules']:
            GroupRuleTemplate.objects.create(
                group=group,
                **rule_data
            )

    return group


def create_all_predefined_groups():
    """
    Crea tutti i gruppi predefiniti
    Utile per inizializzazione sistema

    Returns:
        list: Lista dei gruppi creati
    """
    groups = []

    for template_key in PREDEFINED_TEMPLATES.keys():
        try:
            group = create_predefined_group(template_key)
            groups.append(group)
        except Exception as e:
            print(f"Error creating group '{template_key}': {e}")

    return groups


def get_template_names():
    """Restituisce lista nomi template disponibili"""
    return list(PREDEFINED_TEMPLATES.keys())


def get_template_info(template_key):
    """
    Restituisce informazioni su un template

    Args:
        template_key: Chiave del template

    Returns:
        dict: Informazioni sul template
    """
    if template_key not in PREDEFINED_TEMPLATES:
        return None

    template = PREDEFINED_TEMPLATES[template_key]
    return {
        'key': template_key,
        'name': template['name'],
        'description': template['description'],
        'color': template['color'],
        'icon': template['icon'],
        'rule_count': len(template['rules']),
    }
