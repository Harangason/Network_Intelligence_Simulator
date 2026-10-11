"""Bounded single-device intents; richer requests remain with the planner.

Only a complete match is executable. Purpose text is preserved as a requirement,
not interpreted as a signal, transport binding or acquisition implementation.
"""
import re

_DEVICE_TYPES = {"ecu": "ECU", "controller": "EmbeddedController", "plc": "PLC"}
_CHANNEL = re.compile(
    r'(?:bitte\s+)?(?:füge|fuege)\s+(?:dem|der)\s+(?P<hardware>[^\n;!?]{1,100}?)\s+'
    r'einen\s+(?P<ordinal>ersten|zweiten|dritten|vierten|fünften|fuenften|\d{1,3}\.)\s+'
    r'(?P<technology>[A-Za-z0-9][A-Za-z0-9 _-]{0,40}?)[ -]Kanal\s+hinzu[.!]?', re.I,
)
_ORDINALS = {'ersten': 1, 'zweiten': 2, 'dritten': 3, 'vierten': 4, 'fünften': 5, 'fuenften': 5}


def hardware_channel_intent(prompt: str) -> dict | None:
    """Parse an explicit channel request; do not resolve hardware or capacity."""
    match = _CHANNEL.fullmatch(prompt.strip())
    if not match or re.search(r'\b(?:nicht|kein\w*|ohne|statt|und|oder)\b', prompt, re.I):
        return None
    ordinal = match['ordinal'].casefold()
    channel = _ORDINALS.get(ordinal) or int(ordinal.rstrip('.'))
    if channel < 1:
        return None
    return {'hardware_reference': match['hardware'].strip(' "\''),
            'technology': match['technology'].strip(), 'channel_index': channel}

_SIMPLE = re.compile(
    r"(?:bitte\s+)?(?:erstelle|erzeuge|lege)\s+(?:eine[n]?|ein|1)\s+"
    r"(?P<device>ECU|Controller|PLC)(?:\s+an)?"
    r"(?:\s+(?:für|zur)\s+(?:die\s+)?(?P<purpose>Datenerfassung|Datenaufnahme|Messwerterfassung)"
    r"(?:\s+(?:des|eines|der|einer)\s+(?P<context>Fahrzeugs?|Roboters?|Drohne|Anlage|Maschine|Gebäudes?))?)?"
    r"(?:\s+an)?(?:[.;]?\s+Statusanschluss\s+(?P<technology>[A-Za-z0-9_-]+)"
    r"\s*,?\s+Statuszyklus\s+(?P<cycle>\d+(?:[.,]\d+)?)\s*ms)?[.!]?", re.I,
)


def simple_hardware_intent(prompt: str) -> dict | None:
    match = _SIMPLE.fullmatch(prompt.strip())
    if not match:
        return None
    device_type = _DEVICE_TYPES[match['device'].casefold()]
    return {"device_type": device_type,
            "name": device_type + ("_Datenerfassung" if match['purpose'] else "_01"),
            "description": prompt.strip(),
            "status_technology": match['technology'],
            "status_cycle_ms": float(match['cycle'].replace(',', '.')) if match['cycle'] else None,
            "acquisition_requested": bool(match['purpose'])}


def resume_hardware_request(prompt: str, context: dict) -> tuple[str, str | None]:
    previous = context.get('active_workload') or {}
    goal = previous.get('goal') or {}
    if (context.get('wizard_request') or previous.get('status') != 'WAITING_FOR_ENGINEERING_DECISION'
            or previous.get('project_id') != context.get('active_project_id')
            or goal.get('goal_type') != 'CREATE_HARDWARE'
            or not re.fullmatch(r'Statusanschluss\s+[A-Za-z0-9_-]+\s*,?\s+Statuszyklus\s+\d+(?:[.,]\d+)?\s*ms[.!]?', prompt.strip(), re.I)):
        return prompt, None
    original = goal.get('original_request', '')
    intent = simple_hardware_intent(original)
    if not intent or intent['status_technology']:
        return prompt, None
    return original.rstrip('.!') + '. ' + prompt.strip(), previous.get('workload_id')
