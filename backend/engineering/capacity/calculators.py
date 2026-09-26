"""Technology-aware, deterministic capacity and timing estimators."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import ceil, isfinite
from typing import Any

from backend.communication.technologies.catalog import DIRECT_IO_TECHNOLOGIES


@dataclass(frozen=True)
class FrameEstimate:
    protocol: str
    payload_bytes: int
    frame_bits: float
    transmission_time_s: float
    calculation_model: str
    calculation_version: str = "1.0"
    is_generic_estimate: bool = False
    transmission_time_available: bool = True

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        if not self.transmission_time_available:
            result["transmission_time_s"] = None
        return result


def _positive(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if isfinite(parsed) and parsed > 0 else default


def confirmed_serial_evidence(protocol: str, parameters: dict[str, Any], payload_bytes: int = 0) -> dict[str, Any] | None:
    """Require device-confirmed total transaction bounds before using I2C/SPI math."""
    technology = str(protocol or "").upper()
    evidence = parameters.get("local_timing_evidence") or {}
    if not isinstance(evidence, dict) or evidence.get("confirmed") is not True or not evidence.get("source"):
        return None
    if not evidence.get("master_node_id") or _positive(evidence.get("bitrate_bps"), 0) <= 0:
        return None
    transfer_bits = _positive(evidence.get("transfer_bits_bound"), 0)
    if transfer_bits < max(0, payload_bytes) * 8:
        return None
    required = ({"slave_address", "address_bits", "i2c_mode", "transfer_direction", "start_stop_bound_us",
                 "clock_stretch_limit_us", "multi_master"} if technology == "I2C" else
                {"chip_select", "word_length_bits", "duplex_mode", "cpol", "cpha",
                 "cs_setup_bound_us", "inter_transfer_gap_us"})
    if technology not in {"I2C", "SPI"} or any(evidence.get(field) is None for field in required):
        return None
    try:
        if technology == "I2C":
            address = int(str(evidence["slave_address"]), 0) if isinstance(evidence["slave_address"], str) else int(evidence["slave_address"])
            bits = int(evidence["address_bits"])
            if bits not in {7, 10} or not 0 <= address < 2 ** bits:
                return None
            mode_maximum = {"STANDARD": 100_000, "FAST": 400_000,
                            "FAST_PLUS": 1_000_000, "HIGH_SPEED": 3_400_000}
            if float(evidence["bitrate_bps"]) > mode_maximum.get(str(evidence["i2c_mode"]).upper(), 0):
                return None
            if str(evidence["transfer_direction"]).upper() not in {"READ", "WRITE", "BIDIRECTIONAL"}:
                return None
            if type(evidence["multi_master"]) is not bool:
                return None
            if evidence["multi_master"] and evidence.get("arbitration_bound_us") is None:
                return None
            delay_fields = ("start_stop_bound_us", "clock_stretch_limit_us")
            if evidence["multi_master"] or "arbitration_bound_us" in evidence:
                delay_fields += ("arbitration_bound_us",)
        else:
            if not str(evidence["chip_select"]).strip() or int(evidence["word_length_bits"]) <= 0:
                return None
            if str(evidence["duplex_mode"]).upper() not in {"FULL_DUPLEX", "HALF_DUPLEX"}:
                return None
            if int(evidence["cpol"]) not in {0, 1} or int(evidence["cpha"]) not in {0, 1}:
                return None
            delay_fields = ("cs_setup_bound_us", "inter_transfer_gap_us")
        if any(isinstance(evidence[field], bool)
               or not isfinite(float(evidence[field]))
               or float(evidence[field]) < 0 for field in delay_fields):
            return None
    except (TypeError, ValueError, OverflowError, KeyError):
        return None
    return evidence


def estimate_frame(protocol: str, payload_bytes: int, parameters: dict[str, Any]) -> FrameEstimate:
    """Estimate serialized size and transmit time without claiming exact controller behavior."""
    normalized = str(protocol or "CUSTOM").upper().replace("-", "_").replace(" ", "_")
    payload = max(0, int(payload_bytes))
    if normalized.lower() in DIRECT_IO_TECHNOLOGIES:
        return FrameEstimate(normalized, payload, 0, 0.0, "DIRECT_IO_NO_FRAME",
                             is_generic_estimate=False, transmission_time_available=False)
    if normalized in {"I2C", "SPI"}:
        evidence = confirmed_serial_evidence(normalized, parameters, payload)
        model = f"{normalized}_CONFIRMED_{'TRANSACTION' if normalized == 'I2C' else 'TRANSFER'}_BOUND_V1"
        if evidence is None:
            return FrameEstimate(normalized, payload, 0, 0.0, model,
                                 is_generic_estimate=True, transmission_time_available=False)
        bits = int(evidence["transfer_bits_bound"])
        delay_us = (float(evidence["start_stop_bound_us"]) + float(evidence["clock_stretch_limit_us"])
                    + float(evidence.get("arbitration_bound_us") or 0)) if normalized == "I2C" else (
                    float(evidence["cs_setup_bound_us"]) + float(evidence["inter_transfer_gap_us"]))
        return FrameEstimate(normalized, payload, bits,
                             bits / float(evidence["bitrate_bps"]) + delay_us / 1_000_000, model)
    # A catalog proposal is never transport evidence. Preserve the frame model
    # and size, but expose no numeric time until its explicit rates are present.
    bitrate = _positive(parameters.get("bitrate"), 0.0)
    rate_confirmed = parameters.get("_rate_evidenced") is not False
    available = bitrate > 0 and rate_confirmed

    if normalized in {"CAN", "CAN_CLASSIC"}:
        # SOF, arbitration, control, CRC, ACK, EOF and intermission; stuffing is estimated.
        frame_bits = ceil((47 + payload * 8) * 1.2)
        return FrameEstimate(normalized, payload, frame_bits, frame_bits / bitrate if available else 0.0,
                             "CAN_ESTIMATED_STUFFING", transmission_time_available=available)

    if normalized in {"CAN_FD", "CANFD"}:
        arbitration_bitrate = _positive(parameters.get("arbitration_bitrate", parameters.get("bitrate")), 0.0)
        data_bitrate = _positive(parameters.get("data_bitrate"), 0.0)
        arbitration_bits = ceil(55 * 1.2)
        data_bits = ceil((payload * 8 + 28) * 1.15)
        available = arbitration_bitrate > 0 and data_bitrate > 0 and rate_confirmed
        transmission = arbitration_bits / arbitration_bitrate + data_bits / data_bitrate if available else 0.0
        return FrameEstimate("CAN_FD", payload, arbitration_bits + data_bits, transmission,
                             "CAN_FD_PHASE_ESTIMATE", transmission_time_available=available)

    if normalized == "ETHERNET":
        protocol_overhead = 54
        # Preamble/SFD + MAC frame + FCS + IFG. Enforce the Ethernet minimum frame footprint.
        wire_bytes = max(84, payload + protocol_overhead + 20)
        frame_bits = wire_bytes * 8
        return FrameEstimate(normalized, payload, frame_bits, frame_bits / bitrate if available else 0.0,
                             "ETHERNET_WIRE_ESTIMATE", transmission_time_available=available)

    if normalized == "LIN":
        # Break, sync, identifier, payload, checksum plus UART framing.
        frame_bits = 34 + (payload + 1) * 10
        return FrameEstimate(normalized, payload, frame_bits, frame_bits / bitrate if available else 0.0,
                             "LIN_NOMINAL_WITH_CHECKSUM", calculation_version="2.0",
                             transmission_time_available=available)

    frame_bits = (payload + int(_positive(parameters.get("generic_overhead_bytes"), 24))) * 8
    return FrameEstimate(
        normalized,
        payload,
        frame_bits,
        0.0,
        "GENERIC_ESTIMATE",
        is_generic_estimate=True,
        transmission_time_available=False,
    )


def utilization_percent(transmission_time_s: float, cycle_ms: float, multiplicity: int = 1) -> float:
    cycle_s = max(float(cycle_ms), 0.001) / 1000.0
    return max(0.0, transmission_time_s * max(1, multiplicity) / cycle_s * 100.0)


def can_frame_time_bound_ms(protocol: str, payload_bytes: int, parameters: dict[str, Any]) -> float | None:
    """Conservative error-free wire-time envelope, not a mean stuffing estimate.

    Reserve 160 non-payload bits and 50% stuffing allowance at the slower phase
    rate. This intentionally overbounds standard/FD overhead, CRC, intermission,
    fixed/dynamic stuffing and FD DLC padding. No retry budget is implied.
    """
    normalized = str(protocol).upper().replace("-", "_")
    if normalized not in {"CAN", "CAN_CLASSIC", "CAN_FD", "CANFD"}:
        return None
    payload = max(0, int(payload_bytes))
    if normalized in {"CAN_FD", "CANFD"}:
        payload = next((size for size in [*range(9), 12, 16, 20, 24, 32, 48, 64] if size >= payload), payload)
    if parameters.get("_rate_evidenced") is False:
        return None
    bitrate = _positive(parameters.get("arbitration_bitrate", parameters.get("bitrate")), 0)
    if normalized in {"CAN_FD", "CANFD"}:
        bitrate = min(bitrate, _positive(parameters.get("data_bitrate"), 0))
    if not bitrate:
        return None
    return ceil((160 + 8 * payload) * 1.5) / bitrate * 1000


def queueing_delay_ms(transmission_time_s: float, utilization: float) -> float:
    """M/D/1 engineering estimate; bounded near saturation for stable reporting."""
    rho = min(max(utilization / 100.0, 0.0), 0.99)
    return transmission_time_s * 1000.0 * rho / (2.0 * (1.0 - rho))


def scheduled_queueing_delay_ms(
    transmission_time_s: float,
    utilization: float,
    policy: str,
    priority: int = 50,
) -> float:
    """Apply an explicit scheduling assumption to the deterministic queue estimate."""
    base = queueing_delay_ms(transmission_time_s, utilization)
    normalized = str(policy or "FIFO").upper()
    factors = {
        "FIFO": 1.0,
        "PRIORITY": 0.85,
        "STRICT_PRIORITY": 0.7,
        "WEIGHTED_PRIORITY": 0.8,
        "WRR": 0.8,
        "ROUND_ROBIN": 0.95,
        "TIME_TRIGGERED": 0.35,
        "TAS": 0.35,
        "CBS": 0.65,
        "CUSTOM": 1.0,
    }
    if normalized == "FIFO":
        return base
    normalized_priority = max(0, min(priority, 100)) / 100.0
    priority_factor = 1.75 - normalized_priority * 1.25
    return base * factors.get(normalized, 1.0) * priority_factor


def clock_drift_ms(clock_drift_ppm: float, duration_s: float) -> float:
    return max(0.0, float(clock_drift_ppm)) * max(0.0, float(duration_s)) / 1000.0


def classify_load(value: float, thresholds: dict[str, float]) -> str:
    if value >= thresholds["overload"]:
        return "OVERLOAD"
    if value >= thresholds["critical"]:
        return "CRITICAL"
    if value >= thresholds["warning"]:
        return "WARNING"
    return "NORMAL"
