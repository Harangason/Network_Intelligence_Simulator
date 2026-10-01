"""Project planning limits. These are configurable simulation inputs, not protocol claims."""
from __future__ import annotations

import json
import re

DEFAULT_BUS_PARTICIPANT_LIMITS = {
    'can': 64, 'can_fd': 64, 'can_xl': 64, 'lin': 64,
    'automotive_ethernet': 256, 'flexray': 64,
}


def bus_key(value: str) -> str:
    key = re.sub(r'[^a-z0-9]', '', str(value).lower().removeprefix('detected:'))
    return {'canfd': 'can_fd', 'canxl': 'can_xl', 'ethernet': 'automotive_ethernet',
            'automotiveethernet': 'automotive_ethernet', 'someip': 'automotive_ethernet'}.get(key, key)


def normalize_bus_limits(value=None) -> dict[str, int]:
    result = dict(DEFAULT_BUS_PARTICIPANT_LIMITS)
    if value is None:
        return result
    if not isinstance(value, dict):
        raise ValueError('Bus-Teilnehmergrenzen müssen ein Objekt sein.')
    for technology, limit in value.items():
        key = bus_key(technology)
        if key not in result:
            raise ValueError(f'Unbekannter Bustyp: {technology}')
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0 or limit == 1 or limit > 100000:
            raise ValueError('Teilnehmergrenzen müssen 0 (unbegrenzt) oder ganze Zahlen von 2 bis 100000 sein.')
        result[key] = limit
    return result


def limits_from_prompt(prompt: str) -> dict[str, int]:
    match = re.search(r'^- Bus-Teilnehmergrenzen:\s*(\{[^\r\n]*\})\s*$', prompt, re.M)
    return normalize_bus_limits(json.loads(match.group(1)) if match else None)


def branch_capacity(limits: dict, technology: str) -> int:
    """Reserve one participant for the gateway/controller on a shared segment."""
    total = limits.get(bus_key(technology), 0)
    return total - 1 if total else 100000


def with_project_limits(prompt: str, context: dict) -> str:
    """Freeze planning settings into an agent request unless already specified."""
    if re.search(r"^- Bus-Teilnehmergrenzen:", prompt, re.M):
        limits_from_prompt(prompt)
        return prompt
    settings = context.get("engineering_wizard_settings") or {}
    limits = normalize_bus_limits(settings.get("bus_participant_limits"))
    return prompt.rstrip() + "\n- Bus-Teilnehmergrenzen: " + json.dumps(limits, sort_keys=True) + "\n"
