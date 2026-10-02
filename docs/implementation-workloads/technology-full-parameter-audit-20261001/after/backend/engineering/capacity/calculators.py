"""Technology-aware, deterministic capacity and timing estimators."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import ceil, isfinite
from typing import Any

from backend.communication.technologies.catalog import CAN_FD_DATA_LENGTHS, DIRECT_IO_TECHNOLOGIES, LOCAL_EVIDENCE_FIELDS, REVIEW_RATE_PROPOSALS


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
    if isinstance(evidence, dict):
        from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
        if any(registry.normalize_id(evidence[key]) != registry.normalize_id(protocol)
               for key in ('technology', 'protocol') if evidence.get(key)):
            return None
    if not isinstance(evidence, dict) or evidence.get("confirmed") is not True or not isinstance(evidence.get("source"),str) or not evidence['source'].strip():
        return None
    if technology=='I2C':
        from backend.communication.technologies.i2c import evidence_issues
        if evidence_issues(evidence,payload_bytes,require_transaction=True):
            return None
    if not isinstance(evidence.get('master_node_id'),str) or not evidence['master_node_id'].strip() or _positive(evidence.get("bitrate_bps"), 0) <= 0:
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
            mode_maximum = {option['mode'].upper().replace(' ', '_'): option['maximum']
                            for option in REVIEW_RATE_PROPOSALS['i2c']['options']}
            if float(evidence["bitrate_bps"]) > mode_maximum.get(str(evidence["i2c_mode"]).upper(), 0):
                return None
            if str(evidence["transfer_direction"]).upper() not in {"READ", "WRITE", "BIDIRECTIONAL"}:
                return None
            if type(evidence["multi_master"]) is not bool:
                return None
            if evidence["multi_master"] and evidence.get("arbitration_bound_us") is None:
                return None
            delay_fields = ("start_stop_bound_us", "clock_stretch_limit_us")
            if evidence["multi_master"] or evidence.get("arbitration_bound_us") is not None:
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


def serial_evidence_missing_fields(protocol: str, parameters: dict[str, Any], payload_bytes: int = 0) -> list[str]:
    """Expose the concrete device review, separate from a saved network clock."""
    if confirmed_serial_evidence(protocol, parameters, payload_bytes) is not None:
        return []
    evidence = parameters.get('local_timing_evidence')
    evidence = evidence if isinstance(evidence, dict) else {}
    if str(protocol).upper()=='I2C':
        from backend.communication.technologies.i2c import local_fields, evidence_issues
        scope=evidence.get('evidence_scope') or 'TRANSACTION'
        missing=[f['key'] for f in local_fields() if
            (not f.get('optional') and (not f.get('required_scopes') or scope in f['required_scopes']))
            and (evidence.get(f['key']) is None or evidence.get(f['key'])=='')]
        if evidence.get('multi_master')is True and evidence.get('arbitration_bound_us')is None: missing.append('arbitration_bound_us')
        if not isinstance(evidence.get('source'),str) or not evidence.get('source','').strip(): missing.append('source')
        if evidence.get('confirmed')is not True: missing.append('confirmed')
        if scope in ('CONTROLLER_PORT','TARGET_PORT'): missing.append('transaction_evidence')
        if not missing: missing=evidence_issues(evidence,payload_bytes,require_transaction=True)
        return [f'local_timing_evidence.{key}' for key in dict.fromkeys(missing)] or ['local_timing_evidence.invalid_device_or_transaction_bounds']
    fields = [key for key, _ in LOCAL_EVIDENCE_FIELDS.get(str(protocol).upper(), ())
              if key != 'arbitration_bound_us' or evidence.get('multi_master') is not False]
    missing = [key for key in fields if evidence.get(key) is None or evidence.get(key) == '']
    if not evidence.get('source'): missing.append('source')
    if evidence.get('confirmed') is not True: missing.append('confirmed')
    return [f'local_timing_evidence.{key}' for key in missing] or ['local_timing_evidence.invalid_device_or_transaction_bounds']


def can_fd_wire_data_bytes(payload: int, parameters: dict[str, Any]) -> int:
    if not 0 <= payload <= 64:
        raise ValueError('CAN FD logical payload must be 0..64 B.')
    actual = parameters.get('can_fd_wire_data_bytes')
    dlc = parameters.get('can_fd_dlc')
    if dlc is not None:
        if not isinstance(dlc,(int,float)) or isinstance(dlc,bool) or not isfinite(dlc) or dlc!=int(dlc) or not 0<=dlc<=15:
            raise ValueError('CAN FD DLC must be an integer0..15.')
        encoded = CAN_FD_DATA_LENGTHS[int(dlc)]
        if actual is not None and actual!=encoded:
            raise ValueError('CAN FD DLC and actual wire length disagree.')
        actual = encoded
    if actual is None:
        return next(size for size in CAN_FD_DATA_LENGTHS if size >= payload)
    if isinstance(actual,bool) or actual not in CAN_FD_DATA_LENGTHS or actual<payload:
        raise ValueError('CAN FD wire length must fit payload and its DLC length table.')
    return int(actual)


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
                    + float(evidence.get("arbitration_bound_us") or 0)
                    + (float(evidence['hs_entry_bound_us']) if evidence['i2c_mode']=='HIGH_SPEED' else 0)) if normalized == "I2C" else (
                    float(evidence["cs_setup_bound_us"]) + float(evidence["inter_transfer_gap_us"]))
        return FrameEstimate(normalized, payload, bits,
                             bits / float(evidence["bitrate_bps"]) + delay_us / 1_000_000, model)
    # A catalog proposal is never transport evidence. Preserve the frame model
    # and size, but expose no numeric time until its explicit rates are present.
    bitrate = _positive(parameters.get("bitrate"), 0.0)
    rate_confirmed = parameters.get("_rate_evidenced") is not False
    available = bitrate > 0 and rate_confirmed

    if normalized in {"CAN", "CAN_CLASSIC"}:
        if payload > 8 or parameters.get('can_frame_type') == 'REMOTE' and payload:
            raise ValueError('CAN CC payload must be 0..8 B; remote frames have no data field.')
        # Bosch CAN 2.0 Part B 3.2 / 5: stuffing only SOF through CRC sequence.
        # Unknown IDE uses the longer format as a conservative bound, never an inferred 11-bit ID.
        extended = parameters.get('can_frame_format') != 'BASE_11'
        unstuffed = (67 if extended else 47) + payload * 8
        stuffable = (54 if extended else 34) + payload * 8
        frame_bits = unstuffed + (stuffable - 1) // 4
        return FrameEstimate(normalized, payload, frame_bits, frame_bits / bitrate if available else 0.0,
                             "CAN_CC_STUFFING_UPPER_BOUND", calculation_version="2.0", transmission_time_available=available)

    if normalized in {"CAN_FD", "CANFD"}:
        wire_payload = can_fd_wire_data_bytes(payload,parameters)
        arbitration_bitrate = _positive(parameters.get("arbitration_bitrate", parameters.get("bitrate")), 0.0)
        data_bitrate = _positive(parameters.get("data_bitrate"), 0.0)
        # Successful ISO frame upper envelope: longer IDE header/nominal tail,
        # dynamic data stuffing at <=1 per4 input bits, CRC17/21 + SBC/parity/fixed stuffing.
        # These deliberately conservative phase budgets are not bit-exact CRC encoding.
        arbitration_bits = 80
        data_bits = wire_payload * 10 + 40
        brs = parameters.get('can_fd_brs')
        available = arbitration_bitrate > 0 and (brs is False or data_bitrate > 0) and rate_confirmed
        transmission = 0.0
        if available:
            if brs is False:
                transmission = (arbitration_bits + data_bits) / arbitration_bitrate
            elif brs is True:
                transmission = arbitration_bits / arbitration_bitrate + data_bits / data_bitrate
            else:
                # Unknown BRS cannot silently select faster wire timing.
                transmission = (arbitration_bits + data_bits) / min(arbitration_bitrate,data_bitrate)
        return FrameEstimate("CAN_FD", payload, arbitration_bits + data_bits, transmission,
                             "CAN_FD_PHASE_ESTIMATE", calculation_version="2.0", transmission_time_available=available)

    if normalized == "ETHERNET":
        # Ethernet MAC-client bytes are not necessarily TCP/IP application bytes.
        # No packet headers or VLAN layout are inferred from a confirmed link rate.
        layer=parameters.get('eth_payload_layer')
        headers=parameters.get('eth_upper_header_bytes')
        tags=parameters.get('eth_vlan_tags')
        mtu=parameters.get('mtu_bytes')
        gap=parameters.get('eth_ifg_bits')
        whole=lambda x: isinstance(x,(int,float)) and not isinstance(x,bool) and isfinite(x) and int(x)==x
        if (layer not in {'MAC_CLIENT','UPPER_LAYER'} or not whole(headers) or headers<0
            or layer=='MAC_CLIENT' and headers!=0 or not whole(tags) or tags not in {0,1,2}
            or not whole(mtu) or mtu<=0 or not whole(gap) or gap<96
            or parameters.get('eth_frame_profile') not in {'BASIC_MAC','JUMBO_DEVICE'}):
            return FrameEstimate(normalized,payload,0,0.0,'ETHERNET_LAYOUT_UNVERIFIED',transmission_time_available=False)
        client=payload+int(headers)
        if client>mtu or parameters.get('eth_frame_profile')=='BASIC_MAC' and (client>1500 or mtu>1500):
            raise ValueError('Ethernet MAC-client data exceed selected MTU; segmentation is not evidenced.')
        frame_bits=(max(64,18+client+4*int(tags))+8)*8+int(gap)
        available=available and parameters.get('duplex')=='FULL'
        # Half-duplex carrier extension/collisions/backoff are a different model.
        if parameters.get('duplex')!='FULL':
            return FrameEstimate(normalized,payload,frame_bits,0.0,'ETHERNET_ACCESS_UNVERIFIED',transmission_time_available=False)
        return FrameEstimate(normalized, payload, frame_bits, frame_bits / bitrate if available else 0.0,
                             "ETHERNET_WIRE_ESTIMATE", calculation_version='2.0',transmission_time_available=available)

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
        payload = can_fd_wire_data_bytes(payload,parameters)
    if parameters.get("_rate_evidenced") is False:
        return None
    bitrate = _positive(parameters.get("arbitration_bitrate", parameters.get("bitrate")), 0)
    if normalized in {"CAN_FD", "CANFD"} and parameters.get('can_fd_brs') is not False:
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
