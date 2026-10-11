"""Pending trace events with one arbitration grant per physical CAN bus.

CAN requests enter a release heap, then a priority heap when their bus can
transmit. A busy bus is represented once in the global queue; its waiting
frames are never individually rescheduled after every transmission.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import heapq
from typing import Any

from simulation_cancellation import check_cancellation


@dataclass
class _CanBus:
    future: list = field(default_factory=list)
    ready: list = field(default_factory=list)
    generation: int = 0
    scheduled_at: float | None = None
    last_grant: float = 0.0


@dataclass(frozen=True)
class _BusGrant:
    network: str
    generation: int


class EventScheduler:
    def __init__(self, events: list[dict[str, Any]], network_available_at: dict[str, float]):
        self._available = network_available_at
        self._pending: list = []
        self._buses: dict[str, _CanBus] = {}
        self._serial = 0
        self._active_bus: str | None = None
        for event in events:
            check_cancellation()
            self.enqueue(event)

    def _next_serial(self) -> int:
        self._serial += 1
        return self._serial

    def enqueue(self, event: dict[str, Any]) -> None:
        release = float(event["time_s"])
        serial = self._next_serial()
        if event.get("technology") not in {"can", "can_fd"}:
            heapq.heappush(self._pending, (release, serial, event))
            return
        network = str(event["network"])
        bus = self._buses.setdefault(network, _CanBus())
        heapq.heappush(bus.future, (release, serial, event))
        self._schedule(network, bus)

    def _schedule(self, network: str, bus: _CanBus) -> None:
        # The caller is still serializing this bus's current frame. ACKs and
        # forwarded segments may arrive before its completion is observed.
        if self._active_bus == network or not (bus.future or bus.ready):
            return
        due = max(bus.last_grant, self._available.get(network, 0.0))
        if not bus.ready:
            due = max(due, bus.future[0][0])
        if bus.scheduled_at == due:
            return
        bus.generation += 1
        bus.scheduled_at = due
        heapq.heappush(self._pending, (due, self._next_serial(), _BusGrant(network, bus.generation)))

    def pop(self) -> dict[str, Any] | None:
        # _serialize_event updates the shared wire availability in between
        # calls. Schedule the next grant only after that actual completion.
        if self._active_bus is not None:
            network, self._active_bus = self._active_bus, None
            self._schedule(network, self._buses[network])
        while self._pending:
            check_cancellation()
            due, _, entry = heapq.heappop(self._pending)
            if not isinstance(entry, _BusGrant):
                return entry
            bus = self._buses[entry.network]
            if entry.generation != bus.generation:
                continue
            bus.scheduled_at = None
            if due < self._available.get(entry.network, 0.0) - 1e-12:
                self._schedule(entry.network, bus)
                continue
            bus.last_grant = due
            while bus.future and bus.future[0][0] <= due + 1e-12:
                check_cancellation()
                release, serial, event = heapq.heappop(bus.future)
                identifier = event.get("arbitration_id")
                priority = int(identifier) if identifier is not None else 0x20000000
                # Equal CAN ID and route use release order, then insertion
                # order. Heap-array position is not an arbitration rule.
                heapq.heappush(bus.ready, (priority, str(event["route_id"]), release, serial, event))
            self._active_bus = entry.network
            return heapq.heappop(bus.ready)[-1]
        return None
