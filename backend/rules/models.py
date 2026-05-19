"""
Models per l'app Rules
Gestione delle regole firewall iptables
"""

from django.db import models
from django.core.validators import (
    validate_ipv46_address,
    MinValueValidator,
    MaxValueValidator,
)
from targets.models import Target


class FirewallRule(models.Model):
    """
    Regola firewall iptables su un target specifico
    """

    CHAIN_CHOICES = [
        ("INPUT", "INPUT"),
        ("OUTPUT", "OUTPUT"),
        ("FORWARD", "FORWARD"),
    ]

    PROTOCOL_CHOICES = [
        ("tcp", "TCP"),
        ("udp", "UDP"),
        ("icmp", "ICMP"),
        ("all", "ALL"),
    ]

    ACTION_CHOICES = [
        ("ACCEPT", "ACCEPT"),
        ("DROP", "DROP"),
        ("REJECT", "REJECT"),
    ]

    # Relazione con target
    target = models.ForeignKey(
        Target,
        on_delete=models.CASCADE,
        related_name="firewall_rules",
        help_text="Target su cui applicare la regola",
    )

    # Identificazione regola
    chain = models.CharField(
        max_length=10, choices=CHAIN_CHOICES, db_index=True, help_text="Chain iptables"
    )
    rule_number = models.PositiveIntegerField(
        null=True, blank=True, help_text="Numero della regola nella chain"
    )

    # Configurazione regola
    protocol = models.CharField(
        max_length=10,
        choices=PROTOCOL_CHOICES,
        default="tcp",
        help_text="Protocollo di rete",
    )

    port = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        help_text="Porta di destinazione",
    )

    source_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        validators=[validate_ipv46_address],
        help_text="IP sorgente",
    )

    dest_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        validators=[validate_ipv46_address],
        help_text="IP destinazione",
    )

    action = models.CharField(
        max_length=10,
        choices=ACTION_CHOICES,
        default="ACCEPT",
        help_text="Azione della regola",
    )

    # Metadata
    comment = models.CharField(
        max_length=256, blank=True, help_text="Commento descrittivo della regola"
    )

    is_custom = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Indica se è una regola custom o predefinita",
    )

    # Stato sincronizzazione
    is_synced = models.BooleanField(
        default=False, help_text="Indica se la regola è sincronizzata sul target"
    )

    # Origine: se la regola è stata creata via "Add Group Rule" punta al gruppo
    # che l'ha generata. Le regole single-target hanno questo a NULL.
    group_origin = models.ForeignKey(
        "targets.TargetGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applied_rules",
        help_text=(
            "Gruppo da cui questa rule è stata propagata. NULL = rule creata "
            "direttamente sul singolo target."
        ),
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["target", "chain", "rule_number"]
        indexes = [
            models.Index(fields=["target", "chain"]),
            models.Index(fields=["target", "is_custom"]),
            models.Index(fields=["is_synced"]),
        ]
        verbose_name = "Firewall Rule"
        verbose_name_plural = "Firewall Rules"

    def __str__(self):
        port_info = f":{self.port}" if self.port else ""
        src_info = f" from {self.source_ip}" if self.source_ip else ""
        dst_info = f" to {self.dest_ip}" if self.dest_ip else ""
        return f"{self.chain} {self.protocol}{port_info}{src_info}{dst_info} -> {self.action}"

    @property
    def rule_description(self):
        """Descrizione leggibile della regola"""
        parts = [self.chain, self.protocol.upper()]

        if self.port:
            parts.append(f"port {self.port}")

        if self.source_ip:
            parts.append(f"from {self.source_ip}")

        if self.dest_ip:
            parts.append(f"to {self.dest_ip}")

        parts.append(f"-> {self.action}")

        return " ".join(parts)

    def to_iptables_command(self):
        """
        Genera il comando iptables per questa regola
        """
        cmd_parts = ["iptables"]

        # Aggiungi alla chain
        if self.rule_number:
            cmd_parts.extend(["-I", self.chain, str(self.rule_number)])
        else:
            cmd_parts.extend(["-A", self.chain])

        # Protocollo
        if self.protocol != "all":
            cmd_parts.extend(["-p", self.protocol])

        # Porta
        if self.port:
            if self.chain == "INPUT":
                cmd_parts.extend(["--dport", str(self.port)])
            elif self.chain == "OUTPUT":
                cmd_parts.extend(["--dport", str(self.port)])

        # IP sorgente
        if self.source_ip:
            cmd_parts.extend(["-s", self.source_ip])

        # IP destinazione
        if self.dest_ip:
            cmd_parts.extend(["-d", self.dest_ip])

        # Connection tracking per nuove connessioni
        if self.action == "ACCEPT" and self.protocol in ["tcp", "udp"]:
            cmd_parts.extend(["-m", "conntrack", "--ctstate", "NEW"])

        # Azione
        cmd_parts.extend(["-j", self.action])

        # Commento
        if self.comment:
            cmd_parts.extend(["-m", "comment", "--comment", self.comment[:256]])

        return " ".join(cmd_parts)
