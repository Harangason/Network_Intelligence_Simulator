"""Technology-owned frame and timing implementation; preserved calculation semantics."""
from __future__ import annotations
from math import ceil, isfinite
from typing import Any
from backend.nis.communication.core.timing import FrameEstimate, _positive

from backend.nis.communication.catalog import LOCAL_EVIDENCE_FIELDS, REVIEW_RATE_PROPOSALS

def confirmed_serial_evidence(protocol: str, parameters: dict[str, Any], payload_bytes: int=0) -> dict[str, Any] | None:
    """Require device-confirmed total transaction bounds before using I2C/SPI math."""
    technology = str(protocol or '').upper()
    evidence = parameters.get('local_timing_evidence') or {}
    if isinstance(evidence, dict):
        from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
        if any((registry.normalize_id(evidence[key]) != registry.normalize_id(protocol) for key in ('technology', 'protocol') if evidence.get(key))):
            return None
    if not isinstance(evidence, dict) or evidence.get('confirmed') is not True or (not isinstance(evidence.get('source'), str)) or (not evidence['source'].strip()):
        return None
    from backend.nis.communication.technologies.spi.rules import evidence_issues
    if evidence_issues(evidence, payload_bytes) or parameters.get('spi_bus_variant', 'SPI_SINGLE') != 'SPI_SINGLE':
        return None
    for key, local_key in [('bitrate_bps', 'bitrate_bps'), ('spi_cpol', 'cpol'), ('spi_cpha', 'cpha'), ('spi_word_bits', 'word_length_bits'), ('spi_duplex', 'duplex_mode'), ('spi_chip_select', 'chip_select')]:
        if key in parameters and parameters[key] != evidence.get(local_key):
            return None
    if not isinstance(evidence.get('master_node_id'), str) or not evidence['master_node_id'].strip() or _positive(evidence.get('bitrate_bps'), 0) <= 0:
        return None
    transfer_bits = _positive(evidence.get('transfer_bits_bound'), 0)
    if transfer_bits < max(0, payload_bytes) * 8:
        return None
    required = {'chip_select', 'word_length_bits', 'duplex_mode', 'cpol', 'cpha', 'cs_setup_bound_us', 'inter_transfer_gap_us'}
    if 'SPI' not in {'I2C', 'SPI'} or any((evidence.get(field) is None for field in required)):
        return None
    try:
        if not str(evidence['chip_select']).strip() or int(evidence['word_length_bits']) <= 0:
            return None
        if str(evidence['duplex_mode']).upper() not in {'FULL_DUPLEX', 'HALF_DUPLEX'}:
            return None
        if int(evidence['cpol']) not in {0, 1} or int(evidence['cpha']) not in {0, 1}:
            return None
        delay_fields = ('cs_setup_bound_us', 'inter_transfer_gap_us')
        if any((isinstance(evidence[field], bool) or not isfinite(float(evidence[field])) or float(evidence[field]) < 0 for field in delay_fields)):
            return None
    except (TypeError, ValueError, OverflowError, KeyError):
        return None
    return evidence

def serial_evidence_missing_fields(protocol: str, parameters: dict[str, Any], payload_bytes: int=0) -> list[str]:
    """Expose the concrete device review, separate from a saved network clock."""
    if confirmed_serial_evidence(protocol, parameters, payload_bytes) is not None:
        return []
    evidence = parameters.get('local_timing_evidence')
    evidence = evidence if isinstance(evidence, dict) else {}
    if str(protocol).upper() == 'I2C':
        from backend.nis.communication.technologies.i2c.rules import local_fields, evidence_issues
        scope = evidence.get('evidence_scope') or 'TRANSACTION'
        missing = [f['key'] for f in local_fields() if (not f.get('optional') and (not f.get('required_scopes') or scope in f['required_scopes'])) and (evidence.get(f['key']) is None or evidence.get(f['key']) == '')]
        if evidence.get('multi_master') is True and evidence.get('arbitration_bound_us') is None:
            missing.append('arbitration_bound_us')
        if not isinstance(evidence.get('source'), str) or not evidence.get('source', '').strip():
            missing.append('source')
        if evidence.get('confirmed') is not True:
            missing.append('confirmed')
        if scope in ('CONTROLLER_PORT', 'TARGET_PORT'):
            missing.append('transaction_evidence')
        if not missing:
            missing = evidence_issues(evidence, payload_bytes, require_transaction=True)
        return [f'local_timing_evidence.{key}' for key in dict.fromkeys(missing)] or ['local_timing_evidence.invalid_device_or_transaction_bounds']
    fields = [key for key, _ in LOCAL_EVIDENCE_FIELDS.get(str(protocol).upper(), ()) if key != 'arbitration_bound_us' or evidence.get('multi_master') is not False]
    missing = [key for key in fields if evidence.get(key) is None or evidence.get(key) == '']
    if not evidence.get('source'):
        missing.append('source')
    if evidence.get('confirmed') is not True:
        missing.append('confirmed')
    return [f'local_timing_evidence.{key}' for key in missing] or ['local_timing_evidence.invalid_device_or_transaction_bounds']

def estimate_frame(protocol, payload_bytes, parameters):
    normalized = str(protocol).upper()
    payload = max(0, int(payload_bytes))
    evidence = confirmed_serial_evidence(normalized, parameters, payload)
    model = f"{normalized}_CONFIRMED_{'TRANSACTION' if normalized == 'I2C' else 'TRANSFER'}_BOUND_V1"
    if evidence is None:
        return FrameEstimate(normalized, payload, 0, 0.0, model, is_generic_estimate=True, transmission_time_available=False)
    bits = int(evidence['transfer_bits_bound'])
    delay_us = float(evidence['cs_setup_bound_us']) + float(evidence['inter_transfer_gap_us'])
    return FrameEstimate(normalized, payload, bits, bits / float(evidence['bitrate_bps']) + delay_us / 1_000_000, model)

def prepare_timing_parameters(payload_bytes, bitrate=None, *, arbitration_bitrate=None, data_bitrate=None, local_timing_evidence=None, can_fd_brs=None, can_frame_format=None, can_fd_dlc=None, can_fd_wire_data_bytes=None):
    technology_id = 'spi'

    evidence = confirmed_serial_evidence(technology_id, {"local_timing_evidence": local_timing_evidence}, payload_bytes)
    if evidence is None:
        raise ValueError(f"{technology_id}: bestätigte Geräte- und Transaktionsgrenzen fehlen.")
    if bitrate is not None and bitrate != evidence["bitrate_bps"]:
        raise ValueError(f"{technology_id}: Bitrate widerspricht bestätigtem Geräteprofil.")
    bitrate = evidence["bitrate_bps"]
    rate_parameters = {"bitrate_bps": bitrate}
    frame_parameters = {"local_timing_evidence": evidence}
    native = {key:value for key,value in {'can_fd_brs':can_fd_brs,'can_frame_format':can_frame_format,
                'can_fd_dlc':can_fd_dlc,'can_fd_wire_data_bytes':can_fd_wire_data_bytes}.items() if value is not None}
    if set(native) - set():
        raise ValueError('CAN timing options are not applicable to this technology.')
    rate_parameters.update(native)
    frame_parameters.update(native)
    return rate_parameters, frame_parameters

def validate_timing_scope(payload_bytes, bitrate, rate_parameters, frame_parameters):
    return None

FRAME_PROTOCOLS = ('SPI',)
