import json
import sys

from backend.agent_core.api.tool_contract import Permission
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.agent_tools import wizard_generation
from backend.engineering import wizard_communication
from backend.engineering.workflow.service import WorkflowStatusService

project_id = sys.argv[1]

def probe(_):
    prompt = WorkflowStatusService(project_id).get()['context']['wizard_request']['prompt']
    original = wizard_communication.attach_new_message_contracts

    def inspect(original_prompt, changes, existing):
        graph = {kind: {str(row['id']): row for row in existing.get(kind, [])}
                 for kind in wizard_communication.KINDS}
        for change in changes:
            kind = change['object_type']
            if kind in graph:
                key = str(change.get('object_id') or '$' + change['local_ref'])
                graph[kind][key] = {**graph[kind].get(key, {}), **change['data']}
        rows = []
        for key, message in graph['Message'].items():
            if 'elektromotor' not in str(message.get('name', '')).casefold():
                continue
            rows.append({'ref': key, 'name': message.get('name'),
                         'message_id_hex': message.get('message_id_hex'),
                         'scope': ((message.get('configuration') or {}).get('communication_contract') or {}).get('scope'),
                         'signals': [{'ref': ref, 'name': signal.get('name'),
                                      'start_bit': signal.get('start_bit'),
                                      'length_bits': signal.get('length_bits'),
                                      'data_type': signal.get('data_type')}
                                     for ref, signal in graph['Signal'].items()
                                     if str(signal.get('message_id')) == key]})
        print(json.dumps({'messages': rows}, ensure_ascii=False), flush=True)
        return original(original_prompt, changes, existing)

    wizard_communication.attach_new_message_contracts = inspect
    try:
        wizard_generation.generate({'prompt': prompt})
    except Exception as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), flush=True)
    return {'observed': True}

result = execute(ToolAuthority(project_id, 'txrx-diagnostic'),
                 'txrx_graph_probe', Permission.GENERATE_PROPOSAL, {}, probe)
print(json.dumps({'success': result.success, 'error': str(result.error) if result.error else None}))
