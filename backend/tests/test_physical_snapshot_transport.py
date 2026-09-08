from copy import deepcopy
from contextlib import contextmanager
import pytest

from backend.engineering import simulation
from backend.engineering.routing import config_builder
from hardware_profile import normalize_hardware_config, validate_hardware_profile
from universal_trace import generate_universal_events


def test_reviewed_split_reaches_snapshot_and_reduces_real_queue(monkeypatch):
    nodes = [{'id': n, 'name': n, 'device_type': 'ECU'} for n in ('a', 'b', 'c')]
    interfaces = [{'id': n+'-if', 'hardware_node_id': n, 'interface_type': 'CAN_FD', 'configuration': {}} for n in ('a', 'b', 'c')]
    interfaces.append({'id': 'unused-eth', 'hardware_node_id': 'a', 'interface_type': 'ETHERNET', 'configuration': {}})
    routes = [{'id': f'r{i}', 'route_code': f'R{i}', 'approval_state': 'APPROVED', 'source': {'node_id': source, 'interface_id': source+'-if', 'network_id': 'old', 'protocol': 'CAN_FD'},
        'destinations': [{'node_id': target, 'interface_id': target+'-if'}], 'payload': {'payload_bytes': 8}, 'timing': {'cycle_time_ms': 10}} for i,(source,target) in enumerate([('a','b'),('c','a')])]
    model = {'nodes': nodes, 'interfaces': interfaces, 'routes': routes, 'messages': [], 'signals': [], 'behaviors': [], 'functions': []}
    class Connection:
        def execute(self, sql, args):
            self.rows = nodes if 'FROM engineering_hardware_nodes ' in sql else interfaces if 'FROM engineering_interfaces ' in sql else []
            return self
        def fetchall(self):
            return deepcopy(self.rows)
    @contextmanager
    def connection():
        yield Connection()
    monkeypatch.setattr(config_builder, 'get_connection', connection)
    monkeypatch.setattr(simulation, 'load_engineering_simulation_model', lambda _: deepcopy(model))
    topology = {'nodes': [{'id': n, 'engineeringId': n, 'ports': [{'id': n+str(i), 'hardwareInterfaceId': n+'-hw', 'bus': 'can_fd', 'physicalNetworkId': 'shared'} for i in range(2)]} for n in ('a','b','c')],
        'edges': [{'id': f'e{i}', 'routingEntryId': f'r{i}', 'source': source, 'target': target, 'sourcePort': source+str(i), 'targetPort': target+str(i), 'bus': 'can_fd', 'physicalNetworkId': 'shared'} for i,(source,target) in enumerate([('a','b'),('c','a')])]}
    monkeypatch.setattr('backend.engineering.workflow.service.WorkflowStatusService.get', lambda _: {'topology': deepcopy(topology), 'parameters': {'technology': 'can_fd', 'bitrate': 100000}})
    def execute():
        frozen = simulation.prepare_workflow_simulation_config({'duration_s': .04, 'seed': 0}, 'qa')
        profile = normalize_hardware_config(frozen)
        assert validate_hardware_profile(profile)['valid']
        return frozen, generate_universal_events(frozen, profile, start_utc=1700000000)[1]
    before, before_events = execute()
    assert {e['network'] for e in before_events} == {'shared'}
    for index, edge in enumerate(topology['edges']):
        edge['physicalNetworkId'] = f'split-{index}'
    for node in topology['nodes']:
        for index, port in enumerate(node['ports']):
            port['physicalNetworkId'] = f'split-{index}'
    after, after_events = execute()
    assert {e['network'] for e in after_events} == {'split-0', 'split-1'}
    assert max(e['queue_delay_ms'] for e in after_events) < max(e['queue_delay_ms'] for e in before_events)
    assert len(after['hardware']['devices'][0]['interfaces']) == 2
    assert all(i['id'] != 'unused-eth' for n in after['hardware']['devices'] for i in n['interfaces'])
    assert routes[0]['source']['network_id'] == 'old', 'Snapshot projection must not mutate canonical data'


def test_hardware_validation_failure_is_not_a_completed_simulation(monkeypatch, tmp_path):
    from backend.app.simulation_service import SimulationService
    service = SimulationService()
    monkeypatch.setattr(service, 'prepare_config', lambda *_: {})
    monkeypatch.setattr(service.simulator, 'run', lambda *_, **__: {'status': 'validation_failed', 'hardware_validation': {'valid': False, 'findings': [{'severity': 'error', 'message': 'unknown network'}]}})
    with pytest.raises(ValueError, match='Hardware-Validierung.*unknown network'):
        service.run({}, tmp_path)
