"""Explicit planning decisions, distinct from physically available inventory."""
from collections import Counter
import hashlib
import json

from .network_planning import canonical_protocol, physical_network_inventory, communication_system_inventory


def planning_inventory(state: dict, prompt: str = '') -> dict:
    wizard = (state.get('context') or {}).get('agent_wizard_status') or {}
    return communication_system_inventory(wizard.get('agent_prompt') or prompt)


def planning_policy(state: dict) -> dict:
    raw = (state.get('parameters') or {}).get('network_resource_policy')
    if raw is None:
        raw = {'mode': 'AUTO_SIZE'}
    if not isinstance(raw, dict):
        raise ValueError('network_resource_policy muss ein Objekt sein.')
    mode = str(raw.get('mode') or 'AUTO_SIZE').upper()
    if mode not in {'AUTO_SIZE', 'FIXED_INVENTORY'}:
        raise ValueError('Ressourcenmodus muss AUTO_SIZE oder FIXED_INVENTORY sein.')
    limits = raw.get('hard_limits') or {}
    if not isinstance(limits, dict):
        raise ValueError('hard_limits muss Protokolle auf feste Segmentobergrenzen abbilden.')
    normalized = {}
    for protocol, count in limits.items():
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError('Feste Segmentobergrenzen müssen nichtnegative ganze Zahlen sein.')
        normalized[canonical_protocol(protocol)] = count
    return {'mode': mode, 'hard_limits': normalized}


def topology_signature(topology: dict) -> str:
    return hashlib.sha256(json.dumps(topology, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def resource_decision(before: dict, after: dict, baseline: dict, policy: dict) -> dict:
    """Recomputable receipt: never claim newly planned ports already exist."""
    old = physical_network_inventory(before)
    new = physical_network_inventory(after)
    resources = []
    for protocol in sorted(set(baseline) | set(old) | set(new)):
        baseline_count = baseline.get(protocol, 0)
        previous_count = len(old.get(protocol, set()))
        planned_count = len(new.get(protocol, set()))
        resources.append({
            'protocol': protocol, 'baseline_count': baseline_count,
            'previous_modeled_count': previous_count, 'planned_count': planned_count,
            'increase_over_baseline': max(0, planned_count - baseline_count),
            'new_segments_in_this_change': max(0, planned_count - previous_count),
            'hard_limit': policy['hard_limits'].get(protocol),
        })
    old_ports = {(str(node.get('id')), str(port.get('id')))
                 for node in before.get('nodes') or [] for port in node.get('ports') or []}
    connected_ports = {(str(edge.get(side)), str(edge.get(side + 'Port')))
                       for edge in after.get('edges') or [] for side in ('source', 'target')}
    added_ports = Counter(node for node, port in connected_ports if (node, port) not in old_ports)
    return {
        'version': 1, 'mode': policy['mode'], 'hard_limits': policy['hard_limits'],
        'decision_maker': 'deterministic-network-planner',
        'base_topology_sha256': topology_signature(before),
        'proposed_topology_sha256': topology_signature(after),
        'resources': resources,
        'additional_modeled_ports': [{'node_id': node, 'count': count} for node, count in sorted(added_ports.items())],
        'inventory_is_not_procurement': True,
        'implementation_scope': 'Planungsmodell; neue Segmente und Ports sind ausgewiesener Ressourcenbedarf, kein Nachweis real vorhandener Hardware.',
    }


def decision_summary(decision: dict) -> str:
    additions = [item for item in decision['resources'] if item['increase_over_baseline']]
    if not additions:
        return 'Tool-Entscheidung: vorhandenen Ressourcenrahmen nutzen; keine Bestandserhöhung nötig.'
    detail = '; '.join(f"{item['protocol']} {item['baseline_count']} → {item['planned_count']} Segmente "
                       f"(+{item['increase_over_baseline']} gegenüber dem Ausgangsbestand)" for item in additions)
    return ('Tool-Entscheidung: Ressourcen nach dem berechneten Topologiebedarf dimensionieren: '
            + detail + '. Neue Segmente und Ports sind Planungsbedarf, nicht bereits vorhandene Hardware.')
