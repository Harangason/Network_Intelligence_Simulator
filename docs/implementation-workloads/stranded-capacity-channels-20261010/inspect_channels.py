"""Read delivered canonical data and impact; never change engineering objects."""
import json
import subprocess
from pathlib import Path

folder = Path(__file__).resolve().parent
root = folder.parents[2]
docker = json.loads((root / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
code = '''
from backend.nis.agent.tools.runtime import ToolAuthority, execute
from backend.nis.agent.api.tool_contract import Permission
from backend.nis.agent.tools import model, proposal_service
from backend.nis.infrastructure.persistence.repository import list_versions

def inspect(_):
    snapshot = model.model()
    topology = snapshot['topology']
    connected = {str(e.get(side+'Port')) for e in topology['edges'] for side in ('source', 'target')}
    active = {str(p.get('hardwareInterfaceId')) for n in topology['nodes'] for p in n.get('ports', []) if str(p['id']) in connected}
    ports = snapshot['hardware-interfaces']
    candidates = []
    for port in ports:
        if str(port['id']) in active:
            continue
        siblings = [p for p in ports if str(p['id']) in active and p['hardware_node_id'] == port['hardware_node_id']
                    and p['technology'] == port['technology'] and str(p.get('network_ref', '')).startswith(str(port.get('network_ref', ''))+'-CAP-S')]
        if not siblings:
            continue
        impact = proposal_service.impact('HardwareNetworkInterface', str(port['id']))
        def contains(value, identifier):
            if isinstance(value, dict):
                return any(contains(v, identifier) for v in value.values())
            if isinstance(value, list):
                return any(contains(v, identifier) for v in value)
            return str(value) == identifier
        references = [section for section, value in snapshot.items() if section != 'hardware-interfaces' and contains(value, str(port['id']))]
        resources = snapshot.get('communication_resources', {})
        eligible = (port['source'] == 'ai_generated' and port['lifecycle_state'] == 'draft'
                    and not impact['affected_objects'] and not references
                    and all((p.get('capabilities') or {}).get('source') == 'reviewed-physical-topology' for p in siblings))
        candidates.append({'port': port, 'replacement_channels': siblings, 'impact': impact,
                           'other_references': references, 'eligible': eligible,
                           'versions': model.json_safe(list_versions('HardwareNetworkInterface', str(port['id'])))})
    return {'snapshot': snapshot, 'model_revision': model.model_revision(), 'candidates': candidates,
            'active': len(active), 'disconnected': len(ports)-len(active)}

result = execute(ToolAuthority('20261009072206008-4bb505f1', 'codex-authorized-maintenance'),
                 'inspect_stranded_capacity_channels', Permission.READ_MODEL, {}, inspect)
print('NIS_CHANNEL_INSPECTION='+result.model_dump_json(), flush=True)
'''
result = subprocess.run([docker, 'exec', '-i', 'NetworkIS', 'python', '-'], input=code,
                        text=True, encoding='utf-8', capture_output=True, check=True)
records = [line.removeprefix('NIS_CHANNEL_INSPECTION=') for line in result.stdout.splitlines() if line.startswith('NIS_CHANNEL_INSPECTION=')]
assert len(records) == 1
payload = json.loads(records[0])
assert payload['success'], payload.get('findings')
(folder / 'canonical-inspection.json').write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
data = payload['data']
print(json.dumps({'active': data['active'], 'disconnected': data['disconnected'],
                  'eligible': sum(p['eligible'] for p in data['candidates']),
                  'ineligible': [{'name': p['port']['name'], 'references': p['other_references'],
                                  'impact': p['impact']['affected_objects']} for p in data['candidates'] if not p['eligible']]}))
