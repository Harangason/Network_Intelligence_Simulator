"""Projection over canonical package-owned technology definitions."""
from copy import deepcopy
from typing import Any
from importlib import import_module
DIRECT_IO_TECHNOLOGIES = frozenset({'gpio', 'pwm', 'adc', 'dac'})
PARAMETER_UI_ALIASES = {'bitrate_bps': 'bitrate', 'nominal_bitrate_bps': 'arbitration_bitrate', 'data_bitrate_bps': 'data_bitrate'}
PARAMETER_CORE_ALIASES = {'bitrate': 'bitrate_bps', 'arbitration_bitrate': 'nominal_bitrate_bps', 'data_bitrate': 'data_bitrate_bps'}
RESERVED_PARAMETER_NAMES = frozenset({'arbitration_bitrate',
           'bit_error_rate',
           'bitrate',
           'burst_factor',
           'burst_window_ms',
           'clock_drift_ppm',
           'clock_offset_ms',
           'corruption_probability',
           'critical_threshold',
           'cycle_ms',
           'data_bitrate',
           'deadline_ms',
           'distributed_clock_cycle_ms',
           'dropout_probability',
           'duplex',
           'duplicate_probability',
           'durability',
           'duration_s',
           'frame_loss_probability',
           'freshness_ms',
           'gateway_delay_ms',
           'gateway_input_buffer',
           'gateway_maximum_messages_s',
           'gateway_maximum_routes',
           'gateway_maximum_throughput',
           'gateway_output_buffer',
           'gateway_queue_delay_ms',
           'history_depth',
           'history_kind',
           'jitter_ms',
           'lifespan_ms',
           'liveliness',
           'max_events',
           'maximum_latency_ms',
           'maximum_sync_error_ms',
           'minimum_cycle_time_ms',
           'mtu_bytes',
           'overload_threshold',
           'packet_loss_probability',
           'payload_bytes',
           'peak_factor',
           'propagation_delay_ms',
           'protocol_conversion_delay_ms',
           'qos_priority',
           'queue_policy',
           'queue_size',
           'rate_limit_bit_s',
           'reliability_mode',
           'reordering_probability',
           'required_reliability',
           'reserved_bandwidth_percent',
           'retransmission_delay_ms',
           'retransmission_enabled',
           'retransmission_rate',
           'retry_limit',
           'sample_point_percent',
           'seed',
           'source_processing_delay_ms',
           'sync_interval_ms',
           'sync_method',
           'sync_precision_ms',
           'target_bus_load_percent',
           'target_processing_delay_ms',
           'timeout_ms',
           'traffic_class',
           'vlan_id',
           'warning_threshold'})

TECHNOLOGY_IDS = ('ethernet', 'ip', 'udp', 'tcp', 'can', 'can_fd', 'can_xl', 'lin', 'flexray', 'most', 'canopen', 'j1939', 'isobus', 'uds', 'xcp', 'ccp', 'someip', 'someip_sd', 'doip', 'obd2', 'avb', 'tsn', 'profinet', 'ethercat', 'ethernet_ip', 'modbus_tcp', 'modbus_rtu', 'modbus_ascii', 'profibus_dp', 'profibus_pa', 'devicenet', 'interbus', 'cc_link', 'cc_link_ie', 'sercos_iii', 'powerlink', 'io_link', 'io_link_wireless', 'opc_ua', 'opc_ua_pubsub', 'mqtt', 'sparkplug_b', 'dds', 'ros2', 'arinc429', 'afdx', 'mil_std_1553', 'can_aerospace', 'spacewire', 'tte', 'mvb', 'wtb', 'etb', 'trdp', 'nmea0183', 'nmea2000', 'iec61162', 'bacnet_ip', 'bacnet_mstp', 'bacnet_sc', 'knx_tp', 'knx_ip', 'knx_rf', 'lonworks', 'dali', 'm_bus', 'wireless_m_bus', 'iec61850', 'mms', 'goose', 'sampled_values', 'dnp3', 'iec60870_5_101', 'iec60870_5_104', 'sunspec_modbus', 'ocpp', 'hart', 'wirelesshart', 'foundation_fieldbus_h1', 'i2c', 'i3c', 'spi', 'uart', 'rs232', 'rs422', 'rs485', 'one_wire', 'usb', 'pcie', 'mipi_csi2', 'mipi_dsi', 'lvds', 'gpio', 'pwm', 'adc', 'dac', 'mqtt_sn', 'coap', 'http', 'websocket', 'amqp', 'wifi', 'bluetooth_le', 'zigbee', 'thread', 'matter', 'lorawan', 'lte_m', 'nb_iot', '5g', 'uwb', 'nfc', 'rfid', 'profisafe', 'cip_safety', 'fsoe', 'opensafety', 'generic_serial', 'generic_can', 'generic_ethernet', 'custom_udp', 'custom_tcp', 'custom_binary', 'custom_text', 'custom_protocol')

from json import loads
from pathlib import Path
from backend.nis.communication.technologies.can_fd.constants import CAN_FD_DATA_LENGTHS
from backend.nis.communication.technologies.dds.policies import DDS_POLICY_ENTITIES

def technology_identity(technology_id):
    path = Path(__file__).parent / 'technologies' / technology_id / 'identity.json'
    return loads(path.read_text(encoding='utf-8')) if path.is_file() else {}

