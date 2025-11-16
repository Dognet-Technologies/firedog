"""
Serializers per l'app Targets
"""
from rest_framework import serializers
from .models import Target
"""
Serializers per Whitelist e BlockedIPs
Con validazioni di sicurezza OWASP/NIST
"""
from .models import WhitelistEntry, BlockedIP
import re
import ipaddress



class TargetSerializer(serializers.ModelSerializer):
    """Serializer per il modello Target"""

    connection_string = serializers.ReadOnlyField()
    is_active = serializers.ReadOnlyField()
    gruppo_display = serializers.SerializerMethodField()
    target_groups = serializers.SerializerMethodField()

    class Meta:
        model = Target
        fields = [
            'id',
            'ip_address',
            'hostname',
            'description',
            'status',
            'firedog_version',
            'ssh_port',
            'ssh_user',
            'last_seen',
            'last_fetch',
            'error_message',
            'created_at',
            'updated_at',
            'connection_string',
            'is_active',
            'gruppo',
            'gruppo_custom',
            'gruppo_display',
            'target_groups',
        ]
        read_only_fields = [
            'status',
            'firedog_version',
            'last_seen',
            'last_fetch',
            'error_message',
            'created_at',
            'updated_at',
        ]

    def get_gruppo_display(self, obj):
        """Ritorna il nome leggibile del gruppo"""
        return obj.get_gruppo_display_name()

    def get_target_groups(self, obj):
        """Ritorna i TargetGroup a cui appartiene questo target"""
        return [
            {
                'id': group.id,
                'name': group.name,
                'color': group.color,
                'icon': group.icon,
            }
            for group in obj.groups.all()
        ]

    def update(self, instance, validated_data):
        """Aggiorna target e sincronizza con TargetGroup"""
        from .models import TargetGroup

        # Salva il vecchio gruppo
        old_gruppo = instance.gruppo
        old_gruppo_custom = instance.gruppo_custom

        # Aggiorna il target
        target = super().update(instance, validated_data)

        # Controlla se il gruppo è cambiato
        new_gruppo = validated_data.get('gruppo', old_gruppo)
        new_gruppo_custom = validated_data.get('gruppo_custom', old_gruppo_custom)

        if new_gruppo != old_gruppo or new_gruppo_custom != old_gruppo_custom:
            # Rimuovi da tutti i gruppi auto-creati (quelli con description che inizia con 'Auto-created')
            for group in target.groups.filter(description__startswith='Auto-created'):
                group.targets.remove(target)

            # Aggiungi al nuovo gruppo se presente
            if new_gruppo:
                # Determina il nome del gruppo
                if new_gruppo == 'custom':
                    group_name = new_gruppo_custom
                else:
                    group_name = dict(Target.GRUPPO_CHOICES).get(new_gruppo, new_gruppo)

                if group_name:
                    # Trova o crea il TargetGroup
                    target_group, created = TargetGroup.objects.get_or_create(
                        name=group_name,
                        defaults={
                            'description': f'Auto-created from target gruppo field',
                            'color': self._get_default_color(new_gruppo),
                            'icon': self._get_default_icon(new_gruppo),
                        }
                    )

                    # Aggiungi il target al gruppo
                    target_group.targets.add(target)

        return target

    def _get_default_color(self, gruppo):
        """Restituisce un colore di default basato sul tipo di gruppo"""
        colors = {
            'web': '#10b981',       # green
            'db': '#3b82f6',        # blue
            'dns': '#8b5cf6',       # purple
            'storage': '#f59e0b',   # amber
            'mail': '#ef4444',      # red
            'backup': '#6366f1',    # indigo
            'monitoring': '#06b6d4', # cyan
            'proxy': '#ec4899',     # pink
            'vpn': '#14b8a6',       # teal
            'firewall': '#f97316',  # orange
            'application': '#84cc16', # lime
            'cache': '#a855f7',     # fuchsia
            'queue': '#f43f5e',     # rose
            'other': '#6b7280',     # gray
            'custom': '#3b82f6',    # blue
        }
        return colors.get(gruppo, '#3b82f6')

    def _get_default_icon(self, gruppo):
        """Restituisce un'icona di default basata sul tipo di gruppo"""
        icons = {
            'web': 'globe',
            'db': 'database',
            'dns': 'globe',
            'storage': 'hard-drive',
            'mail': 'server',
            'backup': 'hard-drive',
            'monitoring': 'shield',
            'proxy': 'layers',
            'vpn': 'shield',
            'firewall': 'shield',
            'application': 'layers',
            'cache': 'server',
            'queue': 'layers',
            'other': 'box',
            'custom': 'server',
        }
        return icons.get(gruppo, 'server')


