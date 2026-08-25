"""Technology-aware, deterministic capacity and timing estimators."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import ceil
from typing import Any


@dataclass(frozen=True)
class FrameEstimate:
    protocol: str
    payload_bytes: int
    frame_bits: float
    transmission_time_s: float
    calculation_model: str
    calculation_version: str = "1.0"
    is_generic_estimate: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _positive(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def estimate_frame(protocol: str, payload_bytes: int, parameters: dict[str, Any]) -> FrameEstimate:
    """Estimate serialized size and transmit time without claiming exact controller behavior."""
    normalized = str(protocol or "CUSTOM").upper().replace("-", "_").replace(" ", "_")
    payload = max(0, int(payload_bytes))
    bitrate = _positive(parameters.get("bitrate"), 1_000_000.0)

    if normalized in {"CAN", "CAN_CLASSIC"}:
        # SOF, arbitration, control, CRC, ACK, EOF and intermission; stuffing is estimated.
        frame_bits = ceil((47 + payload * 8) * 1.2)
        return FrameEstimate(normalized, payload, frame_bits, frame_bits / bitrate, "CAN_ESTIMATED_STUFFING")

    if normalized in {"CAN_FD", "CANFD", "CAN_XL"}:
        arbitration_bitrate = _positive(parameters.get("arbitration_bitrate"), bitrate)
        data_bitrate = _positive(parameters.get("data_bitrate"), max(bitrate, 2_000_000.0))
        arbitration_bits = ceil(55 * 1.2)
        data_bits = ceil((payload * 8 + 28) * 1.15)
        transmission = arbitration_bits / arbitration_bitrate + data_bits / data_bitrate
        return FrameEstimate("CAN_FD", payload, arbitration_bits + data_bits, transmission, "CAN_FD_PHASE_ESTIMATE")

    if normalized in {"ETHERNET", "SOME_IP", "SOMEIP", "UDP", "TCP", "DDS", "ROS_2"}:
        protocol_overhead = 42 if normalized in {"SOME_IP", "SOMEIP", "UDP"} else 54
        # Preamble/SFD + MAC frame + FCS + IFG. Enforce the Ethernet minimum frame footprint.
        wire_bytes = max(84, payload + protocol_overhead + 20)
        frame_bits = wire_bytes * 8
        return FrameEstimate(normalized, payload, frame_bits, frame_bits / bitrate, "ETHERNET_WIRE_ESTIMATE")

    if normalized == "LIN":
        # Break, sync, identifier, payload, checksum plus UART framing.
        frame_bits = 34 + payload * 10
        return FrameEstimate(normalized, payload, frame_bits, frame_bits / bitrate, "LIN_FRAME_ESTIMATE")

    if normalized == "FLEXRAY":
        frame_bits = 80 + payload * 8
        return FrameEstimate(normalized, payload, frame_bits, frame_bits / bitrate, "FLEXRAY_FRAME_ESTIMATE")

    frame_bits = (payload + int(_positive(parameters.get("generic_overhead_bytes"), 24))) * 8
    return FrameEstimate(
        normalized,
        payload,
        frame_bits,
        frame_bits / bitrate,
        "GENERIC_ESTIMATE",
        is_generic_estimate=True,
    )


def utilization_percent(transmission_time_s: float, cycle_ms: float, multiplicity: int = 1) -> float:
    cycle_s = max(float(cycle_ms), 0.001) / 1000.0
    return max(0.0, transmission_time_s * max(1, multiplicity) / cycle_s * 100.0)


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
