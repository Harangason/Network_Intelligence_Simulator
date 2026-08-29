from __future__ import annotations

from collections.abc import Callable

from ..errors import AgentCoreValidationError
from .proposal import Proposal, ProposalStatus
from .proposal_store import ProposalStore


class ApprovalBoundary:
    """Only an authenticated human actor may move a proposal to APPROVED."""

    AUTOMATED_ACTOR_MARKERS = ("agent", "orchestrator", "system", "model")

    def __init__(self, store: ProposalStore, human_check: Callable[[str], bool] | None = None) -> None:
        self.store = store
        self.human_check = human_check or self._default_human_check

    @classmethod
    def _default_human_check(cls, actor: str) -> bool:
        normalized = actor.strip().lower()
        return bool(normalized) and not any(marker in normalized for marker in cls.AUTOMATED_ACTOR_MARKERS)

    def require_human(self, actor: str) -> None:
        if not self.human_check(actor):
            raise AgentCoreValidationError("Human approval with an authenticated actor is required.")

    def approve(self, proposal_id: str, *, actor: str) -> Proposal:
        self.require_human(actor)
        proposal = self.store.get(proposal_id)
        if proposal.status != ProposalStatus.READY_FOR_REVIEW:
            raise AgentCoreValidationError("Only READY_FOR_REVIEW proposals can be approved.")
        proposal.status = ProposalStatus.APPROVED
        proposal.approved_by = actor
        return self.store.save(proposal)

    def reject(self, proposal_id: str, *, actor: str) -> Proposal:
        self.require_human(actor)
        proposal = self.store.get(proposal_id)
        proposal.status = ProposalStatus.REJECTED
        proposal.approved_by = actor
        return self.store.save(proposal)