class TargetListSerializer(serializers.ModelSerializer):
    """Serializer semplificato per lista targets"""

    is_active = serializers.ReadOnlyField()
    gruppo_display = serializers.SerializerMethodField()
    target_groups = serializers.SerializerMethodField()

    class Meta:
        model = Target
        fields = [
            'id',
            'ip_address',
            'hostname',
            'status',
            'firedog_version',
            'last_seen',
            'is_active',
            'gruppo',
            'gruppo_custom',
            'gruppo_display',
            'target_groups',
        ]

    def get_gruppo_display(self, obj):
        """Ritorna il nome leggibile del gruppo"""
        return obj.get_gruppo_display_name()

    def get_target_groups(self, obj):
        """Ritorna i TargetGroup a cui appartiene questo target"""
        return [
            {
                'id': group.id,
                'name': group.name,
                'color': group.color,
            }
            for group in obj.groups.all()
        ]


class TargetCreateSerializer(serializers.ModelSerializer):
    """Serializer per creazione target"""

    class Meta:
        model = Target
        fields = [
            'ip_address',
            'hostname',
            'description',
            'ssh_port',
            'ssh_user',
            'gruppo',
            'gruppo_custom',
        ]

    def validate_ip_address(self, value):
        """Verifica che IP non sia già presente"""
        if Target.objects.filter(ip_address=value).exists():
            raise serializers.ValidationError("Questo IP è già registrato come target")
        return value

    def validate(self, data):
        """Validazione gruppo"""
        if data.get('gruppo') == 'custom' and not data.get('gruppo_custom'):
            raise serializers.ValidationError({
                'gruppo_custom': 'Nome gruppo personalizzato obbligatorio quando gruppo="custom"'
            })

        if data.get('gruppo') != 'custom':
            data['gruppo_custom'] = None

        return data

    def create(self, validated_data):
        """Crea target e sincronizza con TargetGroup"""
        from .models import TargetGroup

        # Crea il target
        target = super().create(validated_data)

        # Sincronizza con TargetGroup se ha un gruppo
        gruppo = validated_data.get('gruppo')
        if gruppo:
            # Determina il nome del gruppo
            if gruppo == 'custom':
                group_name = validated_data.get('gruppo_custom')
            else:
                # Usa il display name del gruppo
                group_name = dict(Target.GRUPPO_CHOICES).get(gruppo, gruppo)

            if group_name:
                # Trova o crea il TargetGroup
                target_group, created = TargetGroup.objects.get_or_create(
                    name=group_name,
                    defaults={
                        'description': f'Auto-created from target gruppo field',
                        'color': self._get_default_color(gruppo),
                        'icon': self._get_default_icon(gruppo),
                    }
                )

                # Aggiungi il target al gruppo
                target_group.targets.add(target)

        return target

    def _get_default_color(self, gruppo):
        """Restituisce un colore di default basato sul tipo di gruppo"""
        colors = {
            'web': '#10b981',       # green
            'db': '#3b82f6',        # blue
            'dns': '#8b5cf6',       # purple
            'storage': '#f59e0b',   # amber
            'mail': '#ef4444',      # red
            'backup': '#6366f1',    # indigo
            'monitoring': '#06b6d4', # cyan
            'proxy': '#ec4899',     # pink
            'vpn': '#14b8a6',       # teal
            'firewall': '#f97316',  # orange
            'application': '#84cc16', # lime
            'cache': '#a855f7',     # fuchsia
            'queue': '#f43f5e',     # rose
            'other': '#6b7280',     # gray
            'custom': '#3b82f6',    # blue
        }
        return colors.get(gruppo, '#3b82f6')

    def _get_default_icon(self, gruppo):
        """Restituisce un'icona di default basata sul tipo di gruppo"""
        icons = {
            'web': 'globe',
            'db': 'database',
            'dns': 'globe',
            'storage': 'hard-drive',
            'mail': 'server',
            'backup': 'hard-drive',
            'monitoring': 'shield',
            'proxy': 'layers',
            'vpn': 'shield',
            'firewall': 'shield',
            'application': 'layers',
            'cache': 'server',
            'queue': 'layers',
            'other': 'box',
            'custom': 'server',
        }
        return icons.get(gruppo, 'server')


