"""Canonical PostgreSQL addresses reach the executable transport configuration."""
import os
from uuid import uuid4
import pytest
from backend.engineering.project_context import activate_project, reset_project
from backend.engineering.routing.config_builder import CommunicationConfigBuilder
from backend.engineering.addressing import create_technology_address_binding, LogicalNodeAddressAllocator
from backend.engineering.repository import create_object
from backend.engineering.workflow.service import WorkflowStatusService
from hardware_profile import normalize_hardware_config
from universal_trace import generate_universal_events
from backend.engineering.models import EngineeringValidationError


@pytest.mark.parametrize('version', [4, 6])
def test_canonical_binding_to_port_to_packet(version):
    if not os.environ.get('DATABASE_URL'):
        pytest.skip('isolated PostgreSQL required')
    project = 'astra-ip-bindings-' + uuid4().hex
    token = activate_project(project)
    try:
        WorkflowStatusService(project).get()
        endpoints = []
        for index in range(2):
            node = create_object('HardwareNode', {'name': f'IP Node {index}', 'device_type': 'ECU', 'device_class': 3, 'diagnostic_addressable': True})
            LogicalNodeAddressAllocator().assign_address(str(node['id']))
            interface = create_object('HardwareNetworkInterface', {'name': f'Eth {index}', 'hardware_node_id': str(node['id']),
                'technology': 'Ethernet', 'network_ref': 'ip-net', 'status': 'CONFIGURED', 'physical_port_ref': f'connector-{index}'})
            ip = f'192.0.2.{10+index}' if version == 4 else f'2001:db8::{10+index}'
            binding = create_technology_address_binding({'hardware_node_id': str(node['id']), 'hardware_interface_ref': str(interface['id']),
                'network_ref': 'ip-net', 'technology': f'IPV{version}', 'technology_address': ip})
            endpoints.append((str(node['id']), str(interface['id']), ip, str(binding['id'])))
        source, target = endpoints
        route = {'id': str(uuid4()), 'route_code': 'RT-IP', 'approval_state': 'APPROVED',
            'source': {'node_id': source[0], 'port_id': source[1], 'network_id': 'ip-net', 'protocol': 'ETHERNET'},
            'destinations': [{'node_id': target[0], 'port_id': target[1]}], 'timing': {'cycle_time_ms': 10}}
        config = CommunicationConfigBuilder().build([route])['config']
        config.update(duration_s=.01)
        _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1700000000)
        assert events[0]['src_ip'] == source[2]
        assert events[0]['dst_ips'] == [target[2]]
        assert events[0]['ip_version'] == version
        assert events[0]['sender_port'].endswith('connector-0')
        assert all(e['ethernet']['source']['ip_provenance'] == 'configured' for e in events)
        create_technology_address_binding({'hardware_node_id': source[0], 'hardware_interface_ref': source[1], 'network_ref': 'ip-net',
            'technology': f'IPV{version}', 'technology_address': source[2] + '0'})
        with pytest.raises(EngineeringValidationError, match='Widersprüchliche'):
            CommunicationConfigBuilder().build([route])
    finally:
        reset_project(token)
