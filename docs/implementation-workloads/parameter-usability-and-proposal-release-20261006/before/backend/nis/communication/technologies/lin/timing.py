"""Technology-owned frame and timing implementation; preserved calculation semantics."""
from __future__ import annotations
from math import ceil, isfinite
from typing import Any
from backend.nis.communication.core.timing import FrameEstimate, _positive

def estimate_frame(protocol, payload_bytes, parameters):
    normalized = str(protocol or "CUSTOM").upper().replace("-", "_").replace(" ", "_")
    payload = max(0, int(payload_bytes))
    bitrate = _positive(parameters.get("bitrate"), 0.0)
    rate_confirmed = parameters.get("_rate_evidenced") is not False
    available = bitrate > 0 and rate_confirmed
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    values = {key: value for key, value in parameters.items() if key in registry.parameter_keys('lin')}
    checked = registry.validate_parameters('lin', values)
    available = available and checked['status'] == 'VALID' and (
        parameters.get('lin_edition') == 'LIN_2_2A_2010' and
        parameters.get('lin_physical_profile') == 'LIN_2_2A_SINGLE_WIRE' and
        parameters.get('lin_frame_kind') not in {'WAKE_UP', 'REGISTERED_FRAME'} and 1 <= payload <= 8)
    if parameters.get('lin_frame_kind') in {'DIAGNOSTIC_REQUEST', 'DIAGNOSTIC_RESPONSE', 'GO_TO_SLEEP'}:
        available = available and payload == 8
    available = available and parameters.get('lin_data_octets', payload) == payload
    # Nominal LIN2.2A data frame; schedule and functional acceptance are separate.
    frame_bits = 34 + (payload + 1) * 10
    return FrameEstimate(normalized, payload, frame_bits, frame_bits / bitrate if available else 0.0,
                         "LIN_NOMINAL_WITH_CHECKSUM", calculation_version="2.0",
                         transmission_time_available=available)

from math import isfinite


def lin_schedule_check(rows: list[dict]) -> dict:
    def number(value):
        try:
            parsed = float(value or 0)
            return parsed if isfinite(parsed) and parsed > 0 else 0
        except (ValueError, TypeError):
            return 0
    lin = [row for row in rows if str(row.get('protocol') or '').upper() == 'LIN']
    if not lin:
        return {'status': 'NOT_APPLICABLE'}
    batch = sum(number(row.get('segment_transmission_latency_ms', row.get('transmission_latency_ms'))) for row in lin)
    budgets = []
    for row in lin:
        breakdown = row.get('breakdown') or {}
        overhead = sum(number(breakdown.get(key)) for key in ('source_processing_ms', 'target_processing_ms', 'gateway_processing_ms', 'propagation_ms'))
        for key in ('max_latency_ms', 'timeout_ms'):
            value = number(row.get(key))
            if value:
                budgets.append(max(0, value - overhead))
        period, jitter = number(row.get('cycle_ms')), number(row.get('jitter_budget_ms'))
        if period and jitter:
            budgets.append(period + jitter - overhead)
    budget = min(budgets) if budgets else None
    return {'status': 'FAIL' if budget is not None and batch > budget + .00001 else 'PASS',
            'synchronous_batch_ms': round(batch, 6), 'budget_ms': round(budget, 6) if budget is not None else None,
            'model': 'LIN_NON_PREEMPTIVE_BATCH_BOUND_V1'}

def prepare_timing_parameters(payload_bytes, bitrate=None, *, arbitration_bitrate=None, data_bitrate=None, local_timing_evidence=None, can_fd_brs=None, can_frame_format=None, can_fd_dlc=None, can_fd_wire_data_bytes=None):
    technology_id = 'lin'
    if not bitrate:
        raise ValueError(f"{technology_id} benötigt eine bestätigte Bitrate.")
    rate_parameters = {"bitrate_bps": bitrate}
    frame_parameters = {"bitrate": bitrate}
    native = {key:value for key,value in {'can_fd_brs':can_fd_brs,'can_frame_format':can_frame_format,
                'can_fd_dlc':can_fd_dlc,'can_fd_wire_data_bytes':can_fd_wire_data_bytes}.items() if value is not None}
    if set(native) - set():
        raise ValueError('CAN timing options are not applicable to this technology.')
    rate_parameters.update(native)
    frame_parameters.update(native)
    return rate_parameters, frame_parameters

def validate_timing_scope(payload_bytes, bitrate, rate_parameters, frame_parameters):
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    native_rate = rate_parameters.get('lin_bitrate_bps')
    if native_rate is not None and native_rate != bitrate:
        raise ValueError('LIN LDF rate conflicts with the explicit timing input.')
    rate_parameters.pop('bitrate_bps', None)
    rate_parameters['lin_bitrate_bps'] = bitrate
    report = DEFAULT_TECHNOLOGY_REGISTRY.validate_parameters('lin', rate_parameters)
    if report['status'] != 'VALID':
        raise ValueError(report['findings'][0]['message'])
    if rate_parameters['lin_edition'] != 'LIN_2_2A_2010' or rate_parameters['lin_physical_profile'] != 'LIN_2_2A_SINGLE_WIRE':
        raise ValueError('The nominal LIN 2.2A estimator does not qualify this edition or PHY.')
    if not 1 <= payload_bytes <= 8 or rate_parameters.get('lin_data_octets', payload_bytes) != payload_bytes:
        raise ValueError('LIN response must match its actual 1..8-octet frame layout.')
    kind = rate_parameters['lin_frame_kind']
    if kind in {'WAKE_UP','REGISTERED_FRAME'}:
        raise ValueError('This LIN frame kind is not covered by the nominal data-frame estimator.')
    if kind in {'DIAGNOSTIC_REQUEST','DIAGNOSTIC_RESPONSE','GO_TO_SLEEP'} and payload_bytes != 8:
        raise ValueError('LIN diagnostic and sleep frames require an 8-octet response.')

FRAME_PROTOCOLS = ('LIN',)

from .definition import PROFILE
SCHEDULE_PAYLOAD_LIMIT = PROFILE["max_payload_bytes"]
