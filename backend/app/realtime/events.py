"""Synchronous event-emission helpers for post-commit service hooks."""

from typing import Any

from app.realtime.manager import connection_manager


def emit_group_event(group_id: int, event_type: str, payload: dict[str, Any]) -> None:
    """Best-effort event emission that can never break a committed mutation."""
    try:
        connection_manager.broadcast_from_sync(group_id, event_type, payload)
    except Exception:
        pass


def emit_financial_updates(group_id: int) -> None:
    """Tell group members to refresh group and overall derived balances."""
    emit_group_event(group_id, "balances_updated", {})
    emit_group_event(group_id, "overall_balance_updated", {})
