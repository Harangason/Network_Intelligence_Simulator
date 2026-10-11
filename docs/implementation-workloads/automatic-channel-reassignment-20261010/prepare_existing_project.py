"""Prepare a canonical, revision-checked repair using the delivered product core."""
import argparse
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--receipt', type=Path, required=True)
args = parser.parse_args()
folder = Path(__file__).resolve().parent
root = folder.parents[2]
receipt = json.loads(args.receipt.read_text())
assert receipt['status'] == 'PASS'
docker = json.loads((root / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
running = subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()
assert running == receipt['image_id'], 'The exact tested fix must be deployed before preparing the existing-project repair.'
code = '''
import json
from backend.nis.agent.tools.runtime import ToolAuthority, execute
from backend.nis.agent.api.tool_contract import Permission
from backend.nis.agent.tools import model, proposal_service
from backend.nis.engineering.network.physical_ports import physical_transmit_changes, technology_id

def prepare(_):
    snapshot = model.model()
    by_message = {str(m['id']): m for m in snapshot['messages']}
    by_port = {str(p['id']): p for p in snapshot['hardware-interfaces']}
    changes = [change for change in physical_transmit_changes(snapshot['topology'], snapshot['routing'], snapshot['messages'])
               if 'hardware_interface_id' in change['data']]
    expected = []
    for change in changes:
        message = by_message[change['object_id']]
        before = by_port[str(message['hardware_interface_id'])]
        after = by_port[str(change['data']['hardware_interface_id'])]
        assert str(before['hardware_node_id']) == str(after['hardware_node_id']), message['name']
        assert technology_id(before['technology']) == technology_id(after['technology']), message['name']
        assert change['data']['configuration'] == message.get('configuration', {}), 'Already-approved transmission bindings must remain identical.'
        expected.append({'id': str(message['id']), 'name': message['name'], 'before': str(before['id']), 'after': str(after['id'])})
    if not changes:
        return {'status': 'UNCHANGED', 'expected': []}
    # Reconcile linked routes against the same physical topology in the same
    # canonical proposal transaction, using existing validators and audit.
    changes.append({'object_type': 'NetworkTopology', 'data': {'name': 'Freigegebene Sendepfade konsistent zuordnen',
                                                             'topology': snapshot['topology']}})
    proposal = proposal_service.create('PHYSICAL_CHANNEL_REPAIR', changes,
        'Beauftragte Fehlerkorrektur: Hauptanschlüsse der Nachrichten mit ihren bereits freigegebenen physischen Sendepfaden abgleichen. '
        'Geräte, Technologie, Nachrichten, Signale, Kodierungen, Empfänger und physische Wege bleiben erhalten.',
        evidence=[{'source': 'user-authorized-existing-project-reconciliation',
                   'user_request': 'Dies muss für alle einheitlich gelten. dann mach das produktiv, das nervt mich',
                   'primary_alignment_count': len(expected)}])
    validated = proposal_service.validate(proposal['proposal_id'])
    return {'proposal': validated, 'expected': expected}

result = execute(ToolAuthority('20261009072206008-4bb505f1', 'codex-authorized-maintenance'),
                 'prepare_approved_sender_alignment', Permission.GENERATE_PROPOSAL, {}, prepare)
print('NIS_REPAIR_RESULT=' + result.model_dump_json(), flush=True)
'''
result = subprocess.run([docker, 'exec', '-i', 'NetworkIS', 'python', '-'], input=code,
                        text=True, encoding='utf-8', capture_output=True, check=True)
records = [line.removeprefix('NIS_REPAIR_RESULT=') for line in result.stdout.splitlines() if line.startswith('NIS_REPAIR_RESULT=')]
assert len(records) == 1
payload = json.loads(records[0])
(folder / 'existing-project-prepared-proposal.json').write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
assert payload['success'] is True, payload.get('findings')
data = payload['data']
proposal = data.get('proposal') or {}
print(json.dumps({'status': proposal.get('status', data.get('status')), 'proposal_id': proposal.get('proposal_id'),
                  'revision': proposal.get('revision'), 'primary_alignment_count': len(data.get('expected', [])),
                  'validation': proposal.get('validation_result')}, ensure_ascii=True))
