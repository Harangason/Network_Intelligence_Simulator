"""Exercise the real frontend specification adapter and backend HMI contract."""
import json

from backend.nis.agent.tools.wizard_generation import extract_specification
from backend.nis.engineering.communication.wizard_communication import communication_plan
from backend.nis.engineering.communication.device_communication import actuator_command_template


def test_named_actuator_command_defaults_preserve_explicit_custom_encoding():
    default = actuator_command_template({'name': 'TelematikSchaltausgang', 'device_type': 'ActuatorController'})
    assert default['length_bits'] == 1
    assert default['data']['enum_values'] == {'CLOSE': 0, 'OPEN': 1}
    position = actuator_command_template({'name': 'TelematikStellglied', 'device_type': 'ActuatorController'})
    assert position['length_bits'] == 10 and position['factor'] == 0.1
    custom = {'source': 'wizard-generic-actuator-v1', 'length_bits': 8, 'data': {'enum_values': {'OPEN': 23}}}
    assert actuator_command_template({'name': 'TelematikSchaltausgang', 'device_type': 'ActuatorController',
                                     'identity': {'actuator_command_template': custom}})['data'] == custom['data']


def test_real_wizard_adapter_separates_disabled_hmi_outputs_before_contract_resolution():
    clusters = [{"network_id": "ethernet", "network_label": "Ethernet", "bus_name": "Anzeige",
                 "controllers": [{"ecu": name, "sensors": [], "actuators": []}
                                 for name in ("Konnektivitaet", "Infotainment", "Kombiinstrument")],
                 "hmi_routes": [
                     {"source": "Konnektivitaet", "target": "Infotainment",
                      "signals": ["BluetoothVerbindungen", "KonnektivitaetStatus", "WLANSignalstaerke"],
                      "excluded_signals": ["InternetDatenrate"]},
                     {"source": "Konnektivitaet", "target": "Kombiinstrument",
                      "signals": ["BluetoothVerbindungen", "KonnektivitaetStatus", "WLANSignalstaerke", "InternetDatenrate"],
                      "excluded_signals": []},
                 ]}]
    prompt = ('- Generierungsmodus: EXAMPLE_PROJECT\nIndustrie: Automotive\n'
              'Controller: Konnektivitaet\nController: Infotainment\nController: Kombiinstrument\n'
              '- Geräteanschlüsse: {"Konnektivitaet":"Ethernet","Infotainment":"Ethernet","Kombiinstrument":"Ethernet"}\n'
              '- Systemcluster-Graph: ' + json.dumps(clusters))
    spec = extract_specification(prompt)
    graph = {kind: {} for kind in ('HardwareNode', 'Function', 'Interface', 'Message', 'Signal')}
    for chain in spec['chains']:
        owner, interface, message = chain['hardware_name'], chain['interface_name'], chain['message_name']
        graph['HardwareNode'][owner] = {'name': owner, 'device_type': chain['device_type']}
        graph['Interface'][interface] = {'hardware_node_id': owner}
        graph['Message'][message] = {'name': message, 'interface_id': interface, 'dlc': chain['dlc'], 'configuration': {}}
        graph['Signal'][chain['signal_name']] = {'name': chain['signal_name'], 'message_id': message}
    before = json.dumps(graph, sort_keys=True)
    plan = communication_plan(prompt, graph)
    signals_by_message = {key: {signal['name'] for signal in graph['Signal'].values() if signal['message_id'] == key}
                          for key in graph['Message']}
    forwarded = {target: set().union(*(signals_by_message[key] for key, config in plan.items()
                                     if target in config['transport_unit']['consumer_refs']))
                 for target in ('Infotainment', 'Kombiinstrument')}
    assert 'InternetDatenrate' not in forwarded['Infotainment']
    assert 'InternetDatenrate' in forwarded['Kombiinstrument']
    assert {'BluetoothVerbindungen', 'KonnektivitaetStatus', 'WLANSignalstaerke'} <= forwarded['Infotainment']
    assert json.dumps(graph, sort_keys=True) == before
