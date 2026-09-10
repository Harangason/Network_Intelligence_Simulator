from backend.engineering.agent_tools import generation
from backend.engineering.device_communication import ECU_STATES, communication_findings


def test_camera_and_function_generators_share_the_wizard_status_contract(monkeypatch):
    monkeypatch.setattr(generation.proposals, 'create', lambda kind, changes, *args, **kwargs: changes)
    for changes in [generation.functions({'prompt': 'Erzeuge 1 Funktion zur Temperaturüberwachung.'}),
                    generation.camera_architecture({'coverage': 'surround', 'profile': 'four_wide', 'outputs': ['status']})]:
        graph = {kind: {} for kind in ('HardwareNode', 'Function', 'Interface', 'Message', 'Signal')}
        for change in changes:
            kind = change['object_type']
            if kind in graph:
                key = '$' + change['local_ref']
                graph[kind][key] = {**change['data'], 'id': key}
        assert not communication_findings(graph)
        assert len(graph['Signal']) == len(graph['HardwareNode'])
        for signal in graph['Signal'].values():
            assert signal['data']['enum_values'] == ECU_STATES
            assert signal['configuration']['template'] == 'canonical-device-status-v1'
            assert signal['length_bits'] == 4
            assert signal['semantic']['meaning'] == 'Betriebszustand'
