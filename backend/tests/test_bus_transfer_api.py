"""Real SQL/API transfer, reload, stale preview and transactional rollback."""
import json
import os

import pytest

from backend.tests.test_bus_transfer import same_cluster, request
from backend.tests.test_engineering_api import _client

pytestmark = pytest.mark.skipif(not os.environ.get('ENGINEERING_TEST_DATABASE_URL'), reason='Requires test database')


def test_bus_transfer_persists_reloads_and_rejects_stale_preview(monkeypatch):
    from backend.engineering.project_context import activate_project, reset_project
    from backend.engineering.repository import create_object, update_object, get_object
    from backend.engineering.routing.repository import create_route, get_route, approve_routes, save_validation
    from backend.engineering.routing.validation import RoutingValidator
    from backend.engineering.workflow.service import WorkflowStatusService
    from backend.engineering.db import get_connection

    client = _client()
    project = client.environ_base['HTTP_X_PROJECT_ID']
    token = activate_project(project)
    try:
        state, objects, routes = same_cluster()
        graph = json.loads(state['context']['wizard_request']['prompt'].split(': ',1)[1])
        graph[0]['controllers'].extend(graph[1]['controllers'])
        state['context']['wizard_request']['prompt'] = '- Systemcluster-Graph: ' + json.dumps(graph[:1])
        for hw in objects['HardwareNode']:
            if hw['id'] != 'Gateway':
                hw['identity'].update(cluster_id='first',cluster_name='Antrieb',cluster_source='network-editor')
        ids = {}

        def remap(value):
            if isinstance(value, dict): return {ids.get(k, k):v if k in {'name','node_name'} else remap(v) for k,v in value.items()}
            if isinstance(value, list): return [remap(v) for v in value]
            return ids.get(value, value) if isinstance(value, str) else value

        for kind in ('HardwareNode','Interface','HardwareNetworkInterface','Message','Signal'):
            for original in objects[kind]:
                data = remap({k:v for k,v in original.items() if k != 'id'})
                if kind == 'HardwareNode':
                    data['device_type'] = {'ecu':'ECU','gateway':'Gateway','sensor':'SensorController','actuator':'ActuatorController'}[data['device_type']]
                    data['identity'] = {}
                ids[original['id']] = str(create_object(kind, data)['id'])
        for hw in objects['HardwareNode']:
            update_object('HardwareNode',ids[hw['id']],{'identity':remap(hw['identity'])})
        for route in routes:
            if route['id'] == 'AB':
                route['route'] = {'hops':[{'node_id':n,'name':n} for n in ('A','Gateway','B')],
                                  'gateways':[{'node_id':'Gateway','name':'Gateway'}]}
            data = remap({k:v for k,v in route.items() if k not in {'id','approval_state','status','validation'}})
            ids[route['id']] = str(create_route(data)['id'])
        workflow = WorkflowStatusService(project)
        workflow.get()
        with get_connection() as connection:
            connection.execute('UPDATE engineering_workflow_projects SET context=%s::jsonb WHERE project_id=%s',
                               (json.dumps(state['context']),project))
        workflow.save_parameters(state['parameters'])
        workflow.save_topology(remap(state['topology']))
        validator = RoutingValidator(project)
        status_route = ids['AB']
        validation = validator.validate(get_route(status_route), exclude_route_id=status_route)
        assert validation['valid'], validation['errors']
        save_validation(status_route, validation, actor='pytest')
        approve_routes([status_route],actor='pytest')
        before = workflow.get()
        req = remap(request())
        preview = client.post('/api/engineering/workflow/network-assignment/preview',json=req)
        assert preview.status_code == 200, preview.get_json()
        payload = {**req,'plan_token':preview.get_json()['token'],'expected_token':before['edit_tokens']['topology']}
        bad = client.put('/api/engineering/workflow/network-assignment',json={**payload,'plan_token':'stale'})
        assert bad.status_code == 409, bad.get_json()
        assert workflow.get()['topology'] == before['topology']

        # Failure at the final validation occurs after multiple SQL writes.
        # Every one of them must roll back together, including route revisions.
        original_validate = RoutingValidator.validate
        with monkeypatch.context() as patch:
            patch.setattr(RoutingValidator,'validate',lambda *a,**kw: {'valid':False,'errors':[{'message':'pytest forced validation failure'}]})
            failed = client.put('/api/engineering/workflow/network-assignment',json=payload)
        assert failed.status_code == 400, failed.get_json()
        assert workflow.get()['topology'] == before['topology']
        assert get_object('HardwareNetworkInterface',ids['ACAN_A'])['network_ref'] == 'CAN_A'
        assert get_route(status_route)['revision'] == 1
        assert RoutingValidator.validate is original_validate

        response = client.put('/api/engineering/workflow/network-assignment',json=payload)
        assert response.status_code == 200, response.get_json()
        result = response.get_json()
        assert result['assignment']['routes'] == 1
        assert all(v['valid'] for v in result['assignment']['validations'])
        reloaded = client.get('/api/engineering/workflow/network-view').get_json()
        assert reloaded['topology'] == result['topology']
        assert get_object('HardwareNetworkInterface',ids['ACAN_A'])['network_ref'] == 'CAN_B'
        changed = get_route(status_route)
        assert changed['revision'] == 2
        assert changed['source']['network_id'] == 'CAN_B'
        assert changed['approval_state'] == 'PENDING'
        assert changed['validation']['valid']
        assert get_route(ids['SensorA'])['revision'] == 1
        assert workflow.get()['context'] == before['context']
        approve_routes([status_route],actor='pytest')
        assert get_route(status_route)['approval_state'] == 'APPROVED'
        repeated = client.put('/api/engineering/workflow/network-assignment',json=payload)
        assert repeated.status_code == 409, repeated.get_json()
    finally:
        reset_project(token)
