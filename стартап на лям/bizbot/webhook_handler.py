"""Обработка webhook-уведомлений от платежных систем."""

from typing import Any, Dict


def parse_payment_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Нормализует payload входящего webhook."""
    event = payload.get("event", "unknown")
    obj = payload.get("object", {})
    return {
        "event": event,
        "payment_id": obj.get("id"),
        "status": obj.get("status", "unknown"),
        "amount": obj.get("amount", {}).get("value"),
        "raw": payload,
    }
