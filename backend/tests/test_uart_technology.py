from backend.engineering.models import INTERFACE_TYPES, validate_choice
from backend.engineering.routing.config_builder import PROTOCOL_TO_TECHNOLOGY
from backend.engineering.routing.generation import INTERFACE_TO_PROTOCOL
from backend.engineering.routing.models import PROTOCOLS
from backend.engineering.routing.network_sync import BUS_PROTOCOLS
from backend.engineering.routing.transport_segments import BUS_PROTOCOLS as SEGMENT_BUS_PROTOCOLS
from backend.engineering.routing.validation import INTERFACE_PROTOCOLS, PROTOCOL_CAPACITY
from backend.engineering.scope_rules import canonical_communication_system


def test_uart_is_supported_end_to_end_by_shared_technology_vocabularies():
    assert validate_choice("UART", INTERFACE_TYPES, "technology") == "UART"
    assert canonical_communication_system("uart") == "UART"
    assert "UART" in PROTOCOLS
    assert INTERFACE_TO_PROTOCOL["UART"] == "UART"
    assert INTERFACE_PROTOCOLS["UART"] == {"UART"}
    assert PROTOCOL_CAPACITY["UART"] == (115_200, 65_535)
    assert PROTOCOL_TO_TECHNOLOGY["UART"] == "uart"
    assert BUS_PROTOCOLS["uart"] == "UART"
    assert SEGMENT_BUS_PROTOCOLS["uart"] == "UART"
