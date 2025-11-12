"""
Utility per Target Groups - Template Predefiniti
CREA QUESTO FILE: backend/targets/group_templates.py

Questo file contiene template predefiniti di regole firewall
per gruppi comuni (Web, DNS, Database, Storage)
"""
from .models import TargetGroup, GroupRuleTemplate


# Template di regole predefiniti
PREDEFINED_TEMPLATES = {
    'web': {
        'name': 'Web Servers',
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
    'dns': {
        'name': 'DNS Servers',
        'description': 'Server DNS per risoluzione nomi',
        'color': '#10b981',  # Green
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
    'database': {
        'name': 'Database Servers',
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
    'storage': {
        'name': 'Storage Servers',
        'description': 'Server di storage (SMB, NFS)',
        'color': '#8b5cf6',  # Purple
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
    'mail': {
        'name': 'Mail Servers',
        'description': 'Server email (SMTP, IMAP, POP3)',
        'color': '#ef4444',  # Red
        'icon': 'server',
        'rules': [
            {
                'name': 'SMTP',
                'protocol': 'tcp',
                'port': 25,
                'action': 'ACCEPT',
                'comment': 'SMTP mail transfer',
                'priority': 10,
            },
            {
                'name': 'SMTP Submission',
                'protocol': 'tcp',
                'port': 587,
                'action': 'ACCEPT',
                'comment': 'SMTP submission (authenticated)',
                'priority': 10,
            },
            {
                'name': 'SMTPS',
                'protocol': 'tcp',
                'port': 465,
                'action': 'ACCEPT',
                'comment': 'SMTP over SSL',
                'priority': 10,
            },
            {
                'name': 'IMAP',
                'protocol': 'tcp',
                'port': 143,
                'action': 'ACCEPT',
                'comment': 'IMAP mail access',
                'priority': 15,
            },
            {
                'name': 'IMAPS',
                'protocol': 'tcp',
                'port': 993,
                'action': 'ACCEPT',
                'comment': 'IMAP over SSL',
                'priority': 15,
            },
            {
                'name': 'POP3',
                'protocol': 'tcp',
                'port': 110,
                'action': 'ACCEPT',
                'comment': 'POP3 mail access',
                'priority': 15,
            },
            {
                'name': 'POP3S',
                'protocol': 'tcp',
                'port': 995,
                'action': 'ACCEPT',
                'comment': 'POP3 over SSL',
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
    'monitoring': {
        'name': 'Monitoring Servers',
        'description': 'Server di monitoring (Prometheus, Grafana, etc)',
        'color': '#06b6d4',  # Cyan
        'icon': 'shield',
        'rules': [
            {
                'name': 'Prometheus',
                'protocol': 'tcp',
                'port': 9090,
                'action': 'ACCEPT',
                'comment': 'Prometheus server',
                'priority': 10,
            },
            {
                'name': 'Grafana',
                'protocol': 'tcp',
                'port': 3000,
                'action': 'ACCEPT',
                'comment': 'Grafana dashboard',
                'priority': 10,
            },
            {
                'name': 'Node Exporter',
                'protocol': 'tcp',
                'port': 9100,
                'action': 'ACCEPT',
                'comment': 'Prometheus Node Exporter',
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
