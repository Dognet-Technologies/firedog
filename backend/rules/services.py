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
    """Invia remove_rule all'agent del target. True se dispatchato, False altrimenti."""
    if not rule_number:
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
