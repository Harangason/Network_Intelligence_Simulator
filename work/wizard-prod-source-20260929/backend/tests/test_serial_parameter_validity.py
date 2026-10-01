"""Invalid serial timing evidence must not become a deterministic numeric bound."""
import pytest

from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY
from backend.engineering.capacity.calculators import estimate_frame
from backend.engineering.capacity.dimensioning import DEFAULT_POLICY, bus_schedule


def evidence(technology):
    common = {"confirmed": True, "source": "explicit synthetic test vector", "master_node_id": "controller"}
    if technology == "I2C":
        return {**common, "slave_address": "0x20", "address_bits": 7, "i2c_mode": "FAST",
                "transfer_direction": "READ", "start_stop_bound_us": 2, "clock_stretch_limit_us": 5,
                "multi_master": False, "transfer_bits_bound": 100, "bitrate_bps": 400_000}
    return {**common, "chip_select": "CS0", "word_length_bits": 8, "duplex_mode": "FULL_DUPLEX",
            "cpol": 0, "cpha": 0, "cs_setup_bound_us": 2, "inter_transfer_gap_us": 1,
            "transfer_bits_bound": 64, "bitrate_bps": 1_000_000}


@pytest.mark.parametrize("technology,field", [
    ("I2C", "start_stop_bound_us"), ("I2C", "clock_stretch_limit_us"),
    ("I2C", "arbitration_bound_us"), ("SPI", "cs_setup_bound_us"), ("SPI", "inter_transfer_gap_us"),
])
@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf"), True, False, -1, "invalid"])
def test_invalid_delay_never_becomes_numeric_frame_or_schedule(technology, field, invalid):
    supplied = {**evidence(technology), field: invalid}
    frame = estimate_frame(technology, 8, {"local_timing_evidence": supplied}).to_dict()
    assert frame["transmission_time_available"] is False
    assert frame["transmission_time_s"] is None
    timing = DEFAULT_TECHNOLOGY_REGISTRY.resolve_stack(technology)["timing_model"]
    with pytest.raises(ValueError):
        timing.transmission_time_us(8, local_timing_evidence=supplied)
    schedule = bus_schedule([{"stream_id": "transaction", "protocol": technology, "payload_bytes": 8,
        "cycle_ms": 10, "bitrate": supplied["bitrate_bps"], "segment_transmission_latency_ms": None,
        "local_timing_evidence": supplied, "physical_path_resolved": True}], DEFAULT_POLICY)
    assert schedule["status"] == "UNVERIFIED"
    assert schedule["responses"] == {}
    assert schedule["nominal_load_percent"] is None


@pytest.mark.parametrize("technology,field", [("I2C", "slave_address"), ("I2C", "address_bits"),
                                            ("SPI", "word_length_bits"), ("SPI", "cpol"), ("SPI", "cpha")])
def test_infinite_integer_fields_fail_closed_without_overflow(technology, field):
    supplied = {**evidence(technology), field: float("inf")}
    assert estimate_frame(technology, 8, {"local_timing_evidence": supplied}).to_dict()["transmission_time_s"] is None


@pytest.mark.parametrize("technology,expected_us", [("I2C", 257), ("SPI", 67)])
def test_explicit_finite_serial_model_remains_available(technology, expected_us):
    supplied = evidence(technology)
    frame = estimate_frame(technology, 8, {"local_timing_evidence": supplied})
    assert frame.transmission_time_available is True
    assert frame.transmission_time_s * 1_000_000 == pytest.approx(expected_us)


def test_confirmed_multimaster_arbitration_delay_is_retained():
    supplied = {**evidence("I2C"), "multi_master": True, "arbitration_bound_us": 3}
    frame = estimate_frame("I2C", 8, {"local_timing_evidence": supplied})
    assert frame.transmission_time_s * 1_000_000 == pytest.approx(260)
