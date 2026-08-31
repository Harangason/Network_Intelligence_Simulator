from backend.engineering.signal_audit import build_generation_signal_audit, inspect_signal


def test_signal_audit_flags_oversized_signal_without_mutation():
    signal = {
        "id": "speed",
        "name": "Speed",
        "message_id": "status",
        "start_bit": 0,
        "length_bits": 64,
        "byte_order": "little_endian",
        "data_type": "unsigned",
        "factor": 1,
        "offset_value": 0,
        "min_value": 0,
        "max_value": 255,
    }

    result = inspect_signal(signal, {"id": "status", "name": "Status", "dlc": 8})

    assert result["required_bits"] == 8
    assert result["length_bits"] == 64
    assert result["status"] == "WARNING"
    assert any(check["code"] == "SIGNAL_OVERSIZED" for check in result["checks"])
    assert signal["length_bits"] == 64


def test_signal_audit_keeps_rollrate_16_bits_when_resolution_requires_it():
    result = inspect_signal(
        {
            "id": "rollrate",
            "name": "Rollrate",
            "message_id": "motion",
            "start_bit": 0,
            "length_bits": 16,
            "byte_order": "little_endian",
            "data_type": "signed",
            "factor": 0.01,
            "offset_value": 0,
            "min_value": -300,
            "max_value": 300,
        },
        {"id": "motion", "name": "Motion", "dlc": 8},
    )

    assert result["required_bits"] == 16
    assert result["status"] == "PASS"


def test_generation_signal_audit_reports_sender_participants_systems_and_messages():
    audit = build_generation_signal_audit(
        hardware=[
            {"id": "airbag", "name": "Airbag", "device_type": "ECU"},
            {"id": "pressure", "name": "AirbagPressure", "device_type": "SensorController", "identity": {"system_owner_id": "airbag"}},
            {"id": "gateway", "name": "System-Gateway", "device_type": "Gateway"},
        ],
        interfaces=[
            {"id": "sensor-lin", "name": "Airbag-LIN", "hardware_node_id": "pressure"},
            {"id": "gateway-lin", "name": "Antriebs-CAN", "hardware_node_id": "gateway"},
        ],
        messages=[{"id": "msg", "name": "AirbagStatus", "dlc": 1}],
        signals=[{
            "id": "enabled",
            "name": "Enabled",
            "message_id": "msg",
            "start_bit": 0,
            "length_bits": 1,
            "byte_order": "little_endian",
            "data_type": "unsigned",
            "factor": 1,
            "offset_value": 0,
            "min_value": 0,
            "max_value": 1,
        }],
        routes=[{
            "id": "route",
            "source": {"node_id": "pressure", "interface_id": "sensor-lin", "network_id": "network-lin"},
            "destinations": [{"node_id": "gateway", "interface_id": "gateway-lin"}],
            "payload": {"message_id": "msg", "signal_ids": ["enabled"]},
        }],
        topology={},
    )

    assert audit["summary"]["signals"] == 1
    assert audit["summary"]["passed"] == 1
    network = audit["networks"][0]
    assert network["network_id"] == "network-lin"
    assert network["sender_count"] == 1
    assert network["participant_count"] == 2
    assert network["message_count"] == 1
    assert network["signal_count"] == 1
    sender = next(item for item in network["participants"] if item["id"] == "pressure")
    assert sender["roles"] == ["Sender"]
    assert sender["system_frame"]["id"] == "airbag"