class WhitelistEntrySerializer(serializers.ModelSerializer):
    """Serializer per WhitelistEntry"""
    
    target_ip = serializers.CharField(source='target.ip_address', read_only=True)
    target_hostname = serializers.CharField(source='target.hostname', read_only=True)
    is_subnet = serializers.ReadOnlyField()
    
    class Meta:
        model = WhitelistEntry
        fields = [
            'id',
            'target',
            'target_ip',
            'target_hostname',
            'ip_address',
            'description',
            'added_by',
            'added_at',
            'last_seen',
            'hit_count',
            'is_active',
            'is_subnet',
        ]
        read_only_fields = [
            'added_at',
            'last_seen',
            'hit_count',
        ]
    
    def validate_ip_address(self, value):
        """
        Valida IP o CIDR notation
        Previene injection e valori malformati
        """
        value = value.strip()
        
        # Validazione lunghezza
        if len(value) > 50:
            raise serializers.ValidationError("IP address troppo lungo")
        
        # Validazione caratteri permessi
        if not re.match(r'^[0-9a-fA-F:.\/]+$', value):
            raise serializers.ValidationError(
                "Formato non valido. Usa: 192.168.1.1 o 192.168.1.0/24"
            )
        
        try:
            # Controlla se è un IP o una subnet
            if '/' in value:
                # CIDR notation
                ipaddress.ip_network(value, strict=False)
            else:
                # Singolo IP
                ipaddress.ip_address(value)
        except ValueError as e:
            raise serializers.ValidationError(f"IP o subnet non valido: {str(e)}")
        
        return value
    
    def validate_description(self, value):
        """Sanitizza descrizione (anti-XSS)"""
        if value:
            # Rimuovi caratteri potenzialmente pericolosi
            value = re.sub(r'[<>\'";]', '', value)
            value = value.strip()[:512]
        return value
    
    def validate(self, data):
        """Validazione incrociata"""
        target = data.get('target')
        ip_address = data.get('ip_address')
        
        # Verifica che non esista già
        if WhitelistEntry.objects.filter(
            target=target,
            ip_address=ip_address,
            is_active=True
        ).exists():
            raise serializers.ValidationError(
                f"L'IP {ip_address} è già nella whitelist per questo target"
            )
        
        return data


class WhitelistEntryCreateSerializer(serializers.ModelSerializer):
    """Serializer per creazione whitelist entry"""
    
    class Meta:
        model = WhitelistEntry
        fields = [
            'target',
            'ip_address',
            'description',
            'added_by',
        ]
    
    def validate_ip_address(self, value):
        """Valida IP o CIDR"""
        value = value.strip()
        
        if len(value) > 50:
            raise serializers.ValidationError("IP address troppo lungo")
        
        if not re.match(r'^[0-9a-fA-F:.\/]+$', value):
            raise serializers.ValidationError("Formato non valido")
        
        try:
            if '/' in value:
                ipaddress.ip_network(value, strict=False)
            else:
                ipaddress.ip_address(value)
        except ValueError as e:
            raise serializers.ValidationError(f"IP o subnet non valido: {str(e)}")
        
        return value


