import pytest
from uuid import uuid4

from backend.engineering.agent_tools import proposal_service
from backend.engineering.agent_tools.wizard_generation import _topology_bus, generate
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.agent_core.api.tool_contract import Permission


@pytest.mark.parametrize('source, expected', [
    ('ADC', 'adc'), ('DAC', 'dac'), ('GPIO', 'gpio'), ('PWM', 'pwm'),
    ('I2C', 'i2c'), ('SPI', 'spi'), ('UART', 'uart'),
    ('EtherCAT', 'ethercat'), ('ModbusTCP', 'modbus_tcp'),
    ('CAN_FD', 'can_fd'), ('LIN', 'lin'),
])
def test_topology_preserves_actual_technology(source, expected):
    assert _topology_bus(source) == expected


@pytest.mark.parametrize('source', ['Other', 'invented_link'])
def test_unknown_connection_is_not_replaced_by_automotive_ethernet(source):
    with pytest.raises(ValueError, match='kein Ersatznetz'):
        _topology_bus(source)


def test_embedded_proposal_keeps_confirmed_domain_devices_and_adc():
    prompt = '''- Industrie: Embedded Systems
- Projekt-Modelltyp: embedded_systems
- Netzwerktechnologien: ADC (adc)
- Hardware-Sollwerte: {"gateways":0,"ecus":1,"sensors":3,"actuators":5}
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
ich möchte ein kleines Projekt: ich habe drei sensoren die temperatur messen und ein respary pi und aktoren die ventile steuern
'''
    def check():
        proposal = generate({'prompt': prompt})
        devices = [change['data']['name'] for change in proposal['changes'] if change['object_type'] == 'HardwareNode']
        assert set(devices) == {'RaspberryPi', *(f'Temperatursensor{i}' for i in range(1, 4)), *(f'Ventilaktor{i}' for i in range(1, 6))}
        interfaces = [change['data'] for change in proposal['changes'] if change['object_type'] == 'HardwareNetworkInterface']
        assert interfaces
        assert all(item['technology'] == 'ADC' for item in interfaces)
        functions = [change['data'] for change in proposal['changes'] if change['object_type'] == 'Function']
        assert all(item['domain'] == 'embedded_systems' for item in functions)
    result = execute(ToolAuthority(f'pytest-embedded-identity-{uuid4()}'), 'test_embedded_identity', Permission.GENERATE_PROPOSAL, {}, lambda _: check())
    assert result.success, result


def test_uart_wizard_proposal_validation_accepts_confirmed_technology():
    prompt = '''- Industrie: Custom
- Projekt-Modelltyp: custom
- Netzwerktechnologien: UART / USART (uart)
- Hardware-Sollwerte: {"gateways":0,"ecus":1,"sensors":1,"actuators":1}
- Sensor-Messgrößen: {"Sensor1":"temperature"}
- Geräteanschlüsse: {"MainController":"UART","Sensor1":"UART","Aktor1":"UART"}
- Aktor-Befehle: {"Aktor1":{"length_bits":10,"data_type":"unsigned","unit":"%","factor":0.1,"min_value":0,"max_value":100,"semantic":{"semantic_type":"NUMERIC","meaning":"Angeforderte Stellposition"},"data":{"minimum":0,"maximum":100,"resolution":0.1}}}
- Systemcluster-Graph: [{"network_id":"uart","network_label":"UART","bus_name":"Regelung","controllers":[{"ecu":"MainController","sensors":["Sensor1"],"actuators":["Aktor1"]}]}]
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
Ein zentraler kleiner Rechner überwacht einen Temperatursensor und steuert einen Aktor.
'''

    def check():
        proposal = generate({'prompt': prompt})
        proposal = proposal_service.validate(proposal['proposal_id'])
        messages = [str(item.get('message') or '') for item in proposal['validation_result']['findings']]
        assert not any("Ungültiger Wert für 'technology': 'UART'" in message for message in messages)
        interfaces = [
            change['data']
            for change in proposal['changes']
            if change['object_type'] == 'HardwareNetworkInterface'
        ]
        assert interfaces
        assert all(item['technology'] == 'UART' for item in interfaces)

    result = execute(
        ToolAuthority(f'pytest-uart-wizard-{uuid4()}'),
        'test_uart_wizard',
        Permission.GENERATE_PROPOSAL,
        {},
        lambda _: check(),
    )
    assert result.success, result
