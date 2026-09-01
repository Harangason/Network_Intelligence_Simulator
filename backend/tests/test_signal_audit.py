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
        "semantic": {"semantic_type": "NUMERIC"},
        "data": {"resolution": 1},
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
            "semantic": {"semantic_type": "NUMERIC"},
            "data": {"resolution": 0.01},
        },
        {"id": "motion", "name": "Motion", "dlc": 8},
    )

    assert result["required_bits"] == 16
    assert result["status"] == "PASS"


def test_generation_signal_audit_reports_sender_participants_systems_and_messages():
    audit = build_generation_signal_audit(
        hardware=[
            {"id": "safety-loop", "name": "SafetyLoop", "device_type": "Controller"},
            {"id": "pressure", "name": "PressureProbe", "device_type": "SensorController", "identity": {"system_owner_id": "safety-loop"}},
            {"id": "gateway", "name": "System-Gateway", "device_type": "Gateway"},
        ],
        interfaces=[
            {"id": "sensor-link", "name": "Process-LIN", "hardware_node_id": "pressure"},
            {"id": "gateway-link", "name": "Backbone-CAN", "hardware_node_id": "gateway"},
        ],
        messages=[{"id": "msg", "name": "SafetyLoopStatus", "dlc": 1}],
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
            "semantic": {"semantic_type": "BOOLEAN"},
            "data": {"allowed_values": [False, True]},
        }],
        routes=[{
            "id": "route",
            "source": {"node_id": "pressure", "interface_id": "sensor-link", "network_id": "network-lin"},
            "destinations": [{"node_id": "gateway", "interface_id": "gateway-link"}],
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
    assert sender["system_frame"]["id"] == "safety-loop"


def test_legacy_value_signal_requires_semantic_classification_before_optimization():
    result = inspect_signal(
        {
            "id": "legacy",
            "name": "LegacyValue",
            "message_id": "status",
            "start_bit": 0,
            "length_bits": 8,
            "byte_order": "little_endian",
            "data_type": "unsigned",
            "factor": 1,
            "offset_value": 0,
            "min_value": 0,
            "max_value": 255,
        },
        {"id": "status", "name": "Status", "dlc": 8},
    )

    assert result["required_bits"] is None
    assert result["status"] == "OPEN"
    assert any(check["code"] == "SIGNAL_SEMANTIC_MISSING" for check in result["checks"])


def test_legacy_status_signal_uses_conservative_state_domain():
    result = inspect_signal(
        {
            "id": "status",
            "name": "ProcessStatus",
            "message_id": "status",
            "start_bit": 0,
            "length_bits": 8,
            "byte_order": "little_endian",
            "data_type": "unsigned",
            "factor": 1,
            "offset_value": 0,
            "min_value": 0,
            "max_value": 255,
        },
        {"id": "status", "name": "Status", "dlc": 8},
    )

    assert result["semantic_type"] == "STATE"
    assert result["required_bits"] == 3
    assert result["status"] == "PASS"
    assert not any(check["code"] in {"SIGNAL_SEMANTIC_MISSING", "SIGNAL_BIT_NEED_OPEN"} for check in result["checks"])


def test_unit_based_semantic_classification_unblocks_numeric_bit_optimization():
    result = inspect_signal(
        {
            "id": "pressure",
            "name": "LinePressure",
            "message_id": "process",
            "start_bit": 0,
            "length_bits": 16,
            "byte_order": "little_endian",
            "data_type": "unsigned",
            "factor": 0.1,
            "offset_value": 0,
            "min_value": 0,
            "max_value": 250,
            "unit": "bar",
        },
        {"id": "process", "name": "Process", "dlc": 8},
    )

    assert result["semantic_type"] == "NUMERIC"
    assert result["required_bits"] == 12
    assert not any(check["code"] in {"SIGNAL_SEMANTIC_MISSING", "SIGNAL_BIT_NEED_OPEN"} for check in result["checks"])
