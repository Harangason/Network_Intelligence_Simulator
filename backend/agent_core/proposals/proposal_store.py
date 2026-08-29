from __future__ import annotations

from typing import Protocol

from .proposal import Proposal


class ProposalStore(Protocol):
    def save(self, proposal: Proposal) -> Proposal: ...

    def get(self, proposal_id: str) -> Proposal: ...


class InMemoryProposalStore:
    def __init__(self) -> None:
        self._items: dict[str, Proposal] = {}

    def save(self, proposal: Proposal) -> Proposal:
        self._items[proposal.proposal_id] = proposal
        return proposal

    def get(self, proposal_id: str) -> Proposal:
        return self._items[proposal_id]
