from __future__ import annotations

import pytest

from backend.engineering.message_packing import (
    HardwareCapability,
    HardwareInterfaceAllocationService,
    HardwareInterfaceState,
    PackedMessage,
    SignalCandidate,
    pack_signals,
    valid_payload_bytes,
)


@pytest.mark.parametrize(
    ("required", "expected"),
    [
        (8, 8),
        (9, 12),
        (12, 12),
        (13, 16),
        (20, 20),
        (21, 24),
        (25, 32),
        (33, 48),
        (49, 64),
        (65, None),
    ],
)
def test_can_fd_payload_classes(required: int, expected: int | None) -> None:
    assert valid_payload_bytes("CAN_FD", required) == expected


def test_pack_signals_reuses_one_message_for_compatible_producer_timing_and_receivers() -> None:
    messages = pack_signals(
        [
            SignalCandidate("MotorRpm", 16, "MotorControl", "MotorECU", "CAN_FD", 10, ("Gateway",)),
            SignalCandidate("MotorTorque", 16, "MotorControl", "MotorECU", "CAN_FD", 10, ("Gateway",)),
            SignalCandidate("MotorCurrent", 16, "MotorControl", "MotorECU", "CAN_FD", 10, ("Gateway",)),
        ],
    )

    assert len(messages) == 1
    message = messages[0]
    assert message.dlc == 6
    assert message.payload_used_bits == 48
    assert message.payload_capacity_bits == 48
    assert [signal.start_bit for signal in message.signals] == [0, 16, 32]
    assert message.interface_ref == "MotorECU_1"


def test_pack_signals_keeps_different_timing_classes_separate() -> None:
    messages = pack_signals(
        [
            SignalCandidate("MotorRpm", 16, "MotorControl", "MotorECU", "CAN_FD", 10, ("Gateway",)),
            SignalCandidate("MotorTemperature", 16, "MotorControl", "MotorECU", "CAN_FD", 1000, ("Gateway",)),
        ],
    )

    assert len(messages) == 2
    assert {message.cycle_ms for message in messages} == {10, 1000}
    assert len({message.interface_ref for message in messages}) == 1


def test_pack_signals_keeps_different_receiver_sets_separate() -> None:
    messages = pack_signals(
        [
            SignalCandidate("SignalA", 8, "BodyControl", "BodyECU", "CAN_FD", 20, ("ECU_1", "ECU_2")),
            SignalCandidate("SignalB", 8, "BodyControl", "BodyECU", "CAN_FD", 20, ("ECU_9",)),
        ],
    )

    assert len(messages) == 2
    assert {message.receiver_set for message in messages} == {("ECU_1", "ECU_2"), ("ECU_9",)}


def test_pack_signals_splits_messages_without_splitting_atomic_signals() -> None:
    messages = pack_signals(
        [
            SignalCandidate("BlobA", 392, "Perception", "CameraECU", "CAN_FD", 10, ("Gateway",)),
            SignalCandidate("BlobB", 120, "Perception", "CameraECU", "CAN_FD", 10, ("Gateway",)),
            SignalCandidate("BlobC", 8, "Perception", "CameraECU", "CAN_FD", 10, ("Gateway",)),
        ],
    )

    assert len(messages) == 2
    assert messages[0].signals[0].name == "BlobA"
    assert messages[0].signals[0].start_bit == 0
    assert messages[0].signals[1].name == "BlobB"
    assert messages[0].signals[1].start_bit == 392
    assert messages[0].dlc == 64
    assert [signal.start_bit for signal in messages[1].signals] == [0]
    assert messages[1].dlc == 1


def test_allocation_reuses_interface_until_configured_capacity_threshold() -> None:
    signals = [
        SignalCandidate(f"Status{index}", 8, f"Producer{index}", "Gateway", "CAN_FD", 100, ("ECU",))
        for index in range(10)
    ]
    messages = pack_signals(signals, target_load_percent=60.0)

    assert len(messages) == 10
    assert len({message.interface_ref for message in messages}) == 1
    assert all(message.projected_interface_load_percent <= 60.0 for message in messages)


def test_allocation_uses_new_channel_when_projected_load_crosses_threshold() -> None:
    signals = [
        SignalCandidate(f"Fast{index}", 64, f"Producer{index}", "Gateway", "CAN_FD", 1, ("ECU",))
        for index in range(200)
    ]
    messages = pack_signals(signals, target_load_percent=60.0)

    assert len({message.interface_ref for message in messages}) > 1
    assert all(message.projected_interface_load_percent <= 60.0 for message in messages)


def test_hardware_interface_allocation_reuses_existing_capacity_first() -> None:
    messages = [
        PackedMessage(f"Status{index}", f"Function{index}", "ECU_A", "CAN_FD", 100, ("Gateway",), "NORMAL", payload_capacity_bits=64)
        for index in range(3)
    ]
    service = HardwareInterfaceAllocationService(
        existing_interfaces=[
            HardwareInterfaceState("ECU_A_CAN_FD_1", "ECU_A", "CAN_FD", "CAN_FD_A", target_load_limit=60.0)
        ],
    )

    decisions = service.allocate(messages)

    assert {decision.selected_hardware_interface for decision in decisions} == {"ECU_A_CAN_FD_1"}
    assert {message.interface_ref for message in messages} == {"ECU_A_CAN_FD_1"}
    assert {message.network_ref for message in messages} == {"CAN_FD_A"}


def test_hardware_interface_allocation_blocks_when_capability_channel_limit_is_reached() -> None:
    message = PackedMessage("FastData", "MotorControl", "ECU_A", "CAN_FD", 1, ("Gateway",), "HIGH", payload_capacity_bits=512)
    service = HardwareInterfaceAllocationService(
        target_load_percent=1.0,
        capabilities={
            "ECU_A": HardwareCapability(
                "ECU_A",
                supported_network_technologies=("CAN_FD",),
                max_channels_by_technology={"CAN_FD": 1},
            )
        },
        existing_interfaces=[
            HardwareInterfaceState("ECU_A_CAN_FD_1", "ECU_A", "CAN_FD", "CAN_FD_A", current_load_percent=1.0, target_load_limit=1.0)
        ],
    )

    decision = service.allocate([message])[0]

    assert decision.proposal_required is True
    assert decision.finding == "HARDWARE_CAPABILITY_EXCEEDED"
    assert message.interface_ref is None


def test_two_interfaces_on_same_network_do_not_double_network_capacity() -> None:
    messages = [
        PackedMessage("A", "FunctionA", "ECU_A", "CAN_FD", 100, ("Gateway",), "NORMAL", payload_capacity_bits=64),
        PackedMessage("B", "FunctionB", "ECU_A", "CAN_FD", 100, ("Gateway",), "NORMAL", payload_capacity_bits=64),
    ]
    service = HardwareInterfaceAllocationService(
        existing_interfaces=[
            HardwareInterfaceState("ECU_A_CAN_FD_1", "ECU_A", "CAN_FD", "CAN_FD_A", target_load_limit=60.0),
            HardwareInterfaceState("ECU_A_CAN_FD_2", "ECU_A", "CAN_FD", "CAN_FD_A", target_load_limit=60.0),
        ],
    )

    service.allocate(messages)

    assert {message.network_ref for message in messages} == {"CAN_FD_A"}
    assert len({message.interface_ref for message in messages}) == 1