def technology_review(technology_id):
    path = Path(__file__).parent / 'technologies' / technology_id / 'review.json'
    review = loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    profile_path = path.with_name('profile.json')
    profile = loads(profile_path.read_text(encoding='utf-8')) if profile_path.is_file() else {}
    if profile.get('parameter_proposals'):
        review['rate_proposal'] = profile['parameter_proposals']
    return review

REVIEW_RATE_PROPOSALS = {key: review['rate_proposal'] for key in TECHNOLOGY_IDS
                         if (review := technology_review(key)).get('legacy_rate_projection')}
LOCAL_EVIDENCE_FIELDS = {key.upper(): tuple(map(tuple, review['local_evidence_fields']))
                         for key in TECHNOLOGY_IDS
                         if (review := technology_review(key)).get('local_evidence_fields')}

def technology_definitions():
    return [deepcopy(import_module(f"backend.nis.communication.technologies.{key}.definition").PROFILE)
            for key in TECHNOLOGY_IDS]

def simulation_parameter_proposal(technology_id: str, profile: dict[str, Any], name: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Complete editable scenario examples; never actual device evidence.

    Use only this registered field's choices/bounds and its owner's preset.
    Keep original default/UNKNOWN declarations and physical gates intact.
    """
    preset = (profile.get('simulation_defaults') or {}).get('values', {})
    value = preset.get(name)
    basis = 'PROFILE_SIMULATION_PRESET' if name in preset else 'SCHEMA_SIMULATION_EXAMPLE'
    if value is None:
        kind = spec.get('type') or ('number' if spec.get('numeric') else 'boolean' if spec.get('boolean') else 'select' if spec.get('options') else 'text')
        if kind in {'number', 'integer'}:
            minimum = spec.get('min', spec.get('minimum', 0))
            maximum = spec.get('max', spec.get('maximum'))
            value = max(0, minimum if minimum is not None else 0)
            if maximum is not None:
                value = min(value, maximum)
            if spec.get('allowed_values'):
                value = spec['allowed_values'][0]
            if spec.get('multiple_of'):
                from math import ceil
                value = ceil(value / spec['multiple_of']) * spec['multiple_of']
            if spec.get('integer') or kind == 'integer':
                value = int(value)
        elif kind == 'boolean':
            value = False
        elif kind == 'select':
            choices = spec.get('options') or []
            value = choices[0] if choices else 'SIMULATION_UNSPECIFIED'
        else:
            formats = {'IP_ADDRESS': '192.0.2.1', 'IP_NETWORK': '192.0.2.0/24',
                       'WSS_URI': 'wss://simulation.invalid', 'ABSOLUTE_URI': 'https://simulation.invalid'}
            value = formats.get(spec.get('format'), f'simulation:{technology_id}:{name}')
            if spec.get('pattern'):
                import re
                # Schema-constrained examples, including unicast/multicast
                # addresses, UUIDs, object identifiers and encoded bytes.
                examples = ['0', 'GET', 'simulation_context', '1.3.6.1',
                            '02:00:00:00:00:01', '01:00:00:00:00:01',
                            '00000000-0000-4000-8000-000000000001']
                examples.extend('0' * length for length in range(2, 81))
                value = next((item for item in examples if re.fullmatch(spec['pattern'], item)), value)
    return {'value': value, 'basis': basis, 'source': 'NIS_SIMULATION_ASSUMPTION',
            'status': 'ASSUMED', 'technology': technology_id, 'hardware_evidence': False}


def _parameter_defaults_review(technology_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    """One review policy for every consumer; suggestions are never evidence."""
    model = profile.get("rate_model") or {}
    proposal = profile.get("parameter_proposals") or {}
    values, basis = {}, "NOT_APPLICABLE"
    if model.get("type") == "MULTI_PHASE_BITRATE":
        values = dict(model.get("defaults_bps") or {})
        basis = "PROFILE_PHASE_DEFAULTS" if values else "DEVICE_DEPENDENT"
    elif model.get("fields"):
        basis = "DEVICE_DEPENDENT"
        if model.get("type") != "DEVICE_DEPENDENT_CLOCK" and proposal.get('kind') != 'VARIANT_DEPENDENT':
            options = proposal.get("options") or []
            modes = [option["maximum"] for option in options if option.get("maximum", 0) > 0]
            allowed = model.get("allowed_bps") or model.get("typical_bps") or []
            if model.get("fixed_bps"):
                value, basis = model["fixed_bps"], "FIXED_PROFILE_RATE"
            elif proposal.get('default_bps'):
                value, basis = proposal['default_bps'], proposal.get('default_basis', 'LITERATURE_DEFAULT')
            elif modes:
                value, basis = min(modes), "STANDARD_MODE"
            elif allowed:
                value, basis = min(allowed), "LOWEST_PROFILE_MODE"
            elif model.get("minimum_bps", 0) > 1:
                value, basis = model["minimum_bps"], "PROFILE_MINIMUM"
            else:
                value, basis = proposal.get("candidate"), "CATALOG_REVIEW_CANDIDATE"
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
                values = {field: value for field in model["fields"]}
            else:
                basis = "DEVICE_DEPENDENT"
    return {"technology": technology_id, "rate_profile": profile["id"],
            "values": values, "basis": basis, "status": "REVIEW_REQUIRED",
            "source": proposal.get("source") or f"TechnologyProfile:{profile['id']}",
            "source_revision": proposal.get("source_revision")}

from backend.nis.industries.models import MODEL_TYPES
