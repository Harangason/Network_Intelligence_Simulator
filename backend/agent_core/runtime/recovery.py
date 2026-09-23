"""Classify execution failures for the user; never mask them as generic success."""
from __future__ import annotations

import asyncio


class RecoveryManager:
    def classify(self, error: BaseException) -> dict:
        import httpx
        if isinstance(error, (asyncio.TimeoutError, TimeoutError, httpx.TimeoutException)):
            return {"code": "ENGINEERING_EXECUTION_TIMEOUT", "category": "TRANSIENT_TIMEOUT",
                    "status": "BLOCKED_WITH_EXPLICIT_CAUSE", "retryable": True,
                    "message": "Der Engineering-Auftrag hat sein Zeitlimit erreicht. Der gespeicherte Projektstand bleibt erhalten; du kannst denselben Auftrag erneut fortsetzen."}
        if isinstance(error, httpx.ConnectError):
            return {"code": "ENGINEERING_REASONER_UNAVAILABLE", "category": "DEPENDENCY_UNAVAILABLE",
                    "status": "BLOCKED_WITH_EXPLICIT_CAUSE", "retryable": True,
                    "message": "Der lokale Engineering-Reasoner ist nicht erreichbar. Der Auftrag wurde gespeichert und kann nach Wiederherstellung des Dienstes fortgesetzt werden."}
        if isinstance(error, PermissionError):
            return {"code": "ENGINEERING_AUTHORIZATION_REQUIRED", "category": "AUTHORIZATION",
                    "status": "WAITING_FOR_ENGINEERING_DECISION", "retryable": False,
                    "message": "Für den nächsten Änderungsschritt fehlt eine ausdrückliche technische Freigabe."}
        return {"code": "ENGINEERING_ASSISTANT_EXECUTION_DEFECT", "category": "EXECUTION_FAILURE",
                "status": "BLOCKED_WITH_EXPLICIT_CAUSE", "retryable": True,
                "message": "Der unterstützte Engineering-Auftrag konnte nicht ausgeführt werden. Der technische Fehler wurde protokolliert; der gespeicherte Auftrag kann nach Fehlerbehebung fortgesetzt werden."}
