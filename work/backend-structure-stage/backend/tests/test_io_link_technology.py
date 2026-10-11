from backend.nis.domain.vocabulary import INTERFACE_TYPES
from backend.nis.domain.vocabulary import validate_choice
from backend.nis.engineering.routing.config_builder import PROTOCOL_TO_TECHNOLOGY
from backend.nis.engineering.routing.generation import INTERFACE_TO_PROTOCOL
from backend.nis.engineering.routing.models import PROTOCOLS
from backend.nis.engineering.routing.network_sync import BUS_PROTOCOLS
from backend.nis.engineering.routing.validation import INTERFACE_PROTOCOLS
from backend.nis.engineering.routing.validation import PROTOCOL_CAPACITY


def test_io_link_is_supported_end_to_end_by_shared_technology_vocabularies():
    assert validate_choice("IO_LINK", INTERFACE_TYPES, "technology") == "IO_LINK"
    assert "IO_LINK" in PROTOCOLS
    assert INTERFACE_TO_PROTOCOL["IO_LINK"] == "IO_LINK"
    assert INTERFACE_PROTOCOLS["IO_LINK"] == {"IO_LINK"}
    assert PROTOCOL_CAPACITY["IO_LINK"] == (230_400, 32)
    assert PROTOCOL_TO_TECHNOLOGY["IO_LINK"] == "io_link"
    assert BUS_PROTOCOLS["io_link"] == "IO_LINK"
