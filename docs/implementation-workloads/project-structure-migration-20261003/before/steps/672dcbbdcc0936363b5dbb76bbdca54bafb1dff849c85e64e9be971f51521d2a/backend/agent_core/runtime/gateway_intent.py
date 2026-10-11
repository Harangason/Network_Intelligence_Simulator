"""Bounded explicit selected-gateway outage intent, not inferred fault authority."""
import re


OUTCOMES = ['selected_gateway_resolved', 'fault_scenario_created', 'simulation_completed',
            'trace_created', 'affected_routes_identified', 'findings_created']


def gateway_outage_intent(text: str) -> bool:
    return bool(re.fullmatch(
        r'(?:bitte\s+)?simuliere\s+den\s+ausfall\s+(?:dieses|des\s+ausgewählten|des\s+ausgewaehlten)'
        r'\s+gateways\s+und\s+zeige\s+(?:mir\s*)?,?\s*welche\s+kommunikation\s+betroffen\s+ist[.!]?',
        text.strip(), re.I))
