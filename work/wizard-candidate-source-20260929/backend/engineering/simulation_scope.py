"""One persisted scope contract for preflight, snapshots and simulation."""
from __future__ import annotations

from typing import Any

from .models import EngineeringValidationError


def normalize_simulation_scope(value: Any = None, *, require_reason: bool = False) -> dict:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise EngineeringValidationError("simulation_scope muss ein Objekt sein.")
    mode = str(value.get("mode") or "ALL").upper()
    if mode not in {"ALL", "MESSAGE", "SIGNAL", "SELECTED"}:
        raise EngineeringValidationError("Simulationsumfang: Modus muss ALL, MESSAGE, SIGNAL oder SELECTED sein.")
    if value.get("include_all") is True:
        mode = "ALL"
    def ids(key):
        raw = value.get(key) or []
        if not isinstance(raw, list) or any(not isinstance(item, str) or not item.strip() for item in raw):
            raise EngineeringValidationError(f"Simulationsumfang: {key} muss gültige Objekt-IDs enthalten.")
        return sorted(set(raw))
    messages, signals = ids("message_ids"), ids("signal_ids")
    reason = str(value.get("reason") or "").strip()
    if mode == "ALL":
        messages, signals, reason = [], [], ""
    elif (mode == "MESSAGE" and signals) or (mode == "SIGNAL" and messages):
        raise EngineeringValidationError("Simulationsumfang: Auswahl passt nicht zum gewählten Modus.")
    elif not messages and not signals:
        raise EngineeringValidationError("Der ausgewählte Simulationsumfang ist leer.")
    if mode != "ALL" and require_reason and not reason:
        raise EngineeringValidationError("Bitte begründen, warum die übrigen Modellobjekte vom Simulationsumfang ausgeschlossen werden.")
    return {"mode": mode, "include_all": mode == "ALL", "message_ids": messages, "signal_ids": signals, "reason": reason}
