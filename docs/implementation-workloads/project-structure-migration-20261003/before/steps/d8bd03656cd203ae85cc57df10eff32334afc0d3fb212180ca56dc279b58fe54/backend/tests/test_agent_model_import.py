from uuid import uuid4

from backend.agent_core.api.tool_contract import Permission
from backend.engineering.agent_tools import model_import, proposal_service
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.importer import preview_import, commit_import
from backend.engineering.repository import list_objects


CONTENT = ('Hardware,Device_Type,Function,Interface,Bus,Message,Cycle_ms,DLC,Signal,Start_Bit,Length_Bits,Byte_Order,Data_Type,Factor,Offset,Unit,Min,Max\n'
           'Thermometer,EmbeddedController,Messung,Ethernet,Ethernet,Messwert,100,3,Temperature,0,16,little_endian,uint16,0.01,0,C,0,100\n'
           'Thermometer,EmbeddedController,Messung,Ethernet,Ethernet,Messwert,100,3,OperatingStatus,16,1,little_endian,boolean,1,0,code,0,1\n')


def test_agent_import_has_ui_fields_review_lineage_and_project_isolation():
    authority = ToolAuthority('agent-import-' + uuid4().hex)
    def call(handler, args=None, auth=authority):
        result = execute(auth, 'import-test', Permission.GENERATE_PROPOSAL, args or {}, handler)
        assert result.success, result.findings
        return result.data
    args = {'filename': 'temperature.csv', 'text': CONTENT, 'rationale': 'Gelieferte Temperaturmessung importieren.'}
    preview = model_import.preview(args)
    assert preview == preview_import('temperature.csv', CONTENT.encode())
    proposal = call(model_import.plan, args)
    assert proposal['status'] == 'VALIDATED', proposal['validation_result']
    assert call(lambda _: list_objects('HardwareNode')) == []
    call(lambda _: proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='human', trace_id=uuid4().hex))
    applied = call(lambda _: proposal_service.apply(proposal['proposal_id'], actor='human', trace_id=uuid4().hex))
    assert len(applied['canonical_ids']) == 6
    assert call(model_import.plan, args)['canonical_ids'] == applied['canonical_ids']
    reused = call(lambda _: commit_import(preview))
    assert reused['created'] == 0 and reused['reused'] == 6
    other = ToolAuthority('ui-import-' + uuid4().hex)
    ui = call(lambda _: commit_import(preview), auth=other)
    assert ui['created'] == 6 and ui['reused'] == 0
    for kind in ('HardwareNode', 'Function', 'Interface', 'Message', 'Signal'):
        agent_rows = call(lambda _: list_objects(kind))
        ui_rows = call(lambda _: list_objects(kind), auth=other)
        assert len(agent_rows) == len(ui_rows) == (2 if kind == 'Signal' else 1)
        for left, right in zip(sorted(agent_rows, key=lambda r: r['name']), sorted(ui_rows, key=lambda r: r['name'])):
            for field in ('name', 'domain', 'device_type', 'interface_type', 'cycle_ms', 'length_bits', 'semantic', 'data', 'quality'):
                assert left.get(field) == right.get(field), (kind, field)
        assert str(agent_rows[0]['id']) != str(ui_rows[0]['id'])
    exported = call(model_import.export_project, {'include_data': True})
    assert exported['project_id'] == authority.project_id
    assert exported['counts']['engineering_hardware_nodes'] == 1
    assert {r['name'] for r in exported['bundle']['source_data']['engineering_signals']} == {'Temperature', 'OperatingStatus'}


def test_parseable_but_invalid_sensor_function_stays_unapplied():
    authority = ToolAuthority('invalid-import-' + uuid4().hex)
    result = execute(authority, 'import', Permission.GENERATE_PROPOSAL,
                     {'filename': 'sensor.csv', 'text': CONTENT.replace('EmbeddedController', 'SensorController'),
                      'rationale': 'Datei auf fachliche Eignung prüfen.'}, model_import.plan)
    assert result.success, result.findings
    assert not result.data['validation_result']['valid']
    assert result.data['status'] == 'PROPOSED'
    rows = execute(authority, 'read', Permission.READ_MODEL, {}, lambda _: list_objects('HardwareNode'))
    assert rows.data == []
