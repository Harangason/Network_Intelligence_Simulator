"""Technology-owned frame and timing implementation; preserved calculation semantics."""
from __future__ import annotations
from math import ceil, isfinite
from typing import Any
from backend.nis.communication.core.timing import FrameEstimate, _positive

from .constants import CAN_FD_DATA_LENGTHS

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

def estimate_frame(protocol, payload_bytes, parameters):
    normalized = str(protocol or "CUSTOM").upper().replace("-", "_").replace(" ", "_")
    payload = max(0, int(payload_bytes))
    bitrate = _positive(parameters.get("bitrate"), 0.0)
    rate_confirmed = parameters.get("_rate_evidenced") is not False
    available = bitrate > 0 and rate_confirmed
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

def prepare_timing_parameters(payload_bytes, bitrate=None, *, arbitration_bitrate=None, data_bitrate=None, local_timing_evidence=None, can_fd_brs=None, can_frame_format=None, can_fd_dlc=None, can_fd_wire_data_bytes=None):
    technology_id = 'can_fd'
    nominal = arbitration_bitrate if arbitration_bitrate is not None else bitrate
    if can_fd_brs is not None and type(can_fd_brs) is not bool:
        raise ValueError('CAN FD BRS must be an actual boolean.')
    if not nominal or can_fd_brs is not False and not data_bitrate:
        raise ValueError("CAN FD benötigt bestätigte Arbitrierungs- und Datenphasenraten.")
    rate_parameters = {"nominal_bitrate_bps": nominal}
    if data_bitrate is not None:
        rate_parameters['data_bitrate_bps']=data_bitrate
    frame_parameters = {"bitrate": nominal,
                        "arbitration_bitrate": nominal,
                        "data_bitrate": data_bitrate}
    native = {key:value for key,value in {'can_fd_brs':can_fd_brs,'can_frame_format':can_frame_format,
                'can_fd_dlc':can_fd_dlc,'can_fd_wire_data_bytes':can_fd_wire_data_bytes}.items() if value is not None}
    if set(native) - {'can_fd_brs','can_frame_format','can_fd_dlc','can_fd_wire_data_bytes'}:
        raise ValueError('CAN timing options are not applicable to this technology.')
    rate_parameters.update(native)
    frame_parameters.update(native)
    return rate_parameters, frame_parameters

def validate_timing_scope(payload_bytes, bitrate, rate_parameters, frame_parameters):
    return None

FRAME_PROTOCOLS = ('CAN_FD', 'CANFD')

from .definition import PROFILE
SCHEDULE_PAYLOAD_LIMIT = PROFILE["max_payload_bytes"]
