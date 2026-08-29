"""
Dispatch delle regole firewall verso l'agent del target via WebSocket.

Estratto da FirewallRuleViewSet (perform_create/perform_destroy) perché lo
stesso comportamento serve anche ai tool di scrittura MCP (phase 2): DB come
sorgente di verità, push all'agent se connesso, altrimenti persistenza con
is_synced=False in attesa della prossima riconciliazione.
"""

import logging

from agent_manager.services import AgentNotConnected, dispatch_command_to_agent

logger = logging.getLogger("firedog.rules_api")


def dispatch_add_rule(rule) -> bool:
    """Invia add_rule all'agent del target. True se dispatchato, False se solo DB."""
    payload = {
        "chain": rule.chain,
        "protocol": rule.protocol if rule.protocol != "all" else None,
        "action": rule.action,
        "src_ip": rule.source_ip,
        "dst_ip": rule.dest_ip,
        "dst_port": rule.port,
        "comment": rule.comment or None,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        dispatch_command_to_agent(
            rule.target, action="add_rule", payload=payload, meta={"rule_id": rule.id}
        )
        logger.info("add_rule dispatched to target %s for rule %s", rule.target.id, rule.id)
        return True
    except AgentNotConnected as e:
        logger.warning("rule %s saved DB-only: %s", rule.id, e)
        return False


def dispatch_remove_rule(target, chain, rule_number) -> bool:
    """Invia remove_rule all'agent del target. True se dispatchato, False altrimenti.

    Limite noto: `rule_number` è popolato solo dalla riconciliazione di uno
    snapshot `sync_rules` (agent_manager.consumers._reconcile_snapshot), non
    dall'ack immediato di add_rule. Cancellare una rule prima che arrivi il
    primo sync la lascia orfana su iptables: qui rimane in DB solo lo stato
    "richiesta rimozione", ma senza rule_number non c'è comando `--remove
    <chain> <num>` costruibile. Come mitigazione best-effort chiediamo
    comunque un sync_rules, così la riconciliazione successiva riporta la
    rule orfana in lista (come non-custom) invece di perderla silenziosamente.
    Fix strutturale: far rispondere l'agent con la posizione reale inserita
    sull'ack di add_rule, o rimuovere per contenuto (`iptables -D <chain>
    <spec>`) invece che per numero — richiede modifiche a dog-agent.
    """
    if not rule_number:
        dispatch_sync_rules(target)
        return False

    try:
        dispatch_command_to_agent(
            target,
            action="remove_rule",
            payload={"chain": chain, "rule_num": rule_number},
            meta={},
        )
        logger.info(
            "remove_rule dispatched to target %s chain=%s num=%s",
            target.id, chain, rule_number,
        )
        return True
    except AgentNotConnected as e:
        logger.warning("rule deleted DB-only: %s", e)
        return False


def dispatch_sync_rules(target) -> bool:
    """Chiede all'agent uno snapshot completo (firewall-manager --export-json).

    Best-effort: non solleva se l'agent non è connesso, si limita a loggare.
    Usato come fallback quando una remove_rule non può essere dispatchata
    per rule_number mancante (vedi dispatch_remove_rule).
    """
    try:
        dispatch_command_to_agent(target, action="sync_rules", payload={})
        logger.info("sync_rules dispatched to target %s", target.id)
        return True
    except AgentNotConnected as e:
        logger.warning("sync_rules non dispatchato: %s", e)
        return False
