"""Analysis windows read the frozen source without transferring a whole trace."""
from uuid import uuid4
from psycopg.types.json import Jsonb
from backend.nis.app import create_app
from backend.nis.infrastructure.persistence.db import get_connection
from backend.nis.workflow.services.service import WorkflowStatusService
from backend.tests.test_model_ownership import db_project


def test_analysis_projection_is_scoped_and_preserves_frozen_result(db_project):
    service = WorkflowStatusService(db_project)
    service.get(summary=True)
    snapshot = str(uuid4())
    config = {'networks': [{'id': 'bus', 'technology': 'LIN', 'bitrate': 19200}]}
    metrics = [{'network_id': 'bus', 'peak_load_percent': 31.25}]
    points = [{'network_id': 'bus', 'time_s': .125, 'load_percent': 18.75}]
    result = {'runtime_metrics': {'networks': metrics}, 'model_simulation': {
        'bus_load': points, 'frames': [{'do_not_transfer': True}] * 2000,
        'signals': [{'do_not_transfer': True}] * 2000}}
    with get_connection() as connection:
        connection.execute('INSERT INTO engineering_simulation_snapshots '
                           '(id, project_id, source_versions, configuration, result) VALUES '
                           '(%s,%s,%s,%s,%s)', (snapshot, db_project, Jsonb({'simulation': 0}), Jsonb(config), Jsonb(result)))
    projection = service.get_simulation_snapshot(snapshot, configuration_only=True)
    assert projection['configuration'] == config
    assert projection['analysis_network_metrics'] == metrics
    assert projection['analysis_bus_load'] == points
    assert 'result' not in projection and 'calculated_metrics' not in projection
    assert service.get_simulation_snapshot(snapshot)['result'] == result
    assert WorkflowStatusService('other-' + db_project).get_simulation_snapshot(snapshot, configuration_only=True) is None
    client = create_app(testing=True).test_client()
    path = f'/api/engineering/workflow/simulation-snapshots/{snapshot}?view=configuration'
    response = client.get(path, headers={'X-Project-ID': db_project})
    assert response.status_code == 200 and response.get_json() == projection
    assert client.get(path, headers={'X-Project-ID': 'other-' + db_project}).status_code == 404
    assert client.get(path.split('?')[0], headers={'X-Project-ID': db_project}).get_json()['result'] == result


def test_imported_sequence_preserves_original_names_and_event_identity(tmp_path, monkeypatch):
    from backend.nis.traces import trace_sessions
    import json
    monkeypatch.setattr(trace_sessions, 'session_root', lambda: tmp_path)
    records=[{'time_s':i/10,'time_basis':'clock-a','source_name':'Sensor',
              'destination_names':['Controller'],'message_name':'Druckbericht',
              'message_id':'pressure-message','signals':[{'signal_id':'pressure','signal':'Druck','value':i}]} for i in range(4)]
    source=tmp_path/'source.jsonl'
    data='\n'.join(json.dumps(r) for r in records).encode()
    source.write_bytes(data)
    result=trace_sessions.persist_import(data, 'source.jsonl', source)
    events=result['events']; sequence=result['sequence_model']['events']
    assert [e['id'] for e in sequence] == [e['event_id'] for e in events]
    assert all(e['source']=='Sensor' and e['destination']=='Controller' and e['route']=='Druckbericht' for e in sequence)
    assert [e['timeS'] for e in sequence] == [e['timestamp'] for e in events]
