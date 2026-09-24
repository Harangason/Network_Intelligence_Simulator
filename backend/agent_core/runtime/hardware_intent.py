"""Bounded single-device intents; richer requests remain with the planner.

Only a complete match is executable. Purpose text is preserved as a requirement,
not interpreted as a signal, transport binding or acquisition implementation.
"""
import re

_DEVICE_TYPES = {"ecu": "ECU", "controller": "EmbeddedController", "plc": "PLC"}
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
