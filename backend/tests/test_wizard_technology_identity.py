import pytest
from uuid import uuid4

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
