"""Independent, read-only reference for the traffic-model design review.

This is not the application's capacity engine. It deliberately does not derive
traffic rates from signal names and does not claim a timing proof from average
utilization. Units are explicit: bits, milliseconds and percent.
"""
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class PeriodicTransmission:
    network_id: str
    sender_port_id: str
    message_id: str
    payload_bytes: int
    period_ms: int


def lin_nominal_bits(payload_bytes: int) -> int:
    if not isinstance(payload_bytes, int) or not 1 <= payload_bytes <= 8:
        raise ValueError('LIN data payload must contain 1..8 bytes')
    return 34 + 10 * (payload_bytes + 1)


def unique_transmissions(streams):
    """Broadcast subscribers do not create additional physical transmissions."""
    unique = {}
    for stream in streams:
        key = (stream.network_id, stream.sender_port_id, stream.message_id)
        previous = unique.setdefault(key, stream)
        if previous != stream:
            raise ValueError('Conflicting payload or period for one physical transmission')
    return list(unique.values())


def periodic_lin_demand(streams, bitrate=19200, minimum_interval_ms=20,
                        time_base_ms=5, master_jitter_ms=0):
    """Nominal demand and an explicitly assumed LIN slot reservation scenario.

    The 20 ms floor is a user-confirmed project rule, not a LIN protocol limit.
    The 5 ms time base and zero master jitter are illustrative assumptions.
    Slots are strict multiples of the time base and must exceed maximum frame
    time plus jitter (LIN 2.2A section 2.4.2). This is a necessary utilization
    check, not a constructed or verified schedule table.
    """
    if bitrate <= 0 or minimum_interval_ms <= 0 or time_base_ms <= 0 or master_jitter_ms < 0:
        raise ValueError('Invalid timing or bitrate')
    nominal = reserved = Fraction(0)
    details = []
    for stream in unique_transmissions(streams):
        if stream.period_ms <= 0:
            raise ValueError('Periodic transmission requires a positive period')
        period = max(stream.period_ms, minimum_interval_ms)
        duration = Fraction(lin_nominal_bits(stream.payload_bytes) * 1000, bitrate)
        maximum = duration * Fraction(14, 10) + Fraction(master_jitter_ms)
        slot = (maximum // time_base_ms + 1) * time_base_ms
        nominal += duration / period * 100
        reserved += slot / period * 100
        details.append({'message_id': stream.message_id, 'period_ms': period,
                        'nominal_ms': float(duration), 'reserved_slot_ms': float(slot)})
    return {'nominal_demand_percent': float(nominal), 'slot_reservation_percent': float(reserved),
            'physical_transmissions': len(details), 'details': details,
            'assessment': 'OVERLOAD' if nominal > 100 else
                          'SLOT_BUDGET_EXCEEDED' if reserved > 100 else 'SCHEDULE_NOT_VERIFIED'}


def event_load_percent(duration_ms, *, expected_events_per_second=None):
    """Unknown event frequency stays unknown; explicit zero is a valid scenario."""
    if expected_events_per_second is None:
        return None
    if duration_ms < 0 or expected_events_per_second < 0:
        raise ValueError('Event duration and rate must be nonnegative')
    return duration_ms * expected_events_per_second / 10


def serialize_can_requests(requests):
    """Illustrative lossless CAN bus grants using supplied arbitration priorities.

    Requests are (release_ms, priority, duration_ms, name), with lower priority
    numbers winning. Duration already contains the complete frame footprint and
    intermission. This models non-preemptive bus grants, not bit-level CAN,
    arbitration between frame formats, retransmissions or a worst-case proof.
    """
    waiting = sorted(requests)
    pending, timeline = [], []
    now = 0
    while waiting or pending:
        if not pending:
            now = max(now, waiting[0][0])
        while waiting and waiting[0][0] <= now:
            pending.append(waiting.pop(0))
        selected = min(pending, key=lambda row: (row[1], row[0], row[3]))
        pending.remove(selected)
        release, priority, duration, name = selected
        if duration <= 0:
            raise ValueError('Transmission duration must be positive')
        timeline.append({'name': name, 'release_ms': release, 'start_ms': now,
                         'end_ms': now + duration, 'waiting_ms': now - release})
        now += duration
    return timeline
