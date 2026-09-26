"""Classify execution failures for the user; never mask them as generic success."""
from __future__ import annotations

import asyncio
import re


MAX_EXPLICIT_RESUMES = 2


def recovery_request(prompt: str) -> bool:
    return bool(re.fullmatch(r'(?:bitte\s+)?setze\s+(?:den|diesen)\s+auftrag'
        r'(?:\s+nach\s+einem\s+kontrolliert\s+transienten\s+mcp/core-fehler)?\s+fort[.!]?',
        prompt.strip(), re.I))


def recipient_resume(prompt: str, context: dict) -> dict | None:
    """Select only a supported durable recovery; never authorize a model write."""
    from .goal_resolver import recipient_repair_intent, RECIPIENT_REPAIR_OUTCOMES
    if not recovery_request(prompt) or context.get('wizard_request') or context.get('pending_decisions'):
        return None
    previous = context.get('active_workload') or {}
    goal = previous.get('goal') or {}
    failure = previous.get('failure') or {}
    supported = {'TRANSIENT_TIMEOUT': 'ENGINEERING_EXECUTION_TIMEOUT',
                 'DEPENDENCY_UNAVAILABLE': 'ENGINEERING_REASONER_UNAVAILABLE',
                 'PRECONDITION': 'ENGINEERING_RECIPIENT_PRECONDITION_FAILED'}
    if (previous.get('status') != 'BLOCKED_WITH_EXPLICIT_CAUSE'
            or not previous.get('workload_id') or previous['workload_id'] != goal.get('goal_id')
            or previous.get('project_id') != context.get('active_project_id')
            or goal.get('project_context', {}).get('project_id') != previous.get('project_id')
            or goal.get('goal_type') != 'REPAIR' or goal.get('required_outcomes') != RECIPIENT_REPAIR_OUTCOMES
            or not recipient_repair_intent(goal.get('original_request', ''))
            or failure.get('category') not in supported
            or failure.get('code') != supported.get(failure.get('category'))):
        return None
    if failure['category'] != 'PRECONDITION' and failure.get('retryable') is not True:
        return None
    prior = (previous.get('result') or {}).get('recovery') or {}
    count = prior.get('attempt_count', 0)
    if (type(count) is not int or count < 0
            or prior and (prior.get('source_workload_id') != previous['workload_id']
                          or prior.get('project_id') != previous['project_id'])):
        return None
    scan = previous.get('recipient_repair') or {}
    return {'request': prompt, 'source_workload_id': previous['workload_id'],
            'project_id': previous['project_id'], 'original_request': goal['original_request'],
            'previous_failure': dict(failure), 'attempt_count': min(count + 1, MAX_EXPLICIT_RESUMES),
            'max_attempts': MAX_EXPLICIT_RESUMES, 'blocked': count >= MAX_EXPLICIT_RESUMES,
            'proposal_id': scan.get('proposal_id'), 'model_revision': scan.get('model_revision')}


class RecoveryManager:
    def classify(self, error: BaseException) -> dict:
        import httpx
        if isinstance(error, BaseExceptionGroup):
            failures = [self.classify(child) for child in error.exceptions]
            # A task group may wrap the same actionable failure several times.
            # Mixed or unknown causes must not become a misleading retry hint.
            if failures and all(failure == failures[0] for failure in failures):
                return failures[0]
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
