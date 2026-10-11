"""Create/validate the reviewable proposal; never review, apply or deploy it."""
import json
from pathlib import Path
import subprocess

folder = Path(__file__).resolve().parent
root = folder.parents[2]
preview = json.loads((folder / 'reconciliation-preview.json').read_text(encoding='utf-8'))
docker = json.loads((root / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
code = 'import json\nplan = json.loads(' + repr(json.dumps(preview, ensure_ascii=True)) + ')\n' + '''
from backend.nis.agent.tools.runtime import ToolAuthority, execute
from backend.nis.agent.api.tool_contract import Permission
from backend.nis.agent.tools import model, proposal_service

def prepare(_):
    assert model.model_revision() == plan['base_model_revision'], 'PLAN_STALE: reload and rebuild the detached plan.'
    proposal = proposal_service.create('PHYSICAL_CHANNEL_REPAIR', plan['changes'],
        'Beauftragte konsistente Anschlussreparatur nach Kapazitätsumlegung: ursprüngliche Hardwarekanäle weiterverwenden, '
        'Nachrichten und logische Schnittstellen gemeinsam zuordnen, ausschließlich überzählige erzeugte Duplikate reversibel '
        'als superseded ausmustern. Geräte, Partner, Signaldefinitionen, Kodierungen, Frame-IDs und physische Wege erhalten. '
        'Keine Objekte oder Versionshistorien löschen. Anwendung erst nach geprüftem und ausgeliefertem Software-Release.',
        evidence=[{'source': 'user-authorized-capacity-channel-reconciliation',
                   'original_connectors_preserved': plan['replacements'],
                   'implementation_workload': 'stranded-capacity-channels-20261010',
                   'production_apply_requires_new_complete_pass': True}],
        assumptions=['Die ausgemusterten Duplikate bleiben mit Versionshistorie erhalten und sind keine Reserveanschlüsse.'])
    return proposal_service.validate(proposal['proposal_id'])

result = execute(ToolAuthority('20261009072206008-4bb505f1', 'codex-authorized-maintenance'),
                 'prepare_stranded_channel_reconciliation', Permission.GENERATE_PROPOSAL, {}, prepare)
print('NIS_PREPARED_RECONCILIATION='+result.model_dump_json(), flush=True)
'''
result = subprocess.run([docker, 'exec', '-i', 'NetworkIS', 'python', '-'], input=code,
                        text=True, encoding='utf-8', capture_output=True, check=True)
records = [line.removeprefix('NIS_PREPARED_RECONCILIATION=') for line in result.stdout.splitlines()
           if line.startswith('NIS_PREPARED_RECONCILIATION=')]
assert len(records) == 1
payload = json.loads(records[0])
(folder / 'prepared-reconciliation-proposal.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
assert payload['success'], payload.get('findings')
proposal = payload['data']
print(json.dumps({'status': proposal['status'], 'proposal_id': proposal['proposal_id'],
                  'valid': proposal['validation_result']['valid'],
                  'requested': proposal['validation_result']['requested'],
                  'errors': [p for p in proposal['validation_result']['findings'] if p.get('severity') == 'ERROR'],
                  'applied': False}))
