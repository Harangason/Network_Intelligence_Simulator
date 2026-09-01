from __future__ import annotations

import pytest

from backend.engineering.core import (
    Encoding,
    HardwareNode,
    Message,
    Network,
    NetworkInterface,
    ProtocolBinding,
    Route,
    RouteHop,
    Signal,
    ValueDomain,
)


def test_core_signal_contract_serializes_without_frontend_types() -> None:
    signal = Signal(
        id="signal-1",
        name="VehicleState",
        semantic_type="state",
        value_domain=ValueDomain(
            allowed_values=("OK", "WARNING", "ERROR"),
            reserved_values=("NOT_AVAILABLE",),
        ),
        encoding=Encoding(bit_length=2, start_bit=0, data_type="unsigned"),
        protocol_binding=ProtocolBinding(protocol_id="SOME_IP", message_id="message-1"),
    )

    payload = signal.to_dict()

    assert payload["semantic_type"] == "STATE"
    assert payload["value_domain"]["allowed_values"] == ("OK", "WARNING", "ERROR")
    assert payload["protocol_binding"]["protocol_id"] == "SOME_IP"


def test_core_models_reject_invalid_ranges_and_empty_identity() -> None:
    with pytest.raises(ValueError, match="minimum"):
        ValueDomain(minimum=10, maximum=1)
    with pytest.raises(ValueError, match="id"):
        HardwareNode(id="", name="Gateway", device_type="Gateway")
    with pytest.raises(ValueError, match="byte_order"):
        Encoding(bit_length=8, start_bit=0, byte_order="middle")


def test_core_route_contract_keeps_route_logic_industry_neutral() -> None:
    gateway = HardwareNode(id="node-gw", name="System", device_type="Gateway")
    network = Network(id="net-1", name="Backbone", technology_id="ethernet")
    interface = NetworkInterface(
        id="if-1",
        name="System Ethernet",
        hardware_node_id=gateway.id,
        interface_type="Ethernet",
        network_id=network.id,
    )
    message = Message(id="msg-1", name="StatusMessage", interface_id=interface.id, dlc=8)
    route = Route(
        id="route-1",
        name="StatusRoute",
        source=RouteHop(node_id=gateway.id, interface_id=interface.id, network_id=network.id),
        destinations=(RouteHop(node_id="consumer", network_id=network.id),),
        message_ids=(message.id,),
    )

    assert route.source.network_id == "net-1"
    assert route.destinations[0].node_id == "consumer"
    assert route.message_ids == ("msg-1",)
