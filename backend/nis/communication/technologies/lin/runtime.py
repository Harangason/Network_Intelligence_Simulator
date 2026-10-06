"""LIN poll-slot alignment for the existing simulated schedule."""
from math import ceil

def next_poll_start(transmit_start, slot):
    period_s, offset_s = float(slot["period_ms"]) / 1000, float(slot["offset_ms"]) / 1000
    return offset_s + max(0, ceil((transmit_start - offset_s) / period_s - 1e-9)) * period_s


def initial_release_priority(event):
    return float(event.get('configured_cycle_ms') or 0) if event.get('technology') == 'lin' else 0
