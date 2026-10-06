"""CAN release queues and CAN-ID arbitration; no inferred priority."""
from dataclasses import dataclass, field
import heapq
from backend.nis.simulation.simulation_cancellation import check_cancellation

@dataclass
class _CanBus:
    future: list = field(default_factory=list)
    ready: list = field(default_factory=list)
    generation: int = 0
    scheduled_at: float | None = None
    last_grant: float = 0.0

def supports_event(event):
    return event.get('technology') in {'can', 'can_fd'}

def grant(bus, due):
    while bus.future and bus.future[0][0] <= due + 1e-12:
        check_cancellation()
        release, serial, event = heapq.heappop(bus.future)
        identifier = event.get('arbitration_id')
        priority = int(identifier) if identifier is not None else 0x20000000
        heapq.heappush(bus.ready, (priority, str(event['route_id']), release, serial, event))
    return heapq.heappop(bus.ready)[-1]