class BlockedIPSerializer(serializers.ModelSerializer):
    """Serializer per BlockedIP"""
    
    target_ip = serializers.CharField(source='target.ip_address', read_only=True)
    target_hostname = serializers.CharField(source='target.hostname', read_only=True)
    is_expired = serializers.ReadOnlyField()
    is_permanent = serializers.ReadOnlyField()
    block_reason_display = serializers.CharField(source='get_block_reason_display', read_only=True)
    
    class Meta:
        model = BlockedIP
        fields = [
            'id',
            'target',
            'target_ip',
            'target_hostname',
            'ip_address',
            'block_reason',
            'block_reason_display',
            'description',
            'blocked_by',
            'blocked_at',
            'threat_score',
            'packet_count',
            'last_attempt',
            'expires_at',
            'is_active',
            'is_expired',
            'is_permanent',
            'unblocked_at',
            'unblocked_by',
        ]
        read_only_fields = [
            'blocked_at',
            'packet_count',
            'last_attempt',
            'unblocked_at',
            'unblocked_by',
        ]
    
    def validate_ip_address(self, value):
        """
        Valida IP address
        Previene injection e valori malformati
        """
        try:
            ipaddress.ip_address(value)
        except ValueError as e:
            raise serializers.ValidationError(f"IP address non valido: {str(e)}")
        
        return value
    
    def validate_threat_score(self, value):
        """Valida threat score (0-100)"""
        if value < 0 or value > 100:
            raise serializers.ValidationError("Threat score deve essere tra 0 e 100")
        return value
    
    def validate_description(self, value):
        """Sanitizza descrizione (anti-XSS)"""
        if value:
            value = re.sub(r'[<>\'";]', '', value)
            value = value.strip()[:1000]
        return value
    
    def validate(self, data):
        """Validazione incrociata"""
        target = data.get('target')
        ip_address = data.get('ip_address')
        
        # Verifica che non sia già bloccato
        if BlockedIP.objects.filter(
            target=target,
            ip_address=ip_address,
            is_active=True
        ).exists():
            raise serializers.ValidationError(
                f"L'IP {ip_address} è già bloccato per questo target"
            )
        
        # Non permettere blocco di IP privati critici
        try:
            ip = ipaddress.ip_address(ip_address)
            if ip.is_loopback:
                raise serializers.ValidationError(
                    "Non puoi bloccare indirizzi di loopback"
                )
            if str(ip).startswith('192.168.1.1'):  # Gateway comune
                raise serializers.ValidationError(
                    "Attenzione: stai per bloccare un probabile gateway"
                )
        except ValueError:
            pass
        
        return data


class BlockedIPCreateSerializer(serializers.ModelSerializer):
    """Serializer per creazione blocco IP"""
    
    class Meta:
        model = BlockedIP
        fields = [
            'target',
            'ip_address',
            'block_reason',
            'description',
            'blocked_by',
            'threat_score',
            'expires_at',
        ]
    
    def validate_ip_address(self, value):
        """Valida IP"""
        try:
            ipaddress.ip_address(value)
        except ValueError as e:
            raise serializers.ValidationError(f"IP address non valido: {str(e)}")
        return value


class BlockedIPStatsSerializer(serializers.Serializer):
    """Serializer per statistiche IP bloccati"""
    
    total_blocked = serializers.IntegerField()
    active_blocks = serializers.IntegerField()
    expired_blocks = serializers.IntegerField()
    manual_blocks = serializers.IntegerField()
    automatic_blocks = serializers.IntegerField()
    total_packets_blocked = serializers.IntegerField()
    top_blocked_ips = serializers.ListField(child=serializers.DictField())
    blocks_by_reason = serializers.DictField()
