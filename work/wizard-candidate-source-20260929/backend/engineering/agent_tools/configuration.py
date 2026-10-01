"""Reviewable edits to declared network parameters from a direct agent goal."""
from __future__ import annotations

import re

from ...communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY
from ..workflow.service import WorkflowStatusService
from ..project_context import current_project_id
from . import proposal_service as proposals


_LIN_RATE = re.compile(r"\bLIN(?:[-\s]?Netz)?\b.{0,100}?\b(?:auf|mit)\s+"
                       r"(\d+(?:[,.]\d+)?)\s*([kKmM]?)\s*bit\s*/\s*s\b", re.I | re.S)


def plan_lin_bitrate(arguments: dict) -> dict:
    """Only a unique declared LIN network may be changed without selection."""
    request = str(arguments['requirement'])
    match = _LIN_RATE.search(request)
    if not match:
        return {'supported': False}
    multiplier = {'': 1, 'k': 1000, 'm': 1_000_000}[match.group(2).lower()]
    bitrate = round(float(match.group(1).replace(',', '.')) * multiplier)
    validation = DEFAULT_TECHNOLOGY_REGISTRY.validate_parameters('LIN', {'bitrate_bps': bitrate})
    if validation['status'] != 'VALID':
        return {'supported': True, 'status': 'BLOCKED', 'reason': 'Die angeforderte LIN-Bitrate ist laut TechnologyProfile unzulässig.',
                'findings': validation['findings']}
    parameters = WorkflowStatusService(current_project_id()).get()['parameters']
    declared = [item for item in parameters.get('networks', [])
                if DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(str(item.get('technology') or '')) == 'lin']
    if len(declared) != 1:
        reason = ('Im Projekt ist kein bearbeitbares LIN-Netz deklariert.' if not declared else
                  'Mehrere LIN-Netze sind deklariert. Bitte das gewünschte Netz mit Namen oder ID auswählen.')
        return {'supported': True, 'status': 'WAITING_FOR_ENGINEERING_DECISION', 'reason': reason,
                'candidates': [{'id': str(item['id']), 'name': str(item.get('name') or item['id'])}
                               for item in declared]}
    network = declared[0]
    if network.get('bitrate') == bitrate:
        return {'supported': True, 'status': 'ALREADY_CONFIGURED', 'network_id': str(network['id']),
                'bitrate_bps': bitrate}
    proposal = proposals.create('NETWORK_BITRATE_UPDATE', [{
        'object_type': 'Network', 'action': 'UPDATE', 'object_id': str(network['id']),
        'data': {'bitrate': bitrate}}], request,
        evidence=[{'source': 'explicit_network_bitrate',
                   'engineering_goal_id': arguments.get('workload_id'),
                   'network_id': str(network['id']), 'technology_id': 'LIN',
                   'bitrate_bps': bitrate, 'value_source': 'EXPLICIT_USER_SPECIFICATION'}])
    proposal = proposals.validate(proposal['proposal_id'])
    return {'supported': True, 'status': proposal['status'], 'proposal': proposal,
            'network_id': str(network['id']), 'bitrate_bps': bitrate}
