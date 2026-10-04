"""As-built technology documentation catalog.

Registration and implementation status are deliberately independent.  The
catalog is broad; only technologies with executable core support are marked
IMPLEMENTED/PARTIAL/EXPERIMENTAL/LEGACY by ``technology_definitions``.
"""

from __future__ import annotations

from typing import Any
from copy import deepcopy

from .core.physical import physical_profile
from . import i2c as i2c_rules
from . import i3c as i3c_rules
from . import iec101 as iec101_rules
from . import iec104 as iec104_rules
from . import iec61162 as iec61162_rules
from . import iec61850 as iec61850_rules
from . import interbus as interbus_rules
from . import io_link as io_link_rules
from . import io_link_wireless as io_link_wireless_rules
from . import ip as ip_rules
from . import isobus as isobus_rules
from . import j1939 as j1939_rules
from . import knx_ip as knx_ip_rules
from . import knx_rf as knx_rf_rules
from . import knx_tp as knx_tp_rules
from . import lin as lin_rules
from . import lonworks as lonworks_rules
from . import lorawan as lorawan_rules
from . import lte_m as lte_m_rules
from . import lvds as lvds_rules
from . import m_bus as m_bus_rules
from . import matter as matter_rules
from . import mil_std_1553 as mil1553_rules
from . import mipi_csi2 as csi2_rules
from . import mipi_dsi as dsi_rules
from . import mms as mms_rules
from . import modbus_ascii as ascii_rules
from . import modbus_rtu as rtu_rules
from . import modbus_tcp as mtcp_rules
from . import most as most_rules
from . import mqtt as mqtt_rules
from . import mqtt_sn as mqtt_sn_rules
from . import mvb as mvb_rules
from . import nb_iot as nb_iot_rules
from . import nfc as nfc_rules
from . import nmea0183 as nmea0183_rules
from . import nmea2000 as nmea2000_rules
from . import obd2 as obd2_rules
from . import ocpp as ocpp_rules
from . import one_wire as one_wire_rules
from . import opc_ua as opc_ua_rules
from . import opc_ua_pubsub as opc_ua_pubsub_rules
from . import opensafety as opensafety_rules
from . import pcie as pcie_rules
from . import powerlink as powerlink_rules
from . import profibus_dp as profibus_dp_rules
from . import profibus_pa as profibus_pa_rules
from . import profinet as profinet_rules
from . import profisafe as profisafe_rules
from . import pwm as pwm_rules
from . import rfid as rfid_rules
from . import ros2 as ros2_rules
from . import rs232 as rs232_rules
from . import rs422 as rs422_rules
from . import rs485 as rs485_rules
from . import sampled_values as sampled_values_rules
from . import sercos_iii as sercos_iii_rules
from . import someip as someip_rules
from . import someip_sd as someip_sd_rules
from . import spacewire as spacewire_rules
from . import sparkplug_b as sparkplug_b_rules
from . import spi as spi_rules
from . import sunspec_modbus as sunspec_rules
from . import tcp as tcp_rules
from . import thread as thread_rules
from . import trdp as trdp_rules
from . import tsn as tsn_rules
from . import tte as tte_rules
from . import uart as uart_rules
from . import udp as udp_rules
from . import uds as uds_rules
from . import usb as usb_rules
from . import uwb as uwb_rules
from . import websocket as websocket_rules
from . import wifi as wifi_rules
from . import wireless_m_bus as wireless_m_bus_rules
from . import wirelesshart as wirelesshart_rules
from . import wtb as wtb_rules
from . import xcp as xcp_rules
from . import zigbee as zigbee_rules

COAP_TRANSMIT_SPAN={'product':['coap_ack_timeout_s',{'subtract':[{'power':[2,'coap_max_retransmit']},1]},'coap_ack_random_factor']}
COAP_TRANSMIT_WAIT={'product':['coap_ack_timeout_s',{'subtract':[{'power':[2,{'sum':['coap_max_retransmit',1]}]},1]},'coap_ack_random_factor']}
COAP_MAX_RTT={'sum':[{'product':[2,'coap_max_latency_s']},'coap_processing_delay_s']}
COAP_UDP_FIELDS=('coap_version','coap_message_type','coap_message_id','coap_ack_timeout_s','coap_ack_random_factor',
                 'coap_max_retransmit','coap_nstart','coap_default_leisure_s','coap_probing_rate_Bps',
                 'coap_max_latency_s','coap_processing_delay_s','coap_max_transmit_span_s','coap_max_transmit_wait_s',
                 'coap_max_rtt_s','coap_exchange_lifetime_s','coap_non_lifetime_s','coap_non_repeat','coap_congestion_control_verified')

DDS_COMMON_ENTITIES = ('TOPIC', 'DATAWRITER', 'DATAREADER')
DDS_ALL_ENTITIES = (*DDS_COMMON_ENTITIES, 'PUBLISHER', 'SUBSCRIBER', 'PARTICIPANT', 'PARTICIPANT_FACTORY')
DDS_POLICY_ENTITIES = {
    **{key: DDS_COMMON_ENTITIES for key in ('history_depth', 'history_kind', 'durability', 'liveliness', 'reliability_mode',
       'dds_type_source', 'dds_topic_name', 'dds_deadline_kind', 'dds_deadline_ms', 'dds_latency_budget_ms',
       'dds_lease_kind', 'dds_lease_ms', 'dds_destination_order', 'dds_max_samples', 'dds_max_instances',
       'dds_max_samples_per_instance', 'dds_ownership')},
    **{key: ('TOPIC', 'DATAWRITER') for key in ('lifespan_ms', 'dds_lifespan_kind', 'dds_transport_priority',
       'dds_service_cleanup_kind', 'dds_service_cleanup_ms', 'dds_service_history_kind', 'dds_service_history_depth',
       'dds_service_max_samples', 'dds_service_max_instances', 'dds_service_max_samples_per_instance')},
    **{key: ('DATAWRITER',) for key in ('dds_max_blocking_ms', 'dds_ownership_strength', 'dds_autodispose_unregistered')},
    **{key: ('DATAREADER',) for key in ('dds_time_based_filter_ms', 'dds_nowriter_purge_kind', 'dds_nowriter_purge_ms',
       'dds_disposed_purge_kind', 'dds_disposed_purge_ms')},
    **{key: ('PUBLISHER', 'SUBSCRIBER') for key in ('dds_presentation_scope', 'dds_coherent_access', 'dds_ordered_access',
       'dds_partition_source', 'dds_group_data_source')},
    'dds_autoenable_created_entities': ('PUBLISHER', 'SUBSCRIBER', 'PARTICIPANT', 'PARTICIPANT_FACTORY'),
    'dds_user_data_source': ('PARTICIPANT', 'DATAWRITER', 'DATAREADER'),
    'dds_topic_data_source': ('TOPIC',),
    **{key: DDS_ALL_ENTITIES for key in ('dds_entity', 'dds_transport_binding', 'dds_implementation_source', 'dds_domain_id')},
}

TECHNOLOGY_SEMANTICS: dict[str, dict[str, Any]] = {
    'etb': {
        'rate_model': {'type': 'SINGLE_BITRATE', 'fields': ['bitrate_bps'], 'minimum_bps': 1},
        'required_parameters': ['bitrate_bps','etb_phy','etb_edition','etb_configuration_source','etb_node_role','etb_physical_binding'],
        'mechanisms': {'transport': ['EXPLICIT_ETB_BACKBONE_NOT_ECN'],
                       'arbitration': ['FULL_DUPLEX_SWITCH_QUEUES_AND_TTDP_REDUNDANT_ACTIVE_LINK'],
                       'topology': ['CONSIST_UUID_ETBN_ECN_TTDP_INAUGURATION']},
        'parameter_constraints': [
            *[{'when': {'etb_phy': phy}, 'parameter': 'bitrate_bps', 'allowed': [rate]}
              for phy,rate in (('100BASE_TX',100000000),('1000BASE_T',1000000000))],
            *[{'when': {'etb_phy': phy}, 'parameter': 'duplex', 'allowed': ['FULL']}
              for phy in ('100BASE_TX','1000BASE_T')],
            {'when': {'etb_frame_profile':'BASIC_MAC'}, 'parameter':'payload_bytes', 'maximum':1500},
            {'when': {'etb_frame_profile':'BASIC_MAC'}, 'parameter':'mtu_bytes', 'maximum':1500},
            {'when': {}, 'parameter':'payload_bytes', 'maximum_parameter':'mtu_bytes'},
            {'when': {}, 'parameter':'rate_limit_bit_s', 'maximum_parameter':'bitrate_bps'},
            {'when': {'etb_implementation':'WEOS_5'}, 'parameter':'etb_local_id', 'maximum':32},
            {'when': {'etb_implementation':'WEOS_5'}, 'parameter':'etb_ecn_id', 'maximum':4},
            {'when': {'etb_implementation':'WEOS_5'}, 'parameter':'etb_backbone_id', 'allowed':[0,1]},
            *[{'when': {'etb_implementation':'WEOS_5'}, 'parameter':key, 'maximum':2}
              for key in ('etb_dir1_ports','etb_dir2_ports')],
            {'when': {'etb_aggregation':'TTDP_ACTIVE_STANDBY'}, 'parameter':'etb_active_links_per_direction', 'maximum':1},
            {'when': {'etb_implementation':'WEOS_5'}, 'parameter':'etb_igmp_snooping', 'allowed':[False]},
            {'when': {'etb_implementation':'WEOS_5'}, 'parameter':'etb_topology_vlan', 'allowed':[492]},
            *[{'when': {'etb_inauguration':state}, 'parameter':'etb_traffic_enabled', 'allowed':[False]}
              for state in ('PENDING','FAILED')],
            {'when': {'etb_traffic_enabled':True,'etb_traffic_scope':'INTER_CONSIST'}, 'parameter':'etb_message_topology_counter', 'equal_parameter':'etb_topology_counter'},
            {'when': {}, 'parameter':'etb_hello_timeout_ms', 'minimum_parameter':'etb_hello_period_ms'},
            {'when': {'etb_phy':'100BASE_TX'}, 'parameter':'etb_clock_role', 'allowed':[]},
            {'when': {'etb_phy':'100BASE_TX'}, 'parameter':'etb_peer_clock_role', 'allowed':[]},
            *[{'when': {'etb_phy':'1000BASE_T','etb_clock_role':role}, 'parameter':'etb_peer_clock_role', 'allowed':[peer,'AUTO']}
              for role,peer in (('MASTER','FOLLOWER'),('FOLLOWER','MASTER'))],
            {'when': {}, 'parameter':'etb_active_links_per_direction', 'maximum_parameter':'etb_dir1_ports'},
            {'when': {}, 'parameter':'etb_active_links_per_direction', 'maximum_parameter':'etb_dir2_ports'},
        ],
    },
    'dali': {
        'rate_model': {'type': 'FIXED_LINK_RATE', 'fields': ['bitrate_bps'], 'fixed_bps': 1200},
        'mechanisms': {'encoding': ['MANCHESTER_MSB_FIRST'], 'transport': ['WIRED_TWO_WIRE_BUS_POWER'],
                       'arbitration': ['EXPLICIT_SINGLE_OR_MULTI_MASTER_TIMING'],
                       'framing': ['FORWARD_16_FORWARD_24_EVENT_24_BACKWARD_8']},
        'parameter_constraints': [
            *[{'when': {'dali_frame': frame}, 'parameter': 'payload_bytes', 'allowed': [length]}
              for frame, length in (('FORWARD_16', 2), ('FORWARD_24', 3), ('EVENT_24', 3), ('BACKWARD_8', 1))],
            {'when': {'dali_frame': 'FORWARD_16'}, 'parameter': 'dali_address_space', 'allowed': ['CONTROL_GEAR']},
            *[{'when': {'dali_frame': frame}, 'parameter': 'dali_address_space', 'allowed': ['CONTROL_DEVICE']}
              for frame in ('FORWARD_24', 'EVENT_24')],
            {'when': {'dali_revision': 'VERSION_1'}, 'parameter': 'dali_frame', 'allowed': ['FORWARD_16', 'BACKWARD_8']},
            {'when': {'dali_revision': 'VERSION_1'}, 'parameter': 'dali_address_space', 'allowed': ['CONTROL_GEAR']},
            {'when': {'dali_address_space': 'CONTROL_GEAR'}, 'parameter': 'dali_group_address', 'maximum': 15},
            {'when': {'dali_address_space': 'CONTROL_DEVICE'}, 'parameter': 'dali_scene', 'allowed': []},
            {'when': {'dali_addressing': 'SHORT'}, 'parameter': 'dali_group_address', 'allowed': []},
            {'when': {'dali_addressing': 'GROUP'}, 'parameter': 'dali_short_address', 'allowed': []},
            *[{'when': {'dali_addressing': mode}, 'parameter': key, 'allowed': []}
              for mode in ('BROADCAST', 'BROADCAST_UNADDRESSED') for key in ('dali_group_address', 'dali_short_address')],
            {'when': {'dali_master_mode': 'SINGLE_MASTER'}, 'parameter': 'dali_controller_count', 'allowed': [1]},
            {'when': {'dali_revision': 'VERSION_1'}, 'parameter': 'dali_control_device_count', 'allowed': []},
            {'when': {}, 'parameter': 'dali_guaranteed_supply_ma', 'maximum_parameter': 'dali_maximum_supply_ma'},
            {'when': {}, 'parameter': 'dali_bus_demand_ma', 'maximum_parameter': 'dali_guaranteed_supply_ma'},
            {'when': {}, 'parameter': 'dali_reply_min_ms', 'maximum_parameter': 'dali_reply_max_ms'},
            {'when_half_open_ranges': {'dali_cable_cross_section_mm2': [1.5, None]}, 'when': {},
             'parameter': 'dali_farthest_distance_m', 'maximum': 300},
            {'when': {}, 'parameter': 'dali_cable_cross_section_mm2', 'exclusive_minimum': 0},
            {'when': {}, 'parameter': 'dali_bus_voltage_v', 'exclusive_minimum': 0},
            {'when': {}, 'parameter': 'dali_total_cable_m', 'minimum_parameter': 'dali_farthest_distance_m'},
            {'when': {}, 'parameter': 'dali_controller_count', 'maximum_parameter': 'dali_control_device_count'},
            {'when': {'dali_address_space': 'CONTROL_GEAR'}, 'parameter': 'dali_instance', 'allowed': []},
            {'when': {'dali_repeat_required': False}, 'parameter': 'dali_repeat_window_ms', 'allowed': []},
            *[{'when': {}, 'parameter': key, 'exclusive_minimum': 0}
              for key in ('dali_forward_bound_ms', 'dali_backward_bound_ms', 'dali_repeat_window_ms')],
        ],
    },
    'custom_udp': {
        'rate_model': {'type': 'INHERITED_OR_NOT_APPLICABLE', 'fields': []},
        'mechanisms': {'transport': ['EXPLICIT_UDP_IP_LINK_BINDING'],
                       'framing': ['APPLICATION_PDU_IN_UDP_DATAGRAM'],
                       'reliability': ['NO_UDP_ACK_ORDER_OR_DEDUP_GUARANTEE'],
                       'integrity': ['UDP_PSEUDOHEADER_CHECKSUM_NOT_AUTHENTICATION']},
        'parameter_constraints': [
            {'when': {}, 'parameter': 'cudp_message_bytes', 'equal_expression': {'sum': ['payload_bytes', 'cudp_application_header_bytes', 'cudp_application_trailer_bytes']}},
            {'when': {}, 'parameter': 'cudp_datagram_bytes', 'equal_expression': {'sum': ['cudp_message_bytes', 8]}},
            {'when': {}, 'parameter': 'cudp_message_bytes', 'maximum_parameter': 'cudp_peer_message_limit_bytes'},
            {'when': {}, 'parameter': 'cudp_full_body_bytes', 'minimum_parameter': 'payload_bytes'},
            {'when': {'cudp_ip_version': 'IPV4'}, 'parameter': 'cudp_size_mode', 'allowed': ['NORMAL']},
            {'when': {'cudp_ip_version': 'IPV4'}, 'parameter': 'payload_bytes', 'maximum': 65507},
            {'when': {'cudp_ip_version': 'IPV4'}, 'parameter': 'cudp_message_bytes', 'maximum': 65507, 'maximum_expression': {'subtract': [65527, 'cudp_ipv4_header_bytes']}},
            {'when': {'cudp_ip_version': 'IPV4'}, 'parameter': 'cudp_datagram_bytes', 'maximum_expression': {'subtract': [65535, 'cudp_ipv4_header_bytes']}},
            {'when': {'cudp_ip_version': 'IPV4'}, 'parameter': 'cudp_ip_packet_bytes', 'equal_expression': {'sum': ['cudp_datagram_bytes', 'cudp_ipv4_header_bytes']}, 'maximum': 65535},
            {'when': {'cudp_ip_version': 'IPV6', 'cudp_size_mode': 'NORMAL'}, 'parameter': 'payload_bytes', 'maximum': 65527},
            {'when': {'cudp_ip_version': 'IPV6', 'cudp_size_mode': 'NORMAL'}, 'parameter': 'cudp_message_bytes', 'maximum': 65527, 'maximum_expression': {'subtract': [65527, 'cudp_ipv6_extension_bytes']}},
            {'when': {'cudp_ip_version': 'IPV6', 'cudp_size_mode': 'NORMAL'}, 'parameter': 'cudp_datagram_bytes', 'maximum_expression': {'subtract': [65535, 'cudp_ipv6_extension_bytes']}},
            {'when': {'cudp_ip_version': 'IPV6'}, 'parameter': 'cudp_ip_packet_bytes', 'equal_expression': {'sum': [40, 'cudp_datagram_bytes', 'cudp_ipv6_extension_bytes']}, 'minimum': 48},
            {'when': {'cudp_size_mode': 'NORMAL'}, 'parameter': 'cudp_datagram_bytes', 'maximum': 65535},
            {'when': {'cudp_size_mode': 'NORMAL'}, 'parameter': 'cudp_udp_length_field', 'equal_parameter': 'cudp_datagram_bytes', 'minimum': 8},
            {'when': {'cudp_ip_version': 'IPV6', 'cudp_size_mode': 'NORMAL'}, 'parameter': 'cudp_ipv6_payload_length', 'equal_expression': {'sum': ['cudp_datagram_bytes', 'cudp_ipv6_extension_bytes']}, 'minimum': 8},
            {'when': {'cudp_size_mode': 'JUMBO'}, 'parameter': 'cudp_ip_version', 'allowed': ['IPV6']},
            {'when': {'cudp_size_mode': 'JUMBO'}, 'parameter': 'cudp_ipv6_payload_length', 'allowed': [0]},
            {'when': {'cudp_size_mode': 'JUMBO'}, 'parameter': 'cudp_jumbo_payload_length', 'equal_expression': {'sum': ['cudp_datagram_bytes', 'cudp_ipv6_extension_bytes']}},
            {'when': {'cudp_size_mode': 'JUMBO'}, 'parameter': 'cudp_ipv6_extension_bytes', 'minimum': 8},
            {'when': {'cudp_size_mode': 'JUMBO'}, 'parameter': 'cudp_datagram_bytes', 'maximum_expression': {'subtract': [4294967295, 'cudp_ipv6_extension_bytes']}},
            *[{'when': {'cudp_size_mode': 'JUMBO'}, 'parameter': key, 'maximum': 4294967279, 'maximum_expression': {'subtract': [4294967287, 'cudp_ipv6_extension_bytes']}}
              for key in ('payload_bytes', 'cudp_message_bytes')],
            {'when': {'cudp_size_mode': 'JUMBO'}, 'when_half_open_ranges': {'cudp_datagram_bytes': [65536, None]}, 'parameter': 'cudp_udp_length_field', 'allowed': [0]},
            {'when': {'cudp_size_mode': 'JUMBO'}, 'when_half_open_ranges': {'cudp_datagram_bytes': [8, 65536]}, 'parameter': 'cudp_udp_length_field', 'equal_parameter': 'cudp_datagram_bytes'},
            {'when': {'cudp_size_mode': 'JUMBO'}, 'parameter': 'cudp_fragmentation_policy', 'allowed': ['NO_IP_FRAGMENTATION']},
            {'when': {'cudp_jumbo_supported': False}, 'parameter': 'cudp_size_mode', 'allowed': ['NORMAL']},
            {'when': {'cudp_size_mode': 'NORMAL'}, 'parameter': 'cudp_jumbo_payload_length', 'allowed': []},
            *[{'when': {'cudp_ip_version': 'IPV4'}, 'parameter': key, 'allowed': []}
              for key in ('cudp_ipv6_extension_bytes', 'cudp_ipv6_payload_length', 'cudp_jumbo_payload_length')],
            {'when': {'cudp_ip_version': 'IPV6'}, 'parameter': 'cudp_ipv4_header_bytes', 'allowed': []},
            {'when': {'cudp_ip_version': 'IPV6'}, 'parameter': 'cudp_checksum_policy', 'allowed': ['ENABLED']},
            {'when': {'cudp_checksum_policy': 'IPV4_DISABLED'}, 'parameter': 'cudp_udp_checksum_value', 'allowed': [0]},
            {'when': {'cudp_checksum_policy': 'ENABLED'}, 'parameter': 'cudp_udp_checksum_value', 'minimum': 1},
            {'when': {'cudp_fragmentation_policy': 'NO_IP_FRAGMENTATION'}, 'parameter': 'cudp_ip_packet_bytes', 'maximum_parameter': 'cudp_path_mtu_bytes'},
            *[{'when': {'cudp_application_ack': False}, 'parameter': key, 'allowed': []}
              for key in ('cudp_ack_timeout_ms', 'cudp_ack_retry_limit')],
            {'when': {}, 'parameter': 'cudp_ack_timeout_ms', 'exclusive_minimum': 0},
        ],
    },
    'custom_text': {
        'rate_model': {'type': 'INHERITED_OR_NOT_APPLICABLE', 'fields': []},
        'mechanisms': {'encoding': ['EXPLICIT_CHARSET_AND_SCALAR_BYTE_COUNTS'],
                       'framing': ['EXPLICIT_TEXT_MESSAGE_FRAMING'],
                       'transport': ['EXPLICIT_LOWER_TRANSPORT_BINDING']},
        'parameter_constraints': [
            {'when': {}, 'parameter': 'ctxt_message_bytes', 'equal_expression':
             {'sum': ['payload_bytes', 'ctxt_header_bytes', 'ctxt_trailer_bytes', 'ctxt_escape_expansion_bytes']}},
            {'when': {}, 'parameter': 'ctxt_message_bytes', 'maximum_parameter': 'ctxt_peer_message_limit_bytes'},
            {'when': {'ctxt_framing': 'FIXED_LENGTH'}, 'parameter': 'ctxt_message_bytes', 'equal_parameter': 'ctxt_fixed_length_bytes'},
            *[{'when': {'ctxt_framing': framing}, 'parameter': 'ctxt_delimiter_hex', 'allowed': []}
              for framing in ('FIXED_LENGTH', 'LENGTH_PREFIX', 'TRANSPORT_MESSAGE', 'CONNECTION_CLOSE', 'CUSTOM')],
            *[{'when': {'ctxt_framing': framing}, 'parameter': 'ctxt_fixed_length_bytes', 'allowed': []}
              for framing in ('DELIMITER', 'LENGTH_PREFIX', 'TRANSPORT_MESSAGE', 'CONNECTION_CLOSE', 'CUSTOM')],
            {'when': {'ctxt_encoding': 'ASCII'}, 'parameter': 'payload_bytes', 'equal_parameter': 'ctxt_code_points'},
            {'when': {'ctxt_encoding': 'UTF8'}, 'parameter': 'payload_bytes', 'minimum_parameter': 'ctxt_code_points'},
            {'when': {'ctxt_encoding': 'UTF8'}, 'parameter': 'payload_bytes', 'maximum_parameter': 'ctxt_code_points', 'maximum_factor': 4},
            *[{'when': {'ctxt_encoding': encoding}, 'parameter': 'payload_bytes', 'equal_expression': {'product': [2, 'ctxt_utf16_code_units']}}
              for encoding in ('UTF16LE', 'UTF16BE')],
            *[{'when': {'ctxt_encoding': encoding}, 'parameter': 'payload_bytes', 'multiple_of': 2,
               'minimum_expression': {'product': [2, 'ctxt_code_points']},
               'maximum_expression': {'product': [4, 'ctxt_code_points']}}
              for encoding in ('UTF16LE', 'UTF16BE')],
            *[{'when': {'ctxt_encoding': encoding}, 'parameter': 'ctxt_utf16_code_units', 'minimum_parameter': 'ctxt_code_points', 'maximum_parameter': 'ctxt_code_points', 'maximum_factor': 2}
              for encoding in ('UTF16LE', 'UTF16BE')],
            *[{'when': {'ctxt_encoding': encoding}, 'parameter': 'ctxt_utf16_code_units', 'allowed': []}
              for encoding in ('ASCII', 'UTF8')],
            *[{'when': {'ctxt_encoding': encoding}, 'parameter': 'ctxt_text_value', 'text_encoding': codec,
               'encoded_bytes_parameter': 'payload_bytes', 'text_codepoints_parameter': 'ctxt_code_points',
               **({'text_utf16_units_parameter': 'ctxt_utf16_code_units'} if encoding.startswith('UTF16') else {})}
              for encoding, codec in (('ASCII', 'ascii'), ('UTF8', 'utf-8'), ('UTF16LE', 'utf-16le'), ('UTF16BE', 'utf-16be'))],
        ],
    },
    'custom_tcp': {
        'rate_model': {'type': 'INHERITED_OR_NOT_APPLICABLE', 'fields': []},
        'mechanisms': {'transport': ['EXPLICIT_TCP_IP_LINK_BINDING'],
                       'framing': ['APPLICATION_BOUNDARIES_OVER_TCP_BYTE_STREAM'],
                       'reliability': ['TCP_DELIVERY_IS_NOT_APPLICATION_ACKNOWLEDGEMENT']},
        'parameter_constraints': [
            {'when': {}, 'parameter': 'ctcp_message_bytes', 'equal_expression':
             {'sum': ['payload_bytes', 'ctcp_header_bytes', 'ctcp_trailer_bytes', 'ctcp_escape_expansion_bytes']}},
            {'when': {}, 'parameter': 'ctcp_message_bytes', 'maximum_parameter': 'ctcp_peer_message_limit_bytes'},
            {'when': {'ctcp_framing': 'FIXED_LENGTH'}, 'parameter': 'ctcp_message_bytes', 'equal_parameter': 'ctcp_fixed_length_bytes'},
            *[{'when': {'ctcp_framing': framing}, 'parameter': 'ctcp_length_prefix_bytes', 'allowed': []}
              for framing in ('FIXED_LENGTH', 'DELIMITER', 'CONNECTION_CLOSE', 'CUSTOM')],
            *[{'when': {'ctcp_framing': framing}, 'parameter': 'ctcp_fixed_length_bytes', 'allowed': []}
              for framing in ('LENGTH_PREFIX', 'DELIMITER', 'CONNECTION_CLOSE', 'CUSTOM')],
            *[{'when': {'ctcp_framing': framing}, 'parameter': 'ctcp_delimiter_hex', 'allowed': []}
              for framing in ('FIXED_LENGTH', 'LENGTH_PREFIX', 'CONNECTION_CLOSE', 'CUSTOM')],
            {'when': {'ctcp_application_ack': False}, 'parameter': 'ctcp_application_ack_timeout_ms', 'allowed': []},
            {'when': {}, 'parameter': 'ctcp_application_ack_timeout_ms', 'exclusive_minimum': 0},
        ],
    },
    'custom_protocol': {
        'rate_model': {'type': 'INHERITED_OR_NOT_APPLICABLE', 'fields': []},
        'mechanisms': {'encoding': ['EXPLICIT_PROTOCOL_DATA_UNIT_LAYOUT'],
                       'addressing': ['EXPLICIT_APPLICATION_ADDRESSING'],
                       'reliability': ['EXPLICIT_PROTOCOL_ACKNOWLEDGEMENT_AND_RETRY_STATE'],
                       'session': ['EXPLICIT_APPLICATION_SESSION_CONTRACT']},
        'parameter_constraints': [
            {'when': {}, 'parameter': 'cp_pdu_bytes', 'equal_expression': {'sum': ['payload_bytes', 'cp_overhead_bytes']}},
            {'when': {}, 'parameter': 'cp_pdu_bytes', 'maximum_parameter': 'cp_peer_pdu_limit_bytes'},
            *[{'when': {'cp_acknowledgement': 'NONE'}, 'parameter': key, 'allowed': []}
              for key in ('cp_ack_timeout_ms', 'cp_response_bound_ms', 'cp_retry_limit', 'cp_retry_delay_ms')],
            {'when': {}, 'parameter': 'cp_ack_timeout_ms', 'exclusive_minimum': 0},
            {'when': {}, 'parameter': 'cp_response_bound_ms', 'maximum_parameter': 'cp_ack_timeout_ms'},
            *[{'when': {'cp_acknowledgement': 'LOWER_TRANSPORT_ONLY'}, 'parameter': key, 'allowed': []}
              for key in ('cp_ack_timeout_ms', 'cp_response_bound_ms', 'cp_retry_limit', 'cp_retry_delay_ms')],
        ],
    },
    'custom_binary': {
        'rate_model': {'type': 'INHERITED_OR_NOT_APPLICABLE', 'fields': []},
        'mechanisms': {'encoding': ['EXPLICIT_BINARY_LAYOUT'],
                       'framing': ['EXPLICIT_APPLICATION_FRAMING'],
                       'integrity': ['EXPLICIT_CHECKSUM_SPECIFICATION']},
        'parameter_constraints': [
            {'when': {}, 'parameter': 'cb_message_bytes', 'equal_expression':
             {'sum': ['payload_bytes', 'cb_header_bytes', 'cb_trailer_bytes', 'cb_padding_bytes']}},
            {'when': {}, 'parameter': 'cb_message_bytes', 'maximum_parameter': 'cb_peer_message_limit_bytes'},
            {'when': {'cb_framing': 'FIXED_LENGTH'}, 'parameter': 'cb_message_bytes', 'equal_parameter': 'cb_fixed_length_bytes'},
            {'when': {'cb_checksum': 'NONE'}, 'parameter': 'cb_checksum_bytes', 'allowed': [0]},
            {'when': {'cb_checksum': 'NONE'}, 'parameter': 'cb_checksum_source', 'allowed': []},
            {'when': {'cb_framing': 'LENGTH_PREFIX'}, 'parameter': 'cb_length_prefix_bytes', 'minimum': 1},
            *[{'when': {'cb_framing': framing}, 'parameter': 'cb_length_prefix_bytes', 'allowed': []}
              for framing in ('FIXED_LENGTH', 'DELIMITER', 'TRANSPORT_MESSAGE', 'CUSTOM')],
            *[{'when': {'cb_framing': framing}, 'parameter': 'cb_fixed_length_bytes', 'allowed': []}
              for framing in ('LENGTH_PREFIX', 'DELIMITER', 'TRANSPORT_MESSAGE', 'CUSTOM')],
            *[{'when': {'cb_framing': framing}, 'parameter': 'cb_delimiter_hex', 'allowed': []}
              for framing in ('FIXED_LENGTH', 'LENGTH_PREFIX', 'TRANSPORT_MESSAGE', 'CUSTOM')],
        ],
    },
    'coap': {
        'rate_model':{'type':'INHERITED_OR_NOT_APPLICABLE','fields':[]},
        'mechanisms':{'addressing':['COAP_URI','REQUEST_RESPONSE_TOKEN'],
                      'reliability':['UDP_CONFIRMABLE_ACK_RETRANSMIT','RELIABLE_TRANSPORT_CSM'],
                      'flow_control':['COAP_UDP_CONGESTION_CONTROL','COAP_BLOCKWISE','BERT_IF_NEGOTIATED'],
                      'supervision':['COAP_OBSERVE_OPTION','COAP_MAX_AGE'],
                      'security':['EXPLICIT_DTLS_TLS_OR_OSCORE_PROFILE']},
        'parameter_constraints':[
            *[{'when':{'coap_transport':transport},'parameter':key,'allowed':[]} for transport in ('TCP','TLS','WS','WSS') for key in COAP_UDP_FIELDS],
            *[{'when':{'coap_transport':transport},'parameter':key,'allowed':[]} for transport in ('UDP','DTLS') for key in ('coap_csm_max_message_bytes','coap_csm_blockwise_supported')],
            {'when':{'coap_token_format':'BASE_8'},'parameter':'coap_token_bytes','maximum':8},
            {'when':{},'parameter':'coap_token_bytes','maximum_parameter':'coap_peer_token_limit'},
            *[{'when':{'coap_transport':transport},'parameter':'coap_block_szx','maximum':6} for transport in ('UDP','DTLS')],
            {'when':{'coap_csm_blockwise_supported':False},'parameter':'coap_block_szx','maximum':6},
            {'when':{'coap_block_szx':7},'parameter':'coap_csm_max_message_bytes','exclusive_minimum':1152},
            *[{'when':{'coap_block_usage':'DESCRIPTIVE','coap_block_more':True,'coap_block_szx':szx},'parameter':'payload_bytes','allowed':[2**(szx+4)]} for szx in range(7)],
            {'when':{'coap_block_usage':'DESCRIPTIVE','coap_block_more':True,'coap_block_szx':7},'parameter':'payload_bytes','multiple_of':1024,'minimum':1024},
            {'when':{'coap_block_kind':'BLOCK2','coap_block_usage':'CONTROL'},'parameter':'coap_block_more','allowed':[False]},
            {'when':{'coap_observe_kind':'REQUEST'},'parameter':'coap_observe_value','allowed':[0,1]},
            {'when':{'coap_mtu_policy':'UNKNOWN_PATH_RFC7252'},'parameter':'payload_bytes','maximum':1024},
            {'when':{'coap_mtu_policy':'UNKNOWN_PATH_RFC7252'},'parameter':'coap_message_bytes','maximum':1152},
            *[{'when':{'coap_transport':transport},'parameter':'coap_multicast','allowed':[False]} for transport in ('TCP','TLS','WS','WSS')],
            {'when':{'coap_congestion_control_verified':False},'parameter':'coap_ack_timeout_s','minimum':2},
            {'when':{'coap_congestion_control_verified':False},'parameter':'coap_nstart','maximum':1},
            *[{'when':{},'parameter':key,'exclusive_minimum':0} for key in ('coap_ack_timeout_s','coap_default_leisure_s','coap_probing_rate_Bps')],
            {'when':{},'parameter':'coap_max_transmit_span_s','equal_expression':COAP_TRANSMIT_SPAN},
            {'when':{},'parameter':'coap_max_transmit_wait_s','equal_expression':COAP_TRANSMIT_WAIT},
            {'when':{},'parameter':'coap_max_rtt_s','equal_expression':COAP_MAX_RTT},
            {'when':{},'parameter':'coap_exchange_lifetime_s','minimum_expression':{'sum':[COAP_TRANSMIT_SPAN,COAP_MAX_RTT]}},
            {'when':{},'parameter':'coap_exchange_lifetime_s','minimum_expression':COAP_TRANSMIT_WAIT},
            {'when':{'coap_non_repeat':True},'parameter':'coap_non_lifetime_s','minimum_expression':{'sum':[COAP_TRANSMIT_SPAN,'coap_max_latency_s']}},
            {'when':{'coap_non_repeat':False},'parameter':'coap_non_lifetime_s','minimum_parameter':'coap_max_latency_s'},
            {'when':{},'parameter':'coap_message_bytes','minimum_expression':{'sum':['payload_bytes','coap_token_bytes','coap_options_bytes','coap_header_bytes','coap_payload_marker_bytes']}},
            {'when':{},'parameter':'coap_message_bytes','maximum_parameter':'coap_csm_max_message_bytes'},
            {'when':{'coap_message_type':'RST'},'parameter':'payload_bytes','allowed':[0]},
            {'when':{'coap_message_type':'RST'},'parameter':'coap_code','allowed':[0]},
            {'when':{'coap_message_type':'RST'},'parameter':'coap_token_bytes','allowed':[0]},
            {'when':{'coap_message_type':'RST'},'parameter':'coap_options_bytes','allowed':[0]},
            {'when':{'coap_code':0},'parameter':'payload_bytes','allowed':[0]},
            {'when':{'coap_code':0},'parameter':'coap_token_bytes','allowed':[0]},
            {'when':{'coap_code':0},'parameter':'coap_options_bytes','allowed':[0]},
            {'when':{'payload_bytes':0},'parameter':'coap_payload_marker_bytes','allowed':[0]},
            {'when':{},'when_positive':['payload_bytes'],'parameter':'coap_payload_marker_bytes','allowed':[1]},
            *[{'when':{'coap_transport':transport},'parameter':'coap_header_bytes','minimum':4} for transport in ('UDP','DTLS')],
            *[{'when':{'coap_transport':transport},'parameter':'coap_uri','pattern':pattern} for transport,pattern in (
                ('UDP','(?i)coap://.*'),('DTLS','(?i)coaps://.*'),('TCP','(?i)coap\\+tcp://.*'),
                ('TLS','(?i)coaps\\+tcp://.*'),('WS','(?i)coap\\+ws://.*'),('WSS','(?i)coaps\\+ws://.*'))],
        ],
    },
    'cip_safety': {
        'rate_model':{'type':'INHERITED_OR_NOT_APPLICABLE','fields':[]},
        'mechanisms':{'integrity':['CIP_SAFETY_CRC_24','LONG_DATA_CRC_16_INVERTED_DATA','BLACK_CHANNEL'],
                      'addressing':['SAFETY_NETWORK_NUMBER_NODE_ADDRESS','PRODUCTION_IDENTIFIER'],
                      'supervision':['TIMESTAMP_NETWORK_TIME_EXPECTATION','TIME_COORDINATION','MAXIMUM_FAULT_NUMBER'],
                      'session':['SAFETY_OPEN','CONFIGURATION_SIGNATURE_OWNERSHIP_LOCKING']},
        'parameter_constraints':[
            {'when':{'cips_baseline':'MODERN_EXTENDED'},'parameter':'cips_format','allowed':['EXTENDED']},
            {'when':{'cips_baseline':'MODERN_EXTENDED'},'parameter':'cips_max_fault_number','allowed':[2]},
            {'when':{'cips_data_size':'SHORT'},'parameter':'payload_bytes','maximum':2},
            {'when':{'cips_data_size':'LONG'},'parameter':'payload_bytes','minimum':3},
            {'when':{'cips_connection':'UNICAST'},'parameter':'cips_consumers','allowed':[1]},
            {'when':{'cips_connection':'MULTICAST'},'parameter':'cips_consumers','maximum':15},
            {'when':{'cips_connection':'UNICAST'},'parameter':'cips_time_correction_bound_ms','allowed':[]},
            *[{'when':{},'parameter':key,'exclusive_minimum':0} for key in ('cips_rpi_ms','cips_safety_task_ms','cips_crtl_ms','cips_application_reaction_limit_ms')],
            {'when':{},'parameter':'cips_data_age_bound_ms','maximum_parameter':'cips_crtl_ms'},
            {'when':{},'parameter':'cips_crtl_ms','maximum_parameter':'cips_application_reaction_limit_ms'},
            {'when':{'cips_transport':'DEVICENET'},'parameter':'cips_devicenet_node','maximum':63},
            {'when':{'cips_transport':'DEVICENET'},'parameter':'cips_ip_address','allowed':[]},
            {'when':{'cips_transport':'ETHERNET_IP'},'parameter':'cips_devicenet_node','allowed':[]},
            {'when':{'cips_transport':'SERCOS_III'},'parameter':'cips_devicenet_node','allowed':[]},
            {'when':{'cips_transport':'SERCOS_III'},'parameter':'cips_ip_address','allowed':[]},
            {'when':{'cips_device_profile':'GUARDLOGIX_SAFETY_IO'},'parameter':'cips_timeout_multiplier','maximum':4},
            {'when':{'cips_device_profile':'GUARDLOGIX_SAFETY_IO'},'parameter':'cips_network_delay_percent','minimum':10,'maximum':600},
            {'when':{'cips_device_profile':'GUARDLOGIX_SAFETY_IO','cips_direction':'OUTPUT'},'parameter':'cips_rpi_ms','equal_parameter':'cips_safety_task_ms'},
        ],
    },
    'ccp': {
        'rate_model':{'type':'SINGLE_BITRATE','fields':['bitrate_bps'],'maximum_bps':1000000,'inherited_from':'can'},
        'mechanisms':{'addressing':['CCP_STATION_ADDRESS','CRO_CAN_ID','DTO_CAN_ID','DAQ_ODT_PID'],
                      'integrity':['CAN_CRC'],'flow_control':['CCP_COMMAND_COUNTER_CRM','CCP_DAQ_EVENT_PRESCALER'],
                      'session':['CCP_LOGICAL_CONNECT','CCP_DEVICE_RESOURCE_PROTECTION']},
        'parameter_constraints':[
            {'when':{},'parameter':'can_frame_type','allowed':['DATA']},
            *[{'when':{'ccp_object':obj},'parameter':'payload_bytes','allowed':[8]} for obj in ('CRO','CRM','EVENT')],
            {'when':{'ccp_object':'CRM'},'parameter':'ccp_pid','allowed':[255]},
            {'when':{'ccp_object':'EVENT'},'parameter':'ccp_pid','allowed':[254]},
            {'when':{'ccp_object':'DAQ'},'parameter':'ccp_pid','maximum':253},
            {'when':{'ccp_object':'DAQ'},'parameter':'payload_bytes','equal_parameter':'ccp_data_bytes','equal_parameter_offset':1},
            {'when':{'ccp_object':'CRO'},'parameter':'ccp_data_bytes','maximum':6},
            *[{'when':{'ccp_object':obj},'parameter':'ccp_data_bytes','maximum':5} for obj in ('CRM','EVENT')],
            {'when':{'ccp_object':'CRO'},'parameter':'ccp_pid','allowed':[]},
            {'when':{'ccp_object':'DAQ'},'parameter':'ccp_error_code','allowed':[]},
            {'when':{'ccp_object':'EVENT'},'parameter':'ccp_response_counter','allowed':[]},
            {'when':{'ccp_object':'CRM'},'parameter':'ccp_response_counter','equal_parameter':'ccp_command_counter'},
            *[{'when':{key+'_format':'BASE_11'},'parameter':key,'maximum':2047} for key in ('ccp_cro_id','ccp_dto_id','ccp_daq_can_id')],
            {'when':{},'parameter':'ccp_response_bound_ms','maximum_parameter':'ccp_response_timeout_ms'},
            *[{'when':{},'parameter':key,'exclusive_minimum':0} for key in ('ccp_response_timeout_ms','ccp_event_period_ms')],
        ],
    },
    'cc_link_ie': {
        'rate_model':{'type':'ETHERNET_LINK_RATE','fields':['bitrate_bps'],'allowed_bps':[100000000,1000000000]},
        'mechanisms':{'integrity':['ETHERNET_FCS'],'addressing':['EXPLICIT_CCLINK_IE_VARIANT_ADDRESSING'],
                      'arbitration':['VARIANT_SPECIFIC_TOKEN_POLLING_OR_TIME_SHARING']},
        'parameter_constraints':[
            {'when':{'ccie_variant':'CONTROLLER'},'parameter':'bitrate_bps','allowed':[1000000000]},
            {'when':{'ccie_variant':'FIELD'},'parameter':'bitrate_bps','allowed':[1000000000]},
            {'when':{'ccie_variant':'FIELD_BASIC'},'parameter':'ccie_access','allowed':['UDP_MANAGER_POLLING']},
            {'when':{'ccie_variant':'CONTROLLER'},'parameter':'ccie_access','allowed':['TOKEN_PASSING']},
            {'when':{'ccie_variant':'FIELD'},'parameter':'ccie_access','allowed':['TOKEN_PASSING']},
            {'when':{'ccie_variant':'TSN'},'parameter':'ccie_access','allowed':['TIME_SHARING','TIME_MANAGED_POLLING']},
            {'when':{'ccie_variant':'CONTROLLER'},'parameter':'ccie_nodes','maximum':120},
            {'when':{'ccie_variant':'FIELD'},'parameter':'ccie_nodes','maximum':254},
            {'when':{'ccie_variant':'FIELD_BASIC'},'parameter':'ccie_device_slots','maximum':64},
            {'when':{'ccie_variant':'TSN'},'parameter':'ccie_nodes','maximum':64770},
            {'when':{},'parameter':'ccie_transient_bytes','maximum_parameter':'ccie_transient_limit_bytes'},
            {'when':{'ccie_variant':'TSN'},'parameter':'ccie_station_cyclic_bytes','maximum':4294967296},
            {'when':{'ccie_variant':'FIELD_BASIC'},'parameter':'ccie_topology','allowed':['LINE','STAR','LINE_STAR']},
            {'when':{'ccie_variant':'CONTROLLER','ccie_phy':'1000BASE_SX'},'parameter':'ccie_topology','allowed':['RING']},
            {'when':{'ccie_phy':'100BASE_TX'},'parameter':'bitrate_bps','allowed':[100000000]},
            {'when':{'ccie_phy':'1000BASE_T'},'parameter':'bitrate_bps','allowed':[1000000000]},
            {'when':{'ccie_phy':'1000BASE_SX'},'parameter':'bitrate_bps','allowed':[1000000000]},
            {'when':{'ccie_phy':'100BASE_TX'},'parameter':'ccie_link_length_m','maximum':100},
            {'when':{'ccie_phy':'1000BASE_T'},'parameter':'ccie_link_length_m','maximum':100},
            {'when':{'ccie_phy':'1000BASE_SX'},'parameter':'ccie_link_length_m','maximum':550},
            {'when':{'ccie_phy':'SI_POF'},'parameter':'ccie_link_length_m','maximum':20},
            {'when':{'ccie_phy':'SI_HPCF'},'parameter':'ccie_link_length_m','maximum':100},
            {'when':{'ccie_variant':'FIELD'},'parameter':'ccie_phy','allowed':['1000BASE_T']},
            {'when':{'ccie_variant':'CONTROLLER'},'parameter':'ccie_phy','allowed':['1000BASE_T','1000BASE_SX']},
            {'when':{'ccie_variant':'FIELD_BASIC'},'parameter':'ccie_phy','allowed':['100BASE_TX','1000BASE_T']},
            {'when':{'ccie_variant':'FIELD_BASIC'},'parameter':'ccie_station_rx_bits','maximum_parameter':'ccie_occupied_stations','maximum_factor':64},
            {'when':{'ccie_variant':'FIELD_BASIC'},'parameter':'ccie_station_ry_bits','maximum_parameter':'ccie_occupied_stations','maximum_factor':64},
            {'when':{'ccie_variant':'FIELD_BASIC'},'parameter':'ccie_station_rwr_words','maximum_parameter':'ccie_occupied_stations','maximum_factor':32},
            {'when':{'ccie_variant':'FIELD_BASIC'},'parameter':'ccie_station_rww_words','maximum_parameter':'ccie_occupied_stations','maximum_factor':32},
            {'when':{},'parameter':'ccie_device_slots','minimum_parameter':'ccie_device_count'},
            {'when':{'ccie_variant':'FIELD_BASIC'},'parameter':'ccie_station_number','maximum_parameter':'ccie_occupied_stations','maximum_factor':-1,'maximum_offset':65},
            {'when':{'ccie_basic_controller':'MELSEC_IQ_F'},'parameter':'ccie_basic_timeout_ms','minimum':20},
            {'when':{'ccie_variant':'FIELD_BASIC','ccie_basic_optional_1g_supported':False},'parameter':'bitrate_bps','allowed':[100000000]},
            {'when':{'ccie_controller_mode':'NORMAL'},'parameter':'ccie_controller_lb_bits','maximum':16384},
            {'when':{'ccie_controller_mode':'NORMAL'},'parameter':'ccie_controller_lw_words','maximum':16384},
            {'when':{'ccie_controller_mode':'EXTENDED'},'parameter':'ccie_controller_lb_bits','maximum':32768},
            {'when':{'ccie_controller_mode':'EXTENDED'},'parameter':'ccie_controller_lw_words','maximum':131072},
            {'when':{'ccie_controller_network_extended':False},'parameter':'ccie_controller_network_lb_bits','maximum':32768},
            {'when':{'ccie_controller_network_extended':False},'parameter':'ccie_controller_network_lw_words','maximum':131072},
            {'when':{},'parameter':'ccie_tsn_guard_us','maximum_parameter':'ccie_tsn_gate_period_us'},
            {'when':{},'parameter':'ccie_tsn_guard_us','maximum_parameter':'ccie_tsn_cycle_us'},
        ],
    },
    'cc_link': {
        'rate_model': {'type':'SINGLE_BITRATE','fields':['bitrate_bps'],
                       'allowed_bps':[156000,625000,2500000,5000000,10000000]},
        'mechanisms': {'integrity':['CCLINK_CRC16'], 'addressing':['CCLINK_STATION_NUMBER'],
                       'synchronization':['CCLINK_FRAME_SYNCHRONIZATION'],
                       'arbitration':['CCLINK_BROADCAST_POLLING'], 'encoding':['NRZI_HDLC']},
        'parameter_constraints': [
            {'when':{'ccl_protocol_version':'1.10'},'parameter':'ccl_extended_cycle','allowed':[1]},
            {'when':{'ccl_station_role':'MANAGER'},'parameter':'ccl_station_number','allowed':[0]},
            {'when':{},'parameter':'ccl_station_number','maximum_parameter':'ccl_occupied_stations','maximum_factor':-1,'maximum_offset':65},
            {'when':{},'parameter':'ccl_total_occupied_stations','minimum_parameter':'ccl_device_count'},
            {'when':{'ccl_topology':'T_BRANCH'},'parameter':'bitrate_bps','allowed':[156000,625000]},
            {'when':{'ccl_topology':'T_BRANCH'},'parameter':'ccl_branch_length_m','maximum':8},
            {'when':{'ccl_topology':'T_BRANCH'},'parameter':'ccl_branch_devices','maximum':6},
            {'when':{'ccl_cable_version':'1.10','ccl_topology':'LINE'},'parameter':'ccl_remote_spacing_m','minimum':0.2},
            {'when':{'ccl_cable_version':'1.10','ccl_topology':'LINE'},'parameter':'ccl_special_spacing_m','minimum':0.2},
            {'when':{'ccl_topology':'T_BRANCH'},'parameter':'ccl_remote_spacing_m','exclusive_minimum':0.3},
            {'when':{'ccl_cable_version':'1.00_STANDARD'},'parameter':'ccl_remote_spacing_m','minimum':0.3},
            {'when':{'ccl_topology':'T_BRANCH','ccl_special_nodes_present':False},'parameter':'ccl_special_spacing_m','exclusive_minimum':1},
            {'when':{'ccl_topology':'T_BRANCH','ccl_special_nodes_present':True},'parameter':'ccl_special_spacing_m','exclusive_minimum':2},
            {'when':{'ccl_cable_version':'1.00_STANDARD','ccl_special_nodes_present':False},'parameter':'ccl_special_spacing_m','minimum':1},
            {'when':{'ccl_cable_version':'1.00_STANDARD','ccl_special_nodes_present':True},'parameter':'ccl_special_spacing_m','minimum':2},
            {'when':{},'parameter':'ccl_branch_total_m','minimum_parameter':'ccl_branch_length_m'},
            {'when':{'bitrate_bps':10000000,'ccl_cable_version':'1.10','ccl_topology':'LINE'},
             'when_greater_than':{'ccl_main_length_m':80},'when_half_open_ranges':{'ccl_device_count':[10,None]},
             'parameter':'ccl_consecutive_ten_span_m','minimum':10},
            {'when':{'ccl_controller_profile':'QJ61BT11N'},'parameter':'ccl_q_transient_send_words',
             'maximum_parameter':'ccl_q_transient_receive_words','maximum_factor':-1,'maximum_offset':4096},
        ],
    },
    'can_xl': {
        'rate_model': {'type':'MULTI_PHASE_BITRATE','fields':['nominal_bitrate_bps','data_bitrate_bps'],
                       'minimum_bps':1,'nominal_maximum_bps':1000000},
        'mechanisms': {'arbitration':['CAN_XL_11_BIT_PRIORITY_ID'],
                       'addressing':['CAN_XL_ACCEPTANCE_FIELD_32','CAN_XL_VCID_8','CAN_XL_SDT_8'],
                       'integrity':['CAN_XL_PCRC_13','CAN_XL_FCRC_32'],
                       'clocking':['CAN_XL_ARBITRATION_DATA_PHASES','OPTIONAL_SIC_XL_PWM_MODE_SWITCH']},
        'parameter_constraints': [
            {'when':{},'parameter':'payload_bytes','equal_parameter':'can_xl_dlc','equal_parameter_offset':1},
            {'when':{},'parameter':'data_bitrate_bps','maximum_parameter':'can_xl_transceiver_max_bps'},
            {'when':{'can_xl_mode_switching':True},'parameter':'can_xl_phy','allowed':['CAN_SIC_XL']},
            {'when':{},'parameter':'can_sjw_tq','maximum_parameter':'can_tseg1_tq'},
            {'when':{},'parameter':'can_sjw_tq','maximum_parameter':'can_tseg2_tq'},
            {'when':{},'parameter':'nominal_bitrate_bps','equal_ratio':{'numerator_parameter':'can_clock_hz',
                'denominator_product':['can_prescaler'],'denominator_sum':['can_tseg1_tq','can_tseg2_tq'],'denominator_offset':1}},
            {'when':{},'parameter':'sample_point_percent','equal_ratio':{'numerator_sum':['can_tseg1_tq'],'numerator_offset':1,
                'factor':100,'denominator_sum':['can_tseg1_tq','can_tseg2_tq'],'denominator_offset':1}},
            {'when':{},'parameter':'data_bitrate_bps','equal_ratio':{'numerator_parameter':'can_clock_hz',
                'denominator_product':['can_xl_data_prescaler'],'denominator_sum':['can_xl_data_tseg1_tq','can_xl_data_tseg2_tq'],'denominator_offset':1}},
            {'when':{},'parameter':'can_xl_data_sample_point_percent','equal_ratio':{'numerator_sum':['can_xl_data_tseg1_tq'],
                'numerator_offset':1,'factor':100,'denominator_sum':['can_xl_data_tseg1_tq','can_xl_data_tseg2_tq'],'denominator_offset':1}},
            {'when':{},'parameter':'can_xl_data_sjw_tq','maximum_parameter':'can_xl_data_tseg1_tq'},
            {'when':{},'parameter':'can_xl_data_sjw_tq','maximum_parameter':'can_xl_data_tseg2_tq'},
            {'when':{'can_controller_profile':'X_CAN_3_9'},'parameter':'can_xl_data_prescaler','equal_parameter':'can_prescaler'},
            {'when':{'can_controller_profile':'X_CAN_3_9'},'parameter':'can_prescaler','maximum':32},
            {'when':{'can_controller_profile':'X_CAN_3_9'},'parameter':'can_xl_data_prescaler','maximum':32},
            {'when':{'can_controller_profile':'X_CAN_3_9'},'parameter':'can_tseg1_tq','minimum':2,'maximum':512},
            {'when':{'can_controller_profile':'X_CAN_3_9'},'parameter':'can_tseg2_tq','minimum':2,'maximum':128},
            {'when':{'can_controller_profile':'X_CAN_3_9'},'parameter':'can_sjw_tq','maximum':128},
            {'when':{'can_controller_profile':'X_CAN_3_9'},'parameter':'can_xl_data_tseg1_tq','maximum':256},
            {'when':{'can_controller_profile':'X_CAN_3_9'},'parameter':'can_xl_data_tseg2_tq','minimum':2,'maximum':128},
            {'when':{'can_controller_profile':'X_CAN_3_9'},'parameter':'can_xl_data_sjw_tq','maximum':128},
            {'when':{'can_controller_profile':'X_CAN_3_9'},'parameter':'data_bitrate_bps','maximum':20000000},
            {'when':{'can_controller_profile':'X_CAN_3_9','can_xl_mode_switching':True},'parameter':'can_xl_pwm_offset_clocks',
                'maximum_ratio':{'numerator_sum':['can_xl_pwm_short_clocks','can_xl_pwm_long_clocks'],'denominator_offset':1},
                'exclusive_maximum_ratio':True},
        ],
    },
    'can_aerospace': {
        'rate_model': {'type':'SINGLE_BITRATE','fields':['bitrate_bps'],'minimum_bps':1,'maximum_bps':1000000,'inherited_from':'can'},
        'mechanisms': {'integrity':['CAN_CRC'],'addressing':['CAN_IDENTIFIER','NODE_ID'],
                       'supervision':['MESSAGE_CODE_MODULO_256','IDENTIFICATION_SERVICE'],
                       'synchronization':['NODE_SYNCHRONISATION_SERVICE']},
        'parameter_constraints': [
            {'when': {}, 'parameter':'can_identifier','equal_sum':[{'parameter':'canas_base_identifier'}, {'parameter':'canas_redundancy_level','factor':65536}]},
            {'when': {'can_frame_format':'BASE_11'}, 'parameter':'canas_redundancy_level','allowed':[0]},
            {'when': {'can_frame_format':'BASE_11'}, 'parameter':'can_identifier','maximum':2047},
            {'when': {}, 'parameter':'can_dlc','equal_parameter':'payload_bytes','equal_parameter_offset':4},
            {'when': {}, 'parameter':'canas_response_bound_ms','maximum':100},
            {'when': {'canas_message_class':'NSH'}, 'parameter':'canas_service_channel','minimum':0,'maximum':35},
            {'when': {'canas_message_class':'NSL'}, 'parameter':'canas_service_channel','minimum':100,'maximum':115},
            {'when': {'canas_message_class':'NSH','canas_service_role':'REQUEST'}, 'parameter':'canas_base_identifier',
             'equal_sum':[{'parameter':'canas_service_channel','factor':2}],'equal_sum_offset':128},
            {'when': {'canas_message_class':'NSH','canas_service_role':'RESPONSE'}, 'parameter':'canas_base_identifier',
             'equal_sum':[{'parameter':'canas_service_channel','factor':2}],'equal_sum_offset':129},
            {'when': {'canas_message_class':'NSL','canas_service_role':'REQUEST'}, 'parameter':'canas_base_identifier',
             'equal_sum':[{'parameter':'canas_service_channel','factor':2}],'equal_sum_offset':1800},
            {'when': {'canas_message_class':'NSL','canas_service_role':'RESPONSE'}, 'parameter':'canas_base_identifier',
             'equal_sum':[{'parameter':'canas_service_channel','factor':2}],'equal_sum_offset':1801},
            {'when': {'canas_message_class':'NOD','canas_nod_service_code_used':False}, 'parameter':'canas_service_code_octet','allowed':[0]},
            {'when': {}, 'when_ranges':{'canas_data_type':[32,99]},'parameter':'canas_data_type','allowed':[]},
        ],
    },
    'bluetooth_le': {
        'rate_model': {'type': 'SINGLE_BITRATE', 'fields': ['bitrate_bps'],
                       'allowed_bps': [125000, 500000, 1000000, 2000000]},
        'parameter_constraints': [
            {'when': {'ble_tx_phy':'LE_1M'}, 'parameter':'bitrate_bps', 'allowed':[1000000]},
            {'when': {'ble_tx_phy':'LE_2M'}, 'parameter':'bitrate_bps', 'allowed':[2000000]},
            {'when': {'ble_tx_phy':'LE_CODED_S2'}, 'parameter':'bitrate_bps', 'allowed':[500000]},
            {'when': {'ble_tx_phy':'LE_CODED_S8'}, 'parameter':'bitrate_bps', 'allowed':[125000]},
            {'when': {'ble_2m_supported':False}, 'parameter':'ble_tx_phy', 'allowed':['LE_1M','LE_CODED_S2','LE_CODED_S8']},
            {'when': {'ble_coded_supported':False}, 'parameter':'ble_tx_phy', 'allowed':['LE_1M','LE_2M']},
            {'when': {'ble_2m_supported':False}, 'parameter':'ble_rx_phy', 'allowed':['LE_1M','LE_CODED_S2','LE_CODED_S8']},
            {'when': {'ble_coded_supported':False}, 'parameter':'ble_rx_phy', 'allowed':['LE_1M','LE_2M']},
            {'when': {'ble_interval_set':'BASELINE'}, 'parameter':'ble_connection_interval_us', 'minimum':7500, 'multiple_of':1250},
            {'when': {'ble_interval_set':'ROUNDED'}, 'parameter':'ble_connection_interval_us', 'minimum':1250, 'multiple_of':1250},
            {'when': {'ble_interval_set':'EXTENDED'}, 'parameter':'ble_connection_interval_us', 'multiple_of':125},
            {'when': {'ble_short_intervals_supported':False}, 'parameter':'ble_interval_set', 'allowed':['BASELINE']},
            {'when': {}, 'parameter':'ble_continuation_number', 'maximum_parameter':'ble_subrate_factor', 'maximum_offset':-1},
            {'when': {'ble_subrating_supported':False}, 'parameter':'ble_subrate_factor', 'allowed':[1]},
            {'when': {}, 'parameter':'ble_supervision_timeout_ms', 'minimum_product_parameters':[
                {'parameter':'ble_connection_interval_us'}, {'parameter':'ble_subrate_factor'},
                {'parameter':'ble_peripheral_latency','offset':1}], 'minimum_product_factor':0.002, 'exclusive_minimum_product':True},
            {'when': {}, 'parameter':'ble_peripheral_latency', 'bounded_product_parameters':[
                {'parameter':'ble_subrate_factor'},{'parameter':'ble_peripheral_latency','offset':1}], 'maximum_product':500},
            {'when': {}, 'parameter':'payload_bytes', 'maximum_parameter':'ble_local_max_tx_octets'},
            {'when': {}, 'parameter':'payload_bytes', 'maximum_parameter':'ble_remote_max_rx_octets'},
            {'when': {'ble_dle_supported':False}, 'parameter':'ble_local_max_tx_octets', 'allowed':[27]},
            {'when': {'ble_dle_supported':False}, 'parameter':'ble_local_max_rx_octets', 'allowed':[27]},
            {'when': {}, 'parameter':'ble_local_max_tx_octets', 'maximum_parameter':'ble_supported_max_tx_octets'},
            {'when': {}, 'parameter':'ble_local_max_rx_octets', 'maximum_parameter':'ble_supported_max_rx_octets'},
            {'when': {}, 'parameter':'ble_local_max_tx_time_us', 'maximum_parameter':'ble_supported_max_tx_time_us'},
            {'when': {}, 'parameter':'ble_local_max_rx_time_us', 'maximum_parameter':'ble_supported_max_rx_time_us'},
        ],
        'mechanisms': {'arbitration':['LE_CENTRAL_CONNECTION_EVENTS','ADAPTIVE_FREQUENCY_HOPPING'],
                       'integrity':['LE_CRC24','OPTIONAL_AES_CCM_MIC'],
                       'addressing':['LE_PUBLIC_OR_RANDOM_DEVICE_ADDRESS','LE_ACCESS_ADDRESS'],
                       'reliability':['LE_SN_NESN_ACK','LE_CONNECTION_SUPERVISION'],
                       'security':['LE_PAIRING_AND_DEVICE_SECURITY_POLICY']},
    },
    'bacnet_sc': {
        'parameter_constraints': [
            {'when': {}, 'parameter': 'payload_bytes', 'maximum_parameter': 'bacnet_max_apdu_bytes'},
            {'when': {}, 'parameter': 'payload_bytes', 'maximum_parameter': 'sc_npdu_bytes',
             'maximum_subtract_parameters': ['sc_npci_header_bytes']},
            {'when': {}, 'parameter': 'sc_npdu_bytes', 'maximum_parameter': 'sc_peer_max_npdu_bytes'},
            {'when': {}, 'parameter': 'sc_npdu_bytes', 'maximum_parameter': 'sc_peer_max_bvlc_bytes',
             'maximum_subtract_parameters': ['sc_bvlc_base_header_bytes', 'sc_destination_options_bytes', 'sc_data_options_bytes']},
            {'when': {'sc_connection_type': 'HUB'}, 'parameter': 'sc_websocket_subprotocol', 'allowed': ['hub.bsc.bacnet.org']},
            {'when': {'sc_connection_type': 'DIRECT'}, 'parameter': 'sc_websocket_subprotocol', 'allowed': ['dc.bsc.bacnet.org']},
            {'when': {'sc_vmac_kind': 'RANDOM_48'}, 'parameter': 'sc_vmac', 'pattern': r'[0-9a-fA-F]2[0-9a-fA-F]{10}'},
            {'when': {'sc_reconnect_timeout_modifiable': False}, 'parameter': 'sc_min_reconnect_s', 'minimum': 10, 'maximum': 30},
            {'when': {'sc_heartbeat_timeout_modifiable': False}, 'parameter': 'sc_heartbeat_s', 'minimum': 30, 'maximum': 300},
            {'when': {}, 'parameter': 'sc_min_reconnect_s', 'maximum_parameter': 'sc_max_reconnect_s'},
            {'when_positive': ['bacnet_apdu_retries'], 'parameter': 'bacnet_apdu_timeout_ms', 'minimum': 1},
            {'when_positive': ['bacnet_apdu_retries'], 'parameter': 'bacnet_segment_timeout_ms', 'minimum': 1},
        ],
        'mechanisms': {'addressing': ['VMAC_EUI48_OR_RANDOM48', 'DEVICE_UUID', 'WSS_URI'],
                       'security': ['TLS_1_3_MUTUAL_AUTHENTICATION', 'OPERATIONAL_CERTIFICATE', 'SITE_CA_STORE'],
                       'flow_control': ['BACNET_SC_HUB_CONNECTION', 'OPTIONAL_DIRECT_CONNECTION', 'BACNET_SC_HEARTBEAT'],
                       'reliability': ['TCP_ORDERED_BYTE_STREAM', 'BACNET_CONFIRMED_SERVICE_RETRY']},
    },
    'bacnet_mstp': {
        'rate_model': {'type': 'SINGLE_BITRATE', 'fields': ['bitrate_bps'],
                       'allowed_bps': [9600, 19200, 38400, 57600, 76800, 115200]},
        'parameter_constraints': [
            {'when': {'mstp_frame_format': 'CLASSIC'}, 'parameter': 'payload_bytes', 'maximum': 480},
            {'when': {'mstp_frame_format': 'CLASSIC'}, 'parameter': 'bacnet_max_apdu_bytes', 'maximum': 480},
            {'when': {'mstp_frame_format': 'CLASSIC'}, 'parameter': 'mstp_npdu_bytes', 'maximum': 501},
            {'when': {}, 'parameter': 'payload_bytes', 'maximum_parameter': 'mstp_npdu_bytes', 'maximum_offset': -2},
            {'when': {}, 'parameter': 'mstp_frame_abort_bit_times', 'maximum_parameter': 'bitrate_bps', 'maximum_factor': 0.1},
            {'when': {}, 'parameter': 'payload_bytes', 'maximum_parameter': 'bacnet_max_apdu_bytes'},
            {'when': {'mstp_node_role': 'MASTER'}, 'parameter': 'mstp_mac_address', 'maximum': 127},
            {'when': {'mstp_node_role': 'MASTER'}, 'parameter': 'mstp_mac_address', 'maximum_parameter': 'mstp_max_master'},
            {'when': {'mstp_max_master_modifiable': False}, 'parameter': 'mstp_max_master', 'allowed': [127]},
            {'when': {'mstp_max_info_frames_modifiable': False}, 'parameter': 'mstp_max_info_frames', 'allowed': [1]},
            {'when_positive': ['bacnet_apdu_retries'], 'parameter': 'bacnet_apdu_timeout_ms', 'minimum': 1},
            {'when_positive': ['bacnet_apdu_retries'], 'parameter': 'bacnet_segment_timeout_ms', 'minimum': 1},
        ],
        'mechanisms': {'arbitration': ['BACNET_MSTP_TOKEN_PASSING', 'MASTER_POLL_FOR_MASTER', 'SLAVE_REPLY_ONLY'],
                       'integrity': ['MSTP_HEADER_CRC8', 'CLASSIC_DATA_CRC16', 'EXTENDED_COBS_CRC32K'],
                       'addressing': ['MSTP_STATION_ADDRESS', 'BACNET_DEVICE_INSTANCE'],
                       'clocking': ['EIA485_NRZ_8N1']},
    },
    'avb': {
        'rate_model': {'type': 'ETHERNET_LINK_RATE', 'fields': ['bitrate_bps'],
                       'allowed_bps': [100_000_000, 1_000_000_000, 10_000_000_000]},
        'parameter_constraints': [
            {'when': {'avb_sr_class': 'A'}, 'parameter': 'avb_measurement_interval_us', 'allowed': [125]},
            {'when': {'avb_sr_class': 'B'}, 'parameter': 'avb_measurement_interval_us', 'allowed': [250]},
            {'when': {}, 'parameter': 'avb_idle_slope_bps', 'maximum_parameter': 'bitrate_bps'},
            {'when': {}, 'parameter': 'avb_send_slope_bps', 'difference_parameters': ['avb_idle_slope_bps', 'bitrate_bps']},
            {'when': {}, 'parameter': 'payload_bytes', 'maximum_parameter': 'avb_max_frame_size_bytes'},
        ],
        'mechanisms': {'arbitration': ['AVB_CREDIT_BASED_SHAPING'], 'addressing': ['MAC_ADDRESS', 'AVB_STREAM_ID', 'VLAN_ID'],
                       'synchronization': ['IEEE_802_1AS_GPTP'], 'flow_control': ['MSRP_STREAM_RESERVATION'],
                       'integrity': ['ETHERNET_FCS']},
    },
    'arinc429': {
        'rate_model': {'type': 'SINGLE_BITRATE', 'fields': ['bitrate_bps'],
                       'minimum_bps': 12_000, 'maximum_bps': 101_000,
                       'allowed_ranges_bps': [[12_000, 14_500], [99_000, 101_000]]},
        'parameter_constraints': [
            {'when': {'arinc429_speed_mode': 'LOW'}, 'parameter': 'bitrate_bps', 'minimum': 12_000, 'maximum': 14_500},
            {'when': {'arinc429_speed_mode': 'HIGH'}, 'parameter': 'bitrate_bps', 'minimum': 99_000, 'maximum': 101_000},
            {'when': {'arinc429_speed_mode': 'LOW'}, 'parameter': 'arinc429_rise_time_us', 'minimum': 5, 'maximum': 15},
            {'when': {'arinc429_speed_mode': 'HIGH'}, 'parameter': 'arinc429_rise_time_us', 'minimum': 1, 'maximum': 2},
            {'when': {'arinc429_speed_mode': 'LOW'}, 'parameter': 'arinc429_fall_time_us', 'minimum': 5, 'maximum': 15},
            {'when': {'arinc429_speed_mode': 'HIGH'}, 'parameter': 'arinc429_fall_time_us', 'minimum': 1, 'maximum': 2},
            {'when_ranges': {'bitrate_bps': [12_000, 14_500]}, 'parameter': 'arinc429_rise_time_us', 'minimum': 5, 'maximum': 15},
            {'when_ranges': {'bitrate_bps': [99_000, 101_000]}, 'parameter': 'arinc429_rise_time_us', 'minimum': 1, 'maximum': 2},
            {'when_ranges': {'bitrate_bps': [12_000, 14_500]}, 'parameter': 'arinc429_fall_time_us', 'minimum': 5, 'maximum': 15},
            {'when_ranges': {'bitrate_bps': [99_000, 101_000]}, 'parameter': 'arinc429_fall_time_us', 'minimum': 1, 'maximum': 2},
            {'when_present': ['arinc429_sdi'], 'parameter': 'arinc429_data_bits', 'maximum': 21},
            {'when_present': ['arinc429_ssm'], 'parameter': 'arinc429_data_bits', 'maximum': 21},
            {'when_present': ['arinc429_sdi', 'arinc429_ssm'], 'parameter': 'arinc429_data_bits', 'maximum': 19},
        ],
        'mechanisms': {'integrity': ['ARINC429_ODD_PARITY'], 'addressing': ['ARINC429_LABEL', 'OPTIONAL_SDI'],
                       'arbitration': ['SINGLE_TRANSMITTER_SIMPLEX'], 'clocking': ['BIPOLAR_RETURN_TO_ZERO']},
    },
    'amqp': {'mechanisms': {'addressing': ['AMQP_CONTAINER_LINK_ENDPOINT'],
                           'reliability': ['AMQP_LINK_SETTLEMENT', 'TCP_ORDERED_BYTE_STREAM'],
                           'flow_control': ['AMQP_LINK_CREDIT', 'AMQP_SESSION_WINDOWS']}},
    'afdx': {
        'rate_model': {'type': 'ETHERNET_LINK_RATE', 'fields': ['bitrate_bps'], 'allowed_bps': [10_000_000, 100_000_000]},
        'parameter_constraints': [{'when': {}, 'parameter': 'payload_bytes',
            'maximum_parameter': 'afdx_lmax_frame_bytes', 'maximum_offset': -47,
            'source': 'https://ww1.microchip.com/downloads/aemdocuments/documents/fpga/ApplicationNotes/ApplicationNotes/afdx_solutions_an.pdf',
            'source_revision': 'Actel AC221 March 2005, figure 3: MAC + IPv4 + UDP + sequence + FCS = 47 bytes'}],
        'mechanisms': {'arbitration': ['AFDX_VL_BAG_SHAPING'], 'integrity': ['ETHERNET_FCS', 'AFDX_SEQUENCE_NUMBER'],
                       'addressing': ['AFDX_VIRTUAL_LINK', 'MAC_ADDRESS', 'IP_ADDRESS', 'UDP_PORT'],
                       'reliability': ['AFDX_DUAL_NETWORK_REDUNDANCY', 'AFDX_DUPLICATE_ELIMINATION']},
    },
    "5g": {
        "rate_model": {"type": "SINGLE_BITRATE", "fields": ["bitrate_bps"], "minimum_bps": 1},
        "parameter_constraints": [
            {"when": {"nr_frequency_range": "FR1", "nr_subcarrier_spacing_khz": "15"},
             "parameter": "nr_channel_bandwidth_mhz", "allowed": [5, 10, 15, 20, 25, 30, 40, 50],
             "source": "https://www.etsi.org/deliver/etsi_ts/138100_138199/13810101/16.13.00_60/ts_13810101v161300p.pdf",
             "source_revision": "TS 38.101-1 v16.13.0, table 5.3.2-1"},
            {"when": {"nr_frequency_range": "FR1", "nr_subcarrier_spacing_khz": "30"},
             "parameter": "nr_channel_bandwidth_mhz", "allowed": [5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100],
             "source": "https://www.etsi.org/deliver/etsi_ts/138100_138199/13810101/16.13.00_60/ts_13810101v161300p.pdf",
             "source_revision": "TS 38.101-1 v16.13.0, table 5.3.2-1"},
            {"when": {"nr_frequency_range": "FR1", "nr_subcarrier_spacing_khz": "60"},
             "parameter": "nr_channel_bandwidth_mhz", "allowed": [10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100],
             "source": "https://www.etsi.org/deliver/etsi_ts/138100_138199/13810101/16.13.00_60/ts_13810101v161300p.pdf",
             "source_revision": "TS 38.101-1 v16.13.0, table 5.3.2-1"},
            {"when": {"nr_frequency_range": "FR2", "nr_subcarrier_spacing_khz": "60"},
             "parameter": "nr_channel_bandwidth_mhz", "allowed": [50, 100, 200],
             "source": "https://www.etsi.org/deliver/etsi_ts/138100_138199/13810102/16.12.00_60/ts_13810102v161200p.pdf",
             "source_revision": "TS 38.101-2 v16.12.0, table 5.3.2-1"},
            {"when": {"nr_frequency_range": "FR2", "nr_subcarrier_spacing_khz": "120"},
             "parameter": "nr_channel_bandwidth_mhz", "allowed": [50, 100, 200, 400],
             "source": "https://www.etsi.org/deliver/etsi_ts/138100_138199/13810102/16.12.00_60/ts_13810102v161200p.pdf",
             "source_revision": "TS 38.101-2 v16.12.0, table 5.3.2-1"},
            {"when": {"nr_frequency_range": "FR1"}, "parameter": "nr_subcarrier_spacing_khz", "allowed": ["15", "30", "60"]},
            {"when": {"nr_frequency_range": "FR2"}, "parameter": "nr_subcarrier_spacing_khz", "allowed": ["60", "120"]},
            {"when": {"nr_direction": "UL"}, "parameter": "nr_mimo_layers", "maximum": 4},
        ],
        "mechanisms": {"arbitration": ["NR_GNB_SCHEDULING", "NR_RANDOM_ACCESS"],
                       "supervision": ["NR_RADIO_LINK_MONITORING"], "reliability": ["NR_HARQ", "NR_RLC_MODE_DEPENDENT_ARQ"],
                       "addressing": ["NR_RNTI"]},
    },
    "lin": {**lin_rules.semantics()},
    "lonworks": {**lonworks_rules.semantics()},
    "lorawan": {**lorawan_rules.semantics()},
    "lte_m": {**lte_m_rules.semantics()},
    "nb_iot": {**nb_iot_rules.semantics()},
    "nfc": {**nfc_rules.semantics()},
    "nmea0183": {**nmea0183_rules.semantics()},
    "lvds": {**lvds_rules.semantics()},
    "m_bus": {**m_bus_rules.semantics()},
    "matter": {**matter_rules.semantics()},
    "mil_std_1553": {**mil1553_rules.semantics()},
    "mipi_csi2": {**csi2_rules.semantics()},
    "mipi_dsi": {**dsi_rules.semantics()},
    "mms": {**mms_rules.semantics()},
    "modbus_ascii": {**ascii_rules.semantics()},
    "can": {
        "rate_model": {"type": "SINGLE_BITRATE", "fields": ["bitrate_bps"], "minimum_bps": 1, "maximum_bps": 1_000_000},
        "mechanisms": {"integrity": ["CAN_CRC"], "addressing": ["CAN_IDENTIFIER"], "supervision": ["ERROR_COUNTER", "BUS_OFF"]},
        'parameter_constraints': [
            {'when': {'can_frame_format': 'BASE_11'}, 'parameter': 'can_identifier', 'maximum': 2047},
            {'when': {'can_frame_type': 'REMOTE'}, 'parameter': 'payload_bytes', 'allowed': [0]},
            {'when': {'can_frame_type': 'DATA'}, 'parameter': 'payload_bytes', 'equal_parameter': 'can_dlc'},
            {'when': {}, 'parameter': 'can_sjw_tq', 'maximum_parameter': 'can_tseg2_tq'},
            {'when': {}, 'parameter': 'can_sjw_tq', 'maximum_parameter': 'can_tseg1_tq'},
            {'when': {}, 'parameter': 'bitrate_bps', 'equal_ratio': {
                'numerator_parameter': 'can_clock_hz', 'denominator_product': ['can_prescaler'],
                'denominator_sum': ['can_tseg1_tq', 'can_tseg2_tq'], 'denominator_offset': 1}},
            {'when': {}, 'parameter': 'sample_point_percent', 'equal_ratio': {
                'numerator_sum': ['can_tseg1_tq'], 'numerator_offset': 1, 'factor': 100,
                'denominator_sum': ['can_tseg1_tq', 'can_tseg2_tq'], 'denominator_offset': 1}},
            {'when': {'can_controller_profile': 'M_CAN_3_3_1'}, 'parameter': 'can_prescaler', 'maximum': 512},
            {'when': {'can_controller_profile': 'M_CAN_3_3_1'}, 'parameter': 'can_tseg1_tq', 'minimum': 2, 'maximum': 256},
            {'when': {'can_controller_profile': 'M_CAN_3_3_1'}, 'parameter': 'can_tseg2_tq', 'minimum': 2, 'maximum': 128},
            {'when': {'can_controller_profile': 'M_CAN_3_3_1'}, 'parameter': 'can_sjw_tq', 'maximum': 128},
            {'when': {'can_error_state': 'ERROR_ACTIVE'}, 'parameter': 'can_tx_error_count', 'maximum': 127},
            {'when': {'can_error_state': 'ERROR_ACTIVE'}, 'parameter': 'can_rx_error_count', 'maximum': 127},
            {'when': {'can_error_state': 'ERROR_PASSIVE'}, 'parameter': 'can_tx_error_count', 'maximum': 255},
            {'when': {'can_error_state': 'BUS_OFF'}, 'parameter': 'can_tx_error_count', 'minimum': 256},
            {'when': {}, 'when_ranges': {'can_tx_error_count': [0, 127], 'can_rx_error_count': [0, 127]},
             'parameter': 'can_error_state', 'allowed': ['ERROR_ACTIVE']},
        ],
    },
    "can_fd": {
        "rate_model": {"type": "MULTI_PHASE_BITRATE", "fields": ["nominal_bitrate_bps", "data_bitrate_bps"], "minimum_bps":1,
                       "nominal_maximum_bps": 1_000_000, 'optional_fields_when':{'data_bitrate_bps':{'can_fd_brs':False}}},
        "mechanisms": {"integrity": ["CAN_FD_CRC"], "addressing": ["CAN_IDENTIFIER"], "supervision": ["ERROR_COUNTER", "ERROR_ACTIVE", "ERROR_PASSIVE", "BUS_OFF"]},
        'parameter_constraints': [
            {'when':{},'parameter':'payload_bytes','maximum_parameter':'can_fd_wire_data_bytes'},
            {'when':{},'parameter':'data_bitrate_bps','maximum_parameter':'can_fd_transceiver_max_bps'},
            {'when':{'can_error_state':'ERROR_ACTIVE'},'parameter':'can_fd_error_passive','allowed':[False]},
            {'when':{'can_error_state':'ERROR_PASSIVE'},'parameter':'can_fd_error_passive','allowed':[True]},
            {'when':{},'when_ranges':{'can_fd_wire_data_bytes':[0,16]},'parameter':'can_fd_crc_bits','allowed':[17]},
            {'when':{},'when_ranges':{'can_fd_wire_data_bytes':[20,64]},'parameter':'can_fd_crc_bits','allowed':[21]},
            {'when':{},'parameter':'data_bitrate_bps','equal_ratio':{'numerator_parameter':'can_clock_hz',
                'denominator_product':['can_fd_data_prescaler'],'denominator_sum':['can_fd_data_tseg1_tq','can_fd_data_tseg2_tq'],'denominator_offset':1}},
            {'when':{},'parameter':'can_fd_data_sample_point_percent','equal_ratio':{
                'numerator_sum':['can_fd_data_tseg1_tq'],'numerator_offset':1,'factor':100,
                'denominator_sum':['can_fd_data_tseg1_tq','can_fd_data_tseg2_tq'],'denominator_offset':1}},
            {'when':{},'parameter':'can_fd_data_sjw_tq','maximum_parameter':'can_fd_data_tseg1_tq'},
            {'when':{},'parameter':'can_fd_data_sjw_tq','maximum_parameter':'can_fd_data_tseg2_tq'},
            {'when':{'can_controller_profile':'M_CAN_3_3_1'},'parameter':'can_fd_data_prescaler','maximum':32},
            {'when':{'can_controller_profile':'M_CAN_3_3_1','can_fd_tdc_enabled':True},'parameter':'can_fd_data_prescaler','maximum':2},
            {'when':{'can_controller_profile':'M_CAN_3_3_1'},'parameter':'can_fd_data_tseg1_tq','maximum':32},
            {'when':{'can_controller_profile':'M_CAN_3_3_1'},'parameter':'can_fd_data_tseg2_tq','minimum':2,'maximum':16},
            {'when':{'can_controller_profile':'M_CAN_3_3_1'},'parameter':'can_fd_data_sjw_tq','maximum':16},
            {'when':{'can_controller_profile':'M_CAN_3_3_1'},'parameter':'data_bitrate_bps','minimum_parameter':'nominal_bitrate_bps'},
            {'when':{'can_controller_profile':'M_CAN_3_3_1'},'parameter':'can_fd_mcan_ssp_mtq',
             'equal_sum':[{'parameter':'can_fd_mcan_delay_mtq'},{'parameter':'can_fd_mcan_tdco_mtq'}]},
            {'when':{'can_controller_profile':'M_CAN_3_3_1','can_fd_tdc_enabled':True},'parameter':'can_fd_mcan_ssp_mtq',
             'maximum_ratio':{'numerator_sum':['can_fd_data_tseg1_tq','can_fd_data_tseg2_tq'],'numerator_offset':1,
                              'numerator_product':['can_fd_data_prescaler'],'factor':6,'denominator_offset':1},'exclusive_maximum_ratio':True},
        ],
    },
    "ethernet": {
        'native_parameter_prefixes':['eth_'],
        "rate_model": {"type": "ETHERNET_LINK_RATE", "fields": ["bitrate_bps"],
                       "allowed_bps": [10_000_000, 100_000_000, 1_000_000_000, 2_500_000_000, 5_000_000_000, 10_000_000_000]},
        "mechanisms": {"integrity": ["ETHERNET_FCS"], "addressing": ["MAC_ADDRESS"],
                       "arbitration": ["EXPLICIT_FULL_DUPLEX_OR_CSMA_CD_NOT_CAN"],
                       "upper_layer_resolution": ["ARP_IF_IPV4", "NDP_IF_IPV6"]},
        "parameter_constraints": [
            *[{'when': {'eth_phy':phy},'parameter':'bitrate_bps','allowed':[rate]}
              for phy,rate in (('10BASE_T',10000000),('100BASE_TX',100000000),('1000BASE_T',1000000000),
                               ('2_5GBASE_T',2500000000),('5GBASE_T',5000000000),('10GBASE_T',10000000000),
                               ('10BASE_T1S',10000000),('100BASE_T1',100000000),('1000BASE_T1',1000000000))],
            *[{'when':{'eth_phy':phy},'parameter':'duplex','allowed':['FULL']}
              for phy in ('2_5GBASE_T','5GBASE_T','10GBASE_T','100BASE_T1','1000BASE_T1')],
            {'when':{'eth_phy':'10BASE_T1S'},'parameter':'duplex','allowed':['HALF']},
            *[{'when':{'eth_phy':phy},'parameter':'eth_plca_enabled','allowed':[]}
              for phy in ('10BASE_T','100BASE_TX','1000BASE_T','2_5GBASE_T','5GBASE_T','10GBASE_T','100BASE_T1','1000BASE_T1')],
            *[{'when':{'eth_plca_enabled':False},'parameter':key,'allowed':[]}
              for key in ('eth_plca_active','eth_plca_id','eth_plca_count','eth_plca_to_bits','eth_plca_burst_count','eth_plca_burst_bits')],
            {'when':{'eth_plca_id':255},'parameter':'eth_plca_active','allowed':[False]},
            {'when':{'eth_plca_active':True},'parameter':'eth_plca_id','maximum':254},
            {'when': {'eth_frame_profile':'BASIC_MAC'},'parameter':'mtu_bytes','maximum':1500},
            {'when':{},'parameter':'payload_bytes','maximum_parameter':'mtu_bytes'},
            {'when':{'eth_frame_profile':'BASIC_MAC'},'parameter':'payload_bytes','maximum':1500},
            {'when':{},'parameter':'eth_client_bytes','maximum_parameter':'mtu_bytes'},
            {'when':{'eth_frame_profile':'BASIC_MAC'},'parameter':'eth_client_bytes','maximum':1500},
            {'when':{'eth_frame_profile':'BASIC_MAC'},'parameter':'eth_mac_frame_bytes','maximum_expression':{'sum':[1518,{'product':[4,'eth_vlan_tags']}]}},
            {'when':{'eth_payload_layer':'MAC_CLIENT'},'parameter':'eth_upper_header_bytes','allowed':[0]},
            {'when':{},'parameter':'eth_client_bytes','equal_sum':[
                {'parameter':'payload_bytes'},{'parameter':'eth_upper_header_bytes'}]},
            {'when':{},'parameter':'eth_pad_bytes','equal_expression':{'maximum':[
                0,{'subtract':[46,{'sum':['eth_client_bytes',{'product':[4,'eth_vlan_tags']}]}]}]}},
            {'when':{},'parameter':'eth_mac_frame_bytes','equal_expression':{'sum':[
                18,'eth_client_bytes','eth_pad_bytes',{'product':[4,'eth_vlan_tags']}]}},
            {'when':{},'parameter':'eth_wire_slot_bytes','equal_expression':{'sum':[
                'eth_mac_frame_bytes',8,{'product':['eth_ifg_bits',0.125]}]}},
            *[{'when':{'eth_tag_mode':mode},'parameter':'eth_vlan_tags','allowed':[tags]}
              for mode,tags in (('UNTAGGED',0),('PRIORITY',1),('VLAN',1),('STACKED_DEVICE',2))],
            {'when':{'eth_tag_mode':'UNTAGGED'},'parameter':'vlan_id','allowed':[]},
            {'when':{'eth_tag_mode':'UNTAGGED'},'parameter':'qos_priority','allowed':[]},
            {'when':{'eth_tag_mode':'UNTAGGED'},'parameter':'eth_dei','allowed':[]},
            {'when':{'eth_tag_mode':'PRIORITY'},'parameter':'vlan_id','allowed':[0]},
            {'when':{'eth_tag_mode':'VLAN'},'parameter':'vlan_id','minimum':1},
            {'when':{'eth_tag_mode':'STACKED_DEVICE'},'parameter':'vlan_id','minimum':1},
            {'when':{'eth_frame_format':'ETHERTYPE'},'parameter':'eth_type_length','minimum':1536},
            {'when':{'eth_frame_format':'LENGTH_LLC'},'parameter':'eth_type_length','maximum':1500},
            {'when':{'eth_frame_format':'LENGTH_LLC'},'parameter':'eth_type_length','equal_parameter':'eth_client_bytes'},
            {'when':{'duplex':'FULL'},'parameter':'eth_backpressure','allowed':[False]},
            *[{'when':{'duplex':'HALF'},'parameter':key,'allowed':[False]}
              for key in ('eth_pause_rx','eth_pause_tx','eth_eee_enabled')],
            *[{'when':{'duplex':'FULL'},'parameter':key,'allowed':[]}
              for key in ('eth_collision_slot_bits','eth_attempt_limit','eth_backoff_limit')],
            *[{'when':{'duplex':'HALF','bitrate_bps':rate},'parameter':'eth_collision_slot_bits','allowed':[slot]}
              for rate,slot in ((10000000,512),(100000000,512),(1000000000,4096))],
            {'when':{},'parameter':'eth_pause_time_us','equal_expression':{'product':[
                'eth_pause_quanta',512,1000000,{'power':['bitrate_bps',-1]}]}},
            {'when':{'eth_pause_rx':False,'eth_pause_tx':False},'parameter':'eth_pause_quanta','allowed':[]},
            {'when':{'eth_pause_rx':False,'eth_pause_tx':False},'parameter':'eth_pause_time_us','allowed':[]},
            *[{'when':{'eth_eee_enabled':False},'parameter':key,'allowed':[]}
              for key in ('eth_eee_wake_us','eth_eee_sleep_us')],
            {'when':{},'parameter':'eth_peer_rate_bps','equal_parameter':'bitrate_bps'},
            {'when':{},'parameter':'eth_peer_duplex','equal_parameter':'duplex'},
            {'when':{},'parameter':'rate_limit_bit_s','maximum_parameter':'bitrate_bps'},
        ],
    },
    "ethercat": {
        "rate_model": {"type": "FIXED_LINK_RATE", "fields": ["bitrate_bps"], "fixed_bps": 100_000_000},
        "required_parameters": ['bitrate_bps','ecat_transport','ecat_phy','ecat_esi_source','ecat_topology_source'],
        "mechanisms": {"integrity": ["ETHERNET_FCS", "WORKING_COUNTER"], "addressing": ["AUTO_INCREMENT_ADDRESS", "CONFIGURED_STATION_ADDRESS"], "diagnostics": ["AL_STATUS", "COE"], "supervision": ["WORKING_COUNTER"]},
        'parameter_constraints': [
            {'when': {},'parameter':'duplex','allowed':['FULL']},
            {'when': {},'parameter':'ecat_frame_type','allowed':[1]},
            {'when': {},'parameter':'ecat_header_reserved','allowed':[0]},
            {'when': {},'parameter':'ecat_datagram_reserved','allowed':[0]},
            {'when': {},'parameter':'ecat_datagram_length','equal_parameter':'payload_bytes'},
            {'when': {},'parameter':'ecat_datagram_bytes','equal_expression':{'sum':['ecat_sum_data_bytes',{'product':[12,'ecat_datagram_count']}]}},
            {'when': {},'parameter':'ecat_header_length','equal_parameter':'ecat_datagram_bytes'},
            *[{'when': {'ecat_transport':transport,'ecat_vlan_tags':tags},
               'when_half_open_ranges':{'ecat_datagram_bytes':[12,44-extra-4*tags]},'parameter':'ecat_padding_bytes',
               'equal_expression':{'subtract':[44-extra-4*tags,'ecat_datagram_bytes']}}
              for transport,extra in (('NATIVE_ETHERNET',0),('UDP_IPV4',28)) for tags in (0,1)],
            *[{'when': {'ecat_transport':transport,'ecat_vlan_tags':tags},
               'when_half_open_ranges':{'ecat_datagram_bytes':[44-extra-4*tags,None]},'parameter':'ecat_padding_bytes','allowed':[0]}
              for transport,extra in (('NATIVE_ETHERNET',0),('UDP_IPV4',28)) for tags in (0,1)],
            {'when': {},'parameter':'ecat_datagram_count','maximum_parameter':'ecat_device_datagram_limit'},
            {'when': {},'parameter':'ecat_sum_data_bytes','minimum_parameter':'payload_bytes'},
            {'when': {'ecat_datagram_count':1},'parameter':'ecat_sum_data_bytes','equal_parameter':'payload_bytes'},
            {'when': {'ecat_transport':'NATIVE_ETHERNET'},'parameter':'ecat_datagram_bytes','maximum':1498},
            {'when': {'ecat_transport':'UDP_IPV4'},'parameter':'ecat_datagram_bytes','maximum':1470},
            {'when': {'ecat_transport':'UDP_IPV4'},'parameter':'payload_bytes','maximum':1458},
            {'when': {'ecat_transport':'UDP_IPV4'},'parameter':'ecat_udp_port','allowed':[34980]},
            {'when': {'ecat_transport':'UDP_IPV4'},'parameter':'ecat_ipv4_header_bytes','allowed':[20]},
            {'when': {'ecat_transport':'NATIVE_ETHERNET'},'parameter':'ecat_udp_port','allowed':[]},
            {'when': {'ecat_transport':'NATIVE_ETHERNET'},'parameter':'ecat_ipv4_header_bytes','allowed':[]},
            *[{'when': {'ecat_transport':transport},'parameter':'ecat_mac_frame_bytes',
               'equal_expression':{'sum':[20+extra,'ecat_datagram_bytes','ecat_padding_bytes',{'product':[4,'ecat_vlan_tags']}]},
               'maximum_expression':{'sum':[1518,{'product':[4,'ecat_vlan_tags']}]}}
              for transport,extra in (('NATIVE_ETHERNET',0),('UDP_IPV4',28))],
            {'when': {},'parameter':'ecat_wire_slot_bytes','equal_expression':{'sum':['ecat_mac_frame_bytes',20]}},
            {'when': {'ecat_phy':'EBUS'},'parameter':'ecat_wire_slot_bytes','allowed':[]},
            {'when': {'ecat_response_accepted':True},'parameter':'ecat_received_wkc','equal_parameter':'ecat_expected_wkc'},
            {'when': {},'parameter':'ecat_mailbox_data_bytes','maximum_parameter':'ecat_mailbox_bytes','maximum_offset':-6},
            *[{'when': {'ecat_link_detection':'STANDARD','ecat_phy':phy},'parameter':'ecat_link_loss_bound_us','exclusive_maximum':15}
              for phy in ('100BASE_TX','100BASE_FX','ETHERCAT_P')],
            {'when': {'ecat_datagram_count':1},'parameter':'ecat_more','allowed':[False]},
            {'when': {'ecat_sync_mode':'FREE_RUN'},'parameter':'distributed_clock_cycle_ms','allowed':[]},
            {'when': {'ecat_sync_mode':'SM_EVENT'},'parameter':'distributed_clock_cycle_ms','allowed':[]},
            *[{'when': {'ecat_dc_supported':False},'parameter':key,'allowed':[]} for key in
              ('distributed_clock_cycle_ms','ecat_dc_reference','ecat_dc_width','ecat_sync0_cycle_ns','ecat_sync1_delay_ns','ecat_sync_pulse_ns')],
            {'when': {'ecat_sync_mode':'DC'},'parameter':'ecat_dc_supported','allowed':[True]},
            {'when': {'ecat_sync_generation':'SINGLE_SHOT'},'parameter':'ecat_sync0_cycle_ns','allowed':[0]},
            {'when': {'ecat_sync_generation':'SINGLE_SHOT'},'parameter':'ecat_sync_pulse_ns','minimum':1},
            {'when': {'ecat_sync_generation':'CYCLIC_PULSE'},'parameter':'ecat_sync0_cycle_ns','minimum':1},
            {'when': {'ecat_sync_generation':'CYCLIC_PULSE'},'parameter':'ecat_sync_pulse_ns','minimum':1},
            *[{'when': {'ecat_sync_generation':mode},'parameter':'ecat_sync_pulse_ns','allowed':[0]}
              for mode in ('CYCLIC_ACK','SINGLE_SHOT_ACK')],
            {'when': {'ecat_sync_generation':'SINGLE_SHOT_ACK'},'parameter':'ecat_sync0_cycle_ns','allowed':[0]},
            {'when': {'ecat_sync_generation':'CYCLIC_ACK'},'parameter':'ecat_sync0_cycle_ns','minimum':1},
            {'when': {},'parameter':'ecat_sync_pulse_ns','equal_expression':{'product':['ecat_sync_pulse_register',10]}},
            {'when': {'ecat_sync_mode':'DC'},'parameter':'distributed_clock_cycle_ms',
             'equal_expression':{'product':['ecat_sync0_cycle_ns',0.000001]}},
            {'when': {},'when_positive':['ecat_pd_watchdog_ticks'],'parameter':'ecat_pd_watchdog_min_ns',
             'equal_expression':{'product':[{'sum':['ecat_watchdog_divider',2]},40,'ecat_pd_watchdog_ticks']}},
            {'when': {},'when_positive':['ecat_pd_watchdog_ticks'],'parameter':'ecat_pd_watchdog_max_ns',
             'equal_expression':{'product':[{'sum':['ecat_watchdog_divider',2]},40,{'sum':['ecat_pd_watchdog_ticks',1]}]}},
            *[{'when': {'ecat_pd_watchdog_ticks':0},'parameter':key,'allowed':[]}
              for key in ('ecat_pd_watchdog_min_ns','ecat_pd_watchdog_max_ns')],
            *[{'when': {'ecat_state':state},'parameter':'ecat_outputs_active','allowed':[False]}
              for state in ('INIT','PREOP','SAFEOP','BOOTSTRAP')],
            *[{'when': {'ecat_command':cmd},'parameter':'ecat_addressing','allowed':[mode]}
              for commands,mode in ((('APRD','APWR','APRW','ARMW'),'AUTO_INCREMENT'),
                                    (('FPRD','FPWR','FPRW','FRMW'),'CONFIGURED'),
                                    (('BRD','BWR','BRW'),'BROADCAST'),(('LRD','LWR','LRW'),'LOGICAL')) for cmd in commands],
            *[{'when': {'ecat_addressing':'LOGICAL'},'parameter':key,'allowed':[]} for key in ('ecat_station_address','ecat_register_offset')],
            *[{'when': {'ecat_addressing':mode},'parameter':'ecat_logical_address','allowed':[]}
              for mode in ('AUTO_INCREMENT','CONFIGURED','BROADCAST')],
        ],
    },
    "profinet": {**profinet_rules.semantics()},
    "profisafe": {**profisafe_rules.semantics()},
    "pwm": {**pwm_rules.semantics()},
    "rfid": {**rfid_rules.semantics()},
    "ros2": {**ros2_rules.semantics()},
    "rs232": {**rs232_rules.semantics()},
    "rs422": {**rs422_rules.semantics()},
    "rs485": {**rs485_rules.semantics()},
    "sampled_values": {**sampled_values_rules.semantics()},
    "sercos_iii": {**sercos_iii_rules.semantics()},
    "someip": {**someip_rules.semantics()},
    "someip_sd": {**someip_sd_rules.semantics()},
    "spacewire": {**spacewire_rules.semantics()},
    "sparkplug_b": {**sparkplug_b_rules.semantics()},
    "modbus_rtu": {**rtu_rules.semantics()},
    "modbus_tcp": {**mtcp_rules.semantics()},
    "most": {**most_rules.semantics()},
    "mqtt": {**mqtt_rules.semantics()},
    "mqtt_sn": {**mqtt_sn_rules.semantics()},
    "mvb": {**mvb_rules.semantics()},
    "i2c": {
        **i2c_rules.semantics(),
    },
    'i3c': {**i3c_rules.semantics()},
    'iec60870_5_101': {**iec101_rules.semantics()},
    'iec60870_5_104': {**iec104_rules.semantics()},
    'iec61162': {**iec61162_rules.semantics()},
    'iec61850': {**iec61850_rules.semantics()},
    'interbus': {**interbus_rules.semantics()},
    'io_link': {**io_link_rules.semantics()},
    'io_link_wireless': {**io_link_wireless_rules.semantics()},
    'ip': {**ip_rules.semantics()},
    'isobus': {**isobus_rules.semantics()},
    "spi": {**spi_rules.semantics()},
    "sunspec_modbus": {**sunspec_rules.semantics()},
    "tcp": {**tcp_rules.semantics()},
    "thread": {**thread_rules.semantics()},
    "trdp": {**trdp_rules.semantics()},
    "tsn": {**tsn_rules.semantics()},
    "tte": {**tte_rules.semantics()},
    "uart": {**uart_rules.semantics()},
    "udp": {**udp_rules.semantics()},
    "uds": {**uds_rules.semantics()},
    "usb": {**usb_rules.semantics()},
    "uwb": {**uwb_rules.semantics()},
    "websocket": {**websocket_rules.semantics()},
    "wifi": {**wifi_rules.semantics()},
    "wireless_m_bus": {**wireless_m_bus_rules.semantics()},
    "wirelesshart": {**wirelesshart_rules.semantics()},
    "wtb": {**wtb_rules.semantics()},
    "xcp": {**xcp_rules.semantics()},
    "zigbee": {**zigbee_rules.semantics()},
    'j1939': {**j1939_rules.semantics()},
    'knx_ip': {**knx_ip_rules.semantics()},
    'knx_rf': {**knx_rf_rules.semantics()},
    'knx_tp': {**knx_tp_rules.semantics()},
    'canopen': {
        'rate_model':{'type':'SINGLE_BITRATE','fields':['bitrate_bps'],
                      'allowed_bps':[10000,20000,50000,125000,250000,500000,800000,1000000],'inherited_from':'can'},
        'mechanisms':{'integrity':['CAN_CRC'],'addressing':['CANOPEN_NODE_ID','CAN_COB_ID','OBJECT_DICTIONARY_INDEX_SUBINDEX'],
                      'diagnostics':['CANOPEN_EMCY','CANOPEN_SDO'],'supervision':['HEARTBEAT','NMT'],
                      'synchronization':['CANOPEN_SYNC'],'flow_control':['PDO_TRANSMISSION_TYPE','PDO_INHIBIT_TIMER','SDO_SEGMENT_BLOCK_ACK']},
        'parameter_constraints':[
            {'when':{'co_service':'NMT'},'parameter':'payload_bytes','allowed':[2]},
            {'when':{'co_service':'HEARTBEAT'},'parameter':'payload_bytes','allowed':[1]},
            {'when':{'co_service':'BOOTUP'},'parameter':'payload_bytes','allowed':[1]},
            {'when':{'co_service':'EMCY'},'parameter':'payload_bytes','allowed':[8]},
            {'when':{'co_service':'TIME'},'parameter':'payload_bytes','allowed':[6]},
            {'when':{'co_service':'SDO'},'parameter':'payload_bytes','allowed':[8]},
            {'when':{'co_service':'SYNC','co_sync_counter_overflow':0},'parameter':'payload_bytes','allowed':[0]},
            {'when':{'co_service':'SYNC'},'when_positive':['co_sync_counter_overflow'],'parameter':'payload_bytes','allowed':[1]},
            {'when':{'co_service':'PDO'},'parameter':'co_pdo_mapped_bits','maximum_parameter':'payload_bytes','maximum_factor':8},
            {'when':{'co_rtr_allowed':False},'parameter':'co_pdo_transmission_type','allowed':[*range(241),254,255]},
            {'when':{'co_sdo_variant':'EXPEDITED'},'parameter':'co_sdo_application_bytes','maximum':4},
            {'when':{'co_sync_frame_format':'BASE_11'},'parameter':'co_sync_can_id','maximum':2047},
            {'when':{},'when_positive':['co_sync_period_us'],'parameter':'co_sync_window_us','maximum_parameter':'co_sync_period_us'},
            {'when':{},'when_positive':['co_sync_counter_overflow'],'parameter':'co_pdo_sync_start','maximum_parameter':'co_sync_counter_overflow'},
            {'when':{'co_sync_counter_overflow':0},'parameter':'co_pdo_sync_start','allowed':[0]},
        ],
    },
    "dds": {
        'rate_model': {'type': 'INHERITED_OR_NOT_APPLICABLE', 'fields': []},
        'mechanisms': {'discovery': ['DDS_PARTICIPANT_DISCOVERY', 'DDS_ENDPOINT_DISCOVERY', 'EXPLICIT_DDS_IMPLEMENTATION_AND_WIRE_PROFILE'],
                       'supervision': ['LIVELINESS', 'DEADLINE'],
                       'transport': ['EXPLICIT_LOWER_TRANSPORT_BINDING'],
                       'qos': ['ENTITY_SPECIFIC_REQUESTED_OFFERED_POLICIES']},
        'parameter_constraints': [
            *[{'when': {'dds_entity': entity}, 'parameter': key, 'allowed': [],
               'source': 'https://www.omg.org/spec/DDS/20140501/dds_dcps.idl',
               'source_revision': 'OMG DDS1.4 normative IDL QoS structure members'}
              for key, allowed in DDS_POLICY_ENTITIES.items() for entity in DDS_ALL_ENTITIES if entity not in allowed],
            *[{'when': {mode: 'INFINITE'}, 'parameter': value, 'allowed': []}
              for mode, value in (('dds_lifespan_kind', 'lifespan_ms'), ('dds_deadline_kind', 'dds_deadline_ms'),
                                  ('dds_lease_kind', 'dds_lease_ms'), ('dds_nowriter_purge_kind', 'dds_nowriter_purge_ms'),
                                  ('dds_disposed_purge_kind', 'dds_disposed_purge_ms'),
                                  ('dds_service_cleanup_kind', 'dds_service_cleanup_ms'))],
            *[{'when': {}, 'when_half_open_ranges': {prefix + 'max_samples': [1, None]},
               'parameter': prefix + 'max_samples_per_instance', 'minimum': 1,
               'maximum_parameter': prefix + 'max_samples'} for prefix in ('dds_', 'dds_service_')],
            *[{'when': {kind: 'KEEP_LAST'}, 'when_half_open_ranges': {limit: [1, None]},
               'parameter': depth, 'maximum_parameter': limit}
              for kind, depth, limit in (('history_kind', 'history_depth', 'dds_max_samples_per_instance'),
                                         ('dds_service_history_kind', 'dds_service_history_depth', 'dds_service_max_samples_per_instance'))],
            {'when': {'dds_entity': 'DATAREADER', 'dds_deadline_kind': 'FINITE'},
             'parameter': 'dds_time_based_filter_ms', 'maximum_parameter': 'dds_deadline_ms'},
        ],
    },
    'bacnet_ip': {
        'parameter_constraints': [
            {'when': {}, 'parameter': 'payload_bytes', 'maximum_parameter': 'bacnet_max_apdu_bytes',
             'source': 'https://github.com/bacnet-stack/bacnet-stack/blob/master/src/bacnet/config.h',
             'source_revision': 'BACnet-stack MAX_APDU and actual peer capability, accessed 2026-10-01'},
            {'when_positive': ['bacnet_apdu_retries'], 'parameter': 'bacnet_apdu_timeout_ms', 'minimum': 1,
             'source': 'https://documentation.iconics.com/v10.98/Content/Apps/WBDT/BACnet/BACnet_Configuration_Via_Workbench.htm',
             'source_revision': 'ICONICS v10.98, APDU_Timeout'},
            {'when_positive': ['bacnet_apdu_retries'], 'parameter': 'bacnet_segment_timeout_ms', 'minimum': 1,
             'source': 'https://documentation.iconics.com/v10.98/Content/Apps/WBDT/BACnet/BACnet_Configuration_Via_Workbench.htm',
             'source_revision': 'ICONICS v10.98, APDU_Segment_Timeout'},
        ],
        'mechanisms': {'discovery': ['BACNET_WHO_IS_I_AM', 'BACNET_WHO_HAS_I_HAVE'],
                       'addressing': ['BACNET_DEVICE_INSTANCE', 'IPV4_ADDRESS', 'UDP_PORT'],
                       'reliability': ['BACNET_CONFIRMED_SERVICE_RETRY', 'BACNET_APDU_SEGMENTATION'],
                       'broadcast': ['BVLC_LOCAL_BROADCAST', 'BBMD_FORWARDING', 'FOREIGN_DEVICE_REGISTRATION']},
    },
    "nmea2000": {**nmea2000_rules.semantics()},
    "obd2": {**obd2_rules.semantics()},
    "ocpp": {**ocpp_rules.semantics()},
    "one_wire": {**one_wire_rules.semantics()},
    "opc_ua": {**opc_ua_rules.semantics()},
    "opc_ua_pubsub": {**opc_ua_pubsub_rules.semantics()},
    "opensafety": {**opensafety_rules.semantics()},
    "pcie": {**pcie_rules.semantics()},
    "powerlink": {**powerlink_rules.semantics()},
    "profibus_dp": {**profibus_dp_rules.semantics()},
    "profibus_pa": {**profibus_pa_rules.semantics()},
}

for _coap_constraint in TECHNOLOGY_SEMANTICS['coap']['parameter_constraints']:
    _coap_constraint.setdefault('source','https://www.rfc-editor.org/rfc/rfc7252.html')
    _coap_constraint.setdefault('source_revision','RFC7252 /7959 /8323 /7641 /8974 transport-specific normative definitions accessed2026-10-01')

# Vol 6 Part B 4.5.10: max-octets and max-time need not equal one packet
# duration. Apply controller feature bounds only when actual features are known.
for _ble_phy_parameter in ('ble_tx_phy', 'ble_rx_phy'):
    for _ble_feature, _ble_allowed_phys in (
        ('ble_remote_2m_supported', ['LE_1M', 'LE_CODED_S2', 'LE_CODED_S8']),
        ('ble_remote_coded_supported', ['LE_1M', 'LE_2M']),
    ):
        TECHNOLOGY_SEMANTICS['bluetooth_le']['parameter_constraints'].append(
            {'when': {_ble_feature: False}, 'parameter': _ble_phy_parameter, 'allowed': _ble_allowed_phys})
for _ble_time in ('ble_local_max_tx_time_us','ble_local_max_rx_time_us',
                  'ble_supported_max_tx_time_us','ble_supported_max_rx_time_us'):
    for _ble_features, _ble_maximum in (
        ({'ble_coded_supported':False,'ble_dle_supported':False,'ble_cte_supported':False},328),
        ({'ble_coded_supported':False,'ble_dle_supported':False,'ble_cte_supported':True},336),
        ({'ble_coded_supported':False,'ble_dle_supported':True,'ble_cte_supported':False},2120),
        ({'ble_coded_supported':False,'ble_dle_supported':True,'ble_cte_supported':True},2128),
        ({'ble_coded_supported':True,'ble_dle_supported':False},2704),
    ):
        TECHNOLOGY_SEMANTICS['bluetooth_le']['parameter_constraints'].append(
            {'when': _ble_features, 'parameter': _ble_time, 'maximum': _ble_maximum})

CAN_FD_DATA_LENGTHS = (*range(9),12,16,20,24,32,48,64)
for _fd_dlc, _fd_length in enumerate(CAN_FD_DATA_LENGTHS):
    TECHNOLOGY_SEMANTICS['can_fd']['parameter_constraints'].append(
        {'when':{'can_fd_dlc':_fd_dlc},'parameter':'can_fd_wire_data_bytes','allowed':[_fd_length]})

CANOPEN_CC_RATES = (10000,20000,50000,125000,250000,500000,800000,1000000)
for _ccie_variant,_ccie_bits,_ccie_words in (('FIELD',16384,8192),('FIELD_BASIC',4096,2048)):
    for _ccie_key,_ccie_limit in (('ccie_network_rx_bits',_ccie_bits),('ccie_network_ry_bits',_ccie_bits),
                                 ('ccie_network_rwr_words',_ccie_words),('ccie_network_rww_words',_ccie_words)):
        TECHNOLOGY_SEMANTICS['cc_link_ie']['parameter_constraints'].append(
            {'when':{'ccie_variant':_ccie_variant},'parameter':_ccie_key,'maximum':_ccie_limit})
for _ccie_variant in ('FIELD','FIELD_BASIC','CONTROLLER'):
    for _ccie_key in ('ccie_tsn_class','ccie_tsn_version','ccie_tsn_sync','ccie_tsn_cycle_us','ccie_tsn_gate_period_us','ccie_tsn_guard_us'):
        TECHNOLOGY_SEMANTICS['cc_link_ie']['parameter_constraints'].append(
            {'when':{'ccie_variant':_ccie_variant},'parameter':_ccie_key,'allowed':[]})
for _ccie_variant in ('FIELD','CONTROLLER','TSN'):
    for _ccie_key in ('ccie_basic_cyclic_udp_port','ccie_basic_discovery_udp_port','ccie_basic_group','ccie_basic_timeout_ms',
                      'ccie_basic_disconnect_count','ccie_basic_optional_1g_supported','ccie_basic_controller','ccie_basic_tool_revision','ccie_occupied_stations'):
        TECHNOLOGY_SEMANTICS['cc_link_ie']['parameter_constraints'].append(
            {'when':{'ccie_variant':_ccie_variant},'parameter':_ccie_key,'allowed':[]})
for _ccie_variant in ('FIELD','FIELD_BASIC','TSN'):
    for _ccie_key in ('ccie_controller_mode','ccie_controller_network_extended','ccie_controller_networks','ccie_controller_groups',
                      'ccie_controller_lb_bits','ccie_controller_lw_words','ccie_controller_lx_bits','ccie_controller_ly_bits',
                      'ccie_controller_network_lb_bits','ccie_controller_network_lw_words'):
        TECHNOLOGY_SEMANTICS['cc_link_ie']['parameter_constraints'].append(
            {'when':{'ccie_variant':_ccie_variant},'parameter':_ccie_key,'allowed':[]})
for _ccie_controller in ('MELSEC_IQ_R','MELSEC_IQ_L','MELSEC_IQ_F','MELSEC_Q','MELSEC_L'):
    TECHNOLOGY_SEMANTICS['cc_link_ie']['parameter_constraints'].append(
        {'when':{'ccie_basic_controller':_ccie_controller},'parameter':'ccie_basic_disconnect_count','allowed':[3,5,10]})
for _ccl_vendor_key in ('ccl_q_mode','ccl_q_retry_count','ccl_q_reconnection_count','ccl_q_scan_mode','ccl_q_plc_down',
                        'ccl_q_fault_input','ccl_q_cpu_stop_output','ccl_q_block_assurance',
                        'ccl_q_transient_send_words','ccl_q_transient_receive_words','ccl_q_transient_auto_words'):
    TECHNOLOGY_SEMANTICS['cc_link']['parameter_constraints'].append(
        {'when':{'ccl_controller_profile':'DEVICE_SPECIFIC'},'parameter':_ccl_vendor_key,'allowed':[]})
for _ccl_role in ('LOCAL','INTELLIGENT_DEVICE','REMOTE_IO','REMOTE_DEVICE','STANDBY_MANAGER'):
    TECHNOLOGY_SEMANTICS['cc_link']['parameter_constraints'].append(
        {'when':{'ccl_station_role':_ccl_role},'parameter':'ccl_station_number','minimum':1})
for _ccl_rate,_ccl_maximum in ((156000,1200),(625000,900),(2500000,400),(5000000,160),(10000000,100)):
    TECHNOLOGY_SEMANTICS['cc_link']['parameter_constraints'].append(
        {'when':{'bitrate_bps':_ccl_rate,'ccl_cable_version':'1.10','ccl_topology':'LINE'},'parameter':'ccl_main_length_m','maximum':_ccl_maximum})
for _ccl_rate,_ccl_main,_ccl_branches in ((156000,500,200),(625000,100,50)):
    for _ccl_key,_ccl_limit in (('ccl_main_length_m',_ccl_main),('ccl_branch_total_m',_ccl_branches)):
        TECHNOLOGY_SEMANTICS['cc_link']['parameter_constraints'].append(
            {'when':{'bitrate_bps':_ccl_rate,'ccl_topology':'T_BRANCH'},'parameter':_ccl_key,'maximum':_ccl_limit})
for _ccl_rate,_ccl_limit in ((156000,1200),(625000,600),(2500000,200)):
    TECHNOLOGY_SEMANTICS['cc_link']['parameter_constraints'].append(
        {'when':{'bitrate_bps':_ccl_rate,'ccl_cable_version':'1.00_STANDARD','ccl_topology':'LINE'},'parameter':'ccl_main_length_m','maximum':_ccl_limit})
# The shortest remote-to-remote segment controls the legacy cable limit.
for _ccl_rate,_ccl_spacing,_ccl_limit in ((5000000,(0.3,0.6),110),(5000000,(0.6,None),150),
                                       (10000000,(0.3,0.6),50),(10000000,(0.6,1),80),(10000000,(1,None),100)):
    TECHNOLOGY_SEMANTICS['cc_link']['parameter_constraints'].append(
        {'when':{'bitrate_bps':_ccl_rate,'ccl_cable_version':'1.00_STANDARD','ccl_topology':'LINE'},
         'when_half_open_ranges':{'ccl_remote_spacing_m':_ccl_spacing},'parameter':'ccl_main_length_m','maximum':_ccl_limit})
for _ccl_occ in range(1,5):
    for _ccl_cycle in (1,2,4,8):
        _ccl_bits = 32*_ccl_occ if _ccl_cycle==1 else (2*_ccl_occ-1)*16*_ccl_cycle
        for _ccl_key,_ccl_limit in (('ccl_rx_bits',_ccl_bits),('ccl_ry_bits',_ccl_bits),
                                   ('ccl_rwr_words',4*_ccl_occ*_ccl_cycle),('ccl_rww_words',4*_ccl_occ*_ccl_cycle)):
            TECHNOLOGY_SEMANTICS['cc_link']['parameter_constraints'].append(
                {'when':{'ccl_occupied_stations':_ccl_occ,'ccl_extended_cycle':_ccl_cycle},'parameter':_ccl_key,'maximum':_ccl_limit})
for _ccl_version,_ccl_bits,_ccl_words in (('1.10',2048,256),('2.00',8192,2048)):
    for _ccl_key,_ccl_limit in (('ccl_total_rx_bits',_ccl_bits),('ccl_total_ry_bits',_ccl_bits),
                               ('ccl_total_rwr_words',_ccl_words),('ccl_total_rww_words',_ccl_words)):
        TECHNOLOGY_SEMANTICS['cc_link']['parameter_constraints'].append(
            {'when':{'ccl_protocol_version':_ccl_version},'parameter':_ccl_key,'maximum':_ccl_limit})
for _co_rate, _co_lengths in zip(CANOPEN_CC_RATES,((5000,275,1375),(2500,137.5,687.5),(1000,55,275),
                                               (500,22,110),(250,11,55),(100,5.5,27.5),(50,2.5,12.5),(25,1.5,7.5))):
    for _co_key,_co_limit in zip(('can_bus_length_m','can_stub_length_m','co_accumulated_stub_length_m'),_co_lengths):
        TECHNOLOGY_SEMANTICS['canopen']['parameter_constraints'].append(
            {'when':{'bitrate_bps':_co_rate,'can_phy':'HIGH_SPEED'},'parameter':_co_key,'maximum':_co_limit})
for _co_service in ('NMT','SDO','SYNC','TIME','EMCY','HEARTBEAT','BOOTUP'):
    TECHNOLOGY_SEMANTICS['canopen']['parameter_constraints'].append(
        {'when':{'co_service':_co_service},'parameter':'can_frame_type','allowed':['DATA']})
for _can_constraint in TECHNOLOGY_SEMANTICS['can']['parameter_constraints']:
    TECHNOLOGY_SEMANTICS['canopen']['parameter_constraints'].append(dict(_can_constraint))
    TECHNOLOGY_SEMANTICS['ccp']['parameter_constraints'].append(dict(_can_constraint))

for _canas_class, _canas_range in {'EED':(0,127),'NSH':(128,199),'UDH':(200,299),
                                  'NOD':(300,1799),'UDL':(1800,1899),'DSD':(1900,1999),'NSL':(2000,2031)}.items():
    TECHNOLOGY_SEMANTICS['can_aerospace']['parameter_constraints'].append(
        {'when':{'canas_message_class':_canas_class,'canas_distribution_id':0},'parameter':'canas_base_identifier',
         'minimum':_canas_range[0],'maximum':_canas_range[1]})
for _canas_type, _canas_length in {0:0,1:4,2:4,3:4,4:4,5:4,6:2,7:2,8:2,9:1,10:1,11:1,
                                  12:4,13:4,14:4,15:4,16:4,17:4,18:2,19:2,20:2,21:4,22:4,
                                  23:1,24:2,25:4,26:3,27:3,28:3,29:3,30:4,31:4}.items():
    TECHNOLOGY_SEMANTICS['can_aerospace']['parameter_constraints'].append(
        {'when':{'canas_data_type':_canas_type},'parameter':'payload_bytes','allowed':[_canas_length]})

# DeviceNet deliberately shares the specified CAN CC link while retaining its
# own discrete rates, identifier mapping, CIP connection and wiring constraints.
TECHNOLOGY_SEMANTICS['devicenet'] = {
    'rate_model': {'type': 'SINGLE_BITRATE', 'fields': ['bitrate_bps'],
                   'minimum_bps': 125000, 'maximum_bps': 500000, 'allowed_bps': [125000, 250000, 500000]},
    'mechanisms': {'arbitration': ['CAN_NON_DESTRUCTIVE_BITWISE'], 'integrity': ['CAN_CC_CRC'],
                   'connection': ['UCMM_OR_GROUP2_UNCONNECTED', 'EXPLICIT_AND_IMPLICIT_CIP'],
                   'supervision': ['DUPLICATE_MAC_CHECK', 'CONNECTION_WATCHDOG', 'COS_HEARTBEAT'],
                   'physical': ['DEVICENET_TRUNK_DROP_POWER_AND_SIGNAL']},
    'parameter_constraints': [
        *TECHNOLOGY_SEMANTICS['can']['parameter_constraints'],
        {'when': {}, 'parameter': 'can_frame_format', 'allowed': ['BASE_11']},
        {'when': {}, 'parameter': 'can_frame_type', 'allowed': ['DATA']},
        {'when': {}, 'parameter': 'can_identifier', 'maximum': 2047},
        *[{'when': {'dn_identifier_layout': 'CLASSIC_GROUPS_1_4', 'dn_message_group': group},
           'parameter': 'can_identifier', 'minimum': lower, 'maximum': upper,
           'equal_expression': {'sum': [base, {'product': [factor, 'dn_message_id']}, 'dn_identifier_mac_id']}
           if group in ('GROUP1', 'GROUP3') else
           {'sum': [1024, {'product': [8, 'dn_identifier_mac_id']}, 'dn_message_id']}
           if group == 'GROUP2' else {'sum': [1984, 'dn_message_id']}}
          for group, lower, upper, base, factor in (('GROUP1',0,1023,0,64), ('GROUP2',1024,1535,1024,8),
                                                   ('GROUP3',1536,1983,1536,64), ('GROUP4',1984,2031,1984,1))],
        {'when': {'dn_identifier_layout': 'CLASSIC_GROUPS_1_4'}, 'parameter': 'can_identifier', 'maximum': 2031},
        *[{'when': {'dn_identifier_layout': 'CLASSIC_GROUPS_1_4', 'dn_message_group': group},
           'parameter': 'dn_message_id', 'maximum': maximum}
          for group, maximum in (('GROUP1',15), ('GROUP2',7), ('GROUP3',6), ('GROUP4',47))],
        {'when': {'dn_message_group': 'GROUP4', 'dn_identifier_layout': 'CLASSIC_GROUPS_1_4'}, 'parameter': 'dn_identifier_mac_id', 'allowed': []},
        *[{'when': {'dn_cable_type': cable, 'bitrate_bps': rate}, 'parameter': 'can_bus_length_m', 'maximum': length}
          for cable, lengths in {'THICK': (500,250,100), 'MID': (300,250,100),
                                 'THIN': (100,100,100), 'FLAT': (420,200,75)}.items()
          for rate, length in zip((125000,250000,500000),lengths)],
        *[{'when': {'bitrate_bps': rate}, 'parameter': 'dn_cumulative_drop_m', 'maximum': length}
          for rate,length in ((125000,156),(250000,78),(500000,39))],
        {'when': {}, 'parameter': 'can_stub_length_m', 'maximum': 6},
        {'when': {}, 'parameter': 'can_stub_length_m', 'maximum_parameter': 'dn_cumulative_drop_m'},
        {'when': {}, 'parameter': 'dn_inhibit_ms', 'maximum_parameter': 'dn_heartbeat_ms'},
        {'when': {}, 'parameter': 'dn_worst_node_voltage_v', 'maximum_parameter': 'dn_supply_voltage_v'},
        {'when': {}, 'parameter': 'dn_worst_node_voltage_v', 'minimum_parameter': 'dn_device_minimum_voltage_v'},
        {'when': {}, 'parameter': 'dn_supply_voltage_v', 'exclusive_minimum': 0},
        {'when': {}, 'parameter': 'dn_device_minimum_voltage_v', 'exclusive_minimum': 0},
        {'when': {}, 'parameter': 'dn_cip_data_bytes', 'equal_expression': {'subtract': ['payload_bytes', 'dn_protocol_header_bytes']}},
        {'when': {'dn_fragmented': False}, 'parameter': 'dn_complete_message_bytes', 'equal_parameter': 'dn_cip_data_bytes'},
        {'when': {'dn_fragmented': False}, 'parameter': 'dn_complete_message_bytes', 'maximum': 8},
        {'when': {'dn_fragmented': True}, 'parameter': 'dn_complete_message_bytes', 'minimum_parameter': 'dn_cip_data_bytes'},
        {'when': {}, 'parameter': 'dn_complete_message_bytes', 'maximum_parameter': 'dn_peer_message_limit_bytes'},
        {'when': {'dn_duplicate_mac_passed': False}, 'parameter': 'dn_connection_state', 'allowed': ['UNCONNECTED', 'FAULTED']},
    ],
}

TECHNOLOGY_SEMANTICS['dnp3'] = {
    'rate_model': {'type': 'APPLICATION_TRANSPORT_DEPENDENT', 'fields': []},
    'required_parameters': ['dnp_role', 'dnp_transport', 'dnp_transport_binding', 'dnp_configuration_source'],
    'mechanisms': {'integrity': ['DNP3_LINK_HEADER_AND_16_OCTET_BLOCK_CRC'],
                   'addressing': ['DNP3_SOURCE_DESTINATION_LINK_ADDRESSES'],
                   'fragmentation': ['LINK_250_OCTETS', 'TRANSPORT_249_APPLICATION_OCTETS', 'PEER_BUFFER_LIMITED_APPLICATION_FRAGMENTS'],
                   'delivery': ['POLLING_OR_UNSOLICITED', 'OPTIONAL_LINK_CONFIRM', 'APPLICATION_CONFIRM'],
                   'objects': ['GROUP_VARIATION_POINT_INDEX', 'STATIC_CLASS0_AND_EVENT_CLASSES1_2_3']},
    'parameter_constraints': [
        {'when': {}, 'parameter': 'dnp_master_address', 'not_equal_parameter': 'dnp_outstation_address'},
        {'when': {'dnp_destination_mode': 'UNICAST'}, 'parameter': 'dnp_destination_address', 'maximum': 65519},
        *[{'when': {'dnp_destination_mode': mode}, 'parameter': 'dnp_destination_address', 'allowed': [address]}
          for mode,address in (('SELF',65532),('BROADCAST_NO_CONFIRM',65533),('BROADCAST_CONFIRM',65534),('BROADCAST_OPTIONAL_CONFIRM',65535))],
        {'when_ranges': {'dnp_destination_address': [65520,65531]}, 'when': {}, 'parameter': 'dnp_destination_address', 'allowed': []},
        {'when': {}, 'parameter': 'dnp_link_length_field', 'equal_expression': {'sum': [5,'dnp_link_user_bytes']}},
        {'when': {}, 'parameter': 'dnp_link_frame_bytes', 'equal_expression': {'sum': [10,'dnp_link_user_bytes',
            {'product': [2, {'ceiling': [{'product': [0.0625, 'dnp_link_user_bytes']}]}]}]}},
        {'when': {}, 'when_ranges': {'dnp_link_user_bytes': [1,250]}, 'parameter': 'dnp_transport_data_bytes',
         'equal_expression': {'subtract': ['dnp_link_user_bytes',1]}},
        {'when': {'dnp_link_user_bytes': 0}, 'parameter': 'dnp_transport_data_bytes', 'allowed': []},
        {'when': {}, 'parameter': 'dnp_application_fragment_bytes', 'maximum_parameter': 'dnp_fragment_limit_bytes'},
        {'when': {}, 'parameter': 'dnp_application_fragment_bytes', 'maximum_parameter': 'dnp_peer_rx_buffer_bytes'},
        {'when': {}, 'parameter': 'dnp_fragment_limit_bytes', 'maximum_parameter': 'dnp_peer_rx_buffer_bytes'},
        {'when': {}, 'parameter': 'dnp_application_fragment_bytes', 'maximum_parameter': 'payload_bytes'},
        {'when': {'dnp_application_kind': 'REQUEST'}, 'parameter': 'dnp_application_fragment_bytes', 'minimum': 2},
        *[{'when': {'dnp_application_kind': kind}, 'parameter': 'dnp_application_fragment_bytes', 'minimum': 4}
          for kind in ('RESPONSE','UNSOLICITED_RESPONSE')],
        {'when': {'dnp_link_confirm': False}, 'parameter': 'dnp_link_confirm_timeout_ms', 'allowed': []},
        {'when': {'dnp_link_confirm': False}, 'parameter': 'dnp_link_retries', 'allowed': []},
        {'when': {'dnp_unsolicited_enabled': False}, 'parameter': 'dnp_application_kind', 'allowed': ['REQUEST','RESPONSE']},
        {'when': {'dnp_unsolicited_retry_mode': 'UNLIMITED'}, 'parameter': 'dnp_max_unsolicited_retries', 'allowed': []},
        {'when': {'dnp_keepalive_enabled': False}, 'parameter': 'dnp_keepalive_ms', 'allowed': []},
        {'when': {'dnp_transport': 'SERIAL'}, 'parameter': 'dnp_port', 'allowed': []},
        {'when': {'dnp_transport': 'TLS'}, 'parameter': 'dnp_security_mode', 'allowed': ['TLS_ONLY','TLS_AND_SA','DEVICE_SPECIFIC']},
        {'when': {}, 'parameter': 'dnp_auto_retry_max_ms', 'minimum_parameter': 'dnp_auto_retry_min_ms'},
        {'when': {}, 'parameter': 'dnp_point_index_end', 'minimum_parameter': 'dnp_point_index_start'},
        {'when': {'dnp_application_kind': 'UNSOLICITED_RESPONSE'}, 'parameter': 'dnp_data_class', 'allowed': ['CLASS1','CLASS2','CLASS3']},
        *[{'when': {'dnp_role': 'MASTER'}, 'parameter': key, 'allowed': []} for key in
          ('dnp_app_confirm_timeout_ms','dnp_select_timeout_ms','dnp_unsolicited_enabled',
           'dnp_unsolicited_retry_mode','dnp_max_unsolicited_retries','dnp_unsolicited_retry_delay_ms')],
        *[{'when': {'dnp_role': 'OUTSTATION'}, 'parameter': key, 'allowed': []} for key in
          ('dnp_response_timeout_ms','dnp_auto_retry_min_ms','dnp_auto_retry_max_ms')],
    ],
}

TECHNOLOGY_SEMANTICS['doip'] = {
    'rate_model': {'type': 'APPLICATION_TRANSPORT_DEPENDENT', 'fields': []},
    'required_parameters': ['doip_transport','doip_transport_binding','doip_edition','doip_configuration_source'],
    'mechanisms': {'integrity': ['VERSION_INVERSE_PATTERN_AND_PAYLOAD_LENGTH', 'SELECTED_IP_TRANSPORT_INTEGRITY'],
                   'discovery': ['UDP_VEHICLE_IDENTIFICATION_ANNOUNCEMENT'],
                   'diagnostics': ['TCP_DATA_OR_TLS', 'ROUTING_ACTIVATION', 'LOGICAL_SOURCE_TARGET_ADDRESSES', 'DOIP_ACK_NACK'],
                   'supervision': ['INITIAL_GENERAL_INACTIVITY_AND_ALIVE_CHECK'],
                   'upper_layer': ['UDS_TIMING_IS_SEPARATE_FROM_DOIP_ACK']},
    'parameter_constraints': [
        {'when': {}, 'parameter': 'doip_inverse_version', 'equal_expression': {'subtract': [255,'doip_protocol_version']}},
        {'when': {}, 'parameter': 'doip_message_bytes', 'equal_expression': {'sum': [8,'payload_bytes']}},
        *[{'when': {'doip_edition': edition}, 'when_ranges': {'doip_protocol_version': [0,254]},
           'parameter': 'doip_protocol_version', 'allowed': [version]} for edition,version in (('ISO_2012',2),('ISO_2019',3))],
        {'when': {'doip_protocol_version': 255}, 'parameter': 'doip_payload_type', 'allowed': [1,2,3]},
        {'when': {'doip_protocol_version': 255}, 'parameter': 'doip_transport', 'allowed': ['UDP']},
        *[{'when': {'doip_edition': edition}, 'parameter': 'doip_payload_type',
           'allowed': [0,1,2,3,4,5,6,7,8,16385,16386,16387,16388,32769,32770,32771]}
          for edition in ('ISO_2012','ISO_2019')],
        *[{'when': {'doip_payload_type': kind}, 'parameter': 'doip_transport', 'allowed': ['UDP']}
          for kind in (1,2,3,4,16385,16386,16387,16388)],
        *[{'when': {'doip_payload_type': kind}, 'parameter': 'doip_transport', 'allowed': ['TCP','TLS']}
          for kind in (5,6,7,8,32769,32770,32771)],
        *[{'when': {'doip_payload_type': kind}, 'parameter': 'payload_bytes', 'allowed': [length]}
          for kind,length in ((0,1),(1,0),(2,6),(3,17),(7,0),(8,2),(16385,0),(16387,0),(16388,1))],
        *[{'when': {'doip_payload_type': kind,'doip_optional_field_present': present}, 'parameter': 'payload_bytes', 'allowed': [base+extra if present else base]}
          for kind,base,extra in ((4,32,1),(5,7,4),(6,9,4),(16386,3,4)) for present in (False,True)],
        {'when': {'doip_payload_type': 32769}, 'parameter': 'payload_bytes', 'minimum': 5,
         'equal_expression': {'sum': [4,'doip_user_data_bytes']}},
        *[{'when': {'doip_payload_type': kind}, 'parameter': 'payload_bytes', 'minimum': 5,
           'equal_expression': {'sum': [5,'doip_ack_copy_bytes']}} for kind in (32770,32771)],
        {'when': {'doip_payload_type': 32770}, 'parameter': 'doip_ack_code', 'allowed': [0]},
        {'when': {}, 'parameter': 'doip_open_sockets', 'maximum_parameter': 'doip_max_sockets'},
        {'when': {'doip_peer_size_definition': 'DOIP_PAYLOAD'}, 'parameter': 'payload_bytes', 'maximum_parameter': 'doip_peer_size_limit_bytes'},
        {'when': {'doip_peer_size_definition': 'DIAGNOSTIC_USER_DATA'}, 'parameter': 'doip_user_data_bytes', 'maximum_parameter': 'doip_peer_size_limit_bytes'},
        {'when': {'doip_peer_size_definition': 'COMPLETE_DOIP_MESSAGE'}, 'parameter': 'doip_message_bytes', 'maximum_parameter': 'doip_peer_size_limit_bytes'},
        *[{'when': {'doip_peer_size_definition': definition}, 'parameter': 'doip_peer_size_limit_bytes', 'maximum': 4294967295}
          for definition in ('DOIP_PAYLOAD','DIAGNOSTIC_USER_DATA')],
        {'when': {'doip_transport': 'UDP'}, 'parameter': 'doip_routing_active', 'allowed': []},
        {'when': {'doip_transport': 'UDP'}, 'parameter': 'doip_tls_source', 'allowed': []},
        {'when': {'doip_payload_type': 32769}, 'parameter': 'doip_routing_active', 'allowed': [True]},
        {'when': {'doip_source_role': 'CLIENT'}, 'parameter': 'doip_source_address', 'minimum': 3584, 'maximum': 4095},
        {'when': {}, 'parameter': 'doip_reserved', 'allowed': [0]},
        {'when': {'doip_edition': 'ISO_2012'}, 'parameter': 'doip_transport', 'allowed': ['UDP','TCP']},
        *[{'when': {'doip_transport': 'UDP'}, 'parameter': key, 'allowed': []} for key in
          ('doip_initial_inactivity_ms','doip_general_inactivity_ms','doip_alive_check_ms','doip_diagnostic_ack_ms')],
        *[{'when': {'doip_transport': transport}, 'parameter': key, 'allowed': []}
          for transport in ('TCP','TLS') for key in ('doip_announce_wait_max_ms','doip_announce_interval_ms','doip_announce_count')],
        *[{'when': {'doip_payload_type': kind}, 'parameter': key, 'allowed': []}
          for kind in (0,1,2,3,4,5,6,7,8,16385,16386,16387,16388)
          for key in ('doip_user_data_bytes','doip_ack_copy_bytes','doip_ack_code')],
        {'when': {'doip_payload_type': 32769}, 'parameter': 'doip_ack_copy_bytes', 'allowed': []},
        {'when': {'doip_payload_type': 32769}, 'parameter': 'doip_ack_code', 'allowed': []},
        *[{'when': {'doip_payload_type': kind}, 'parameter': 'doip_user_data_bytes', 'allowed': []} for kind in (32770,32771)],
        *[{'when': {'doip_optional_field_present': False,'doip_payload_type': kind}, 'parameter': 'doip_oem_data', 'allowed': []} for kind in (5,6)],
    ],
}

# Generic Ethernet is the explicit IEEE 802.3 catalog entry. It shares the
# reviewed MAC/PHY declarations with Ethernet, rather than a separate guessed
# gigabit rate or protocol-independent payload/queue defaults.
TECHNOLOGY_SEMANTICS['generic_ethernet'] = deepcopy(TECHNOLOGY_SEMANTICS['ethernet'])

TECHNOLOGY_SEMANTICS['http'] = {'rate_model': {'type': 'APPLICATION_TRANSPORT_DEPENDENT', 'fields': []},
 'required_parameters': ['http_version',
                         'http_transport',
                         'http_binding_source',
                         'http_implementation_source',
                         'http_schedule_source'],
 'native_parameter_prefixes': ['http_', 'http2_', 'http3_'],
 'mechanisms': {'access': ['ACTUAL_HTTP1_ORDERING_HTTP2_STREAMS_OR_HTTP3_QUIC'],
                'integrity': ['ACTUAL_TRANSPORT_TLS_QUIC_AND_APPLICATION_ACCEPTANCE'],
                'scope': ['VERSION_SPECIFIC_APPLICATION_NOT_UNIVERSAL_ETHERNET_TCP_STACK']},
 'parameter_constraints': [{'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http2_frame_type',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http2_stream_id',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http2_frame_header_bytes',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http2_frame_payload_bytes',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http2_frame_bytes',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http2_settings_phase',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http2_max_frame_size',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http2_header_table_size',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http2_initial_window_size',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http2_current_stream_window',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http2_current_connection_window',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http2_enable_push',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http2_max_concurrent_streams',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http2_max_header_list_bytes',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http2_pad_length_present',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http2_padding_bytes',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http2_data_bytes',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http3_frame_type',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http3_frame_length',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http3_stream_kind',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http3_qpack_max_table',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http3_qpack_blocked_streams',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http3_max_field_section_bytes',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http3_settings_phase',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_1_1'},
                            'parameter': 'http3_quic_source',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_2'},
                            'parameter': 'http3_frame_type',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_2'},
                            'parameter': 'http3_frame_length',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_2'},
                            'parameter': 'http3_stream_kind',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_2'},
                            'parameter': 'http3_qpack_max_table',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_2'},
                            'parameter': 'http3_qpack_blocked_streams',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_2'},
                            'parameter': 'http3_max_field_section_bytes',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_2'},
                            'parameter': 'http3_settings_phase',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_2'},
                            'parameter': 'http3_quic_source',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http2_frame_type',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http2_stream_id',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http2_frame_header_bytes',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http2_frame_payload_bytes',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http2_frame_bytes',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http2_settings_phase',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http2_max_frame_size',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http2_header_table_size',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http2_initial_window_size',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http2_current_stream_window',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http2_current_connection_window',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http2_enable_push',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http2_max_concurrent_streams',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http2_max_header_list_bytes',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http2_pad_length_present',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http2_padding_bytes',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http2_data_bytes',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_2'},
                            'parameter': 'http_transport',
                            'allowed': ['TCP']},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http_transport',
                            'allowed': ['QUIC_V1']},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http_tls_version',
                            'allowed': ['TLS_1_3']},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http_security_source',
                            'required': True},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http3_quic_source',
                            'required': True},
                           {'when': {'http_scheme': 'https'},
                            'parameter': 'http_security_source',
                            'required': True},
                           {'when': {'http_scheme': 'https'},
                            'parameter': 'http_tls_version',
                            'required': True},
                           {'when': {'http_message_kind': 'REQUEST'},
                            'parameter': 'http_method',
                            'required': True},
                           {'when': {'http_message_kind': 'RESPONSE'},
                            'parameter': 'http_status',
                            'required': True},
                           {'when': {'http_message_kind': 'REQUEST'},
                            'parameter': 'http_status',
                            'allowed': []},
                           {'when': {'http_message_kind': 'REQUEST'},
                            'parameter': 'http_framing',
                            'allowed': ['NONE', 'CONTENT_LENGTH', 'CHUNKED', 'MULTIPLEXED']},
                           {'when': {'http_target_form': 'AUTHORITY'},
                            'parameter': 'http_method',
                            'allowed': ['CONNECT']},
                           {'when': {'http_target_form': 'ASTERISK'},
                            'parameter': 'http_method',
                            'allowed': ['OPTIONS']},
                           {'when': {'http_version': 'HTTP_1_1',
                                     'http_method': 'CONNECT',
                                     'http_message_kind': 'REQUEST'},
                            'parameter': 'http_target_form',
                            'allowed': ['AUTHORITY']},
                           {'when': {'http_version': 'HTTP_2'},
                            'parameter': 'http_target_form',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_2'},
                            'parameter': 'http_transfer_encoding',
                            'allowed': ['NONE']},
                           {'when': {'http_version': 'HTTP_2'},
                            'parameter': 'http_framing',
                            'allowed': ['NONE', 'MULTIPLEXED', 'TUNNEL']},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http_target_form',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http_transfer_encoding',
                            'allowed': ['NONE']},
                           {'when': {'http_version': 'HTTP_3'},
                            'parameter': 'http_framing',
                            'allowed': ['NONE', 'MULTIPLEXED', 'TUNNEL']},
                           {'when': {},
                            'parameter': 'http_content_length_present',
                            'when_present': ['http_content_length'],
                            'allowed': [True]},
                           {'when': {'http_content_length_present': False},
                            'parameter': 'http_content_length',
                            'allowed': []},
                           {'when': {'http_content_length_present': True},
                            'parameter': 'http_content_length',
                            'required': True},
                           {'when': {'http_content_length_present': True},
                            'parameter': 'http_length_semantics',
                            'required': True},
                           {'when': {'http_length_semantics': 'MESSAGE_BODY'},
                            'parameter': 'http_content_length',
                            'equal_decimal_parameter': 'http_body_bytes'},
                           {'when': {'http_transfer_encoding': 'CHUNKED'},
                            'parameter': 'http_content_length_present',
                            'allowed': [False]},
                           {'when': {'http_transfer_encoding': 'CHUNKED'},
                            'parameter': 'http_content_length',
                            'allowed': []},
                           {'when': {'http_transfer_encoding': 'CHUNKED'},
                            'parameter': 'http_transfer_source',
                            'required': True},
                           {'when': {'http_transfer_encoding': 'OTHER'},
                            'parameter': 'http_content_length_present',
                            'allowed': [False]},
                           {'when': {'http_transfer_encoding': 'OTHER'},
                            'parameter': 'http_content_length',
                            'allowed': []},
                           {'when': {'http_transfer_encoding': 'OTHER'},
                            'parameter': 'http_transfer_source',
                            'required': True},
                           {'when': {'http_framing': 'CHUNKED'},
                            'parameter': 'http_framing',
                            'when_present': ['http_transfer_encoding'],
                            'allowed': ['CHUNKED']},
                           {'when': {'http_version': 'HTTP_1_1', 'http_framing': 'CHUNKED'},
                            'parameter': 'http_transfer_encoding',
                            'allowed': ['CHUNKED']},
                           {'when': {'http_version': 'HTTP_1_1', 'http_framing': 'CHUNKED'},
                            'parameter': 'http_transfer_encoding',
                            'required': True},
                           {'when': {'http_version': 'HTTP_1_1', 'http_framing': 'CONTENT_LENGTH'},
                            'parameter': 'http_content_length_present',
                            'allowed': [True]},
                           {'when': {'http_version': 'HTTP_1_1', 'http_framing': 'CONTENT_LENGTH'},
                            'parameter': 'http_content_length_present',
                            'required': True},
                           {'when': {'http_message_kind': 'RESPONSE', 'http_method': 'HEAD'},
                            'parameter': 'http_body_bytes',
                            'pattern': '0+'},
                           {'when': {'http_message_kind': 'RESPONSE', 'http_status': 204},
                            'parameter': 'http_body_bytes',
                            'pattern': '0+'},
                           {'when': {'http_message_kind': 'RESPONSE', 'http_status': 205},
                            'parameter': 'http_body_bytes',
                            'pattern': '0+'},
                           {'when': {'http_message_kind': 'RESPONSE', 'http_status': 304},
                            'parameter': 'http_body_bytes',
                            'pattern': '0+'},
                           {'when': {'http_message_kind': 'RESPONSE'},
                            'parameter': 'http_body_bytes',
                            'when_ranges': {'http_status': [100, 199]},
                            'pattern': '0+'},
                           {'when': {'http_message_kind': 'RESPONSE', 'http_status': 204},
                            'parameter': 'http_content_length',
                            'allowed': []},
                           {'when': {'http_message_kind': 'RESPONSE'},
                            'parameter': 'http_content_length',
                            'when_ranges': {'http_status': [100, 199]},
                            'allowed': []},
                           {'when': {'http_message_kind': 'RESPONSE', 'http_status': 204},
                            'parameter': 'http_transfer_encoding',
                            'allowed': ['NONE']},
                           {'when': {'http_message_kind': 'RESPONSE'},
                            'parameter': 'http_transfer_encoding',
                            'when_ranges': {'http_status': [100, 199]},
                            'allowed': ['NONE']},
                           {'when': {'http_message_kind': 'REQUEST'},
                            'parameter': 'http_length_semantics',
                            'allowed': ['MESSAGE_BODY']},
                           {'when': {'http_message_kind': 'RESPONSE', 'http_method': 'CONNECT'},
                            'parameter': 'http_content_length',
                            'when_ranges': {'http_status': [200, 299]},
                            'allowed': []},
                           {'when': {'http_message_kind': 'RESPONSE', 'http_method': 'CONNECT'},
                            'parameter': 'http_transfer_encoding',
                            'when_ranges': {'http_status': [200, 299]},
                            'allowed': ['NONE']},
                           {'when': {'http_transition_optimistic': True},
                            'parameter': 'http_transition_source',
                            'required': True},
                           {'when': {},
                            'parameter': 'http_retry_source',
                            'when_positive': ['http_retry_limit'],
                            'required': True},
                           {'when': {'http_version': 'HTTP_2'},
                            'parameter': 'http2_frame_bytes',
                            'equal_sum': [{'parameter': 'http2_frame_header_bytes'},
                                          {'parameter': 'http2_frame_payload_bytes'}]},
                           {'when': {'http_version': 'HTTP_2'},
                            'parameter': 'http2_frame_payload_bytes',
                            'maximum_parameter': 'http2_max_frame_size'},
                           {'when': {'http_version': 'HTTP_2', 'http2_frame_type': 'DATA'},
                            'parameter': 'http2_stream_id',
                            'exclusive_minimum': 0},
                           {'when': {'http_version': 'HTTP_2', 'http2_frame_type': 'HEADERS'},
                            'parameter': 'http2_stream_id',
                            'exclusive_minimum': 0},
                           {'when': {'http_version': 'HTTP_2', 'http2_frame_type': 'PRIORITY'},
                            'parameter': 'http2_stream_id',
                            'exclusive_minimum': 0},
                           {'when': {'http_version': 'HTTP_2', 'http2_frame_type': 'RST_STREAM'},
                            'parameter': 'http2_stream_id',
                            'exclusive_minimum': 0},
                           {'when': {'http_version': 'HTTP_2', 'http2_frame_type': 'PUSH_PROMISE'},
                            'parameter': 'http2_stream_id',
                            'exclusive_minimum': 0},
                           {'when': {'http_version': 'HTTP_2', 'http2_frame_type': 'CONTINUATION'},
                            'parameter': 'http2_stream_id',
                            'exclusive_minimum': 0},
                           {'when': {'http_version': 'HTTP_2', 'http2_frame_type': 'SETTINGS'},
                            'parameter': 'http2_stream_id',
                            'allowed': [0]},
                           {'when': {'http_version': 'HTTP_2', 'http2_frame_type': 'PING'},
                            'parameter': 'http2_stream_id',
                            'allowed': [0]},
                           {'when': {'http_version': 'HTTP_2', 'http2_frame_type': 'GOAWAY'},
                            'parameter': 'http2_stream_id',
                            'allowed': [0]},
                           {'when': {'http_version': 'HTTP_2', 'http2_frame_type': 'PING'},
                            'parameter': 'http2_frame_payload_bytes',
                            'allowed': [8]},
                           {'when': {'http_version': 'HTTP_2', 'http2_frame_type': 'PRIORITY'},
                            'parameter': 'http2_frame_payload_bytes',
                            'allowed': [5]},
                           {'when': {'http_version': 'HTTP_2', 'http2_frame_type': 'RST_STREAM'},
                            'parameter': 'http2_frame_payload_bytes',
                            'allowed': [4]},
                           {'when': {'http_version': 'HTTP_2', 'http2_frame_type': 'WINDOW_UPDATE'},
                            'parameter': 'http2_frame_payload_bytes',
                            'allowed': [4]},
                           {'when': {'http_version': 'HTTP_2', 'http2_frame_type': 'GOAWAY'},
                            'parameter': 'http2_frame_payload_bytes',
                            'minimum': 8},
                           {'when': {'http_version': 'HTTP_2', 'http2_frame_type': 'SETTINGS'},
                            'parameter': 'http2_frame_payload_bytes',
                            'multiple_of': 6},
                           {'when': {'http_version': 'HTTP_2', 'http2_frame_type': 'DATA'},
                            'parameter': 'http2_frame_payload_bytes',
                            'when_positive': ['http2_frame_payload_bytes'],
                            'maximum_parameter': 'http2_current_stream_window'},
                           {'when': {'http_version': 'HTTP_2', 'http2_frame_type': 'DATA'},
                            'parameter': 'http2_frame_payload_bytes',
                            'when_positive': ['http2_frame_payload_bytes'],
                            'maximum_parameter': 'http2_current_connection_window'},
                           {'when': {'http_version': 'HTTP_2',
                                     'http2_frame_type': 'DATA',
                                     'http2_pad_length_present': False},
                            'parameter': 'http2_frame_payload_bytes',
                            'equal_sum': [{'parameter': 'http2_data_bytes'},
                                          {'parameter': 'http2_padding_bytes'}],
                            'equal_sum_offset': 0},
                           {'when': {'http_version': 'HTTP_2',
                                     'http2_frame_type': 'DATA',
                                     'http2_pad_length_present': True},
                            'parameter': 'http2_frame_payload_bytes',
                            'equal_sum': [{'parameter': 'http2_data_bytes'},
                                          {'parameter': 'http2_padding_bytes'}],
                            'equal_sum_offset': 1},
                           {'when': {'http_version': 'HTTP_2', 'http2_pad_length_present': False},
                            'parameter': 'http2_padding_bytes',
                            'allowed': [0]},
                           {'when': {'http_version': 'HTTP_2', 'http_role': 'SERVER'},
                            'parameter': 'http2_enable_push',
                            'allowed': [0]},
                           {'when': {'http_version': 'HTTP_3', 'http3_stream_kind': 'CONTROL'},
                            'parameter': 'http3_frame_type',
                            'forbidden': ['0', '1', '5']},
                           {'when': {'http_version': 'HTTP_3', 'http3_stream_kind': 'QPACK_ENCODER'},
                            'parameter': 'http3_frame_type',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3', 'http3_stream_kind': 'QPACK_DECODER'},
                            'parameter': 'http3_frame_type',
                            'allowed': []},
                           {'when': {'http_version': 'HTTP_3', 'http3_stream_kind': 'REQUEST'},
                            'parameter': 'http3_frame_type',
                            'forbidden': ['3', '4', '7', '13']},
                           {'when': {'http_version': 'HTTP_3', 'http3_stream_kind': 'PUSH'},
                            'parameter': 'http3_frame_type',
                            'forbidden': ['3', '4', '7', '13']},
                           {'when': {'http_message_kind': 'RESPONSE'},
                            'when_not': {'http_method': 'HEAD', 'http_status': 304},
                            'parameter': 'http_length_semantics',
                            'allowed': ['MESSAGE_BODY']},
                           {'when': {'http_transition_optimistic': True},
                            'parameter': 'http_transition_token',
                            'required': True},
                           {'when': {'http_transition_token': 'WEBSOCKET'},
                            'parameter': 'http_transition_optimistic',
                            'allowed': [False]},
                           {'when': {'http_version': 'HTTP_1_1', 'http_transition_token': 'CONNECT_UDP'},
                            'parameter': 'http_transition_optimistic',
                            'allowed': [False]},
                           {'when': {'http_version': 'HTTP_1_1', 'http_transition_token': 'CONNECT_IP'},
                            'parameter': 'http_transition_optimistic',
                            'allowed': [False]},
                           {'when': {'http_version': 'HTTP_1_1',
                                     'http_transition_token': 'CONNECT_TCP',
                                     'http_connect_untrusted': True},
                            'when_not': {'http_connection_close': True},
                            'parameter': 'http_wait_success',
                            'required': True,
                            'allowed': [True]},
                           {'when': {'http_version': 'HTTP_1_1',
                                     'http_transition_token': 'CONNECT_TCP',
                                     'http_transition_rejected': True,
                                     'http_role': 'PROXY'},
                            'parameter': 'http_connection_close',
                            'required': True,
                            'allowed': [True]},
                           {'when': {'http_version': 'HTTP_3', 'http_role': 'CLIENT'},
                            'parameter': 'http3_frame_type',
                            'forbidden': ['5']},
                           {'when': {'http_version': 'HTTP_3', 'http_role': 'SERVER'},
                            'parameter': 'http3_frame_type',
                            'forbidden': ['13']}]}

TECHNOLOGY_SEMANTICS['hart'] = {'rate_model': {'type': 'SINGLE_BITRATE', 'fields': ['bitrate_bps'], 'allowed_bps': [1200, 9600]},
 'required_parameters': ['bitrate_bps',
                         'hart_profile',
                         'hart_phy',
                         'hart_revision',
                         'hart_role',
                         'hart_binding_source',
                         'hart_device_source',
                         'hart_physical_source',
                         'hart_schedule_source'],
 'native_parameter_prefixes': ['hart_'],
 'mechanisms': {'access': ['ACTUAL_HALF_DUPLEX_DUAL_HOST_AND_BURST_ARBITRATION'],
                'integrity': ['QUALIFIED_FSK_ODD_PARITY_AND_XOR_CHECKSUM_NOT_AUTHENTICATION'],
                'scope': ['WIRED_FSK_OR_EXPLICIT_C8PSK_NOT_WIRELESSHART_HARTIP']},
 'parameter_constraints': [{'when': {'hart_phy': 'FSK'}, 'parameter': 'bitrate_bps', 'allowed': [1200]},
                           {'when': {'hart_phy': 'C8PSK'}, 'parameter': 'bitrate_bps', 'allowed': [9600]},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023'},
                            'parameter': 'hart_phy',
                            'allowed': ['FSK']},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023', 'hart_address_format': 'SHORT'},
                            'parameter': 'hart_address_bytes',
                            'allowed': [1]},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023', 'hart_address_format': 'LONG'},
                            'parameter': 'hart_address_bytes',
                            'allowed': [5]},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023'},
                            'parameter': 'hart_address_bytes',
                            'allowed': [1, 5]},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023'},
                            'parameter': 'hart_preamble_bytes',
                            'minimum_parameter': 'hart_peer_preamble_bytes'},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023'},
                            'parameter': 'hart_byte_count',
                            'equal_sum': [{'parameter': 'hart_data_bytes'},
                                          {'parameter': 'hart_status_bytes'}]},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023'},
                            'parameter': 'hart_wire_octets',
                            'equal_sum': [{'parameter': 'hart_preamble_bytes'},
                                          {'parameter': 'hart_address_bytes'},
                                          {'parameter': 'hart_expansion_bytes'},
                                          {'parameter': 'hart_byte_count'},
                                          {'parameter': 'hart_checksum_bytes'}],
                            'equal_sum_offset': 3},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023'},
                            'parameter': 'hart_wire_bits',
                            'equal_expression': {'product': ['hart_wire_octets', 'hart_char_bits']}},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023'},
                            'parameter': 'hart_serialization_ms',
                            'equal_ratio': {'numerator_parameter': 'hart_wire_bits',
                                            'denominator_sum': ['bitrate_bps'],
                                            'factor': 1000}},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023', 'hart_frame_kind': 'REQUEST'},
                            'parameter': 'hart_status_bytes',
                            'allowed': [0]},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023',
                                     'hart_frame_kind': 'REQUEST',
                                     'hart_address_format': 'SHORT'},
                            'parameter': 'hart_delimiter',
                            'equal_expression': {'sum': [2, {'product': [32, 'hart_expansion_bytes']}]}},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023',
                                     'hart_frame_kind': 'REQUEST',
                                     'hart_address_format': 'LONG'},
                            'parameter': 'hart_delimiter',
                            'equal_expression': {'sum': [130, {'product': [32, 'hart_expansion_bytes']}]}},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023', 'hart_frame_kind': 'RESPONSE'},
                            'parameter': 'hart_status_bytes',
                            'allowed': [2]},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023',
                                     'hart_frame_kind': 'RESPONSE',
                                     'hart_address_format': 'SHORT'},
                            'parameter': 'hart_delimiter',
                            'equal_expression': {'sum': [6, {'product': [32, 'hart_expansion_bytes']}]}},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023',
                                     'hart_frame_kind': 'RESPONSE',
                                     'hart_address_format': 'LONG'},
                            'parameter': 'hart_delimiter',
                            'equal_expression': {'sum': [134, {'product': [32, 'hart_expansion_bytes']}]}},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023', 'hart_frame_kind': 'BURST'},
                            'parameter': 'hart_status_bytes',
                            'allowed': [2]},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023',
                                     'hart_frame_kind': 'BURST',
                                     'hart_address_format': 'SHORT'},
                            'parameter': 'hart_delimiter',
                            'equal_expression': {'sum': [1, {'product': [32, 'hart_expansion_bytes']}]}},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023',
                                     'hart_frame_kind': 'BURST',
                                     'hart_address_format': 'LONG'},
                            'parameter': 'hart_delimiter',
                            'equal_expression': {'sum': [129, {'product': [32, 'hart_expansion_bytes']}]}},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023', 'hart_revision': 'REV5_OR_EARLIER'},
                            'parameter': 'hart_poll_address',
                            'maximum': 15},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023', 'hart_revision': 'REV6'},
                            'parameter': 'hart_poll_address',
                            'maximum': 63},
                           {'when': {'hart_profile': 'PUBLIC_FSK_2023', 'hart_revision': 'REV7'},
                            'parameter': 'hart_poll_address',
                            'maximum': 63},
                           {'when': {'hart_profile': 'FCG_FSK_2016'},
                            'parameter': 'hart_phy',
                            'allowed': ['FSK']},
                           {'when': {'hart_profile': 'FCG_FSK_2016', 'hart_address_format': 'SHORT'},
                            'parameter': 'hart_address_bytes',
                            'allowed': [1]},
                           {'when': {'hart_profile': 'FCG_FSK_2016', 'hart_address_format': 'LONG'},
                            'parameter': 'hart_address_bytes',
                            'allowed': [5]},
                           {'when': {'hart_profile': 'FCG_FSK_2016'},
                            'parameter': 'hart_address_bytes',
                            'allowed': [1, 5]},
                           {'when': {'hart_profile': 'FCG_FSK_2016'},
                            'parameter': 'hart_preamble_bytes',
                            'minimum_parameter': 'hart_peer_preamble_bytes'},
                           {'when': {'hart_profile': 'FCG_FSK_2016'},
                            'parameter': 'hart_byte_count',
                            'equal_sum': [{'parameter': 'hart_data_bytes'},
                                          {'parameter': 'hart_status_bytes'}]},
                           {'when': {'hart_profile': 'FCG_FSK_2016'},
                            'parameter': 'hart_wire_octets',
                            'equal_sum': [{'parameter': 'hart_preamble_bytes'},
                                          {'parameter': 'hart_address_bytes'},
                                          {'parameter': 'hart_expansion_bytes'},
                                          {'parameter': 'hart_byte_count'},
                                          {'parameter': 'hart_checksum_bytes'}],
                            'equal_sum_offset': 3},
                           {'when': {'hart_profile': 'FCG_FSK_2016'},
                            'parameter': 'hart_wire_bits',
                            'equal_expression': {'product': ['hart_wire_octets', 'hart_char_bits']}},
                           {'when': {'hart_profile': 'FCG_FSK_2016'},
                            'parameter': 'hart_serialization_ms',
                            'equal_ratio': {'numerator_parameter': 'hart_wire_bits',
                                            'denominator_sum': ['bitrate_bps'],
                                            'factor': 1000}},
                           {'when': {'hart_profile': 'FCG_FSK_2016', 'hart_frame_kind': 'REQUEST'},
                            'parameter': 'hart_status_bytes',
                            'allowed': [0]},
                           {'when': {'hart_profile': 'FCG_FSK_2016',
                                     'hart_frame_kind': 'REQUEST',
                                     'hart_address_format': 'SHORT'},
                            'parameter': 'hart_delimiter',
                            'equal_expression': {'sum': [2, {'product': [32, 'hart_expansion_bytes']}]}},
                           {'when': {'hart_profile': 'FCG_FSK_2016',
                                     'hart_frame_kind': 'REQUEST',
                                     'hart_address_format': 'LONG'},
                            'parameter': 'hart_delimiter',
                            'equal_expression': {'sum': [130, {'product': [32, 'hart_expansion_bytes']}]}},
                           {'when': {'hart_profile': 'FCG_FSK_2016', 'hart_frame_kind': 'RESPONSE'},
                            'parameter': 'hart_status_bytes',
                            'allowed': [2]},
                           {'when': {'hart_profile': 'FCG_FSK_2016',
                                     'hart_frame_kind': 'RESPONSE',
                                     'hart_address_format': 'SHORT'},
                            'parameter': 'hart_delimiter',
                            'equal_expression': {'sum': [6, {'product': [32, 'hart_expansion_bytes']}]}},
                           {'when': {'hart_profile': 'FCG_FSK_2016',
                                     'hart_frame_kind': 'RESPONSE',
                                     'hart_address_format': 'LONG'},
                            'parameter': 'hart_delimiter',
                            'equal_expression': {'sum': [134, {'product': [32, 'hart_expansion_bytes']}]}},
                           {'when': {'hart_profile': 'FCG_FSK_2016', 'hart_frame_kind': 'BURST'},
                            'parameter': 'hart_status_bytes',
                            'allowed': [2]},
                           {'when': {'hart_profile': 'FCG_FSK_2016',
                                     'hart_frame_kind': 'BURST',
                                     'hart_address_format': 'SHORT'},
                            'parameter': 'hart_delimiter',
                            'equal_expression': {'sum': [1, {'product': [32, 'hart_expansion_bytes']}]}},
                           {'when': {'hart_profile': 'FCG_FSK_2016',
                                     'hart_frame_kind': 'BURST',
                                     'hart_address_format': 'LONG'},
                            'parameter': 'hart_delimiter',
                            'equal_expression': {'sum': [129, {'product': [32, 'hart_expansion_bytes']}]}},
                           {'when': {'hart_profile': 'FCG_FSK_2016', 'hart_revision': 'REV5_OR_EARLIER'},
                            'parameter': 'hart_poll_address',
                            'maximum': 15},
                           {'when': {'hart_profile': 'FCG_FSK_2016', 'hart_revision': 'REV6'},
                            'parameter': 'hart_poll_address',
                            'maximum': 63},
                           {'when': {'hart_profile': 'FCG_FSK_2016', 'hart_revision': 'REV7'},
                            'parameter': 'hart_poll_address',
                            'maximum': 63},
                           {'when': {'hart_role': 'HOST'},
                            'parameter': 'hart_frame_kind',
                            'allowed': ['REQUEST']},
                           {'when': {'hart_role': 'FIELD_DEVICE'},
                            'parameter': 'hart_frame_kind',
                            'allowed': ['RESPONSE', 'BURST']},
                           {'when': {'hart_mode': 'REQUEST_RESPONSE'},
                            'parameter': 'hart_frame_kind',
                            'allowed': ['REQUEST', 'RESPONSE']},
                           {'when': {'hart_mode': 'BURST'},
                            'parameter': 'hart_burst_supported',
                            'allowed': [True]},
                           {'when': {'hart_mode': 'BURST'},
                            'parameter': 'hart_burst_supported',
                            'required': True},
                           {'when': {}, 'parameter': 'hart_burst_period_ms', 'exclusive_minimum': 0},
                           {'when': {},
                            'parameter': 'hart_extended_command',
                            'when_present': ['hart_extended_command'],
                            'required': True},
                           {'when': {},
                            'parameter': 'hart_command',
                            'when_present': ['hart_extended_command'],
                            'allowed': [31]},
                           {'when': {},
                            'parameter': 'hart_data_bytes',
                            'when_present': ['hart_extended_command'],
                            'minimum': 2},
                           {'when': {}, 'parameter': 'payload_bytes', 'equal_parameter': 'hart_data_bytes'},
                           {'when': {'hart_profile': 'FCG_FSK_2016',
                                     'hart_phy': 'FSK',
                                     'hart_host_role': 'PRIMARY'},
                            'parameter': 'hart_quiet_chars',
                            'allowed': [33]},
                           {'when': {'hart_profile': 'FCG_FSK_2016',
                                     'hart_phy': 'FSK',
                                     'hart_host_role': 'SECONDARY'},
                            'parameter': 'hart_quiet_chars',
                            'allowed': [41]},
                           {'when': {'hart_profile': 'FCG_FSK_2016', 'hart_phy': 'FSK', 'hart_role': 'HOST'},
                            'parameter': 'hart_host_role',
                            'required': True},
                           {'when': {'hart_profile': 'FCG_FSK_2016', 'hart_phy': 'FSK'},
                            'parameter': 'hart_gap_us',
                            'maximum_ratio': {'numerator_parameter': 'hart_char_bits',
                                              'denominator_sum': ['bitrate_bps'],
                                              'factor': 1000000},
                            'exclusive_maximum_ratio': True},
                           {'when': {'hart_profile': 'FCG_FSK_2016', 'hart_phy': 'FSK'},
                            'parameter': 'hart_response_start_ms',
                            'maximum_expression': {'product': ['hart_slave_timeout_chars',
                                                               11,
                                                               0.8333333333333334]}},
                           {'when': {}, 'parameter': 'hart_loop_supply_v', 'exclusive_minimum': 0},
                           {'when': {}, 'parameter': 'hart_signal_pp_ma', 'exclusive_minimum': 0},
                           {'when': {'hart_is_required': True},
                            'parameter': 'hart_is_source',
                            'required': True}]}

TECHNOLOGY_SEMANTICS['gpio'] = {'rate_model': {'type': 'DIRECT_IO_NO_PACKET_RATE', 'fields': []},
 'required_parameters': ['gpio_profile',
                         'gpio_pin',
                         'gpio_device_source',
                         'gpio_wiring_source',
                         'gpio_direction'],
 'native_parameter_prefixes': ['gpio_'],
 'mechanisms': {'access': ['ACTUAL_PIN_MODE_AND_REGISTER_TASK_INTERRUPT_SCHEDULE'],
                'integrity': ['ACTUAL_VOLTAGE_THRESHOLD_CURRENT_LOAD_AND_NOISE_EVIDENCE'],
                'scope': ['LOCAL_DIGITAL_IO_NOT_FRAMED_BUS']},
 'parameter_constraints': [{'when': {'gpio_profile': 'STM8TL5_RM0312_3',
                                     'gpio_phase': 'RESET',
                                     'gpio_reset_exception': False},
                            'parameter': 'gpio_direction',
                            'allowed': ['DIGITAL_INPUT']},
                           {'when': {'gpio_profile': 'STM8TL5_RM0312_3',
                                     'gpio_phase': 'RESET',
                                     'gpio_reset_exception': False},
                            'parameter': 'gpio_pull',
                            'allowed': ['NONE']},
                           {'when': {'gpio_profile': 'STM8TL5_RM0312_3'},
                            'parameter': 'gpio_pull',
                            'allowed': ['NONE', 'UP']},
                           {'when': {'gpio_direction': 'DIGITAL_INPUT'},
                            'parameter': 'gpio_drive',
                            'allowed': []},
                           {'when': {'gpio_direction': 'DIGITAL_OUTPUT'},
                            'parameter': 'gpio_input_mode',
                            'allowed': []},
                           {'when': {'gpio_direction': 'DIGITAL_OUTPUT'},
                            'parameter': 'gpio_event',
                            'allowed': []},
                           {'when': {'gpio_profile': 'STM8TL5_RM0312_3', 'gpio_direction': 'DIGITAL_OUTPUT'},
                            'parameter': 'gpio_pull',
                            'allowed': ['NONE']},
                           {'when': {'gpio_direction': 'DIGITAL_INPUT'},
                            'parameter': 'gpio_source_load_ma',
                            'allowed': []},
                           {'when': {'gpio_direction': 'DIGITAL_INPUT'},
                            'parameter': 'gpio_sink_load_ma',
                            'allowed': []},
                           {'when': {'gpio_direction': 'DIGITAL_OUTPUT', 'gpio_drive': 'PSEUDO_OPEN_DRAIN'},
                            'parameter': 'gpio_pull_source',
                            'required': True},
                           {'when': {'gpio_direction': 'DIGITAL_OUTPUT', 'gpio_drive': 'TRUE_OPEN_DRAIN'},
                            'parameter': 'gpio_pull_source',
                            'required': True},
                           {'when': {'gpio_input_mode': 'POLLED'}, 'parameter': 'gpio_event', 'allowed': []},
                           {'when': {}, 'parameter': 'gpio_vdd_v', 'exclusive_minimum': 0},
                           {'when': {}, 'parameter': 'gpio_pull_ohms', 'exclusive_minimum': 0},
                           {'when': {}, 'parameter': 'gpio_vil_max_v', 'maximum_parameter': 'gpio_vih_min_v'},
                           {'when': {}, 'parameter': 'gpio_vol_max_v', 'maximum_parameter': 'gpio_vil_max_v'},
                           {'when': {}, 'parameter': 'gpio_voh_min_v', 'minimum_parameter': 'gpio_vih_min_v'},
                           {'when': {},
                            'parameter': 'gpio_sink_load_ma',
                            'maximum_parameter': 'gpio_sink_bound_ma'},
                           {'when': {},
                            'parameter': 'gpio_source_load_ma',
                            'maximum_parameter': 'gpio_source_bound_ma'}]}

TECHNOLOGY_SEMANTICS['goose'] = {
    'rate_source_profile_id': 'ethernet',
    'rate_model': deepcopy(TECHNOLOGY_SEMANTICS['ethernet']['rate_model']),
    'required_parameters': ['bitrate_bps', 'goose_profile', 'goose_edition', 'goose_role', 'goose_binding_source', 'goose_scl_source', 'goose_device_source', 'goose_schedule_source'], 'native_parameter_prefixes':['eth_','goose_'],
    'mechanisms': {'access':['EXPLICIT_IEEE8023_L2_MULTICAST_GOCB'],
                   'integrity':['BER_DATASET_REVISION_STATE_SEQUENCE_AND_ACTUAL_SECURITY_SEPARATE'],
                   'scope':['LAN_GOOSE_NOT_UDP_IP_MMS_OR_ROUTED_GOOSE']},
    'parameter_constraints': deepcopy(TECHNOLOGY_SEMANTICS['ethernet']['parameter_constraints']) + [{'when': {'goose_profile': 'LIBIEC61850_1_6_L2'}, 'parameter': 'goose_encoding', 'allowed': ['ASN1_BER']},
 {'when': {}, 'parameter': 'goose_ethertype', 'allowed': [35000]},
 {'when': {}, 'parameter': 'eth_type_length', 'allowed': [35000]},
 {'when': {}, 'parameter': 'eth_frame_format', 'allowed': ['ETHERTYPE']},
 {'when': {}, 'parameter': 'eth_payload_layer', 'allowed': ['MAC_CLIENT']},
 {'when': {'goose_vlan_tag': True}, 'parameter': 'eth_vlan_tags', 'allowed': [1]},
 {'when': {'goose_vlan_tag': False}, 'parameter': 'eth_vlan_tags', 'allowed': [0]},
 {'when': {'goose_vlan_tag': False}, 'parameter': 'eth_tag_mode', 'allowed': ['UNTAGGED']},
 {'when': {'goose_profile': 'LIBIEC61850_1_6_L2'}, 'parameter': 'goose_timestamp_bytes', 'allowed': [8]},
 {'when': {}, 'parameter': 'goose_header_bytes', 'allowed': [8]},
 {'when': {'goose_profile': 'LIBIEC61850_1_6_L2'}, 'parameter': 'goose_reserved1', 'allowed': [0]},
 {'when': {'goose_profile': 'LIBIEC61850_1_6_L2'}, 'parameter': 'goose_reserved2', 'allowed': [0]},
 {'when': {},
  'parameter': 'goose_length_bytes',
  'equal_sum': [{'parameter': 'goose_header_bytes'}, {'parameter': 'goose_apdu_bytes'}]},
 {'when': {}, 'parameter': 'goose_length_bytes', 'maximum_parameter': 'mtu_bytes'},
 {'when': {}, 'parameter': 'payload_bytes', 'equal_parameter': 'goose_length_bytes'},
 {'when': {}, 'parameter': 'eth_client_bytes', 'equal_parameter': 'goose_length_bytes'},
 {'when': {}, 'parameter': 'goose_all_data_bytes', 'maximum_parameter': 'goose_apdu_bytes'},
 {'when': {}, 'parameter': 'goose_num_entries', 'equal_parameter': 'goose_actual_entries'},
 {'when': {}, 'parameter': 'goose_max_ms', 'minimum_parameter': 'goose_min_ms'},
 {'when': {}, 'parameter': 'goose_next_ms', 'maximum_parameter': 'goose_tal_ms'},
 {'when': {'goose_profile': 'LIBIEC61850_1_6_L2'},
  'parameter': 'goose_tal_ms',
  'equal_sum': [{'parameter': 'goose_tal_basis_ms', 'factor': 3}]},
 {'when': {'goose_profile': 'LIBIEC61850_1_6_L2', 'goose_phase': 'STATE_CHANGE'},
  'parameter': 'goose_sq_num',
  'allowed': [0]},
 {'when': {'goose_profile': 'LIBIEC61850_1_6_L2', 'goose_phase': 'STABLE'},
  'parameter': 'goose_next_ms',
  'equal_parameter': 'goose_max_ms'},
 {'when': {'goose_profile': 'LIBIEC61850_1_6_L2', 'goose_phase': 'STABLE'},
  'parameter': 'goose_tal_basis_ms',
  'equal_parameter': 'goose_max_ms'},
 {'when': {'goose_accept_operational': True},
  'parameter': 'goose_operating_mode',
  'allowed': ['OPERATIONAL']},
 {'when': {'goose_accept_operational': True},
  'parameter': 'goose_test',
  'required': True,
  'allowed': [False]},
 {'when': {'goose_accept_operational': True},
  'parameter': 'goose_nds_com',
  'required': True,
  'allowed': [False]},
 {'when': {'goose_accept_operational': True},
  'parameter': 'goose_conf_rev',
  'required': True,
  'equal_parameter': 'goose_expected_conf_rev'},
 {'when': {'goose_accept_operational': True}, 'parameter': 'goose_expected_conf_rev', 'required': True},
 {'when': {'goose_accept_operational': True}, 'parameter': 'goose_acceptance_source', 'required': True}]
}

TECHNOLOGY_SEMANTICS['generic_serial'] = {'rate_model': {'type': 'APPLICATION_TRANSPORT_DEPENDENT', 'fields': []},
 'required_parameters': ['gs_mode', 'gs_transport_binding', 'gs_implementation_source', 'gs_framing_source'],
 'native_parameter_prefixes': ['gs_'],
 'mechanisms': {'access': ['EXPLICIT_SERIAL_PORT_IMPLEMENTATION_AND_FRAMING'],
                'integrity': ['ACTUAL_UART_PARITY_AND_APPLICATION_FRAME_INTEGRITY_SEPARATE'],
                'scope': ['GENERIC_STREAM_NOT_UNIVERSAL_UART_USB_OR_SYNCHRONOUS_BUS']},
 'parameter_constraints': [{'when': {'gs_mode': 'SYNC_SERIAL'},
                            'parameter': 'gs_uart_profile',
                            'allowed': []},
                           {'when': {'gs_mode': 'SYNC_SERIAL'}, 'parameter': 'gs_baud_rate', 'allowed': []},
                           {'when': {'gs_mode': 'SYNC_SERIAL'},
                            'parameter': 'gs_peer_baud_rate',
                            'allowed': []},
                           {'when': {'gs_mode': 'SYNC_SERIAL'}, 'parameter': 'gs_data_bits', 'allowed': []},
                           {'when': {'gs_mode': 'SYNC_SERIAL'}, 'parameter': 'gs_parity', 'allowed': []},
                           {'when': {'gs_mode': 'SYNC_SERIAL'}, 'parameter': 'gs_start_bits', 'allowed': []},
                           {'when': {'gs_mode': 'SYNC_SERIAL'}, 'parameter': 'gs_stop_bits', 'allowed': []},
                           {'when': {'gs_mode': 'SYNC_SERIAL'}, 'parameter': 'gs_char_bits', 'allowed': []},
                           {'when': {'gs_mode': 'SYNC_SERIAL'},
                            'parameter': 'gs_encoded_characters',
                            'allowed': []},
                           {'when': {'gs_mode': 'SYNC_SERIAL'}, 'parameter': 'gs_wire_bits', 'allowed': []},
                           {'when': {'gs_mode': 'SYNC_SERIAL'},
                            'parameter': 'gs_serialization_us',
                            'allowed': []},
                           {'when': {'gs_mode': 'SYNC_SERIAL'},
                            'parameter': 'gs_gap_bound_us',
                            'allowed': []},
                           {'when': {'gs_mode': 'SYNC_SERIAL'},
                            'parameter': 'gs_flow_control',
                            'allowed': []},
                           {'when': {'gs_mode': 'SYNC_SERIAL'},
                            'parameter': 'gs_flow_bound_us',
                            'allowed': []},
                           {'when': {'gs_mode': 'SYNC_SERIAL'},
                            'parameter': 'gs_wire_bound_us',
                            'allowed': []},
                           {'when': {'gs_mode': 'USB_CDC'}, 'parameter': 'gs_uart_profile', 'allowed': []},
                           {'when': {'gs_mode': 'USB_CDC'}, 'parameter': 'gs_baud_rate', 'allowed': []},
                           {'when': {'gs_mode': 'USB_CDC'}, 'parameter': 'gs_peer_baud_rate', 'allowed': []},
                           {'when': {'gs_mode': 'USB_CDC'}, 'parameter': 'gs_data_bits', 'allowed': []},
                           {'when': {'gs_mode': 'USB_CDC'}, 'parameter': 'gs_parity', 'allowed': []},
                           {'when': {'gs_mode': 'USB_CDC'}, 'parameter': 'gs_start_bits', 'allowed': []},
                           {'when': {'gs_mode': 'USB_CDC'}, 'parameter': 'gs_stop_bits', 'allowed': []},
                           {'when': {'gs_mode': 'USB_CDC'}, 'parameter': 'gs_char_bits', 'allowed': []},
                           {'when': {'gs_mode': 'USB_CDC'},
                            'parameter': 'gs_encoded_characters',
                            'allowed': []},
                           {'when': {'gs_mode': 'USB_CDC'}, 'parameter': 'gs_wire_bits', 'allowed': []},
                           {'when': {'gs_mode': 'USB_CDC'},
                            'parameter': 'gs_serialization_us',
                            'allowed': []},
                           {'when': {'gs_mode': 'USB_CDC'}, 'parameter': 'gs_gap_bound_us', 'allowed': []},
                           {'when': {'gs_mode': 'USB_CDC'}, 'parameter': 'gs_flow_control', 'allowed': []},
                           {'when': {'gs_mode': 'USB_CDC'}, 'parameter': 'gs_flow_bound_us', 'allowed': []},
                           {'when': {'gs_mode': 'USB_CDC'}, 'parameter': 'gs_wire_bound_us', 'allowed': []},
                           {'when': {'gs_mode': 'CUSTOM_STREAM'},
                            'parameter': 'gs_uart_profile',
                            'allowed': []},
                           {'when': {'gs_mode': 'CUSTOM_STREAM'}, 'parameter': 'gs_baud_rate', 'allowed': []},
                           {'when': {'gs_mode': 'CUSTOM_STREAM'},
                            'parameter': 'gs_peer_baud_rate',
                            'allowed': []},
                           {'when': {'gs_mode': 'CUSTOM_STREAM'}, 'parameter': 'gs_data_bits', 'allowed': []},
                           {'when': {'gs_mode': 'CUSTOM_STREAM'}, 'parameter': 'gs_parity', 'allowed': []},
                           {'when': {'gs_mode': 'CUSTOM_STREAM'},
                            'parameter': 'gs_start_bits',
                            'allowed': []},
                           {'when': {'gs_mode': 'CUSTOM_STREAM'}, 'parameter': 'gs_stop_bits', 'allowed': []},
                           {'when': {'gs_mode': 'CUSTOM_STREAM'}, 'parameter': 'gs_char_bits', 'allowed': []},
                           {'when': {'gs_mode': 'CUSTOM_STREAM'},
                            'parameter': 'gs_encoded_characters',
                            'allowed': []},
                           {'when': {'gs_mode': 'CUSTOM_STREAM'}, 'parameter': 'gs_wire_bits', 'allowed': []},
                           {'when': {'gs_mode': 'CUSTOM_STREAM'},
                            'parameter': 'gs_serialization_us',
                            'allowed': []},
                           {'when': {'gs_mode': 'CUSTOM_STREAM'},
                            'parameter': 'gs_gap_bound_us',
                            'allowed': []},
                           {'when': {'gs_mode': 'CUSTOM_STREAM'},
                            'parameter': 'gs_flow_control',
                            'allowed': []},
                           {'when': {'gs_mode': 'CUSTOM_STREAM'},
                            'parameter': 'gs_flow_bound_us',
                            'allowed': []},
                           {'when': {'gs_mode': 'CUSTOM_STREAM'},
                            'parameter': 'gs_wire_bound_us',
                            'allowed': []},
                           {'when': {'gs_mode': 'ASYNC_UART'}, 'parameter': 'gs_clock_hz', 'allowed': []},
                           {'when': {'gs_mode': 'USB_CDC'}, 'parameter': 'gs_clock_hz', 'allowed': []},
                           {'when': {'gs_mode': 'CUSTOM_STREAM'}, 'parameter': 'gs_clock_hz', 'allowed': []},
                           {'when': {'gs_mode': 'ASYNC_UART'},
                            'parameter': 'gs_cdc_line_coding_role',
                            'allowed': []},
                           {'when': {'gs_mode': 'SYNC_SERIAL'},
                            'parameter': 'gs_cdc_line_coding_role',
                            'allowed': []},
                           {'when': {'gs_mode': 'CUSTOM_STREAM'},
                            'parameter': 'gs_cdc_line_coding_role',
                            'allowed': []},
                           {'when': {'gs_mode': 'ASYNC_UART'},
                            'parameter': 'gs_uart_profile',
                            'required': True},
                           {'when': {'gs_mode': 'ASYNC_UART'}, 'parameter': 'gs_baud_rate', 'required': True},
                           {'when': {'gs_mode': 'SYNC_SERIAL'}, 'parameter': 'gs_clock_hz', 'required': True},
                           {'when': {'gs_mode': 'USB_CDC'},
                            'parameter': 'gs_cdc_line_coding_role',
                            'required': True},
                           {'when': {'gs_mode': 'ASYNC_UART'},
                            'parameter': 'gs_peer_baud_rate',
                            'equal_parameter': 'gs_baud_rate'},
                           {'when': {'gs_mode': 'ASYNC_UART', 'gs_uart_profile': 'TB3216_8N1'},
                            'parameter': 'gs_data_bits',
                            'allowed': [5, 6, 7, 8, 9]},
                           {'when': {'gs_mode': 'ASYNC_UART', 'gs_uart_profile': 'TB3216_8N1'},
                            'parameter': 'gs_parity',
                            'allowed': ['NONE', 'EVEN', 'ODD']},
                           {'when': {'gs_mode': 'ASYNC_UART', 'gs_uart_profile': 'TB3216_8N1'},
                            'parameter': 'gs_start_bits',
                            'allowed': [1]},
                           {'when': {'gs_mode': 'ASYNC_UART', 'gs_uart_profile': 'TB3216_8N1'},
                            'parameter': 'gs_stop_bits',
                            'allowed': [1, 2]},
                           {'when': {'gs_mode': 'ASYNC_UART',
                                     'gs_uart_profile': 'TB3216_8N1',
                                     'gs_parity': 'NONE'},
                            'parameter': 'gs_char_bits',
                            'equal_sum': [{'parameter': 'gs_start_bits'},
                                          {'parameter': 'gs_data_bits'},
                                          {'parameter': 'gs_stop_bits'}],
                            'equal_sum_offset': 0},
                           {'when': {'gs_mode': 'ASYNC_UART',
                                     'gs_uart_profile': 'TB3216_8N1',
                                     'gs_parity': 'EVEN'},
                            'parameter': 'gs_char_bits',
                            'equal_sum': [{'parameter': 'gs_start_bits'},
                                          {'parameter': 'gs_data_bits'},
                                          {'parameter': 'gs_stop_bits'}],
                            'equal_sum_offset': 1},
                           {'when': {'gs_mode': 'ASYNC_UART',
                                     'gs_uart_profile': 'TB3216_8N1',
                                     'gs_parity': 'ODD'},
                            'parameter': 'gs_char_bits',
                            'equal_sum': [{'parameter': 'gs_start_bits'},
                                          {'parameter': 'gs_data_bits'},
                                          {'parameter': 'gs_stop_bits'}],
                            'equal_sum_offset': 1},
                           {'when': {'gs_mode': 'ASYNC_UART', 'gs_uart_profile': 'TB3216_8N1'},
                            'parameter': 'gs_wire_bits',
                            'equal_expression': {'product': ['gs_char_bits', 'gs_encoded_characters']}},
                           {'when': {'gs_mode': 'ASYNC_UART', 'gs_uart_profile': 'TB3216_8N1'},
                            'parameter': 'gs_serialization_us',
                            'equal_ratio': {'numerator_parameter': 'gs_wire_bits',
                                            'denominator_sum': ['gs_baud_rate'],
                                            'factor': 1000000}},
                           {'when': {'gs_mode': 'ASYNC_UART', 'gs_uart_profile': 'TB3216_8N1'},
                            'parameter': 'gs_wire_bound_us',
                            'minimum_expression': {'sum': ['gs_serialization_us',
                                                           'gs_gap_bound_us',
                                                           'gs_flow_bound_us']}},
                           {'when': {'gs_mode': 'ASYNC_UART', 'gs_uart_profile': 'AVR_FRAME_FORMATS'},
                            'parameter': 'gs_data_bits',
                            'allowed': [5, 6, 7, 8, 9]},
                           {'when': {'gs_mode': 'ASYNC_UART', 'gs_uart_profile': 'AVR_FRAME_FORMATS'},
                            'parameter': 'gs_parity',
                            'allowed': ['NONE', 'EVEN', 'ODD']},
                           {'when': {'gs_mode': 'ASYNC_UART', 'gs_uart_profile': 'AVR_FRAME_FORMATS'},
                            'parameter': 'gs_start_bits',
                            'allowed': [1]},
                           {'when': {'gs_mode': 'ASYNC_UART', 'gs_uart_profile': 'AVR_FRAME_FORMATS'},
                            'parameter': 'gs_stop_bits',
                            'allowed': [1, 2]},
                           {'when': {'gs_mode': 'ASYNC_UART',
                                     'gs_uart_profile': 'AVR_FRAME_FORMATS',
                                     'gs_parity': 'NONE'},
                            'parameter': 'gs_char_bits',
                            'equal_sum': [{'parameter': 'gs_start_bits'},
                                          {'parameter': 'gs_data_bits'},
                                          {'parameter': 'gs_stop_bits'}],
                            'equal_sum_offset': 0},
                           {'when': {'gs_mode': 'ASYNC_UART',
                                     'gs_uart_profile': 'AVR_FRAME_FORMATS',
                                     'gs_parity': 'EVEN'},
                            'parameter': 'gs_char_bits',
                            'equal_sum': [{'parameter': 'gs_start_bits'},
                                          {'parameter': 'gs_data_bits'},
                                          {'parameter': 'gs_stop_bits'}],
                            'equal_sum_offset': 1},
                           {'when': {'gs_mode': 'ASYNC_UART',
                                     'gs_uart_profile': 'AVR_FRAME_FORMATS',
                                     'gs_parity': 'ODD'},
                            'parameter': 'gs_char_bits',
                            'equal_sum': [{'parameter': 'gs_start_bits'},
                                          {'parameter': 'gs_data_bits'},
                                          {'parameter': 'gs_stop_bits'}],
                            'equal_sum_offset': 1},
                           {'when': {'gs_mode': 'ASYNC_UART', 'gs_uart_profile': 'AVR_FRAME_FORMATS'},
                            'parameter': 'gs_wire_bits',
                            'equal_expression': {'product': ['gs_char_bits', 'gs_encoded_characters']}},
                           {'when': {'gs_mode': 'ASYNC_UART', 'gs_uart_profile': 'AVR_FRAME_FORMATS'},
                            'parameter': 'gs_serialization_us',
                            'equal_ratio': {'numerator_parameter': 'gs_wire_bits',
                                            'denominator_sum': ['gs_baud_rate'],
                                            'factor': 1000000}},
                           {'when': {'gs_mode': 'ASYNC_UART', 'gs_uart_profile': 'AVR_FRAME_FORMATS'},
                            'parameter': 'gs_wire_bound_us',
                            'minimum_expression': {'sum': ['gs_serialization_us',
                                                           'gs_gap_bound_us',
                                                           'gs_flow_bound_us']}},
                           {'when': {'gs_mode': 'ASYNC_UART', 'gs_uart_profile': 'TB3216_8N1'},
                            'parameter': 'gs_data_bits',
                            'allowed': [8]},
                           {'when': {'gs_mode': 'ASYNC_UART', 'gs_uart_profile': 'TB3216_8N1'},
                            'parameter': 'gs_parity',
                            'allowed': ['NONE']},
                           {'when': {'gs_mode': 'ASYNC_UART', 'gs_uart_profile': 'TB3216_8N1'},
                            'parameter': 'gs_start_bits',
                            'allowed': [1]},
                           {'when': {'gs_mode': 'ASYNC_UART', 'gs_uart_profile': 'TB3216_8N1'},
                            'parameter': 'gs_stop_bits',
                            'allowed': [1]},
                           {'when': {'gs_mode': 'ASYNC_UART', 'gs_uart_profile': 'TB3216_8N1'},
                            'parameter': 'gs_char_bits',
                            'allowed': [10]},
                           {'when': {},
                            'parameter': 'gs_message_bytes',
                            'maximum_parameter': 'gs_max_message_bytes'}]}

TECHNOLOGY_SEMANTICS['generic_can'] = {'rate_model': {'type': 'APPLICATION_TRANSPORT_DEPENDENT', 'fields': []},
 'required_parameters': ['gcan_family',
                         'gcan_transport_binding',
                         'gcan_implementation_source',
                         'gcan_schedule_source'],
 'mechanisms': {'access': ['EXPLICIT_CC_FD_XL_REGISTERED_LINK_IDENTIFIER_ARBITRATION'],
                'integrity': ['SELECTED_FAMILY_CRC_AND_STUFFING_REQUIRED'],
                'scope': ['GENERIC_WRAPPER_NOT_NEW_NORMATIVE_CAN_GENERATION']},
 'parameter_constraints': [{'when': {'gcan_family': 'CAN_CC'},
                            'parameter': 'gcan_frame_format',
                            'allowed': ['STANDARD', 'EXTENDED']},
                           {'when': {'gcan_family': 'CAN_CC'},
                            'parameter': 'payload_bytes',
                            'minimum': 0,
                            'maximum': 8},
                           {'when': {'gcan_family': 'CAN_CC'},
                            'parameter': 'gcan_priority_id',
                            'allowed': []},
                           {'when': {'gcan_family': 'CAN_CC'},
                            'parameter': 'gcan_acceptance_field',
                            'allowed': []},
                           {'when': {'gcan_family': 'CAN_FD'},
                            'parameter': 'gcan_frame_format',
                            'allowed': ['STANDARD', 'EXTENDED']},
                           {'when': {'gcan_family': 'CAN_FD'},
                            'parameter': 'payload_bytes',
                            'minimum': 0,
                            'maximum': 64},
                           {'when': {'gcan_family': 'CAN_FD'},
                            'parameter': 'gcan_frame_kind',
                            'allowed': ['DATA']},
                           {'when': {'gcan_family': 'CAN_FD'},
                            'parameter': 'gcan_requested_bytes',
                            'allowed': []},
                           {'when': {'gcan_family': 'CAN_FD'},
                            'parameter': 'gcan_priority_id',
                            'allowed': []},
                           {'when': {'gcan_family': 'CAN_FD'},
                            'parameter': 'gcan_acceptance_field',
                            'allowed': []},
                           {'when': {'gcan_family': 'CAN_XL'},
                            'parameter': 'gcan_frame_format',
                            'allowed': ['XL']},
                           {'when': {'gcan_family': 'CAN_XL'},
                            'parameter': 'payload_bytes',
                            'minimum': 1,
                            'maximum': 2048},
                           {'when': {'gcan_family': 'CAN_XL'},
                            'parameter': 'gcan_frame_kind',
                            'allowed': ['DATA']},
                           {'when': {'gcan_family': 'CAN_XL'},
                            'parameter': 'gcan_requested_bytes',
                            'allowed': []},
                           {'when': {'gcan_frame_format': 'STANDARD'},
                            'parameter': 'gcan_identifier',
                            'maximum': 2047},
                           {'when': {'gcan_family': 'CAN_XL'}, 'parameter': 'gcan_identifier', 'allowed': []},
                           {'when': {'gcan_family': 'CAN_CC', 'gcan_frame_kind': 'REMOTE'},
                            'parameter': 'payload_bytes',
                            'allowed': [0]},
                           {'when': {'gcan_frame_kind': 'DATA'},
                            'parameter': 'gcan_requested_bytes',
                            'allowed': []},
                           {'when': {'gcan_family': 'CAN_FD'},
                            'parameter': 'payload_bytes',
                            'allowed': [0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64]}]}

TECHNOLOGY_SEMANTICS['fsoe'] = {'rate_model': {'type': 'APPLICATION_TRANSPORT_DEPENDENT', 'fields': []},
 'required_parameters': ['fsoe_profile',
                         'fsoe_role',
                         'fsoe_transport_binding',
                         'fsoe_implementation_source',
                         'fsoe_connection_source',
                         'fsoe_timing_source'],
 'mechanisms': {'access': ['MASTER_SLAVE_HANDSHAKE_OVER_EXPLICIT_BLACK_CHANNEL'],
                'integrity': ['CRC16_PER_TWO_SAFE_OCTETS',
                              'INHERITED_CRC_VIRTUAL_SEQUENCE_SESSION_AND_CONN_ID'],
                'supervision': ['BIDIRECTIONAL_WATCHDOG', 'SAFE_STATE_APPLICATION_DEFINED']},
 'parameter_constraints': [{'when': {'fsoe_profile': 'BASE_5100_1_2'},
                            'parameter': 'payload_bytes',
                            'minimum': 1},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2'},
                            'when_greater_than': {'payload_bytes': 1},
                            'parameter': 'payload_bytes',
                            'multiple_of': 2},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2'},
                            'parameter': 'fsoe_master_safe_bytes',
                            'minimum': 1},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2'},
                            'when_greater_than': {'fsoe_master_safe_bytes': 1},
                            'parameter': 'fsoe_master_safe_bytes',
                            'multiple_of': 2},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2'},
                            'parameter': 'fsoe_slave_safe_bytes',
                            'minimum': 1},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2'},
                            'when_greater_than': {'fsoe_slave_safe_bytes': 1},
                            'parameter': 'fsoe_slave_safe_bytes',
                            'multiple_of': 2},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_direction': 'MASTER_TO_SLAVE'},
                            'parameter': 'payload_bytes',
                            'equal_parameter': 'fsoe_master_safe_bytes'},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_direction': 'SLAVE_TO_MASTER'},
                            'parameter': 'payload_bytes',
                            'equal_parameter': 'fsoe_slave_safe_bytes'},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2'},
                            'parameter': 'fsoe_crc_count',
                            'equal_expression': {'ceiling': [{'product': [0.5, 'payload_bytes']}]}},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2'},
                            'parameter': 'fsoe_frame_bytes',
                            'equal_expression': {'sum': ['fsoe_command_bytes',
                                                         'payload_bytes',
                                                         {'product': ['fsoe_crc_count',
                                                                      'fsoe_crc_word_bytes']},
                                                         'fsoe_connection_bytes']}},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2'},
                            'parameter': 'fsoe_frame_bytes',
                            'maximum_parameter': 'fsoe_pdo_capacity_bytes'},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2'},
                            'parameter': 'fsoe_slave_address',
                            'equal_parameter': 'fsoe_peer_address'},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2'},
                            'parameter': 'fsoe_master_watchdog_ms',
                            'equal_parameter': 'fsoe_slave_watchdog_ms'},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2'},
                            'parameter': 'fsoe_master_watchdog_ms',
                            'minimum_parameter': 'fsoe_exchange_bound_ms'},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2'},
                            'when_present': ['fsoe_exchange_bound_ms'],
                            'parameter': 'fsoe_master_watchdog_ms',
                            'not_equal_parameter': 'fsoe_exchange_bound_ms'},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2'},
                            'parameter': 'fsoe_slave_watchdog_ms',
                            'minimum_parameter': 'fsoe_exchange_bound_ms'},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2'},
                            'when_present': ['fsoe_exchange_bound_ms'],
                            'parameter': 'fsoe_slave_watchdog_ms',
                            'not_equal_parameter': 'fsoe_exchange_bound_ms'},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2'},
                            'parameter': 'fsoe_parameter_remaining_bytes',
                            'maximum_parameter': 'fsoe_parameter_bytes'},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'RESET'},
                            'parameter': 'fsoe_data_command',
                            'allowed': []},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'RESET'},
                            'parameter': 'fsoe_conn_id',
                            'allowed': [0]},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'SESSION'},
                            'parameter': 'fsoe_conn_id',
                            'allowed': [0]},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'RESET'},
                            'parameter': 'fsoe_crc0',
                            'allowed': [0]},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'RESET'},
                            'parameter': 'fsoe_command',
                            'allowed': [42]},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'DATA'},
                            'parameter': 'fsoe_conn_id',
                            'minimum': 1},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'DATA'},
                            'parameter': 'fsoe_sequence',
                            'minimum': 1},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'DATA'},
                            'parameter': 'fsoe_parameters_accepted',
                            'allowed': [True]},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2',
                                     'fsoe_state': 'DATA',
                                     'fsoe_data_command': 'PROCESS_DATA'},
                            'parameter': 'fsoe_command',
                            'allowed': [54]},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2',
                                     'fsoe_state': 'DATA',
                                     'fsoe_data_command': 'FAILSAFE_DATA'},
                            'parameter': 'fsoe_command',
                            'allowed': [8]},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'DATA'},
                            'parameter': 'fsoe_direction',
                            'required': True},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'DATA'},
                            'parameter': 'fsoe_conn_id',
                            'required': True},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'DATA'},
                            'parameter': 'fsoe_slave_address',
                            'required': True},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'DATA'},
                            'parameter': 'fsoe_peer_address',
                            'required': True},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'DATA'},
                            'parameter': 'fsoe_parameters_accepted',
                            'required': True},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'DATA'},
                            'parameter': 'fsoe_master_watchdog_ms',
                            'required': True},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'DATA'},
                            'parameter': 'fsoe_slave_watchdog_ms',
                            'required': True},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'DATA'},
                            'parameter': 'fsoe_exchange_bound_ms',
                            'required': True},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'DATA'},
                            'parameter': 'fsoe_mapping_source',
                            'required': True},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'DATA'},
                            'parameter': 'fsoe_crc_source',
                            'required': True},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'DATA'},
                            'parameter': 'fsoe_safe_output_source',
                            'required': True},
                           {'when': {'fsoe_profile': 'BASE_5100_1_2', 'fsoe_state': 'DATA'},
                            'parameter': 'fsoe_assurance_source',
                            'required': True}]}

TECHNOLOGY_SEMANTICS['foundation_fieldbus_h1'] = {'rate_model': {'type': 'FIXED_LINK_RATE', 'fields': ['bitrate_bps'], 'fixed_bps': 31250},
 'required_parameters': ['bitrate_bps',
                         'ff_profile',
                         'ff_configuration_source',
                         'ff_cff_source',
                         'ff_physical_source',
                         'ff_schedule_source'],
 'mechanisms': {'access': ['LAS_SCHEDULED_COMPEL_DATA', 'PASS_TOKEN_UNSCHEDULED'],
                'integrity': ['DLPDU_FRAME_CHECK_SEQUENCE'],
                'synchronization': ['LINK_SCHEDULING_TIME_DISTRIBUTION', 'APPLICATION_TIME_SEPARATE'],
                'relationships': ['BUFFERED_PUBLISHER_SUBSCRIBER',
                                  'QUEUED_CLIENT_SERVER',
                                  'QUEUED_SOURCE_SINK']},
 'parameter_constraints': [{'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'DT'},
                            'parameter': 'ff_fms_pci_bytes',
                            'allowed': [4]},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'DT'},
                            'parameter': 'ff_fas_pci_bytes',
                            'allowed': [1]},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'DT'},
                            'parameter': 'ff_fcs_bytes',
                            'allowed': [2]},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'DT'},
                            'parameter': 'ff_dl_pci_bytes',
                            'minimum': 5,
                            'maximum': 15},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'DT'},
                            'parameter': 'ff_ph_sdu_bytes',
                            'minimum': 8,
                            'maximum': 273},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'DT'},
                            'parameter': 'ff_dl_sdu_bytes',
                            'minimum': 5,
                            'equal_expression': {'sum': ['payload_bytes',
                                                         'ff_fms_pci_bytes',
                                                         'ff_fas_pci_bytes']}},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'DT'},
                            'parameter': 'ff_ph_sdu_bytes',
                            'equal_expression': {'sum': ['ff_dl_sdu_bytes',
                                                         'ff_dl_pci_bytes',
                                                         'ff_fcs_bytes']}},
                           {'when': {'ff_profile': 'H1_VOLTAGE_MODE'},
                            'parameter': 'ff_wire_octets',
                            'equal_expression': {'sum': ['ff_ph_sdu_bytes',
                                                         'ff_preamble_bytes',
                                                         'ff_start_bytes',
                                                         'ff_end_bytes']}},
                           {'when': {'ff_priority': 'URGENT'}, 'parameter': 'ff_dl_sdu_bytes', 'maximum': 64},
                           {'when': {'ff_priority': 'NORMAL'},
                            'parameter': 'ff_dl_sdu_bytes',
                            'maximum': 128},
                           {'when': {'ff_priority': 'TIME_AVAILABLE'},
                            'parameter': 'ff_dl_sdu_bytes',
                            'maximum': 256},
                           {'when': {'ff_vcr': 'PUBLISHER_SUBSCRIBER'},
                            'parameter': 'ff_access',
                            'allowed': ['SCHEDULED_CD']},
                           {'when': {'ff_vcr': 'PUBLISHER_SUBSCRIBER'},
                            'parameter': 'ff_buffering',
                            'allowed': ['BUFFERED']},
                           {'when': {'ff_vcr': 'CLIENT_SERVER'},
                            'parameter': 'ff_access',
                            'allowed': ['UNSCHEDULED_PT']},
                           {'when': {'ff_vcr': 'CLIENT_SERVER'},
                            'parameter': 'ff_buffering',
                            'allowed': ['QUEUED']},
                           {'when': {'ff_vcr': 'SOURCE_SINK'},
                            'parameter': 'ff_access',
                            'allowed': ['UNSCHEDULED_PT']},
                           {'when': {'ff_vcr': 'SOURCE_SINK'},
                            'parameter': 'ff_buffering',
                            'allowed': ['QUEUED']},
                           {'when': {'ff_device_class': 'BASIC'},
                            'parameter': 'ff_las_active',
                            'allowed': [False]},
                           {'when': {'ff_address_state': 'OPERATIONAL'},
                            'parameter': 'ff_node_address',
                            'minimum': 16,
                            'maximum': 247},
                           {'when': {'ff_address_state': 'CLEARED'},
                            'parameter': 'ff_node_address',
                            'minimum': 248,
                            'maximum': 251},
                           {'when': {'ff_address_state': 'TEMPORARY'},
                            'parameter': 'ff_node_address',
                            'minimum': 252,
                            'maximum': 255},
                           {'when': {'ff_address_state': 'OPERATIONAL', 'ff_device_class': 'LINK_MASTER'},
                            'parameter': 'ff_node_address',
                            'maximum_parameter': 'ff_fun'},
                           {'when': {'ff_address_state': 'OPERATIONAL', 'ff_device_class': 'BRIDGE'},
                            'parameter': 'ff_node_address',
                            'maximum_parameter': 'ff_fun'},
                           {'when': {'ff_address_state': 'OPERATIONAL', 'ff_device_class': 'BASIC'},
                            'parameter': 'ff_node_address',
                            'minimum_expression': {'sum': ['ff_fun', 'ff_nun']}},
                           {'when': {},
                            'parameter': 'ff_nun',
                            'maximum_expression': {'subtract': [247, 'ff_fun']}},
                           {'when': {},
                            'parameter': 'ff_macrocycle_us',
                            'equal_expression': {'sum': ['ff_scheduled_us',
                                                         'ff_unscheduled_us',
                                                         'ff_maintenance_us']}},
                           {'when': {},
                            'parameter': 'ff_publish_offset_us',
                            'maximum_parameter': 'ff_macrocycle_us',
                            'maximum_offset': -0.001},
                           {'when': {'ff_access': 'SCHEDULED_CD'},
                            'parameter': 'ff_exchange_bound_us',
                            'maximum_parameter': 'ff_scheduled_us'},
                           {'when': {'ff_access': 'SCHEDULED_CD'},
                            'parameter': 'ff_token_hold_us',
                            'allowed': []},
                           {'when': {'ff_access': 'UNSCHEDULED_PT'},
                            'parameter': 'ff_publish_offset_us',
                            'allowed': []},
                           {'when': {'ff_access': 'UNSCHEDULED_PT'},
                            'parameter': 'ff_token_hold_us',
                            'maximum_parameter': 'ff_unscheduled_us'},
                           {'when': {},
                            'parameter': 'ff_segment_total_m',
                            'equal_expression': {'sum': ['ff_trunk_m', 'ff_spurs_total_m']}},
                           {'when': {'ff_profile': 'H1_VOLTAGE_MODE', 'ff_cable_type': 'TYPE_A'},
                            'parameter': 'ff_segment_total_m',
                            'maximum': 1900},
                           {'when': {'ff_profile': 'H1_VOLTAGE_MODE', 'ff_cable_type': 'TYPE_B'},
                            'parameter': 'ff_segment_total_m',
                            'maximum': 1200},
                           {'when': {'ff_profile': 'H1_VOLTAGE_MODE', 'ff_cable_type': 'TYPE_C'},
                            'parameter': 'ff_segment_total_m',
                            'maximum': 400},
                           {'when': {'ff_profile': 'H1_VOLTAGE_MODE', 'ff_cable_type': 'TYPE_D'},
                            'parameter': 'ff_segment_total_m',
                            'maximum': 200},
                           {'when': {'ff_profile': 'H1_VOLTAGE_MODE'},
                            'parameter': 'ff_terminal_v',
                            'minimum': 9,
                            'maximum': 32},
                           {'when': {'ff_profile': 'H1_VOLTAGE_MODE'},
                            'parameter': 'ff_terminators',
                            'allowed': [2]},
                           {'when': {}, 'parameter': 'ff_devices_ma', 'maximum_parameter': 'ff_supply_ma'},
                           {'when': {'ff_is_required': True}, 'parameter': 'ff_is_source', 'required': True},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'CD'},
                            'parameter': 'payload_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'CD'},
                            'parameter': 'ff_fms_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'CD'},
                            'parameter': 'ff_fas_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'PT'},
                            'parameter': 'payload_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'PT'},
                            'parameter': 'ff_fms_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'PT'},
                            'parameter': 'ff_fas_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'RT'},
                            'parameter': 'payload_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'RT'},
                            'parameter': 'ff_fms_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'RT'},
                            'parameter': 'ff_fas_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'EC'},
                            'parameter': 'payload_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'EC'},
                            'parameter': 'ff_fms_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'EC'},
                            'parameter': 'ff_fas_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'DC'},
                            'parameter': 'payload_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'DC'},
                            'parameter': 'ff_fms_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'DC'},
                            'parameter': 'ff_fas_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'RI'},
                            'parameter': 'payload_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'RI'},
                            'parameter': 'ff_fms_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'RI'},
                            'parameter': 'ff_fas_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'PN'},
                            'parameter': 'payload_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'PN'},
                            'parameter': 'ff_fms_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'PN'},
                            'parameter': 'ff_fas_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'PR'},
                            'parameter': 'payload_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'PR'},
                            'parameter': 'ff_fms_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'PR'},
                            'parameter': 'ff_fas_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'TD'},
                            'parameter': 'payload_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'TD'},
                            'parameter': 'ff_fms_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'TD'},
                            'parameter': 'ff_fas_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'CT'},
                            'parameter': 'payload_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'CT'},
                            'parameter': 'ff_fms_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'CT'},
                            'parameter': 'ff_fas_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'RQ'},
                            'parameter': 'payload_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'RQ'},
                            'parameter': 'ff_fms_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'RQ'},
                            'parameter': 'ff_fas_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'RR'},
                            'parameter': 'payload_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'RR'},
                            'parameter': 'ff_fms_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'RR'},
                            'parameter': 'ff_fas_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'CL'},
                            'parameter': 'payload_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'CL'},
                            'parameter': 'ff_fms_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'CL'},
                            'parameter': 'ff_fas_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'TL'},
                            'parameter': 'payload_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'TL'},
                            'parameter': 'ff_fms_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'TL'},
                            'parameter': 'ff_fas_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'IDLE'},
                            'parameter': 'payload_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'IDLE'},
                            'parameter': 'ff_fms_pci_bytes',
                            'allowed': []},
                           {'when': {'ff_layout': 'YOKOGAWA_FMS_DIAGRAM', 'ff_pdu': 'IDLE'},
                            'parameter': 'ff_fas_pci_bytes',
                            'allowed': []}]}

TECHNOLOGY_SEMANTICS['flexray'] = {
    'rate_model': {'type':'SINGLE_BITRATE','fields':['bitrate_bps'],'allowed_bps':[2500000,5000000,8000000,10000000]},
    'required_parameters':['bitrate_bps','fr_profile','fr_configuration_source','fr_physical_source','fr_schedule_source'],
    'mechanisms': {'access':['STATIC_TDMA','DYNAMIC_MINISLOT_FTDMA'],
                   'integrity':['HEADER_CRC11','CHANNEL_SPECIFIC_FRAME_CRC24'],
                   'synchronization':['COLDSTART_SYNC_FRAMES','OFFSET_AND_RATE_CORRECTION'],
                   'channels':['A_B_OR_AB','INDEPENDENT_OR_REDUNDANT_DECLARED_CONFIGURATION']},
    'parameter_constraints': [
        {'when': {'fr_profile':'PROTOCOL_3_0_1'},'parameter':'bitrate_bps','allowed':[2500000,5000000,10000000]},
        {'when': {'fr_profile':'NXP_MFR4310_2_1'},'parameter':'fr_cycle_count_max','allowed':[63]},
        {'when': {'fr_profile':'NXP_MFR4310_2_1'},'parameter':'fr_macro_per_cycle','minimum':10},
        *[{'when': {'fr_profile':'NXP_MFR4310_2_1','bitrate_bps':rate},'parameter':'fr_microtick_ns','allowed':[duration]}
          for rate,duration in ((2500000,50),(5000000,25),(8000000,25),(10000000,25))],
        *[{'when': {'fr_profile':'NXP_MFR4310_2_1','bitrate_bps':rate},'parameter':'fr_samples_per_microtick','allowed':[samples]}
          for rate,samples in ((2500000,1),(5000000,1),(8000000,2),(10000000,2))],
        {'when': {},'parameter':'payload_bytes','equal_expression':{'product':[2,'fr_payload_words']}},
        {'when': {'fr_segment':'STATIC'},'parameter':'fr_payload_words','equal_parameter':'fr_static_payload_words'},
        {'when': {'fr_segment':'DYNAMIC'},'parameter':'fr_payload_words','maximum_parameter':'fr_dynamic_payload_words_max'},
        {'when': {'fr_segment':'STATIC'},'parameter':'fr_frame_id','maximum_parameter':'fr_static_slots'},
        {'when': {'fr_segment':'DYNAMIC'},'parameter':'fr_frame_id','minimum_expression':{'sum':['fr_static_slots',1]}},
        {'when': {},'parameter':'fr_frame_bytes','equal_expression':{'sum':[8,'payload_bytes']}},
        {'when': {},'parameter':'fr_cycle_us','equal_expression':{'product':['fr_macro_per_cycle','fr_macrotick_us']}},
        {'when': {},'parameter':'fr_cycle_us','equal_expression':{'product':[0.001,'fr_micro_per_cycle','fr_microtick_ns']}},
        {'when': {},'parameter':'fr_cycle_mt','equal_expression':{'sum':[
            {'product':['fr_static_slots','fr_static_slot_mt']},
            {'product':['fr_minislots','fr_minislot_mt']},'fr_symbol_window_mt','fr_nit_mt']}},
        {'when': {},'parameter':'fr_cycle_mt','equal_parameter':'fr_macro_per_cycle'},
        {'when': {},'parameter':'fr_action_point_mt','maximum_parameter':'fr_static_slot_mt','maximum_offset':-1},
        {'when': {},'parameter':'fr_minislot_action_point_mt','maximum_parameter':'fr_minislot_mt','maximum_offset':-1},
        {'when': {},'parameter':'fr_symbol_action_point_mt','maximum_parameter':'fr_symbol_window_mt','maximum_offset':-1},
        {'when': {},'parameter':'fr_correction_start_mt','maximum_parameter':'fr_macro_per_cycle','maximum_offset':-1},
        {'when': {},'parameter':'fr_correction_start_mt','minimum_expression':{'subtract':['fr_macro_per_cycle','fr_nit_mt']}},
        {'when': {},'parameter':'fr_clock_fatal_pairs','minimum_parameter':'fr_clock_passive_pairs'},
        {'when': {},'parameter':'fr_cycle_counter','maximum_parameter':'fr_cycle_count_max'},
        {'when': {},'parameter':'fr_cycle_offset','maximum_parameter':'fr_repetition','maximum_offset':-1},
        {'when': {},'parameter':'fr_cycle_offset','maximum_parameter':'fr_cycle_count_max'},
        {'when': {'fr_segment':'DYNAMIC'},'parameter':'fr_sync_frame','allowed':[False]},
        {'when': {'fr_segment':'DYNAMIC'},'parameter':'fr_startup_frame','allowed':[False]},
        {'when': {'fr_startup_frame':True},'parameter':'fr_sync_frame','allowed':[True]},
        {'when': {'fr_startup_frame':True},'parameter':'fr_coldstart_node','allowed':[True]},
        {'when': {'fr_payload_valid':False},'parameter':'fr_preamble','allowed':[False]},
        {'when': {'fr_key_startup':True},'parameter':'fr_key_sync','allowed':[True]},
        *[{'when': {key:True},'parameter':'fr_key_slot_id','minimum':1,'maximum_parameter':'fr_static_slots'}
          for key in ('fr_key_startup','fr_key_sync','fr_key_only')],
        {'when': {'fr_two_key_mode':True},'parameter':'fr_second_key_id','minimum':1,
         'maximum_parameter':'fr_static_slots','not_equal_parameter':'fr_key_slot_id'},
        {'when': {'fr_channels':'A'},'parameter':'fr_tx_channels','allowed':['A']},
        {'when': {'fr_channels':'B'},'parameter':'fr_tx_channels','allowed':['B']},
        {'when': {'fr_channels':'A'},'parameter':'fr_wakeup_channel','allowed':['A']},
        {'when': {'fr_channels':'B'},'parameter':'fr_wakeup_channel','allowed':['B']},
        {'when': {'fr_segment':'STATIC','fr_preamble':True},'parameter':'fr_nmv_bytes','maximum_parameter':'payload_bytes'},
        {'when': {'fr_segment':'DYNAMIC','fr_preamble':True},'parameter':'payload_bytes','minimum':2},
        {'when': {'fr_segment':'DYNAMIC','fr_preamble':False},'parameter':'fr_message_id','allowed':[]},
        {'when': {'fr_segment':'STATIC'},'parameter':'fr_message_id','allowed':[]},
        {'when': {},'parameter':'fr_latest_tx','maximum_parameter':'fr_minislots'},
    ],
}

TECHNOLOGY_SEMANTICS['ethernet_ip'] = {
    'rate_model': {'type': 'APPLICATION_TRANSPORT_DEPENDENT', 'fields': []},
    'required_parameters': ['eip_mode','eip_transport','eip_transport_binding','eip_configuration_source'],
    'mechanisms': {'transport': ['TCP_EXPLICIT_ENCAPSULATION','UDP_CLASS_0_OR_1_IO','TCP_OR_UDP_DISCOVERY'],
                   'connection': ['FORWARD_OPEN_NEGOTIATED_DIRECTIONAL_RPI_AND_SIZE','CONNECTED_OR_UCMM'],
                   'integrity': ['SELECTED_LOWER_TRANSPORT','CPF_LENGTH_AND_SEQUENCE'],
                   'optional_services': ['CIP_SAFETY_SYNC_MOTION_SECURITY_REQUIRE_SEPARATE_PROFILES']},
    'parameter_constraints': [
        *[{'when': {'eip_mode':mode}, 'parameter':'eip_transport','allowed':transports}
          for mode,transports in (('IMPLICIT_IO',['UDP']),('CONNECTED_EXPLICIT',['TCP']),
                                   ('UNCONNECTED_EXPLICIT',['TCP']),('DISCOVERY',['TCP','UDP']))],
        *[{'when': {'eip_mode':mode}, 'parameter':'eip_class','allowed':classes}
          for mode,classes in (('IMPLICIT_IO',[0,1]),('CONNECTED_EXPLICIT',[3]),
                              ('UNCONNECTED_EXPLICIT',[]),('DISCOVERY',[]))],
        *[{'when': {'eip_mode':mode}, 'parameter':'eip_command','allowed':commands}
          for mode,commands in (('IMPLICIT_IO',[]),('CONNECTED_EXPLICIT',[112]),
                              ('UNCONNECTED_EXPLICIT',[111]),('DISCOVERY',[4,99,100]))],
        *[{'when': {'eip_mode':mode}, 'parameter':key,'allowed':[]}
          for mode in ('UNCONNECTED_EXPLICIT','DISCOVERY')
          for key in ('eip_o_to_t_rpi_us','eip_t_to_o_rpi_us','eip_timeout_code','eip_watchdog_us',
                      'eip_initial_watchdog_us','eip_inhibit_ms','eip_trigger','eip_forward_open',
                      'eip_o_to_t_size','eip_t_to_o_size','eip_established','eip_class_sequence')],
        *[{'when': {'eip_mode':mode}, 'parameter':key,'allowed':[]}
          for mode in ('CONNECTED_EXPLICIT','UNCONNECTED_EXPLICIT','DISCOVERY')
          for key in ('eip_run_idle_present','eip_run_idle_bytes','eip_io_sequence','eip_delivery')],
        *[{'when': {'eip_mode':'IMPLICIT_IO'}, 'parameter':key,'allowed':[]}
          for key in ('eip_encap_version','eip_encap_options','eip_encap_length','eip_session','eip_encap_status')],
        *[{'when': {'eip_mode':mode}, 'parameter':'eip_address_bytes','allowed':[length]}
          for mode,length in (('IMPLICIT_IO',8),('CONNECTED_EXPLICIT',4),('UNCONNECTED_EXPLICIT',0))],
        *[{'when': {'eip_class':klass}, 'parameter':'eip_class_sequence_bytes','allowed':[length]}
          for klass,length in ((0,0),(1,2),(3,2))],
        {'when': {'eip_mode':'UNCONNECTED_EXPLICIT'}, 'parameter':'eip_class_sequence_bytes','allowed':[0]},
        *[{'when': {'eip_run_idle_present':present}, 'parameter':'eip_run_idle_bytes','allowed':[length]}
          for present,length in ((False,0),(True,4))],
        *[{'when': {'eip_mode':mode}, 'parameter':'payload_bytes',
           'equal_expression':{'sum':['eip_application_bytes','eip_class_sequence_bytes',0]}}
          for mode in ('CONNECTED_EXPLICIT','UNCONNECTED_EXPLICIT')],
        {'when': {'eip_mode':'IMPLICIT_IO'}, 'parameter':'payload_bytes',
         'equal_expression':{'sum':['eip_application_bytes','eip_class_sequence_bytes','eip_run_idle_bytes']}},
        {'when': {'eip_cpf_layout':'TWO_ITEM'}, 'parameter':'eip_cpf_bytes',
         'equal_expression':{'sum':[10,'eip_address_bytes','payload_bytes']}},
        *[{'when': {'eip_mode':mode}, 'parameter':'eip_encap_length',
           'equal_expression':{'sum':[6,'eip_cpf_bytes']}} for mode in ('CONNECTED_EXPLICIT','UNCONNECTED_EXPLICIT')],
        *[{'when': {'eip_mode':mode}, 'parameter':'eip_packet_bytes',
           'equal_expression':{'sum':[24,'eip_encap_length']}}
          for mode in ('CONNECTED_EXPLICIT','UNCONNECTED_EXPLICIT','DISCOVERY')],
        {'when': {'eip_mode':'IMPLICIT_IO'}, 'parameter':'eip_packet_bytes','equal_parameter':'eip_cpf_bytes'},
        {'when': {'eip_delivery':'MULTICAST'}, 'parameter':'eip_port','allowed':[2222]},
        *[{'when': {'eip_forward_open':'STANDARD'}, 'parameter':key,'maximum':511}
          for key in ('eip_o_to_t_size','eip_t_to_o_size')],
        {'when': {'eip_watchdog_profile':'ACCEPTED_API'}, 'parameter':'eip_watchdog_us',
         'equal_expression':{'product':['eip_o_to_t_api_us',{'power':[2,{'sum':[2,'eip_timeout_code']}]}]}},
        {'when': {'eip_watchdog_profile':'OPENER_MILLISECOND'}, 'parameter':'eip_watchdog_us',
         'equal_expression':{'product':[1000,{'subtract':[0,{'ceiling':[{'product':[-0.001,'eip_o_to_t_rpi_us']}]}]},
                                      {'power':[2,{'sum':[2,'eip_timeout_code']}]}]}},
        {'when': {'eip_watchdog_profile':'OPENER_MILLISECOND'}, 'parameter':'eip_initial_watchdog_us',
         'equal_expression':{'maximum':[10000000,'eip_watchdog_us']}},
        *[{'when': {'eip_trigger':trigger,'eip_inhibit_profile':'OPENER_CYCLIC'}, 'parameter':'eip_inhibit_ms',
           'maximum_expression':{'product':[0.001,'eip_t_to_o_rpi_us']}}
          for trigger in ('CYCLIC',)],
        {'when': {'eip_mode':'CONNECTED_EXPLICIT'}, 'parameter':'eip_trigger','allowed':['APPLICATION']},
        *[{'when': {'eip_mode':mode}, 'parameter':key,'allowed':[]}
          for mode in ('UNCONNECTED_EXPLICIT','DISCOVERY')
          for key in ('eip_o_to_t_api_us','eip_t_to_o_api_us','eip_watchdog_profile','eip_inhibit_profile',
                      'eip_o_to_t_priority','eip_t_to_o_priority','eip_o_to_t_type','eip_t_to_o_type',
                      'eip_owner_mode','eip_owner_source','eip_o_to_t_id','eip_t_to_o_id',
                      'eip_size_mode','eip_size_direction','eip_size_definition')],
        *[{'when': {'eip_mode':'DISCOVERY'}, 'parameter':key,'allowed':[]}
          for key in ('eip_application_bytes','payload_bytes','eip_class_sequence_bytes','eip_cpf_layout',
                      'eip_address_bytes','eip_cpf_bytes','eip_connection_path')],
        {'when': {'eip_class':0}, 'parameter':'eip_class_sequence','allowed':[]},
        *[{'when': {'eip_mode':'IMPLICIT_IO','eip_size_direction':direction,'eip_size_mode':'FIXED','eip_size_definition':'OPENER_CPF_DATA'}, 'parameter':'payload_bytes',
           'equal_parameter':key} for direction,key in (('O_TO_T','eip_o_to_t_size'),('T_TO_O','eip_t_to_o_size'))],
        *[{'when': {'eip_mode':'IMPLICIT_IO','eip_size_direction':direction,'eip_size_mode':'VARIABLE','eip_size_definition':'OPENER_CPF_DATA'}, 'parameter':'payload_bytes',
           'maximum_parameter':key} for direction,key in (('O_TO_T','eip_o_to_t_size'),('T_TO_O','eip_t_to_o_size'))],
    ],
}

# These are the transport models implemented by the capacity service. A catalog
# entry, a default link rate, or a binding/generator is not capacity evidence.
CAPACITY_MODELS = {
    "can": ("CAN_CC_STUFFING_UPPER_BOUND", "CAN_SUFFICIENT_COMPLETION_BOUND_V1"),
    "can_fd": ("CAN_FD_PHASE_ESTIMATE", "CAN_SUFFICIENT_COMPLETION_BOUND_V1"),
    # Nominal serialization and periodic-table estimates are not actual LDF proof.
    "lin": ("LIN_NOMINAL_WITH_CHECKSUM", "LIN_PERIODIC_MASTER_TABLE_V1"),
    "ethernet": ("ETHERNET_WIRE_ESTIMATE", "ETHERNET_FULL_DUPLEX_FIFO_RESPONSE_BOUND_V1"),
    "i2c": ("I2C_CONFIRMED_TRANSACTION_BOUND_V1", "SERIAL_MASTER_BUSY_WINDOW_V1"),
    "spi": ("SPI_CONFIRMED_TRANSFER_BOUND_V1", "SERIAL_MASTER_BUSY_WINDOW_V1"),
}

# These physical endpoints carry a value on a conductor, not framed bus traffic.
# A missing timing bound remains a separate review item.
DIRECT_IO_TECHNOLOGIES = frozenset({"gpio", "pwm", "adc", "dac"})

# Source-backed proposals are deliberately distinct from confirmed port/device
# parameters and from executable capacity models. No proposal is a fallback rate.
REVIEW_RATE_PROPOSALS: dict[str, dict[str, Any]] = {
    'thread': {'kind':'FIXED_PHY_CONDITIONAL','status':'REVIEW_REQUIRED',
        'source':thread_rules.RADIO,'source_revision':thread_rules.SOURCES[thread_rules.RADIO],
        'conditional_defaults':[{'when':{'th_review_profile':'PUBLIC_BASELINE_2026','th_phy':'IEEE_802154_24GHZ_OQPSK'},'value':250000}],
        'minimum_standard_bitrate_bps':None,'note':'250kbps applies only to reviewed2.4GHz OQPSK; actual CSMA/poll/retry/path/fragment evidence remains independent.'},
    'profinet': {'kind':'STANDARD_BASELINE','default_bps':100000000,'status':'REVIEW_REQUIRED',
        'source':profinet_rules.PI,'source_revision':profinet_rules.SOURCES[profinet_rules.PI],
        'reason':'Conventional PROFINET100Mbps proposal; actual PHY/IOCR/RTclass/device interval/domain plan remain explicit.'},
    'profibus_pa': {'kind':'FIXED_STANDARD_BASELINE','default_bps':31250,'status':'REVIEW_REQUIRED',
        'source':profibus_pa_rules.PNO,'source_revision':profibus_pa_rules.SOURCES[profibus_pa_rules.PNO],
        'note':'Fixed MBP31.25kbit/s with synchronous Manchester octets and own CRC16; PA power/coupler/device profile/schedule separate from DP UART and FF LAS.'},
    'profibus_dp': {'kind':'LOWEST_STANDARD_BASELINE','default_bps':9600,'status':'REVIEW_REQUIRED',
        'source':profibus_dp_rules.ABB,'source_revision':profibus_dp_rules.SOURCES[profibus_dp_rules.ABB],
        'note':'Lowest listed DP nominal rate proposal; actual all-station rate agreement, selected bearer and configurator timing remain explicit.'},
    'powerlink': {'kind':'FIXED_STANDARD_BASELINE','default_bps':100000000,'status':'REVIEW_REQUIRED',
        'source':powerlink_rules.P,'source_revision':powerlink_rules.SOURCES[powerlink_rules.P],
        'note':'Classic DS301100BASE-X HALF duplex. Device/cycle/slot/grant evidence distinct nominal clock; no universal cycle default.'},
    'pcie': {'kind':'NEGOTIATED_GENERATION_LANES_CODEC','status':'REVIEW_REQUIRED',
        'source':pcie_rules.REG,'source_revision':pcie_rules.SOURCES[pcie_rules.REG],
        'values':{},'minimum_standard_bitrate_bps':None,
        'note':'Gen1/x1/128byte MPS and MRRS baseline proposals; actual generation/lane/mode/credits/PHY and traffic remain explicit. GT/s not application throughput.'},
    'opensafety': {'kind':'BLACK_CHANNEL_DEVICE_AND_SAFETY_CASE_DEPENDENT','status':'REVIEW_REQUIRED',
        'source':opensafety_rules.INTRO,'source_revision':opensafety_rules.SOURCES[opensafety_rules.INTRO],
        'values':{},'minimum_standard_bitrate_bps':None},
    'opc_ua_pubsub': {'kind':'APPLICATION_MAPPING_BEARER_DEPENDENT','status':'REVIEW_REQUIRED',
        'source':opc_ua_pubsub_rules.P14,'source_revision':opc_ua_pubsub_rules.SOURCES[opc_ua_pubsub_rules.P14],
        'values':{},'minimum_standard_bitrate_bps':None},
    'opc_ua': {'kind':'APPLICATION_PEER_TRANSPORT_DEPENDENT','status':'REVIEW_REQUIRED',
        'source':opc_ua_rules.P6,'source_revision':opc_ua_rules.SOURCES[opc_ua_rules.P6],
        'values':{},'minimum_standard_bitrate_bps':None},
    'one_wire': {'kind':'DEVICE_SLOT_TIMING_DEPENDENT','status':'REVIEW_REQUIRED',
        'source':one_wire_rules.STYLE,'source_revision':one_wire_rules.SOURCES[one_wire_rules.STYLE],
        'note':'Standard mode baseline, nominal16.3k label separate actual source-qualified slots/recovery/load. Deviceconversion and hostbridge clocks separate; no scalarCAN/I2C fallback or255byteframe.'},
    'ocpp': {'kind':'APPLICATION_TRANSPORT_DEPENDENT','status':'REVIEW_REQUIRED',
        'source':ocpp_rules.P21,'source_revision':ocpp_rules.SOURCES[ocpp_rules.P21],
        'note':'Actual version/binding/peer limits and bearer required. OCPP has no own bus clock, Ethernet10M or generic65535 payload default. Source-qualified WebSocket subprotocol/SOAP1.2 proposals are separate from actual device timeout, heartbeat and capacity.'},
    'obd2': {'kind':'VEHICLE_TRANSPORT_DEPENDENT','status':'REVIEW_REQUIRED',
        'source':obd2_rules.ELM,'source_revision':obd2_rules.SOURCES[obd2_rules.ELM],
        'note':'Selectedactualvehicleprotocol J1850PWM41600/VPW10400,Kline10400,CAN250k/500k. No universalCAN orEthernetbus. AdapterhostUART,init5baud,serviceedition andresponse timer areseparate.'},
    'nmea2000': {'kind':'FIXED_STANDARD_BASELINE','default_bps':250000,'status':'REVIEW_REQUIRED',
        'source':nmea2000_rules.WC,'source_revision':nmea2000_rules.SOURCES[nmea2000_rules.WC],
        'note':'NMEA2000 fixed250k CAN-CC. Actual PGN transport/name/addressclaim/physical/power/device timing required. Fast223 differsSINGLE8 andqualifiedISO1785. No NMEA0183 or genericJ1939 parameter fallback.'},
    'nmea0183': {'kind':'SERIAL_OR_REGISTERED_BINDING_DEPENDENT','status':'REVIEW_REQUIRED',
        'source':nmea0183_rules.P,'source_revision':nmea0183_rules.SOURCES[nmea0183_rules.P],
        'note':'Standard4800 andHS38400 proposals are serial-path-specific. DeviceUART and TCP/UDP/USB/I2C/SPI carriage need actualport/lowerlayer configuration; no NMEA2000CAN250k or Ethernet default. Untaggedsentence82 differs selecteddevice highprecision and fullstream traffic.'},
    'nfc': {'kind':'RF_PROTOCOL_ROLE_AND_FIRMWARE_DEPENDENT','status':'REVIEW_REQUIRED',
        'source':nfc_rules.ECMA,'source_revision':nfc_rules.SOURCES[nfc_rules.ECMA],
        'note':'No universal424k NFC default. Selected NFCIP1/A/B106k, F212k and PN7160V26.48k proposals differ; exact carrier/divisor and named rounded rates, RF versus hostI2C/SPI, firmware and role qualify every path. NCI255byte packet limit does not bound application bytes.'},
    'nb_iot': {'kind':'CATEGORY_GRANT_REPETITION_AND_NEGOTIATED_NAS_DEPENDENT','status':'REVIEW_REQUIRED',
        'source':nb_iot_rules.CAP,'source_revision':nb_iot_rules.SOURCES[nb_iot_rules.CAP],
        'note':'NB1/NB2 has no fixed250kbit/s baseline or universal1500byte application payload. Own channel200kHz versus180kHz resource grid, UL3.75/15kHz, category/optional-QAM and actualgrants/repetitions/PSM/eDRX/core path determine service; no LTE-M/CAN/Ethernet fallback.'},
    'mvb': {'kind':'FIXED_STANDARD_BASELINE','default_bps':1500000,'status':'REVIEW_REQUIRED',
        'source':mvb_rules.IMC,'source_revision':mvb_rules.SOURCES[mvb_rules.IMC],
        'note':'MVB gross1.5Mbit/s proposal, Manchester/frame/check/turnaround and actualadministrator scanlist separate. WiredEMD/ESD+ logging4.15 differs historicABBcontroller qualification. No nominalrate capacity or CAN/Ethernet fallback.'},
    'mqtt_sn': {'kind':'APPLICATION_TRANSPORT_DEPENDENT','status':'REVIEW_REQUIRED',
        'source':mqtt_sn_rules.P,'source_revision':mqtt_sn_rules.SOURCES[mqtt_sn_rules.P],
        'note':'MQTT-SN1.2 has no own wireless speed or universally usable65535byte payload. Explicit lower datagram/gateway/codec required; no protocol fragmentation. Qualified timer recommendations and message codes are proposals; actual client/address/topic maps and capacity remain evidence.'},
    'mqtt': {'kind':'APPLICATION_TRANSPORT_DEPENDENT','status':'REVIEW_REQUIRED',
        'source':mqtt_rules.P5,'source_revision':mqtt_rules.SOURCES[mqtt_rules.P5],
        'note':'MQTT has no own rate or universalEthernet stack. Ordered lossless bidirectional TCP/TLS/WebSocket/registered stream required. MQTT3.1.1 and5 session, per-hopQoS and optional absence defaults are separately scoped; no standard keepalive60seconds or fixedretry timer.'},
    'most': {'kind':'DEVICE_GENERATION_FRAME_CLOCK','status':'REVIEW_REQUIRED',
        'source':most_rules.P25,'source_revision':most_rules.SOURCES[most_rules.P25],
        'note':'Selected generation frame64/128/384 bytes times actual targetFs. Qualified MOST25 44.1kHz baseline yields22579200bit/s; 25/50/150 labels are rounded. Host MediaLB/I2C/USB clocks and message limits are separate; no unconditional installed rate.'},
    'modbus_tcp': {'kind':'APPLICATION_TRANSPORT_DEPENDENT','status':'REVIEW_REQUIRED',
        'source':mtcp_rules.TCP,'source_revision':mtcp_rules.SOURCES[mtcp_rules.TCP],
        'note':'MBAP has no own physical bitrate. Explicit actual TCP/IP/PHY and optional Modbus Security binding; port502/802 and directUnitFF are conditional proposals. No Ethernet10M fallback, serial gap/CRC or universal response timeout.'},
    'modbus_rtu': {'kind':'STANDARD_SERIAL_BASELINE','default_bps':19200,'status':'REVIEW_REQUIRED',
        'source':rtu_rules.SERIAL,'source_revision':rtu_rules.SOURCES[rtu_rules.SERIAL],
        'note':'V1.02 section3.2 and class table:19200 proposal if implemented, Basic fallback9600 if not. Actual supported/calibrated baud required; no universal1200..115200cap. RTU8data/11wirebits, CRC16 and own t1.5/t3.5 timers.'},
    'modbus_ascii': {'kind':'STANDARD_SERIAL_BASELINE','default_bps':19200,'status':'REVIEW_REQUIRED',
        'source':ascii_rules.SERIAL,'source_revision':ascii_rules.SOURCES[ascii_rules.SERIAL],
        'note':'V1.02 section3.2 requires19200 default; optional ASCII Regular class uses7data/10wirebits and EVEN parity. Baud supported/calibrated at actual endpoints; no global115200cap or capacity from proposal.'},
    'http': {'kind': 'APPLICATION_TRANSPORT_DEPENDENT', 'status': 'REVIEW_REQUIRED', 'source': 'https://www.rfc-editor.org/rfc/rfc9110.html', 'source_revision': 'RFC9110/9112/9113/9114 June2022; RFC9204 June2022; RFC9931 March2026 updates RFC9112 optimistic transition handling', 'note': 'No own physical rate or universal HTTP65535-byte message cap. Version-specific initialsettings proposals only until actual peer advertisements; actual explicit transport binding required.'},
    'hart': {'kind': 'STANDARD_BASELINE', 'default_bps': 1200, 'default_basis': 'WIRED_FSK_BASELINE', 'status': 'REVIEW_REQUIRED', 'source': 'https://www.ti.com/lit/an/slaaeh0/slaaeh0.pdf', 'source_revision': 'TI SLAAEH0 November2023 sections1.1-1.5 pp2-9; FieldComm character-time support article modified2016-11-11; full licensed HART specifications not read', 'note': 'Wired FSK baseline1200bit/s proposal. C8PSK requires explicit actual mode9600 and own codec/PHY evidence. No automatic HART-IP/WirelessHART transport or device identity.'},
    'gpio': {'kind': 'ACTUAL_DEVICE_NO_PACKET_RATE', 'status': 'REVIEW_REQUIRED', 'source': 'https://www.st.com.cn/resource/en/reference_manual/rm0312-stm8tl5xxx-microcontroller-family-stmicroelectronics.pdf', 'source_revision': 'ST RM0312 DocID022352 Rev3 October2013 chapter10 pp75-82; ST AN2710 Rev1 February2008 safe transition tables', 'note': 'GPIO has no standard packet speed/voltage/timing. Qualified STM8TL5 non-exception reset input/no-pull proposal is conditional; programmed outputs and real pin/peer evidence remain actual.'},
    'goose': {'kind': 'PHYSICAL_RATE_FROM_DECLARED_STACK', 'status': 'REVIEW_REQUIRED', 'source': 'https://raw.githubusercontent.com/mz-automation/libiec61850/v1.6/src/goose/goose_publisher.c', 'source_revision': 'libIEC61850 v1.6 publisher/server/config source and API1.6.0 read2026-10-01; IEC61850-8-1 Ed2.1 2020-02-21 publisher metadata, full licensed normative text not read', 'note': 'GOOSE raw L2 uses explicit canonical IEEE802.3 PHY modes; no independent universal100Mbit/s or event4ms. Library-qualified default PCP4 and configured retransmission fallbacks are conditional proposals, not actual SCL/device evidence.'},
    'generic_serial': {'kind': 'CONFIGURED_TRANSPORT_PROFILE', 'status': 'REVIEW_REQUIRED', 'source': 'https://ww1.microchip.com/downloads/en/Appnotes/TB3216-Getting-Started-with-USART-90003216B.pdf', 'source_revision': 'Microchip TB3216 DS90003216B 2019 sections2/3/6; Arduino official Serial.begin reference master read2026-10-01; AVR USART frame-format documentation7.1.1 section15.5', 'note': 'Generic Serial has no universal physical rate. Explicit async TB3216 tutorial profile has conditional9600/8N1 proposals; sync and USB CDC require their own actual bound implementation.'},
    'generic_can': {'kind': 'CONFIGURED_TRANSPORT_PROFILE', 'status': 'REVIEW_REQUIRED', 'source': 'https://www.can-cia.org/can-knowledge/can-data-link-layer-generations', 'source_revision': 'CiA primary CAN generation, CAN FD and CAN XL descriptions read2026-10-01; ISO11898-1:2024 referenced, full licensed text not read', 'note': 'Generic CAN is an NIS abstraction. Actual CC/FD/XL transmitted family and lower link required; no own universal500kbit/s or8-byte proposal.'},
    'fsoe': {'kind': 'APPLICATION_TRANSPORT_DEPENDENT', 'status': 'REVIEW_REQUIRED', 'source': 'https://www.beckhoff.com/media/downloads/information-media/pc-control/pcc_0107_e.pdf', 'source_revision': 'Beckhoff PC-Control01/2007 pages24-26; HMS public FSoE PDU/state tutorial July23/24 2026 interpreted for base ETG5100v1.2.0, not licensed full text', 'note': 'FSoE has no own bitrate, universal safe-data maximum or universal watchdog default. Base one-byte/even-block container requires configured directional data/mapping, CRC chain and endpoint watchdog. Black channel and optional enhancements need their own profiles; no automatic SIL/PL acceptance.'},
    'foundation_fieldbus_h1': {'kind': 'FIXED_NOMINAL_RATE', 'default_bps': 31250, 'status': 'REVIEW_REQUIRED', 'source': 'https://www.yokogawa.com/pdf/provide/E/GW/TI/0000001497/0/TI38K02A01-01E.pdf', 'source_revision': 'Yokogawa TI38K02A01-01E third edition April2012 sections2.1.2/2.2/2.3/2.4/2.5/3.5.2; manufacturer tutorial, not full normative specification', 'note': 'Fixed31.25kbit/s H1 baseline. Actual FMS data, DLSDU, complete physical telegram and LAS transaction are distinct; native device/CFF/physical/schedule evidence remains unknown. No100M HSE or CAN defaults.'},
    'flexray': {'kind':'DISCRETE_STANDARD_RATES','default_bps':2500000,'status':'REVIEW_REQUIRED',
        'source':'https://www.nxp.com/docs/en/data-sheet/MFR4310RM.pdf',
        'source_revision':'MFR4310RM Rev2 May2008 section3.5.1/Table3-110; NXP FlexRay V3 webinar2010; Vector SIL Kit5.0.7 native API representation',
        'note':'Lowest reviewed standard rate2.5Mbit/s proposal, standard modes2.5/5/10M;8M is explicitly NXP-specific. Cluster/node/slot/clock/topology values are configured, not universal defaults. No aggregate two-channel capacity or valid schedule is inferred.'},
    'ethernet_ip': {'kind':'APPLICATION_TRANSPORT_DEPENDENT','status':'REVIEW_REQUIRED',
        'source':'https://www.odva.org/publication_download/ethernet-ip-technology-overview/',
        'source_revision':'ODVA PUB00138; PUB00095 Version9 PR002; Volume1 v3.40 / Volume2 v1.36 publisher April2026. Public OpENer implementation accessed2026-10-01; licensed specification not read.',
        'note':'EtherNet/IP has no own physical bitrate or universal1400-byte I/O limit. TCP explicit/UDP implicit/discovery require separate actual bindings. RPI100ms/Class1 or250ms/Class3 and multiplier4 are qualified ODVA interoperability test proposals, not universal installed-device defaults.'},
    'ethernet': {'kind':'BASELINE_PROFILE_RATE','default_bps':10000000,'status':'REVIEW_REQUIRED',
                 'source':'https://ww1.microchip.com/downloads/en/DeviceDoc/00002268B.pdf',
                 'source_revision':'LAN9116 DS00002268B 2017 sections1.2/3.2/5.4; qualified10BASE-T baseline. TI DP83867 SNLS484J June2026; Broadcom BCM84918 rates',
                 'note':'10BASE-T is the lowest reviewed baseline mode, not a minimum physical clock or actual negotiated speed. MAC client1500B differs from IP MTU, frames and upper-layer payload. PHY/duplex/flow-control/device evidence remains required; no TCP/IP overhead is assumed.'},
    'ethercat': {'kind':'FIXED_NOMINAL_RATE','default_bps':100000000,'status':'REVIEW_REQUIRED',
                'source':'https://download.beckhoff.com/download/document/io/ethercat-development-products/ethercat_esc_datasheet_sec1_technology_v2.5.pdf',
                'source_revision':'BeckhoffESCSectionI Technology2.5 2025-07-28 chapters2/5/8/9/10/13',
                'note':'Registered classic EtherCAT100Mbit/s full-duplex, not EtherCATG/G10. Datagram data, multiple-datagram frame and UDP encapsulation have distinct limits; ESI/physical/DC/watchdog/state evidence stays unknown.'},
    'etb': {'kind':'BASELINE_PROFILE_RATE','default_bps':100000000,'status':'REVIEW_REQUIRED',
            'source':'https://docs.westermo.com/weos/weos-5/HowTo/iec61375-port-setting-backbone-ports.html',
            'source_revision':'WeOS5.29 ETBN port settings 100Mb/Gbit sections, accessed2026-10-01; IEC61375-2-5:2014 publisher edition1.0',
            'note':'100Mb full-duplex is a source-qualified baseline proposal. Gbit ports require their own PHY and clock roles; redundant TTDP links do not double capacity. Actual inauguration, bindings, queues and edition remain unverified.'},
    'doip': {'kind': 'APPLICATION_TRANSPORT_DEPENDENT', 'status': 'REVIEW_REQUIRED',
             'source': 'https://www.autosar.org/fileadmin/standards/R25-11/CP/AUTOSAR_CP_SWS_DiagnosticOverIP.pdf',
             'source_revision': 'AUTOSAR CP R25-11 Document418 chapters7.3/10.2, ISO13400-2:2019 representation; primary implementation constants read2026-10-01',
             'note': 'DoIP has no own Ethernet bitrate or universal4096B message limit. Eight-byte header/32-bit payload length, UDP discovery and TCP/TLS diagnostics require matched edition, actual peer and explicit lower profile.'},
    'dnp3': {'kind': 'APPLICATION_TRANSPORT_DEPENDENT', 'status': 'REVIEW_REQUIRED',
             'source': 'https://www.dnp.org/Portals/0/AboutUs/DNP3%20Primer%20Rev%20A.pdf',
             'source_revision': 'DNP Users Group Primer RevisionA 20March2005 pages5..7; StepFunctionDNP3 1.6.0 June2024 implementation is separate',
             'note': 'DNP3 has no own physical bitrate. Link frame292/octet-data250/transport-data249 and peer buffer-limited application fragments differ;2048 is a typical fragment proposal, not a complete-message limit. Actual transport/edition/device evidence required.'},
    'devicenet': {'kind': 'DISCRETE_STANDARD_RATES', 'default_bps': 125000, 'status': 'REVIEW_REQUIRED',
                 'source': 'https://literature.rockwellautomation.com/idc/groups/literature/documents/um/dnet-um004_-en-p.pdf',
                 'source_revision': 'DNET-UM004E-EN-P March2022 page19; ODVA PUB00026R4 March2016; PUB00027R1 cable manual2003',
                 'note': 'DeviceNet registered rates125/250/500kbit/s; default125kbit/s. Matching nodes/selected cable/drop lengths and actual connection evidence remain explicit.'},
    'dds': {'kind': 'APPLICATION_TRANSPORT_DEPENDENT', 'status': 'REVIEW_REQUIRED',
            'source': 'https://www.omg.org/spec/DDS/1.4/PDF',
            'source_revision': 'OMG DDS1.4 formal/2015-04-10, QoS table2.2.3 and sections2.2.3.1..22; normative20140501IDL',
            'note': 'DDS data-centric middleware has no own link rate or universalUDP/IPv4/Ethernet payload bound. Actual entity/implementation/type/transport and requested-offered compatibility remain explicit.'},
    'dali': {'kind': 'FIXED_NOMINAL_RATE', 'default_bps': 1200, 'status': 'REVIEW_REQUIRED',
             'source': 'https://onlinedocs.microchip.com/oxy/GUID-084B347F-65C0-4C09-9EA7-6D2B7587F5D3-en-US-1/GUID-6AC92B0B-C2A1-4B0C-AE27-03712EEA75E5.html',
             'source_revision': 'Microchip TB3201 sections2/3.2; DALI Alliance Quick Start v1.1 April2023; Technical Note1.3 November2017',
             'note': 'Nominal wired DALI information rate1200 bit/s. Manchester half-bit sampling2400 is not data rate; tolerance is not a selectable lower mode. Actual topology, power and matched-edition transaction/arbitration evidence remain separate.'},
    'dac': {'kind': 'DIRECT_IO_DEVICE_DEPENDENT', 'status': 'REVIEW_REQUIRED',
            'source': 'https://www.analog.com/en/resources/app-notes/an-1444.html',
            'source_revision': 'Analog Devices AN-1444, actual device/load/code-step/tolerance dependence; accessed2026-10-01',
            'note': 'No universal DAC bus frequency or packet size. Digital access/update timing and analogue settling are separate actual device facts; SPI/I2C programming uses its own explicit transport profile.'},
    'custom_udp': {'kind': 'NO_OWN_PHYSICAL_RATE', 'status': 'REVIEW_REQUIRED',
                   'source': 'https://www.rfc-editor.org/rfc/rfc8085.html',
                   'source_revision': 'RFC768 August1980; RFC791 September1981; RFC8200 July2017; RFC2675 August1999; RFC8085 March2017',
                   'note': 'Actual UDP/IP/link binding and custom application contract required. No Ethernet rate, universal65507 payload for IPv6, implicit fragmentation or UDP application acknowledgement.'},
    'custom_text': {'kind': 'NO_OWN_PHYSICAL_RATE', 'status': 'REVIEW_REQUIRED',
                    'source': 'https://www.rfc-editor.org/rfc/rfc3629.html',
                    'source_revision': 'RFC3629 November2003 sections3/4/6; Unicode UTF FAQ accessed2026-10-01',
                    'note': 'No universal custom-text charset/framing/physical rate/message limit. Actual protocol selects encoding; Unicode scalar, code-unit and encoded byte counts are distinct.'},
    'custom_tcp': {'kind': 'NO_OWN_PHYSICAL_RATE', 'status': 'REVIEW_REQUIRED',
                   'source': 'https://www.rfc-editor.org/rfc/rfc9293.html',
                   'source_revision': 'RFC9293 August2022 sections2.2/3.7/3.8; application specification remains explicit',
                   'note': 'TCP byte stream supplies no application framing or universal full-message size. Explicit actual TCP/IP/link binding; no Ethernet10M default or application65535 cap.'},
    'custom_protocol': {'kind': 'NO_UNIVERSAL_STANDARD', 'status': 'REVIEW_REQUIRED',
                        'source': 'docs/COMMUNICATION_DESIGN_CONTRACT.md',
                        'source_revision': 'Explicit application contracts and independent transport evidence, accessed 2026-10-01',
                        'note': 'No universal custom-protocol bitrate, message length, addressing, acknowledgement or retry defaults. Require the actual specification and selected transport.'},
    'custom_binary': {'kind': 'NO_UNIVERSAL_STANDARD', 'status': 'REVIEW_REQUIRED',
                      'source': 'docs/COMMUNICATION_DESIGN_CONTRACT.md',
                      'source_revision': 'Explicit encoding and separate transport/capacity evidence, accessed 2026-10-01',
                      'note': 'User-defined binary protocol has no universal bitrate, message length, byte order or checksum. Actual specification and lower transport binding are required.'},
    'coap':{'kind':'NO_OWN_PHYSICAL_RATE','status':'REVIEW_REQUIRED',
            'source':'https://www.rfc-editor.org/rfc/rfc7252.html',
            'source_revision':'RFC7252 June2014 /7959 Aug2016 /8323 Feb2018 /8974 Jan2021',
            'note':'No CoAP bitrate. Actual UDP/DTLS, TCP/TLS orWebSocket andIP/link bindings mustbe explicit; applicationbody/message/block lengths areseparate andno1152universalpayloadcap.'},
    'cip_safety':{'kind':'NO_OWN_PHYSICAL_RATE','status':'REVIEW_REQUIRED',
                  'source':'https://www.odva.org/technology-standards/distinct-cip-services/cip-safety/',
                  'source_revision':'ODVA Volume5 v2.28 catalog April2026; publicprotocoloverview /2022changes',
                  'note':'Safety application protocol over explicit EtherNet/IP, DeviceNet or SercosIII. Each underlying network needs its own TechnologyProfile parameters and evidence; no CAN/Ethernet rate fallback.'},
    'cc_link_ie':{'kind':'VARIANT_DEPENDENT','unit':'bit/s','status':'REVIEW_REQUIRED',
                  'source':'https://www.cc-link.org/en/networktechnology/spec.html',
                  'source_revision':'CLPA separateController/Field/FieldBasic/TSN tables accessed2026-10-01',
                  'note':'Select the actual variant before proposing a link speed. Controller/Field1G, Basic100M mandatory/1G optional, TSN100M/1G. No universal1G or10M Ethernet fallback.'},
    'cc_link':{'kind':'STANDARD_BASELINE','unit':'bit/s','status':'REVIEW_REQUIRED','default_bps':156000,
               'default_basis':'LOWEST_DEFINED_CCLINK_MODE','source':'https://www.cc-link.org/en/networktechnology/spec.html',
               'source_revision':'CLPA CC-Link V1.10/V2 tables accessed2026-10-01',
               'note':'156k is the lowest listed mode proposal. Actual hardware, common station speed and dedicated cable version remain unconfirmed.'},
    'ccp':{'kind':'DEVICE_DEPENDENT','unit':'bit/s','status':'REVIEW_REQUIRED',
           'source':'https://download.ni.com/support/manuals/371601f.pdf',
           'source_revision':'ASAM MCD-1 CCP2.1 1999-02-18; NI371601F September2008 appendixA /4-5/4-6',
           'note':'CCP uses actual CAN CC rate from device/A2L configuration. No universal500k default, no CANopen predefined mode list and no XCP on CAN FD transport.'},
    'canopen':{'kind':'STANDARD_BASELINE','unit':'bit/s','status':'REVIEW_REQUIRED','default_bps':10000,
               'default_basis':'LOWEST_DEFINED_CANOPEN_CC_MODE',
               'source':'https://www.can-cia.org/can-knowledge/canopen-lower-layers',
               'source_revision':'CiA CANopen CC bit timing table accessed2026-10-01',
               'note':'Each device supports at least one defined rate, not necessarily all.10k is lowest listed proposal, not confirmed hardware support. CANopen FD/CiA1301 requires a separate profile.'},
    'can_xl':{'kind':'DEVICE_DEPENDENT','unit':'bit/s','status':'REVIEW_REQUIRED',
              'source':'https://www.can-cia.org/can-knowledge/can-xl',
              'source_revision':'CiA CAN XL / ISO11898-1:2024 accessed2026-10-01; Bosch X_CAN3.9 2024-02-28',
              'note':'No universal10M default. Arbitration and XL data phase are independently configured.20M is an X_CAN3.9 capability, not a universal PHY speed limit.'},
    'can_fd':{'kind':'DEVICE_DEPENDENT','unit':'bit/s','status':'REVIEW_REQUIRED',
              'source':'https://www.can-cia.org/can-knowledge/can-fd-the-basic-idea',
              'source_revision':'CiA CAN FD basic idea / PMA options accessed2026-10-01; ISO11898-1:2015 / 2024',
              'note':'No universal nominal/data-rate defaults. Nominal <=1M; actual data-rate ceiling depends on transceiver, controller and topology. BRS false uses nominal timing throughout the frame.'},
    'can_aerospace': {'kind':'DEVICE_DEPENDENT','unit':'bit/s','status':'REVIEW_REQUIRED',
                     'source':'https://files.stockflightsystems.com/_5_CANaerospace/canas_17.pdf',
                     'source_revision':'CANaerospace1.7 2006-01-12 sections1 / 4.11 / 6.1',
                     'note':'Any CAN data rate is permitted. 1 Mbit/s and 12.5-ms minor frame in section6 are illustrative, not mandatory defaults.'},
    'can': {'kind': 'DEVICE_DEPENDENT', 'unit': 'bit/s', 'status': 'REVIEW_REQUIRED',
            'source': 'https://www.zlg.cn/data/upload/software/Can/CANag.pdf',
            'source_revision': 'Bosch CAN Specification 2.0 September 1991 Part B sections 2 / 10; CiA CAN HS transmission accessed 2026-10-01',
            'note': 'CAN CC has no universal standard bitrate or minimum mode. Actual uniform network rate and controller/PHY timing require evidence; CANopen rate tables are not generic CAN defaults.'},
    'bluetooth_le': {'kind':'STANDARD_BASELINE','unit':'bit/s','default_bps':1000000,
                     'default_basis':'LOWEST_MANDATORY_PHY',
                     'source':'https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-62/out/en/low-energy-controller/radio-physical-layer-specification.html',
                     'source_revision':'Bluetooth Core 6.2 Vol 6 Part A section 2, mandatory LE 1M; accessed 2026-10-01',
                     'status':'REVIEW_REQUIRED','note':'Optional PHY/coding and actual direction must be confirmed. Coded payload rate is not a uniform whole-packet rate.'},
    'bacnet_mstp': {'kind': 'STANDARD_BASELINE', 'unit': 'bit/s', 'default_bps': 9600,
                    'default_basis': 'LOWEST_MANDATORY_MODE',
                    'source': 'https://infosys.beckhoff.com/content/1033/el6861/4104700811.html',
                    'source_revision': 'Beckhoff MS/TP Supplement, 2021, Interface settings; mandatory 9600 and 38400',
                    'status': 'REVIEW_REQUIRED',
                    'note': 'Mandatory lowest baseline 9600 baud, not the historical optional 115200 or vendor default 38400. All stations must use the same configured speed.'},
    'avb': {'kind': 'BASELINE_LINK_MODE', 'unit': 'bit/s', 'default_bps': 100_000_000,
            'default_basis': 'LOWEST_PROFILE_MODE',
            'source': 'https://ieee802.org/3/cg/email/msg00694.html',
            'source_revision': 'IEEE 802.3 working-group correspondence 2018-09-10 on 802.1BA AVB Ethernet profile',
            'status': 'REVIEW_REQUIRED',
            'note': 'Ethernet AVB baseline excludes 10 Mbit/s and half duplex. A link mode proposal does not prove MSRP reservation, gPTP or CBS scheduling.'},
    'arinc429': {'kind': 'NOMINAL_MODES', 'unit': 'bit/s', 'default_bps': 12_500,
                 'default_basis': 'LOWEST_NOMINAL_MODE',
                 'source': 'https://www.aim-online.com/wp-content/uploads/2019/07/aim-tutorial-oview429-190712-u.pdf',
                 'source_revision': 'AIM ARINC 429 Tutorial v2.2, July 2019, pages 8-11',
                 'status': 'REVIEW_REQUIRED',
                 'note': 'Proposed low-speed nominal mode, not tolerance minimum or an installed-link confirmation. One mode per simplex channel.'},
    'afdx': {'kind': 'LITERATURE_DEFAULT', 'unit': 'bit/s', 'default_bps': 100_000_000,
             'source': 'https://ww1.microchip.com/downloads/aemdocuments/documents/fpga/ApplicationNotes/ApplicationNotes/afdx_solutions_an.pdf',
             'source_revision': 'Actel Application Note AC221, March 2005, page 3, Performance',
             'status': 'REVIEW_REQUIRED',
             'note': 'Documented AFDX default 100 Mbit/s; 10 Mbit/s is another documented mode. Confirm installed end systems and VL configuration.'},
    "5g": {
        "kind": "CONFIGURATION_DEPENDENT", "unit": "bit/s",
        "source": "https://www.etsi.org/deliver/etsi_ts/138300_138399/138306/16.13.00_60/ts_138306v161300p.pdf",
        "source_revision": "3GPP TS 38.306 v16.13.0, section 4.1.2",
        "status": "REVIEW_REQUIRED",
        "note": "No universal 5G bitrate: band, bandwidth, numerology, MIMO, modulation, carriers and direction determine the rate. The historical 10 Gbit/s value is not a standard default.",
    },
    "i2c": {
        "kind": "STANDARD_MODE_LIMITS", "unit": "bit/s",
        "options": [{"mode": "Standard", "maximum": 100_000},
                    {"mode": "Fast", "maximum": 400_000},
                    {"mode": "Fast Plus", "maximum": 1_000_000},
                    {"mode": "High Speed", "maximum": 3_400_000},
                    {"mode": "Ultra Fast", "maximum": 5_000_000}],
        "source": "https://www.nxp.com/docs/en/user-guide/UM10204.pdf",
        "source_revision": "UM10204 Rev. 7.0 (2021-10-01)",
        "status": "REVIEW_REQUIRED",
        "note": "Mode, controller, target, clock stretching and physical bus must be confirmed.",
    },
}


REVIEW_RATE_PROPOSALS['generic_ethernet'] = deepcopy(REVIEW_RATE_PROPOSALS['ethernet'])
REVIEW_RATE_PROPOSALS['generic_ethernet']['note'] = (
    'Explicit IEEE802.3 Generic Ethernet entry uses the reviewed 10BASE-T/10M baseline '
    'proposal. Actual PHY, duplex, MAC-client layout, peer, flow and path configuration '
    'remain required; no independent 1G default or implicit TCP/IP header.')

REVIEW_RATE_PROPOSALS['mil_std_1553'] = {
    'kind':'VARIANT_DEPENDENT','status':'REVIEW_REQUIRED','source':mil1553_rules.CORE,
    'source_revision':mil1553_rules.SOURCES[mil1553_rules.CORE],
    'note':'MIL-STD-1553C nominal1Mbit/s is a conditional standard proposal; actual revision, observed clock, terminal options, message schedule and electrical qualification remain required.'}

LOCAL_EVIDENCE_FIELDS = {
    "I2C": (("master_node_id", "Bestätigter I2C-Master"), ("slave_address", "Slave-Adresse des Geräts"),
            ("address_bits", "I2C-Adressbreite (7/10 Bit)"),
            ("i2c_mode", "I2C-Modus (STANDARD/FAST/FAST_PLUS/HIGH_SPEED)"),
            ("transfer_direction", "Übertragungsrichtung (READ/WRITE/BIDIRECTIONAL)"),
            ("start_stop_bound_us", "Start-/Stop-Grenze je Transaktion (µs)"),
            ("clock_stretch_limit_us", "Gesamte Clock-Stretch-Grenze je Transaktion (µs)"),
            ("transfer_bits_bound", "Transferumfang einschließlich Adresse und ACK (Bit)"),
            ("multi_master", "Mehrere Master (true/false)"),
            ("arbitration_bound_us", "Arbitrationsgrenze bei mehreren Mastern (µs)"),
            ("bitrate_bps", "Bestätigter I2C-Takt (bit/s)")),
    "SPI": (("master_node_id", "Bestätigter SPI-Master"), ("chip_select", "Chip-Select je Gerät"),
            ("word_length_bits", "Wortlänge (Bit)"), ("duplex_mode", "Duplexmodus"),
            ("cpol", "CPOL (0/1)"), ("cpha", "CPHA (0/1)"),
            ("cs_setup_bound_us", "CS-Setup-Grenze (µs)"),
            ("inter_transfer_gap_us", "Transferabstandsgrenze (µs)"),
            ("transfer_bits_bound", "Transfergrenze in Taktbits"),
            ("bitrate_bps", "Bestätigter SPI-Takt (bit/s)")),
    "GPIO": (("sample_bound_ms", "Abtastgrenze (ms)"), ("debounce_bound_ms", "Entprellgrenze (ms)"),
             ("edge_detection_bound_ms", "Flankenerkennungsgrenze (ms)")),
    "ADC": (("sample_bound_ms", "ADC-Abtastgrenze (ms)"),
            ("conversion_bound_ms", "ADC-Wandlungsgrenze (ms)")),
    "DAC": (("update_bound_ms", "DAC-Aktualisierungsgrenze (ms)"),
            ("settling_bound_ms", "DAC-Einschwinggrenze (ms)")),
}


def _local_timing_schema(technology_id):
    if technology_id == 'i2c':
        return i2c_rules.local_fields()
    if technology_id == 'spi':
        return spi_rules.local_fields()
    numeric = {'address_bits', 'start_stop_bound_us', 'clock_stretch_limit_us',
               'transfer_bits_bound', 'arbitration_bound_us', 'bitrate_bps', 'word_length_bits',
               'cpol', 'cpha', 'cs_setup_bound_us', 'inter_transfer_gap_us', 'pwm_frequency_hz',
               'update_bound_ms', 'capture_bound_ms', 'sample_bound_ms', 'debounce_bound_ms',
               'edge_detection_bound_ms', 'conversion_bound_ms', 'settling_bound_ms'}
    fields = [{'key': key, 'label': label, 'numeric': key in numeric,
             'boolean': key == 'multi_master', 'optional': key == 'arbitration_bound_us',
             **({'default': 'STANDARD'} if key == 'i2c_mode' else {})}
            for key, label in LOCAL_EVIDENCE_FIELDS.get(technology_id.upper(), ())]
    if technology_id == 'gpio':
        fields.append({'key':'update_bound_ms','label':'Output-update bound (ms)','numeric':True,'boolean':False,'optional':True})
        conditions={'sample_bound_ms':{'gpio_direction':'DIGITAL_INPUT','gpio_input_mode':'POLLED'},
                    'debounce_bound_ms':{'gpio_debounce_enabled':True},
                    'edge_detection_bound_ms':{'gpio_direction':'DIGITAL_INPUT','gpio_input_mode':'INTERRUPT'},
                    'update_bound_ms':{'gpio_direction':'DIGITAL_OUTPUT'}}
        source=REVIEW_RATE_PROPOSALS['gpio']
        for item in fields:
            item.update(unit='ms',minimum=0,optional=True,required_when=conditions[item['key']],
                        parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',scope='device',
                        source=source['source'],source_revision=source['source_revision'],
                        description='Actual matching pin/task/interrupt/debounce/update timing bound, not a bus rate or generic period. Confirm only with actual datasheet/measurement source.')
    if technology_id == 'adc':
        for item in fields:
            item.update(unit='ms', minimum=0, parameter_origin='DEVICE_CONFIGURATION',
                        default_status='UNKNOWN', scope='device',
                        source='https://developerhelp.microchip.com/xwiki/bin/view/products/data-converters/adc-specs/acquisition-time/',
                        source_revision='Microchip ADC Acquisition Time, 2023-11-09',
                        description='Datenblattgrenze des konkreten ADC; Erfassung/Acquisition und Wandlung sind getrennte Zeiten, keine Busfrequenz.')
    if technology_id == 'dac':
        source = REVIEW_RATE_PROPOSALS['dac']
        for item in fields:
            item.update(unit='ms', minimum=0, parameter_origin='DEVICE_CONFIGURATION',
                        default_status='UNKNOWN', scope='device', source=source['source'],
                        source_revision=source['source_revision'],
                        description='Actual DAC update or settling bound from the matching datasheet/measurement, including code-step/load/tolerance conditions. Digital interface speed does not prove settled analogue output.')
    return fields


MODEL_TYPES: tuple[dict[str, Any], ...] = (
    {"id": "generic_networking", "label": "Generische Kommunikationsarchitektur", "device_types": ["HardwareNode", "Gateway", "Sensor", "Actuator", "Switch", "Router"], "recommended_technologies": ["ethernet", "ip", "udp", "tcp", "generic_serial", "generic_can", "generic_ethernet", "custom_udp", "custom_tcp", "custom_binary", "custom_text", "custom_protocol"]},
    {"id": "automotive", "label": "Automotive / Vehicle", "device_types": ["ECU", "Gateway", "DomainController", "ZoneController", "Sensor", "Actuator"], "recommended_technologies": ["can", "can_fd", "can_xl", "lin", "flexray", "automotive_ethernet", "canopen", "j1939", "isobus", "someip", "doip", "uds", "xcp", "obd2", "tsn"]},
    {"id": "industrial_automation", "label": "Industrial Automation / SPS", "device_types": ["PLC", "RemoteIO", "IndustrialPC", "Sensor", "Actuator", "Gateway"], "recommended_technologies": ["profinet", "profibus_dp", "ethercat", "ethernet_ip", "modbus_tcp", "modbus_rtu", "canopen", "opc_ua", "opc_ua_pubsub", "io_link", "generic_serial"]},
    {"id": "robotics_ros", "label": "Robotics / ROS 2", "device_types": ["RobotController", "IndustrialPC", "Sensor", "Actuator", "Gateway"], "recommended_technologies": ["ros2", "dds", "ethercat", "profinet", "ethernet_ip", "canopen", "modbus_tcp", "modbus_rtu", "usb", "ethernet"]},
    {"id": "aerospace", "label": "Aerospace / Avionics", "device_types": ["FlightComputer", "RemoteTerminal", "Sensor", "Actuator", "Gateway"]},
    {"id": "rail", "label": "Rail", "device_types": ["TrainControlUnit", "VehicleControlUnit", "Gateway", "Sensor", "Actuator", "HMI"], "recommended_technologies": ["mvb", "wtb", "etb", "trdp", "canopen", "profinet", "ethernet"]},
    {"id": "marine", "label": "Marine / Off-Highway", "device_types": ["MarineController", "Gateway", "Sensor", "Actuator", "Display"], "recommended_technologies": ["nmea0183", "nmea2000", "iec61162", "j1939", "can", "can_fd", "modbus_tcp", "modbus_rtu", "ethernet"]},
    {"id": "building_automation", "label": "Building Automation", "device_types": ["BuildingController", "Gateway", "Sensor", "Actuator", "Meter"]},
    {"id": "energy", "label": "Energy / Smart Grid", "device_types": ["EnergyController", "IED", "Gateway", "Meter", "Sensor", "Actuator"]},
    {"id": "process_industry", "label": "Process Industry", "device_types": ["PLC", "DCSController", "RemoteIO", "FieldDevice", "Sensor", "Actuator"], "recommended_technologies": ["hart", "wirelesshart", "foundation_fieldbus_h1", "profibus_pa", "modbus_tcp", "modbus_rtu", "ethernet_ip", "profinet", "opc_ua"]},
    {"id": "embedded_systems", "label": "Embedded / Electronics", "device_types": ["EmbeddedController", "Sensor", "Actuator", "Peripheral", "Gateway"]},
    {"id": "iot_wireless", "label": "IoT / Edge / Wireless", "device_types": ["EdgeComputer", "IoTDevice", "Gateway", "Sensor", "Actuator"]},
    {"id": "custom", "label": "Custom / Proprietary", "device_types": ["CustomDevice", "Gateway", "Sensor", "Actuator"]},
)


PHASE_1 = {
    "can", "can_fd", "lin", "ethernet", "someip", "modbus_rtu", "modbus_tcp",
    "profinet", "ethercat", "canopen", "dds", "ros2", "ip", "udp", "tcp",
}
PHASE_2 = {
    "profibus_dp", "profibus_pa", "ethernet_ip", "io_link", "opc_ua", "opc_ua_pubsub",
    "j1939", "isobus", "arinc429", "afdx", "mil_std_1553", "trdp", "bacnet_ip",
    "bacnet_mstp", "knx_ip", "knx_tp", "iec61850", "goose", "sampled_values",
}
PHASE_3 = {
    "flexray", "can_xl", "cc_link", "cc_link_ie", "sercos_iii", "powerlink", "hart",
    "foundation_fieldbus_h1", "mvb", "wtb", "nmea0183", "nmea2000", "dali", "m_bus",
    "wireless_m_bus", "dnp3", "iec60870_5_101", "iec60870_5_104", "spacewire",
}
LEGACY = {"most", "ccp", "interbus", "lonworks", "modbus_ascii"}
EXPERIMENTAL = {
    "can_xl", "i3c", "io_link_wireless", "bacnet_sc", "matter", "thread", "uwb", "5g",
    "mqtt", "mqtt_sn", "coap", "http", "websocket", "amqp", "wifi", "bluetooth_le", "zigbee",
    "lorawan", "lte_m", "nb_iot", "nfc", "rfid", "generic_serial", "generic_can",
    "generic_ethernet", "custom_udp", "custom_tcp", "custom_binary", "custom_text", "custom_protocol",
}
PARTIAL_BASELINES = {
    "i2c", "spi", "uart", "rs232", "rs422", "rs485", "one_wire", "usb", "pcie",
    "mipi_csi2", "mipi_dsi", "lvds", "gpio", "pwm", "adc", "dac",
}


def _status(technology_id: str) -> str:
    if technology_id in PHASE_1:
        return "IMPLEMENTED"
    if technology_id in LEGACY:
        return "LEGACY"
    if technology_id in EXPERIMENTAL:
        return "EXPERIMENTAL"
    if technology_id in PHASE_2 or technology_id in PHASE_3 or technology_id in PARTIAL_BASELINES:
        return "PARTIAL"
    return "PLANNED"


def _capabilities(*tokens: str) -> dict[str, bool]:
    selected = set(tokens)
    return {
        "supports_signals": "no_signals" not in selected,
        "supports_data_objects": "objects" in selected,
        "supports_streams": "streams" in selected,
        "supports_multicast": "multicast" in selected,
        "supports_publish_subscribe": "pubsub" in selected,
        "supports_request_response": "request_response" in selected,
        "supports_cyclic": "no_cyclic" not in selected,
        "supports_event": "no_event" not in selected,
        "supports_redundancy": "redundancy" in selected,
        "supports_time_sync": "time_sync" in selected,
        "supports_safety_profile": "safety" in selected,
        "supports_segmentation": "segmentation" in selected,
        "supports_fragmentation": "fragmentation" in selected,
        "supports_qos": "qos" in selected,
    }


def _spec(
    technology_id: str,
    label: str,
    domain: str,
    layer: str,
    transport_unit: str,
    payload_types: tuple[str, ...],
    hardware_interface: str,
    stack: tuple[str, ...] = (),
    bitrate: int | None = None,
    payload: int | None = None,
    capabilities: tuple[str, ...] = (),
    deterministic: bool = False,
    overhead_bytes: int = 8,
    limitations: str = "Technology-specific conformance details require a vendor/profile extension.",
) -> dict[str, Any]:
    semantics = TECHNOLOGY_SEMANTICS.get(technology_id, {})
    physical = physical_profile(technology_id)
    rate_model = semantics.get("rate_model") or ({
        "type": "SINGLE_BITRATE", "fields": ["bitrate_bps"], "minimum_bps": 1,
    } if bitrate else {"type": "INHERITED_OR_NOT_APPLICABLE", "fields": []})
    capacity_models = CAPACITY_MODELS.get(technology_id)
    direct_io = technology_id in DIRECT_IO_TECHNOLOGIES
    return {
        "id": technology_id,
        "label": label,
        "domain": domain,
        "layer": layer,
        "transport_unit": transport_unit,
        "payload_element_types": list(payload_types),
        "hardware_interface": hardware_interface,
        "hardware_capability_aliases": HARDWARE_CAPABILITY_ALIASES.get(technology_id, []),
        "default_stack": list(stack or (technology_id,)),
        "stack_variants": list({tuple(v): v for v in [
            *([["ip", "udp", "someip"], ["ip", "tcp", "someip"],
               ["ethernet", "ip", "udp", "someip"], ["ethernet", "ip", "tcp", "someip"]]
              if technology_id == "someip" else [list(stack or (technology_id,))]),
            *EXPLICIT_STACK_VARIANTS.get(technology_id, [])]}.values()),
        "default_bitrate": bitrate,
        "rate_model": rate_model,
        "local_timing_schema": _local_timing_schema(technology_id),
        "parameter_schema": {
            field: {"type": "integer", "unit": "bit/s", "minimum": 1}
            for field in rate_model.get("fields", [])
        },
        "mechanisms": semantics.get("mechanisms", {}),
        "parameter_constraints": [
            {**item, **({'source': REVIEW_RATE_PROPOSALS[technology_id]['source'],
                        'source_revision': REVIEW_RATE_PROPOSALS[technology_id]['source_revision']}
                       if technology_id == 'arinc429' else
                       {'source': 'https://www.ieee802.org/1/files/public/docs2013/avb-mjt-et-all-AVB-for-IEEE-Smart-Home-0213.pdf',
                        'source_revision': 'IEEE AVB Task Group authors, February 2013, sections III-IV'}
                       if technology_id == 'avb' else
                       {'source': 'https://raw.githubusercontent.com/bacnet-stack/bacnet-stack/master/src/bacnet/datalink/mstp.h',
                        'source_revision': 'BACnet-stack normative comments and mstpdef.h / config.h, accessed 2026-10-01'}
                       if technology_id == 'bacnet_mstp' else
                       {'source': 'https://bacnet.org/wp-content/uploads/sites/4/2022/08/Add-135-2016bj.pdf',
                        'source_revision': 'Addendum 135-2016bj 2019-11-18, clauses 6.5.1 / YY.2 / YY.6 / YY.7 / H.7.X'}
                       if technology_id == 'bacnet_sc' else
                       {'source':'https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-62/out/en/low-energy-controller/link-layer-specification.html',
                        'source_revision':'Bluetooth Core 6.2 Vol 6 Part B sections 2.4 / 4.5; accessed 2026-10-01'}
                       if technology_id == 'bluetooth_le' else
                       {'source': ('https://www.bosch-semiconductors.com/media/ip_modules/pdf_2/m_can/mcan_users_manual_v331.pdf'
                                   if item.get('when', {}).get('can_controller_profile') == 'M_CAN_3_3_1'
                                   else REVIEW_RATE_PROPOSALS['can']['source']),
                        'source_revision': ('Bosch M_CAN User Manual 3.3.1 2023-03-11 section 2.3.8'
                                            if item.get('when', {}).get('can_controller_profile') == 'M_CAN_3_3_1'
                                            else 'Bosch CAN Specification 2.0 September 1991 Part B 3.2 / 8 / 10')}
                       if technology_id == 'can' else
                       {'source':REVIEW_RATE_PROPOSALS['can_aerospace']['source'],
                        'source_revision':'CANaerospace1.7 2006-01-12 sections2 / 3 / 4 / 7'}
                       if technology_id == 'can_aerospace' else
                       {'source':'https://www.bosch-semiconductors.com/media/ip_modules/pdf_2/m_can/mcan_users_manual_v331.pdf',
                        'source_revision':'Bosch M_CAN3.3.1 2023-03-11 sections2.3.4/2.3.15/3.1.4; CiA CAN FD ISO baseline'}
                       if technology_id == 'can_fd' else
                       {'source': ('https://www.bosch-semiconductors.com/media/ip_modules/pdf_2/x_can/xcan_user_manual_v390.pdf'
                                   if item.get('when',{}).get('can_controller_profile')=='X_CAN_3_9' else REVIEW_RATE_PROPOSALS['can_xl']['source']),
                        'source_revision':'CAN XL ISO11898-1:2024; explicit X_CAN3.9 2024-02-28 sections1.5.4.2.4 / 1.6.4'}
                       if technology_id == 'can_xl' else
                       {'source':REVIEW_RATE_PROPOSALS['canopen']['source'],
                        'source_revision':'CiA CANopen CC lower layers / PDO / SDO / error control; accessed2026-10-01'}
                       if technology_id == 'canopen' else
                       {'source':REVIEW_RATE_PROPOSALS['ccp']['source'],
                        'source_revision':REVIEW_RATE_PROPOSALS['ccp']['source_revision']}
                       if technology_id == 'ccp' else
                       {'source':('https://www.mitsubishielectric.com/dl/fa/document/manual/plc/sh080394e/sh080394es.pdf'
                                  if item['parameter'].startswith('ccl_q_') else 'https://www.cc-link.org/en/networktechnology/spec.html'),
                        'source_revision':'CLPA V1.10/V2 and Notice2404_e April24 2024; Mitsubishi SH080394E-S June2024'}
                       if technology_id == 'cc_link' else
                       {'source':REVIEW_RATE_PROPOSALS['cc_link_ie']['source'],
                        'source_revision':'CLPA variant tables2026-10-01; SH081684ENG-J October2024; MELSEC current product-specific extensions'}
                       if technology_id == 'cc_link_ie' else
                       {'source':REVIEW_RATE_PROPOSALS['cip_safety']['source'],
                        'source_revision':REVIEW_RATE_PROPOSALS['cip_safety']['source_revision']}
                       if technology_id == 'cip_safety' else
                       {'source': REVIEW_RATE_PROPOSALS['dali']['source'],
                        'source_revision': REVIEW_RATE_PROPOSALS['dali']['source_revision']}
                       if technology_id == 'dali' else
                       {'source':REVIEW_RATE_PROPOSALS['goose' if item['parameter'].startswith('goose_') else 'ethernet']['source'],
                        'source_revision':REVIEW_RATE_PROPOSALS['goose' if item['parameter'].startswith('goose_') else 'ethernet']['source_revision']}
                       if technology_id == 'goose' else
                       {'source': REVIEW_RATE_PROPOSALS[technology_id]['source'],
                        'source_revision': REVIEW_RATE_PROPOSALS[technology_id]['source_revision']}
                       if technology_id in {'dnp3','devicenet','doip','etb','ethercat','ethernet_ip','flexray','foundation_fieldbus_h1','fsoe','generic_can','generic_serial','gpio','hart','http'} else {}),
             **({'source':'https://support.fieldcommgroup.org/support/solutions/articles/8000040648-how-is-character-time-calculated-',
                 'source_revision':'FieldComm character-time support article2016-11-11'}
                if technology_id=='hart' and item.get('when',{}).get('hart_profile')=='FCG_FSK_2016'
                and item['parameter'] in {'hart_host_role','hart_quiet_chars','hart_gap_us','hart_response_start_ms'} else {})}
            for item in semantics.get('parameter_constraints', [])
        ],
        "physical_layer_profile_id": physical.id if physical else None,
        "medium_access_model": physical.access_model.value if physical else None,
        "native_parameter_prefixes": list(semantics.get('native_parameter_prefixes',[])),
        "parameter_aliases": deepcopy(semantics.get("parameter_aliases", {})),
        "parameter_alias_limits": deepcopy(semantics.get("parameter_alias_limits", {})),
        "parameter_evidence_scope": semantics.get('parameter_evidence_scope'),
        "rate_source_profile_id": semantics.get('rate_source_profile_id'),
        "arbitration_model_id": physical.arbitration.id if physical and physical.arbitration else None,
        "max_payload_bytes": payload,
        "capabilities": _capabilities(*capabilities),
        "deterministic": deterministic,
        "overhead_bytes": 0 if technology_id in {'adc', 'dac'} else overhead_bytes,
        "implementation_status": _status(technology_id),
        "connection_type": "DIRECT_IO" if direct_io else "COMMUNICATION_TECHNOLOGY",
        "parameter_proposals": REVIEW_RATE_PROPOSALS.get(technology_id) or (
            {"kind": "EXISTING_CATALOG_CANDIDATE", "unit": "bit/s",
             "candidate": bitrate, "source": "NIS built-in catalog",
             "status": "REVIEW_REQUIRED",
             "note": "Historical catalog value; confirm hardware, mode and physical link before use."}
            if bitrate and not direct_io and rate_model.get("type") != "DEVICE_DEPENDENT_CLOCK" else
            {"kind": "DEVICE_DEPENDENT", "status": "REVIEW_REQUIRED",
             "required_fields": list(rate_model.get("fields") or []),
             "note": "No universal rate is available; inspect the selected hardware/profile."}
        ),
        "capacity_evidence": {
            "status": "NOT_APPLICABLE" if direct_io else "MODEL_AVAILABLE" if capacity_models else "MODEL_MISSING",
            "frame_model": capacity_models[0] if capacity_models else None,
            "schedule_model": capacity_models[1] if capacity_models else None,
            "requires_confirmed_device_parameters": not direct_io,
        },
        "components": {
            "binding": f"{technology_id}.binding",
            "generator": f"{technology_id}.generator",
            "validator": f"{technology_id}.validator",
            "timing_model": f"{technology_id}.timing" if capacity_models else None,
            "load_model": f"{technology_id}.load" if capacity_models else None,
            "encoder": f"{technology_id}.encoder",
            "decoder": f"{technology_id}.decoder",
        },
        "known_limitations": limitations,
    }


# id, label, domain, layer, unit, elements, interface, stack, bitrate, payload, capabilities, deterministic
ROWS: tuple[tuple[Any, ...], ...] = (
    # Generic layered foundations
    ("ethernet", "Ethernet", "generic_networking", "DATA_LINK", "FRAME", ("FIELD", "RAW_DATA"), "ethernet_port", (), 1_000_000_000, 1500, ("objects", "streams", "multicast", "redundancy", "time_sync", "qos"), False),
    ("ip", "Internet Protocol", "generic_networking", "NETWORK", "PACKET", ("FIELD", "RAW_DATA"), "explicit_registered_link", (), None, None, ("objects", "streams", "multicast", "fragmentation", "qos"), False),
    ("udp", "UDP", "generic_networking", "TRANSPORT", "DATAGRAM", ("FIELD", "RAW_DATA"), "explicit_udp_ip_and_phy_path", (), None, None, ("objects", "multicast", "fragmentation"), False),
    ("tcp", "TCP", "generic_networking", "TRANSPORT", "STREAM_CHUNK", ("FIELD", "RAW_DATA"), "explicit_ip_path", (), None, None, ("objects", "streams", "request_response", "segmentation", "fragmentation", "qos"), False),
    # Automotive / vehicle
    ("can", "CAN 2.0A/B", "generic_networking", "DATA_LINK", "FRAME", ("SIGNAL", "STATUS"), "can_controller", (), None, 8, ("multicast",), False),
    ("can_fd", "CAN-FD", "generic_networking", "DATA_LINK", "FRAME", ("SIGNAL", "STATUS"), "can_fd_controller", (), None, 64, ("multicast",), False),
    ("can_xl", "CAN XL", "generic_networking", "DATA_LINK", "FRAME", ("SIGNAL", "FIELD", "RAW_DATA"), "can_xl_controller", (), None, 2048, ("objects", "multicast", "qos"), False),
    ("lin", "LIN", "generic_networking", "DATA_LINK", "FRAME", ("SIGNAL", "STATUS"), "lin_qualified_channel", (), None, 8, (), False),
    ("flexray", "FlexRay", "generic_networking", "DATA_LINK", "FRAME", ("SIGNAL", "STATUS"), "flexray_controller", (), 2_500_000, 254, ("multicast", "redundancy", "time_sync"), True),
    ("most", "MOST", "generic_networking", "DATA_LINK", "STREAM_CHUNK", ("AUDIO", "RAW_DATA"), "explicit_most_generation_phy", (), None, None, ("streams", "time_sync"), True),
    ("canopen", "CANopen", "generic_networking", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "SIGNAL"), "can_controller", ("can", "canopen"), 10_000, 8, ("objects", "pubsub", "request_response"), False),
    ("j1939", "SAE J1939", "generic_networking", "APPLICATION", "MESSAGE", ("FIELD", "SIGNAL"), "j1939_qualified_classic_or_fd_port", (), None, None, ("multicast", "segmentation"), False),
    ("isobus", "ISO 11783 / ISOBUS", "generic_networking", "INDUSTRY_PROFILE", "MESSAGE", ("FIELD", "SIGNAL"), "isobus_qualified_can_port", (), None, None, ("objects", "multicast", "segmentation"), False),
    ("uds", "UDS", "generic_networking", "APPLICATION", "SERVICE_REQUEST", ("COMMAND", "STATUS", "RAW_DATA"), "explicit_uds_selected_transport", (), None, None, ("request_response",), False),
    ("xcp", "XCP", "generic_networking", "APPLICATION", "SERVICE_REQUEST", ("COMMAND", "DATA_OBJECT"), "xcp_actual_lower_transport", (), None, None, ("objects", "request_response", "segmentation"), False),
    ("ccp", "CCP", "generic_networking", "APPLICATION", "SERVICE_REQUEST", ("COMMAND", "DATA_OBJECT"), "can_controller", ("can", "ccp"), None, 8, ("objects", "request_response"), False),
    ("someip", "SOME/IP", "generic_networking", "APPLICATION", "SERVICE_EVENT", ("FIELD", "DATA_OBJECT"), "actual_someip_transport_binding", ("someip",), None, None, ("objects", "pubsub", "request_response", "segmentation", "qos"), False),
    ("someip_sd", "SOME/IP-SD", "generic_networking", "APPLICATION", "SERVICE_EVENT", ("FIELD", "STATUS"), "actual_someip_sd_udp_ip_binding", ("someip_sd",), None, None, ("objects", "multicast", "pubsub"), False),
    ("doip", "DoIP", "automotive", "APPLICATION", "PDU", ("COMMAND", "STATUS", "RAW_DATA"), "explicit_ip_transport_binding", (), None, 4_294_967_295, ("request_response", "stream_framing"), False),
    ("obd2", "OBD-II", "generic_networking", "INDUSTRY_PROFILE", "SERVICE_REQUEST", ("COMMAND", "STATUS"), "obd_actual_vehicle_binding_and_adapter_host", (), None, None, ("request_response",), False),
    ("avb", "AVB", "generic_networking", "INDUSTRY_PROFILE", "STREAM_CHUNK", ("AUDIO", "RAW_DATA"), "ethernet_port", ("ethernet", "avb"), 100_000_000, 1500, ("streams", "multicast", "time_sync", "qos"), True),
    ("tsn", "Time-Sensitive Networking", "generic_networking", "INDUSTRY_PROFILE", "FRAME", ("FIELD", "RAW_DATA"), "explicit_tsn_tools_and_qualified_phy", (), None, None, ("objects", "streams", "multicast", "redundancy", "time_sync", "qos"), False),
    # Industrial / PLC
    ("profinet", "PROFINET RT/IRT", "industrial_automation", "DATA_LINK", "PROCESS_DATA", ("FIELD", "STATUS", "QUALITY"), "explicit_profinet_io", (), None, None, ("objects", "pubsub", "cyclic", "time_sync", "safety", "qos"), False),
    ("ethercat", "EtherCAT", "industrial_automation", "INDUSTRY_PROFILE", "DATAGRAM", ("FIELD", "REGISTER", "STATUS"), "ethercat_port", ("ethernet", "ethercat"), 100_000_000, 1486, ("objects", "pubsub", "time_sync", "safety", "qos"), True),
    ("ethernet_ip", "EtherNet/IP", "generic_networking", "APPLICATION", "PDU", ("FIELD", "DATA_OBJECT"), "explicit_ip_transport_binding", (), None, 65535, ("objects", "pubsub", "request_response"), False),
    ("modbus_tcp", "Modbus TCP", "generic_networking", "APPLICATION", "PDU", ("REGISTER", "COIL"), "explicit_mbap_tcp_binding", (), None, 253, ("request_response", "segmentation"), False),
    ("modbus_rtu", "Modbus RTU", "generic_networking", "APPLICATION", "PDU", ("REGISTER", "COIL"), "explicit_rtu_serial_binding", ("modbus_rtu",), 19200, 253, ("request_response",), True),
    ("modbus_ascii", "Modbus ASCII", "generic_networking", "APPLICATION", "PDU", ("REGISTER", "COIL"), "explicit_ascii_serial_binding", ("modbus_ascii",), 19_200, 253, ("request_response",), False),
    ("profibus_dp", "PROFIBUS DP", "industrial_automation", "DATA_LINK", "TELEGRAM", ("FIELD", "STATUS"), "explicit_profibus_dp_bearer", (), None, None, ("pubsub", "request_response", "safety"), False),
    ("profibus_pa", "PROFIBUS PA", "process_industry", "DATA_LINK", "TELEGRAM", ("FIELD", "STATUS", "QUALITY"), "explicit_profibus_pa_mbp", (), None, None, ("pubsub", "request_response", "safety"), False),
    ("devicenet", "DeviceNet", "industrial_automation", "INDUSTRY_PROFILE", "MESSAGE", ("DATA_OBJECT", "SIGNAL"), "can_controller", ("can", "devicenet"), 125_000, 8, ("objects", "pubsub", "request_response", "fragmentation"), True),
    ("interbus", "INTERBUS", "generic_networking", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS"), "interbus_interface", (), None, None, ("pubsub", "ordered_ring", "pcp"), False),
    ("cc_link", "CC-Link", "generic_networking", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS"), "cc_link_interface", (), 156_000, None, ("pubsub",), False),
    ("cc_link_ie", "CC-Link IE", "generic_networking", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS"), "ethernet_or_optical_interface", (), None, None, ("objects", "pubsub", "time_sync", "qos"), False),
    ("sercos_iii", "Sercos III", "generic_networking", "DATA_LINK", "PROCESS_DATA", ("FIELD", "STATUS"), "actual_sercos_iii_full_duplex_link", ("sercos_iii",), None, None, ("pubsub", "time_sync"), False),
    ("powerlink", "POWERLINK", "industrial_automation", "DATA_LINK", "PROCESS_DATA", ("FIELD", "STATUS"), "explicit_powerlink_100base_x_half_duplex", (), None, None, ("pubsub", "time_sync", "safety"), False),
    ("io_link", "IO-Link", "generic_networking", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS", "QUALITY"), "io_link_master_port", (), None, None, ("request_response", "wired_point_to_point"), False),
    ("io_link_wireless", "IO-Link Wireless", "generic_networking", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS", "QUALITY"), "wireless_interface", (), None, None, ("request_response", "time_sync"), False),
    ("opc_ua", "OPC UA Client/Server", "generic", "APPLICATION", "SERVICE_RESPONSE", ("DATA_OBJECT", "STRUCT", "STATUS", "QUALITY"), "explicit_opc_ua_endpoint_transport_and_peer", (), None, None, ("objects", "request_response", "segmentation", "qos"), False),
    ("opc_ua_pubsub", "OPC UA PubSub", "generic", "APPLICATION", "DATAGRAM", ("DATA_OBJECT", "STRUCT", "STATUS", "QUALITY"), "explicit_pubsub_transport_mapping_and_bearer", (), None, None, ("objects", "multicast", "pubsub", "time_sync", "qos"), True),
    ("mqtt", "MQTT", "generic_networking", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "RAW_DATA"), "explicit_ordered_stream_binding", (), None, None, ("objects", "pubsub", "qos", "segmentation"), False),
    ("sparkplug_b", "Sparkplug B", "generic_networking", "INDUSTRY_PROFILE", "MESSAGE", ("DATA_OBJECT", "STATUS", "QUALITY"), "independently_bound_mqtt_transport", ("sparkplug_b",), None, None, ("objects", "pubsub", "qos", "segmentation"), False),
    # Robotics
    ("dds", "DDS", "generic_networking", "APPLICATION", "TOPIC_SAMPLE", ("DATA_OBJECT", "STRUCT", "ARRAY", "IMAGE", "POINT_CLOUD"), "explicit_dds_transport_interface", (), None, None, ("objects", "streams", "multicast", "pubsub", "redundancy", "fragmentation", "qos"), True),
    ("ros2", "ROS 2", "generic_networking", "INDUSTRY_PROFILE", "TOPIC_SAMPLE", ("DATA_OBJECT", "STRUCT", "ARRAY", "IMAGE", "POINT_CLOUD"), "actual_ros_rmw_bearer", ("ros2",), None, None, ("objects", "streams", "multicast", "pubsub", "request_response", "fragmentation", "qos"), False),
    # Aerospace
    ("arinc429", "ARINC 429", "aerospace", "DATA_LINK", "WORD", ("FIELD", "STATUS"), "arinc429_interface", (), 12_500, 4, (), True),
    ("afdx", "ARINC 664 / AFDX", "aerospace", "INDUSTRY_PROFILE", "PACKET", ("FIELD", "RAW_DATA"), "afdx_ethernet_port", ("ethernet", "ip", "udp", "afdx"), 100_000_000, 1471, ("multicast", "redundancy", "qos"), True),
    ("mil_std_1553", "MIL-STD-1553", "aerospace", "DATA_LINK", "WORD", ("COMMAND", "FIELD", "STATUS"), "mil1553_interface", (), 1_000_000, 64, ("multicast", "redundancy"), True),
    ("can_aerospace", "CAN Aerospace", "aerospace", "INDUSTRY_PROFILE", "MESSAGE", ("SIGNAL", "STATUS"), "can_controller", ("can", "can_aerospace"), None, 4, ("multicast", "objects", "request_response"), False, 4),
    ("spacewire", "SpaceWire", "generic_networking", "DATA_LINK", "PACKET", ("FIELD", "RAW_DATA"), "actual_spacewire_point_to_point_ds", ("spacewire",), None, None, ("objects", "streams", "time_sync", "fragmentation"), False),
    ("tte", "Time-Triggered Ethernet", "generic_networking", "INDUSTRY_PROFILE", "FRAME", ("FIELD", "RAW_DATA"), "explicit_tte_tt_rc_be_sync_and_phy", (), None, None, ("multicast", "redundancy", "time_sync", "qos"), False),
    # Rail / marine / heavy vehicle
    ("mvb", "MVB", "generic_networking", "DATA_LINK", "PROCESS_DATA", ("SIGNAL", "STATUS"), "mvb_interface", (), 1_500_000, 32, ("multicast", "time_sync"), True),
    ("wtb", "WTB", "generic_networking", "DATA_LINK", "PROCESS_DATA", ("SIGNAL", "STATUS"), "wtb_actual_master_segment", (), None, None, ("multicast", "redundancy", "time_sync"), True),
    ("etb", "Ethernet Train Backbone", "rail", "INDUSTRY_PROFILE", "FRAME", ("FIELD", "RAW_DATA"), "ethernet_port", ("ethernet", "etb"), 100_000_000, 1500, ("objects", "streams", "multicast", "redundancy", "qos"), True),
    ("trdp", "TRDP", "generic_networking", "APPLICATION", "PROCESS_DATA", ("FIELD", "STATUS"), "explicit_pd_udp_or_md_udp_tcp_path", (), None, None, ("objects", "multicast", "pubsub", "request_response", "qos"), False),
    ("nmea0183", "NMEA 0183", "generic_networking", "APPLICATION", "TELEGRAM", ("FIELD", "STATUS"), "nmea0183_actual_serial_or_registered_host", (), None, None, ("ascii_sentences", "one_way_serial_or_registered_host"), False),
    ("nmea2000", "NMEA 2000", "generic_networking", "INDUSTRY_PROFILE", "MESSAGE", ("FIELD", "SIGNAL"), "nmea2000_can_cc_250k_qualified_topology", (), 250_000, None, ("multicast", "segmentation"), True),
    ("iec61162", "IEC 61162", "generic_networking", "APPLICATION", "MESSAGE", ("FIELD", "STATUS"), "explicit_iec61162_part_binding", (), None, None, ("objects", "part_specific_transport"), False),
    # Building automation
    ("bacnet_ip", "BACnet/IP", "building_automation", "APPLICATION", "PDU", ("DATA_OBJECT", "FIELD"), "ethernet_port", ("ethernet", "ip", "udp", "bacnet_ip"), None, 1476, ("objects", "multicast", "request_response", "segmentation"), False),
    ("bacnet_mstp", "BACnet MS/TP", "building_automation", "APPLICATION", "PDU", ("DATA_OBJECT", "FIELD"), "rs485_port", (), 9600, 1476, ("objects", "request_response", "segmentation"), True),
    ("bacnet_sc", "BACnet/SC", "building_automation", "APPLICATION", "PDU", ("DATA_OBJECT", "FIELD"), "ethernet_port", ("ethernet", "ip", "tcp", "bacnet_sc"), None, 61325, ("objects", "request_response", "qos"), False),
    ("knx_tp", "KNX TP", "generic_networking", "INDUSTRY_PROFILE", "TELEGRAM", ("DATA_OBJECT", "FIELD"), "knx_tp_qualified_interface", (), None, None, ("objects", "multicast", "pubsub"), False),
    ("knx_ip", "KNX IP", "generic_networking", "INDUSTRY_PROFILE", "TELEGRAM", ("DATA_OBJECT", "FIELD"), "knx_ip_qualified_endpoint", (), None, None, ("objects", "multicast", "pubsub"), False),
    ("knx_rf", "KNX RF", "generic_networking", "INDUSTRY_PROFILE", "TELEGRAM", ("DATA_OBJECT", "FIELD"), "knx_rf_qualified_radio", (), None, None, ("objects", "multicast", "pubsub"), False),
    ("lonworks", "LonWorks", "generic_networking", "INDUSTRY_PROFILE", "MESSAGE", ("DATA_OBJECT", "FIELD"), "lonworks_qualified_channel", (), None, None, ("objects", "pubsub", "multicast", "request_response"), False),
    ("dali", "DALI", "building_automation", "APPLICATION", "TELEGRAM", ("COMMAND", "STATUS", "EVENT"), "dali_interface", (), 1_200, 3, ("request_response",), True),
    ("m_bus", "M-Bus", "generic_networking", "APPLICATION", "TELEGRAM", ("FIELD", "STATUS"), "wired_mbus_actual_voltage_current_segment", (), None, None, ("request_response", "half_duplex_poll"), False),
    ("wireless_m_bus", "Wireless M-Bus", "generic_networking", "APPLICATION", "TELEGRAM", ("FIELD", "STATUS"), "wireless_mbus_actual_mode_direction", (), None, None, ("no_cyclic",), False),
    # Energy and process
    ("iec61850", "IEC 61850", "generic_networking", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "STRUCT", "STATUS", "QUALITY"), "explicit_iec61850_service_binding", (), None, None, ("objects", "service_specific_transport"), False),
    ("mms", "MMS", "generic_networking", "APPLICATION", "SERVICE_RESPONSE", ("DATA_OBJECT", "STRUCT"), "explicit_mms_transport_binding", (), None, None, ("objects", "request_response", "segmentation"), False),
    ("goose", "GOOSE", "generic_networking", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "STATUS", "QUALITY"), "ethernet_port", ("ethernet", "goose"), None, None, ("objects", "multicast", "pubsub", "redundancy", "qos"), False),
    ("sampled_values", "IEC 61850 Sampled Values", "generic_networking", "APPLICATION", "TOPIC_SAMPLE", ("ARRAY", "QUALITY"), "actual_sv_lower_link", ("sampled_values",), None, None, ("objects", "streams", "multicast", "pubsub", "time_sync", "qos"), False),
    ("dnp3", "DNP3", "generic_networking", "APPLICATION", "PDU", ("DATA_OBJECT", "STATUS", "QUALITY"), "explicit_transport_binding", (), None, None, ("objects", "request_response", "segmentation"), False),
    ("iec60870_5_101", "IEC 60870-5-101", "generic_networking", "APPLICATION", "TELEGRAM", ("DATA_OBJECT", "STATUS", "QUALITY"), "explicit_iec101_serial_binding", (), None, None, ("objects", "request_response"), False),
    ("iec60870_5_104", "IEC 60870-5-104", "generic_networking", "APPLICATION", "PDU", ("DATA_OBJECT", "STATUS", "QUALITY"), "explicit_iec104_tcp_path", ("iec60870_5_104",), None, None, ("objects", "request_response", "stream_reassembly"), False),
    ("sunspec_modbus", "SunSpec Modbus", "generic_networking", "INDUSTRY_PROFILE", "REGISTER_BLOCK", ("REGISTER", "STATUS"), "explicit_modbus_serial_or_tcp_binding", (), None, None, ("objects", "request_response"), False),
    ("ocpp", "OCPP", "generic_networking", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "COMMAND", "STATUS"), "explicit_ocpp_application_transport_and_peer", (), None, None, ("objects", "request_response"), False),
    ("hart", "HART (wired)", "generic_networking", "INDUSTRY_PROFILE", "TELEGRAM", ("FIELD", "STATUS", "QUALITY"), "explicit_hart_modem_loop", (), None, 255, ("request_response",), False),
    ("wirelesshart", "WirelessHART", "generic_networking", "APPLICATION", "MESSAGE", ("FIELD", "STATUS", "QUALITY"), "wirelesshart_actual_radio_mesh", (), None, None, ("multicast", "time_sync", "qos"), True),
    ("foundation_fieldbus_h1", "FOUNDATION Fieldbus H1", "generic_networking", "APPLICATION", "PDU", ("FIELD", "STATUS", "QUALITY"), "h1_fieldbus_interface", (), 31_250, 251, ("objects", "pubsub", "time_sync", "request_response"), True),
    # Embedded interfaces
    ("i2c", "I2C", "generic_networking", "DATA_LINK", "MESSAGE", ("REGISTER", "RAW_DATA"), "explicit_i2c_port", (), None, None, ("request_response",), False),
    ("i3c", "I3C", "generic_networking", "DATA_LINK", "MESSAGE", ("REGISTER", "RAW_DATA"), "explicit_i3c_port", (), None, None, ("request_response", "event"), False),
    ("spi", "SPI / separately qualified QSPI", "generic_networking", "DATA_LINK", "STREAM_CHUNK", ("REGISTER", "RAW_DATA"), "actual_spi_voltage_pins_and_layout", (), None, None, ("streams",), False),
    ("uart", "UART / USART", "generic_networking", "DATA_LINK", "STREAM_CHUNK", ("RAW_DATA",), "explicit_uart_clock_framing_and_phy", (), None, None, ("streams",), False),
    ("rs232", "RS-232", "generic_networking", "PHYSICAL", "STREAM_CHUNK", ("RAW_DATA",), "rs232_actual_single_ended_interchange", (), None, None, ("streams",), False),
    ("rs422", "RS-422", "generic_networking", "PHYSICAL", "STREAM_CHUNK", ("RAW_DATA",), "rs422_actual_single_driver_pair", (), None, None, ("streams",), False),
    ("rs485", "RS-485", "generic_networking", "PHYSICAL", "STREAM_CHUNK", ("RAW_DATA",), "rs485_actual_electrical_multipoint", (), None, None, ("streams",), False),
    ("one_wire", "1-Wire", "embedded_systems", "DATA_LINK", "MESSAGE", ("REGISTER", "RAW_DATA"), "source_qualified_1wire_slot_and_load", (), None, None, ("request_response",), True),
    ("usb", "USB", "generic_networking", "DATA_LINK", "PACKET", ("RAW_DATA", "STREAM_CHUNK"), "usb_actual_host_endpoint_and_tunnel", (), None, None, ("objects", "streams", "segmentation", "qos"), False),
    ("pcie", "PCIe", "generic_networking", "DATA_LINK", "PACKET", ("RAW_DATA", "DATA_OBJECT"), "explicit_pcie_trained_channel", (), None, None, ("objects", "streams", "qos"), False),
    ("mipi_csi2", "MIPI CSI-2", "embedded_systems", "DATA_LINK", "STREAM_CHUNK", ("IMAGE", "RAW_DATA"), "mipi_csi2_interface", (), 0, 65535, ("streams",), True),
    ("mipi_dsi", "MIPI DSI", "embedded_systems", "DATA_LINK", "STREAM_CHUNK", ("IMAGE", "RAW_DATA"), "mipi_dsi_interface", (), 0, 65535, ("streams",), True),
    ("lvds", "LVDS", "generic_networking", "PHYSICAL", "STREAM_CHUNK", ("RAW_DATA",), "lvds_actual_qualified_balanced_pair", (), None, None, ("streams", "actual_clock_encoding"), False),
    ("gpio", "GPIO", "generic_networking", "PHYSICAL", "PROCESS_DATA", ("SIGNAL", "STATUS"), "gpio_port", (), None, None, (), False),
    ("pwm", "PWM", "embedded_systems", "PHYSICAL", "PROCESS_DATA", ("SIGNAL",), "explicit_pwm_driver_waveform", (), None, None, (), True),
    ("adc", "ADC", "embedded_systems", "PHYSICAL", "PROCESS_DATA", ("SIGNAL",), "analog_input", (), None, None, (), True),
    ("dac", "DAC", "embedded_systems", "PHYSICAL", "PROCESS_DATA", ("SIGNAL",), "analog_output", (), None, None, (), True),
    # IoT / wireless
    ("mqtt_sn", "MQTT-SN", "generic_networking", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "RAW_DATA"), "explicit_datagram_gateway_binding", (), None, None, ("objects", "pubsub", "qos"), False),
    ("coap", "CoAP", "generic_networking", "APPLICATION", "PDU", ("DATA_OBJECT", "RAW_DATA"), "explicit_ip_link_interface", (), None, None, ("objects", "multicast", "request_response", "segmentation"), False),
    ("http", "HTTP", "generic_networking", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "RAW_DATA"), "explicit_http_transport_binding", (), None, None, ("objects", "streams", "request_response", "segmentation"), False),
    ("websocket", "WebSocket", "generic_networking", "APPLICATION", "STREAM_CHUNK", ("DATA_OBJECT", "RAW_DATA"), "websocket_actual_negotiated_stream", (), None, None, ("objects", "streams", "pubsub", "segmentation"), False),
    ("amqp", "AMQP", "iot_wireless", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "RAW_DATA"), "ethernet_or_wireless_interface", ("ethernet", "ip", "tcp", "amqp"), None, None, ("objects", "pubsub", "request_response", "qos"), False),
    ("wifi", "Wi-Fi", "generic_networking", "DATA_LINK", "FRAME", ("FIELD", "RAW_DATA"), "wifi_actual_generation_peer_radio", (), None, None, ("objects", "streams", "multicast", "qos"), False),
    ("bluetooth_le", "Bluetooth LE", "iot_wireless", "DATA_LINK", "PDU", ("FIELD", "DATA_OBJECT"), "wireless_interface", (), 1_000_000, 251, ("objects", "pubsub", "request_response"), False),
    ("zigbee", "Zigbee", "generic_networking", "APPLICATION", "PACKET", ("DATA_OBJECT", "FIELD"), "zigbee_actual_phy_mesh", (), None, None, ("objects", "multicast", "pubsub"), False),
    ("thread", "Thread", "generic_networking", "NETWORK", "PACKET", ("DATA_OBJECT", "FIELD"), "explicit_thread_radio_and_ipv6_path", (), None, None, ("objects", "multicast", "fragmentation"), False),
    ("matter", "Matter", "generic_networking", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "COMMAND", "STATUS"), "matter_actual_ipv6_or_commissioning_path", (), None, None, ("objects", "multicast", "pubsub", "request_response"), False),
    ("lorawan", "LoRaWAN", "generic_networking", "INDUSTRY_PROFILE", "PACKET", ("FIELD", "DATA_OBJECT"), "lorawan_actual_regional_radio", (), None, None, ("objects", "confirmed_unconfirmed", "class_a_b_c"), False),
    ("lte_m", "LTE-M", "generic_networking", "DATA_LINK", "PACKET", ("FIELD", "RAW_DATA"), "lte_m_actual_eutra_radio", (), None, None, ("objects", "scheduled_radio", "category_ce_repetition"), False),
    ("nb_iot", "NB-IoT", "generic_networking", "DATA_LINK", "PACKET", ("FIELD", "RAW_DATA"), "nb_iot_actual_radio_band_and_deployment", (), None, None, ("objects", "scheduled_radio", "category_repetition_and_negotiated_nas"), False),
    ("5g", "5G", "iot_wireless", "DATA_LINK", "PACKET", ("FIELD", "RAW_DATA"), "wireless_interface", (), None, None, ("objects", "streams", "multicast", "qos"), False),
    ("uwb", "UWB", "generic_networking", "DATA_LINK", "FRAME", ("FIELD", "RAW_DATA"), "uwb_actual_radio_mac_host", (), None, None, ("objects", "time_sync"), False),
    ("nfc", "NFC", "generic_networking", "DATA_LINK", "MESSAGE", ("DATA_OBJECT", "RAW_DATA"), "nfc_actual_rf_protocol_and_controller", (), None, None, ("objects", "request_response", "mode_role_and_firmware_qualified"), False),
    ("rfid", "RFID", "generic_networking", "INDUSTRY_PROFILE", "MESSAGE", ("DATA_OBJECT", "RAW_DATA"), "explicit_rfid_lf_hf_uhf_air_and_host", (), None, None, ("objects", "request_response", "protocol_qualified_inventory"), False),
    # Safety profiles and custom
    ("profisafe", "PROFIsafe", "generic_networking", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS", "QUALITY"), "explicit_profisafe_black_channel_and_device", (), None, None, ("safety", "time_sync", "qos"), False),
    ("cip_safety", "CIP Safety", "generic_networking", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS", "QUALITY"), "explicit_safety_transport_interface", (), None, 250, ("safety", "pubsub", "multicast"), False),
    ("fsoe", "FSoE", "generic_networking", "APPLICATION", "PDU", ("FIELD", "STATUS", "QUALITY"), "explicit_black_channel_binding", (), None, None, ("safety", "request_response"), False),
    ("opensafety", "openSAFETY", "generic_networking", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS", "QUALITY"), "explicit_opensafety_black_channel_and_device", (), None, None, ("safety", "redundancy"), True),
    ("generic_serial", "Generic Serial", "generic_networking", "DATA_LINK", "STREAM_CHUNK", ("RAW_DATA",), "explicit_serial_transport_binding", (), None, None, ("streams",), False),
    ("generic_can", "Generic CAN", "generic_networking", "DATA_LINK", "FRAME", ("SIGNAL", "RAW_DATA"), "explicit_can_family_binding", (), None, 2048, ("multicast",), False),
    ("generic_ethernet", "Generic Ethernet", "generic_networking", "DATA_LINK", "FRAME", ("FIELD", "RAW_DATA"), "ethernet_port", (), 10_000_000, 1500, ("multicast",), False),
    ("custom_udp", "Custom UDP", "generic_networking", "APPLICATION", "DATAGRAM", ("RAW_DATA", "DATA_OBJECT"), "explicit_udp_ip_link_interface", (), None, None, ("objects", "streams", "multicast"), False),
    ("custom_tcp", "Custom TCP", "generic_networking", "APPLICATION", "STREAM_CHUNK", ("RAW_DATA", "DATA_OBJECT"), "explicit_tcp_ip_link_interface", (), None, None, ("objects", "streams", "segmentation"), False),
    ("custom_binary", "Custom Binary", "generic_networking", "APPLICATION", "MESSAGE", ("RAW_DATA",), "explicit_transport_interface", (), None, None, ("streams", "segmentation"), False),
    ("custom_text", "Custom Text", "generic_networking", "APPLICATION", "MESSAGE", ("RAW_DATA",), "explicit_transport_interface", (), None, None, ("streams", "segmentation"), False),
    ("custom_protocol", "Custom Protocol", "generic_networking", "APPLICATION", "MESSAGE", ("RAW_DATA", "DATA_OBJECT"), "explicit_transport_interface", (), None, None, ("objects", "streams", "segmentation"), False),
)


PARAMETER_UI_ALIASES = {'bitrate_bps': 'bitrate', 'nominal_bitrate_bps': 'arbitration_bitrate',
                        'data_bitrate_bps': 'data_bitrate'}
PARAMETER_CORE_ALIASES = {alias: key for key, alias in PARAMETER_UI_ALIASES.items()}


# Historical parameter names remain reserved after the last profile retires them.
# Otherwise a foreign CAN queue/retry field would become arbitrary project metadata.
RESERVED_PARAMETER_NAMES = frozenset(['arbitration_bitrate', 'bit_error_rate', 'bitrate', 'burst_factor', 'burst_window_ms', 'clock_drift_ppm', 'clock_offset_ms', 'corruption_probability', 'critical_threshold', 'cycle_ms', 'data_bitrate', 'deadline_ms', 'distributed_clock_cycle_ms', 'dropout_probability', 'duplex', 'duplicate_probability', 'durability', 'duration_s', 'frame_loss_probability', 'freshness_ms', 'gateway_delay_ms', 'gateway_input_buffer', 'gateway_maximum_messages_s', 'gateway_maximum_routes', 'gateway_maximum_throughput', 'gateway_output_buffer', 'gateway_queue_delay_ms', 'history_depth', 'history_kind', 'jitter_ms', 'lifespan_ms', 'liveliness', 'max_events', 'maximum_latency_ms', 'maximum_sync_error_ms', 'minimum_cycle_time_ms', 'mtu_bytes', 'overload_threshold', 'packet_loss_probability', 'payload_bytes', 'peak_factor', 'propagation_delay_ms', 'protocol_conversion_delay_ms', 'qos_priority', 'queue_policy', 'queue_size', 'rate_limit_bit_s', 'reliability_mode', 'reordering_probability', 'required_reliability', 'reserved_bandwidth_percent', 'retransmission_delay_ms', 'retransmission_enabled', 'retransmission_rate', 'retry_limit', 'sample_point_percent', 'seed', 'source_processing_delay_ms', 'sync_interval_ms', 'sync_method', 'sync_precision_ms', 'target_bus_load_percent', 'target_processing_delay_ms', 'timeout_ms', 'traffic_class', 'vlan_id', 'warning_threshold'])

# Physical capability names identify review candidates, not qualified PHY facts.
HARDWARE_CAPABILITY_ALIASES = {'ethernet': ['ethernet_port'], 'ip': ['ethernet_port'], 'udp': ['ethernet_port'], 'tcp': ['ethernet_port'], 'can': ['can_controller'], 'can_fd': ['can_fd_controller'], 'can_xl': ['can_xl_controller'], 'lin': ['lin_channel'], 'flexray': ['flexray_controller'], 'most': ['most_interface'], 'canopen': ['can_controller'], 'j1939': ['can_controller'], 'isobus': ['can_controller'], 'uds': ['can_or_ethernet_interface'], 'xcp': ['can_or_ethernet_interface'], 'ccp': ['can_controller'], 'someip': ['ethernet_port'], 'someip_sd': ['ethernet_port'], 'doip': ['ethernet_port'], 'obd2': ['can_or_ethernet_interface'], 'avb': ['ethernet_port'], 'tsn': ['ethernet_port'], 'profinet': ['ethernet_port'], 'ethercat': ['ethercat_port'], 'ethernet_ip': ['ethernet_port'], 'modbus_tcp': ['ethernet_port'], 'modbus_rtu': ['rs485_port'], 'modbus_ascii': ['rs485_port'], 'profibus_dp': ['profibus_interface'], 'profibus_pa': ['profibus_interface'], 'devicenet': ['can_controller'], 'interbus': ['interbus_interface'], 'cc_link': ['cc_link_interface'], 'cc_link_ie': ['ethernet_port'], 'sercos_iii': ['ethernet_port'], 'powerlink': ['ethernet_port'], 'io_link': ['io_link_master_port'], 'io_link_wireless': ['wireless_interface'], 'opc_ua': ['ethernet_port'], 'opc_ua_pubsub': ['ethernet_port'], 'mqtt': ['ethernet_or_wireless_interface'], 'sparkplug_b': ['ethernet_port'], 'dds': ['ethernet_port'], 'ros2': ['ethernet_port'], 'arinc429': ['arinc429_interface'], 'afdx': ['afdx_ethernet_port'], 'mil_std_1553': ['mil1553_interface'], 'can_aerospace': ['can_controller'], 'spacewire': ['spacewire_interface'], 'tte': ['ethernet_port'], 'mvb': ['mvb_interface'], 'wtb': ['wtb_interface'], 'etb': ['ethernet_port'], 'trdp': ['ethernet_port'], 'nmea0183': ['rs422_port'], 'nmea2000': ['can_controller'], 'iec61162': ['serial_or_ethernet_interface'], 'bacnet_ip': ['ethernet_port'], 'bacnet_mstp': ['rs485_port'], 'bacnet_sc': ['ethernet_port'], 'knx_tp': ['knx_tp_interface'], 'knx_ip': ['ethernet_port'], 'knx_rf': ['wireless_interface'], 'lonworks': ['lonworks_interface'], 'dali': ['dali_interface'], 'm_bus': ['m_bus_interface'], 'wireless_m_bus': ['wireless_interface'], 'iec61850': ['ethernet_port'], 'mms': ['ethernet_port'], 'goose': ['ethernet_port'], 'sampled_values': ['ethernet_port'], 'dnp3': ['serial_or_ethernet_interface'], 'iec60870_5_101': ['serial_port'], 'iec60870_5_104': ['ethernet_port'], 'sunspec_modbus': ['ethernet_or_rs485_interface'], 'ocpp': ['ethernet_or_wireless_interface'], 'hart': ['hart_interface'], 'wirelesshart': ['wireless_interface'], 'foundation_fieldbus_h1': ['fieldbus_interface'], 'i2c': ['i2c_controller'], 'i3c': ['i3c_controller'], 'spi': ['spi_controller'], 'uart': ['serial_port'], 'rs232': ['rs232_port'], 'rs422': ['rs422_port'], 'rs485': ['rs485_port'], 'one_wire': ['one_wire_interface'], 'usb': ['usb_controller'], 'pcie': ['pcie_interface'], 'mipi_csi2': ['mipi_csi2_interface'], 'mipi_dsi': ['mipi_dsi_interface'], 'lvds': ['lvds_interface'], 'gpio': ['gpio_port'], 'pwm': ['pwm_output'], 'adc': ['analog_input'], 'dac': ['analog_output'], 'mqtt_sn': ['wireless_interface'], 'coap': ['ethernet_or_wireless_interface'], 'http': ['ethernet_or_wireless_interface'], 'websocket': ['ethernet_or_wireless_interface'], 'amqp': ['ethernet_or_wireless_interface'], 'wifi': ['wireless_interface'], 'bluetooth_le': ['wireless_interface'], 'zigbee': ['wireless_interface'], 'thread': ['wireless_interface'], 'matter': ['ethernet_or_wireless_interface'], 'lorawan': ['wireless_interface'], 'lte_m': ['wireless_interface'], 'nb_iot': ['wireless_interface'], '5g': ['wireless_interface'], 'uwb': ['wireless_interface'], 'nfc': ['wireless_interface'], 'rfid': ['wireless_interface'], 'profisafe': ['ethernet_or_profibus_interface'], 'cip_safety': ['ethernet_or_can_interface'], 'fsoe': ['ethercat_port'], 'opensafety': ['generic_network_interface'], 'generic_serial': ['serial_port'], 'generic_can': ['can_controller'], 'generic_ethernet': ['ethernet_port'], 'custom_udp': ['ethernet_or_wireless_interface'], 'custom_tcp': ['ethernet_or_wireless_interface'], 'custom_binary': ['generic_network_interface'], 'custom_text': ['generic_network_interface'], 'custom_protocol': ['generic_network_interface']}

# Source-supported explicit legacy bindings; defaults remain industry neutral.
EXPLICIT_STACK_VARIANTS = {'ip': [['ethernet', 'ip']], 'udp': [['ethernet', 'ip', 'udp']], 'tcp': [['ethernet', 'ip', 'tcp']], 'canopen': [['can', 'canopen']], 'j1939': [['can', 'j1939']], 'isobus': [['can', 'j1939', 'isobus']], 'uds': [['can', 'uds']], 'xcp': [['can', 'xcp']], 'ccp': [['can', 'ccp']], 'someip': [['ethernet', 'ip', 'udp', 'someip']], 'someip_sd': [['ethernet', 'ip', 'udp', 'someip_sd']], 'doip': [['ethernet', 'ip', 'tcp', 'doip']], 'obd2': [['can', 'uds', 'obd2']], 'avb': [['ethernet', 'avb']], 'tsn': [['ethernet', 'tsn']], 'profinet': [['ethernet', 'profinet']], 'ethercat': [['ethernet', 'ethercat']], 'ethernet_ip': [['ethernet', 'ip', 'udp', 'ethernet_ip']], 'modbus_tcp': [['ethernet', 'ip', 'tcp', 'modbus_tcp']], 'modbus_rtu': [['modbus_rtu']], 'modbus_ascii': [['modbus_ascii']], 'devicenet': [['can', 'devicenet']], 'cc_link_ie': [['ethernet', 'cc_link_ie']], 'sercos_iii': [['ethernet', 'sercos_iii']], 'powerlink': [['ethernet', 'powerlink']], 'opc_ua': [['ethernet', 'ip', 'tcp', 'opc_ua']], 'opc_ua_pubsub': [['ethernet', 'ip', 'udp', 'opc_ua_pubsub']], 'mqtt': [['ethernet', 'ip', 'tcp', 'mqtt']], 'sparkplug_b': [['ethernet', 'ip', 'tcp', 'mqtt', 'sparkplug_b']], 'dds': [['ethernet', 'ip', 'udp', 'dds']], 'ros2': [['ethernet', 'ip', 'udp', 'dds', 'ros2']], 'afdx': [['ethernet', 'ip', 'udp', 'afdx']], 'can_aerospace': [['can', 'can_aerospace']], 'tte': [['ethernet', 'tte']], 'etb': [['ethernet', 'etb']], 'trdp': [['ethernet', 'ip', 'udp', 'trdp']], 'nmea2000': [['can', 'nmea2000']], 'bacnet_ip': [['ethernet', 'ip', 'udp', 'bacnet_ip']], 'bacnet_sc': [['ethernet', 'ip', 'tcp', 'bacnet_sc']], 'knx_ip': [['ethernet', 'ip', 'udp', 'knx_ip']], 'iec61850': [['ethernet', 'iec61850']], 'mms': [['ethernet', 'ip', 'tcp', 'mms']], 'goose': [['ethernet', 'goose']], 'sampled_values': [['ethernet', 'sampled_values']], 'iec60870_5_104': [['ethernet', 'ip', 'tcp', 'iec60870_5_104']], 'sunspec_modbus': [['modbus_tcp', 'sunspec_modbus']], 'ocpp': [['ethernet', 'ip', 'tcp', 'ocpp']], 'coap': [['ethernet', 'ip', 'udp', 'coap']], 'http': [['ethernet', 'ip', 'tcp', 'http']], 'websocket': [['ethernet', 'ip', 'tcp', 'websocket']], 'amqp': [['ethernet', 'ip', 'tcp', 'amqp']], 'fsoe': [['ethernet', 'ethercat', 'fsoe']], 'custom_udp': [['ethernet', 'ip', 'udp', 'custom_udp']], 'custom_tcp': [['ethernet', 'ip', 'tcp', 'custom_tcp']]}


def technology_definitions() -> list[dict[str, Any]]:
    definitions = [_spec(*row) for row in ROWS]
    by_id = {profile['id']: profile for profile in definitions}
    by_id['can_aerospace']['parameter_constraints'].extend(
        item for item in by_id['can']['parameter_constraints'] if item['parameter'] != 'payload_bytes')
    by_id['can_fd']['parameter_constraints'].extend(
        {**item,'parameter':'nominal_bitrate_bps' if item['parameter']=='bitrate_bps' else item['parameter']}
        for item in by_id['can']['parameter_constraints'] if item['parameter'] != 'payload_bytes')
    for profile in definitions:
        rate_profile = profile
        if profile.get('rate_source_profile_id'):
            rate_id=profile['rate_source_profile_id']
            if rate_id not in profile['default_stack'] or rate_id not in by_id:
                raise ValueError(f"{profile['id']}: rate source must be an explicitly registered stack layer")
            rate_profile=by_id[rate_id]
        elif not (profile.get('rate_model') or {}).get('fields'):
            rate_profile = next((by_id[layer] for layer in profile['default_stack']
                                 if by_id[layer]['rate_model'].get('fields')), profile)
        review = _parameter_defaults_review(profile['id'], rate_profile)
        fields = _parameter_form_schema(profile['id'], profile, rate_profile, review)
        profile['parameter_schema'] = {
            PARAMETER_CORE_ALIASES.get(item['key'], item['key']): {
                key: value for key, value in item.items() if key != 'key'
            } for item in fields
        }
    return definitions


def _parameter_form_schema(technology_id: str, technology: dict[str, Any], rate_source: dict[str, Any], review: dict[str, Any]) -> list[dict[str, Any]]:
    """Describe editable parameters so the UI does not hard-code technology forms."""
    if technology_id == 'generic_ethernet':
        # Explicit shared IEEE 802.3 schema; this branch is never selected for
        # another transport. Fresh dictionaries retain independent identities.
        return _parameter_form_schema('ethernet',
            {**technology,'id':'ethernet','default_stack':['ethernet']},
            {**rate_source,'id':'ethernet'},review)
    maximum_payload = int(technology.get("max_payload_bytes") or 65_535)

    def field(
        key: str,
        label: str,
        category: str,
        scope: str,
        *,
        field_type: str = "number",
        unit: str | None = None,
        default: Any = None,
        minimum: float | None = None,
        maximum: float | None = None,
        options: list[str] | None = None,
        description: str = "",
        simulation_relevant: bool = True,
        validation_relevant: bool = True,
    ) -> dict[str, Any]:
        item: dict[str, Any] = {
            "key": key,
            "label": label,
            "category": category,
            "scope": scope,
            "type": field_type,
            "description": description,
            "required": True,
            "editable": True,
            "simulation_relevant": simulation_relevant,
            "validation_relevant": validation_relevant,
        }
        if default is not None:
            item["default"] = default
        if unit:
            item["unit"] = unit
        if minimum is not None:
            item["min"] = minimum
        if maximum is not None:
            item["max"] = maximum
        if options:
            item["options"] = options
        return item

    rate_model = rate_source.get("rate_model") or {}
    inherited_rate = rate_source['id'] != technology_id
    defaults = review['values']
    rate_type = rate_model.get("type")
    rate_fields: list[dict[str, Any]] = []
    if rate_type in {"SINGLE_BITRATE", "ETHERNET_LINK_RATE", "FIXED_LINK_RATE"}:
        ethernet_stack = 'ethernet' in {technology_id, *(technology.get('default_stack') or [])}
        label = "Ethernet Link Speed" if inherited_rate and ethernet_stack else (
            "Link Speed" if rate_type == "ETHERNET_LINK_RATE" or ethernet_stack else "Bitrate"
        )
        rate_fields.append(field(
            "bitrate", label, "physical", "network", unit="bit/s",
            minimum=rate_model.get("minimum_bps", 1),
            maximum=rate_model.get("maximum_bps"),
            default=defaults.get('bitrate_bps'),
            description=("Inherited physical link rate from the declared technology stack."
                         if inherited_rate else "Technology-profiled network rate."),
        ))
    elif rate_type == "MULTI_PHASE_BITRATE":
        rate_fields.extend([
            field("arbitration_bitrate", "Nominal Bitrate", "physical", "network", unit="bit/s", minimum=1, maximum=rate_model.get("nominal_maximum_bps"), default=defaults.get("nominal_bitrate_bps")),
            field("data_bitrate", "Data Bitrate", "physical", "network", unit="bit/s", minimum=1, maximum=rate_model.get("data_maximum_bps"), default=defaults.get("data_bitrate_bps")),
        ])
    elif rate_type == "I2C_CONFIRMED_CLOCK":
        rate_fields.append(field(
            "bitrate", "I²C Bus Clock", "physical", "network", unit="bit/s",
            minimum=rate_model.get("minimum_bps", 1),
            maximum=rate_model.get("maximum_bps"),
            default=defaults.get('bitrate_bps'),
            description="Controller mode and confirmed bus clock are required; no unreviewed rate is assumed.",
        ))
    elif rate_type == "DEVICE_DEPENDENT_CLOCK":
        rate_fields.append(field(
            "bitrate", "SPI Device Clock", "physical", "network", unit="bit/s",
            minimum=rate_model.get("minimum_bps", 1),
            maximum=rate_model.get("maximum_bps"),
            description="The connected device datasheet must supply the clock limit; no profile default is assumed.",
        ))
    for rate_field in rate_fields:
        rate_field['default_review'] = review
        rate_field['allowed_bps'] = rate_model.get('allowed_bps') or ([rate_model['fixed_bps']] if rate_model.get('fixed_bps') else [])
    fields: list[dict[str, Any]] = [
        *rate_fields,
        field("payload_bytes", "Payload", "physical", "message", unit="Byte", minimum=0, maximum=maximum_payload, default=min(8, maximum_payload), description="Nutzdaten pro Nachricht."),
        field("cycle_ms", "Cycle Time", "timing", "message", unit="ms", minimum=0.001, default=100, description="Standardperiode fuer zyklische Nachrichten."),
        field("minimum_cycle_time_ms", "Minimum Cycle Time", "timing", "message", unit="ms", minimum=0.001, default=1),
        field("deadline_ms", "Deadline", "timing", "message", unit="ms", minimum=0.001, default=100),
        field("timeout_ms", "Timeout", "timing", "route", unit="ms", minimum=0.001, default=500),
        field("maximum_latency_ms", "Maximum Latency", "timing", "route", unit="ms", minimum=0, default=100),
        field("jitter_ms", "Jitter Budget", "timing", "route", unit="ms", minimum=0, default=1),
        field("freshness_ms", "Data Freshness", "timing", "signal", unit="ms", minimum=0, default=500),
        field("source_processing_delay_ms", "Source Processing", "timing", "route", unit="ms", minimum=0, default=0.1),
        field("target_processing_delay_ms", "Target Processing", "timing", "route", unit="ms", minimum=0, default=0.1),
        field("propagation_delay_ms", "Propagation", "timing", "network", unit="ms", minimum=0, default=0.01),
        field("target_bus_load_percent", "Ziel-Buslast", "capacity", "analysis", unit="%", minimum=0, maximum=100, default=60, description="Zielwert fuer die aus Routing, Payload, Zyklus und Bitrate berechnete Buslast.", simulation_relevant=False),
        field("peak_factor", "Peak Factor", "capacity", "analysis", minimum=1, default=1.15, simulation_relevant=False),
        field("burst_factor", "Burst Factor", "capacity", "analysis", minimum=1, default=1.5, simulation_relevant=False),
        field("burst_window_ms", "Burst Window", "capacity", "analysis", unit="ms", minimum=0.1, default=100, simulation_relevant=False),
        field("warning_threshold", "Load Warning", "capacity", "analysis", unit="%", minimum=0, maximum=100, default=60, simulation_relevant=False),
        field("critical_threshold", "Load Critical", "capacity", "analysis", unit="%", minimum=0, maximum=100, default=75, simulation_relevant=False),
        field("overload_threshold", "Load Overload", "capacity", "analysis", unit="%", minimum=1, maximum=100, default=90, simulation_relevant=False),
        field("queue_size", "Queue Size", "qos", "network", unit="Frames", minimum=1, default=256),
        field("queue_policy", "Queue Policy", "qos", "network", field_type="select", default="FIFO", options=["FIFO", "PRIORITY", "STRICT_PRIORITY", "WEIGHTED_PRIORITY", "WRR", "ROUND_ROBIN", "TIME_TRIGGERED", "TAS", "CBS", "CUSTOM"]),
        field("qos_priority", "Default Priority", "qos", "route", minimum=0, maximum=7, default=3),
        field("traffic_class", "Traffic Class", "qos", "route", field_type="select", default="BEST_EFFORT", options=["BEST_EFFORT", "CONTROL", "REALTIME", "SAFETY_CRITICAL"]),
        field("reserved_bandwidth_percent", "Reserved Bandwidth", "qos", "network", unit="%", minimum=0, maximum=100, default=0),
        field("packet_loss_probability", "Packet Loss", "reliability", "reliability", minimum=0, maximum=1, default=0),
        field("frame_loss_probability", "Frame Loss", "reliability", "reliability", minimum=0, maximum=1, default=0),
        field("bit_error_rate", "Bit Error Rate", "reliability", "reliability", minimum=0, maximum=1, default=0),
        field("corruption_probability", "Corruption", "reliability", "reliability", minimum=0, maximum=1, default=0),
        field("duplicate_probability", "Duplication", "reliability", "reliability", minimum=0, maximum=1, default=0),
        field("reordering_probability", "Reordering", "reliability", "reliability", minimum=0, maximum=1, default=0),
        field("retransmission_enabled", "Retransmission", "reliability", "reliability", field_type="boolean", default=False),
        field("retransmission_rate", "Retransmission Rate", "reliability", "reliability", minimum=0, maximum=1, default=0),
        field("retry_limit", "Retry Limit", "reliability", "reliability", minimum=0, default=0),
        field("retransmission_delay_ms", "Retry Delay", "reliability", "reliability", unit="ms", minimum=0, default=0),
        field("required_reliability", "Required Reliability", "reliability", "reliability", minimum=0, maximum=1, default=0.999),
        field("clock_offset_ms", "Clock Offset", "synchronization", "network", unit="ms", default=0),
        field("clock_drift_ppm", "Clock Drift", "synchronization", "network", unit="ppm", minimum=0, default=20),
        field("sync_precision_ms", "Sync Precision", "synchronization", "network", unit="ms", minimum=0, default=0.1),
        field("sync_interval_ms", "Sync Interval", "synchronization", "network", unit="ms", minimum=0.001, default=1000),
        field("sync_method", "Sync Method", "synchronization", "network", field_type="select", default="NONE", options=["NONE", "NTP", "PTP", "GPTP", "BUS_NATIVE"]),
        field("maximum_sync_error_ms", "Maximum Sync Error", "synchronization", "network", unit="ms", minimum=0, default=1),
        field("gateway_delay_ms", "Gateway Processing", "gateway", "gateway", unit="ms", minimum=0, default=0.2),
        field("gateway_queue_delay_ms", "Gateway Queueing", "gateway", "gateway", unit="ms", minimum=0, default=0),
        field("protocol_conversion_delay_ms", "Protocol Conversion", "gateway", "gateway", unit="ms", minimum=0, default=0),
        field("gateway_maximum_throughput", "Gateway Throughput", "gateway", "gateway", unit="bit/s", minimum=1, default=100_000_000),
        field("gateway_input_buffer", "Gateway Input Buffer", "gateway", "gateway", unit="Frames", minimum=1, default=256),
        field("gateway_output_buffer", "Gateway Output Buffer", "gateway", "gateway", unit="Frames", minimum=1, default=256),
        field("gateway_maximum_routes", "Gateway Maximum Routes", "gateway", "gateway", minimum=1, default=10_000),
        field("gateway_maximum_messages_s", "Gateway Messages per Second", "gateway", "gateway", unit="msg/s", minimum=1, default=100_000),
        field("duration_s", "Simulation Duration", "simulation", "simulation", unit="s", minimum=0.001, default=1, validation_relevant=False),
        field("seed", "Random Seed", "simulation", "simulation", minimum=0, default=42, validation_relevant=False),
        field("max_events", "Maximum Events", "simulation", "simulation", minimum=1, default=100_000, validation_relevant=False),
        field("dropout_probability", "Failure Injection Dropout", "simulation", "simulation", minimum=0, maximum=1, default=0, validation_relevant=False),
    ]
    normalized = technology_id.lower()
    if normalized in {"can_fd", "can_xl"}:
        fields.append(field("sample_point_percent", "Sample Point", "physical", "network", unit="%", minimum=50, maximum=99.9, default=80))
    if 'ethernet' in {technology_id, *(technology.get('default_stack') or [])}:
        fields.extend(
            [
                field("mtu_bytes", "MTU", "physical", "network", unit="Byte", minimum=64, maximum=65_535, default=1500),
                field("duplex", "Duplex", "physical", "network", field_type="select", default="FULL", options=["FULL", "HALF"]),
                field("vlan_id", "VLAN ID", "qos", "network", minimum=0, maximum=4094, default=0),
                field("rate_limit_bit_s", "Rate Limit", "qos", "route", unit="bit/s", minimum=0, default=0),
            ]
        )
    if normalized in {"dds", "dds_rtps", "ros2"}:
        fields.extend(
            [
                field("history_depth", "History Depth", "qos", "route", minimum=1, default=10),
                field("history_kind", "History", "qos", "route", field_type="select", default="KEEP_LAST", options=["KEEP_LAST", "KEEP_ALL"]),
                field("durability", "Durability", "qos", "route", field_type="select", default="VOLATILE", options=["VOLATILE", "TRANSIENT_LOCAL", "TRANSIENT", "PERSISTENT"]),
                field("lifespan_ms", "Lifespan", "timing", "message", unit="ms", minimum=0, default=0),
                field("liveliness", "Liveliness", "qos", "route", field_type="select", default="AUTOMATIC", options=["AUTOMATIC", "MANUAL_BY_PARTICIPANT", "MANUAL_BY_TOPIC"]),
                field("reliability_mode", "Reliability Mode", "reliability", "route", field_type="select", default="RELIABLE", options=["BEST_EFFORT", "RELIABLE"]),
            ]
        )
    if "ethercat" in normalized:
        fields.append(field("distributed_clock_cycle_ms", "Distributed Clock Cycle", "synchronization", "network", unit="ms", minimum=0.001, default=1))
    rate_keys = {item["key"] for item in rate_fields}
    for item in fields:
        item["required"] = item["key"] in rate_keys
        item["parameter_origin"] = "TRANSPORT_PROFILE" if item["key"] in rate_keys else "NIS_SCENARIO"
        item["default_status"] = "PROPOSED" if "default" in item else "UNKNOWN"
        item["source"] = review["source"] if item["key"] in rate_keys else "docs/COMMUNICATION_DESIGN_CONTRACT.md"
        item["source_revision"] = review.get("source_revision") if item["key"] in rate_keys else "NIS_SCENARIO_POLICY_V1"
    if technology_id == 'ethernet':
        source=REVIEW_RATE_PROPOSALS['ethernet']
        removed={'reserved_bandwidth_percent','sync_method','retransmission_enabled','retransmission_rate','retry_limit',
                 'retransmission_delay_ms','gateway_maximum_throughput','gateway_input_buffer','gateway_output_buffer',
                 'gateway_maximum_routes','gateway_maximum_messages_s'}
        fields=[item for item in fields if item['key'] not in removed]
        for item in fields:
            key=item['key']
            if key in {'payload_bytes','mtu_bytes','duplex','vlan_id','qos_priority','rate_limit_bit_s'}:
                item.pop('default',None)
                item.update(default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',source=source['source'],
                            source_revision=source['source_revision'],simulation_relevant=False)
                if key!='duplex': item['integer']=True
                if key=='payload_bytes':
                    item.pop('max',None)
                    item['description']='Actual selected MAC-client or upper-layer octets. Upper headers, padding, VLAN tags and FCS are separate; no universal8-byte payload.'
                if key=='mtu_bytes':
                    item.update(min=1)
                    item.pop('max',None)
                    item.update(conditional_defaults=[{'when':{'eth_frame_profile':'BASIC_MAC'},'value':1500}],
                                default_status='PROPOSED_CONDITIONAL',description='MAC-client octet limit, not IP MTU or whole frame. BASIC_MAC max1500; jumbo requires actual matched endpoints and path source.')
                if key=='duplex':
                    item['description']='Actual negotiated or consistently forced duplex, unknown. HALF uses collision access; cannot inherit full-duplex FIFO proof.'
                if key=='vlan_id':
                    item['description']='Actual tag VID0 is priority-only,1..4094 assigned VLAN,4095 reserved. Untagged has no VID; no invented VLAN0.'
                if key=='qos_priority':
                    item['description']='Actual IEEE802.1Q PCP integer0..7 only for tags; no default3 or automatic queue mapping, reservation, CBS/TAS.'
                if key=='rate_limit_bit_s':
                    item['description']='Actual configured policer/shaper bit rate;0 means explicitly disabled, not absence. Byte-accounting/burst/queue source required for timing.'
            if key=='queue_policy': item['options']=['FIFO','CUSTOM']
            if key in {'queue_size','gateway_count'}: item['integer']=True
        for key,label,kind,unit,options,minimum,maximum,default in (
            ('eth_phy','Actual selected Ethernet PHY','select',None,['10BASE_T','100BASE_TX','1000BASE_T','2_5GBASE_T','5GBASE_T','10GBASE_T','10BASE_T1S','100BASE_T1','1000BASE_T1','DEVICE_SPECIFIC'],None,None,'10BASE_T'),
            ('eth_device_source','Actual PHY/MAC hardware revision and capabilities','text',None,None,None,None,None),
            ('eth_topology_source','Actual per-direction ports/cabling/forwarding path','text',None,None,None,None,None),
            ('eth_frame_profile','MAC frame size profile','select',None,['BASIC_MAC','JUMBO_DEVICE'],None,None,'BASIC_MAC'),
            ('eth_frame_format','Actual length/type interpretation','select',None,['ETHERTYPE','LENGTH_LLC'],None,None,None),
            ('eth_payload_layer','Actual octet measurement boundary','select',None,['MAC_CLIENT','UPPER_LAYER'],None,None,'MAC_CLIENT'),
            ('eth_upper_header_bytes','Actual headers within MAC client','number','Byte',None,0,None,None),
            ('eth_header_source','Actual higher-layer/LLC headers and encapsulation source','text',None,None,None,None,None),
            ('eth_client_bytes','Actual full MAC-client bytes before pad','number','Byte',None,0,None,None),
            ('eth_pad_bytes','Actual minimum-frame padding','number','Byte',None,0,46,None),
            ('eth_tag_mode','Actual tag layout','select',None,['UNTAGGED','PRIORITY','VLAN','STACKED_DEVICE'],None,None,None),
            ('eth_vlan_tags','Actual tag count','number',None,None,0,2,None),
            ('eth_dei','Actual tag drop-eligibility bit','boolean',None,None,None,None,None),
            ('eth_type_length','Actual innermost type/length16-bit field','number',None,None,0,65535,None),
            ('eth_source_mac','Actual sender48-bit MAC','text',None,None,None,None,None),
            ('eth_destination_mac','Actual unicast/multicast/broadcast48-bit MAC','text',None,None,None,None,None),
            ('eth_mac_frame_bytes','Actual frame including FCS, excluding preamble/IFG','number','Byte',None,64,None,None),
            ('eth_wire_slot_bytes','Actual MAC frame+preamble/SFD+IFG','number','Byte',None,84,None,None),
            ('eth_ifg_bits','Actual transmit inter-frame gap','number','bit',None,96,None,96),
            ('eth_peer_rate_bps','Actual peer negotiated rate','number','bit/s',None,1,None,None),
            ('eth_peer_duplex','Actual peer duplex','select',None,['FULL','HALF'],None,None,None),
            ('eth_autoneg_enabled','Actual PHY auto-negotiation enabled','boolean',None,None,None,None,None),
            ('eth_autoneg_complete','Actual auto-negotiation completed','boolean',None,None,None,None,None),
            ('eth_link_up','Actual operational link state','boolean',None,None,None,None,None),
            ('eth_negotiation_source','Actual advertised/resolved peer capabilities and status','text',None,None,None,None,None),
            ('eth_pause_rx','Actual MAC reaction to received PAUSE','boolean',None,None,None,None,None),
            ('eth_pause_tx','Actual transmitted PAUSE enabled','boolean',None,None,None,None,None),
            ('eth_pause_quanta','Actual PAUSE timer512-bit quanta','number',None,None,0,65535,None),
            ('eth_pause_time_us','Actual PAUSE timer at selected link rate','number','us',None,0,None,None),
            ('eth_flow_bound_us','Actual aggregate flow-control blocking bound','number','us',None,0,None,None),
            ('eth_flow_source','Actual PAUSE/PFC/backpressure admission/burst proof','text',None,None,None,None,None),
            ('eth_backpressure','Actual half-duplex collision backpressure','boolean',None,None,None,None,None),
            ('eth_collision_slot_bits','Actual CSMA/CD collision slot','number','bit',None,512,4096,None),
            ('eth_attempt_limit','Actual device MAC transmission attempt budget','number',None,None,1,None,None),
            ('eth_backoff_limit','Actual device MAC exponential backoff limit','number',None,None,0,None,None),
            ('eth_collision_source','Actual collision domain/backoff/retry/extension model','text',None,None,None,None,None),
            ('eth_plca_enabled','Actual10BASE-T1S PLCA enabled','boolean',None,None,None,None,None),
            ('eth_plca_active','Actual PLCA beacon status','boolean',None,None,None,None,None),
            ('eth_plca_id','Actual PLCA LocalID','number',None,None,0,255,None),
            ('eth_plca_count','Actual coordinator transmit-opportunity count','number',None,None,1,255,None),
            ('eth_plca_to_bits','PLCA transmit opportunity timer','number','bit',None,0,255,None),
            ('eth_plca_burst_count','Actual additional frames per opportunity','number',None,None,0,255,None),
            ('eth_plca_burst_bits','Actual PLCA burst timer','number','bit',None,0,255,None),
            ('eth_plca_source','Actual revision/coordinator/uniqueID/delay/opportunity map','text',None,None,None,None,None),
            ('eth_eee_enabled','Actual energy-efficient Ethernet LPI enabled','boolean',None,None,None,None,None),
            ('eth_eee_wake_us','Actual PHY LPI wake bound','number','us',None,0,None,None),
            ('eth_eee_sleep_us','Actual PHY LPI sleep bound','number','us',None,0,None,None),
            ('eth_eee_source','Actual negotiated LPI mode and PHY timing source','text',None,None,None,None,None),
            ('eth_forwarding_mode','Actual forwarding behavior','select',None,['ENDPOINT','STORE_FORWARD','CUT_THROUGH','DEVICE_SPECIFIC'],None,None,None),
            ('eth_forwarding_bound_us','Actual forwarding/processing bound','number','us',None,0,None,None),
            ('eth_queue_source','Actual TX queue capacity/priority mapping/traffic source','text',None,None,None,None,None),
            ('eth_policing_source','Actual byte accounting/burst/policer/shaper source','text',None,None,None,None,None),
        ):
            native=field(key,label,'timing' if unit=='us' else 'physical','network',field_type=kind,unit=unit,
                         options=options,minimum=minimum,maximum=maximum,default=default,simulation_relevant=False)
            native.update(required=False,integer=kind=='number' and unit!='us',
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN',source=source['source'],source_revision=source['source_revision'],
                          description='Ethernet declaration. Installed link/queue/device evidence is separate; source-qualified proposals never confirm physical or E2E capacity.')
            if key in {'eth_source_mac','eth_destination_mac'}:
                native['pattern']=r'[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}'
            if key=='eth_source_mac':
                native['pattern']=r'[0-9A-Fa-f][02468AaCcEe](?::[0-9A-Fa-f]{2}){5}'
                native['forbidden_values']=['00:00:00:00:00:00']
            if key=='eth_destination_mac': native['forbidden_values']=['00:00:00:00:00:00']
            if key=='eth_wire_slot_bytes':
                native.update(integer=False,description='Equivalent octets of MAC+preamble/SFD+actual bit gap. Non-octet-multiple IFG yields a fractional octet count; calculator uses exact bit count.')
            if key=='eth_upper_header_bytes':
                native.update(conditional_defaults=[{'when':{'eth_payload_layer':'MAC_CLIENT'},'value':0}],default_status='PROPOSED_CONDITIONAL')
            if key.startswith('eth_plca_'):
                native.update(source='https://ww1.microchip.com/downloads/aemDocuments/documents/AIS/ProductDocuments/DataSheets/LAN8670-1-2-Data-Sheet-60001573.pdf',
                              source_revision='LAN8670/1/2 DS60001573K 2025 sections4.8/5.4.74..78; PLCA optional, ID255 disabled, register/default revision distinctions')
            if key=='eth_plca_to_bits':
                native.update(conditional_defaults=[{'when':{'eth_phy':'10BASE_T1S','eth_plca_enabled':True},'value':32}],default_status='PROPOSED_CONDITIONAL',
                              description='IEEE802.3-2022 Clause30.16.1.1.5 baseline32BT, not historicalOA1.0 value24; identical across actual mixing segment.100ns perBT at10M, actual delay evaluation required for change.')
            if key=='eth_pause_time_us':
                native.update(source='https://ww1.microchip.com/downloads/en/DeviceDoc/00002268B.pdf',source_revision='LAN9116 DS00002268B sections3.2.1/5.4.8 PAUSE512-bit quanta; aggregateblocking separate')
            if key in {'eth_pause_rx','eth_pause_tx','eth_flow_source','eth_eee_source','eth_forwarding_mode','eth_queue_source','eth_policing_source'}:
                native.update(source='https://www.microchip.com/content/dam/mchp/documents/UNG/ProductDocuments/DataSheets/LAN9645xF-Data-Sheet-DS00006065.pdf',
                              source_revision='LAN9645xF DS00006065C 2026 sections4.7/4.13/4.14; device-dependent features, not universal defaults')
            fields.append(native)
    if technology_id == 'ethercat':
        source=REVIEW_RATE_PROPOSALS['ethercat']
        removed={'qos_priority','reserved_bandwidth_percent','sync_method','retransmission_enabled','retransmission_rate',
                 'retry_limit','retransmission_delay_ms','gateway_maximum_throughput','gateway_input_buffer',
                 'gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s','rate_limit_bit_s'}
        fields=[item for item in fields if item['key'] not in removed]
        for item in fields:
            key=item['key']
            if key in {'payload_bytes','mtu_bytes','duplex','vlan_id','distributed_clock_cycle_ms'}:
                item.pop('default',None)
                item.update(default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',source=source['source'],
                            source_revision=source['source_revision'],simulation_relevant=False)
                if key in {'payload_bytes','mtu_bytes','vlan_id'}:
                    item['integer']=True
                if key=='payload_bytes':
                    item['description']='Actual selected EtherCAT datagram data; frame aggregate and header overhead are separate. Native<=1486, reviewedUDP/IPv4<=1458.'
                if key=='mtu_bytes':
                    item.update(min=1500,max=1500,default=1500,default_status='PROPOSED',parameter_origin='TRANSPORT_PROFILE',
                                description='Classic MAC-client limit1500B, not TwinCAT MTU1514B includingMACheader/noFCS or datagram1486B.')
                if key=='duplex':
                    item.update(options=['FULL'],default='FULL',default_status='PROPOSED',parameter_origin='TRANSPORT_PROFILE')
                if key=='vlan_id':
                    item.update(min=1,max=4094,description='Actual optionalIEEE802.1Q VLAN ID. ESC accepts tag but doesnot evaluate VLANcontents; no inventedVLAN0 or switched-office reachability.')
                if key=='distributed_clock_cycle_ms':
                    item.update(min=0,description='ActualSYNC0cycle in ms; zero is valid single-shot. No universal1ms cycle, PTPprecision or installedDC capability.')
            if key in {'queue_size','gateway_count'}:
                item['integer']=True
            if key=='queue_policy':
                item['options']=['FIFO','CUSTOM']
        for key,label,kind,unit,options,minimum,maximum,default in (
            ('ecat_transport','Selected classic EtherCAT encapsulation','select',None,['NATIVE_ETHERNET','UDP_IPV4'],None,None,'NATIVE_ETHERNET'),
            ('ecat_phy','Actual classic EtherCAT physical link','select',None,['100BASE_TX','100BASE_FX','EBUS','ETHERCAT_P'],None,None,None),
            ('ecat_esi_source','Actual ESI/SII/ESC variant and configuration source','text',None,None,None,None,None),
            ('ecat_topology_source','Actual MainDevice/ordered ports/loop/cable topology','text',None,None,None,None,None),
            ('ecat_main_device','Actual sole active MainDevice in segment','text',None,None,None,None,None),
            ('ecat_frame_type','EtherCAT header protocol type','number',None,None,1,1,1),
            ('ecat_header_reserved','EtherCAT header reserved bit','number',None,None,0,0,0),
            ('ecat_header_length','Actual header datagram area length','number','Byte',None,12,1498,None),
            ('ecat_datagram_count','Actual datagrams in this frame','number',None,None,1,124,None),
            ('ecat_device_datagram_limit','Actual MainDevice/ESC datagram limit','number',None,None,1,124,None),
            ('ecat_sum_data_bytes','Actual sum of all datagram data','number','Byte',None,0,1486,None),
            ('ecat_datagram_bytes','Actual complete datagram area','number','Byte',None,12,1498,None),
            ('ecat_padding_bytes','Actual MAC padding','number','Byte',None,0,32,None),
            ('ecat_vlan_tags','Actual classic VLAN tag count','number',None,None,0,1,None),
            ('ecat_mac_frame_bytes','Actual MAC frame includingFCS excludingpreamble/IFG','number','Byte',None,64,1522,None),
            ('ecat_wire_slot_bytes','Ethernet wire occupation includingpreamble/IFG','number','Byte',None,84,1542,None),
            ('ecat_udp_port','Selected IPv4 UDP destination port','number',None,None,1,65535,None),
            ('ecat_ipv4_header_bytes','Selected classicIPv4 header length','number','Byte',None,20,20,None),
            ('ecat_command','Actual datagram command','select',None,['NOP','APRD','APWR','APRW','FPRD','FPWR','FPRW','BRD','BWR','BRW','LRD','LWR','LRW','ARMW','FRMW'],None,None,None),
            ('ecat_index','Actual datagram index','number',None,None,0,255,None),
            ('ecat_datagram_length','Actual selected datagram length field','number','Byte',None,0,1486,None),
            ('ecat_datagram_reserved','Datagram reserved bits','number',None,None,0,0,0),
            ('ecat_circulating','Actual circulating-frame bit','boolean',None,None,None,None,None),
            ('ecat_more','Actual more-datagrams bit','boolean',None,None,None,None,None),
            ('ecat_irq','Actual combined event-request bits','number',None,None,0,65535,None),
            ('ecat_addressing','Actual command addressing mode','select',None,['AUTO_INCREMENT','CONFIGURED','BROADCAST','LOGICAL'],None,None,None),
            ('ecat_station_address','Actual position/configured16-bit address field','number',None,None,0,65535,None),
            ('ecat_register_offset','Actual local register/memory offset','number',None,None,0,65535,None),
            ('ecat_logical_address','Actual logical process-image address','number',None,None,0,4294967295,None),
            ('ecat_mapping_source','Actual station/FMMU/SyncManager/PDO mapping','text',None,None,None,None,None),
            ('ecat_expected_wkc','Actual expected working counter','number',None,None,0,65535,None),
            ('ecat_received_wkc','Actual observed working counter','number',None,None,0,65535,None),
            ('ecat_response_accepted','Actual response accepted for application','boolean',None,None,None,None,None),
            ('ecat_sync_mode','Actual application synchronization','select',None,['FREE_RUN','SM_EVENT','DC'],None,None,None),
            ('ecat_dc_supported','Actual DistributedClocks capability','boolean',None,None,None,None,None),
            ('ecat_dc_width','Actual DC width','select',None,['32','64'],None,None,None),
            ('ecat_dc_reference','Actual selected reference clock','text',None,None,None,None,None),
            ('ecat_dc_source','Actual DC support/calibration/synchronization evidence','text',None,None,None,None,None),
            ('ecat_sync_generation','Actual DC signal generation mode','select',None,['CYCLIC_PULSE','SINGLE_SHOT','CYCLIC_ACK','SINGLE_SHOT_ACK'],None,None,None),
            ('ecat_sync0_cycle_ns','Actual SYNC0 cycle register','number','ns',None,0,4294967295,None),
            ('ecat_sync1_delay_ns','Actual SYNC1 delay from SYNC0','number','ns',None,0,4294967295,None),
            ('ecat_sync_pulse_ns','Actual SYNC pulse width','number','ns',None,0,655350,None),
            ('ecat_sync_pulse_register','Actual16-bit pulse width in10ns units','number',None,None,0,65535,None),
            ('ecat_watchdog_divider','Actual shared watchdog divider','number',None,None,0,65535,None),
            ('ecat_register_profile','Actual matching ESC register profile','select',None,['BECKHOFF_3_0','DEVICE_SPECIFIC'],None,None,None),
            ('ecat_pd_watchdog_ticks','Actual process-data watchdog time register','number',None,None,0,65535,None),
            ('ecat_pdi_watchdog_ticks','Actual PDI watchdog time register','number',None,None,0,65535,None),
            ('ecat_pd_watchdog_min_ns','Process-data watchdog approximate earliest timeout','number','ns',None,0,None,None),
            ('ecat_pd_watchdog_max_ns','Process-data watchdog approximate latest timeout','number','ns',None,0,None,None),
            ('ecat_watchdog_source','Actual PD/PDI watchdog configuration and safe reaction','text',None,None,None,None,None),
            ('ecat_state','Actual SubDevice application-layer state','select',None,['INIT','PREOP','SAFEOP','OP','BOOTSTRAP'],None,None,None),
            ('ecat_outputs_active','Actual functional process outputs active','boolean',None,None,None,None,None),
            ('ecat_al_status_code','Actual application-layer error/status code','number',None,None,0,65535,None),
            ('ecat_state_source','Actual acknowledged state/output/error observations','text',None,None,None,None,None),
            ('ecat_mailbox_protocol','Actual configured mailbox protocol','select',None,['COE','FOE','EOE','SOE','AOE','VOE','DEVICE_SPECIFIC'],None,None,None),
            ('ecat_mailbox_bytes','Actual configured mailbox buffer','number','Byte',None,6,65535,None),
            ('ecat_mailbox_data_bytes','Actual mailbox payload after6-byte header','number','Byte',None,0,65529,None),
            ('ecat_mailbox_source','Actual supported mailbox/buffer/timeout profile','text',None,None,None,None,None),
            ('ecat_link_detection','Actual port link-loss detection mode','select',None,['STANDARD','ENHANCED'],None,None,None),
            ('ecat_link_loss_bound_us','Actual PHY link-loss reaction bound','number','us',None,0,None,None),
            ('ecat_link_source','Actual PHY/cable/port/forwarding/reset bounds','text',None,None,None,None,None),
        ):
            native=field(key,label,'timing' if unit in {'ns','us'} else 'physical','route',field_type=kind,unit=unit,
                         options=options,minimum=minimum,maximum=maximum,default=default,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['ethercat']['required_parameters'],integer=kind=='number',
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN',source=source['source'],source_revision=source['source_revision'],
                          description='Classic EtherCAT ESC declaration. Actual ESI/port/map/state/DC/watchdog evidence is separate; EtherCATG/G10 and full E2E capacity are not inferred.')
            if key=='ecat_udp_port':
                native.update(conditional_defaults=[{'when':{'ecat_transport':'UDP_IPV4'},'value':34980}],default_status='PROPOSED_CONDITIONAL')
            if key=='ecat_link_loss_bound_us':
                native['integer']=False
            if key=='ecat_sync_pulse_ns':
                native.update(multiple_of=10,source='https://download.beckhoff.com/download/Document/io/ethercat-development-products/ethercat_esc_datasheet_sec2_registers_3i0.pdf',
                              source_revision='BeckhoffSectionII3.0 table11116-bit register counts10ns; SII/power-on value unknown')
            if key in {'ecat_watchdog_divider','ecat_pd_watchdog_ticks','ecat_pdi_watchdog_ticks'}:
                native.update(conditional_defaults=[{'when':{'ecat_register_profile':'BECKHOFF_3_0'},'value':2498 if key=='ecat_watchdog_divider' else 1000}],
                              default_status='PROPOSED_CONDITIONAL',source='https://download.beckhoff.com/download/Document/io/ethercat-development-products/ethercat_esc_datasheet_sec2_registers_3i0.pdf',
                              source_revision='BeckhoffESCregistersSectionII3.0 tables57..59 resetvalues; actualSII/ESI/runtimeconfiguration separate')
            fields.append(native)
    if technology_id == 'etb':
        source=REVIEW_RATE_PROPOSALS['etb']
        ttdp_source='https://docs.westermo.com/weos/5/Train/ttdp/'
        mac_source='https://www.ieee802.org/3/frame_study/0409/daines_3_0409.pdf'
        removed={'qos_priority','reserved_bandwidth_percent','sync_method','retransmission_enabled','retransmission_rate',
                 'retry_limit','retransmission_delay_ms','gateway_maximum_throughput','gateway_input_buffer',
                 'gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s'}
        fields=[item for item in fields if item['key'] not in removed]
        for item in fields:
            key=item['key']
            if key=='bitrate':
                item.update(conditional_defaults=[{'when':{'etb_phy':phy},'value':rate}
                            for phy,rate in (('100BASE_TX',100000000),('1000BASE_T',1000000000))])
            if key in {'payload_bytes','mtu_bytes','duplex','vlan_id','rate_limit_bit_s'}:
                item.pop('default',None)
                item.pop('max',None)
                item.update(default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                            source=ttdp_source,source_revision='WeOS5 TTDP and ETBN port settings accessed2026-10-01')
                if key in {'payload_bytes','mtu_bytes','vlan_id','rate_limit_bit_s'}:
                    item['integer']=True
                if key=='mtu_bytes':
                    item.update(min=1,source=mac_source,source_revision='IEEE802.3 FESG 30September2004 existing basic MAC frame, pages3/5/6',
                                conditional_defaults=[{'when':{'etb_frame_profile':'BASIC_MAC'},'value':1500}],default_status='PROPOSED_CONDITIONAL',
                                description='Selected MAC-client payload limit, not IP MTU or complete application message; actual peer limit and frame profile required.')
                if key=='payload_bytes':
                    item.update(description='Actual MAC-client data octets excluding MAC header/FCS/padding; not complete TRDP/IP application data.',source=mac_source)
                if key=='vlan_id':
                    item.update(min=1,max=4094,description='Actual configured backbone VLAN, distinct from TTDP topology VLAN492 and ECN VLAN/interface mapping. No invented VLAN0.')
                if key=='duplex':
                    item.update(conditional_defaults=[{'when':{'etb_phy':phy},'value':'FULL'} for phy in ('100BASE_TX','1000BASE_T')],
                                default_status='PROPOSED_CONDITIONAL',source=source['source'])
                if key=='rate_limit_bit_s':
                    item.update(min=0,description='Actual configured port policer limit; zero only explicitly declared disabled. Not a generic unknown-rate fallback.')
            if key in {'queue_size','gateway_count'}:
                item['integer']=True
            if key=='queue_policy':
                item['options']=['FIFO','PRIORITY','CUSTOM']
        for key,label,kind,unit,options,minimum,maximum,default in (
            ('etb_edition','Actual ETB edition','select',None,['IEC_2014','DEVICE_SPECIFIC'],None,None,None),
            ('etb_phy','Selected ETB PHY','select',None,['100BASE_TX','1000BASE_T','DEVICE_SPECIFIC'],None,None,'100BASE_TX'),
            ('etb_node_role','Actual ETB endpoint role','select',None,['ETBN','END_DEVICE','DEVICE_SPECIFIC'],None,None,None),
            ('etb_configuration_source','Actual edition/device/firmware configuration','text',None,None,None,None,None),
            ('etb_physical_binding','Actual backbone port/cabling/bypass profile','text',None,None,None,None,None),
            ('etb_implementation','Actual ETB implementation','select',None,['WEOS_5','DEVICE_SPECIFIC'],None,None,None),
            ('etb_frame_profile','Selected MAC frame profile','select',None,['BASIC_MAC','DEVICE_SPECIFIC'],None,None,'BASIC_MAC'),
            ('etb_local_id','Actual static ETBN position in consist','number',None,None,1,None,None),
            ('etb_ecn_id','Actual attached consist network ID','number',None,None,1,None,None),
            ('etb_backbone_id','Actual backbone purpose ID','number',None,None,0,None,None),
            ('etb_dir1_ports','Actual direction1 redundant port count','number',None,None,0,None,None),
            ('etb_dir2_ports','Actual direction2 redundant port count','number',None,None,0,None,None),
            ('etb_aggregation','Actual link aggregation mechanism','select',None,['TTDP_ACTIVE_STANDBY','DEVICE_SPECIFIC'],None,None,None),
            ('etb_active_links_per_direction','Actual simultaneously active data links per direction','number',None,None,0,None,None),
            ('etb_topology_vlan','Actual TTDP topology signalling VLAN','number',None,None,1,4094,None),
            ('etb_igmp_snooping','Actual backbone IGMP snooping enabled','boolean',None,None,None,None,None),
            ('etb_consist_uuid','Actual consist UUID','text',None,None,None,None,None),
            ('etb_etbn_mac','Actual ETBN MAC address','text',None,None,None,None,None),
            ('etb_topology_counter','Actual current etbTopoCnt value','text',None,None,None,None,None),
            ('etb_message_topology_counter','Actual message etbTopoCnt value','text',None,None,None,None,None),
            ('etb_inauguration','Actual inauguration state','select',None,['PENDING','INAUGURATED','FAILED'],None,None,None),
            ('etb_inhibition','Actual inauguration inhibition','boolean',None,None,None,None,None),
            ('etb_traffic_enabled','Actual ETB application traffic enabled','boolean',None,None,None,None,None),
            ('etb_traffic_scope','Actual application traffic scope','select',None,['INTRA_CONSIST','INTER_CONSIST'],None,None,None),
            ('etb_state_source','Actual inauguration/topology/traffic state evidence','text',None,None,None,None,None),
            ('etb_topology_source','Actual ordered consist/ETBN/ECN topology mapping','text',None,None,None,None,None),
            ('etb_hello_period_ms','Actual TTDP HELLO period','number','ms',None,0.001,None,None),
            ('etb_hello_timeout_ms','Actual TTDP HELLO neighbour-loss timeout','number','ms',None,0.001,None,None),
            ('etb_topology_period_ms','Actual TTDP TOPOLOGY period','number','ms',None,0.001,None,None),
            ('etb_link_recovery_bound_ms','Actual link/bypass/failover upper bound','number','ms',None,0,None,None),
            ('etb_ip_address','Actual topology-assigned IPv4/IPv6 address','text',None,None,None,None,None),
            ('etb_address_mapping_source','Actual TTDP/ECN/NAT/multicast mapping','text',None,None,None,None,None),
            ('etb_mdix_mode','Actual port crossover configuration','select',None,['MDI','MDIX','AUTO'],None,None,None),
            ('etb_autonegotiation','Actual port auto negotiation enabled','boolean',None,None,None,None,None),
            ('etb_clock_role','Actual Gbit port clock role','select',None,['MASTER','FOLLOWER','AUTO'],None,None,None),
            ('etb_peer_clock_role','Actual connected peer Gbit clock role','select',None,['MASTER','FOLLOWER','AUTO'],None,None,None),
            ('etb_queue_source','Actual switching/control-class queue and scheduling evidence','text',None,None,None,None,None),
            ('etb_peer_limit_source','Actual peer MAC frame/payload limits','text',None,None,None,None,None),
        ):
            native=field(key,label,'timing' if unit=='ms' else 'physical','network',field_type=kind,unit=unit,options=options,
                         minimum=minimum,maximum=maximum,default=default,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['etb']['required_parameters'],integer=kind=='number' and unit!='ms',
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN',source=ttdp_source,
                          source_revision='WeOS5.29 TTDP and ETBN port-settings documentation accessed2026-10-01; implementation-qualified limits, not all-edition IEC conformance',
                          description='ETB-specific declaration. Static consist position differs from dynamically assigned train ETBN ID; real topology and state require separate evidence.')
            if key in {'etb_phy','etb_clock_role','etb_peer_clock_role','etb_mdix_mode','etb_autonegotiation','etb_physical_binding'}:
                native['source']=source['source']
            if key=='etb_consist_uuid':
                native.update(pattern=r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}',
                              forbidden_values=['00000000-0000-0000-0000-000000000000'])
            if key=='etb_etbn_mac':
                native['pattern']=r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}'
            if key=='etb_ip_address':
                native['format']='IP_ADDRESS'
            if key=='etb_topology_vlan':
                native.update(conditional_defaults=[{'when':{'etb_implementation':'WEOS_5'},'value':492}],default_status='PROPOSED_CONDITIONAL')
            if key=='etb_backbone_id':
                native.update(conditional_defaults=[{'when':{'etb_implementation':'WEOS_5'},'value':0}],default_status='PROPOSED_CONDITIONAL')
            fields.append(native)
    if technology_id == 'mvb':
        fields=[item for item in fields if item['key']not in mvb_rules.REMOVED]
        for item in fields:
            if item['key']=='bitrate':
                item.update(label='MVB nominal carrier rate',min=1500000,max=1500000,integer=True,default=1500000,
                    parameter_origin='TRANSPORT_PROFILE',default_status='PROPOSED',source=mvb_rules.IMC,source_revision=mvb_rules.SOURCES[mvb_rules.IMC],
                    description='Fixed nominal gross1.5Mbit/s, not measuredclock/usablethroughput or doubledManchesterbaud. ActualPHY/frame/scan/tolerance requireevidence.',simulation_relevant=False)
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.update(min=0,max=32,integer=True,required=False,default_status='UNKNOWN',simulation_relevant=False,
                    parameter_origin='DEVICE_CONFIGURATION',source=mvb_rules.IMC,source_revision=mvb_rules.SOURCES[mvb_rules.IMC],
                    description='Actual applicationencodedbytes within selected16/32/64/128/256bitdataset. Messageport256bits includes actualheader; no universal32byte applicationallocation.')
        fields.extend(mvb_rules.fields())
    if technology_id == 'mqtt_sn':
        fields=[item for item in fields if item['key'] not in mqtt_sn_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.update(min=0,max=65526,integer=True,required=False,default_status='UNKNOWN',simulation_relevant=False,
                    parameter_origin='DEVICE_CONFIGURATION',source=mqtt_sn_rules.P,source_revision=mqtt_sn_rules.SOURCES[mqtt_sn_rules.P],
                    description='Actual PUBLISH Data bytes. Ordinary extended message<=65535 includes9byte header/fields, hence extended payload<=65526; shorter frame max255 includes7byte overhead. Actual lower datagram cap applies. No universal65535payload or ownradio clock.')
        fields.extend(mqtt_sn_rules.fields())
    if technology_id == 'mqtt':
        fields=[item for item in fields if item['key'] not in mqtt_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.update(min=0,max=268435455,integer=True,required=False,default_status='UNKNOWN',simulation_relevant=False,
                    parameter_origin='DEVICE_CONFIGURATION',source=mqtt_rules.P5,source_revision=mqtt_rules.SOURCES[mqtt_rules.P5],
                    description='Actual PUBLISH application payload excluding TopicName/identifier/properties. RemainingLength max268435455 includes header andpayload, fullpacket max268435460; lower transport and receiver cap separate.')
        fields.extend(mqtt_rules.fields())
    if technology_id == 'most':
        fields=[item for item in fields if item['key'] not in most_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',simulation_relevant=False,
                    parameter_origin='DEVICE_CONFIGURATION',source=most_rules.P25,source_revision=most_rules.SOURCES[most_rules.P25],
                    description='Actual channel application bytes; allocated carrier frame bytes differ from one message. Device/host-qualified MDP limits apply only to their actual binding; no generic1500Byte maximum.')
        fields.append(dict(key='bitrate',label='MOST carrier clock (bit/s)',type='number',min=1,integer=True,
            category='physical',scope='network',editable=True,required=True,parameter_origin='TRANSPORT_PROFILE',
            default_status='PROPOSED_CONDITIONAL',simulation_relevant=False,validation_relevant=True,
            source=most_rules.P25,source_revision=most_rules.SOURCES[most_rules.P25],
            description='Exact carrier framebits times selected Fs, distinct host-port clock and usable channel allocation.',
            conditional_defaults=[dict(when={'mo_generation':generation,'mo_target_fs_hz':fs},value=n*8*fs,
                source=source,source_revision=most_rules.SOURCES[source])
                for generation,n,fs,source in [('MOST25',64,44100,most_rules.P25),('MOST25',64,48000,most_rules.P25),
                    ('MOST50',128,48000,most_rules.P50),('MOST150',384,48000,most_rules.P150)]]))
        fields.extend(most_rules.fields())
    if technology_id == 'modbus_tcp':
        fields=[item for item in fields if item['key'] not in mtcp_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.update(min=0,max=252,integer=True,required=False,default_status='UNKNOWN',
                    parameter_origin='DEVICE_CONFIGURATION',source=mtcp_rules.APP,source_revision=mtcp_rules.SOURCES[mtcp_rules.APP],
                    simulation_relevant=False,description='Actual complete function-specific PDU data0..252, including metadata; function1 givesPDU<=253. MBAP7 yieldsADU<=260; actual TCP/IP/TLS/PHY overhead separate.')
        fields.extend(mtcp_rules.fields())
    if technology_id == 'modbus_rtu':
        fields=[item for item in fields if item['key'] not in rtu_rules.REMOVED]
        for item in fields:
            if item['key']=='bitrate':
                item.update(source=rtu_rules.SERIAL,source_revision=rtu_rules.SOURCES[rtu_rules.SERIAL],
                    conditional_defaults=[dict(when={'mr_implementation_class':'BASIC','mr_supports_19200':False},value=9600,
                        source=rtu_rules.SERIAL,source_revision=rtu_rules.SOURCES[rtu_rules.SERIAL])])
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.update(min=0,max=252,integer=True,required=False,default_status='UNKNOWN',
                    parameter_origin='DEVICE_CONFIGURATION',source=rtu_rules.APP,source_revision=rtu_rules.SOURCES[rtu_rules.APP],
                    simulation_relevant=False,description='Actual complete binary Modbus PDU data0..252; function1 forms PDU<=253. RTU address1 and CRC2 form ADU<=256, each binary octet uses11wirebits.')
        fields.extend(rtu_rules.fields())
    if technology_id == 'modbus_ascii':
        fields=[item for item in fields if item['key'] not in ascii_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.update(min=0,max=252,integer=True,required=False,default_status='UNKNOWN',
                    parameter_origin='DEVICE_CONFIGURATION',source=ascii_rules.APP,source_revision=ascii_rules.SOURCES[ascii_rules.APP],
                    simulation_relevant=False,description='Actual complete binary Modbus PDU data field0..252 includes function-dependent metadata. Function1 forms PDU<=253. ASCII address/LRC hex encoding and delimiters form up to513characters with10wirebits each.')
        fields.extend(ascii_rules.fields())
    if technology_id == 'mms':
        fields=[item for item in fields if item['key'] not in mms_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.update(min=0,max=2147483647,integer=True,required=False,default_status='UNKNOWN',
                    parameter_origin='DEVICE_CONFIGURATION',source=mms_rules.INIT,source_revision=mms_rules.SOURCES[mms_rules.INIT],
                    simulation_relevant=False,description='Actual MMS service application octets fit actual complete BER PDU and negotiated/compiled cap. COTP/TPKT/TCP/IP/TLS and lower PHY have separate overhead and evidence; no universal65535 payload.')
        fields.extend(mms_rules.fields())
    if technology_id == 'mipi_dsi':
        fields=[item for item in fields if item['key'] not in dsi_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.update(min=0,max=65535,integer=True,required=False,default_status='UNKNOWN',
                    parameter_origin='DEVICE_CONFIGURATION',source=dsi_rules.TI,source_revision=dsi_rules.SOURCES[dsi_rules.TI],
                    simulation_relevant=False,description='Actual DSI long-packet application octets within word count; classic header4/CRC2 and PHY/blanking are separate. Short command bytes live inside header. Actual device buffers and pixel groups impose separate bounds.')
        fields.extend(dsi_rules.fields())
    if technology_id == 'mipi_csi2':
        fields=[item for item in fields if item['key'] not in csi2_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.update(min=0,max=65535,integer=True,required=False,default_status='UNKNOWN',
                    parameter_origin='DEVICE_CONFIGURATION',source=csi2_rules.TI,source_revision=csi2_rules.SOURCES[csi2_rules.TI],
                    simulation_relevant=False,description='Actual CSI encoded long-packet payload octets within word count; classic header4/CRC2 and PHY transition are separate. Short packet has16bit information field and no application long payload. Device buffers can impose smaller bounds.')
        fields.extend(csi2_rules.fields())
    if technology_id == 'mil_std_1553':
        fields=[item for item in fields if item['key'] not in mil1553_rules.REMOVED]
        for item in fields:
            if item['key'] in ('bitrate','payload_bytes'):
                item.pop('default',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    simulation_relevant=False,source=mil1553_rules.CORE,source_revision=mil1553_rules.SOURCES[mil1553_rules.CORE])
            if item['key']=='bitrate':
                item.pop('default_review',None)
                item.update(min=1000000,max=1000000,allowed_bps=[1000000],
                    description='MIL-STD-1553C nominal information clock1Mbit/s. Measured999000..1001000clock and one-second stability are independent; Manchester transitions do not double useful or nominal bitrate.',
                    schema_when={'ms_edition':mil1553_rules.EDITION},default_status='PROPOSED_CONDITIONAL',
                    conditional_defaults=[dict(when={'ms_edition':mil1553_rules.EDITION},value=1000000,
                        source=mil1553_rules.CORE,source_revision=mil1553_rules.SOURCES[mil1553_rules.CORE])])
            if item['key']=='payload_bytes':
                item.update(required=False,min=0,max=64,
                    description='Actual encoded application bytes fit two octets per data word1..32; mode data belongs to bus management and busy transmitter sends no data. Command/status/sync/parity are separate.')
        fields.extend(mil1553_rules.fields())
    if technology_id == 'matter':
        fields=[item for item in fields if item['key'] not in matter_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=matter_rules.CORE,source_revision=matter_rules.SOURCES[matter_rules.CORE],simulation_relevant=False,
                    description='Actual complete encoded application bytes. UDP1280includesIPv6/UDP/Matterheaders/MIC; TCPpeer64000fallbackexcludes4byteframing. NoCAN8bytepayloadoruniversal65535limit.')
        fields.extend(matter_rules.fields())
    if technology_id == 'm_bus':
        fields=[item for item in fields if item['key'] not in m_bus_rules.REMOVED]
        if not any(item['key']=='bitrate'for item in fields):
            fields.append(dict(key='bitrate',label='Wired M-Bus Baud',type='number',category='physical',scope='network',
              unit='baud',required=False,editable=True,validation_relevant=True))
        for item in fields:
            if item['key']in('bitrate','payload_bytes'):
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=m_bus_rules.P,source_revision=m_bus_rules.SOURCES[m_bus_rules.P])
            if item['key']=='bitrate':
                item.update(min=1,schema_when={'mb_edition':m_bus_rules.EDITION},
                    description='Actual wiredM-Bus transaction baud; master/slave capabilities and TX/RX agreement required. Lowest mandated baseline300baud is a source-qualified proposal;2400is the recommended standard/medium-distance rate, optionalhigher rates need device/line proof.',
                    conditional_defaults=[dict(when={'mb_edition':m_bus_rules.EDITION,'mb_rate_set':'OMS_STANDARD_SET'},value=300,
                        source=m_bus_rules.P,source_revision=m_bus_rules.SOURCES[m_bus_rules.P])],default_status='PROPOSED_CONDITIONAL')
                item.pop('allowed_bps',None)
            if item['key']=='payload_bytes':
                item.update(required=False,description='Actual encoded application bytes, distinct from user area252octets, C/A/CIand Lfield255, wire261octets, transport/AFL/security and records. No8byteapplicationdefault or unconditional252byteapplicationmaximum.')
        fields.extend(m_bus_rules.fields())
    if technology_id == 'lvds':
        fields=[item for item in fields if item['key'] not in lvds_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=lvds_rules.GUIDE,source_revision=lvds_rules.SOURCES[lvds_rules.GUIDE],simulation_relevant=False,
                    description='Actual application byte count only where its separately registered codec uses bytes; physical LVDS defines no8byte frame,65535byte payload, address, CRC or packet queue. Non-byte words and actual encoded bit positions remain separate.')
        fields.extend(lvds_rules.fields())
    if technology_id == 'sercos_iii':
        fields=[item for item in fields if item['key']not in sercos_iii_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=sercos_iii_rules.BROCHURE,source_revision=sercos_iii_rules.SOURCES[sercos_iii_rules.BROCHURE],
                    description='Actual directional applicationconnection bytes withinapprovedRTD mapping, separateSVC/hotplug/aggregateMDT-ATlength andUCCEthernetMTU. No generic1500applicationcap.')
        fields.extend(sercos_iii_rules.fields())
    if technology_id == 'sampled_values':
        fields=[item for item in fields if item['key']not in sampled_values_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=sampled_values_rules.UCA,source_revision=sampled_values_rules.SOURCES[sampled_values_rules.UCA],
                    description='Actual serialized dataset sample bytes, separate BERASDU/APDU length and physical Ethernet MTU/linkoccupation. No universal1500byte applicationcap or8byte frame.')
        fields.extend(sampled_values_rules.fields())
    if technology_id == 'zigbee':
        fields=[item for item in fields if item['key']not in zigbee_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                for key in ('default','max'):item.pop(key,None)
                item.update(min=0,integer=True,default_status='UNKNOWN',source=zigbee_rules.API,source_revision=zigbee_rules.SOURCES[zigbee_rules.API],description='Actual Zigbee applicationbytes; APSfragmentation/security/nodecapability separate127byte MACPSDU.')
        fields.extend(zigbee_rules.fields())
    if technology_id == 'xcp':
        fields=[item for item in fields if item['key']not in xcp_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                for key in ('default','max'):item.pop(key,None)
                item.update(min=0,integer=True,default_status='UNKNOWN',source=xcp_rules.AUTO,source_revision=xcp_rules.SOURCES[xcp_rules.AUTO],description='Actual XCP payload within negotiated CTO/DTO and qualifiedlowertransportbudget; not CAN/Ethernetdefault65535.')
        fields.extend(xcp_rules.fields())
    if technology_id == 'wtb':
        fields=[item for item in fields if item['key']not in wtb_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                for key in ('default','max'):item.pop(key,None)
                item.update(min=0,max=128,integer=True,default_status='UNKNOWN',source=wtb_rules.PAPER,source_revision=wtb_rules.SOURCES[wtb_rules.PAPER],description='Actual WTB usefulframebytes, separateDD/LC/SD/SZ/FCS/flags/stuffing; noEthernet payload.')
        fields.extend(wtb_rules.fields())
    if technology_id == 'wirelesshart':
        fields=[item for item in fields if item['key']not in wirelesshart_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                for key in ('default','max'):item.pop(key,None)
                item.update(min=0,default_status='UNKNOWN',source=wirelesshart_rules.DATA,source_revision=wirelesshart_rules.SOURCES[wirelesshart_rules.DATA],description='Actual WirelessHART applicationbytes, separate radio/frame/security/graph/hostpath; no127byte application default.')
        fields.extend(wirelesshart_rules.fields())
    if technology_id == 'wireless_m_bus':
        fields=[item for item in fields if item['key']not in wireless_m_bus_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=wireless_m_bus_rules.OMS,source_revision=wireless_m_bus_rules.SOURCES[wireless_m_bus_rules.OMS],description='Actual wirelessM-Bus application data, separate DLL/ELL/TPL/security/CRC/linecoding/mode and direction. No universal100k/255 applicationframe.')
        fields.extend(wireless_m_bus_rules.fields())
    if technology_id == 'wifi':
        fields=[item for item in fields if item['key']not in wifi_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=wifi_rules.KERNEL,source_revision=wifi_rules.SOURCES[wifi_rules.KERNEL],description='Actual application bytes, separate MSDU/MPDU/crypto/FCS/aggregation/peerlimits and selected radio generation. No1G/2304 universalframecap.')
        fields.extend(wifi_rules.fields())
    if technology_id == 'websocket':
        fields=[item for item in fields if item['key']not in websocket_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=websocket_rules.BASE,source_revision=websocket_rules.SOURCES[websocket_rules.BASE],description='Actual decoded application message, independent WSframe extension/mask/reassembly/transport and operationalmemorylimit. No65535byte universalcap.')
        fields.extend(websocket_rules.fields())
    if technology_id == 'uwb':
        fields=[item for item in fields if item['key']not in uwb_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=uwb_rules.DATA,source_revision=uwb_rules.SOURCES[uwb_rules.DATA],description='Actual application MAC data, separate complete PSDU/FCS/security/header/FEC/STS. No universal27M or1023 applicationcap.')
        fields.extend(uwb_rules.fields())
    if technology_id == 'usb':
        fields=[item for item in fields if item['key']not in usb_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=usb_rules.USB2,source_revision=usb_rules.SOURCES[usb_rules.USB2],description='Actual applicationtransfer bytes, separate negotiated endpoint/packet/companion/hostschedule and USB4tunnel allocation. No480M/1024 universal rate/payload cap.')
        fields.extend(usb_rules.fields())
    if technology_id == 'uds':
        fields=[item for item in fields if item['key']not in uds_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=uds_rules.DCM,source_revision=uds_rules.SOURCES[uds_rules.DCM],description='Actual diagnostic service data, separate request/subfunction/negative headers and selected CAN/DoIP/FlexRay/LIN transport N-SDU. No universal4095 byte UDS or CAN rate.')
        fields.extend(uds_rules.fields())
    if technology_id == 'udp':
        fields=[item for item in fields if item['key']not in udp_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=udp_rules.USAGE,source_revision=udp_rules.SOURCES[udp_rules.USAGE],description='Actual UDP datagram data, not API buffers. IPv4 options, IPv6 extensions/jumbograms, actual path MTU and encapsulation determine limits; no Ethernet rate or universal65507 cap.')
        fields.extend(udp_rules.fields())
    if technology_id == 'uart':
        fields=[item for item in fields if item['key']not in uart_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=uart_rules.PIC,source_revision=uart_rules.SOURCES[uart_rules.PIC],description='Actual application octets; distinct encoded characters, UART start/parity/stop periods, electrical bridge and host read chunks. No universal baud or message limit.')
        fields.extend(uart_rules.fields())
    if technology_id == 'tte':
        fields=[item for item in fields if item['key']not in tte_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=tte_rules.SAE,source_revision=tte_rules.SOURCES[tte_rules.SAE],description='Actual serializeddataset/applicationbytes, separate actualEthernetframe/PHY/IFG andTT/RC/BE path. No globalTTE1Gbit/s or1500byte limit.')
        fields.extend(tte_rules.fields())
    if technology_id == 'tsn':
        fields=[item for item in fields if item['key']not in tsn_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=tsn_rules.SCHED,source_revision=tsn_rules.SOURCES[tsn_rules.SCHED],description='Actual selectedstreamL2/application bytes, no universalTSN1500bytecap; ownqueueMaxSDU0inheritsactualMACmax, port/class/framing/guard independent.')
        fields.extend(tsn_rules.fields())
    if technology_id == 'trdp':
        fields=[item for item in fields if item['key']not in trdp_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=trdp_rules.CODE,source_revision=trdp_rules.SOURCES[trdp_rules.CODE],description='Actual applicationencoded bytes. PD1432/MD65388 are selectedTCNOpen3.0 dataset limits; headers40/116,padding and IP/PHY constraints separate.')
        fields.extend(trdp_rules.fields())
    if technology_id == 'thread':
        fields=[item for item in fields if item['key']not in thread_rules.REMOVED]
        for item in fields:
            if item['key']in('bitrate','payload_bytes'):
                item.pop('default',None);item.pop('max',None)
                item.update(default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',source=thread_rules.RADIO if item['key']=='bitrate'else thread_rules.OV,
                    source_revision=thread_rules.SOURCES[thread_rules.RADIO if item['key']=='bitrate'else thread_rules.OV],description='Actual selected Thread PHY rate or serialized application bytes, separate whole127bytePSDU and1280byteIPv6/6LoWPAN fragmentation envelope.')
            if item['key']=='bitrate':
                item.update(default_status='PROPOSED_CONDITIONAL',conditional_defaults=[dict(when={'th_review_profile':'PUBLIC_BASELINE_2026','th_proposal_mode':'SOURCE_BASELINE','th_phy':'IEEE_802154_24GHZ_OQPSK'},value=250000,source=thread_rules.RADIO,source_revision=thread_rules.SOURCES[thread_rules.RADIO])])
            if item['key']=='payload_bytes':item.update(min=0,integer=True,required=False,simulation_relevant=False)
        fields.extend(thread_rules.fields())
    if technology_id == 'tcp':
        fields=[item for item in fields if item['key']not in tcp_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',source=tcp_rules.BASE,
                    source_revision=tcp_rules.SOURCES[tcp_rules.BASE],description='Actual applicationstream bytes, no65535byte stream limit; independent segmentMSS/IP/reassembly and messageframing.')
        fields.extend(tcp_rules.fields())
    if technology_id == 'sunspec_modbus':
        fields=[item for item in fields if item['key']not in sunspec_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',source=sunspec_rules.MODEL,
                    source_revision=sunspec_rules.SOURCES[sunspec_rules.MODEL],description='Actual encoded application/model bytes, separate per-function register quantity and253-byte ModbusPDU.')
        fields.extend(sunspec_rules.fields())
    if technology_id == 'spi':
        fields=[item for item in fields if item['key']not in spi_rules.REMOVED]
        for item in fields:
            if item['key']in('bitrate','payload_bytes'):
                item.pop('default',None);item.pop('max',None)
                item.update(default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',source=spi_rules.NXP,source_revision=spi_rules.SOURCES[spi_rules.NXP],
                    description='Actual selected SPI device clock or data bytes, separate whole transaction command/address/dummy/CS/ready envelope; no universal50MHz/65535-byte default.')
            if item['key']=='payload_bytes':item.update(min=0,integer=True,required=False,simulation_relevant=False)
        fields.extend(spi_rules.fields())
    if technology_id == 'sparkplug_b':
        fields=[item for item in fields if item['key']not in sparkplug_b_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=sparkplug_b_rules.SPEC,source_revision=sparkplug_b_rules.SOURCES[sparkplug_b_rules.SPEC],
                    description='Actual ProtobufB or hostSTATEJSON payload; no generic8byte metric or MQTT remaininglength as payload maximum.')
        fields.extend(sparkplug_b_rules.fields())
    if technology_id == 'spacewire':
        fields=[item for item in fields if item['key']not in spacewire_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=spacewire_rules.ECSS,source_revision=spacewire_rules.SOURCES[spacewire_rules.ECSS],
                    description='Actual cargo bytes separate address/higher protocol/packet symbols and FCT stalls. No fixed65535-byte limit or8-byte default.')
        fields.extend(spacewire_rules.fields())
    if technology_id == 'someip_sd':
        fields=[item for item in fields if item['key']not in someip_sd_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=someip_sd_rules.SD,source_revision=someip_sd_rules.SOURCES[someip_sd_rules.SD],
                    description='Actual complete SD body bytes12+entries+options, separate16byte SOME/IP header and independently qualified UDP/IP/security budget. No fixed1400byte cap or8byte default.')
        fields.extend(someip_sd_rules.fields())
    if technology_id == 'someip':
        fields=[item for item in fields if item['key']not in someip_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=someip_rules.PROTOCOL,source_revision=someip_rules.SOURCES[someip_rules.PROTOCOL],
                    description='Actual serialized SOME/IP payload including selected independent E2E protection bytes, distinct16byte header/TP segment/UDP budget/TCP stream. 1400bytes is a recommendation; no universal65535byte maximum or8byte default.')
        fields.extend(someip_rules.fields())
    if technology_id == 'rs485':
        fields=[item for item in fields if item['key']not in rs485_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=rs485_rules.TI,source_revision=rs485_rules.SOURCES[rs485_rules.TI],
                    description='Actual application byte count from separately selected higher wire protocol. Electrical RS485 defines no universal packet size,UART8N1 or65535byte payload.')
        fields.extend(rs485_rules.fields())
    if technology_id == 'rs422':
        fields=[item for item in fields if item['key']not in rs422_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=rs422_rules.TI,source_revision=rs422_rules.SOURCES[rs422_rules.TI],
                    description='Actual application byte count from independently specified higher-layer codec. Balanced RS422 pair defines no universal frame or65535byte payload.')
        fields.extend(rs422_rules.fields())
    if technology_id == 'rs232':
        fields=[item for item in fields if item['key']not in rs232_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=rs232_rules.TI,source_revision=rs232_rules.SOURCES[rs232_rules.TI],
                    description='Actual application bytes only for separately specified codec. RS232 does not define65535byte payload or automatic8N1framing.')
        fields.extend(rs232_rules.fields())
    if technology_id == 'ros2':
        fields=[item for item in fields if item['key']not in ros2_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=ros2_rules.API,source_revision=ros2_rules.SOURCES[ros2_rules.API],
                    description='Actual serialized application bytes from selected ROS type support and sequence bounds. No UDP65507byte or Ethernet MTU application maximum.')
        fields.extend(ros2_rules.fields())
    if technology_id == 'rfid':
        fields=[item for item in fields if item['key']not in rfid_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=rfid_rules.GS,source_revision=rfid_rules.SOURCES[rfid_rules.GS],
                    description='Whole application bytes distinct Gen2EPC/TID/PC/XPC/CRC, HFframing/127byteFIFO and MRD2host/air codecs. No255byte universal application maximum.')
        fields.extend(rfid_rules.fields())
    if technology_id == 'pwm':
        fields=[item for item in fields if item['key']not in pwm_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=pwm_rules.DOC,source_revision=pwm_rules.SOURCES[pwm_rules.DOC],
                    description='Application byte metadata only for an independently registered codec; PWM defines no1byte frame, bitrate, CRC, packet queue or payload maximum.')
        fields.extend(pwm_rules.fields())
    if technology_id == 'profisafe':
        fields=[item for item in fields if item['key']not in profisafe_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=profisafe_rules.PI,source_revision=profisafe_rules.SOURCES[profisafe_rules.PI],
                    description='Whole application bytes distinct directional0..12/40/123 F-user data, control/status byte and mode-qualifiedCRC2/SPDU/native bearer. No ownphysicalrate orEthernet1440 limit.')
        fields.extend(profisafe_rules.fields())
    if technology_id == 'profinet':
        fields=[item for item in fields if item['key']not in profinet_rules.REMOVED]
        for item in fields:
            if item['key']=='bitrate':
                item.pop('default_review',None);item.pop('max',None);item.pop('allowed_bps',None)
                item.update(min=1,integer=True,default=100000000,source=profinet_rules.PI,source_revision=profinet_rules.SOURCES[profinet_rules.PI],
                    default_status='PROPOSED',parameter_origin='TRANSPORT_PROFILE',simulation_relevant=False,
                    description='Conventional100Mbps PROFINET physical rate proposal; actual PHY, RTclass, IOCR and domain schedule required. Optional other PHY needs registered source.')
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=profinet_rules.PPM,source_revision=profinet_rules.SOURCES[profinet_rules.PPM],
                    description='Whole application bytes distinct native1440 CSDU inclIOPS/IOCS/padding and24byte NIC-buffer/28byte MAC framing. No8byte/1500byte universal application limit.')
        fields.extend(profinet_rules.fields())
    if technology_id == 'profibus_pa':
        fields=[item for item in fields if item['key']not in profibus_pa_rules.REMOVED]
        for item in fields:
            if item['key']=='bitrate':
                item.pop('default_review',None)
                item.update(min=31250,max=31250,integer=True,allowed_bps=[31250],default=31250,
                    source=profibus_pa_rules.PNO,source_revision=profibus_pa_rules.SOURCES[profibus_pa_rules.PNO],default_status='PROPOSED',
                    parameter_origin='TRANSPORT_PROFILE',simulation_relevant=False,
                    description='Fixed PA MBP31.25k nominal bitrate, synchronous Manchester8-bit data octets and CRC16. Actual power/coupler/profile/polling evidence separate from DP UART.')
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=profibus_pa_rules.EH,source_revision=profibus_pa_rules.SOURCES[profibus_pa_rules.EH],
                    description='Whole application bytes distinct PA module value/status/control and244-direction cyclic mapping, FDL/PHY telegrams and acyclic transfers. No8byte default.')
        fields.extend(profibus_pa_rules.fields())
    if technology_id == 'profibus_dp':
        fields=[item for item in fields if item['key']not in profibus_dp_rules.REMOVED]
        for item in fields:
            if item['key']=='bitrate':
                item.pop('default_review',None)
                item.update(min=9600,max=12000000,integer=True,allowed_bps=profibus_dp_rules.RATES,default=9600,
                    source=profibus_dp_rules.ABB,source_revision=profibus_dp_rules.SOURCES[profibus_dp_rules.ABB],default_status='PROPOSED',
                    parameter_origin='TRANSPORT_PROFILE',simulation_relevant=False,
                    description='Lowest listed DP nominal baud proposal; actual all-station supported rate, FDL UART/token/polling and selected device parameters remain explicit.')
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=profibus_dp_rules.PI,source_revision=profibus_dp_rules.SOURCES[profibus_dp_rules.PI],
                    description='Whole application bytes distinct separately244 input/output cyclic bytes, FDL data unit246/255whole-frame and acyclic segmented services. No8byte default.')
        fields.extend(profibus_dp_rules.fields())
    if technology_id == 'powerlink':
        fields=[item for item in fields if item['key']not in powerlink_rules.REMOVED]
        for item in fields:
            if item['key']=='bitrate':
                item.pop('default_review',None)
                item.update(min=100000000,max=100000000,integer=True,allowed_bps=[100000000],default=100000000,
                    source=powerlink_rules.P,source_revision=powerlink_rules.SOURCES[powerlink_rules.P],default_status='PROPOSED',
                    parameter_origin='TRANSPORT_PROFILE',simulation_relevant=False,
                    description='Classic DS301100M nominal physical bitrate; HALF duplex and actual cycle/grants/propagation govern service, not generic switched Ethernet capacity.')
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(min=0,integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=powerlink_rules.P,source_revision=powerlink_rules.SOURCES[powerlink_rules.P],
                    description='Whole application bytes distinct mapped PDO Size1490, fixed padded slots, ASnd/IP headers and SDO segmentation. No8byte default or1500application maximum.')
        fields.extend(powerlink_rules.fields())
    if technology_id == 'pcie':
        fields=[item for item in fields if item['key']not in pcie_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=pcie_rules.REG,source_revision=pcie_rules.SOURCES[pcie_rules.REG],
                    description='Actual whole application bytes distinct TLP payload/MPS/read request/MRRS/completions or FLIT. No universal8byte or4096byte application maximum.')
        fields.extend(pcie_rules.fields())
    if technology_id == 'opensafety':
        fields=[item for item in fields if item['key']not in opensafety_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=opensafety_rules.FRAME,source_revision=opensafety_rules.SOURCES[opensafety_rules.FRAME],
                    description='Actual application bytes separate versioned safety LE/ordinary redundant copy/slim service framing and selected black-channel overhead. No universalCAN8byte orEthernet1500byte payload proposal.')
        fields.extend(opensafety_rules.fields())
    if technology_id == 'opc_ua_pubsub':
        fields=[item for item in fields if item['key']not in opc_ua_pubsub_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=opc_ua_pubsub_rules.P14,source_revision=opc_ua_pubsub_rules.SOURCES[opc_ua_pubsub_rules.P14],
                    description='Actual application bytes distinct encoded DataSet/NetworkMessage including metadata/security/padding and selected bearer overhead. No universal8byte payload or65507byte UDP ceiling on all mappings.')
        fields.extend(opc_ua_pubsub_rules.fields())
    if technology_id == 'opc_ua':
        fields=[item for item in fields if item['key']not in opc_ua_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=opc_ua_rules.P6,source_revision=opc_ua_rules.SOURCES[opc_ua_rules.P6],
                    description='Actual encoded application bytes separate UA unencrypted message body, directional chunk/security overhead and actual bearer. No universal8byte payload or65535byte ceiling.')
        fields.extend(opc_ua_rules.fields())
    if technology_id == 'one_wire':
        fields=[item for item in fields if item['key']not in one_wire_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=one_wire_rules.STYLE,source_revision=one_wire_rules.SOURCES[one_wire_rules.STYLE],
                    description='Actual selectedfunction application bytes, distinct ROMcommand/search/CRC/reset/conversion/host wrappers. No universal8byte proposal or255bytemaximum.')
        fields.extend(one_wire_rules.fields())
    if technology_id == 'ocpp':
        fields=[item for item in fields if item['key']not in ocpp_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,required=False,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=ocpp_rules.P21,source_revision=ocpp_rules.SOURCES[ocpp_rules.P21],
                    description='Actual application object bytes separate whole encoded UTF8 JSON/SOAP, wrappers, escaping, WebSocket/TLS records and selected bearer. Actual direction/action/device limits required, no8/65535 default.')
        fields.extend(ocpp_rules.fields())
    if technology_id == 'obd2':
        fields=[item for item in fields if item['key']not in obd2_rules.REMOVED]
        for item in fields:
            if item['key']in('bitrate','payload_bytes'):
                item.pop('default',None);item.pop('max',None)
                item.update(default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=obd2_rules.ELM,source_revision=obd2_rules.SOURCES[obd2_rules.ELM])
            if item['key']=='bitrate':
                item.update(required=False,min=1,conditional_defaults=[dict(when={'o_transport':t},value=v,source=obd2_rules.ELM,source_revision=obd2_rules.SOURCES[obd2_rules.ELM])for t,v in obd2_rules.RATES.items()],default_status='PROPOSED_CONDITIONAL',
                    description='Actual selectedvehiclebus rate, not adapter-PCUART or5baudinitialization. J1850PWM41600,VPW/Kline10400,CAN250k/500k bybinding. RegisteredDoIP hasno ownphysicalbus rate.')
                item.pop('allowed_bps',None)
            if item['key']=='payload_bytes':
                item.update(integer=True,description='Actual applicationservice data length, distinct request/reassembledresponse/PCI/padding/adapterASCII. ClassicELMCAN12bitresponse<=4095, not universalUDS/DoIP payload maximum.')
        fields.extend(obd2_rules.fields())
    if technology_id == 'nmea2000':
        fields=[item for item in fields if item['key']not in nmea2000_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=nmea2000_rules.SS,source_revision=nmea2000_rules.SOURCES[nmea2000_rules.SS],
                    description='Actual complete PGN encodeddata: SINGLE<=8, FAST<=223, source-qualified ISOtransport<=1785 plusmanagementframes. No fixed8byte default or223globalmaximum.')
        fields.extend(nmea2000_rules.fields())
    if technology_id == 'nmea0183':
        fields=[item for item in fields if item['key']not in nmea0183_rules.REMOVED]
        for item in fields:
            if item['key']in('bitrate','payload_bytes'):
                item.pop('default',None);item.pop('max',None)
                item.update(default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=nmea0183_rules.P,source_revision=nmea0183_rules.SOURCES[nmea0183_rules.P])
            if item['key']=='bitrate':
                item.update(required=False,min=1,description='Actual selected serial port baud; standard4800 versusHS38400. DeviceUART configured separately. NMEA sentences over registered TCP/UDP/host do not acquire a physical bitrate from this field.',
                    conditional_defaults=[dict(when={'nt_binding':b},value=rate,source=nmea0183_rules.P,source_revision=nmea0183_rules.SOURCES[nmea0183_rules.P])
                        for b,rate in [('STANDARD_SERIAL',4800),('HIGH_SPEED_SERIAL',38400)]],default_status='PROPOSED_CONDITIONAL')
                item.pop('allowed_bps',None)
            if item['key']=='payload_bytes':
                item.update(integer=True,description='Actual encoded application data, separate from sentence/address/commas/XOR/CRLF/tag bytes. No universal8byte value or82byteapplicationlimit; per-sentence and aggregate port schedule required.')
        fields.extend(nmea0183_rules.fields())
    if technology_id == 'nfc':
        fields=[item for item in fields if item['key'] not in nfc_rules.REMOVED]
        for item in fields:
            if item['key'] in ('bitrate','payload_bytes'):
                item.pop('default',None);item.pop('max',None)
                item.update(default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',simulation_relevant=False,
                    source=nfc_rules.ECMA,source_revision=nfc_rules.SOURCES[nfc_rules.ECMA])
            if item['key']=='bitrate':
                item.update(min=1,description='Selected RF nominal label or exact carrier/divisor rate; host I2C/SPI clock is separate. NFCIP1/A/B baseline106k, F212k and selected PN7160V26.48k are conditional proposals, not confirmed device capability.',
                    conditional_defaults=[dict(when={'nf_protocol':'NFCIP1_ECMA340_2024','nf_rate_basis':'NOMINAL_LABEL'},value=106000,source=nfc_rules.ECMA,source_revision=nfc_rules.SOURCES[nfc_rules.ECMA])]+[
                        dict(when={'nf_protocol':p,'nf_implementation':impl,'nf_rate_basis':'NOMINAL_LABEL'},value=rate,source=nfc_rules.DATA,source_revision=nfc_rules.SOURCES[nfc_rules.DATA])
                        for impl in('PN7160','PN7161')for p,rate in [('NFC_A',106000),('NFC_B',106000),('NFC_F',212000),('NFC_V',26480)]],default_status='PROPOSED_CONDITIONAL')
                item.pop('allowed_bps',None)
            if item['key']=='payload_bytes':
                item.update(integer=True,description='Actual encoded application bytes may require multiple RF and NCI packets; NFCIP1 LEN255 and NCI payload255 describe different framed layers. No unconditional application255byte limit or8byte default.')
        fields.extend(nfc_rules.fields())
    if technology_id == 'nb_iot':
        fields=[item for item in fields if item['key'] not in nb_iot_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=nb_iot_rules.CAP,source_revision=nb_iot_rules.SOURCES[nb_iot_rules.CAP],simulation_relevant=False,
                    description='Actual encoded application bytes, distinct from upper-layer overhead, MAC/RLC segmentation, granted NPUSCH/NPDSCH TBS and coded/repeated radio airtime. No universal8/1500byte NB-IoT payload or peak-rate capacity.')
        fields.extend(nb_iot_rules.fields())
    if technology_id == 'lte_m':
        fields=[item for item in fields if item['key'] not in lte_m_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=lte_m_rules.CAP,source_revision=lte_m_rules.SOURCES[lte_m_rules.CAP],simulation_relevant=False,
                    description='Actual encoded application bytes, distinct from MAC/RLC/PDCP segmentation, granted transport blocks and coded/repeated PHY airtime. No universal8 or1500byte LTE-M payload or category-peak capacity.')
        fields.extend(lte_m_rules.fields())
    if technology_id == 'lorawan':
        fields=[item for item in fields if item['key'] not in lorawan_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=lorawan_rules.L2,source_revision=lorawan_rules.SOURCES[lorawan_rules.L2],simulation_relevant=False,
                    description='Actual encoded application bytes, distinct from FHDR/FOpts/FPort/MIC and complete PHY airtime; limits depend on selected region, DR, direction, dwell and repeater context. No universal8 or242bytepayload.')
        fields.extend(lorawan_rules.fields())
    if technology_id == 'lonworks':
        fields=[item for item in fields if item['key'] not in lonworks_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=lonworks_rules.PROGRAM,source_revision=lonworks_rules.SOURCES[lonworks_rules.PROGRAM],simulation_relevant=False,
                    description='Actual application bytes distinct from NVelement31,qualifiedNeuronapplicationdata228,NPDU/address/CRC andcompletephysicalframe; no universal8bytepayload.')
        fields.extend(lonworks_rules.fields())
    if technology_id == 'lin':
        fields=[item for item in fields if item['key'] not in lin_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=lin_rules.SPEC,source_revision=lin_rules.SOURCES[lin_rules.SPEC],simulation_relevant=False,
                    description='Actual application bytes distinct from agreed1..8byte LIN response and diagnostic SID-inclusive segmentedmessage; no automatic8byte data frame.')
        fields.extend(lin_rules.fields())
    if technology_id == 'knx_tp':
        fields=[item for item in fields if item['key'] not in knx_tp_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=knx_tp_rules.TI,source_revision=knx_tp_rules.SOURCES[knx_tp_rules.TI],simulation_relevant=False,
                    description='Actual DPT/application bytes, distinct from TPDU, wire telegram parity/check, TP ACK and separate PHY-host framing.')
        fields.extend(knx_tp_rules.fields())
    if technology_id == 'knx_rf':
        fields=[item for item in fields if item['key'] not in knx_rf_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=knx_rf_rules.SPEC,source_revision=knx_rf_rules.SOURCES[knx_rf_rules.SPEC],simulation_relevant=False,
                    description='Actual KNX DPT/LTE/application bytes, distinct from L-count, FT3 blocks/CRCs, RF preamble and Data Secure overhead.')
        fields.extend(knx_rf_rules.fields())
    if technology_id == 'knx_ip':
        fields=[item for item in fields if item['key'] not in knx_ip_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=knx_ip_rules.EXT,source_revision=knx_ip_rules.SOURCES[knx_ip_rules.EXT],simulation_relevant=False,
                    description='Actual KNX application data; selected DPT/TPCI/APCI/cEMI and IP/UDP/TCP/secure wrapper lengths are distinct, not Ethernet1476byte payload.')
        fields.extend(knx_ip_rules.fields())
    if technology_id == 'j1939':
        fields=[item for item in fields if item['key'] not in j1939_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=j1939_rules.DOC,source_revision=j1939_rules.SOURCES[j1939_rules.DOC],simulation_relevant=False,
                    description='Actual complete J1939 application message; classical single8/TP1785, explicitETP117440505 and separateFD MultiPG60/BAM15300/connection16777215 limits.')
        fields.extend(j1939_rules.fields())
    if technology_id == 'isobus':
        fields=[item for item in fields if item['key'] not in isobus_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=isobus_rules.TP,source_revision=isobus_rules.SOURCES[isobus_rules.TP],simulation_relevant=False,
                    description='Actual full ISOBUS application message; single frame8, TP1785, ETP117440505 and GNSS FastPacket223 apply to independently selected layouts.')
        fields.extend(isobus_rules.fields())
    if technology_id == 'ip':
        fields=[item for item in fields if item['key'] not in ip_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=ip_rules.V6,source_revision=ip_rules.SOURCES[ip_rules.V6],simulation_relevant=False,
                    description='Actual upper-layer/application data; IP headers, extension headers, fragment lengths and jumbo payload limits are separate.')
        fields.extend(ip_rules.fields())
    if technology_id == 'io_link_wireless':
        fields=[item for item in fields if item['key'] not in io_link_wireless_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=io_link_wireless_rules.SPEC,source_revision=io_link_wireless_rules.SOURCES[io_link_wireless_rules.SPEC],simulation_relevant=False,
                    description='Actual wireless process/application data; directional PD32, ISDU record232/full238 and SS/DS slot packet limits are separate.')
        fields.extend(io_link_wireless_rules.fields())
    if technology_id == 'io_link':
        fields=[item for item in fields if item['key'] not in io_link_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=io_link_rules.SPEC,source_revision=io_link_rules.SOURCES[io_link_rules.SPEC],simulation_relevant=False,
                    description='Actual selected wired IO-Link process/application data; directional PD32, record232 and full ISDU238 limits apply to separate layouts.')
        fields.extend(io_link_rules.fields())
    if technology_id == 'interbus':
        fields=[item for item in fields if item['key'] not in interbus_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=interbus_rules.BC,source_revision=interbus_rules.SOURCES[interbus_rules.BC],simulation_relevant=False,
                    description='Actual process-data or PCP application bytes; per-direction image, rounded registers and PCP service limits are independent.')
        fields.extend(interbus_rules.fields())
    if technology_id == 'iec61850':
        fields=[item for item in fields if item['key'] not in iec61850_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=iec61850_rules.ACSI,source_revision=iec61850_rules.SOURCES[iec61850_rules.ACSI],simulation_relevant=False,
                    description='Actual selected ACSI application encoding; MMS PDU, GOOSE/SV frame, routed security and XML layouts have independent bounds.')
        fields.extend(iec61850_rules.fields())
    if technology_id == 'iec61162':
        fields=[item for item in fields if item['key'] not in iec61162_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=iec61162_rules.P1,source_revision=iec61162_rules.SOURCES[iec61162_rules.P1],simulation_relevant=False,
                    description='Actual application payload for selected part/encoding; serial sentence, CAN PGN, IP datagram and binary block have independent layout/bounds.')
        fields.extend(iec61162_rules.fields())
    if technology_id == 'iec60870_5_104':
        fields=[item for item in fields if item['key'] not in iec104_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=iec104_rules.ASDU,source_revision=iec104_rules.SOURCES[iec104_rules.ASDU],simulation_relevant=False,
                    description='Actual encoded application data. ASDU encoding, APCI length-L, complete APDU and TCP/TLS framing remain distinct.')
        fields.extend(iec104_rules.fields())
    if technology_id == 'iec60870_5_101':
        fields=[item for item in fields if item['key'] not in iec101_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=iec101_rules.ASDU,source_revision=iec101_rules.SOURCES[iec101_rules.ASDU],simulation_relevant=False,
                    description='Actual encoded application data. ASDU addresses/header, FT1.2 L and wire bytes are separately bounded by configured peers.')
        fields.extend(iec101_rules.fields())
    if technology_id == 'i3c':
        fields=[item for item in fields if item['key'] not in i3c_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=i3c_rules.MIPI,source_revision=i3c_rules.REVISIONS[i3c_rules.MIPI],simulation_relevant=False,
                    description='Actual meaningful data; no universal65535B transfer. Negotiated limits, padding, CCC/IBI and phase layout are separate.')
        fields.extend(i3c_rules.fields())
    if technology_id == 'i2c':
        fields=[item for item in fields if item['key'] not in i2c_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=i2c_rules.SOURCE,source_revision=i2c_rules.REVISION,simulation_relevant=False,
                    description='Actual encoded data octets; I2C imposes no255-byte transfer maximum. Address/register/ninth-clock/layout overhead is separate.')
        for key,kind,unit,options,minimum,maximum,meaning in i2c_rules.DECLARATIONS:
            native=field(key,key.replace('i2c_','').replace('_',' '),'communication','route',field_type=kind,
                unit=unit,options=options,minimum=minimum,maximum=maximum,description=meaning,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['i2c']['required_parameters'],
                integer=kind=='number' and unit not in {'ns','V','mA','pF','Ohm'},
                parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',source=i2c_rules.SOURCE,source_revision=i2c_rules.REVISION)
            if key=='i2c_mode': native.update(default='STANDARD',default_status='PROPOSED_STANDARD')
            if key=='i2c_ack_policy':
                native.update(conditional_defaults=[{'when':{'i2c_mode':mode},'value':'NINTH_HIGH_NO_ACK' if mode=='ULTRA_FAST' else 'ACK_NACK'} for mode in i2c_rules.MODES],default_status='PROPOSED_CONDITIONAL')
            fields.append(native)
    if technology_id == 'http':
        source=REVIEW_RATE_PROPOSALS['http']
        fields=[item for item in fields if item['key'] not in {'qos_priority', 'gateway_maximum_throughput', 'mtu_bytes', 'sync_method', 'gateway_input_buffer', 'duplex', 'retransmission_rate', 'gateway_maximum_messages_s', 'retransmission_enabled', 'vlan_id', 'retry_limit', 'reserved_bandwidth_percent', 'queue_size', 'bitrate', 'retransmission_delay_ms', 'gateway_output_buffer', 'gateway_maximum_routes', 'queue_policy'}]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.pop('max',None)
                item.update(integer=True,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',
                    source=source['source'],source_revision=source['source_revision'],simulation_relevant=False,
                    description='Actual NIS application chunk octets; whole HTTP content/message/framing differ. No8-byte or65535-byte protocol default.')
        for key,kind,unit,options,minimum,maximum,meaning in [('http_version',
  'select',
  None,
  ['HTTP_1_1', 'HTTP_2', 'HTTP_3'],
  None,
  None,
  'Actual protocol version, unknown. Different text/binary/QUIC framing and flow control; no latest-version '
  'default.'),
 ('http_transport',
  'select',
  None,
  ['TCP', 'QUIC_V1', 'DEVICE_SPECIFIC'],
  None,
  None,
  'Actual selected transport, unknown. HTTP2TCP and HTTP3QUIC differ; HTTP1 custom reliable transport needs '
  'matched implementation source.'),
 ('http_binding_source',
  'text',
  None,
  None,
  None,
  None,
  'Required actual registered TCP/TLS or QUIC/IP/physical path and peer endpoints, unknown; no automatic '
  'Ethernet100M or TCP mapping for all versions.'),
 ('http_implementation_source',
  'text',
  None,
  None,
  None,
  None,
  'Required actual client/server/proxy version, supported negotiated protocol and resource limits, unknown.'),
 ('http_schedule_source',
  'text',
  None,
  None,
  None,
  None,
  'Required actual handshake/application/flow-control/transport recovery/concurrency schedule evidence, '
  'unknown; HTTP defines no universal deadline.'),
 ('http_role',
  'select',
  None,
  ['CLIENT', 'SERVER', 'PROXY'],
  None,
  None,
  'Actual endpoint role, unknown. Response, push and settings direction depend on role; proxy requires each '
  'actual leg.'),
 ('http_message_kind',
  'select',
  None,
  ['REQUEST', 'RESPONSE'],
  None,
  None,
  'Actual message direction; method/status/body semantics differ.'),
 ('http_scheme',
  'select',
  None,
  ['http', 'https'],
  None,
  None,
  'Actual origin scheme, unknown. Default ports80/443 are proposals only when origin has no explicit port, '
  'not all endpoints.'),
 ('http_port_explicit',
  'boolean',
  None,
  None,
  None,
  None,
  'Whether actual origin contains explicit port, unknown; false permits scheme-default proposal, never '
  'overwrites explicit13500 etc.'),
 ('http_port',
  'number',
  None,
  None,
  1,
  65535,
  'Actual endpoint port, unknown; scheme-default80/443 proposal only when port elided.'),
 ('http_origin',
  'text',
  None,
  None,
  None,
  None,
  'Actual http(s) origin/resource URI, unknown; nonempty host, no embedded credentials or fragment. '
  'Request-target forms are separate.'),
 ('http_method',
  'text',
  None,
  None,
  None,
  None,
  'Actual case-sensitive method token, unknown; extension tokens allowed, no universal GET command.'),
 ('http_status',
  'number',
  None,
  None,
  100,
  599,
  'Actual response status100..599; unknown/reserved3-digit statuses retain class semantics. Not mandatory '
  'for requests.'),
 ('http_target_form',
  'select',
  None,
  ['ORIGIN', 'ABSOLUTE', 'AUTHORITY', 'ASTERISK'],
  None,
  None,
  'Actual HTTP1 request-target form. CONNECT authority, OPTIONS asterisk and proxy absolute target differ '
  'from HTTP2/3 pseudoheaders.'),
 ('http_target_source',
  'text',
  None,
  None,
  None,
  None,
  'Actual URI/Host/:authority/:scheme/:path and target normalization/route evidence, unknown; no automatic '
  'URL constructed from device name.'),
 ('http_tls_version',
  'select',
  None,
  ['TLS_1_2', 'TLS_1_3', 'DEVICE_SPECIFIC'],
  None,
  None,
  'Actual negotiated security version, unknown. HTTP3 QUICv1 TLS1.3; HTTP2TLS at least1.2; actual '
  'certificate/ALPN acceptance separate.'),
 ('http_security_source',
  'text',
  None,
  None,
  None,
  None,
  'Actual negotiated TLS/QUIC certificate/origin authentication/ALPN/cipher/0RTT policy evidence, unknown.'),
 ('http_framing',
  'select',
  None,
  ['NONE', 'CONTENT_LENGTH', 'CHUNKED', 'CLOSE_DELIMITED', 'TUNNEL', 'MULTIPLEXED'],
  None,
  None,
  'Actual selected message framing. HTTP1 chunk/close differ from HTTP2/3 stream framing; successful CONNECT '
  'becomes tunnel.'),
 ('http_transfer_encoding',
  'select',
  None,
  ['NONE', 'CHUNKED', 'OTHER'],
  None,
  None,
  'Actual HTTP1 Transfer-Encoding final coding; not content compression. HTTP2/3 forbid Transfer-Encoding, '
  'though TE:trailers differs.'),
 ('http_transfer_source',
  'text',
  None,
  None,
  None,
  None,
  'Actual transfer coding chain/chunk extensions/final terminator/trailers source, unknown; raw byte parsing '
  'not proven by counters.'),
 ('http_content_length_present',
  'boolean',
  None,
  None,
  None,
  None,
  'Actual presence of Content-Length, unknown. Sender must not combine with Transfer-Encoding; HEAD/304 may '
  'report selected-representation length.'),
 ('http_content_length',
  'text',
  'Byte',
  None,
  None,
  None,
  'Actual nonnegative decimal Content-Length with no protocol-wide upper bound; text preserves arbitrary '
  'exact digits without JS precision loss.'),
 ('http_length_semantics',
  'select',
  None,
  ['MESSAGE_BODY', 'SELECTED_REPRESENTATION'],
  None,
  None,
  'Actual Content-Length semantic target, unknown; HEAD/304 metadata can differ from transmitted empty '
  'content.'),
 ('http_body_bytes',
  'text',
  'Byte',
  None,
  None,
  None,
  'Actual transmitted content octets as exact decimal text. No65535 maximum or8-byte default; excludes chunk '
  'framing and HTTP2 padding.'),
 ('http_wire_message_bytes',
  'text',
  'Byte',
  None,
  None,
  None,
  'Actual whole encoded HTTP message/stream octets as exact decimal text, unknown. '
  'Compression/headers/chunks/frame boundaries are not inferred from content.'),
 ('http_encoding_source',
  'text',
  None,
  None,
  None,
  None,
  'Actual encoded content/header/trailer/chunk/HPACK/QPACK representation and whole message evidence, '
  'unknown.'),
 ('http_acceptance_source',
  'text',
  None,
  None,
  None,
  None,
  'Actual application acceptance/units/idempotence/retries/cache/proxy/response correlation evidence, '
  'unknown; transport delivery is not functional acceptance.'),
 ('http_request_timeout_ms',
  'number',
  'ms',
  None,
  0,
  None,
  'Actual implementation/application request deadline, unknown; no universal HTTP100/500ms standard.'),
 ('http_retry_limit',
  'number',
  'attempts',
  None,
  0,
  None,
  'Actual application retry policy and idempotence/source evidence, unknown; HTTP retries differ from '
  'TCP/QUIC retransmission.'),
 ('http_retry_source',
  'text',
  None,
  None,
  None,
  None,
  'Actual method idempotence/replay/partial-processing and retry acceptance evidence, unknown. A lost '
  'response does not prove request was not applied.'),
 ('http_transition_optimistic',
  'boolean',
  None,
  None,
  None,
  None,
  'Actual optimistic HTTP1 Upgrade/CONNECT behavior, unknown; RFC9931 requires explicit safety relative to '
  'possible HTTP misinterpretation.'),
 ('http_transition_source',
  'text',
  None,
  None,
  None,
  None,
  'Actual negotiated transition/confirmation and harmless-prefix/smuggling risk evidence per RFC9931, '
  'unknown; tunnel is not auto-safe.'),
 ('http2_frame_type',
  'select',
  None,
  ['DATA',
   'HEADERS',
   'PRIORITY',
   'RST_STREAM',
   'SETTINGS',
   'PUSH_PROMISE',
   'PING',
   'GOAWAY',
   'WINDOW_UPDATE',
   'CONTINUATION',
   'EXTENSION'],
  None,
  None,
  'Actual HTTP2 frame type, unknown; fixed-type payloads and stream scope differ.'),
 ('http2_stream_id',
  'number',
  None,
  None,
  0,
  2147483647,
  'Actual31-bit HTTP2 stream ID; DATA/HEADERS on nonzero streams; connection frames stream0. No '
  'defaultassigned stream1.'),
 ('http2_frame_header_bytes',
  'number',
  'Byte',
  None,
  9,
  9,
  'HTTP2 fixed9-octet header proposal only for actual HTTP2. Excluded from SETTINGS_MAX_FRAME_SIZE.'),
 ('http2_frame_payload_bytes',
  'number',
  'Byte',
  None,
  0,
  16777215,
  'Actual24-bit HTTP2 frame payload, incl padding/pad length if used; at most actual receiver-advertised '
  'max, distinct from content/message.'),
 ('http2_frame_bytes',
  'number',
  'Byte',
  None,
  9,
  16777224,
  'Actual HTTP2 frame9+payload octets; not TCP segment or Ethernet frame length.'),
 ('http2_settings_phase',
  'select',
  None,
  ['INITIAL_DEFAULTS', 'PEER_ADVERTISED'],
  None,
  None,
  'Actual settings state. Normative initial values can be proposed only before peer values are supplied; '
  'never overwrite peer advertisements.'),
 ('http2_max_frame_size',
  'number',
  'Byte',
  None,
  16384,
  16777215,
  'Actual peer SETTINGS_MAX_FRAME_SIZE range16384..16777215; initial16384 proposal. Not message-body '
  'maximum.'),
 ('http2_header_table_size',
  'number',
  'Byte',
  None,
  0,
  4294967295,
  'Actual HPACK SETTINGS_HEADER_TABLE_SIZE uint32, initial4096 proposal; negotiated decoder context differs '
  'from uncompressed field size.'),
 ('http2_initial_window_size',
  'number',
  'Byte',
  None,
  0,
  2147483647,
  'Actual SETTINGS_INITIAL_WINDOW_SIZE stream limit, initial65535 proposal; current stream/connection '
  'windows change independently.'),
 ('http2_current_stream_window',
  'number',
  'Byte',
  None,
  None,
  2147483647,
  'Actual remaining stream flow-control window. Can be negative after SETTINGS decrease; negative window '
  'permits no DATA, no unsigned fallback.'),
 ('http2_current_connection_window',
  'number',
  'Byte',
  None,
  0,
  2147483647,
  'Actual remaining connection DATA window; initial65535, WINDOW_UPDATE changes it. Not changed by stream '
  'SETTINGS.'),
 ('http2_enable_push',
  'number',
  None,
  None,
  0,
  1,
  'Actual SETTINGS_ENABLE_PUSH0/1; initialclient1, serverinitial value has no effect equivalent0. Actual '
  'support/state required.'),
 ('http2_max_concurrent_streams',
  'number',
  None,
  None,
  0,
  4294967295,
  'Actual advertised uint32 limit, initially unlimited if absent; no fabricated100/256-stream maximum.'),
 ('http2_max_header_list_bytes',
  'number',
  'Byte',
  None,
  0,
  4294967295,
  'Actual advisory uncompressed field-list limit incl32bytes per field; initially unlimited if absent, not a '
  'zero-byte default.'),
 ('http2_pad_length_present',
  'boolean',
  None,
  None,
  None,
  None,
  'Actual PADDED flag and one-byte PadLength presence for DATA/HEADERS/PUSH_PROMISE, unknown.'),
 ('http2_padding_bytes',
  'number',
  'Byte',
  None,
  0,
  255,
  'Actual padding octets0..255 when PADDED, excluding1-byte PadLength; all are part of frame payload and '
  'DATA flow-control cost.'),
 ('http2_data_bytes',
  'number',
  'Byte',
  None,
  0,
  16777215,
  'Actual content inside DATA frame excluding padding/PadLength; distinct from complete message content and '
  'receiver window cost.'),
 ('http3_frame_type',
  'text',
  None,
  None,
  None,
  None,
  'Actual QUIC-varint HTTP3 frame type0..2^62-1 as exact decimal text. Separate registry from HTTP2.'),
 ('http3_frame_length',
  'text',
  'Byte',
  None,
  None,
  None,
  'Actual QUIC-varint HTTP3 frame payload length0..2^62-1 as exact decimal text; no9-byte header or16384 '
  'maximum inherited from HTTP2.'),
 ('http3_stream_kind',
  'select',
  None,
  ['REQUEST', 'CONTROL', 'PUSH', 'QPACK_ENCODER', 'QPACK_DECODER', 'EXTENSION'],
  None,
  None,
  'Actual QUIC stream kind: DATA/HEADERS request or push; SETTINGS control. QPACK streams are independent '
  'byte streams.'),
 ('http3_qpack_max_table',
  'text',
  'Byte',
  None,
  None,
  None,
  'Actual SETTINGS_QPACK_MAX_TABLE_CAPACITY uint62 as exact decimal text, initial0; not HTTP2 HPACK4096 '
  'default.'),
 ('http3_qpack_blocked_streams',
  'text',
  None,
  None,
  None,
  None,
  'Actual SETTINGS_QPACK_BLOCKED_STREAMS uint62 as exact decimal text, initial0; blocking/recovery remains '
  'actual QUIC/QPACK schedule.'),
 ('http3_max_field_section_bytes',
  'text',
  'Byte',
  None,
  None,
  None,
  'Actual advertised uint62 maximum field-section size as exact decimal text; absent means unlimited, not0 '
  'or HTTP2 frame-size limit.'),
 ('http3_settings_phase',
  'select',
  None,
  ['INITIAL_1RTT', 'PEER_ADVERTISED', 'RESUMED_0RTT'],
  None,
  None,
  'Actual HTTP3 settings state.1RTT initial defaults differ from remembered0RTT peer values; do not '
  'overwrite remembered settings.'),
 ('http3_quic_source',
  'text',
  None,
  None,
  None,
  None,
  'Actual QUIC version, varint widths, stream limits, flow control, recovery and congestion/pacing source, '
  'unknown; no assumed TCP schedule.')]:
            native=field(key,key.replace('http_','').replace('_',' '),'communication','route',field_type=kind,
                unit=unit,options=options,minimum=minimum,maximum=maximum,description=meaning,simulation_relevant=False)
            field_source=('https://www.rfc-editor.org/rfc/rfc9113.html' if key.startswith('http2_') else
                'https://www.rfc-editor.org/rfc/rfc9204.html' if key.startswith('http3_qpack') else
                'https://www.rfc-editor.org/rfc/rfc9114.html' if key.startswith('http3_') else
                'https://www.rfc-editor.org/rfc/rfc9931.html' if key.startswith('http_transition') else source['source'])
            native.update(required=key in TECHNOLOGY_SEMANTICS['http']['required_parameters'],integer=kind=='number' and unit!='ms',
                parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',source=field_source,source_revision=source['source_revision'])
            if key.startswith('http2_'): native['schema_when']={'http_version':'HTTP_2'}
            if key.startswith('http3_'): native['schema_when']={'http_version':'HTTP_3'}
            if key in {'http_content_length','http_body_bytes','http_wire_message_bytes'}: native['pattern']=r'[0-9]+'
            if key.startswith('http3_') and kind=='text' and key!='http3_quic_source':
                native.update(pattern=r'0|[1-9][0-9]*',integer_text_maximum=4611686018427387903)
            if key=='http_method': native['pattern']=r"[!#$%&'*+.^_`|~0-9A-Za-z-]+"
            if key=='http_origin': native.update(format='ABSOLUTE_URI',allowed_schemes=['http','https'])
            if key in {'http2_frame_header_bytes','http2_max_frame_size','http2_header_table_size','http2_initial_window_size'}:
                value={'http2_frame_header_bytes':9,'http2_max_frame_size':16384,'http2_header_table_size':4096,'http2_initial_window_size':65535}[key]
                when={'http_version':'HTTP_2'}
                if key!='http2_frame_header_bytes': when['http2_settings_phase']='INITIAL_DEFAULTS'
                native.update(conditional_defaults=[{'when':when,'value':value}],default_status='PROPOSED_CONDITIONAL')
            if key=='http2_enable_push':
                native.update(conditional_defaults=[{'when':{'http_version':'HTTP_2','http2_settings_phase':'INITIAL_DEFAULTS','http_role':role},'value':value} for role,value in [('CLIENT',1),('SERVER',0)]],default_status='PROPOSED_CONDITIONAL')
            if key in {'http3_qpack_max_table','http3_qpack_blocked_streams'}:
                native.update(conditional_defaults=[{'when':{'http_version':'HTTP_3','http3_settings_phase':'INITIAL_1RTT'},'value':'0'}],default_status='PROPOSED_CONDITIONAL')
            if key=='http_port':
                native.update(conditional_defaults=[{'when':{'http_scheme':scheme,'http_port_explicit':False},'value':port} for scheme,port in [('http',80),('https',443)]],default_status='PROPOSED_CONDITIONAL')
            fields.append(native)
        for key,kind,unit,options,minimum,maximum,meaning in [('http_transition_token',
  'select',
  None,
  ['TLS', 'WEBSOCKET', 'CONNECT_UDP', 'CONNECT_IP', 'CONNECT_TCP', 'DEVICE_SPECIFIC'],
  None,
  None,
  'Actual upgrade/CONNECT protocol, unknown. RFC9931 distinguishes TLS, WebSocket, UDP/IP tunneling and '
  'untrusted TCP CONNECT; source alone does not override prohibited optimistic sending.'),
 ('http_connect_untrusted',
  'boolean',
  None,
  None,
  None,
  None,
  'Actual CONNECT forwarding on behalf of untrusted TCP client, unknown. Do not assume trusted false; '
  'wait-success or Connection:close required for HTTP1.'),
 ('http_wait_success',
  'boolean',
  None,
  None,
  None,
  None,
  'Actual proxy waits for successful2xx before forwarding TCP payload, unknown. Distinct from application '
  'deadline and declared source text.'),
 ('http_connection_close',
  'boolean',
  None,
  None,
  None,
  None,
  'Actual Connection:close request/rejection connection behavior. HTTP1 untrusted CONNECT requires close or '
  'wait; rejecting proxy must close underlying connection under RFC9931.'),
 ('http_transition_rejected',
  'boolean',
  None,
  None,
  None,
  None,
  'Actual CONNECT transition rejection state, unknown. Underlying connection must be closed by HTTP1 '
  'rejecting proxy without processing further requests.')]:
            native=field(key,key.replace('http_','').replace('_',' '),'communication','route',field_type=kind,
                unit=unit,options=options,minimum=minimum,maximum=maximum,description=meaning,simulation_relevant=False)
            native.update(required=False,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',
                source='https://www.rfc-editor.org/rfc/rfc9931.html',source_revision='RFC9931 March2026 sections6/8')
            fields.append(native)
    if technology_id == 'hart':
        source=REVIEW_RATE_PROPOSALS['hart']
        fields=[item for item in fields if item['key'] not in {'reserved_bandwidth_percent', 'retry_limit', 'gateway_maximum_throughput', 'gateway_input_buffer', 'gateway_maximum_routes', 'sync_method', 'qos_priority', 'queue_size', 'retransmission_enabled', 'retransmission_delay_ms', 'retransmission_rate', 'queue_policy', 'gateway_output_buffer', 'gateway_maximum_messages_s'}]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=source['source'],source_revision=source['source_revision'],simulation_relevant=False,
                    description='Actual encoded HART data excl response status; count/whole frame differ, no8-byte default.')
        for key,kind,unit,options,minimum,maximum,meaning in [('hart_profile',
  'select',
  None,
  ['PUBLIC_FSK_2023', 'FCG_FSK_2016', 'DEVICE_SPECIFIC'],
  None,
  None,
  'Actual selected implementation/revision scope. Public FSK rules do not certify C8PSK, WirelessHART or '
  'HART-IP.'),
 ('hart_phy',
  'select',
  None,
  ['FSK', 'C8PSK'],
  None,
  None,
  'Actual wired modulation. FSK standard baseline1200bit/s; C8PSK9600bit/s is a different mode requiring '
  'actual matched modem. HART-IP/WirelessHART need separate transport paths.'),
 ('hart_revision',
  'select',
  None,
  ['REV5_OR_EARLIER', 'REV6', 'REV7', 'DEVICE_SPECIFIC'],
  None,
  None,
  'Actual peer universal-command revision, unknown. Polling range and command capability must match it; not '
  'automatically latest7.'),
 ('hart_role',
  'select',
  None,
  ['HOST', 'FIELD_DEVICE'],
  None,
  None,
  'Actual sending endpoint role, unknown. Requests originate at host; response/burst at field device.'),
 ('hart_host_role',
  'select',
  None,
  ['PRIMARY', 'SECONDARY'],
  None,
  None,
  'Actual interacting host identity, unknown. Primary/secondary arbitration and quiet times differ; not '
  'universal primary master.'),
 ('hart_binding_source',
  'text',
  None,
  None,
  None,
  None,
  'Required actual registered modem/port/current-loop binding and both endpoint capabilities, unknown.'),
 ('hart_device_source',
  'text',
  None,
  None,
  None,
  None,
  'Required actual device description/revision/commands/preamble and response behavior, unknown.'),
 ('hart_physical_source',
  'text',
  None,
  None,
  None,
  None,
  'Required actual impedance/cable/power/coupling/modem/IS/filtering evidence, unknown; nominal FSK rate '
  'does not prove installation.'),
 ('hart_schedule_source',
  'text',
  None,
  None,
  None,
  None,
  'Required actual host arbitration, command turnaround, retry/burst and complete transaction schedule '
  'evidence, unknown.'),
 ('hart_mode',
  'select',
  None,
  ['REQUEST_RESPONSE', 'BURST'],
  None,
  None,
  'Actual request/response or device-supported enabled burst mode, unknown. Generic multicast is not wired '
  'HART burst.'),
 ('hart_frame_kind',
  'select',
  None,
  ['REQUEST', 'RESPONSE', 'BURST'],
  None,
  None,
  'Actual frame direction/category; status and delimiter differ between request and field response/burst.'),
 ('hart_address_format',
  'select',
  None,
  ['SHORT', 'LONG'],
  None,
  None,
  'Actual encoded short1-byte or long5-byte address; long unique identity is distinct from polling number.'),
 ('hart_address_bytes',
  'number',
  'Byte',
  None,
  1,
  5,
  'Actual address field octets: short1, long5. No arbitrary2/3/4-byte encoding.'),
 ('hart_poll_address',
  'number',
  None,
  None,
  0,
  63,
  'Actual device polling number, unknown: rev5-or-earlier0..15, rev6+0..63. Point-to-point0 is a proposal, '
  'not a real device assignment.'),
 ('hart_topology',
  'select',
  None,
  ['POINT_TO_POINT', 'MULTIDROP'],
  None,
  None,
  'Actual current-loop topology, unknown. Multidrop analog fixed-current behavior requires actual '
  'revision/device configuration.'),
 ('hart_expanded_device_type',
  'number',
  None,
  None,
  0,
  16383,
  'Actual14-bit expanded device type in qualified long-address layout, unknown; not an automatically '
  'generated device identifier.'),
 ('hart_device_id',
  'number',
  None,
  None,
  0,
  16777215,
  'Actual24-bit device ID in qualified long-address layout, unknown; host and burst flags are separate.'),
 ('hart_preamble_bytes',
  'number',
  'Byte',
  None,
  5,
  20,
  'Actual transmitted0xFF preamble octets in public FSK profile. Peer-specific required length and detection '
  'loss matter;5 is not a safe default for every unknown peer.'),
 ('hart_peer_preamble_bytes',
  'number',
  'Byte',
  None,
  5,
  20,
  'Actual required preamble length learned from matching field device, unknown. Configured transmit preamble '
  'must be at least this.'),
 ('hart_delimiter',
  'number',
  None,
  None,
  0,
  255,
  'Actual delimiter octet; qualified FSK encodes address length, expansion count and frame category. C8PSK '
  'delimiter rules not inferred from asynchronous FSK.'),
 ('hart_expansion_bytes',
  'number',
  'Byte',
  None,
  0,
  3,
  'Actual encoded expansion bytes matching delimiter. Normal0 proposal belongs to qualified public FSK '
  'layout; future extensions need revision evidence.'),
 ('hart_command',
  'number',
  None,
  None,
  0,
  255,
  'Actual wire command octet, unknown. Command31 carries extended16-bit command in data; command support and '
  'response semantics remain device-specific.'),
 ('hart_extended_command',
  'number',
  None,
  None,
  0,
  65535,
  'Actual16-bit extended command when wire command31, unknown; its two bytes must be included in transmitted '
  'data length, not extra hidden overhead.'),
 ('hart_command_source',
  'text',
  None,
  None,
  None,
  None,
  'Actual supported command, request/response data layout, units and encoding source, unknown. Generic data '
  'length does not prove functional command compatibility.'),
 ('hart_status_bytes',
  'number',
  'Byte',
  None,
  0,
  2,
  'Actual status length: request0, field response/burst2 in qualified FSK layout.'),
 ('hart_data_bytes',
  'number',
  'Byte',
  None,
  0,
  255,
  'Actual encoded data octets excluding response status, including extended-command bytes when present. '
  'Request/response layouts differ; no8-byte default.'),
 ('hart_byte_count',
  'number',
  'Byte',
  None,
  0,
  255,
  'Actual byte-count field = data plus status octets, excluding checksum. Response data at most253 when '
  'status2; not a universal complete255-byte frame limit.'),
 ('hart_checksum_bytes',
  'number',
  'Byte',
  None,
  1,
  1,
  'One transmitted XOR checksum octet in qualified public FSK layout; checksum covers delimiter through '
  'data, excluding preamble. Numeric length is not executed integrity evidence.'),
 ('hart_checksum_source',
  'text',
  None,
  None,
  None,
  None,
  'Actual XOR calculation and observed parity/byte stream evidence, unknown; no auto-confirmed checksum or '
  'authentication.'),
 ('hart_wire_octets',
  'number',
  'Byte',
  None,
  0,
  None,
  'Actual whole frame incl preamble/delimiter/address/expansion/command/count/status/data/checksum. Separate '
  'from data and byte count.'),
 ('hart_char_bits',
  'number',
  'bit',
  None,
  11,
  11,
  'FSK asynchronous character:1start+8dataLSB-first+odd parity+1stop=11bits. These bounds apply only to '
  'selected qualified FSK profile; not generic8N1.'),
 ('hart_wire_bits',
  'number',
  'bit',
  None,
  0,
  None,
  'Actual serialization bits including all qualified FSK characters, not payload×8. C8PSK encoded stream '
  'needs actual physical evidence.'),
 ('hart_serialization_ms',
  'number',
  'ms',
  None,
  0,
  None,
  'Actual frame serialization time from complete encoded bits and selected physical rate, excluding '
  'turnaround/gaps/arbitration; not whole transaction latency.'),
 ('hart_gap_us',
  'number',
  'us',
  None,
  0,
  None,
  'Actual worst inter-character gap; qualified FCG FSK rule requires less than one11-bit character time. No '
  'universal gap0 default.'),
 ('hart_slave_timeout_chars',
  'number',
  'character',
  None,
  28,
  28,
  'Qualified FieldComm2016 FSK slave timeout28character times; timeout is not actual device processing '
  'latency or application deadline.'),
 ('hart_hold_chars',
  'number',
  'character',
  None,
  2,
  2,
  'Qualified FieldComm2016 FSK HOLD2character times, separate from frame serialization and actual modem '
  'turnaround.'),
 ('hart_link_grant_chars',
  'number',
  'character',
  None,
  8,
  8,
  'Qualified FieldComm2016 FSK link grant RT2=8character times.'),
 ('hart_quiet_chars',
  'number',
  'character',
  None,
  0,
  None,
  'Qualified FieldComm2016 FSK RT1 primary33/secondary41character times. Master identity must be explicit.'),
 ('hart_response_start_ms',
  'number',
  'ms',
  None,
  0,
  None,
  'Actual request-end to response-start upper bound incl device and modem, unknown; qualified FCG timeout '
  'relation applies. Does not include response duration.'),
 ('hart_retry_limit',
  'number',
  'attempts',
  None,
  0,
  None,
  'Actual host/device retry budget, unknown; no inherited CAN0 or Siemens client-specific universal value.'),
 ('hart_retry_bound_ms',
  'number',
  'ms',
  None,
  0,
  None,
  'Actual total additional retry/arbitration recovery bound, unknown. Per-message or transport-independent '
  'timeout cannot substitute.'),
 ('hart_burst_supported',
  'boolean',
  None,
  None,
  None,
  None,
  'Actual endpoint burst capability confirmed by device source, unknown; enabling mode must not fabricate '
  'support.'),
 ('hart_burst_period_ms',
  'number',
  'ms',
  None,
  0,
  None,
  'Actual device/revision configured burst schedule, unknown. Tutorial3-4updates/s is illustrative, not a '
  'universal standard period.'),
 ('hart_loop_load_ohms',
  'number',
  'Ohm',
  None,
  230,
  600,
  'Actual loop receiver resistor/communication load for qualified TI FSK example230..600Ohm, typically250. '
  'Bounds are not universal total loop impedance; device-specific topology requires actual source.'),
 ('hart_loop_supply_v',
  'number',
  'V',
  None,
  0,
  None,
  'Actual loop supply and device compliance budget, unknown; not a universal24V supply.'),
 ('hart_loop_current_ma',
  'number',
  'mA',
  None,
  0,
  None,
  'Actual operating analog loop current, unknown;4..20mA measurement range and multidrop fixed current are '
  'not arbitrary digital defaults.'),
 ('hart_signal_pp_ma',
  'number',
  'mA',
  None,
  0,
  None,
  'Actual FSK signal amplitude at matched load, unknown.1mApp is nominal tutorial value, not measured '
  'endpoint evidence.'),
 ('hart_cable_cap_pf',
  'number',
  'pF',
  None,
  0,
  None,
  'Actual cable/receiver capacitance and length/loading bound, unknown; not I2C400pF or an inferred '
  'universal cable length.'),
 ('hart_is_required',
  'boolean',
  None,
  None,
  None,
  None,
  'Actual hazardous-area/intrinsic-safety requirement, unknown; HART name does not imply certified safe '
  'installation.'),
 ('hart_is_source',
  'text',
  None,
  None,
  None,
  None,
  'Actual matched barriers/entities/cable/loop intrinsically-safe certification evidence, unknown; separate '
  'from message checksum.')]:
            native=field(key,key.replace('hart_','').replace('_',' '),'communication','route',field_type=kind,
                unit=unit,options=options,minimum=minimum,maximum=maximum,description=meaning,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['hart']['required_parameters'],
                integer=kind=='number' and unit not in {'ms','us','Ohm','V','mA','pF'},
                parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',source=source['source'],source_revision=source['source_revision'])
            if key in {'hart_peer_preamble_bytes', 'hart_expanded_device_type', 'hart_char_bits', 'hart_preamble_bytes', 'hart_loop_load_ohms', 'hart_checksum_bytes', 'hart_device_id'}: native['schema_when']={'hart_profile': ['PUBLIC_FSK_2023', 'FCG_FSK_2016'], 'hart_phy': ['FSK']}
            if key in {'hart_slave_timeout_chars','hart_hold_chars','hart_link_grant_chars','hart_quiet_chars'}:
                native.update(schema_when={'hart_profile':['FCG_FSK_2016'],'hart_phy':['FSK']},source='https://support.fieldcommgroup.org/support/solutions/articles/8000040648-how-is-character-time-calculated-',source_revision='FieldComm character-time support article2016-11-11')
            if key=='hart_expanded_device_type': native['schema_when']['hart_revision']=['REV6','REV7']
            if key in {'hart_phy','hart_char_bits','hart_expansion_bytes','hart_checksum_bytes'}:
                value={'hart_phy':'FSK','hart_char_bits':11,'hart_expansion_bytes':0,'hart_checksum_bytes':1}[key]
                native.update(conditional_defaults=[{'when':{'hart_profile':'PUBLIC_FSK_2023'},'value':value}],default_status='PROPOSED_CONDITIONAL')
            if key in {'hart_slave_timeout_chars','hart_hold_chars','hart_link_grant_chars'}:
                value={'hart_slave_timeout_chars':28,'hart_hold_chars':2,'hart_link_grant_chars':8}[key]
                native.update(conditional_defaults=[{'when':{'hart_profile':'FCG_FSK_2016','hart_phy':'FSK'},'value':value}],default_status='PROPOSED_CONDITIONAL')
            if key=='hart_quiet_chars':
                native.update(conditional_defaults=[{'when':{'hart_profile':'FCG_FSK_2016','hart_phy':'FSK','hart_host_role':host},'value':n} for host,n in [('PRIMARY',33),('SECONDARY',41)]],default_status='PROPOSED_CONDITIONAL')
            fields.append(native)
    if technology_id == 'gpio':
        source=REVIEW_RATE_PROPOSALS['gpio']
        fields=[item for item in fields if item['key'] not in {'corruption_probability', 'gateway_maximum_messages_s', 'gateway_delay_ms', 'retransmission_delay_ms', 'reordering_probability', 'warning_threshold', 'gateway_maximum_throughput', 'retry_limit', 'retransmission_rate', 'critical_threshold', 'reserved_bandwidth_percent', 'payload_bytes', 'peak_factor', 'gateway_queue_delay_ms', 'protocol_conversion_delay_ms', 'target_bus_load_percent', 'queue_policy', 'sync_method', 'burst_window_ms', 'burst_factor', 'overload_threshold', 'frame_loss_probability', 'packet_loss_probability', 'bit_error_rate', 'gateway_input_buffer', 'gateway_maximum_routes', 'queue_size', 'retransmission_enabled', 'gateway_output_buffer', 'duplicate_probability', 'qos_priority'}]
        for key,kind,unit,options,minimum,maximum,meaning in [('gpio_profile',
  'select',
  None,
  ['STM8TL5_RM0312_3', 'DEVICE_SPECIFIC'],
  None,
  None,
  'Actual GPIO device profile, unknown; digital pin is not a packet bus and has no universal baud or '
  'voltage.'),
 ('gpio_pin',
  'text',
  None,
  None,
  None,
  None,
  'Required actual port/pin/package identity and ownership, unknown; unavailable package pins and '
  'alternate-function conflicts must be resolved.'),
 ('gpio_device_source',
  'text',
  None,
  None,
  None,
  None,
  'Required actual datasheet/pinout/revision/clock/threshold/drive/interrupt capabilities, unknown.'),
 ('gpio_wiring_source',
  'text',
  None,
  None,
  None,
  None,
  'Required actual peer wiring/voltage domains/load/pull resistors/isolation/contention and physical limits, '
  'unknown.'),
 ('gpio_phase',
  'select',
  None,
  ['OPERATING', 'RESET'],
  None,
  None,
  'Actual operating versus reset state. Reset defaults do not overwrite programmed application outputs.'),
 ('gpio_direction',
  'select',
  None,
  ['DIGITAL_INPUT', 'DIGITAL_OUTPUT', 'ALTERNATE', 'ANALOG_HIGH_Z'],
  None,
  None,
  'Actual pin mode, unknown. Qualified non-exception STM8TL reset proposes input only; alternate functions '
  'use a separate explicit technology.'),
 ('gpio_reset_exception',
  'boolean',
  None,
  None,
  None,
  None,
  'Actual pin/package exception to reset configuration from datasheet, unknown; e.g. PA_CR1 reset differs. '
  'Never assume all reset pins float.'),
 ('gpio_pull',
  'select',
  None,
  ['NONE', 'UP', 'DOWN', 'DEVICE_SPECIFIC'],
  None,
  None,
  'Actual controller internal pull, unknown; reviewed STM8TL digital input supports NONE/UP, not universal '
  'pull-down.'),
 ('gpio_drive',
  'select',
  None,
  ['PUSH_PULL', 'PSEUDO_OPEN_DRAIN', 'TRUE_OPEN_DRAIN', 'DEVICE_SPECIFIC'],
  None,
  None,
  'Actual output driver/pad kind. True open-drain is pin-specific, not inferred from register option.'),
 ('gpio_active_low',
  'boolean',
  None,
  None,
  None,
  None,
  'Actual application polarity, unknown; electrical HIGH/LOW and functional active state are separate.'),
 ('gpio_level',
  'select',
  None,
  ['LOW', 'HIGH', 'HIGH_Z'],
  None,
  None,
  'Actual electrical drive/read state, unknown; floating input is not automatically logicLOW or safe '
  'actuation.'),
 ('gpio_input_mode',
  'select',
  None,
  ['POLLED', 'INTERRUPT'],
  None,
  None,
  'Actual input sampling/event mechanism, unknown. Output update does not require a slave address or input '
  'polling bound.'),
 ('gpio_event',
  'select',
  None,
  ['RISING', 'FALLING', 'BOTH_EDGES', 'HIGH_LEVEL', 'LOW_LEVEL', 'DEVICE_SPECIFIC'],
  None,
  None,
  'Actual selected interrupt sensitivity and controller support, unknown; no mandatory rising edge.'),
 ('gpio_debounce_enabled',
  'boolean',
  None,
  None,
  None,
  None,
  'Actual hardware/software debounce enabled, unknown; no universal debounce0ms or10ms.'),
 ('gpio_vdd_v',
  'number',
  'V',
  None,
  0,
  None,
  'Actual operating GPIO supply/domain voltage, unknown; datasheet governs min/max and pin '
  'tolerance.3.3/5/24V are not universal GPIO defaults.'),
 ('gpio_vil_max_v',
  'number',
  'V',
  None,
  None,
  None,
  'Actual receiving maximum low-input voltage at matched supply/temperature/logic mode, unknown.'),
 ('gpio_vih_min_v',
  'number',
  'V',
  None,
  None,
  None,
  'Actual receiving minimum high-input voltage at matched supply/temperature/logic mode, unknown.'),
 ('gpio_vol_max_v',
  'number',
  'V',
  None,
  None,
  None,
  'Actual driving worst-case low voltage at the actual sink load, unknown; must meet receiving VIL.'),
 ('gpio_voh_min_v',
  'number',
  'V',
  None,
  None,
  None,
  'Actual driving worst-case high voltage at the actual source load, unknown; must meet receiving VIH.'),
 ('gpio_sink_bound_ma',
  'number',
  'mA',
  None,
  0,
  None,
  'Actual safe per-pin sink-current bound for specified voltage, unknown; absolute maximum is not an '
  'operating default.'),
 ('gpio_source_bound_ma',
  'number',
  'mA',
  None,
  0,
  None,
  'Actual safe per-pin source-current bound for specified voltage, unknown; not universal20mA.'),
 ('gpio_sink_load_ma',
  'number',
  'mA',
  None,
  0,
  None,
  'Actual sink load, unknown; must fit per-pin limit and separately verified package/port aggregate.'),
 ('gpio_source_load_ma',
  'number',
  'mA',
  None,
  0,
  None,
  'Actual source load, unknown; must fit pin and actual port/package aggregate.'),
 ('gpio_pull_source',
  'text',
  None,
  None,
  None,
  None,
  'Actual external pull-up/down resistance/load/rise/fall/rail and leakage evidence, unknown; open-drain '
  'high state needs explicit pull network.'),
 ('gpio_pull_ohms',
  'number',
  'Ohm',
  None,
  0,
  None,
  'Actual external resistor value, unknown; no universal4.7k resistor. An explicitly present resistor must '
  'be positive.'),
 ('gpio_load_pf',
  'number',
  'pF',
  None,
  0,
  None,
  'Actual pad+wiring+peer load capacitance, unknown; no universal I2C400pF limit or timing default for '
  'GPIO.'),
 ('gpio_rise_bound_ns',
  'number',
  'ns',
  None,
  0,
  None,
  'Actual pin transition upper bound at actual load/slew/drive conditions, unknown; nominal MCU clock does '
  'not prove this.'),
 ('gpio_fall_bound_ns',
  'number',
  'ns',
  None,
  0,
  None,
  'Actual falling transition upper bound, unknown, separate from source/target software processing.'),
 ('gpio_transition_source',
  'text',
  None,
  None,
  None,
  None,
  'Actual register-write/configuration sequence and intermediate-state/glitch/interrupt masking evidence, '
  'unknown; required for deliberate mode transitions.')]:
            native=field(key,key.replace('gpio_','').replace('_',' '),'physical','device',field_type=kind,
                unit=unit,options=options,minimum=minimum,maximum=maximum,description=meaning,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['gpio']['required_parameters'],
                parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',source=source['source'],source_revision=source['source_revision'])
            if key in {'gpio_direction','gpio_pull'}:
                native.update(conditional_defaults=[{'when':{'gpio_profile':'STM8TL5_RM0312_3','gpio_phase':'RESET','gpio_reset_exception':False},
                    'value':'DIGITAL_INPUT' if key=='gpio_direction' else 'NONE'}],default_status='PROPOSED_CONDITIONAL')
            fields.append(native)
    if technology_id == 'goose':
        source=REVIEW_RATE_PROPOSALS['goose']
        # Explicit composition of the reviewed raw IEEE802.3 transport and
        # GOOSE application schema; never an implicit foreign transport fallback.
        fields=_parameter_form_schema('ethernet',
            {**technology,'id':'ethernet','default_stack':['ethernet']},
            {**rate_source,'id':'ethernet'},review)
        for item in fields:
            if item['key'] in {'qos_priority','vlan_id'}:
                item.update(conditional_defaults=[{'when':{'goose_profile':'LIBIEC61850_1_6_L2','goose_vlan_tag':True},
                    'value':4 if item['key']=='qos_priority' else 0}],default_status='PROPOSED_CONDITIONAL')
            if item['key']=='payload_bytes':
                item['description']='Actual L2 GOOSE8-byte header plus full encoded APDU as MAC-client octets; allData/counts are separate. No8-byte default.'
        for key,kind,unit,options,minimum,maximum,meaning in [('goose_profile',
  'select',
  None,
  ['LIBIEC61850_1_6_L2', 'DEVICE_SPECIFIC'],
  None,
  None,
  'Actual L2 GOOSE implementation/profile. Library-qualified proposals and bounds are not a universal IED '
  'profile or R-GOOSE UDP configuration.'),
 ('goose_edition',
  'select',
  None,
  ['ED1', 'ED2', 'ED2_1', 'DEVICE_SPECIFIC'],
  None,
  None,
  'Actual IEC edition and supported encoding/security extensions, unknown; edition alone does not select '
  'library firmware.'),
 ('goose_role',
  'select',
  None,
  ['PUBLISHER', 'SUBSCRIBER'],
  None,
  None,
  'Actual control-block role; publisher retransmission and subscriber loss/acceptance are distinct.'),
 ('goose_binding_source',
  'text',
  None,
  None,
  None,
  None,
  'Required actual L2 MAC/PHY/port/VLAN/multicast path, not UDP/IP/MMS transport. Routed GOOSE needs an '
  'independent explicit transport path.'),
 ('goose_scl_source',
  'text',
  None,
  None,
  None,
  None,
  'Required actual SCL/GoCB/dataset/member order and engineering revision, unknown.'),
 ('goose_device_source',
  'text',
  None,
  None,
  None,
  None,
  'Required actual firmware/implementation/PIXIT/PICS/security and supported encoding source, unknown.'),
 ('goose_schedule_source',
  'text',
  None,
  None,
  None,
  None,
  'Required actual state-change burst/retransmission/steady rates and competing LAN schedule source; link '
  'speed alone proves no event response time.'),
 ('goose_encoding',
  'select',
  None,
  ['ASN1_BER', 'FIXED_LENGTH', 'DEVICE_SPECIFIC'],
  None,
  None,
  'Actual GOOSE dataset/APDU encoding, unknown; reviewed library publisher uses BER, not universal '
  'fixed8-byte overhead for allData.'),
 ('goose_ethertype',
  'number',
  None,
  None,
  0,
  65535,
  'Actual raw Ethernet GOOSE EtherType0x88B8=35000, distinct from Sampled Values, GSSE, IP or R-GOOSE.'),
 ('goose_appid',
  'number',
  None,
  None,
  0,
  65535,
  'Actual uint16 header APPID in reviewed library API, unknown. Actual IEC edition allocation/publisher '
  'uniqueness remains SCL evidence, no arbitrary0x1000 installation default.'),
 ('goose_vlan_tag',
  'boolean',
  None,
  None,
  None,
  None,
  'Actual L2 802.1Q tag presence, unknown; library createEx supports tag or no tag. PCP/VID apply only when '
  'tagged.'),
 ('goose_cb_ref',
  'text',
  None,
  None,
  None,
  None,
  'Actual GoCB reference, unknown, matched to subscriber SCL; never universal65-char limit from an older IEC '
  'edition.'),
 ('goose_dataset_ref',
  'text',
  None,
  None,
  None,
  None,
  'Actual dataset reference and stable member order, unknown.'),
 ('goose_id',
  'text',
  None,
  None,
  None,
  None,
  'Actual optional GoID/reference from device/SCL, unknown; no manufactured project identifier.'),
 ('goose_conf_rev',
  'number',
  None,
  None,
  0,
  4294967295,
  'Actual uint32 configuration revision, unknown; subscriber expected revision must match before operational '
  'acceptance.'),
 ('goose_expected_conf_rev',
  'number',
  None,
  None,
  0,
  4294967295,
  'Actual commissioned subscriber expected configuration revision, unknown.'),
 ('goose_st_num',
  'number',
  None,
  None,
  1,
  4294967295,
  'Actual state counter; reviewed library starts1, increments on state changes and skips0 on rollover. '
  'Initial1 is not a default for every observed frame.'),
 ('goose_sq_num',
  'number',
  None,
  None,
  0,
  4294967295,
  'Actual sequence counter; reviewed library resets0 on state change, increments per publication and rolls '
  'over to1.'),
 ('goose_test',
  'boolean',
  None,
  None,
  None,
  None,
  'Actual APDU test flag, unknown; distinct from edition-specific reserved-header simulation semantics and '
  'functional safety certification.'),
 ('goose_nds_com',
  'boolean',
  None,
  None,
  None,
  None,
  'Actual needs-commissioning flag, unknown; no automatic false confirmation.'),
 ('goose_num_entries',
  'number',
  None,
  None,
  0,
  4294967295,
  'Actual uint32 numDatSetEntries, unknown; must equal actual ordered allData element count.'),
 ('goose_actual_entries',
  'number',
  None,
  None,
  0,
  4294967295,
  'Actual encoded allData element count, unknown; data type/quality and BER sizes need actual member '
  'evidence.'),
 ('goose_timestamp_bytes',
  'number',
  'Byte',
  None,
  8,
  8,
  'Reviewed library UTC timestamp content8 octets, before ASN.1 tag/length; clock accuracy/status bits '
  'remain actual device evidence.'),
 ('goose_all_data_bytes',
  'number',
  'Byte',
  None,
  0,
  None,
  'Actual encoded allData container bytes including BER tag/length, unknown. Cannot infer bytes from entry '
  'count alone.'),
 ('goose_apdu_bytes',
  'number',
  'Byte',
  None,
  1,
  None,
  'Actual full BER GOOSE APDU bytes, unknown, including references/counters/TAL/time/flags/allData and '
  'variable length encodings.'),
 ('goose_header_bytes',
  'number',
  'Byte',
  None,
  8,
  8,
  'Raw L2 APPID/Length/Reserved1/Reserved2 header8 octets, excluding APDU and Ethernet '
  'header/tags/padding/FCS.'),
 ('goose_length_bytes',
  'number',
  'Byte',
  None,
  8,
  65535,
  'Actual raw L2 Length =8+APDU octets, excluding Ethernet pad and FCS; must fit selected actual MAC-client '
  'MTU.'),
 ('goose_reserved1',
  'number',
  None,
  None,
  0,
  65535,
  'Actual reserved header word1; reviewed library writes0. Edition/security simulation extensions need their '
  'own schema and source.'),
 ('goose_reserved2',
  'number',
  None,
  None,
  0,
  65535,
  'Actual reserved header word2; reviewed library writes0. No blanket universal security-extension default.'),
 ('goose_phase',
  'select',
  None,
  ['STATE_CHANGE', 'EVENT_REPEAT', 'STABLE'],
  None,
  None,
  'Actual publisher state-change/event-repeat/steady phase, unknown; event repeats are not generic '
  'reliability retries.'),
 ('goose_schedule_origin',
  'select',
  None,
  ['SCL', 'STACK_FALLBACK', 'DEVICE_SPECIFIC'],
  None,
  None,
  'Actual interval source. Qualified library fallback defaults apply only when actual SCL MinTime/MaxTime '
  'are absent.'),
 ('goose_min_ms',
  'number',
  'ms',
  None,
  1,
  None,
  'Actual fast-repeat interval from SCL/device; library config fallback500ms only in explicit fallback '
  'profile, not universal4ms.'),
 ('goose_max_ms',
  'number',
  'ms',
  None,
  1,
  None,
  'Actual steady interval from SCL/device; library fallback5000ms only explicitly selected, not generic '
  'cycle100ms.'),
 ('goose_event_repeats',
  'number',
  'frame',
  None,
  0,
  None,
  'Actual library/configured fast-repeat count after state change; qualified config fallback2, no universal '
  'retry budget.'),
 ('goose_next_ms',
  'number',
  'ms',
  None,
  1,
  None,
  'Actual announced/selected next publication interval; must fit advertised TAL. Event transitions and '
  'actual source schedule remain explicit.'),
 ('goose_tal_basis_ms',
  'number',
  'ms',
  None,
  1,
  None,
  'Actual library MinTime/MaxTime basis chosen for this TAL by publisher state machine; no '
  'universal2-times-TAL convention.'),
 ('goose_tal_ms',
  'number',
  'ms',
  None,
  1,
  4294967295,
  'Actual uint32 timeAllowedToLive in milliseconds. Library server sets3 times selected MinTime/MaxTime; '
  'other IED PIXIT may differ.'),
 ('goose_operating_mode',
  'select',
  None,
  ['OPERATIONAL', 'TEST', 'MONITOR'],
  None,
  None,
  'Actual subscriber application mode, unknown; monitoring a test frame does not make it valid operational '
  'input.'),
 ('goose_accept_operational',
  'boolean',
  None,
  None,
  None,
  None,
  'Actual operational acceptance, unknown; requires commissioned non-test data, matching revision/count, '
  'dataset/source evidence. No automatic acceptance from Ethernet rate.'),
 ('goose_acceptance_source',
  'text',
  None,
  None,
  None,
  None,
  'Actual subscriber filter/control-block/dataset/test/loss/out-of-order/rollover and application acceptance '
  'evidence, unknown.'),
 ('goose_security_source',
  'text',
  None,
  None,
  None,
  None,
  'Actual IEC62351/authentication/access assumptions and device support, unknown; sequence counters/CRC are '
  'not authentication or SIL certification.')]:
            native=field(key,key.replace('goose_','').replace('_',' '),'communication','route',field_type=kind,
                unit=unit,options=options,minimum=minimum,maximum=maximum,description=meaning,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['goose']['required_parameters'],integer=kind=='number',
                parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',source=source['source'],source_revision=source['source_revision'])
            if key in {'goose_timestamp_bytes','goose_appid','goose_conf_rev','goose_expected_conf_rev','goose_st_num','goose_sq_num','goose_num_entries','goose_actual_entries','goose_reserved1','goose_reserved2'}:
                native['schema_when']={'goose_profile':'LIBIEC61850_1_6_L2'}
            proposals={'goose_encoding':'ASN1_BER','goose_ethertype':35000,'goose_timestamp_bytes':8,'goose_header_bytes':8,'goose_reserved1':0,'goose_reserved2':0}
            fallback={'goose_min_ms':500,'goose_max_ms':5000,'goose_event_repeats':2}
            if key in proposals or key in fallback:
                when={'goose_profile':'LIBIEC61850_1_6_L2'}
                if key in fallback: when['goose_schedule_origin']='STACK_FALLBACK'
                native.update(conditional_defaults=[{'when':when,'value':proposals.get(key,fallback.get(key))}],default_status='PROPOSED_CONDITIONAL')
            fields.append(native)
    if technology_id == 'generic_serial':
        source=REVIEW_RATE_PROPOSALS['generic_serial']
        fields=[item for item in fields if item['key'] not in {'gateway_maximum_routes', 'qos_priority', 'retransmission_enabled', 'gateway_maximum_messages_s', 'retransmission_rate', 'reserved_bandwidth_percent', 'queue_size', 'retry_limit', 'gateway_output_buffer', 'queue_policy', 'gateway_input_buffer', 'sync_method', 'retransmission_delay_ms', 'gateway_maximum_throughput'}]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=source['source'],source_revision=source['source_revision'],simulation_relevant=False,
                    description='Actual qualified API stream-chunk or application octets, not UART character/wire count. No universal8-byte default or65535 maximum.')
        for key,kind,unit,options,minimum,maximum,meaning in [('gs_mode',
  'select',
  None,
  ['ASYNC_UART', 'SYNC_SERIAL', 'USB_CDC', 'CUSTOM_STREAM'],
  None,
  None,
  'Actual serial mechanism, unknown. A stream/COM-port name alone selects neither UART nor synchronous '
  'clocks nor native USB CDC.'),
 ('gs_transport_binding',
  'text',
  None,
  None,
  None,
  None,
  'Required actual registered serial/USB/PHY port and direction topology reference; no silent '
  'RS232/RS485/SPI binding.'),
 ('gs_implementation_source',
  'text',
  None,
  None,
  None,
  None,
  'Required device/firmware/clock/driver capabilities and revision, unknown. Generic Serial is an NIS '
  'abstraction, not a normative serial bus.'),
 ('gs_framing_source',
  'text',
  None,
  None,
  None,
  None,
  'Required actual message encoding/framing/escaping/integrity and byte/character boundary source, unknown; '
  'stream chunks are not necessarily complete messages.'),
 ('gs_uart_profile',
  'select',
  None,
  ['TB3216_8N1', 'AVR_FRAME_FORMATS', 'DEVICE_SPECIFIC'],
  None,
  None,
  'Explicit source-qualified async UART framing profile, unknown. TB3216 tutorial supplies '
  'conditional9600/8N1 proposals, not universal baud minimum.'),
 ('gs_baud_rate',
  'number',
  'Bd',
  None,
  1,
  None,
  'Actual async binary UART symbol rate, unknown until matched clock/divisor/configuration;9600 is '
  'conditional tutorial proposal, not generic minimum.'),
 ('gs_peer_baud_rate',
  'number',
  'Bd',
  None,
  1,
  None,
  'Actual peer configured baud rate; must agree with selected UART configuration. Clock error/oversampling '
  'tolerance needs actual device proof.'),
 ('gs_data_bits',
  'number',
  'bit',
  None,
  1,
  None,
  'Actual data bits per UART character; reviewed AVR5..9, tutorial8. Not application octets or USB packet '
  'size.'),
 ('gs_parity',
  'select',
  None,
  ['NONE', 'EVEN', 'ODD', 'MARK', 'SPACE', 'DEVICE_SPECIFIC'],
  None,
  None,
  'Actual UART parity; reviewed AVR NONE/EVEN/ODD only, tutorial NONE. Other devices require their own '
  'source.'),
 ('gs_start_bits',
  'number',
  'bit',
  None,
  1,
  None,
  'Actual UART start bits; reviewed AVR/tutorial1. Unknown device-specific layouts are not verified using '
  'AVR limits.'),
 ('gs_stop_bits',
  'number',
  'bit',
  None,
  0.5,
  None,
  'Actual UART stop-bit periods; reviewed AVR1 or2, tutorial1. Fractional stop periods are '
  'device-dependent.'),
 ('gs_char_bits',
  'number',
  'bit',
  None,
  1,
  None,
  'Actual start+data+parity+stop bit-periods per character. Tutorial8N1=10, AVR parity adds1. Not8 useful '
  'bits.'),
 ('gs_encoded_characters',
  'number',
  'character',
  None,
  1,
  None,
  'Actual serialized character count including framing/encoding/escaping/flow characters as applicable, '
  'unknown; not blindly equal to application payload octets.'),
 ('gs_wire_bits',
  'number',
  'bit',
  None,
  1,
  None,
  'Actual UART occupied bit-period count = encoded characters times character bits; start/stop/parity '
  'included.'),
 ('gs_serialization_us',
  'number',
  'us',
  None,
  0,
  None,
  'Actual UART serialization time = wire bit periods / binary UART baud times1e6, excluding actual gaps/flow '
  'stalls.'),
 ('gs_gap_bound_us',
  'number',
  'us',
  None,
  0,
  None,
  'Actual aggregate character/message/turnaround idle bound, unknown; zero only when explicitly justified.'),
 ('gs_flow_control',
  'select',
  None,
  ['NONE', 'RTS_CTS', 'XON_XOFF', 'DEVICE_SPECIFIC'],
  None,
  None,
  'Actual UART flow control and peer support, unknown. No automatic disabled flow-control assumption.'),
 ('gs_flow_bound_us',
  'number',
  'us',
  None,
  0,
  None,
  'Actual bounded UART flow-control blocking from both endpoints, unknown. Unbounded peer stalls do not '
  'prove capacity.'),
 ('gs_wire_bound_us',
  'number',
  'us',
  None,
  0,
  None,
  'Actual complete UART transfer bound at least serialization+aggregate idle+flow stalls, unknown; '
  'driver/application processing remains separate.'),
 ('gs_clock_hz',
  'number',
  'Hz',
  None,
  1,
  None,
  'Actual synchronous serial clock, unknown. Encoding/bits per clock/edge/role/word lengths supplied by '
  'actual bound port; never UART baud or USB speed.'),
 ('gs_cdc_line_coding_role',
  'select',
  None,
  ['NATIVE_ADVISORY', 'BRIDGE_UART', 'DEVICE_SPECIFIC'],
  None,
  None,
  'Actual CDC implementation interpretation of line coding, unknown. Arduino native CDC ignores Serial.begin '
  'baud for wire speed; USB-to-UART bridges require separate real UART binding.'),
 ('gs_framing',
  'select',
  None,
  ['NONE', 'FIXED_LENGTH', 'LENGTH_PREFIX', 'DELIMITER', 'DEVICE_SPECIFIC'],
  None,
  None,
  'Actual application message framing, unknown; optional line delimiters in TB3216 example are not mandatory '
  'for all serial streams.'),
 ('gs_message_bytes',
  'number',
  'Byte',
  None,
  0,
  None,
  'Actual application-message octets, unknown. Not API read/write chunk, UART characters, USB packets or '
  'encoded wire count.'),
 ('gs_max_message_bytes',
  'number',
  'Byte',
  None,
  1,
  None,
  'Actual implementation/application-message limit, unknown.65535 is not a generic serial standard maximum.')]:
            native=field(key,key.replace('gs_','').replace('_',' '),'communication','route',field_type=kind,
                unit=unit,options=options,minimum=minimum,maximum=maximum,description=meaning,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['generic_serial']['required_parameters'],
                integer=kind=='number' and key not in {'gs_stop_bits','gs_char_bits','gs_serialization_us','gs_gap_bound_us','gs_flow_bound_us','gs_wire_bound_us'},
                parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',source=source['source'],source_revision=source['source_revision'])
            proposals={'gs_baud_rate':9600,'gs_data_bits':8,'gs_parity':'NONE','gs_start_bits':1,'gs_stop_bits':1,'gs_char_bits':10}
            if key in proposals:
                native.update(conditional_defaults=[{'when':{'gs_mode':'ASYNC_UART','gs_uart_profile':'TB3216_8N1'},'value':proposals[key]}],default_status='PROPOSED_CONDITIONAL')
            fields.append(native)
    if technology_id == 'generic_can':
        source=REVIEW_RATE_PROPOSALS['generic_can']
        fields=[item for item in fields if item['key'] not in {'gateway_maximum_throughput', 'gateway_output_buffer', 'sync_method', 'gateway_input_buffer', 'retransmission_delay_ms', 'queue_size', 'bitrate', 'qos_priority', 'retransmission_rate', 'queue_policy', 'gateway_maximum_messages_s', 'retransmission_enabled', 'gateway_maximum_routes', 'retry_limit', 'reserved_bandwidth_percent'}]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=source['source'],source_revision=source['source_revision'],simulation_relevant=False,
                    description='Actual selected CAN-family wire data field. CC, FD discrete encoded lengths and XL limits are separate; no implicit padding or payload8 default.')
        for key,kind,unit,options,minimum,maximum,meaning in [('gcan_family',
  'select',
  None,
  ['CAN_CC', 'CAN_FD', 'CAN_XL'],
  None,
  None,
  'Actual transmitted frame family, unknown. A CAN FD/XL-capable controller may send CC frames, so '
  'controller capability does not select this family.'),
 ('gcan_transport_binding',
  'text',
  None,
  None,
  None,
  None,
  'Required actual registered can/can_fd/can_xl link/controller/PHY/bit-timing configuration reference, '
  'unknown. Generic wrapper has no independent physical rate.'),
 ('gcan_implementation_source',
  'text',
  None,
  None,
  None,
  None,
  'Required actual encoding/edition/controller/device capability reference, unknown. Generic CAN is an NIS '
  'abstraction, not a fourth normative CAN generation.'),
 ('gcan_schedule_source',
  'text',
  None,
  None,
  None,
  None,
  'Required actual identifier ownership/traffic/interference/error/queue schedule reference, unknown. Family '
  'shape does not prove arbitration response time.'),
 ('gcan_frame_format',
  'select',
  None,
  ['STANDARD', 'EXTENDED', 'XL'],
  None,
  None,
  'Actual CC/FD11-bit or29-bit frame format, or XL separated priority/acceptance format. No inferred '
  'standard format.'),
 ('gcan_frame_kind',
  'select',
  None,
  ['DATA', 'REMOTE'],
  None,
  None,
  'Actual DATA/REMOTE frame. Only CC supports remote requests; remote wire data is empty even when requested '
  'data length is nonzero.'),
 ('gcan_identifier',
  'number',
  None,
  None,
  0,
  536870911,
  'Actual CC/FD arbitration identifier, unknown. Standard11-bit ceiling2047, extended29-bit '
  'ceiling536870911. Not XL acceptance or priority field.'),
 ('gcan_priority_id',
  'number',
  None,
  None,
  0,
  2047,
  'Actual XL11-bit priority ID, unknown. Not a CAN CC/FD application identifier or generic QoS priority3.'),
 ('gcan_acceptance_field',
  'number',
  None,
  None,
  0,
  4294967295,
  'Actual XL32-bit acceptance field, unknown, separate from arbitration priority.'),
 ('gcan_requested_bytes',
  'number',
  'Byte',
  None,
  0,
  8,
  'Actual CC remote requested length0..8, unknown; not transmitted remote payload or FD/XL data length.')]:
            native=field(key,key.replace('gcan_','').replace('_',' '),'communication','route',field_type=kind,
                unit=unit,options=options,minimum=minimum,maximum=maximum,description=meaning,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['generic_can']['required_parameters'],integer=kind=='number',
                parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',source=source['source'],source_revision=source['source_revision'])
            fields.append(native)
    if technology_id == 'fsoe':
        source=REVIEW_RATE_PROPOSALS['fsoe']
        fields=[item for item in fields if item['key'] not in {'retry_limit', 'bitrate', 'queue_size', 'qos_priority', 'gateway_output_buffer', 'sync_method', 'reserved_bandwidth_percent', 'gateway_input_buffer', 'retransmission_enabled', 'retransmission_delay_ms', 'gateway_maximum_throughput', 'mtu_bytes', 'queue_policy', 'gateway_maximum_routes', 'retransmission_rate', 'gateway_maximum_messages_s', 'duplex', 'vlan_id', 'rate_limit_bit_s'}]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.pop('max',None)
                item.update(min=1,integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    schema_when={'fsoe_profile':'BASE_5100_1_2'},
                    source=source['source'],source_revision=source['source_revision'],simulation_relevant=False,
                    description='Actual selected-direction safe data: one byte or even count for reviewed base format; mapped complete container capacity is separate.')
        for key,kind,unit,options,minimum,maximum,default,meaning in [('fsoe_profile',
  'select',
  None,
  ['BASE_5100_1_2', 'ENHANCEMENTS_5120', 'DEVICE_SPECIFIC'],
  None,
  None,
  'BASE_5100_1_2',
  'Source-qualified base declaration proposal; ETG5120 enhancements require independent matched '
  'edition/implementation bounds.'),
 ('fsoe_role',
  'select',
  None,
  ['MASTER', 'SLAVE'],
  None,
  None,
  None,
  'Actual safety protocol instance role; EtherCAT main-device/subdevice roles are independent.'),
 ('fsoe_transport_binding',
  'text',
  None,
  None,
  None,
  None,
  None,
  'Required actual black-channel link/process-data/buffer mapping reference; no implicit '
  'EtherCAT100M/Ethernet inherited rate.'),
 ('fsoe_implementation_source',
  'text',
  None,
  None,
  None,
  None,
  None,
  'Required matched actual safety device/firmware/protocol edition and supported data limits reference, '
  'unknown.'),
 ('fsoe_connection_source',
  'text',
  None,
  None,
  None,
  None,
  None,
  'Required actual unique connection ID/slave address/parameter/configuration reference, unknown.'),
 ('fsoe_timing_source',
  'text',
  None,
  None,
  None,
  None,
  None,
  'Required actual direction-dependent watchdog/whole exchange/transport mapping bounds and endpoint timing '
  'reference, unknown.'),
 ('fsoe_direction',
  'select',
  None,
  ['MASTER_TO_SLAVE', 'SLAVE_TO_MASTER'],
  None,
  None,
  None,
  'Actual safe-data direction. Configured input/output lengths may differ; never duplicate one length into '
  'both.'),
 ('fsoe_master_safe_bytes',
  'number',
  'Byte',
  None,
  1,
  None,
  None,
  'Actual master-to-slave safe-data capacity, unknown. One byte or even count; bounded by actual '
  'device/process-data mapping.'),
 ('fsoe_slave_safe_bytes',
  'number',
  'Byte',
  None,
  1,
  None,
  None,
  'Actual slave-to-master safe-data capacity, unknown, independent of master direction. No '
  'universal1486-byte maximum.'),
 ('fsoe_crc_count',
  'number',
  None,
  None,
  1,
  None,
  None,
  'Actual CRC word count=ceil(selected safe bytes/2). One-byte exception uses virtual zero in CRC '
  'calculation, not an extra wire payload byte.'),
 ('fsoe_crc_word_bytes',
  'number',
  'Byte',
  None,
  2,
  2,
  2,
  'Baseline two-octet CRC field per block; not a single checksum overhead for all safe data.'),
 ('fsoe_command_bytes',
  'number',
  'Byte',
  None,
  1,
  1,
  1,
  'Baseline one command octet; not an EtherCAT datagram header.'),
 ('fsoe_connection_bytes',
  'number',
  'Byte',
  None,
  2,
  2,
  2,
  'Baseline two ConnID octets at end of PDU; connection identifier differs from safety slave address.'),
 ('fsoe_frame_bytes',
  'number',
  'Byte',
  None,
  6,
  None,
  None,
  'Actual safety container CMD+safe data+2*CRCcount+ConnID. Six-byte minimum corresponds to one safe byte; '
  'excludes black-channel framing.'),
 ('fsoe_pdo_capacity_bytes',
  'number',
  'Byte',
  None,
  6,
  None,
  None,
  'Actual mapped black-channel process-data container capacity; full FSoE frame must fit, not just safe '
  'payload.'),
 ('fsoe_state',
  'select',
  None,
  ['RESET', 'SESSION', 'CONNECTION', 'PARAMETER', 'DATA'],
  None,
  None,
  None,
  'Actual protocol state, unknown. Saved state declaration does not execute handshake or release safe '
  'outputs.'),
 ('fsoe_data_command',
  'select',
  None,
  ['PROCESS_DATA', 'FAILSAFE_DATA'],
  None,
  None,
  None,
  'Actual outgoing data-state command, unknown. Independent peer command is not inferred; no auto '
  'ProcessData release.'),
 ('fsoe_command',
  'number',
  None,
  None,
  0,
  255,
  None,
  'Actual wire command octet. Public base Reset0x2A/Data Process0x36/FailSafe0x08 constraints; remaining '
  'startup command encoding requires source.'),
 ('fsoe_conn_id',
  'number',
  None,
  None,
  0,
  65535,
  None,
  'Actual16-bit ConnID unknown. Zero before connection allocation/reset; Data requires nonzero. Uniqueness '
  'requires actual network configuration.'),
 ('fsoe_slave_address',
  'number',
  None,
  None,
  1,
  65535,
  None,
  'Actual configured16-bit safety slave address, unknown; must match endpoint setting. Distinct from '
  'EtherCAT address and ConnID.'),
 ('fsoe_peer_address',
  'number',
  None,
  None,
  1,
  65535,
  None,
  'Actual peer accepted/configured safety slave address, unknown, must equal selected endpoint address; '
  'scalar equality is not commissioning evidence.'),
 ('fsoe_session_id',
  'number',
  None,
  None,
  0,
  65535,
  None,
  'Actual locally generated16-bit session ID, unknown. Not default0, not an on-wire field in every Data '
  'PDU.'),
 ('fsoe_peer_session_id',
  'number',
  None,
  None,
  0,
  65535,
  None,
  'Actual independently generated peer session ID, unknown. Not forced equal to local session or copied from '
  'it.'),
 ('fsoe_sequence',
  'number',
  None,
  None,
  0,
  65535,
  None,
  'Actual internal virtual sequence, unknown; base Data1..65535, absent as a standalone wire field. '
  'Increment/rollover/CRC-change mechanism needs executor.'),
 ('fsoe_crc0',
  'number',
  None,
  None,
  0,
  65535,
  None,
  'Actual current16-bit CRC0, unknown. Scalar bounds do not recompute CRC chain/virtual '
  'sequence/session/ConnID/block index.'),
 ('fsoe_previous_crc0',
  'number',
  None,
  None,
  0,
  65535,
  None,
  'Actual previous received CRC0 in inherited chain, unknown. Not default0 outside actual reset.'),
 ('fsoe_crc_source',
  'text',
  None,
  None,
  None,
  None,
  None,
  'Actual encoded/container/chain/sequence/session/block-index integrity evidence, unknown. Safety CRC is '
  'not cryptographic authentication.'),
 ('fsoe_master_watchdog_ms',
  'number',
  'ms',
  None,
  1,
  65535,
  None,
  'Actual base communication watchdog1..65535ms from matched configuration; no universal shortest1ms or '
  'sampled1000ms default.'),
 ('fsoe_slave_watchdog_ms',
  'number',
  'ms',
  None,
  1,
  65535,
  None,
  'Actual peer accepted same connection communication watchdog, independently sourced; setting alone is not '
  'a live watchdog or safety-response certificate.'),
 ('fsoe_exchange_bound_ms',
  'number',
  'ms',
  None,
  0.001,
  None,
  None,
  'Actual complete bidirectional exchange bound, unknown, must be below both configured watchdogs. Not a '
  'single EtherCAT frame cycle.'),
 ('fsoe_parameter_bytes',
  'number',
  'Byte',
  None,
  0,
  None,
  None,
  'Actual complete parameter-transfer stream bytes, unknown. Fragmented across frames if needed; not '
  'restricted to one frame or copied safe-data length.'),
 ('fsoe_parameter_remaining_bytes',
  'number',
  'Byte',
  None,
  0,
  None,
  None,
  'Actual remaining parameter stream count0..actual total, unknown. Counter alone does not certify accepted '
  'safety application parameters.'),
 ('fsoe_parameters_accepted',
  'boolean',
  None,
  None,
  None,
  None,
  None,
  'Actual peer parameter acceptance unknown; Data requires true declaration, but protocol/runtime acceptance '
  'remains unexecuted.'),
 ('fsoe_mapping_source',
  'text',
  None,
  None,
  None,
  None,
  None,
  'Actual ESI/PDO/black-channel buffering and direction/mapping version evidence, unknown; require '
  'verification after parameter changes.'),
 ('fsoe_safe_output_source',
  'text',
  None,
  None,
  None,
  None,
  None,
  'Actual defined failure/output response and safety application configuration, unknown. Do not infer '
  'all-zero application safe state universally.'),
 ('fsoe_safety_requirement',
  'select',
  None,
  ['SIL1', 'SIL2', 'SIL3', 'PL_A', 'PL_B', 'PL_C', 'PL_D', 'PL_E', 'DEVICE_SPECIFIC'],
  None,
  None,
  None,
  'Actual project safety-integrity requirement, unknown. Protocol capability alone does not certify '
  'device/system SIL or PL.'),
 ('fsoe_assurance_source',
  'text',
  None,
  None,
  None,
  None,
  None,
  'Actual matched safety-device/system validation/response/certificate reference, unknown. NIS declaration '
  'checks are not a safety certification.')]:
            native=field(key,key.replace('fsoe_','').replace('_',' '),'timing' if unit=='ms' else 'physical','route',
                field_type=kind,unit=unit,options=options,minimum=minimum,maximum=maximum,
                default=default if key=='fsoe_profile' else None,description=meaning,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['fsoe']['required_parameters'],
                integer=kind=='number' and key!='fsoe_exchange_bound_ms',
                parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                default_status='PROPOSED' if default is not None else 'UNKNOWN',
                source=source['source'],source_revision=source['source_revision'])
            if default is not None and key!='fsoe_profile':
                native.update(conditional_defaults=[{'when':{'fsoe_profile':'BASE_5100_1_2'},'value':default}],default_status='PROPOSED_CONDITIONAL')
            if key not in TECHNOLOGY_SEMANTICS['fsoe']['required_parameters']:
                native['schema_when']={'fsoe_profile':'BASE_5100_1_2'}
            fields.append(native)
    if technology_id == 'foundation_fieldbus_h1':
        source=REVIEW_RATE_PROPOSALS['foundation_fieldbus_h1']
        fields=[item for item in fields if item['key'] not in {'queue_policy', 'gateway_maximum_throughput', 'gateway_maximum_routes', 'gateway_output_buffer', 'qos_priority', 'retransmission_enabled', 'gateway_input_buffer', 'gateway_maximum_messages_s', 'retransmission_delay_ms', 'retry_limit', 'sync_method', 'queue_size', 'retransmission_rate', 'reserved_bandwidth_percent'}]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=source['source'],source_revision=source['source_revision'],simulation_relevant=False,
                    description='Actual FMS encoded data, not full telegram or logical segmented domain; applies to qualified DT layout only.')
        for key,kind,unit,options,minimum,maximum,default,meaning in [('ff_profile',
  'select',
  None,
  ['H1_VOLTAGE_MODE', 'DEVICE_SPECIFIC'],
  None,
  None,
  'H1_VOLTAGE_MODE',
  'Reviewed two-wire voltage-mode H1 baseline proposal. Optical/media extensions require their own physical '
  'evidence; HSE Ethernet is a different transport.'),
 ('ff_configuration_source',
  'text',
  None,
  None,
  None,
  None,
  None,
  'Required matched specification/firmware/network configuration reference, unknown.'),
 ('ff_cff_source',
  'text',
  None,
  None,
  None,
  None,
  None,
  'Required matched device CFF capability file/version, unknown. Capacity, timer and block constraints are '
  'not universal defaults.'),
 ('ff_physical_source',
  'text',
  None,
  None,
  None,
  None,
  None,
  'Required actual segment cable/power/terminator/repeater/signal/intrinsic-safety evidence, unknown.'),
 ('ff_schedule_source',
  'text',
  None,
  None,
  None,
  None,
  None,
  'Required actual LAS/VCR/block execution/communication schedule evidence, unknown. Schedule feasibility is '
  'not implied by bitrate.'),
 ('ff_layout',
  'select',
  None,
  ['YOKOGAWA_FMS_DIAGRAM', 'DEVICE_SPECIFIC'],
  None,
  None,
  'YOKOGAWA_FMS_DIAGRAM',
  'Qualified FMS/FAS/data-transfer diagram layout. Control PDUs and fragmented logical domains need their '
  'own definition.'),
 ('ff_pdu',
  'select',
  None,
  ['DT', 'CD', 'PT', 'RT', 'EC', 'DC', 'RI', 'PN', 'PR', 'TD', 'CT', 'RQ', 'RR', 'CL', 'TL', 'IDLE'],
  None,
  None,
  None,
  'Actual link PDU, unknown. Native control traffic is not an FMS data-transfer packet.'),
 ('ff_fms_pci_bytes',
  'number',
  'Byte',
  None,
  0,
  255,
  4,
  'Four-octet FMS PCI proposal only for reviewed FMS DT layout.'),
 ('ff_fas_pci_bytes',
  'number',
  'Byte',
  None,
  0,
  255,
  1,
  'One-octet FAS PCI proposal only for reviewed FMS DT layout.'),
 ('ff_dl_sdu_bytes',
  'number',
  'Byte',
  None,
  0,
  256,
  None,
  'Actual data-link SDU, equals FMS encoded payload plus FMS/FAS PCI in reviewed DT layout. Priority ceiling '
  'applies to DLSDU, not payload.'),
 ('ff_dl_pci_bytes',
  'number',
  'Byte',
  None,
  0,
  255,
  None,
  'Actual data-link PCI, unknown; reviewed DT diagram range5..15 octets. Not a universal overhead8.'),
 ('ff_fcs_bytes',
  'number',
  'Byte',
  None,
  0,
  255,
  2,
  'Two-octet frame-check sequence baseline proposal. A declared size does not recompute or verify '
  'integrity.'),
 ('ff_ph_sdu_bytes',
  'number',
  'Byte',
  None,
  0,
  None,
  None,
  'Actual complete DL PDU/physical SDU, including DL PCI/SDU/FCS. Reviewed FMS diagram range8..273; excludes '
  'physical delimiters/preamble.'),
 ('ff_preamble_bytes',
  'number',
  'Byte',
  None,
  1,
  None,
  1,
  'Baseline one-octet preamble proposal; actual repeaters may require extension. Lower baseline does not '
  'prove physical synchronization.'),
 ('ff_start_bytes',
  'number',
  'Byte',
  None,
  1,
  1,
  1,
  'One-octet-equivalent physical start delimiter proposal, includes non-data symbols; not an Ethernet '
  'preamble.'),
 ('ff_end_bytes',
  'number',
  'Byte',
  None,
  1,
  1,
  1,
  'One-octet-equivalent physical end delimiter proposal; not an Ethernet interframe gap.'),
 ('ff_wire_octets',
  'number',
  'octet-equivalents',
  None,
  0,
  None,
  None,
  'Actual physical telegram sum including preamble/start/end. Excludes idle/response/token exchanges and '
  'block execution; not whole transaction latency.'),
 ('ff_priority',
  'select',
  None,
  ['URGENT', 'NORMAL', 'TIME_AVAILABLE'],
  None,
  None,
  None,
  'Actual native DLL urgency, unknown. Qualified DLSDU ceilings64/128/256 bytes respectively; no CAN ID or '
  'Ethernet PCP conversion.'),
 ('ff_vcr',
  'select',
  None,
  ['PUBLISHER_SUBSCRIBER', 'CLIENT_SERVER', 'SOURCE_SINK'],
  None,
  None,
  None,
  'Actual VCR model. Buffered scheduled publication differs from queued client/server or source/sink token '
  'traffic.'),
 ('ff_access',
  'select',
  None,
  ['SCHEDULED_CD', 'UNSCHEDULED_PT'],
  None,
  None,
  None,
  'Actual native access mechanism. CD scheduled publication; PT unscheduled token passing. Not generic FIFO '
  'arbitration.'),
 ('ff_buffering',
  'select',
  None,
  ['BUFFERED', 'QUEUED'],
  None,
  None,
  None,
  'Actual VCR storage semantics; buffered publisher/subscriber is not a queue. Queue capacity remains actual '
  'CFF configuration.'),
 ('ff_device_class',
  'select',
  None,
  ['BASIC', 'LINK_MASTER', 'BRIDGE'],
  None,
  None,
  None,
  'Actual device class, unknown. BASIC cannot become LAS; link master and bridge have capability, not '
  'automatic active status.'),
 ('ff_las_active',
  'boolean',
  None,
  None,
  None,
  None,
  None,
  'Actual LAS active state, unknown. Exactly one active LAS per link requires topology/runtime evidence; not '
  'auto true.'),
 ('ff_las_owner',
  'text',
  None,
  None,
  None,
  None,
  None,
  'Actual LAS node identity, unknown. LAS service address4 differs from configured physical node address.'),
 ('ff_las_service_address',
  'number',
  None,
  None,
  4,
  4,
  4,
  'Reserved LAS service address4 baseline; does not allocate node address4 to an ordinary device.'),
 ('ff_node_address',
  'number',
  None,
  None,
  16,
  255,
  None,
  'Actual8-bit node address, unknown. Operational range16..247 differs from cleared248..251 and '
  'temporary252..255; LM/BASIC allocation uses actual FUN/NUN.'),
 ('ff_address_state',
  'select',
  None,
  ['OPERATIONAL', 'CLEARED', 'TEMPORARY'],
  None,
  None,
  None,
  'Actual address allocation category, unknown. A random commissioning address is not a persisted '
  'operational default.'),
 ('ff_fun',
  'number',
  None,
  None,
  16,
  247,
  None,
  'Actual boundary of link-master address pool, unknown. Not hard-coded16 or vendor sample20.'),
 ('ff_nun',
  'number',
  None,
  None,
  0,
  231,
  None,
  'Actual unused address count, unknown. BASIC start=FUN+NUN; actual address availability must be checked.'),
 ('ff_link_address',
  'number',
  None,
  None,
  0,
  65535,
  None,
  'Actual logical link16-bit identifier, unknown; may be omitted within a link, needed across bridge.'),
 ('ff_selector',
  'number',
  None,
  None,
  0,
  255,
  None,
  'Actual8-bit selector, unknown. DLCEP and DLSAP reserved allocation depends on VCR and device CFF, not '
  'just scalar range.'),
 ('ff_vcr_index',
  'number',
  None,
  None,
  0,
  None,
  None,
  'Actual device-local VCR index, unknown; device-specific capacity and supported index allocation require '
  'CFF.'),
 ('ff_pd_tag',
  'text',
  None,
  None,
  None,
  None,
  None,
  'Actual physical-device readable tag, unknown. Tag identity differs from numeric network address.'),
 ('ff_sm_state',
  'select',
  None,
  ['UNINITIALIZED', 'INITIALIZED', 'SM_OPERATIONAL'],
  None,
  None,
  None,
  'Actual system-management state, unknown. SM_OPERATIONAL is not inferred from address or selected '
  'profile.'),
 ('ff_macrocycle_us',
  'number',
  'us',
  None,
  0.001,
  None,
  None,
  'Actual configured communication/block macrocycle microseconds, unknown. No universal100ms '
  'CAN/application-cycle default.'),
 ('ff_scheduled_us',
  'number',
  'us',
  None,
  0,
  None,
  None,
  'Actual total scheduled communication occupied window microseconds. Complete CD/DT/response gaps and other '
  'scheduled traffic must be included by schedule source.'),
 ('ff_unscheduled_us',
  'number',
  'us',
  None,
  0,
  None,
  None,
  'Actual available unscheduled budget microseconds, unknown; cannot be treated as zero merely because '
  'schedule is absent.'),
 ('ff_maintenance_us',
  'number',
  'us',
  None,
  0,
  None,
  None,
  'Actual maintenance/synchronization/probing and remaining reserved macrocycle budget microseconds. Budget '
  'partition must sum to declared macrocycle.'),
 ('ff_publish_offset_us',
  'number',
  'us',
  None,
  0,
  None,
  None,
  'Actual publication offset within macrocycle microseconds, unknown; not block execution completion proof.'),
 ('ff_exchange_bound_us',
  'number',
  'us',
  None,
  0.001,
  None,
  None,
  'Actual bounded complete scheduled transaction duration microseconds including CD/DT/gaps/response. Wire '
  'telegram duration alone is insufficient.'),
 ('ff_token_hold_us',
  'number',
  'us',
  None,
  0.001,
  None,
  None,
  'Actual granted PT token holding interval microseconds, unknown. Different from scheduled DT and NIS '
  'request timeout.'),
 ('ff_response_bound_us',
  'number',
  'us',
  None,
  0,
  None,
  None,
  'Actual matched CFF/device response bound normalized to microseconds, unknown. Native timer units require '
  'source conversion; no sample-device value copied.'),
 ('ff_cable_type',
  'select',
  None,
  ['TYPE_A', 'TYPE_B', 'TYPE_C', 'TYPE_D', 'DEVICE_SPECIFIC'],
  None,
  None,
  'TYPE_A',
  'Source-recommended Type A shielded twisted-pair baseline proposal. B/C/D are source reference wiring '
  'profiles, not automatically accepted installation designs.'),
 ('ff_trunk_m',
  'number',
  'm',
  None,
  0,
  None,
  None,
  'Actual trunk length, unknown. Total segment includes all spurs; nominal1900m Type A is an upper reference '
  'limit, not a default length.'),
 ('ff_spurs_total_m',
  'number',
  'm',
  None,
  0,
  None,
  None,
  'Actual summed spur lengths, unknown. Per-spur/device-count/reference limits and IS constraints require '
  'actual topology source.'),
 ('ff_segment_total_m',
  'number',
  'm',
  None,
  0,
  None,
  None,
  'Actual trunk plus summed spurs. Qualified reference limits A1900/B1200/C400/D200m; DEVICE_SPECIFIC '
  'requires own verified bounds.'),
 ('ff_terminators',
  'number',
  None,
  None,
  0,
  None,
  2,
  'Baseline two end terminators proposal, not evidence that wiring has two. Different media require their '
  'own realization.'),
 ('ff_termination_ohm',
  'number',
  'ohm',
  None,
  0.001,
  None,
  100,
  'Nominal100ohm end termination proposal. Actual impedance/tolerance and capacitive coupling require '
  'source.'),
 ('ff_terminal_v',
  'number',
  'V',
  None,
  0,
  None,
  None,
  'Actual received device voltage, unknown. Reviewed voltage-mode envelope9..32V does not certify selected '
  'device/IS barrier operating limits.'),
 ('ff_supply_ma',
  'number',
  'mA',
  None,
  0,
  None,
  None,
  'Actual available power-conditioner/barrier current budget, unknown. Not inferred from32-node '
  'illustration.'),
 ('ff_devices_ma',
  'number',
  'mA',
  None,
  0,
  None,
  None,
  'Actual total device current including limits/reserves, unknown; must fit available current. Individual '
  'voltage drops still require evidence.'),
 ('ff_power_source',
  'text',
  None,
  None,
  None,
  None,
  None,
  'Actual voltage-drop/current-budget/power-conditioner/isolator calculation source, unknown.'),
 ('ff_is_required',
  'boolean',
  None,
  None,
  None,
  None,
  None,
  'Actual intrinsic-safety requirement, unknown. It does not claim SIL/safety communication or explosion '
  'protection.'),
 ('ff_is_source',
  'text',
  None,
  None,
  None,
  None,
  None,
  'Actual matched intrinsic-safety barrier/device/cable certificate and entity/FISCO design evidence, '
  'unknown; required when IS selected.')]:
            native=field(key,key.replace('ff_','').replace('_',' '),'timing' if unit=='us' else 'physical','route',
                field_type=kind,unit=unit,options=options,minimum=minimum,maximum=maximum,
                default=default if key in {'ff_profile','ff_layout','ff_las_service_address'} else None,
                description=meaning,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['foundation_fieldbus_h1']['required_parameters'],
                integer=kind=='number' and unit not in {'us','m','V','mA','ohm'},
                parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                default_status='PROPOSED' if default is not None else 'UNKNOWN',
                source=source['source'],source_revision=source['source_revision'])
            if default is not None and key not in {'ff_profile','ff_layout','ff_las_service_address'}:
                when={'ff_layout':'YOKOGAWA_FMS_DIAGRAM','ff_pdu':'DT'} if key in {'ff_fms_pci_bytes','ff_fas_pci_bytes','ff_fcs_bytes'} else {'ff_profile':'H1_VOLTAGE_MODE'}
                native.update(conditional_defaults=[{'when':when,'value':default}],default_status='PROPOSED_CONDITIONAL')
            fields.append(native)
    if technology_id == 'flexray':
        source=REVIEW_RATE_PROPOSALS['flexray']
        removed={'qos_priority','reserved_bandwidth_percent','sync_method','retransmission_enabled','retransmission_rate',
                 'retry_limit','retransmission_delay_ms','gateway_maximum_throughput','gateway_input_buffer',
                 'gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s'}
        fields=[item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.update(integer=True,multiple_of=2,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                            source=source['source'],source_revision=source['source_revision'],simulation_relevant=False,
                            description='Actual frame payload0..254 octets in two-octet words. Static configured global size and dynamic actual frame/maximum size are distinct; prefixes/padding are included.')
            if item['key']=='queue_policy': item['options']=['FIFO','CUSTOM']
            if item['key']=='queue_size': item['integer']=True
        for key,label,kind,unit,options,minimum,maximum,default in (
            ('fr_profile','Actual FlexRay protocol/controller profile','select',None,['PROTOCOL_3_0_1','NXP_MFR4310_2_1','DEVICE_SPECIFIC'],None,None,'PROTOCOL_3_0_1'),
            ('fr_configuration_source','Actual matched controller/protocol/cluster/node configuration','text',None,None,None,None,None),
            ('fr_physical_source','Actual A/B PHY/cabling/termination/star/topology evidence','text',None,None,None,None,None),
            ('fr_schedule_source','Actual slot/owner/cycle/channel schedule evidence','text',None,None,None,None,None),
            ('fr_segment','Actual transmitted frame segment','select',None,['STATIC','DYNAMIC'],None,None,None),
            ('fr_channels','Actual controller connected channels','select',None,['A','B','AB'],None,None,None),
            ('fr_tx_channels','Actual selected TX channels','select',None,['A','B','AB'],None,None,None),
            ('fr_channel_use','Actual dual-channel traffic relationship','select',None,['SINGLE','REDUNDANT','INDEPENDENT'],None,None,None),
            ('fr_frame_id','Actual transmitted slot/frame identifier','number',None,None,1,2047,None),
            ('fr_payload_words','Actual frame payload length field','number','16-bit words',None,0,127,None),
            ('fr_static_payload_words','Actual global static frame payload length','number','16-bit words',None,0,127,None),
            ('fr_dynamic_payload_words_max','Actual local maximum dynamic frame payload','number','16-bit words',None,0,127,None),
            ('fr_frame_bytes','Actual header/payload/trailer octets excluding line coding','number','Byte',None,8,262,None),
            ('fr_cycle_counter','Actual received/transmitted cycle counter','number',None,None,0,63,None),
            ('fr_cycle_count_max','Actual cluster maximum cycle counter','number',None,None,7,63,None),
            ('fr_cycle_offset','Actual cycle multiplexing base offset','number','cycles',None,0,63,None),
            ('fr_repetition','Actual cycle multiplexing repetition','number','cycles',None,1,64,None),
            ('fr_transmission_mode','Actual TX buffer update semantics','select',None,['SINGLE_SHOT','CONTINUOUS'],None,None,None),
            ('fr_preamble','Actual payload preamble indicator','boolean',None,None,None,None,None),
            ('fr_payload_valid','Actual null-frame bit data-valid meaning','boolean',None,None,None,None,None),
            ('fr_sync_frame','Actual synchronization frame indicator','boolean',None,None,None,None,None),
            ('fr_startup_frame','Actual startup frame indicator','boolean',None,None,None,None,None),
            ('fr_coldstart_node','Actual configured coldstart node role','boolean',None,None,None,None,None),
            ('fr_header_crc','Actual encoded11-bit header CRC','number',None,None,0,2047,None),
            ('fr_frame_crc','Actual encoded24-bit channel-specific frame CRC','number',None,None,0,16777215,None),
            ('fr_crc_source','Actual encoded flags/ID/length/payload/channel CRC verification','text',None,None,None,None,None),
            ('fr_nmv_bytes','Actual global network-management-vector length','number','Byte',None,0,12,None),
            ('fr_message_id','Actual dynamic payload preamble message identifier','number',None,None,0,65535,None),
            ('fr_macro_per_cycle','Actual global macroticks per cycle','number','MT',None,8,16000,None),
            ('fr_macrotick_us','Actual global nominal macrotick duration','number','us',None,0.001,None,None),
            ('fr_microtick_ns','Actual node microtick duration','number','ns',None,0.001,None,None),
            ('fr_micro_per_cycle','Actual nominal node microticks per cycle','number','uT',None,960,1280000,None),
            ('fr_samples_per_microtick','Actual controller samples per microtick','number',None,None,1,2,None),
            ('fr_cycle_us','Actual communication cycle duration','number','us',None,0.001,None,None),
            ('fr_cycle_mt','Actual complete cycle segment sum','number','MT',None,8,16000,None),
            ('fr_static_slots','Actual global static slot count','number','slots',None,2,1023,None),
            ('fr_static_slot_mt','Actual global static slot duration','number','MT',None,3,664,None),
            ('fr_action_point_mt','Actual static action-point offset','number','MT',None,1,63,None),
            ('fr_minislots','Actual global dynamic minislot count','number','minislots',None,0,7988,None),
            ('fr_minislot_mt','Actual global minislot duration','number','MT',None,2,63,None),
            ('fr_minislot_action_point_mt','Actual dynamic action-point offset','number','MT',None,1,31,None),
            ('fr_dynamic_idle_minislots','Actual dynamic slot idle phase','number','minislots',None,0,2,None),
            ('fr_symbol_window_mt','Actual global symbol-window duration','number','MT',None,0,162,None),
            ('fr_symbol_action_point_mt','Actual symbol-window action-point offset','number','MT',None,1,63,None),
            ('fr_nit_mt','Actual network idle time','number','MT',None,1,None,None),
            ('fr_tss_bits','Actual transmission start sequence duration','number','bit times',None,1,15,None),
            ('fr_coldstart_attempts','Actual global coldstart attempt count','number',None,None,2,31,None),
            ('fr_listen_noise','Actual startup/wakeup listen noise multiplier','number',None,None,2,16,None),
            ('fr_clock_fatal_pairs','Actual no-correction fatal threshold','number','cycle pairs',None,1,15,None),
            ('fr_clock_passive_pairs','Actual no-correction passive threshold','number','cycle pairs',None,1,15,None),
            ('fr_sync_frame_ids_max','Actual maximum distinct sync identifiers','number',None,None,2,15,None),
            ('fr_allow_halt_clock','Actual halt on synchronization error setting','boolean',None,None,None,None,None),
            ('fr_passive_to_active_pairs','Actual passive-to-active threshold','number','cycle pairs',None,0,31,None),
            ('fr_drift_damping_ut','Actual node cluster-drift damping','number','uT',None,0,10,None),
            ('fr_startup_range_ut','Actual accepted startup timing deviation','number','uT',None,29,2743,None),
            ('fr_listen_timeout_ut','Actual node listen duration','number','uT',None,1926,2567692,None),
            ('fr_key_slot_id','Actual key slot;0 means not configured','number',None,None,0,1023,None),
            ('fr_key_only','Actual key-slot-only startup mode','boolean',None,None,None,None,None),
            ('fr_key_startup','Actual key slot startup role','boolean',None,None,None,None,None),
            ('fr_key_sync','Actual key slot synchronization role','boolean',None,None,None,None,None),
            ('fr_latest_tx','Actual local last allowed dynamic minislot','number','minislot',None,0,7988,None),
            ('fr_macro_offset_a','Actual startup macrotick offset on A','number','MT',None,2,68,None),
            ('fr_macro_offset_b','Actual startup macrotick offset on B','number','MT',None,2,68,None),
            ('fr_micro_offset_a','Actual secondary-reference offset on A','number','uT',None,0,239,None),
            ('fr_micro_offset_b','Actual secondary-reference offset on B','number','uT',None,0,239,None),
            ('fr_offset_correction_ut','Actual maximum permitted offset correction','number','uT',None,15,16082,None),
            ('fr_correction_start_mt','Actual offset-correction start within NIT','number','MT',None,7,15999,None),
            ('fr_rate_correction_ut','Actual maximum permitted rate correction','number','uT',None,3,3846,None),
            ('fr_wakeup_channel','Actual wakeup TX channel','select',None,['A','B'],None,None,None),
            ('fr_wakeup_pattern','Actual wakeup symbol repetition count','number',None,None,0,63,None),
            ('fr_wakeup_active_bits','Actual wakeup LOW phase','number','bit times',None,15,60,None),
            ('fr_wakeup_idle_bits','Actual wakeup idle phase','number','bit times',None,45,180,None),
            ('fr_second_key_id','Actual second key slot;0 means not configured','number',None,None,0,1023,None),
            ('fr_two_key_mode','Actual two-key-slot/single-coldstart mode','boolean',None,None,None,None,None),
            ('fr_clock_source','Actual oscillator/precision/drift/decoder/correction evidence','text',None,None,None,None,None),
            ('fr_poc_state','Actual protocol operation controller state','select',None,['DEFAULT_CONFIG','CONFIG','READY','WAKEUP','STARTUP','NORMAL_ACTIVE','NORMAL_PASSIVE','HALT'],None,None,None),
        ):
            native=field(key,label,'timing' if unit in {'us','ns','MT','uT','bit times','cycles','cycle pairs','minislot','minislots'} else 'physical',
                         'route',field_type=kind,unit=unit,options=options,minimum=minimum,maximum=maximum,default=default,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['flexray']['required_parameters'],
                          integer=kind=='number' and unit not in {'us','ns'},
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN',
                          source='https://vectorgrp.github.io/sil-kit-docs/api/services/flexray.html',
                          source_revision='Vector SIL Kit5.0.7 FlexrayClusterParameters/NodeParameters/Header/TxBufferConfig representation of protocol3.0.1, not complete normative conformance',
                          description='Actual matched FlexRay cluster/node/frame declaration. Controller/edition limits and physical timing/slot fit require their own evidence; no scalar default confirms a valid startup or schedule.')
            if key=='fr_repetition': native['allowed_values']=[1,2,4,8,16,32,64]
            if key=='fr_cycle_count_max': native['allowed_values']=list(range(7,64,2))
            if key=='fr_samples_per_microtick': native['allowed_values']=[1,2]
            if key in {'fr_micro_per_cycle','fr_static_slot_mt','fr_minislots','fr_symbol_window_mt',
                       'fr_tss_bits','fr_drift_damping_ut','fr_startup_range_ut','fr_listen_timeout_ut',
                       'fr_latest_tx','fr_macro_offset_a','fr_macro_offset_b','fr_micro_offset_a','fr_micro_offset_b',
                       'fr_offset_correction_ut','fr_correction_start_mt','fr_rate_correction_ut',
                       'fr_passive_to_active_pairs','fr_second_key_id','fr_two_key_mode'}:
                native.update(schema_when={'fr_profile':'PROTOCOL_3_0_1'},
                              description='These reviewed bounds apply to the Vector5.0.7 representation of FlexRay3.0.1 only. A different protocol/controller profile stays UNVERIFIED until its own bounds are reviewed; no foreign-version fallback.')
            fields.append(native)
    if technology_id == 'ethernet_ip':
        source = REVIEW_RATE_PROPOSALS['ethernet_ip']
        removed = {'bitrate','qos_priority','sync_method','reserved_bandwidth_percent','retransmission_enabled',
                   'retransmission_rate','retry_limit','retransmission_delay_ms','gateway_maximum_throughput',
                   'gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s'}
        fields = [item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.update(max=65535,integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                            source=source['source'],source_revision=source['source_revision'],simulation_relevant=False,
                            description='Actual CPF data-item octets including selected class sequence and optional Run/Idle header. Not application-only bytes, entire CIP logical message, Ethernet MTU or a universal1400-byte limit.')
            if item['key']=='queue_policy': item['options']=['FIFO','PRIORITY','CUSTOM']
            if item['key'] in {'queue_size','gateway_count'}: item['integer']=True
        for key,label,kind,unit,options,minimum,maximum,default in (
            ('eip_mode','Actual EtherNet/IP message mode','select',None,['IMPLICIT_IO','CONNECTED_EXPLICIT','UNCONNECTED_EXPLICIT','DISCOVERY'],None,None,None),
            ('eip_transport','Actual selected message transport','select',None,['TCP','UDP'],None,None,None),
            ('eip_transport_binding','Actual IP/transport/link profile reference','text',None,None,None,None,None),
            ('eip_configuration_source','Actual EDS/device/edition/firmware/connection configuration','text',None,None,None,None,None),
            ('eip_baseline_profile','Source-qualified parameter proposal profile','select',None,['ODVA_INTEROP_V9','DEVICE_SPECIFIC'],None,None,'ODVA_INTEROP_V9'),
            ('eip_class','Actual selected supported CIP transport class','number',None,None,0,3,None),
            ('eip_port','Actual selected transport port','number',None,None,1,65535,None),
            ('eip_command','Actual encapsulation command','number',None,None,0,65535,None),
            ('eip_encap_version','RegisterSession encapsulation version','number',None,None,1,1,1),
            ('eip_encap_options','Supported base encapsulation options','number',None,None,0,0,0),
            ('eip_encap_length','Encapsulation bytes following24-byte header','number','Byte',None,0,65535,None),
            ('eip_encap_status','Actual encapsulation status code','number',None,None,0,4294967295,None),
            ('eip_session','Actual registered session handle','number',None,None,0,4294967295,None),
            ('eip_cpf_layout','Actual common-packet item layout','select',None,['TWO_ITEM','EXTENDED_DEVICE'],None,None,None),
            ('eip_address_bytes','Actual CPF address-item data length','number','Byte',None,0,65535,None),
            ('eip_class_sequence_bytes','Actual class-specific sequence prefix length','number','Byte',None,0,2,None),
            ('eip_application_bytes','Actual application bytes excluding class and Run/Idle prefixes','number','Byte',None,0,65535,None),
            ('eip_run_idle_present','Actual selected32-bit Run/Idle header presence','boolean',None,None,None,None,None),
            ('eip_run_idle_bytes','Actual selected Run/Idle prefix length','number','Byte',None,0,4,None),
            ('eip_cpf_bytes','Actual complete Common Packet Format size','number','Byte',None,2,None,None),
            ('eip_packet_bytes','Actual EtherNet/IP transport-payload size','number','Byte',None,0,None,None),
            ('eip_io_sequence','Actual implicit sequenced-address counter','number',None,None,0,4294967295,None),
            ('eip_class_sequence','Actual class1/3 sequence counter','number',None,None,0,65535,None),
            ('eip_delivery','Actual implicit delivery','select',None,['UNICAST','MULTICAST'],None,None,None),
            ('eip_ip_address','Actual selected peer/group IP address','text',None,None,None,None,None),
            ('eip_forward_open','Actual ForwardOpen encoding','select',None,['STANDARD','LARGE'],None,None,None),
            ('eip_o_to_t_size','Actual accepted Originator-to-Target connection size','number','Byte',None,0,65535,None),
            ('eip_t_to_o_size','Actual accepted Target-to-Originator connection size','number','Byte',None,0,65535,None),
            ('eip_size_direction','Actual packet direction','select',None,['O_TO_T','T_TO_O'],None,None,None),
            ('eip_size_mode','Actual selected direction fixed/variable size','select',None,['FIXED','VARIABLE'],None,None,None),
            ('eip_size_definition','Actual negotiated-size measurement boundary','select',None,['OPENER_CPF_DATA','DEVICE_SPECIFIC'],None,None,None),
            ('eip_o_to_t_rpi_us','Requested Originator-to-Target packet interval','number','us',None,1,4294967295,None),
            ('eip_t_to_o_rpi_us','Requested Target-to-Originator packet interval','number','us',None,1,4294967295,None),
            ('eip_o_to_t_api_us','Accepted Originator-to-Target packet interval','number','us',None,1,4294967295,None),
            ('eip_t_to_o_api_us','Accepted Target-to-Originator packet interval','number','us',None,1,4294967295,None),
            ('eip_timeout_code','Actual base connection-timeout multiplier encoding','number',None,None,0,7,None),
            ('eip_watchdog_profile','Actual consuming watchdog calculation profile','select',None,['ACCEPTED_API','OPENER_MILLISECOND','DEVICE_SPECIFIC'],None,None,None),
            ('eip_watchdog_us','Actual regular consuming watchdog duration','number','us',None,0,None,None),
            ('eip_initial_watchdog_us','Actual first-consumption watchdog duration','number','us',None,0,None,None),
            ('eip_timer_source','Actual negotiated intervals/timer resolution/watchdog evidence','text',None,None,None,None,None),
            ('eip_trigger','Actual production trigger','select',None,['CYCLIC','CHANGE_OF_STATE','APPLICATION'],None,None,None),
            ('eip_inhibit_profile','Actual production-inhibit validation profile','select',None,['OPENER_CYCLIC','DEVICE_SPECIFIC'],None,None,None),
            ('eip_inhibit_ms','Actual production-inhibit interval','number','ms',None,0,65535,None),
            ('eip_o_to_t_priority','Actual Originator-to-Target CIP priority','select',None,['LOW','HIGH','SCHEDULED','URGENT'],None,None,None),
            ('eip_t_to_o_priority','Actual Target-to-Originator CIP priority','select',None,['LOW','HIGH','SCHEDULED','URGENT'],None,None,None),
            ('eip_o_to_t_type','Actual Originator-to-Target connection type','select',None,['NULL','MULTICAST','POINT_TO_POINT'],None,None,None),
            ('eip_t_to_o_type','Actual Target-to-Originator connection type','select',None,['NULL','MULTICAST','POINT_TO_POINT'],None,None,None),
            ('eip_owner_mode','Actual application connection ownership','select',None,['EXCLUSIVE_OWNER','INPUT_ONLY','LISTEN_ONLY','REDUNDANT_OWNER'],None,None,None),
            ('eip_owner_source','Actual connection path/owner/listen dependency evidence','text',None,None,None,None,None),
            ('eip_connection_path','Actual encoded CIP connection/object/assembly path reference','text',None,None,None,None,None),
            ('eip_o_to_t_id','Actual Originator-to-Target connection identifier','number',None,None,0,4294967295,None),
            ('eip_t_to_o_id','Actual Target-to-Originator connection identifier','number',None,None,0,4294967295,None),
            ('eip_established','Actual accepted and active CIP connection','boolean',None,None,None,None,None),
            ('eip_peer_source','Actual accepted sizes/connection IDs/IP/sockets/state evidence','text',None,None,None,None,None),
        ):
            native=field(key,label,'timing' if unit in {'us','ms'} else 'physical','route',field_type=kind,
                         unit=unit,options=options,minimum=minimum,maximum=maximum,default=default,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['ethernet_ip']['required_parameters'],integer=kind=='number',
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN',source=source['source'],source_revision=source['source_revision'],
                          description='Base EtherNet/IP declaration; exact edition/EDS/implementation and selected TCP/UDP/IP/link path remain required. Scalar validity is not connection execution or capacity evidence.')
            if key=='eip_class': native['allowed_values']=[0,1,3]
            if key in {'eip_class_sequence_bytes','eip_run_idle_bytes'}:
                native['allowed_values']=[0,2] if key=='eip_class_sequence_bytes' else [0,4]
            if key=='eip_port':
                native.update(conditional_defaults=[{'when':{'eip_mode':mode},'value':port}
                    for mode,port in (('IMPLICIT_IO',2222),('CONNECTED_EXPLICIT',44818),('UNCONNECTED_EXPLICIT',44818),('DISCOVERY',44818))],
                    default_status='PROPOSED_CONDITIONAL',parameter_origin='TRANSPORT_PROFILE',
                    description='Explicit/discovery standard port44818; implicit UDP2222 recommended unicast and required multicast. Actual unicast socket may be negotiated.')
            if key in {'eip_o_to_t_rpi_us','eip_t_to_o_rpi_us','eip_timeout_code','eip_o_to_t_priority','eip_t_to_o_priority'}:
                native.update(conditional_defaults=[{'when':{'eip_baseline_profile':'ODVA_INTEROP_V9','eip_class':klass},'value':value}
                    for klass,value in ((1,100000),(3,250000))] if key.endswith('_rpi_us') else
                    [{'when':{'eip_baseline_profile':'ODVA_INTEROP_V9','eip_class':klass},'value':0 if key=='eip_timeout_code' else priority}
                     for klass,priority in ((1,'SCHEDULED'),(3,'LOW'))],
                    default_status='PROPOSED_CONDITIONAL',parameter_origin='TRANSPORT_PROFILE',
                    source='https://www.odva.org/wp-content/uploads/2020/05/PUB00095_PF-Test-Procedure-v9.pdf',
                    source_revision='PUB00095 Version9 PR002 sectionsP9/P12; proposals scoped to ODVA interoperability profile, actual EDS and negotiated API required')
            if key=='eip_ip_address': native['format']='IP_ADDRESS'
            fields.append(native)
    if technology_id == 'doip':
        source = REVIEW_RATE_PROPOSALS['doip']
        removed = {'bitrate','qos_priority','sync_method','reserved_bandwidth_percent','retransmission_enabled',
                   'retransmission_rate','retry_limit','retransmission_delay_ms','gateway_maximum_throughput',
                   'gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s'}
        fields = [item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.update(max=4294967295, integer=True, default_status='UNKNOWN', parameter_origin='DEVICE_CONFIGURATION',
                            source=source['source'], source_revision=source['source_revision'], simulation_relevant=False,
                            description='Actual DoIP payload excluding generic8-byte header, uint32 length. Diagnostic payload includes4 address bytes and at least1 user-data byte; ACK/control/discovery layouts have distinct lengths.')
            if item['key']=='queue_policy':
                item['options']=['FIFO','PRIORITY','CUSTOM']
            if item['key'] in {'queue_size','gateway_count'}:
                item['integer']=True
        for key,label,kind,unit,options,minimum,maximum,default in (
            ('doip_edition','Actual DoIP protocol edition','select',None,['ISO_2012','ISO_2019','DEVICE_SPECIFIC'],None,None,None),
            ('doip_transport','Actual message transport','select',None,['UDP','TCP','TLS'],None,None,None),
            ('doip_transport_binding','Actual IP/transport/network path profile','text',None,None,None,None,None),
            ('doip_configuration_source','Actual edition/entity/OEM/implementation configuration','text',None,None,None,None,None),
            ('doip_protocol_version','Actual generic-header version','number',None,None,0,255,None),
            ('doip_inverse_version','Actual inverted version byte','number',None,None,0,255,None),
            ('doip_payload_type','Actual encoded payload type','number',None,None,0,65535,None),
            ('doip_message_bytes','Actual complete DoIP message','number','Byte',None,8,4294967303,None),
            ('doip_port','Actual selected transport port','number',None,None,1,65535,None),
            ('doip_optional_field_present','Actual layout optional-field presence','boolean',None,None,None,None,None),
            ('doip_user_data_bytes','Actual diagnostic data excluding addresses','number','Byte',None,1,4294967291,None),
            ('doip_ack_copy_bytes','Actual previous-message data copied in ACK/NACK','number','Byte',None,0,4294967290,None),
            ('doip_ack_code','Actual diagnostic ACK/NACK code','number',None,None,0,255,None),
            ('doip_source_role','Actual logical source role','select',None,['CLIENT','ENTITY','DEVICE_SPECIFIC'],None,None,None),
            ('doip_source_address','Actual logical source address','number',None,None,1,65535,None),
            ('doip_target_address','Actual configured logical target address','number',None,None,1,65535,None),
            ('doip_address_mapping_source','Actual supported source/target/functional route mapping','text',None,None,None,None,None),
            ('doip_activation_type','Selected routing activation type','number',None,None,0,255,0),
            ('doip_reserved','Reserved routing-activation field','number',None,None,0,0,0),
            ('doip_oem_data','Actual optional OEM routing-activation uint32','number',None,None,0,4294967295,None),
            ('doip_routing_active','Actual completed routing activation','boolean',None,None,None,None,None),
            ('doip_routing_source','Actual activation/authentication/confirmation/socket evidence','text',None,None,None,None,None),
            ('doip_max_sockets','Actual maximum concurrent TCP_DATA sockets','number',None,None,1,255,None),
            ('doip_open_sockets','Actual currently open TCP_DATA sockets','number',None,None,0,255,None),
            ('doip_peer_size_definition','Actual meaning of peer maximum size','select',None,['DOIP_PAYLOAD','DIAGNOSTIC_USER_DATA','COMPLETE_DOIP_MESSAGE','DEVICE_SPECIFIC'],None,None,None),
            ('doip_peer_size_limit_bytes','Actual advertised/configured peer size limit','number','Byte',None,0,4294967303,None),
            ('doip_peer_size_source','Actual peer-buffer/max-size interpretation evidence','text',None,None,None,None,None),
            ('doip_node_type','Actual entity node type','select',None,['GATEWAY','NODE'],None,None,None),
            ('doip_initial_inactivity_ms','Initial TCP inactivity timeout','number','ms',None,0.001,None,2000),
            ('doip_general_inactivity_ms','General TCP inactivity timeout','number','ms',None,0.001,None,300000),
            ('doip_alive_check_ms','Alive-check response timeout','number','ms',None,0,None,500),
            ('doip_control_timeout_ms','DoIP control response timeout','number','ms',None,0.001,None,2000),
            ('doip_diagnostic_ack_ms','DoIP diagnostic message ACK wait','number','ms',None,0.001,None,2000),
            ('doip_announce_wait_max_ms','Maximum randomized initial announcement delay','number','ms',None,0,None,500),
            ('doip_announce_interval_ms','Announcement interval','number','ms',None,0,None,500),
            ('doip_announce_count','Announcement repetitions','number',None,None,1,255,3),
            ('doip_vin_hex','Actual17-byte VIN field as hex octets','text',None,None,None,None,None),
            ('doip_eid_hex','Actual6-byte EID field as hex octets','text',None,None,None,None,None),
            ('doip_gid_hex','Actual6-byte GID field as hex octets','text',None,None,None,None,None),
            ('doip_ip_address','Actual destination IP address','text',None,None,None,None,None),
            ('doip_tls_source','Actual TLS version/trust/peer/certificate configuration','text',None,None,None,None,None),
            ('doip_upper_timing_source','Actual UDS/application P2/P2star/session timing contract','text',None,None,None,None,None),
        ):
            native=field(key,label,'timing' if unit=='ms' else 'physical','route',field_type=kind,unit=unit,
                         options=options,minimum=minimum,maximum=maximum,default=default,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['doip']['required_parameters'], integer=kind=='number' and unit!='ms',
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN',source=source['source'],source_revision=source['source_revision'],
                          description='Matched DoIP edition/message/connection declaration. IP bandwidth, routing state, actual buffers and upper diagnostic timing remain separate from scalar validity.')
            if default is not None and (unit=='ms' or key=='doip_announce_count'):
                native.update(source='https://raw.githubusercontent.com/jacobschaer/python-doipclient/main/doipclient/constants.py',
                              source_revision='python-doipclient primary constants representingISO13400-2:2019 accessed2026-10-01; proposals not observed device parameters')
                native.pop('default',None)
                transports = ('UDP',) if key.startswith('doip_announce_') else ('UDP','TCP','TLS') if key=='doip_control_timeout_ms' else ('TCP','TLS')
                native.update(conditional_defaults=[{'when':{'doip_edition':'ISO_2019','doip_transport':t},'value':default} for t in transports],
                              default_status='PROPOSED_CONDITIONAL')
            if key in {'doip_activation_type','doip_reserved'}:
                native.pop('default',None)
                native.update(conditional_defaults=[{'when':{'doip_payload_type':t},'value':0} for t in ((5,) if key=='doip_activation_type' else (5,6))],
                              default_status='PROPOSED_CONDITIONAL')
            if key=='doip_port':
                native.update(conditional_defaults=[{'when':{'doip_transport':t},'value':p} for t,p in (('UDP',13400),('TCP',13400),('TLS',3496))],
                              default_status='PROPOSED_CONDITIONAL',parameter_origin='TRANSPORT_PROFILE',
                              source='https://raw.githubusercontent.com/jacobschaer/python-doipclient/main/doipclient/constants.py',source_revision='ISO13400-2:2019 represented constants tables39/41; separate securedTCP3496')
            if key in {'doip_protocol_version','doip_inverse_version'}:
                native.update(conditional_defaults=[{'when':{'doip_edition':edition},'value':version if key=='doip_protocol_version' else 255-version}
                                                    for edition,version in (('ISO_2012',2),('ISO_2019',3))],
                              default_status='PROPOSED_CONDITIONAL',parameter_origin='TRANSPORT_PROFILE')
            if key in {'doip_vin_hex','doip_eid_hex','doip_gid_hex'}:
                native['pattern']=r'[0-9A-Fa-f]{34}' if key=='doip_vin_hex' else r'[0-9A-Fa-f]{12}'
            if key=='doip_ip_address':
                native['format']='IP_ADDRESS'
            fields.append(native)
    if technology_id == 'dnp3':
        source = REVIEW_RATE_PROPOSALS['dnp3']
        removed = {'qos_priority', 'sync_method', 'reserved_bandwidth_percent', 'retransmission_enabled',
                   'retransmission_rate', 'retry_limit', 'retransmission_delay_ms', 'gateway_maximum_throughput',
                   'gateway_input_buffer', 'gateway_output_buffer', 'gateway_maximum_routes', 'gateway_maximum_messages_s'}
        fields = [item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key'] == 'payload_bytes':
                item.pop('default', None)
                item.pop('max', None)
                item.update(default_status='UNKNOWN', parameter_origin='DEVICE_CONFIGURATION', integer=True,
                            source=source['source'], source_revision=source['source_revision'], simulation_relevant=False,
                            description='Actual complete encoded DNP3 application message octets including application headers; may span multiple peer-limited fragments and transport segments. Not universal2048B limit.')
            if item['key'] == 'queue_policy':
                item['options'] = ['FIFO','PRIORITY','CUSTOM']
            if item['key'] in {'queue_size','gateway_count'}:
                item['integer'] = True
        implementation_source = 'https://docs.stepfunc.io/dnp3/1.6.0/rust/src/dnp3/outstation/config.rs.html'
        for key, label, kind, unit, options, minimum, maximum, default in (
            ('dnp_role', 'Actual DNP3 endpoint role', 'select', None, ['MASTER','OUTSTATION'], None, None, None),
            ('dnp_transport', 'Actual DNP3 lower transport', 'select', None, ['SERIAL','TCP','UDP','TLS','SCTP','DEVICE_SPECIFIC'], None, None, None),
            ('dnp_transport_binding', 'Actual matched lower transport profile', 'text', None, None, None, None, None),
            ('dnp_configuration_source', 'Actual IEEE1815 edition/device profile/configuration source', 'text', None, None, None, None, None),
            ('dnp_implementation', 'Actual matching DNP3 implementation', 'select', None, ['STEPFUNC_1_6','DEVICE_SPECIFIC'], None, None, None),
            ('dnp_master_address', 'Actual master link address', 'number', None, None, 0, 65519, None),
            ('dnp_outstation_address', 'Actual outstation link address', 'number', None, None, 0, 65519, None),
            ('dnp_destination_mode', 'Actual link destination addressing', 'select', None, ['UNICAST','SELF','BROADCAST_NO_CONFIRM','BROADCAST_CONFIRM','BROADCAST_OPTIONAL_CONFIRM'], None, None, None),
            ('dnp_destination_address', 'Actual link destination address', 'number', None, None, 0, 65535, None),
            ('dnp_port', 'Actual selected IP service port', 'number', None, None, 1, 65535, None),
            ('dnp_link_user_bytes', 'Actual link data without block CRC', 'number', 'Byte', None, 0, 250, None),
            ('dnp_link_length_field', 'Actual link length-field value excluding CRC', 'number', 'Byte', None, 5, 255, None),
            ('dnp_link_frame_bytes', 'Actual complete DNP3 link frame', 'number', 'Byte', None, 10, 292, None),
            ('dnp_transport_data_bytes', 'Actual application octets in transport segment', 'number', 'Byte', None, 0, 249, None),
            ('dnp_fragment_limit_bytes', 'Proposed application fragment limit', 'number', 'Byte', None, 1, None, 2048),
            ('dnp_peer_rx_buffer_bytes', 'Actual receiving peer reassembly buffer', 'number', 'Byte', None, 1, None, None),
            ('dnp_application_fragment_bytes', 'Actual selected encoded application fragment', 'number', 'Byte', None, 2, None, None),
            ('dnp_application_kind', 'Actual application request/response', 'select', None, ['REQUEST','RESPONSE','UNSOLICITED_RESPONSE'], None, None, None),
            ('dnp_link_confirm', 'Actual link-layer confirmation enabled', 'boolean', None, None, None, None, None),
            ('dnp_link_confirm_timeout_ms', 'Actual link confirmation timeout', 'number', 'ms', None, 0.001, None, None),
            ('dnp_link_retries', 'Actual link confirmation retry count', 'number', None, None, 0, None, None),
            ('dnp_response_timeout_ms', 'Actual master association response timeout', 'number', 'ms', None, 0.001, None, None),
            ('dnp_app_confirm_timeout_ms', 'Actual outstation application-confirmation timeout', 'number', 'ms', None, 0.001, None, None),
            ('dnp_select_timeout_ms', 'Actual outstation select-before-operate timeout', 'number', 'ms', None, 0.001, None, None),
            ('dnp_unsolicited_enabled', 'Actual outstation unsolicited reporting enabled', 'boolean', None, None, None, None, None),
            ('dnp_unsolicited_retry_mode', 'Actual unsolicited retry limit mode', 'select', None, ['FINITE','UNLIMITED'], None, None, None),
            ('dnp_max_unsolicited_retries', 'Actual finite non-regenerated unsolicited retries', 'number', None, None, 0, None, None),
            ('dnp_unsolicited_retry_delay_ms', 'Actual delay between unsolicited retry series', 'number', 'ms', None, 0, None, None),
            ('dnp_keepalive_enabled', 'Actual REQUEST_LINK_STATUS keepalive enabled', 'boolean', None, None, None, None, None),
            ('dnp_keepalive_ms', 'Actual link inactivity before status request', 'number', 'ms', None, 0.001, None, None),
            ('dnp_auto_retry_min_ms', 'Actual master automatic-task minimum backoff', 'number', 'ms', None, 0, None, None),
            ('dnp_auto_retry_max_ms', 'Actual master automatic-task maximum backoff', 'number', 'ms', None, 0, None, None),
            ('dnp_data_class', 'Actual static/event object class', 'select', None, ['CLASS0','CLASS1','CLASS2','CLASS3'], None, None, None),
            ('dnp_group', 'Actual encoded object group', 'number', None, None, 0, 255, None),
            ('dnp_variation', 'Actual encoded object variation', 'number', None, None, 0, 255, None),
            ('dnp_object_mapping_source', 'Actual supported object/variation/index/qualifier mapping', 'text', None, None, None, None, None),
            ('dnp_point_index_start', 'Actual first requested point index', 'number', None, None, 0, 65535, None),
            ('dnp_point_index_end', 'Actual last requested point index', 'number', None, None, 0, 65535, None),
            ('dnp_event_buffer_source', 'Actual per-object-type event capacities/overflow policy', 'text', None, None, None, None, None),
            ('dnp_medium_access_source', 'Actual shared-medium unsolicited access policy', 'text', None, None, None, None, None),
            ('dnp_time_sync', 'Actual DNP3 time synchronization procedure', 'select', None, ['DISABLED','LAN','NON_LAN','DEVICE_SPECIFIC'], None, None, None),
            ('dnp_time_sync_source', 'Actual clock timestamp/source/delay/acceptance evidence', 'text', None, None, None, None, None),
            ('dnp_control_mode', 'Actual control transaction', 'select', None, ['SELECT_BEFORE_OPERATE','DIRECT_OPERATE','DIRECT_OPERATE_NO_ACK'], None, None, None),
            ('dnp_security_mode', 'Actual transport/authentication security configuration', 'select', None, ['NONE','TLS_ONLY','SA_ONLY','TLS_AND_SA','DEVICE_SPECIFIC'], None, None, None),
            ('dnp_security_source', 'Actual TLS/SA edition/keys/peer verification source', 'text', None, None, None, None, None),
        ):
            native = field(key,label,'timing' if unit=='ms' else 'physical','route',field_type=kind,unit=unit,
                           options=options,minimum=minimum,maximum=maximum,default=default,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['dnp3']['required_parameters'], integer=kind=='number' and unit!='ms',
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN', source=source['source'],
                          source_revision=source['source_revision'],
                          description='Separate DNP3 link/transport/application/peer configuration. Native scalar declarations do not prove supported group/variation, installed peer buffers, timestamps, security, medium access or capacity.')
            conditional = {
                'dnp_port': [{'when': {'dnp_transport': t}, 'value': 20000} for t in ('TCP','UDP','SCTP')],
                'dnp_app_confirm_timeout_ms': [{'when': {'dnp_implementation': 'STEPFUNC_1_6', 'dnp_role': 'OUTSTATION'}, 'value': 5000}],
                'dnp_select_timeout_ms': [{'when': {'dnp_implementation': 'STEPFUNC_1_6', 'dnp_role': 'OUTSTATION'}, 'value': 5000}],
                'dnp_unsolicited_retry_delay_ms': [{'when': {'dnp_implementation': 'STEPFUNC_1_6', 'dnp_role': 'OUTSTATION'}, 'value': 5000}],
                'dnp_unsolicited_enabled': [{'when': {'dnp_implementation': 'STEPFUNC_1_6', 'dnp_role': 'OUTSTATION'}, 'value': True}],
                'dnp_unsolicited_retry_mode': [{'when': {'dnp_implementation': 'STEPFUNC_1_6', 'dnp_role': 'OUTSTATION'}, 'value': 'UNLIMITED'}],
                'dnp_keepalive_enabled': [{'when': {'dnp_implementation': 'STEPFUNC_1_6', 'dnp_role': role}, 'value': role=='OUTSTATION'} for role in ('MASTER','OUTSTATION')],
                'dnp_keepalive_ms': [{'when': {'dnp_implementation': 'STEPFUNC_1_6', 'dnp_role': 'OUTSTATION', 'dnp_keepalive_enabled': True}, 'value': 60000}],
                'dnp_time_sync': [{'when': {'dnp_implementation': 'STEPFUNC_1_6','dnp_role': 'MASTER'}, 'value': 'DISABLED'}],
            }.get(key)
            if conditional:
                native.update(conditional_defaults=conditional, default_status='PROPOSED_CONDITIONAL', parameter_origin='TRANSPORT_PROFILE',
                              source='https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.txt' if key=='dnp_port' else implementation_source,
                              source_revision='IANA dnp TCP/UDP/SCTP20000 accessed2026-10-01' if key=='dnp_port' else 'StepFunctionDNP3 1.6.0 config/association/Features defaults, June24 2024; vendor-specific')
            if key in {'dnp_master_address','dnp_outstation_address','dnp_destination_address','dnp_destination_mode'}:
                native.update(source='https://raw.githubusercontent.com/stepfunc/dnp3/1.6.0/dnp3/src/link/header.rs',
                              source_revision='StepFunctionDNP3 1.6.0 link header constants and AnyAddress; individual0..65519 reserved65520..65531 self65532 broadcast65533..65535')
            fields.append(native)
    if technology_id == 'devicenet':
        source = REVIEW_RATE_PROPOSALS['devicenet']
        can_profile = _spec(*next(row for row in ROWS if row[0] == 'can'))
        fields = _parameter_form_schema('can', can_profile, can_profile, _parameter_defaults_review('can', can_profile))
        for item in fields:
            if item['key'] == 'bitrate':
                item.update(min=125000, max=500000, allowed_bps=[125000,250000,500000], default=125000,
                            default_status='PROPOSED', source=source['source'], source_revision=source['source_revision'],
                            default_review=review, description=source['note'])
            if item['key'] == 'can_frame_format':
                item.update(options=['BASE_11'], default='BASE_11', default_status='PROPOSED',
                            source='https://jp.odva.org/wp-content/uploads/2020/05/PUB00026R4-Tech-Adv-Series-DeviceNet.pdf',
                            source_revision='PUB00026R4 March2016 pages3/4 11-bit identifier')
            if item['key'] == 'can_frame_type':
                item['options'] = ['DATA']
            if item['key'] == 'can_identifier':
                item['max'] = 2047
            if item['key'] == 'can_termination_ohms':
                item.update(default=121, min=119.79, max=122.21, source='https://www.odva.org/wp-content/uploads/2023/05/PUB00027R1_Cable_Guide.pdf',
                            source_revision='ODVA PUB00027R1 2003 page1-7; 121ohms1percent each trunk end',
                            description='Nominal121ohms proposal per trunk end, 1percent tolerance. Actual installed two terminators/source required; not generic120ohms exact or drop-line terminators.')
            if item['key'] == 'can_bus_length_m':
                item['description'] = 'Actual maximum path between nodes/terminators including longer end drops as needed, metres. Selected DeviceNet cable and125/250/500kbit/s bounds apply; not universally500m.'
            if item['key'] == 'can_stub_length_m':
                item.update(max=6, description='Actual longest branching drop to trunk, metres, max6; cumulative drops also rate-limited.')
        for key, label, kind, unit, options, minimum, maximum, default in (
            ('dn_specification_source', 'Actual DeviceNet adaptation revision', 'text', None, None, None, None, None),
            ('dn_eds_source', 'Actual matching device EDS/capability source', 'text', None, None, None, None, None),
            ('dn_mac_id', 'Actual node MAC ID', 'number', None, None, 0, 63, None),
            ('dn_node_count', 'Actual bus nodes', 'number', None, None, 1, 64, None),
            ('dn_identifier_layout', 'Selected DeviceNet identifier layout', 'select', None, ['CLASSIC_GROUPS_1_4', 'DEVICE_SPECIFIC'], None, None, 'CLASSIC_GROUPS_1_4'),
            ('dn_message_group', 'Actual DeviceNet message group', 'select', None, ['GROUP1', 'GROUP2', 'GROUP3', 'GROUP4'], None, None, None),
            ('dn_identifier_mac_id', 'Actual MAC encoded in CAN identifier', 'number', None, None, 0, 63, None),
            ('dn_message_id', 'Actual group message ID', 'number', None, None, 0, 47, None),
            ('dn_cable_type', 'Actual DeviceNet cable type', 'select', None, ['THICK', 'MID', 'THIN', 'FLAT', 'MIXED'], None, None, None),
            ('dn_topology', 'DeviceNet physical topology', 'select', None, ['TRUNK_DROP'], None, None, 'TRUNK_DROP'),
            ('dn_cumulative_drop_m', 'Actual sum of all drop lines', 'number', 'm', None, 0, 156, None),
            ('dn_supply_voltage_v', 'Actual regulated supply voltage', 'number', 'V', None, 0, None, None),
            ('dn_worst_node_voltage_v', 'Actual lowest node voltage under load', 'number', 'V', None, 0, None, None),
            ('dn_device_minimum_voltage_v', 'Actual device minimum operating voltage', 'number', 'V', None, 0, None, None),
            ('dn_power_evidence', 'Actual cable/current/voltage-drop/supply budget source', 'text', None, None, None, None, None),
            ('dn_connection_type', 'Actual CIP connection type', 'select', None, ['EXPLICIT', 'POLLED', 'BIT_STROBE', 'CYCLIC', 'CHANGE_OF_STATE'], None, None, None),
            ('dn_connection_state', 'Actual CIP connection state', 'select', None, ['UNCONNECTED', 'ESTABLISHED', 'FAULTED'], None, None, None),
            ('dn_duplicate_mac_passed', 'Actual duplicate-MAC test passed', 'boolean', None, None, None, None, None),
            ('dn_connection_source', 'Actual connection/scan-list/object mapping source', 'text', None, None, None, None, None),
            ('dn_expected_packet_rate_ms', 'Actual expected packet rate', 'number', 'ms', None, 0, None, None),
            ('dn_inhibit_ms', 'Actual COS production inhibit', 'number', 'ms', None, 0, None, None),
            ('dn_heartbeat_ms', 'Actual COS heartbeat period', 'number', 'ms', None, 0, None, None),
            ('dn_interscan_ms', 'Actual scanner interscan delay', 'number', 'ms', None, 0, None, None),
            ('dn_protocol_header_bytes', 'Actual encoded DeviceNet header in selected frame', 'number', 'Byte', None, 0, 8, None),
            ('dn_cip_data_bytes', 'Actual application data in selected frame', 'number', 'Byte', None, 0, 8, None),
            ('dn_complete_message_bytes', 'Actual complete reassembled CIP message', 'number', 'Byte', None, 0, None, None),
            ('dn_peer_message_limit_bytes', 'Actual peer complete-message limit', 'number', 'Byte', None, 0, None, None),
            ('dn_fragmented', 'Actual DeviceNet message fragmented', 'boolean', None, None, None, None, None),
            ('dn_fragmentation_source', 'Actual fragmentation/header/ACK/state specification', 'text', None, None, None, None, None),
        ):
            native = field(key, label, 'physical' if key.startswith(('dn_cable','dn_supply','dn_worst','dn_device','dn_power','dn_topology','dn_cumulative')) else 'qos',
                           'network' if key in {'dn_node_count','dn_cable_type','dn_topology','dn_cumulative_drop_m','dn_power_evidence'} else 'route',
                           field_type=kind, unit=unit, options=options, minimum=minimum, maximum=maximum, default=default, simulation_relevant=False)
            native.update(required=False, integer=kind == 'number' and unit not in {'ms','m','V'},
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN',
                          source='https://jp.odva.org/wp-content/uploads/2020/05/PUB00026R4-Tech-Adv-Series-DeviceNet.pdf',
                          source_revision='ODVA PUB00026R4 March2016 pages3-5; cable guidePUB00027R1 2003; actual edition/device EDS required',
                          description='Actual DeviceNet/CIP adaptation and matching node/cable/connection evidence. No CANopen object dictionary, Ethernet rate or scanner-specific timer default is inferred.')
            if key in {'dn_cable_type','dn_cumulative_drop_m','dn_supply_voltage_v','dn_worst_node_voltage_v','dn_device_minimum_voltage_v','dn_power_evidence'}:
                native.update(source='https://www.odva.org/wp-content/uploads/2023/05/PUB00027R1_Cable_Guide.pdf', source_revision='PUB00027R1 2003 sections1/4/AppendixB')
            if key in {'dn_expected_packet_rate_ms','dn_inhibit_ms','dn_heartbeat_ms','dn_interscan_ms','dn_connection_source'}:
                native.update(source=source['source'], source_revision='DNET-UM004E-EN-P March2022 chapters6/11; differing scanner families prevent universal auto-scan/default timers')
            fields.append(native)
    if technology_id == 'dds':
        source = REVIEW_RATE_PROPOSALS['dds']
        removed = {'bitrate', 'mtu_bytes', 'duplex', 'vlan_id', 'rate_limit_bit_s', 'qos_priority', 'sync_method',
                   'reserved_bandwidth_percent', 'retransmission_enabled', 'retransmission_rate', 'retry_limit',
                   'retransmission_delay_ms', 'gateway_maximum_throughput', 'gateway_input_buffer',
                   'gateway_output_buffer', 'gateway_maximum_routes', 'gateway_maximum_messages_s'}
        fields = [item for item in fields if item['key'] not in removed]
        common = ['TOPIC', 'DATAWRITER', 'DATAREADER']
        entities = [*common, 'PUBLISHER', 'SUBSCRIBER', 'PARTICIPANT', 'PARTICIPANT_FACTORY']
        def dds_metadata(item, allowed_entities, default=None):
            assert tuple(allowed_entities) == DDS_POLICY_ENTITIES[item['key']]
            item.pop('default', None)
            item.update(required=False, source=source['source'], source_revision=source['source_revision'],
                        parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                        default_status='PROPOSED_CONDITIONAL' if default is not None else 'UNKNOWN',
                        simulation_relevant=False,
                        description='OMG DDS1.4 entity-specific QoS declaration. Standard proposals apply only to the stated entity; actual middleware, wire protocol, peer compatibility and capacity remain unverified.')
            if default is not None:
                item['conditional_defaults'] = [{'when': {'dds_entity': entity}, 'value': default} for entity in allowed_entities]

        for item in fields:
            key = item['key']
            if key == 'payload_bytes':
                item.pop('default', None)
                item.pop('max', None)
                item.update(min=0, integer=True, source=source['source'], source_revision=source['source_revision'],
                            parameter_origin='DEVICE_CONFIGURATION', default_status='UNKNOWN',
                            description='Actual serialized topic sample body octets, separate from selected XTypes/CDR/RTPS/transport framing and fragmentation. No universal65507/1500-byte body limit.')
            if key == 'queue_policy':
                item['options'] = ['FIFO', 'PRIORITY', 'CUSTOM']
            if key in {'queue_size', 'seed', 'max_events'}:
                item['integer'] = True
            if key in {'history_depth', 'history_kind', 'durability', 'liveliness', 'reliability_mode', 'lifespan_ms'}:
                default = {'history_depth': 1, 'history_kind': 'KEEP_LAST', 'durability': 'VOLATILE', 'liveliness': 'AUTOMATIC'}.get(key)
                dds_metadata(item, ['TOPIC', 'DATAWRITER'] if key == 'lifespan_ms' else common, default)
                if key == 'history_depth':
                    item.update(integer=True, min=1, max=2147483647)
                    for proposal in item['conditional_defaults']:
                        proposal['when']['history_kind'] = 'KEEP_LAST'
                if key == 'reliability_mode':
                    item['conditional_defaults'] = [{'when': {'dds_entity': entity}, 'value': 'RELIABLE' if entity == 'DATAWRITER' else 'BEST_EFFORT'} for entity in common]
                    item['default_status'] = 'PROPOSED_CONDITIONAL'
        for key, label, kind, unit, options, minimum, maximum, default, allowed_entities in (
            ('dds_entity', 'Actual DDS entity', 'select', None, entities, None, None, None, entities),
            ('dds_transport_binding', 'Actual DDS transport/wire profile reference', 'text', None, None, None, None, None, entities),
            ('dds_implementation_source', 'Actual DDS implementation/revision/QoS source', 'text', None, None, None, None, None, entities),
            ('dds_type_source', 'Actual topic type/encoding/key definition', 'text', None, None, None, None, None, common),
            ('dds_topic_name', 'Actual topic name', 'text', None, None, None, None, None, common),
            ('dds_domain_id', 'Actual implementation-supported DDS domain', 'number', None, None, -2147483648, 2147483647, None, entities),
            ('dds_lifespan_kind', 'Lifespan duration mode', 'select', None, ['INFINITE', 'FINITE'], None, None, 'INFINITE', ['TOPIC', 'DATAWRITER']),
            ('dds_deadline_kind', 'Deadline period mode', 'select', None, ['INFINITE', 'FINITE'], None, None, 'INFINITE', common),
            ('dds_deadline_ms', 'Actual finite DDS deadline period', 'number', 'ms', None, 0, 2147483647999.999, None, common),
            ('dds_latency_budget_ms', 'DDS latency-budget hint', 'number', 'ms', None, 0, 2147483647999.999, 0, common),
            ('dds_lease_kind', 'Liveliness lease mode', 'select', None, ['INFINITE', 'FINITE'], None, None, 'INFINITE', common),
            ('dds_lease_ms', 'Actual finite liveliness lease', 'number', 'ms', None, 0, 2147483647999.999, None, common),
            ('dds_max_blocking_ms', 'DDS reliable-write maximum blocking', 'number', 'ms', None, 0, 2147483647999.999, 100, ['DATAWRITER']),
            ('dds_transport_priority', 'DDS transport-priority hint', 'number', None, None, -2147483648, 2147483647, 0, ['TOPIC', 'DATAWRITER']),
            ('dds_destination_order', 'DDS sample ordering', 'select', None, ['BY_RECEPTION_TIMESTAMP', 'BY_SOURCE_TIMESTAMP'], None, None, 'BY_RECEPTION_TIMESTAMP', common),
            ('dds_max_samples', 'DDS maximum retained samples (-1 unlimited)', 'number', None, None, -1, 2147483647, -1, common),
            ('dds_max_instances', 'DDS maximum managed instances (-1 unlimited)', 'number', None, None, -1, 2147483647, -1, common),
            ('dds_max_samples_per_instance', 'DDS samples per instance (-1 unlimited)', 'number', None, None, -1, 2147483647, -1, common),
            ('dds_ownership', 'DDS instance ownership', 'select', None, ['SHARED', 'EXCLUSIVE'], None, None, 'SHARED', common),
            ('dds_ownership_strength', 'DDS exclusive writer ownership strength', 'number', None, None, -2147483648, 2147483647, 0, ['DATAWRITER']),
            ('dds_time_based_filter_ms', 'DDS reader minimum separation', 'number', 'ms', None, 0, 2147483647999.999, 0, ['DATAREADER']),
            ('dds_presentation_scope', 'DDS publisher/subscriber presentation scope', 'select', None, ['INSTANCE', 'TOPIC', 'GROUP'], None, None, 'INSTANCE', ['PUBLISHER', 'SUBSCRIBER']),
            ('dds_coherent_access', 'DDS coherent presentation', 'boolean', None, None, None, None, False, ['PUBLISHER', 'SUBSCRIBER']),
            ('dds_ordered_access', 'DDS ordered presentation', 'boolean', None, None, None, None, False, ['PUBLISHER', 'SUBSCRIBER']),
            ('dds_partition_source', 'Actual partition string sequence', 'text', None, None, None, None, None, ['PUBLISHER', 'SUBSCRIBER']),
            ('dds_autoenable_created_entities', 'DDS factory automatically enables entities', 'boolean', None, None, None, None, True, ['PUBLISHER', 'SUBSCRIBER', 'PARTICIPANT', 'PARTICIPANT_FACTORY']),
            ('dds_autodispose_unregistered', 'DDS writer automatically disposes unregistered instances', 'boolean', None, None, None, None, True, ['DATAWRITER']),
            ('dds_nowriter_purge_kind', 'Reader purge delay without writers', 'select', None, ['INFINITE', 'FINITE'], None, None, 'INFINITE', ['DATAREADER']),
            ('dds_nowriter_purge_ms', 'Actual finite no-writer purge delay', 'number', 'ms', None, 0, 2147483647999.999, None, ['DATAREADER']),
            ('dds_disposed_purge_kind', 'Reader purge delay after dispose', 'select', None, ['INFINITE', 'FINITE'], None, None, 'INFINITE', ['DATAREADER']),
            ('dds_disposed_purge_ms', 'Actual finite disposed purge delay', 'number', 'ms', None, 0, 2147483647999.999, None, ['DATAREADER']),
            ('dds_service_cleanup_kind', 'Durability-service cleanup mode', 'select', None, ['INFINITE', 'FINITE'], None, None, 'FINITE', ['TOPIC', 'DATAWRITER']),
            ('dds_service_cleanup_ms', 'Durability-service cleanup delay', 'number', 'ms', None, 0, 2147483647999.999, 0, ['TOPIC', 'DATAWRITER']),
            ('dds_service_history_kind', 'Durability-service history', 'select', None, ['KEEP_LAST', 'KEEP_ALL'], None, None, 'KEEP_LAST', ['TOPIC', 'DATAWRITER']),
            ('dds_service_history_depth', 'Durability-service retained depth', 'number', None, None, 1, 2147483647, 1, ['TOPIC', 'DATAWRITER']),
            ('dds_service_max_samples', 'Durability-service sample limit (-1 unlimited)', 'number', None, None, -1, 2147483647, -1, ['TOPIC', 'DATAWRITER']),
            ('dds_service_max_instances', 'Durability-service instance limit (-1 unlimited)', 'number', None, None, -1, 2147483647, -1, ['TOPIC', 'DATAWRITER']),
            ('dds_service_max_samples_per_instance', 'Durability-service per-instance sample limit (-1 unlimited)', 'number', None, None, -1, 2147483647, -1, ['TOPIC', 'DATAWRITER']),
            ('dds_user_data_source', 'Actual user-data octet sequence', 'text', None, None, None, None, None, ['PARTICIPANT', 'DATAWRITER', 'DATAREADER']),
            ('dds_topic_data_source', 'Actual topic-data octet sequence', 'text', None, None, None, None, None, ['TOPIC']),
            ('dds_group_data_source', 'Actual publisher/subscriber group-data octet sequence', 'text', None, None, None, None, None, ['PUBLISHER', 'SUBSCRIBER']),
        ):
            native = field(key, label, 'qos', 'route', field_type=kind, unit=unit, options=options,
                           minimum=minimum, maximum=maximum, simulation_relevant=False)
            dds_metadata(native, allowed_entities, default)
            native['integer'] = kind == 'number' and unit != 'ms'
            if key in {'dds_max_samples', 'dds_max_instances', 'dds_max_samples_per_instance',
                       'dds_service_max_samples', 'dds_service_max_instances', 'dds_service_max_samples_per_instance'}:
                native['forbidden_values'] = [0]
            if key in {'dds_entity', 'dds_transport_binding', 'dds_implementation_source'}:
                native['required'] = True
            if key == 'dds_max_blocking_ms':
                for proposal in native['conditional_defaults']:
                    proposal['when']['reliability_mode'] = 'RELIABLE'
            if key == 'dds_ownership_strength':
                for proposal in native['conditional_defaults']:
                    proposal['when']['dds_ownership'] = 'EXCLUSIVE'
            if key == 'dds_service_history_depth':
                for proposal in native['conditional_defaults']:
                    proposal['when']['dds_service_history_kind'] = 'KEEP_LAST'
            if key == 'dds_service_cleanup_ms':
                native['description'] = 'DDS1.4 default durability-service cleanup delay zero means never clean up cached samples. It is not zero lifespan, nor an immediate purge deadline.'
            if key == 'dds_partition_source':
                native['description'] = 'Actual source for ordered string sequence including wildcard syntax; default sequence is empty, matching default partition. This text reference is not the partition sequence or a validated compatibility proof.'
            if key.endswith('_source') or key in {'dds_transport_binding', 'dds_domain_id', 'dds_topic_name'}:
                native['default_status'] = 'UNKNOWN'
            fields.append(native)
    if technology_id == 'dali':
        source = REVIEW_RATE_PROPOSALS['dali']
        removed = {'qos_priority', 'sync_method', 'reserved_bandwidth_percent', 'retransmission_enabled',
                   'retransmission_rate', 'retry_limit', 'retransmission_delay_ms', 'gateway_maximum_throughput',
                   'gateway_input_buffer', 'gateway_output_buffer', 'gateway_maximum_routes', 'gateway_maximum_messages_s'}
        fields = [item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key'] == 'bitrate':
                item.update(min=1200, max=1200, integer=True, description=source['note'])
            if item['key'] == 'payload_bytes':
                item.pop('default', None)
                item.update(min=1, max=3, integer=True, parameter_origin='DEVICE_CONFIGURATION', default_status='UNKNOWN',
                            source=source['source'], source_revision=source['source_revision'],
                            description='Actual complete frame data including address/command: forward16 two octets, forward24/event24 three, backward8 one; excludes start/stop/settling. Actual frame type required, no generic8-byte or fixed2-byte assumption.')
            if item['key'] == 'queue_policy':
                item['options'] = ['FIFO', 'PRIORITY', 'CUSTOM']
            if item['key'] in {'queue_size', 'seed', 'max_events'}:
                item['integer'] = True
        for key, label, scope, kind, unit, options, minimum, maximum, default in (
            ('dali_revision', 'Actual wired DALI revision', 'network', 'select', None, ['VERSION_1', 'DALI_2'], None, None, None),
            ('dali_frame', 'Actual DALI frame type', 'message', 'select', None, ['FORWARD_16', 'FORWARD_24', 'EVENT_24', 'BACKWARD_8'], None, None, None),
            ('dali_encoding', 'DALI line encoding', 'network', 'select', None, ['MANCHESTER'], None, None, 'MANCHESTER'),
            ('dali_bit_order', 'DALI data bit order', 'message', 'select', None, ['MSB_FIRST'], None, None, 'MSB_FIRST'),
            ('dali_address_space', 'Actual DALI address space', 'message', 'select', None, ['CONTROL_GEAR', 'CONTROL_DEVICE'], None, None, None),
            ('dali_addressing', 'Actual command addressing', 'message', 'select', None, ['SHORT', 'GROUP', 'BROADCAST', 'BROADCAST_UNADDRESSED'], None, None, None),
            ('dali_short_address', 'Actual target short address', 'message', 'number', None, None, 0, 63, None),
            ('dali_group_address', 'Actual target group address', 'message', 'number', None, None, 0, 31, None),
            ('dali_scene', 'Actual control-gear scene', 'message', 'number', None, None, 0, 15, None),
            ('dali_instance', 'Actual input-device instance', 'message', 'number', None, None, 0, 31, None),
            ('dali_gear_count', 'Actual control-gear logical address units', 'network', 'number', None, None, 0, 64, None),
            ('dali_control_device_count', 'Actual control-device logical address units', 'network', 'number', None, None, 0, 64, None),
            ('dali_master_mode', 'Actual controller access mode', 'network', 'select', None, ['SINGLE_MASTER', 'MULTI_MASTER'], None, None, None),
            ('dali_controller_count', 'Actual active application controllers', 'network', 'number', None, None, 1, None, None),
            ('dali_topology', 'Actual wired bus topology', 'network', 'select', None, ['DAISY_CHAIN', 'STAR', 'MIXED'], None, None, None),
            ('dali_cable_cross_section_mm2', 'Actual bus cable cross section', 'network', 'number', 'mm2', None, 0, None, None),
            ('dali_farthest_distance_m', 'Actual greatest pairwise cable distance', 'network', 'number', 'm', None, 0, None, None),
            ('dali_total_cable_m', 'Actual total bus cable length', 'network', 'number', 'm', None, 0, None, None),
            ('dali_bus_voltage_v', 'Actual bus supply voltage', 'network', 'number', 'V', None, 0, None, None),
            ('dali_supply_current_limit_ma', 'Maximum permitted total supply current', 'network', 'number', 'mA', None, 250, 250, 250),
            ('dali_maximum_supply_ma', 'Actual total maximum supply current', 'network', 'number', 'mA', None, 0, 250, None),
            ('dali_guaranteed_supply_ma', 'Actual total guaranteed supply current', 'network', 'number', 'mA', None, 0, 250, None),
            ('dali_bus_demand_ma', 'Actual total connected-device bus demand', 'network', 'number', 'mA', None, 0, 250, None),
            ('dali_timing_source', 'Actual matched-edition timing specification', 'network', 'text', None, None, None, None, None),
            ('dali_device_evidence', 'Actual device and electrical capability source', 'network', 'text', None, None, None, None, None),
            ('dali_forward_bound_ms', 'Actual complete forward frame timing bound', 'message', 'number', 'ms', None, 0, None, None),
            ('dali_backward_bound_ms', 'Actual complete backward frame timing bound', 'message', 'number', 'ms', None, 0, None, None),
            ('dali_reply_min_ms', 'Actual earliest reply start', 'message', 'number', 'ms', None, 0, None, None),
            ('dali_reply_max_ms', 'Actual latest reply start', 'message', 'number', 'ms', None, 0, None, None),
            ('dali_idle_bound_ms', 'Actual settling/idle bound before next transfer', 'network', 'number', 'ms', None, 0, None, None),
            ('dali_arbitration_bound_ms', 'Actual multi-master arbitration bound', 'network', 'number', 'ms', None, 0, None, None),
            ('dali_repeat_required', 'Actual command requires repeated frame', 'message', 'boolean', None, None, None, None, None),
            ('dali_repeat_window_ms', 'Actual selected-command repeat window', 'message', 'number', 'ms', None, 0, None, None),
            ('dali_priority_source', 'Actual event priority/access schedule source', 'network', 'text', None, None, None, None, None),
        ):
            native = field(key, label, 'physical', scope, field_type=kind, unit=unit, options=options,
                           minimum=minimum, maximum=maximum, default=default, simulation_relevant=False)
            native.update(required=False, integer=kind == 'number' and unit not in {'ms', 'm', 'mm2', 'mA', 'V'},
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN',
                          source=source['source'], source_revision=source['source_revision'],
                          description='Actual wired DALI version/device/transaction/electrical evidence; DALI+ IP/wireless and AUX24V are separate. Unknown actual settings are not auto-confirmed. NIS field validation is not a capacity or certification proof.')
            if key not in {'dali_encoding', 'dali_bit_order'}:
                native.update(source='https://www.dali-alliance.org/data/downloadables/3/4/8/dali-quick-start-guide_public-v1_1_april-2023.pdf',
                              source_revision='DALI Alliance Quick Start v1.1 April2023; Technical Note1.3 November2017; actual timing requires matching IEC62386 edition')
            if key == 'dali_farthest_distance_m':
                native['description'] = '300m reference applies to farthest pair with recommended1.5mm2 cable and <=250mA maximum total supply. Total star cable may exceed300m; actual voltage drop/capacitance/device limits require evidence.'
            fields.append(native)
    if technology_id == 'custom_udp':
        source = REVIEW_RATE_PROPOSALS[technology_id]
        removed = {'bitrate', 'mtu_bytes', 'duplex', 'vlan_id', 'rate_limit_bit_s', 'qos_priority', 'sync_method',
                   'reserved_bandwidth_percent', 'retransmission_enabled', 'retransmission_rate', 'retry_limit',
                   'retransmission_delay_ms', 'gateway_maximum_throughput', 'gateway_input_buffer',
                   'gateway_output_buffer', 'gateway_maximum_routes', 'gateway_maximum_messages_s'}
        fields = [item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key'] == 'payload_bytes':
                item.pop('default', None)
                item.pop('max', None)
                item.update(min=0, integer=True, parameter_origin='DEVICE_CONFIGURATION', default_status='UNKNOWN',
                            source=source['source'], source_revision=source['source_revision'],
                            description='Actual application data octets in one UDP datagram, separate from application headers/trailers, complete multi-datagram body and UDP/IP headers. Actual IPv4/IPv6/header/Jumbo/peer/path bounds apply.')
            if item['key'] == 'queue_policy':
                item['options'] = ['FIFO', 'PRIORITY', 'CUSTOM']
            if item['key'] in {'queue_size', 'seed', 'max_events'}:
                item['integer'] = True
        for key, label, kind, unit, options, minimum, maximum, default in (
            ('cudp_specification_source', 'Actual UDP application specification', 'text', None, None, None, None, None),
            ('cudp_specification_revision', 'Actual UDP application revision', 'text', None, None, None, None, None),
            ('cudp_transport_binding', 'Actual UDP/IP/link profile reference', 'text', None, None, None, None, None),
            ('cudp_ip_version', 'Actual IP family', 'select', None, ['IPV4', 'IPV6'], None, None, None),
            ('cudp_size_mode', 'UDP/IP datagram size mode', 'select', None, ['NORMAL', 'JUMBO'], None, None, 'NORMAL'),
            ('cudp_udp_header_bytes', 'UDP fixed header', 'number', 'Byte', None, 8, 8, 8),
            ('cudp_application_header_bytes', 'Actual custom application header', 'number', 'Byte', None, 0, None, None),
            ('cudp_application_trailer_bytes', 'Actual custom application trailer', 'number', 'Byte', None, 0, None, None),
            ('cudp_message_bytes', 'Actual complete UDP application PDU', 'number', 'Byte', None, 0, None, None),
            ('cudp_datagram_bytes', 'Actual UDP header plus PDU', 'number', 'Byte', None, 8, 4294967295, None),
            ('cudp_udp_length_field', 'Actual UDP Length field', 'number', 'Byte', None, 0, 65535, None),
            ('cudp_ipv4_header_bytes', 'Actual IPv4 header including options', 'number', 'Byte', None, 20, 60, None),
            ('cudp_ipv6_extension_bytes', 'Actual IPv6 extension headers before UDP', 'number', 'Byte', None, 0, 4294967295, None),
            ('cudp_ipv6_payload_length', 'Actual IPv6 Payload Length field', 'number', 'Byte', None, 0, 65535, None),
            ('cudp_jumbo_payload_length', 'Actual IPv6 Jumbo Payload option value', 'number', 'Byte', None, 65536, 4294967295, None),
            ('cudp_ip_packet_bytes', 'Actual complete unfragmented IP packet', 'number', 'Byte', None, 28, 4294967335, None),
            ('cudp_peer_message_limit_bytes', 'Actual peer accepted application PDU', 'number', 'Byte', None, 0, None, None),
            ('cudp_path_mtu_bytes', 'Actual confirmed path MTU', 'number', 'Byte', None, 1, None, None),
            ('cudp_fragmentation_policy', 'IP fragmentation policy', 'select', None, ['NO_IP_FRAGMENTATION', 'EXPLICIT_IP_FRAGMENTATION'], None, None, 'NO_IP_FRAGMENTATION'),
            ('cudp_checksum_policy', 'UDP checksum policy', 'select', None, ['ENABLED', 'IPV4_DISABLED'], None, None, 'ENABLED'),
            ('cudp_udp_checksum_value', 'Actual serialized UDP checksum', 'number', None, None, 0, 65535, None),
            ('cudp_jumbo_supported', 'Actual complete path/peer Jumbo support', 'boolean', None, None, None, None, None),
            ('cudp_application_ack', 'Actual application acknowledgement', 'boolean', None, None, None, None, None),
            ('cudp_ack_timeout_ms', 'Actual application acknowledgement timeout', 'number', 'ms', None, 0, None, None),
            ('cudp_ack_retry_limit', 'Actual application acknowledgement retries', 'number', 'retries', None, 0, None, None),
            ('cudp_retry_control_source', 'Actual retry/deduplication/order contract', 'text', None, None, None, None, None),
            ('cudp_congestion_control_source', 'Actual congestion-control contract', 'text', None, None, None, None, None),
            ('cudp_application_integrity_source', 'Actual application integrity/security contract', 'text', None, None, None, None, None),
            ('cudp_fragmentation_source', 'Actual fragmentation/reassembly contract', 'text', None, None, None, None, None),
            ('cudp_full_body_bytes', 'Actual complete multi-datagram application body', 'number', 'Byte', None, 0, None, None),
            ('cudp_device_evidence', 'Actual endpoint/path/timing evidence', 'text', None, None, None, None, None),
        ):
            native = field(key, label, 'communication', 'message', field_type=kind, unit=unit,
                           options=options, minimum=minimum, maximum=maximum, default=default, simulation_relevant=False)
            native.update(required=key in {'cudp_specification_source', 'cudp_specification_revision', 'cudp_transport_binding', 'cudp_ip_version', 'cudp_size_mode'},
                          integer=kind == 'number' and unit != 'ms',
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN',
                          source=source['source'], source_revision=source['source_revision'],
                          description='Registered UDP/IP baseline proposal or actual custom application/path fact. UDP does not supply application reliability/order/deduplication. Path/peer/framing and checksum execution remain separate evidence.')
            if key == 'cudp_ipv4_header_bytes':
                native['multiple_of'] = 4
            fields.append(native)
    if technology_id == 'custom_text':
        source = REVIEW_RATE_PROPOSALS[technology_id]
        removed = {'qos_priority', 'sync_method', 'reserved_bandwidth_percent', 'retransmission_enabled',
                   'retransmission_rate', 'retry_limit', 'retransmission_delay_ms', 'gateway_maximum_throughput',
                   'gateway_input_buffer', 'gateway_output_buffer', 'gateway_maximum_routes', 'gateway_maximum_messages_s'}
        fields = [item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key'] == 'payload_bytes':
                item.pop('default', None)
                item.pop('max', None)
                item.update(min=0, integer=True, parameter_origin='DEVICE_CONFIGURATION', default_status='UNKNOWN',
                            source=source['source'], source_revision=source['source_revision'],
                            description='Actual encoded text octets, excluding framing/signature overhead counted in header/trailer. Not Unicode scalar count, no default8 or universal65535-byte cap.')
            if item['key'] == 'queue_policy':
                item['options'] = ['FIFO', 'PRIORITY', 'CUSTOM']
            if item['key'] in {'queue_size', 'seed', 'max_events'}:
                item['integer'] = True
        for key, label, kind, unit, options, minimum in (
            ('ctxt_specification_source', 'Actual text protocol specification', 'text', None, None, None),
            ('ctxt_specification_revision', 'Actual text protocol revision', 'text', None, None, None),
            ('ctxt_transport_binding', 'Actual lower transport/interface reference', 'text', None, None, None),
            ('ctxt_encoding', 'Actual text encoding', 'select', None, ['UTF8', 'ASCII', 'UTF16LE', 'UTF16BE', 'OTHER'], None),
            ('ctxt_framing', 'Actual text message framing', 'select', None, ['FIXED_LENGTH', 'LENGTH_PREFIX', 'DELIMITER', 'TRANSPORT_MESSAGE', 'CONNECTION_CLOSE', 'CUSTOM'], None),
            ('ctxt_encoding_source', 'Actual encoding/normalization/invalid-input contract', 'text', None, None, None),
            ('ctxt_layout_source', 'Actual application and framing layout', 'text', None, None, None),
            ('ctxt_text_value', 'Actual text value for byte-count verification', 'text', None, None, None),
            ('ctxt_code_points', 'Actual Unicode scalar count (not grapheme count)', 'number', 'scalars', None, 0),
            ('ctxt_utf16_code_units', 'Actual UTF16 code units (excluding framing signature)', 'number', 'units', None, 0),
            ('ctxt_header_bytes', 'Actual framing header/signature bytes', 'number', 'Byte', None, 0),
            ('ctxt_trailer_bytes', 'Actual framing trailer/delimiter bytes', 'number', 'Byte', None, 0),
            ('ctxt_escape_expansion_bytes', 'Actual encoded escaping expansion', 'number', 'Byte', None, 0),
            ('ctxt_message_bytes', 'Actual complete encoded text message', 'number', 'Byte', None, 0),
            ('ctxt_peer_message_limit_bytes', 'Actual peer full-message limit', 'number', 'Byte', None, 0),
            ('ctxt_fixed_length_bytes', 'Actual fixed complete message bytes', 'number', 'Byte', None, 1),
            ('ctxt_delimiter_hex', 'Actual encoded delimiter octets (hex)', 'text', None, None, None),
            ('ctxt_escaping_source', 'Actual delimiter/character escaping rules', 'text', None, None, None),
            ('ctxt_device_evidence', 'Actual peer encoding/buffering/timing evidence', 'text', None, None, None),
        ):
            native = field(key, label, 'communication', 'message', field_type=kind, unit=unit,
                           options=options, minimum=minimum, simulation_relevant=False)
            native.update(required=key in {'ctxt_specification_source', 'ctxt_specification_revision', 'ctxt_transport_binding', 'ctxt_encoding', 'ctxt_framing'},
                          integer=kind == 'number', parameter_origin='DEVICE_CONFIGURATION', default_status='UNKNOWN',
                          source=source['source'], source_revision=source['source_revision'],
                          description='Actual custom-text fact from the named application revision. No universal charset or delimiter default. Encoding checks do not establish actual transport/framing/peer capacity.')
            if key == 'ctxt_delimiter_hex':
                native['pattern'] = r'(?:[0-9a-fA-F]{2})+'
            fields.append(native)
    if technology_id == 'custom_tcp':
        source = REVIEW_RATE_PROPOSALS[technology_id]
        removed = {'bitrate', 'mtu_bytes', 'duplex', 'vlan_id', 'rate_limit_bit_s', 'qos_priority', 'sync_method',
                   'reserved_bandwidth_percent', 'retransmission_enabled', 'retransmission_rate', 'retry_limit',
                   'retransmission_delay_ms', 'gateway_maximum_throughput', 'gateway_input_buffer',
                   'gateway_output_buffer', 'gateway_maximum_routes', 'gateway_maximum_messages_s'}
        fields = [item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key'] == 'payload_bytes':
                item.pop('default', None)
                item.pop('max', None)
                item.update(min=0, integer=True, parameter_origin='DEVICE_CONFIGURATION', default_status='UNKNOWN',
                            source=source['source'], source_revision=source['source_revision'],
                            description='Actual encoded application data bytes; a full message may span TCP segments/chunks. No65535/MTU/MSS application limit or default8.')
            if item['key'] == 'queue_policy':
                item['options'] = ['FIFO', 'PRIORITY', 'CUSTOM']
            if item['key'] in {'queue_size', 'seed', 'max_events'}:
                item['integer'] = True
        for key, label, kind, unit, options, minimum, default in (
            ('ctcp_specification_source', 'Actual TCP application specification', 'text', None, None, None, None),
            ('ctcp_specification_revision', 'Actual TCP application revision', 'text', None, None, None, None),
            ('ctcp_transport_binding', 'Actual TCP/IP/link profile reference', 'text', None, None, None, None),
            ('ctcp_stream_service', 'TCP delivery service', 'select', None, ['ORDERED_BYTE_STREAM'], None, 'ORDERED_BYTE_STREAM'),
            ('ctcp_framing', 'Actual TCP application message framing', 'select', None, ['FIXED_LENGTH', 'LENGTH_PREFIX', 'DELIMITER', 'CONNECTION_CLOSE', 'CUSTOM'], None, None),
            ('ctcp_layout_source', 'Actual data and framing layout reference', 'text', None, None, None, None),
            ('ctcp_header_bytes', 'Actual application header bytes', 'number', 'Byte', None, 0, None),
            ('ctcp_trailer_bytes', 'Actual application trailer bytes', 'number', 'Byte', None, 0, None),
            ('ctcp_escape_expansion_bytes', 'Actual encoded escaping expansion', 'number', 'Byte', None, 0, None),
            ('ctcp_message_bytes', 'Actual complete encoded application message', 'number', 'Byte', None, 0, None),
            ('ctcp_peer_message_limit_bytes', 'Actual peer accepted application message', 'number', 'Byte', None, 0, None),
            ('ctcp_fixed_length_bytes', 'Actual complete fixed message length', 'number', 'Byte', None, 1, None),
            ('ctcp_length_prefix_bytes', 'Actual message-length prefix width', 'number', 'Byte', None, 1, None),
            ('ctcp_length_prefix_scope', 'Actual prefix count scope', 'select', None, ['PAYLOAD', 'COMPLETE_MESSAGE', 'CUSTOM'], None, None),
            ('ctcp_length_prefix_order', 'Actual prefix byte order', 'select', None, ['LITTLE_ENDIAN', 'BIG_ENDIAN', 'CUSTOM'], None, None),
            ('ctcp_delimiter_hex', 'Actual delimiter octets (hex)', 'text', None, None, None, None),
            ('ctcp_escaping_source', 'Actual delimiter escaping rules', 'text', None, None, None, None),
            ('ctcp_security_profile', 'Actual application security profile reference', 'text', None, None, None, None),
            ('ctcp_application_ack', 'Actual application acknowledgement', 'boolean', None, None, None, None),
            ('ctcp_application_ack_timeout_ms', 'Actual application acknowledgement timeout', 'number', 'ms', None, 0, None),
            ('ctcp_device_evidence', 'Actual peer buffering/timing evidence', 'text', None, None, None, None),
        ):
            native = field(key, label, 'communication', 'message', field_type=kind, unit=unit,
                           options=options, minimum=minimum, default=default, simulation_relevant=False)
            native.update(required=key in {'ctcp_specification_source', 'ctcp_specification_revision', 'ctcp_transport_binding', 'ctcp_framing'},
                          integer=kind == 'number' and unit != 'ms',
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN',
                          source=source['source'], source_revision=source['source_revision'],
                          description='TCP standard delivery semantics or actual application framing fact; transport segments/read buffers/PSH are not application message boundaries. Actual lower TCP/IP/link parameters are separate.')
            if key == 'ctcp_delimiter_hex':
                native['pattern'] = r'(?:[0-9a-fA-F]{2})+'
            fields.append(native)
    if technology_id == 'custom_protocol':
        source = REVIEW_RATE_PROPOSALS[technology_id]
        removed = {'qos_priority', 'sync_method', 'reserved_bandwidth_percent', 'retransmission_enabled',
                   'retransmission_rate', 'retry_limit', 'retransmission_delay_ms', 'gateway_maximum_throughput',
                   'gateway_input_buffer', 'gateway_output_buffer', 'gateway_maximum_routes', 'gateway_maximum_messages_s'}
        fields = [item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key'] == 'payload_bytes':
                item.pop('default', None)
                item.pop('max', None)
                item.update(min=0, integer=True, parameter_origin='DEVICE_CONFIGURATION', default_status='UNKNOWN',
                            source=source['source'], source_revision=source['source_revision'],
                            description='Actual custom application data octets. No universal8/65535-byte limit/default; actual PDU overhead, peer limit and lower transport are independent.')
            if item['key'] == 'queue_policy':
                item['options'] = ['FIFO', 'PRIORITY', 'CUSTOM']
            if item['key'] in {'queue_size', 'seed', 'max_events'}:
                item['integer'] = True
        for key, label, kind, unit, options, minimum in (
            ('cp_specification_source', 'Actual application protocol specification', 'text', None, None, None),
            ('cp_specification_revision', 'Actual application protocol revision', 'text', None, None, None),
            ('cp_transport_binding', 'Actual lower transport/interface reference', 'text', None, None, None),
            ('cp_pdu_layout_source', 'Actual PDU layout/encoding reference', 'text', None, None, None),
            ('cp_framing_source', 'Actual message framing contract', 'text', None, None, None),
            ('cp_overhead_bytes', 'Actual complete application overhead', 'number', 'Byte', None, 0),
            ('cp_pdu_bytes', 'Actual complete application PDU', 'number', 'Byte', None, 0),
            ('cp_peer_pdu_limit_bytes', 'Actual peer accepted PDU limit', 'number', 'Byte', None, 0),
            ('cp_addressing_source', 'Actual endpoint/resource addressing contract', 'text', None, None, None),
            ('cp_session_source', 'Actual session/state-transition contract', 'text', None, None, None),
            ('cp_integrity_source', 'Actual checksum/security contract', 'text', None, None, None),
            ('cp_acknowledgement', 'Actual acknowledgement semantics', 'select', None, ['NONE', 'LOWER_TRANSPORT_ONLY', 'APPLICATION', 'CUSTOM'], None),
            ('cp_ack_timeout_ms', 'Actual application acknowledgement timeout', 'number', 'ms', None, 0),
            ('cp_response_bound_ms', 'Actual application response bound', 'number', 'ms', None, 0),
            ('cp_retry_limit', 'Actual application retry count', 'number', 'retries', None, 0),
            ('cp_retry_delay_ms', 'Actual application retry delay', 'number', 'ms', None, 0),
            ('cp_device_evidence', 'Actual peer capability/timing evidence', 'text', None, None, None),
        ):
            native = field(key, label, 'communication', 'route' if unit == 'ms' else 'message',
                           field_type=kind, unit=unit, options=options, minimum=minimum, simulation_relevant=False)
            native.update(required=key in {'cp_specification_source', 'cp_specification_revision', 'cp_transport_binding', 'cp_framing_source'},
                          integer=kind == 'number' and unit != 'ms', parameter_origin='DEVICE_CONFIGURATION', default_status='UNKNOWN',
                          source=source['source'], source_revision=source['source_revision'],
                          description='Actual application protocol fact from the named revision. No general literature default; application acknowledgements/retries and lower transport reliability remain separate.')
            fields.append(native)
    if technology_id == 'custom_binary':
        source = REVIEW_RATE_PROPOSALS[technology_id]
        removed = {'qos_priority', 'sync_method', 'reserved_bandwidth_percent', 'retransmission_enabled',
                   'retransmission_rate', 'retry_limit', 'retransmission_delay_ms', 'gateway_maximum_throughput',
                   'gateway_input_buffer', 'gateway_output_buffer', 'gateway_maximum_routes', 'gateway_maximum_messages_s'}
        fields = [item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key'] == 'payload_bytes':
                item.pop('default', None)
                item.pop('max', None)
                item.update(min=0, integer=True, parameter_origin='DEVICE_CONFIGURATION', default_status='UNKNOWN',
                            source=source['source'], source_revision=source['source_revision'],
                            description='Actual encoded application data bytes. No universal 65535-byte binary message limit or 8-byte CAN default; header/trailer/padding and actual peer limit are separate.')
            if item['key'] == 'queue_policy':
                item['options'] = ['FIFO', 'PRIORITY', 'CUSTOM']
            if item['key'] in {'queue_size', 'seed', 'max_events'}:
                item['integer'] = True
        for key, label, kind, unit, options, minimum in (
            ('cb_specification_source', 'Actual binary specification reference', 'text', None, None, None),
            ('cb_specification_revision', 'Actual binary specification revision', 'text', None, None, None),
            ('cb_transport_binding', 'Actual lower transport/interface reference', 'text', None, None, None),
            ('cb_layout_source', 'Actual signal/field layout reference', 'text', None, None, None),
            ('cb_framing', 'Actual binary message framing', 'select', None, ['FIXED_LENGTH', 'LENGTH_PREFIX', 'DELIMITER', 'TRANSPORT_MESSAGE', 'CUSTOM'], None),
            ('cb_byte_order', 'Actual multi-byte value order', 'select', None, ['LITTLE_ENDIAN', 'BIG_ENDIAN', 'FIELD_SPECIFIC'], None),
            ('cb_bit_order', 'Actual bit significance/layout order', 'select', None, ['LSB_FIRST', 'MSB_FIRST', 'FIELD_SPECIFIC'], None),
            ('cb_header_bytes', 'Actual encoded application header', 'number', 'Byte', None, 0),
            ('cb_trailer_bytes', 'Actual encoded application trailer', 'number', 'Byte', None, 0),
            ('cb_padding_bytes', 'Actual encoded application padding', 'number', 'Byte', None, 0),
            ('cb_message_bytes', 'Actual complete encoded binary message', 'number', 'Byte', None, 0),
            ('cb_peer_message_limit_bytes', 'Actual peer message capacity', 'number', 'Byte', None, 0),
            ('cb_fixed_length_bytes', 'Actual fixed message length', 'number', 'Byte', None, 1),
            ('cb_length_prefix_bytes', 'Actual length-prefix width', 'number', 'Byte', None, 1),
            ('cb_length_prefix_scope', 'Actual length-prefix count scope', 'select', None, ['PAYLOAD', 'COMPLETE_MESSAGE', 'CUSTOM'], None),
            ('cb_delimiter_hex', 'Actual framing delimiter octets (hex)', 'text', None, None, None),
            ('cb_escaping_source', 'Actual delimiter escaping specification', 'text', None, None, None),
            ('cb_checksum', 'Actual application checksum scheme', 'select', None, ['NONE', 'CRC', 'HASH_MAC', 'CUSTOM'], None),
            ('cb_checksum_bytes', 'Actual checksum octets included in header/trailer', 'number', 'Byte', None, 0),
            ('cb_checksum_source', 'Actual checksum algorithm/coverage reference', 'text', None, None, None),
            ('cb_device_evidence', 'Actual peer capability/timing evidence reference', 'text', None, None, None),
        ):
            native = field(key, label, 'communication', 'message', field_type=kind, unit=unit,
                           options=options, minimum=minimum, simulation_relevant=False)
            native.update(required=key in {'cb_specification_source', 'cb_specification_revision', 'cb_transport_binding', 'cb_framing'},
                          integer=kind == 'number', parameter_origin='DEVICE_CONFIGURATION', default_status='UNKNOWN',
                          source=source['source'], source_revision=source['source_revision'],
                          description='Actual user-defined protocol fact from the named revision; there is no universal literature default. This field alone does not prove wire encoding, peer capability or capacity.')
            if key == 'cb_delimiter_hex':
                native['pattern'] = r'(?:[0-9a-fA-F]{2})+'
            fields.append(native)
    if technology_id == 'coap':
        source=REVIEW_RATE_PROPOSALS['coap']
        removed={'bitrate','qos_priority','sync_method','reserved_bandwidth_percent','retransmission_enabled',
                 'retransmission_rate','retry_limit','retransmission_delay_ms','gateway_maximum_throughput',
                 'gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s',
                 'mtu_bytes','duplex','vlan_id','rate_limit_bit_s'}
        fields=[item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.pop('max',None)
                item.update(min=0,integer=True,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',
                            source=source['source'],source_revision=source['source_revision'],
                            description='Actual CoAP payload in one message/block, not complete body or message size.1152 is a conservative unknown-path message bound,1024 its payload suggestion. Reliable CSMSizes/BERT can differ; no universal1152payloadcap.')
            if item['key']=='queue_policy':
                item['options']=['FIFO','PRIORITY','CUSTOM']
            if item['key'] in {'queue_size','seed','max_events'}:
                item['integer']=True
        native_defaults={'coap_version':1,'coap_ack_timeout_s':2,'coap_ack_random_factor':1.5,'coap_max_retransmit':4,
                         'coap_nstart':1,'coap_default_leisure_s':5,'coap_probing_rate_Bps':1,'coap_max_latency_s':100}
        for key,label,unit,options,minimum,maximum,default,document in (
            ('coap_transport','Actual CoAP transport',None,['UDP','DTLS','TCP','TLS','WS','WSS'],None,None,None,'7252'),
            ('coap_version','UDP message version baseline',None,None,1,1,None,'7252'),
            ('coap_message_type','Actual UDP message type',None,['CON','NON','ACK','RST'],None,None,None,'7252'),
            ('coap_message_id','Actual UDP message ID',None,None,0,65535,None,'7252'),
            ('coap_code','Actual encoded request/response code',None,None,0,255,None,'7252'),
            ('coap_token_format','Token encoding baseline',None,['BASE_8','EXTENDED_RFC8974'],None,None,'BASE_8','8974'),
            ('coap_token_bytes','Actual token length','Byte',None,0,65804,None,'8974'),
            ('coap_peer_token_limit','Actual peer-supported token limit','Byte',None,8,65804,None,'8974'),
            ('coap_uri','Actual CoAP resource URI',None,None,None,None,None,'7252'),
            ('coap_port','Endpoint service port proposal',None,None,1,65535,None,'8323'),
            ('coap_ack_timeout_s','ACK timeout baseline','s',None,0,None,None,'7252'),
            ('coap_ack_random_factor','ACK randomization factor baseline',None,None,1,None,None,'7252'),
            ('coap_max_retransmit','Maximum retransmission count baseline',None,None,0,None,None,'7252'),
            ('coap_nstart','Outstanding confirmable exchanges baseline',None,None,1,None,None,'7252'),
            ('coap_default_leisure_s','Multicast response leisure baseline','s',None,0,None,None,'7252'),
            ('coap_probing_rate_Bps','Nonresponsive endpoint probing rate','Byte/s',None,0,None,None,'7252'),
            ('coap_congestion_control_verified','Actual changed-timer congestion-control evidence',None,None,None,None,None,'7252'),
            ('coap_max_latency_s','Protocol datagram lifetime assumption','s',None,0,None,None,'7252'),
            ('coap_processing_delay_s','Protocol processing-delay assumption','s',None,0,None,None,'7252'),
            ('coap_max_transmit_span_s','Derived last retransmission span','s',None,0,None,None,'7252'),
            ('coap_max_transmit_wait_s','Derived acknowledgement wait bound','s',None,0,None,None,'7252'),
            ('coap_max_rtt_s','Derived protocol maximum RTT','s',None,0,None,None,'7252'),
            ('coap_exchange_lifetime_s','Message ID exchange lifetime','s',None,0,None,None,'7252'),
            ('coap_non_lifetime_s','Non-confirmable message ID lifetime','s',None,0,None,None,'7252'),
            ('coap_non_repeat','Actual NON message repetition',None,None,None,None,None,'7252'),
            ('coap_max_age_s','Absent response Max-Age baseline','s',None,0,4294967295,60,'7252'),
            ('coap_content_format','Actual registered Content-Format',None,None,0,65535,None,'7252'),
            ('coap_accept','Actual registered Accept format',None,None,0,65535,None,'7252'),
            ('coap_options_bytes','Actual encoded options length','Byte',None,0,None,None,'7252'),
            ('coap_header_bytes','Actual native header length','Byte',None,2,None,None,'8323'),
            ('coap_payload_marker_bytes','Actual payload marker length','Byte',None,0,1,None,'7252'),
            ('coap_message_bytes','Actual complete encoded CoAP message','Byte',None,2,None,None,'8323'),
            ('coap_body_bytes','Actual complete representation body','Byte',None,0,None,None,'7959'),
            ('coap_mtu_policy','Actual path-size policy',None,['VALIDATED_PATH','UNKNOWN_PATH_RFC7252'],None,None,None,'7252'),
            ('coap_path_mtu_bytes','Actual confirmed path MTU','Byte',None,1,None,None,'7252'),
            ('coap_csm_max_message_bytes','Reliable CSM max-message base value','Byte',None,0,4294967295,None,'8323'),
            ('coap_csm_blockwise_supported','Actual reliable block-wise capability',None,None,None,None,None,'8323'),
            ('coap_block_kind','Actual block option',None,['BLOCK1','BLOCK2'],None,None,None,'7959'),
            ('coap_block_usage','Actual block option usage',None,['DESCRIPTIVE','CONTROL'],None,None,None,'7959'),
            ('coap_block_number','Actual block number',None,None,0,1048575,None,'7959'),
            ('coap_block_szx','Actual block size exponent;7 meansBERT',None,None,0,7,None,'8323'),
            ('coap_block_more','Actual more blocks flag',None,None,None,None,None,'7959'),
            ('coap_observe_kind','Actual Observe option use',None,['REQUEST','NOTIFICATION'],None,None,None,'7641'),
            ('coap_observe_value','Actual Observe register/cancel or sequence',None,None,0,16777215,None,'7641'),
            ('coap_multicast','Actual multicast communication',None,None,None,None,None,'7252'),
            ('coap_peer_capability_source','Actual endpoint/negotiation evidence',None,None,None,None,None,'8323'),
        ):
            boolean=key in {'coap_congestion_control_verified','coap_non_repeat','coap_csm_blockwise_supported','coap_block_more','coap_multicast'}
            text=key in {'coap_uri','coap_peer_capability_source'}
            native=field(key,label,'communication','message' if key in {'coap_code','coap_message_id','coap_message_type','coap_token_bytes','coap_options_bytes','coap_header_bytes','coap_payload_marker_bytes','coap_message_bytes','coap_block_number','coap_block_szx','coap_block_more'} else 'route',
                         field_type='text' if text else 'boolean' if boolean else 'select' if options else 'number',
                         unit=unit,minimum=minimum,maximum=maximum,options=options,default=default,simulation_relevant=False,
                         description='CoAP native configuration. Standard proposals are not measured endpoint/path/round-trip facts. UDP reliability fields do not apply to reliable transports; actual capabilities and protocol sequence require evidence.')
            native.update(required=key=='coap_transport',integer=native['type']=='number' and unit!='s' and key not in {'coap_ack_random_factor','coap_probing_rate_Bps'},
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN',source='https://www.rfc-editor.org/rfc/rfc'+document+'.html',
                          source_revision='IETF RFC'+document+' accessed2026-10-01')
            if key in native_defaults:
                native['conditional_defaults']=[{'when':{'coap_transport':transport},'value':native_defaults[key]} for transport in ('UDP','DTLS')]
            if key=='coap_port':
                native['conditional_defaults']=[{'when':{'coap_transport':transport},'value':port} for transport,port in (('UDP',5683),('DTLS',5684),('TCP',5683),('TLS',5684),('WS',80),('WSS',443))]
            if key=='coap_processing_delay_s':
                native['conditional_defaults']=[{'when':{'coap_transport':transport,'coap_ack_timeout_s':2},'value':2} for transport in ('UDP','DTLS')]
            if key in {'coap_max_transmit_span_s','coap_max_transmit_wait_s'}:
                native['conditional_defaults']=[{'when':{'coap_transport':transport,'coap_ack_timeout_s':2,'coap_ack_random_factor':1.5,'coap_max_retransmit':4},'value':45 if key=='coap_max_transmit_span_s' else 93} for transport in ('UDP','DTLS')]
            if key=='coap_max_rtt_s':
                native['conditional_defaults']=[{'when':{'coap_transport':transport,'coap_max_latency_s':100,'coap_processing_delay_s':2},'value':202} for transport in ('UDP','DTLS')]
            if key=='coap_exchange_lifetime_s':
                native['conditional_defaults']=[{'when':{'coap_transport':transport,'coap_ack_timeout_s':2,'coap_ack_random_factor':1.5,'coap_max_retransmit':4,'coap_max_latency_s':100,'coap_processing_delay_s':2},'value':247} for transport in ('UDP','DTLS')]
            if key=='coap_non_lifetime_s':
                native['conditional_defaults']=[{'when':{'coap_transport':transport,'coap_non_repeat':repeat,'coap_ack_timeout_s':2,'coap_ack_random_factor':1.5,'coap_max_retransmit':4,'coap_max_latency_s':100},'value':145 if repeat else 100} for transport in ('UDP','DTLS') for repeat in (True,False)]
            if key=='coap_csm_max_message_bytes':
                native['conditional_defaults']=[{'when':{'coap_transport':transport},'value':1152} for transport in ('TCP','TLS','WS','WSS')]
            if key=='coap_uri':
                native.update(format='ABSOLUTE_URI',allowed_schemes=['coap','coaps','coap+tcp','coaps+tcp','coap+ws','coaps+ws'])
            if key=='coap_max_age_s':
                native['integer']=True
            if native.get('conditional_defaults'):
                native.update(parameter_origin='TRANSPORT_PROFILE',default_status='PROPOSED')
            fields.append(native)
    if technology_id == 'cip_safety':
        source=REVIEW_RATE_PROPOSALS['cip_safety']
        removed={'qos_priority','sync_method','reserved_bandwidth_percent','retransmission_enabled',
                 'retransmission_rate','retry_limit','retransmission_delay_ms','gateway_maximum_throughput',
                 'gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s'}
        fields=[item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.update(min=0,max=250,integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                            source='https://www.odva.org/publication_download/cip-safety-safety-networking-for-today-and-beyond-pub-110/',
                            source_revision='ODVA Pub110 extended short<=2/long<=250 safety data',
                            description='Actual safety user data before native CRC/time/redundancy/transport overhead. Not EtherNet/IP MTU, CAN frame length, or a250byte wire packet. Actual certified device assembly may be smaller.')
            if item['key']=='queue_policy':
                item.update(options=['FIFO','PRIORITY','CUSTOM'],description='Abstract host queue; not a CIP Safety age limit or confirmed black-channel transport schedule.')
            if item['key'] in {'queue_size','seed','max_events'}:
                item['integer']=True
        public='https://www.odva.org/publication_download/cip-safety-safety-networking-for-today-and-beyond-pub-110/'
        change='https://www.odva.org/wp-content/uploads/2022/03/2022-ODVA-Conference_CIP_Safety_Embracing_IEC61784-3_Edition_4_Peng-Seidlitz-Crane-Guru_FINAL.pdf'
        vendor='https://www.rockwellautomation.com/en-pl/docs/add-on-profiles/common/8/pvdnsafetyio2-ditamap/reaction-time-limit-config-dialog/reaction-time-limit-config-dialog-params.html'
        for key,label,unit,options,minimum,maximum,default,reference in (
            ('cips_transport','Actual safety transport',None,['ETHERNET_IP','DEVICENET','SERCOS_III'],None,None,None,'public'),
            ('cips_baseline','Safety conformance baseline',None,['MODERN_EXTENDED','CERTIFIED_LEGACY'],None,None,'MODERN_EXTENDED','change'),
            ('cips_format','Safety packet format baseline',None,['EXTENDED','BASE'],None,None,'EXTENDED','change'),
            ('cips_max_fault_number','Maximum fault number baseline',None,None,0,None,None,'change'),
            ('cips_data_size','Actual short/long safety data section',None,['SHORT','LONG'],None,None,None,'public'),
            ('cips_connection','Actual safety connection cast',None,['UNICAST','MULTICAST'],None,None,None,'public'),
            ('cips_consumers','Actual safety validator consumers','nodes',None,1,None,None,'public'),
            ('cips_direction','Actual connection direction',None,['INPUT','OUTPUT','PEER'],None,None,None,'public'),
            ('cips_snn','Actual six-byte safety network number',None,None,None,None,None,'snn'),
            ('cips_node_reference','Actual local node/port address reference',None,None,None,None,None,'public'),
            ('cips_ip_address','Actual EtherNet/IP node address',None,None,None,None,None,'public'),
            ('cips_devicenet_node','Actual DeviceNet node MAC ID',None,None,0,63,None,'devicenet'),
            ('cips_production_id','Actual production identifier reference',None,None,None,None,None,'public'),
            ('cips_configuration_signature','Actual certified configuration signature',None,None,None,None,None,'public'),
            ('cips_configuration_owner','Actual configuration ownership reference',None,None,None,None,None,'public'),
            ('cips_configuration_locked','Observed configuration locking',None,None,None,None,None,'public'),
            ('cips_safety_connection_established','Observed Safety_Open establishment',None,None,None,None,None,'public'),
            ('cips_device_profile','Actual device-specific timing profile',None,['DEVICE_SPECIFIC','GUARDLOGIX_SAFETY_IO'],None,None,None,'vendor'),
            ('cips_rpi_ms','Actual requested packet interval','ms',None,0,None,None,'vendor'),
            ('cips_safety_task_ms','Actual safety task period','ms',None,0,None,None,'vendor'),
            ('cips_timeout_multiplier','Actual timeout multiplier','RPIs',None,1,None,None,'vendor'),
            ('cips_network_delay_percent','Actual network delay multiplier','%',None,0,None,None,'vendor'),
            ('cips_crtl_ms','Actual rounded connection reaction time limit','ms',None,0,None,None,'vendor'),
            ('cips_data_age_bound_ms','Actual worst-case received data age','ms',None,0,None,None,'public'),
            ('cips_application_reaction_limit_ms','Actual allocated safety reaction budget','ms',None,0,None,None,'public'),
            ('cips_time_coordination_bound_ms','Actual time-coordination delay bound','ms',None,0,None,None,'public'),
            ('cips_time_correction_bound_ms','Actual multicast time-correction bound','ms',None,0,None,None,'public'),
            ('cips_nte_ticks','Actual Network Time Expectation','128us ticks',None,1,None,None,'change'),
            ('cips_safety_manual_source','Actual device safety manual/revision',None,None,None,None,None,'public'),
            ('cips_conformance_source','Actual device declaration/certification reference',None,None,None,None,None,'public'),
        ):
            boolean=key in {'cips_configuration_locked','cips_safety_connection_established'}
            text=key in {'cips_snn','cips_node_reference','cips_ip_address','cips_production_id','cips_configuration_signature','cips_configuration_owner','cips_safety_manual_source','cips_conformance_source'}
            native=field(key,label,'communication','route',field_type='text' if text else 'boolean' if boolean else 'select' if options else 'number',
                         unit=unit,minimum=minimum,maximum=maximum,options=options,default=default,simulation_relevant=False,
                         description='CIP Safety native configuration/provenance. Protocol proposals do not prove certified device behavior, actual data age, safety reaction time or black-channel capacity. Use explicit lower transport parameters separately.')
            native.update(required=key=='cips_transport',integer=native['type']=='number' and unit not in {'ms','%'},
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN',
                          source={'public':public,'change':change,'vendor':vendor,
                                  'snn':'https://www.rockwellautomation.com/en-gb/docs/technical/logix5000/_online/1756-rm012/guardlogix-5580-and-compact-guardlogix-5580-safety/cip-safety-systems-and-safety-network-numbers/snn-formats.html',
                                  'devicenet':'https://www.odva.org/technology-standards/key-technologies/devicenet/'}[reference],
                          source_revision='ODVA publicprotocoloverview /2022IEC61784changes; actualcertifieddevice andcurrentfullVolume5 revision required')
            if key=='cips_snn':
                native['pattern']='(?:[0-9A-Fa-f]{12}|[0-9A-Fa-f]{4}_[0-9A-Fa-f]{4}_[0-9A-Fa-f]{4})'
            if key=='cips_ip_address':
                native['format']='IP_ADDRESS'
            if key=='cips_max_fault_number':
                native['conditional_defaults']=[{'when':{'cips_baseline':'MODERN_EXTENDED'},'value':2}]
            if key in {'cips_timeout_multiplier','cips_network_delay_percent'}:
                native['conditional_defaults']=[{'when':{'cips_device_profile':'GUARDLOGIX_SAFETY_IO'},'value':2 if key=='cips_timeout_multiplier' else 200}]
            fields.append(native)
    if technology_id == 'cc_link_ie':
        source=REVIEW_RATE_PROPOSALS['cc_link_ie']
        removed={'qos_priority','sync_method','reserved_bandwidth_percent','retransmission_enabled','retransmission_rate',
                 'retry_limit','retransmission_delay_ms','gateway_maximum_throughput','gateway_input_buffer',
                 'gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s'}
        fields=[item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key']=='bitrate':
                item['conditional_defaults']=[{'when':{'ccie_variant':variant},'value':speed} for variant,speed in
                                             (('CONTROLLER',1000000000),('FIELD',1000000000),('FIELD_BASIC',100000000),('TSN',100000000))]
                item['description']='Actual selected variant link rate. Basic100M mandatory/1G optional; Controller/Field1G; TSN100M/1G. Unknown variant has no universal rate proposal.'
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.pop('max',None)
                item.update(integer=True,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',source=source['source'],source_revision=source['source_revision'],
                            description='Actual logical communication bytes. Variant cyclic areas/transient message limits are separate from Ethernet MTU and frame fragmentation.')
            if item['key']=='queue_policy':
                item.update(options=['FIFO','PRIORITY','CUSTOM'],description='Explicit abstract host queue. Native token/polling/TSN gating require actual variant and schedule evidence.')
            if item['key'] in {'queue_size','seed','max_events'}:
                item['integer']=True
        for key,label,unit,options,minimum,maximum,default in (
            ('ccie_variant','Actual CC-Link IE variant',None,['CONTROLLER','FIELD','FIELD_BASIC','TSN'],None,None,None),
            ('ccie_access','Actual variant medium access',None,['TOKEN_PASSING','UDP_MANAGER_POLLING','TIME_SHARING','TIME_MANAGED_POLLING'],None,None,None),
            ('ccie_phy','Actual per-link PHY/media',None,['100BASE_TX','1000BASE_T','1000BASE_SX','SI_POF','SI_HPCF'],None,None,None),
            ('ccie_topology','Actual network topology',None,['LINE','STAR','LINE_STAR','RING'],None,None,None),
            ('ccie_link_length_m','Actual longest station-to-station link','m',None,0,None,None),
            ('ccie_nodes','Actual total manager/device nodes',None,None,1,65535,None),
            ('ccie_device_count','Actual remote device modules',None,None,0,None,None),
            ('ccie_device_slots','Actual total device occupation slots',None,None,0,None,None),
            ('ccie_station_number','Actual device start station',None,None,1,None,None),
            ('ccie_occupied_stations','Actual Basic device occupation slots',None,None,1,4,None),
            ('ccie_station_rx_bits','Actual station remote inputs','bit',None,0,None,None),
            ('ccie_station_ry_bits','Actual station remote outputs','bit',None,0,None,None),
            ('ccie_station_rwr_words','Actual station input registers','16bit words',None,0,None,None),
            ('ccie_station_rww_words','Actual station output registers','16bit words',None,0,None,None),
            ('ccie_network_rx_bits','Actual network remote input area','bit',None,0,None,None),
            ('ccie_network_ry_bits','Actual network remote output area','bit',None,0,None,None),
            ('ccie_network_rwr_words','Actual network input registers','16bit words',None,0,None,None),
            ('ccie_network_rww_words','Actual network output registers','16bit words',None,0,None,None),
            ('ccie_station_cyclic_bytes','Actual station total cyclic area','Byte',None,0,None,None),
            ('ccie_transient_bytes','Actual complete transient message data','Byte',None,0,None,None),
            ('ccie_transient_limit_bytes','Actual supported transient data limit','Byte',None,0,None,None),
            ('ccie_duplex','Actual link duplex',None,['FULL'],None,None,None),
            ('ccie_controller_mode','Actual Controller area mode',None,['NORMAL','EXTENDED'],None,None,None),
            ('ccie_controller_network_extended','Actual MELSEC extended network area support',None,None,None,None,None),
            ('ccie_controller_networks','Actual Controller connected networks',None,None,1,239,None),
            ('ccie_controller_groups','Actual Controller groups',None,None,1,32,None),
            ('ccie_controller_lb_bits','Actual Controller station link bits','bit',None,0,None,None),
            ('ccie_controller_lw_words','Actual Controller station link words','16bit words',None,0,None,None),
            ('ccie_controller_lx_bits','Actual Controller station input points','bit',None,0,8192,None),
            ('ccie_controller_ly_bits','Actual Controller station output points','bit',None,0,8192,None),
            ('ccie_controller_network_lb_bits','Actual Controller network link bits','bit',None,0,65536,None),
            ('ccie_controller_network_lw_words','Actual Controller network link words','16bit words',None,0,262144,None),
            ('ccie_basic_optional_1g_supported','Actual Basic optional1G support',None,None,None,None,None),
            ('ccie_basic_cyclic_udp_port','Basic cyclic UDP destination port',None,None,61450,61450,None),
            ('ccie_basic_discovery_udp_port','Basic device discovery UDP port',None,None,61451,61451,None),
            ('ccie_basic_group','Actual Basic group',None,None,1,4,None),
            ('ccie_basic_controller','Actual Basic manager implementation',None,['DEVICE_SPECIFIC','MELSEC_IQ_R','MELSEC_IQ_L','MELSEC_IQ_F','MELSEC_Q','MELSEC_L'],None,None,None),
            ('ccie_basic_tool_revision','Actual Basic configuration tool baseline',None,['GX_WORKS_CURRENT','GX_WORKS_LEGACY'],None,None,None),
            ('ccie_basic_timeout_ms','Actual Basic disconnection timeout','ms',None,10,65535,None),
            ('ccie_basic_disconnect_count','Actual Basic consecutive disconnection count',None,None,1,None,None),
            ('ccie_tsn_class','Actual device/switch TSN class',None,['A','B'],None,None,None),
            ('ccie_tsn_version','Actual TSN protocol version',None,['1.0','2.0'],None,None,None),
            ('ccie_tsn_sync','Actual TSN clock method',None,['IEEE_802_1AS','IEEE_1588'],None,None,None),
            ('ccie_tsn_cycle_us','Actual configured TSN cycle','us',None,0.001,None,None),
            ('ccie_tsn_gate_period_us','Actual gate control period','us',None,0.001,None,None),
            ('ccie_tsn_guard_us','Actual gate guard interval','us',None,0,None,None),
            ('ccie_master_request_bound_ms','Actual manager request processing bound','ms',None,0,None,None),
            ('ccie_device_response_bound_ms','Actual slowest device response bound','ms',None,0,None,None),
            ('ccie_cpu_scan_bound_ms','Actual CPU/end-processing scan bound','ms',None,0,None,None),
            ('ccie_link_scan_bound_ms','Actual complete link scan bound','ms',None,0,None,None),
        ):
            native=field(key,label,'physical' if key in {'ccie_phy','ccie_topology','ccie_link_length_m'} else 'communication','network',
                         field_type='select' if options else 'boolean' if key in {'ccie_basic_optional_1g_supported','ccie_controller_network_extended'} else 'number',
                         unit=unit,minimum=minimum,maximum=maximum,options=options,default=default,simulation_relevant=False,
                         description='Variant-specific CC-Link IE configuration. Actual node areas, device support, PHY, addresses and schedules need confirmation. No token/Basic/TSN capability is inferred from industry.')
            native.update(required=key=='ccie_variant',integer=native['type']=='number' and unit not in {'m','ms','us'},
                          parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',source=source['source'],source_revision=source['source_revision'])
            defaults={'ccie_access':[('CONTROLLER','TOKEN_PASSING'),('FIELD','TOKEN_PASSING'),('FIELD_BASIC','UDP_MANAGER_POLLING')],
                      'ccie_duplex':[(variant,'FULL') for variant in ('CONTROLLER','FIELD','FIELD_BASIC','TSN')],
                      'ccie_transient_limit_bytes':[('CONTROLLER',960),('FIELD',2048),('FIELD_BASIC',2048)],
                      'ccie_basic_cyclic_udp_port':[('FIELD_BASIC',61450)],'ccie_basic_discovery_udp_port':[('FIELD_BASIC',61451)]}
            if key in defaults:
                native['conditional_defaults']=[{'when':{'ccie_variant':variant},'value':value} for variant,value in defaults[key]]
            if key in {'ccie_basic_timeout_ms','ccie_basic_disconnect_count'}:
                native['source']='https://www.mitsubishielectric.com/dl/fa/document/manual/plc/sh081684eng/sh081684engj.pdf'
                native['source_revision']='SH081684ENG-J October2024 section8.1'
                native['conditional_defaults']=[{'when':{'ccie_variant':'FIELD_BASIC','ccie_basic_controller':controller,
                                                        'ccie_basic_tool_revision':tool},'value':(100 if tool=='GX_WORKS_CURRENT' else 500) if key=='ccie_basic_timeout_ms' else 3}
                                               for controller in ('MELSEC_IQ_R','MELSEC_IQ_L','MELSEC_IQ_F','MELSEC_Q','MELSEC_L')
                                               for tool in ('GX_WORKS_CURRENT','GX_WORKS_LEGACY')]
            fields.append(native)
    if technology_id == 'cc_link':
        source = REVIEW_RATE_PROPOSALS['cc_link']
        removed = {'qos_priority','sync_method','reserved_bandwidth_percent','retransmission_enabled','retransmission_rate',
                   'retry_limit','retransmission_delay_ms','gateway_maximum_throughput','gateway_input_buffer',
                   'gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s'}
        fields = [item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.pop('max',None)
                item.update(integer=True,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',source=source['source'],
                            source_revision=source['source_revision'],description='Actual logical application bytes; cyclic bit/word areas and HDLC wire frames are distinct. No universal256byte frame cap.')
            if item['key']=='queue_policy':
                item.update(options=['FIFO','PRIORITY','CUSTOM'],description='Abstract host queue; not CC-Link broadcast polling order or an Ethernet TAS/CBS schedule.')
            if item['key'] in {'queue_size','seed','max_events'}:
                item['integer']=True
        for key,label,unit,options,minimum,maximum,default in (
            ('ccl_protocol_version','CC-Link protocol baseline',None,['1.10','2.00'],None,None,'1.10'),
            ('ccl_cable_version','Dedicated cable baseline',None,['1.10','1.00_STANDARD'],None,None,'1.10'),
            ('ccl_topology','Physical topology baseline',None,['LINE','T_BRANCH'],None,None,'LINE'),
            ('ccl_station_role','Actual station role',None,['MANAGER','LOCAL','INTELLIGENT_DEVICE','REMOTE_IO','REMOTE_DEVICE','STANDBY_MANAGER'],None,None,None),
            ('ccl_station_number','Actual start station number',None,None,0,64,None),
            ('ccl_occupied_stations','Actual occupied station slots',None,None,1,4,None),
            ('ccl_total_occupied_stations','Actual total occupied slots',None,None,0,64,None),
            ('ccl_device_count','Actual device station count',None,None,0,64,None),
            ('ccl_extended_cycle','Extended cyclic multiplier',None,None,1,8,1),
            ('ccl_rx_bits','Actual remote input area','bit',None,0,896,None),
            ('ccl_ry_bits','Actual remote output area','bit',None,0,896,None),
            ('ccl_rwr_words','Actual device-to-manager register area','16bit words',None,0,128,None),
            ('ccl_rww_words','Actual manager-to-device register area','16bit words',None,0,128,None),
            ('ccl_total_rx_bits','Actual network remote input area','bit',None,0,8192,None),
            ('ccl_total_ry_bits','Actual network remote output area','bit',None,0,8192,None),
            ('ccl_total_rwr_words','Actual network input register area','16bit words',None,0,2048,None),
            ('ccl_total_rww_words','Actual network output register area','16bit words',None,0,2048,None),
            ('ccl_main_length_m','Actual trunk length','m',None,0,None,None),
            ('ccl_consecutive_ten_span_m','Actual minimum cable span across every ten consecutive stations','m',None,0,None,None),
            ('ccl_remote_spacing_m','Actual shortest remote-to-remote segment','m',None,0,None,None),
            ('ccl_special_spacing_m','Actual shortest manager/local/intelligent adjacent segment','m',None,0,None,None),
            ('ccl_special_nodes_present','Actual local/intelligent nodes present',None,None,None,None,None),
            ('ccl_branch_length_m','Actual longest branch','m',None,0,None,None),
            ('ccl_branch_total_m','Actual sum of branch lengths','m',None,0,None,None),
            ('ccl_branch_devices','Actual maximum devices per branch',None,None,0,None,None),
            ('ccl_termination_ohms','Cable1.10 line-end terminator proposal','Ohm',None,110,110,110),
            ('ccl_encoding','Registered encoding',None,['NRZI'],None,None,'NRZI'),
            ('ccl_crc_bits','Registered HDLC CRC width','bit',None,16,16,16),
            ('ccl_controller_profile','Actual manager implementation',None,['DEVICE_SPECIFIC','QJ61BT11N'],None,None,None),
            ('ccl_link_scan_bound_ms','Actual measured or device-derived link scan bound','ms',None,0,None,None),
            ('ccl_q_mode','Actual QJ61BT11N operating mode',None,['VER1_REMOTE_NET','VER2_REMOTE_NET','ADDITIONAL','REMOTE_IO_NET','OFFLINE'],None,None,None),
            ('ccl_q_retry_count','QJ61BT11N link scan retry count',None,None,1,7,None),
            ('ccl_q_reconnection_count','QJ61BT11N returning stations per scan',None,None,1,10,None),
            ('ccl_q_scan_mode','QJ61BT11N link/CPU scan mode',None,['ASYNCHRONOUS','SYNCHRONOUS'],None,None,None),
            ('ccl_q_plc_down','QJ61BT11N CPU fault data-link behavior',None,['STOP','CONTINUE'],None,None,None),
            ('ccl_q_fault_input','QJ61BT11N faulty-station input policy',None,['CLEAR','HOLD'],None,None,None),
            ('ccl_q_cpu_stop_output','QJ61BT11N CPU STOP output policy',None,['REFRESH','CLEAR'],None,None,None),
            ('ccl_q_block_assurance','QJ61BT11N block data assurance',None,None,None,None,None),
            ('ccl_q_transient_send_words','Actual QJ61BT11N transient send buffer','16bit words',None,0,4096,None),
            ('ccl_q_transient_receive_words','Actual QJ61BT11N transient receive buffer','16bit words',None,0,4096,None),
            ('ccl_q_transient_auto_words','Actual QJ61BT11N auto-update buffer','16bit words',None,0,4096,None),
        ):
            vendor = key.startswith('ccl_q_')
            native = field(key,label,'physical' if unit in {'m','Ohm'} or key in {'ccl_cable_version','ccl_topology'} else 'communication','network',
                           field_type='select' if options else 'boolean' if key in {'ccl_special_nodes_present','ccl_q_block_assurance'} else 'number',
                           unit=unit,minimum=minimum,maximum=maximum,options=options,default=default,simulation_relevant=False,
                           description='CC-Link dedicated EIA485 broadcast polling profile. Actual station/device configuration requires confirmation; bit/word areas are not one HDLC packet.' if not vendor else
                           'QJ61BT11N-only configuration. Vendor factory proposals apply only to this explicitly chosen manager, not all CC-Link devices. Actual response/scan bounds remain unconfirmed.')
            native.update(required=False,integer=native['type']=='number' and unit not in {'m','ms','Ohm'},
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN',source=source['source'] if not vendor else
                          'https://www.mitsubishielectric.com/dl/fa/document/manual/plc/sh080394e/sh080394es.pdf',
                          source_revision=source['source_revision'] if not vendor else 'SH(NA)-080394E-S June2024 sections7.2/7.3.2')
            if key=='ccl_extended_cycle':
                native['allowed_values']=[1,2,4,8]
            vendor_defaults={'ccl_q_retry_count':3,'ccl_q_reconnection_count':1,'ccl_q_scan_mode':'ASYNCHRONOUS',
                             'ccl_q_plc_down':'STOP','ccl_q_fault_input':'CLEAR','ccl_q_cpu_stop_output':'REFRESH',
                             'ccl_q_block_assurance':False,'ccl_q_transient_send_words':64,'ccl_q_transient_receive_words':64,'ccl_q_transient_auto_words':128}
            if key in vendor_defaults:
                native['conditional_defaults']=[{'when':{'ccl_controller_profile':'QJ61BT11N'},'value':vendor_defaults[key]}]
            if key in {'ccl_q_transient_send_words','ccl_q_transient_receive_words'}:
                native['allowed_values']=[0,*range(64,4097)]
            if key=='ccl_q_transient_auto_words':
                native['allowed_values']=[0,*range(128,4097)]
            fields.append(native)
    if technology_id == 'ccp':
        source=REVIEW_RATE_PROPOSALS['ccp']
        can_profile=_spec(*next(row for row in ROWS if row[0]=='can'))
        fields=_parameter_form_schema('can',can_profile,can_profile,_parameter_defaults_review('can',can_profile))
        for item in fields:
            if item['key']=='can_frame_type':
                item['options']=['DATA']
            if item['key']=='payload_bytes':
                item.update(min=1,description='Actual complete CCP CAN Data field, including native header. CRO/CRM/event eight bytes; DAQ one PID plus up to seven data bytes. Total memory transfer is not one frame.')
        for key,label,unit,options,minimum,maximum,default in (
            ('ccp_revision','Registered CCP revision',None,['2.1'],None,None,'2.1'),
            ('ccp_object','Actual CCP object type',None,['CRO','CRM','EVENT','DAQ'],None,None,None),
            ('ccp_station_address','Actual logical station address',None,None,0,65535,None),
            ('ccp_station_byte_order','CONNECT station address encoding',None,['LITTLE_ENDIAN'],None,None,'LITTLE_ENDIAN'),
            ('ccp_byte_order','Actual ECU data byte order',None,['LITTLE_ENDIAN','BIG_ENDIAN'],None,None,None),
            ('ccp_cro_id','Actual command receive CAN ID',None,None,0,536870911,None),
            ('ccp_cro_id_format','Actual command receive ID format',None,['BASE_11','EXTENDED_29'],None,None,None),
            ('ccp_dto_id','Actual response/status CAN ID',None,None,0,536870911,None),
            ('ccp_dto_id_format','Actual response/status ID format',None,['BASE_11','EXTENDED_29'],None,None,None),
            ('ccp_daq_can_id','Actual selected DAQ CAN ID',None,None,0,536870911,None),
            ('ccp_daq_can_id_format','Actual DAQ CAN ID format',None,['BASE_11','EXTENDED_29'],None,None,None),
            ('ccp_command','Actual CRO command octet',None,None,0,255,None),
            ('ccp_command_counter','Actual CRO command counter',None,None,0,255,None),
            ('ccp_response_counter','Observed CRM counter',None,None,0,255,None),
            ('ccp_pid','Actual DTO packet ID',None,None,0,255,None),
            ('ccp_error_code','Actual CRM/event error octet',None,None,0,255,None),
            ('ccp_data_bytes','Actual native parameter/data bytes','Byte',None,0,7,None),
            ('ccp_memory_address','Actual memory transfer address',None,None,0,4294967295,None),
            ('ccp_address_extension','Actual memory address extension',None,None,0,255,None),
            ('ccp_transfer_bytes','Actual complete memory transfer size','Byte',None,0,None,None),
            ('ccp_response_timeout_ms','Actual host command response timeout','ms',None,0,None,None),
            ('ccp_response_bound_ms','Actual device response bound','ms',None,0,None,None),
            ('ccp_daq_list','Actual configured DAQ list',None,None,0,None,None),
            ('ccp_daq_odt','Actual ODT within selected DAQ list',None,None,0,None,None),
            ('ccp_daq_prescaler','Actual event prescaler',None,None,1,None,None),
            ('ccp_event_period_ms','Actual periodic event interval','ms',None,0,None,None),
            ('ccp_event_mode','Actual DAQ trigger mode',None,['PERIODIC','EVENT_DRIVEN'],None,None,None),
            ('ccp_connected','Observed logical connection',None,None,None,None,None),
            ('ccp_resource_protection','Actual device resource protection',None,['UNPROTECTED','SEED_KEY','DEVICE_SPECIFIC'],None,None,None),
            ('ccp_a2l_source','Actual A2L/configuration reference',None,None,None,None,None),
        ):
            native=field(key,label,'communication','network' if key in {'ccp_revision','ccp_station_address','ccp_byte_order','ccp_cro_id','ccp_dto_id','ccp_connected','ccp_resource_protection','ccp_a2l_source'} else 'message',
                         field_type='text' if key=='ccp_a2l_source' else 'boolean' if key=='ccp_connected' else 'select' if options else 'number',
                         unit=unit,minimum=minimum,maximum=maximum,options=options,default=default,simulation_relevant=False,
                         description='CCP2.1 native configuration. Actual device/A2L identities, memory layout, command capabilities and observed session/DAQ timing remain unconfirmed. No XCP/CAN FD fields or automatic calibration operation.')
            native.update(required=False,integer=native['type']=='number' and unit!='ms',
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN',source=source['source'],source_revision=source['source_revision'])
            if key in {'ccp_station_address','ccp_station_byte_order'}:
                native['source']='https://www.csselectronics.com/pages/ccp-xcp-on-can-bus-calibration-protocol'
                native['source_revision']='CSS Electronics authored CCP packet trace / CONNECT station address description, accessed2026-10-01'
            fields.append(native)
    if technology_id == 'canopen':
        source = REVIEW_RATE_PROPOSALS['canopen']
        can_profile = _spec(*next(row for row in ROWS if row[0]=='can'))
        fields = _parameter_form_schema('can',can_profile,can_profile,_parameter_defaults_review('can',can_profile))
        for item in fields:
            if item['key']=='bitrate':
                item.update(default=10000,min=10000,max=1000000,allowed_values=list(CANOPEN_CC_RATES),
                            parameter_origin='TRANSPORT_PROFILE',default_status='PROPOSED',source=source['source'],source_revision=source['source_revision'],
                            description='Lowest defined CANopen CC rate10k proposed. Actual participating devices must all support selected rate; no universal CAN default or CAN FD phase rate.')
            if item['key']=='sample_point_percent':
                item.update(default=87.5,default_status='PROPOSED',parameter_origin='TRANSPORT_PROFILE',
                            source=source['source'],source_revision=source['source_revision'],
                            description='CANopen CC recommends closest achievable sample point to87.5%. Actual clock/segments determine realizable value, which is preserved and checked.')
        for key,label,unit,options,minimum,maximum,default,source_kind in (
            ('co_baseline','Registered CANopen bearer',None,['CANOPEN_CC_CIA301'],None,None,'CANOPEN_CC_CIA301','lower'),
            ('co_node_id','Actual configured node ID',None,None,1,127,None,'nmt'),
            ('co_service','Actual communication object service',None,['PDO','SDO','NMT','SYNC','TIME','EMCY','HEARTBEAT','BOOTUP'],None,None,None,'lower'),
            ('co_nmt_state','Observed NMT state',None,['INITIALIZING','PRE_OPERATIONAL','OPERATIONAL','STOPPED'],None,None,None,'nmt'),
            ('co_nmt_command','Actual NMT command octet',None,None,1,130,None,'nmt'),
            ('co_nmt_target','Actual NMT target; zero broadcast',None,None,0,127,None,'nmt'),
            ('co_pdo_transmission_type','Actual PDO transmission type',None,None,0,255,None,'pdo'),
            ('co_pdo_inhibit_100us','Actual TPDO inhibit time','100us',None,0,65535,None,'pdo'),
            ('co_pdo_event_timer_ms','Actual PDO event/monitoring timer','ms',None,0,65535,None,'pdo'),
            ('co_pdo_sync_start','Actual TPDO SYNC counter start',None,None,0,240,None,'pdo'),
            ('co_pdo_mapped_bits','Actual sum of mapped PDO lengths','bit',None,0,64,None,'pdo'),
            ('co_pdo_mapping','Actual device mapping capability',None,['STATIC','VARIABLE','DYNAMIC'],None,None,None,'pdo_cia'),
            ('co_pdo_valid','Actual communication object valid state',None,None,None,None,None,'pdo'),
            ('co_rtr_allowed','Actual legacy PDO RTR permission',None,None,None,None,None,'pdo_cia'),
            ('co_od_index','Actual object dictionary index',None,None,0,65535,None,'sdo'),
            ('co_od_subindex','Actual object dictionary subindex',None,None,0,255,None,'sdo'),
            ('co_sdo_variant','Actual SDO transfer variant',None,['EXPEDITED','SEGMENTED','BLOCK'],None,None,None,'sdo'),
            ('co_sdo_application_bytes','Actual total SDO object length','Byte',None,0,None,None,'sdo'),
            ('co_sdo_block_segments','Actual SDO block size','segments',None,1,127,None,'sdo'),
            ('co_sdo_response_bound_ms','Actual measured/datasheet response bound','ms',None,0,None,None,'sdo'),
            ('co_sync_can_id','SYNC default connection identifier',None,None,0,536870911,128,'sync'),
            ('co_sync_frame_format','SYNC predefined frame format',None,['BASE_11','EXTENDED_29'],None,None,'BASE_11','sync'),
            ('co_sync_producer','Actual SYNC producer state',None,None,None,None,None,'sync'),
            ('co_sync_period_us','Actual OD1006 SYNC period','us',None,0,4294967295,None,'sync'),
            ('co_sync_window_us','Actual OD1007 synchronous window','us',None,0,4294967295,None,'sync'),
            ('co_sync_counter_overflow','OD1019 counter baseline',None,None,0,240,0,'sync'),
            ('co_error_control','Recommended error control baseline',None,['HEARTBEAT','NODE_GUARDING'],None,None,'HEARTBEAT','error'),
            ('co_heartbeat_producer_ms','Actual OD1017 producer heartbeat','ms',None,0,65535,None,'heartbeat'),
            ('co_heartbeat_consumer_ms','Actual OD1016 consumer timeout','ms',None,0,65535,None,'heartbeat'),
            ('co_accumulated_stub_length_m','Actual sum of unterminated stubs','m',None,0,None,None,'lower'),
        ):
            sources = {'lower':source['source'],'nmt':'https://canopennode.github.io/CANopenNode/group__CO__NMT__Heartbeat.html',
                       'pdo':'https://github.com/CANopenNode/CANopenDemo/blob/master/tutorial/PDO.md',
                       'pdo_cia':'https://www.can-cia.org/can-knowledge/pdo-protocol',
                       'sdo':'https://www.can-cia.org/can-knowledge/sdo-protocol',
                       'sync':'https://canopennode.github.io/CANopenNode/group__CO__SYNC.html',
                       'error':'https://www.can-cia.org/can-knowledge/error-control-protocols',
                       'heartbeat':'https://canopennode.github.io/CANopenNode/group__CO__HBconsumer.html'}
            boolean = key in {'co_pdo_valid','co_rtr_allowed','co_sync_producer'}
            native = field(key,label,'communication','network' if source_kind in {'lower','sync','error','heartbeat','nmt'} else 'message',
                           field_type='boolean' if boolean else 'select' if options else 'number',
                           unit=unit,minimum=minimum,maximum=maximum,options=options,default=default,simulation_relevant=False,
                           description='CANopen CC native configuration. Actual object dictionary, node/COB assignments and service scheduling require confirmation. Zero timers disable a service; no universal device timer is proposed.')
            native.update(required=False,integer=native['type']=='number' and unit not in {'m','ms'} or key in {'co_pdo_event_timer_ms','co_heartbeat_producer_ms','co_heartbeat_consumer_ms'},
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN',source=sources[source_kind],
                          source_revision='CiA CANopen CC/CANopenNode primary documentation accessed2026-10-01')
            if key=='co_nmt_command':
                native['allowed_values']=[1,2,128,129,130]
            if key=='co_pdo_transmission_type':
                native['allowed_values']=[*range(241),252,253,254,255]
                native['description'] += '252/253 are legacy RTR services, unsupported by CANopenNode; explicit device support is needed.'
                native['source']='https://infosys.beckhoff.com/content/1033/cx805x_hw/2037701515.html'
                native['source_revision']='Beckhoff official CANopen PDO transmission type table accessed2026-10-01; standard vs device support distinguished'
            if key=='co_sync_counter_overflow':
                native['allowed_values']=[0,*range(2,241)]
            fields.append(native)
    if technology_id == 'can_xl':
        source = REVIEW_RATE_PROPOSALS['can_xl']
        controller_source = 'https://www.bosch-semiconductors.com/media/ip_modules/pdf_2/x_can/xcan_user_manual_v390.pdf'
        can_profile = _spec(*next(row for row in ROWS if row[0]=='can'))
        lower_fields = _parameter_form_schema('can',can_profile,can_profile,_parameter_defaults_review('can',can_profile))
        fields = rate_fields + [item for item in lower_fields if item['key'] not in {
            'bitrate','can_dlc','can_phy','can_frame_format','can_frame_type','can_identifier',
            'can_error_state','can_tx_error_count','can_rx_error_count','retransmission_enabled'}]
        for item in fields:
            if item['key']=='payload_bytes':
                item.update(min=1,max=2048,description='Actual XL Data field1..2048 bytes in single-byte steps. Encoded XL DLC is length minus one; not CAN FD padding.',
                            source=source['source'],source_revision=source['source_revision'])
            if item['key']=='can_controller_profile':
                item.update(options=['DEVICE_SPECIFIC','X_CAN_3_9'])
            if item['key'] in {'can_clock_hz','can_prescaler','can_tseg1_tq','can_tseg2_tq','can_sjw_tq','sample_point_percent','can_controller_profile'}:
                item.update(source=controller_source,source_revision='X_CAN3.9 2024-02-28 section1.5.4.2.4',
                            description='Actual nominal CAN XL timing. X_CAN3.9 register limits apply only with explicit controller; functional values are register values plus one. No M_CAN defaults or limits.')
        for key,label,unit,options,minimum,maximum,default,section in (
            ('can_xl_revision','Registered XL wire baseline',None,['ISO_2024'],None,None,'ISO_2024','CiA XL / ISO11898-1:2024'),
            ('can_xl_priority_id','Actual arbitration priority identifier',None,None,0,2047,None,'CiA XL priority/addressing'),
            ('can_xl_acceptance_field','Actual acceptance/addressing field',None,None,0,4294967295,None,'CiA XL priority/addressing'),
            ('can_xl_sdt','Actual service data unit type',None,None,0,255,None,'CiA611-1 SDT'),
            ('can_xl_vcid','Actual virtual CAN network identifier',None,None,0,255,None,'CiA XL VCID'),
            ('can_xl_dlc','Actual encoded XL data length',None,None,0,2047,None,'CiA XL Data length / X_CAN1.4.5.6'),
            ('can_xl_rrs','Actual remote request substitution bit',None,None,None,None,None,'X_CAN1.4.5.6'),
            ('can_xl_sec','Actual simple extended content bit',None,None,None,None,None,'CiA XL optional extensions'),
            ('can_xl_pcrc_bits','Preface CRC sequence length','bit',None,13,13,13,'CiA XL CRC'),
            ('can_xl_fcrc_bits','Frame CRC sequence length','bit',None,32,32,32,'CiA XL CRC'),
            ('can_xl_phy','Actual physical transceiver family',None,['CAN_HS','CAN_SIC','CAN_SIC_XL'],None,None,None,'CiA XL PMA'),
            ('can_xl_mode_switching','Actual transceiver mode switching',None,None,None,None,None,'CiA XL PMA / X_CAN1.5.4.2.4.1'),
            ('can_xl_transceiver_max_bps','Actual transceiver data capability','bit/s',None,1,None,None,'CiA XL PMA'),
            ('can_xl_data_prescaler','Actual XL data functional prescaler',None,None,1,None,None,'X_CAN1.5.4.2.4.2'),
            ('can_xl_data_tseg1_tq','Actual XL data TSEG1 functional value','TQ',None,1,None,None,'X_CAN1.5.4.2.4.4'),
            ('can_xl_data_tseg2_tq','Actual XL data TSEG2 functional value','TQ',None,1,None,None,'X_CAN1.5.4.2.4.4'),
            ('can_xl_data_sjw_tq','Actual XL data resynchronization jump','TQ',None,1,None,None,'X_CAN1.5.4.2.4.4'),
            ('can_xl_data_sample_point_percent','Actual XL data sample point','%',None,0.000001,99.999999,None,'X_CAN1.5.4.2.4.4'),
            ('can_xl_xtdco_clocks','Actual X_CAN XL secondary sample offset','clock',None,0,255,None,'X_CAN1.5.4.2.4.4'),
            ('can_xl_tdc_enabled','Actual transmitter delay compensation',None,None,None,None,None,'X_CAN1.5.4.2.4.1'),
            ('can_xl_pwm_short_clocks','Actual X_CAN PWM short phase','clock',None,1,64,None,'X_CAN1.6.4.1'),
            ('can_xl_pwm_long_clocks','Actual X_CAN PWM long phase','clock',None,1,64,None,'X_CAN1.6.4.1'),
            ('can_xl_pwm_offset_clocks','Actual X_CAN raw PWM offset','clock',None,0,63,None,'X_CAN1.6.4.1'),
            ('can_xl_error_signalling_disabled','Actual X_CAN error flag disable',None,None,None,None,None,'X_CAN1.5.4.2.4.1'),
        ):
            boolean = key in {'can_xl_rrs','can_xl_sec','can_xl_mode_switching','can_xl_tdc_enabled','can_xl_error_signalling_disabled'}
            native = field(key,label,'physical' if unit in {'TQ','%','clock','bit/s'} or key in {'can_xl_phy','can_xl_mode_switching','can_xl_tdc_enabled'} else 'communication',
                           'message' if key in {'can_xl_priority_id','can_xl_acceptance_field','can_xl_sdt','can_xl_vcid','can_xl_dlc','can_xl_rrs','can_xl_sec'} else 'network',
                           field_type='boolean' if boolean else 'select' if options else 'number',
                           unit=unit,minimum=minimum,maximum=maximum,default=default,options=options,simulation_relevant=False,
                           description='CAN XL configuration; addressing and arbitration are separate. Actual installed timing/PHY remains unknown. Extensions and executable capacity require separate evidence.')
            native.update(required=False,integer=native['type']=='number' and unit!='%',
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN',
                          source=controller_source if section.startswith('X_CAN') else source['source'],source_revision=section+'; accessed2026-10-01')
            fields.append(native)
    if technology_id == 'can_fd':
        source = REVIEW_RATE_PROPOSALS['can_fd']
        can_profile = _spec(*next(row for row in ROWS if row[0]=='can'))
        lower_fields = _parameter_form_schema('can',can_profile,can_profile,_parameter_defaults_review('can',can_profile))
        fields = rate_fields + [item for item in lower_fields if item['key'] not in {'bitrate','can_dlc','can_phy'}]
        for item in fields:
            if item['key']=='payload_bytes':
                item.update(max=64,description='Actual logical payload0..64 bytes. CAN FD wire data length follows DLC and may include padding; no default full64-byte payload.',
                            source=source['source'],source_revision=source['source_revision'])
            if item['key']=='can_frame_type':
                item.update(options=['DATA'],description='CAN FD has no remote frame. Classic CAN compatibility is a separately identified CC frame.')
            if item['key']=='data_bitrate':
                item.update(required=False,required_when={'can_fd_brs':True})
        for key,label,unit,options,minimum,maximum,default,section in (
            ('can_fd_revision','CAN FD wire baseline',None,['ISO_2015_2024'],None,None,'ISO_2015_2024','3.1.4'),
            ('can_fd_brs','Actual bit rate switching',None,None,None,None,False,'3.1.4'),
            ('can_fd_dlc','Actual encoded CAN FD DLC',None,None,0,15,None,'3.1.4 Table54'),
            ('can_fd_wire_data_bytes','Actual DLC data length including padding','Byte',None,0,64,None,'3.1.4 Table54'),
            ('can_fd_error_passive','Actual ESI error-passive indicator',None,None,None,None,None,'3.1.4'),
            ('can_fd_crc_bits','Required CRC sequence length','bit',None,17,21,None,'ISO CRC17/21'),
            ('can_fd_transceiver_max_bps','Actual transceiver data-rate capability','bit/s',None,1,None,None,'CiA PMA options'),
            ('can_fd_data_prescaler','Actual data prescaler functional value',None,None,1,None,None,'2.3.4'),
            ('can_fd_data_tseg1_tq','Actual data TSEG1 functional value','TQ',None,1,None,None,'2.3.4'),
            ('can_fd_data_tseg2_tq','Actual data TSEG2 functional value','TQ',None,1,None,None,'2.3.4'),
            ('can_fd_data_sjw_tq','Actual data resynchronization jump','TQ',None,1,None,None,'2.3.4'),
            ('can_fd_data_sample_point_percent','Actual data sample point','%',None,0.000001,99.999999,None,'2.3.4'),
            ('can_fd_tdc_enabled','Actual transmitter delay compensation',None,None,None,None,None,'3.1.4.1'),
            ('can_fd_mcan_delay_mtq','Actual M_CAN measured transmitter delay','mtq',None,0,127,None,'3.1.4.1'),
            ('can_fd_mcan_tdco_mtq','Actual M_CAN secondary sample offset','mtq',None,0,127,None,'2.3.15'),
            ('can_fd_mcan_tdcf_mtq','Actual M_CAN delay filter window','mtq',None,0,127,None,'2.3.15'),
            ('can_fd_mcan_ssp_mtq','Actual M_CAN secondary sample position','mtq',None,0,127,None,'3.1.4.1'),
        ):
            native = field(key,label,'physical','message' if key in {'can_fd_brs','can_fd_dlc','can_fd_wire_data_bytes','can_fd_error_passive','can_fd_crc_bits'} else 'network',
                           field_type='boolean' if key in {'can_fd_brs','can_fd_error_passive','can_fd_tdc_enabled'} else 'select' if options else 'number',
                           unit=unit,minimum=minimum,maximum=maximum,options=options,default=default,
                           simulation_relevant=key in {'can_fd_brs','can_fd_dlc','can_fd_wire_data_bytes'},
                           description='ISO CAN FD configuration. Actual hardware, wire data and timing remain unconfirmed; M_CAN fields apply to explicitly selected M_CAN3.3.1 only.')
            native.update(required=False,integer=native['type']=='number' and unit!='%',
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN',
                          source='https://www.bosch-semiconductors.com/media/ip_modules/pdf_2/m_can/mcan_users_manual_v331.pdf',
                          source_revision='Bosch M_CAN3.3.1 2023-03-11 section'+section)
            if key=='can_fd_wire_data_bytes':
                native['allowed_values']=list(CAN_FD_DATA_LENGTHS)
            if key=='can_fd_crc_bits':
                native['allowed_values']=[17,21]
            if key=='can_fd_transceiver_max_bps':
                native.update(source=source['source'],source_revision=source['source_revision'])
            fields.append(native)
    if technology_id == 'can_aerospace':
        source = REVIEW_RATE_PROPOSALS['can_aerospace']
        # Use the already reviewed explicit lower layer; native aerospace rules remain separate.
        can_profile = _spec(*next(row for row in ROWS if row[0] == 'can'))
        fields = _parameter_form_schema('can',can_profile,can_profile,_parameter_defaults_review('can',can_profile))
        for item in fields:
            if item['key'] == 'payload_bytes':
                item.update(min=0,max=4,description='Actual CANaerospace message body excludes its four-byte standard header; NODATA zero is valid. Not raw CAN Data field length.',
                            source=source['source'],source_revision=source['source_revision'])
            if item['key'] == 'can_dlc':
                item.update(min=4,description='CAN Data field contains four header bytes plus 0..4 CANaerospace body bytes.')
            if item['key'] == 'can_frame_type':
                item.update(options=['DATA'])
        for key,label,unit,options,minimum,maximum,default,section in (
            ('canas_revision','Registered CANaerospace revision',None,['1.7'],None,None,'1.7','1'),
            ('canas_header_type','Registered standard header code',None,None,0,0,0,'3.1 / 4.1'),
            ('canas_byte_order','Standard message encoding',None,['BIG_ENDIAN'],None,None,'BIG_ENDIAN','3'),
            ('canas_message_class','Actual message class',None,['EED','NSH','UDH','NOD','UDL','DSD','NSL'],None,None,None,'2.1'),
            ('canas_base_identifier','Actual identifier before redundancy offset',None,None,0,2031,None,'2.1 / 7.1'),
            ('canas_redundancy_level','Redundancy level baseline',None,None,0,8191,0,'7.1'),
            ('canas_node_id','Actual sender or addressed node; zero broadcast',None,None,0,255,None,'3.1'),
            ('canas_data_type','Actual datatype code',None,None,0,255,None,'2.2'),
            ('canas_service_code_octet','Actual encoded service code octet',None,None,0,255,None,'3.1'),
            ('canas_message_code','Actual message/sequence code octet',None,None,0,255,None,'3.1'),
            ('canas_nod_service_code_used','Actual NOD service code use',None,None,None,None,None,'3.1'),
            ('canas_service_role','Actual node service direction',None,['REQUEST','RESPONSE'],None,None,None,'4'),
            ('canas_service_channel','Actual node service channel',None,None,0,115,None,'4'),
            ('canas_ids_supported','Actual mandatory IDS support on channel zero',None,None,None,None,None,'4'),
            ('canas_response_deadline_ms','Node service response deadline','ms',None,100,100,100,'4'),
            ('canas_response_bound_ms','Actual node service response bound','ms',None,0,100,None,'4'),
            ('canas_distribution_id','Identifier distribution baseline',None,None,0,255,0,'4.1'),
        ):
            native = field(key,label,'communication','message' if key in {'canas_message_class','canas_base_identifier','canas_node_id','canas_data_type','canas_service_code_octet','canas_message_code','canas_nod_service_code_used','canas_service_role','canas_service_channel'} else 'network',
                           field_type='boolean' if key in {'canas_nod_service_code_used','canas_ids_supported'} else 'select' if options else 'number',
                           unit=unit,options=options,minimum=minimum,maximum=maximum,default=default,
                           simulation_relevant=False,description='CANaerospace1.7 standard header baseline. Actual node/message/service state remains unconfirmed; custom headers/distributions require explicit extensions.')
            native.update(required=False,integer=not options and native['type']=='number' and unit is None,
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN',source=source['source'],
                          source_revision='CANaerospace1.7 2006-01-12 section'+section)
            if key == 'canas_ids_supported':
                native['allowed_values'] = [True]
            if key == 'canas_distribution_id':
                native['allowed_values'] = [0,*range(100,256)]
            if key == 'canas_service_channel':
                native['allowed_values'] = [*range(36),*range(100,116)]
            fields.append(native)
    if technology_id == 'can':
        source = REVIEW_RATE_PROPOSALS['can']
        removed = {'qos_priority','sync_method','reserved_bandwidth_percent','retransmission_rate',
                   'retry_limit','retransmission_delay_ms','gateway_maximum_throughput','gateway_input_buffer',
                   'gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s'}
        fields = [item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key'] == 'payload_bytes':
                item.pop('default', None)
                item.update(min=0,max=8,integer=True,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',
                            source=source['source'],source_revision=source['source_revision'],
                            description='Actual CAN CC Data field. Remote request has zero data bytes regardless of its requested DLC; DATA DLC equals actual byte length.')
            if item['key'] == 'retransmission_enabled':
                item.update(default=True,allowed_values=[True],parameter_origin='TRANSPORT_PROFILE',
                            source=source['source'],source_revision=source['source_revision'],
                            description='CAN automatic retransmission baseline. One-shot/listen-only hardware modes require separate device behavior; no finite retry count is implied.')
            if item['key'] == 'queue_policy':
                item.update(options=['FIFO','PRIORITY','CUSTOM'],description='Abstract host queue. Wire arbitration uses the CAN identifier; host FIFO can introduce priority inversion.')
            if item['key'] in {'queue_size','seed','max_events'}:
                item['integer'] = True
        for key,label,unit,options,minimum,maximum,default,section in (
            ('can_phy','Registered CAN CC physical baseline',None,['HIGH_SPEED'],None,None,'HIGH_SPEED','CiA ISO 11898-2 high-speed PMA'),
            ('can_frame_format','Actual CAN identifier format',None,['BASE_11','EXTENDED_29'],None,None,None,'Part B 3.1 / 3.2.1'),
            ('can_frame_type','CAN frame baseline',None,['DATA','REMOTE'],None,None,'DATA','Part B 3.2'),
            ('can_identifier','Actual identifier / wire priority',None,None,0,536870911,None,'Part B 3.2.1'),
            ('can_dlc','Actual data length / requested remote length','Byte',None,0,8,None,'Part B 3.2.1 / 3.2.2'),
            ('can_controller_profile','Actual bit timing controller profile',None,['DEVICE_SPECIFIC','M_CAN_3_3_1'],None,None,None,'Part B 10 / Bosch M_CAN 3.3.1 2.3.8'),
            ('can_clock_hz','Actual CAN clock','Hz',None,1,None,None,'Part B 10'),
            ('can_prescaler','Actual prescaler (functional value)',None,None,1,None,None,'Part B 10 / Bosch M_CAN 3.3.1 2.3.8'),
            ('can_tseg1_tq','Actual Prop_Seg + Phase_Seg1 (functional value)','TQ',None,1,None,None,'Part B 10 / Bosch M_CAN 3.3.1 2.3.8'),
            ('can_tseg2_tq','Actual Phase_Seg2 (functional value)','TQ',None,1,None,None,'Part B 10 / Bosch M_CAN 3.3.1 2.3.8'),
            ('can_sjw_tq','Actual resynchronization jump width','TQ',None,1,None,None,'Part B 10 / Bosch M_CAN 3.3.1 2.3.8'),
            ('sample_point_percent','Actual nominal sample point','%',None,0.000001,99.999999,None,'Part B 10'),
            ('can_error_state','Observed controller error state',None,['ERROR_ACTIVE','ERROR_PASSIVE','BUS_OFF'],None,None,None,'Part B 8'),
            ('can_tx_error_count','Observed transmit error counter',None,None,0,None,None,'Part B 8'),
            ('can_rx_error_count','Observed receive error counter',None,None,0,None,None,'Part B 8'),
            ('can_ack_receiver_count','Actual receivers capable of acknowledgement','nodes',None,0,None,None,'Part B 2 / 3.2.1'),
            ('can_termination_ohms','HS line termination recommendation','Ohm',None,1,None,120,'CiA CAN HS transmission'),
            ('can_bus_length_m','Actual main line length','m',None,0,None,None,'CiA CAN HS transmission'),
            ('can_stub_length_m','Actual longest stub','m',None,0,None,None,'CiA CAN network design'),
        ):
            native = field(key,label,'physical' if unit in {'Hz','TQ','%','Ohm','m'} or key in {'can_phy','can_controller_profile'} else 'communication',
                           'message' if key in {'can_identifier','can_frame_format','can_frame_type','can_dlc'} else 'network',
                           field_type='select' if options else 'number',unit=unit,minimum=minimum,maximum=maximum,options=options,default=default,
                           simulation_relevant=key in {'can_frame_format','can_frame_type'},description='Declared CAN CC configuration, not proof of actual controller state, hardware conformance or bounded retransmissions.')
            native.update(required=False,integer=not options and unit not in {'%','Ohm','m'},
                          parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                          default_status='PROPOSED' if default is not None else 'UNKNOWN',
                          source=source['source'],source_revision=section + '; reviewed 2026-10-01')
            if 'M_CAN' in section:
                native['source'] = 'https://www.bosch-semiconductors.com/media/ip_modules/pdf_2/m_can/mcan_users_manual_v331.pdf'
            elif section.startswith('CiA'):
                native['source'] = 'https://www.can-cia.org/can-knowledge/can-hs-transmission'
            fields.append(native)
    if technology_id == 'bluetooth_le':
        ll_source = 'https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-62/out/en/low-energy-controller/link-layer-specification.html'
        removed = {'qos_priority','sync_method','reserved_bandwidth_percent','retransmission_enabled',
                   'retransmission_rate','retry_limit','retransmission_delay_ms','gateway_maximum_throughput',
                   'gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s'}
        fields = [item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key'] == 'bitrate':
                item['description'] = 'Selected transmit PHY effective data rate. LE Coded packets use separately coded sections; this is not sufficient for packet airtime. LE 1M is mandatory, 2M/Coded optional.'
            if item['key'] == 'payload_bytes':
                item.pop('default',None)
                item.update(min=0,max=251,integer=True,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',
                            source=ll_source,source_revision='Bluetooth Core 6.2 Vol 6 Part B 2.4.1 / 4.5.10',
                            description='Actual LL Data PDU Payload field, not a GATT value or ATT MTU. Includes L2CAP fragments, excludes LL header/CRC/MIC. Empty data PDU is valid. Actual negotiated lengths/times limit it.')
            if item['key'] == 'queue_policy':
                item.update(options=['FIFO','PRIORITY','CUSTOM'],description='Abstract NIS host queue; not a proven central radio schedule or TAS/CBS.')
            if item['key'] in {'queue_size','seed','max_events'}:
                item['integer'] = True
        for key,label,unit,options,minimum,maximum,default,section in (
            ('ble_bearer','Registered BLE transport baseline',None,['ACL_DATA'],None,None,'ACL_DATA','4.5'),
            ('ble_tx_phy','Selected transmit PHY',None,['LE_1M','LE_2M','LE_CODED_S2','LE_CODED_S8'],None,None,'LE_1M','4.5.1 / 5.1.10'),
            ('ble_rx_phy','Actual independently selected receive PHY',None,['LE_1M','LE_2M','LE_CODED_S2','LE_CODED_S8'],None,None,None,'4.5.1 / 5.1.10'),
            ('ble_2m_supported','Actual local optional 2M capability',None,None,None,None,None,'4.6'),
            ('ble_coded_supported','Actual local optional coded PHY capability',None,None,None,None,None,'4.6'),
            ('ble_remote_2m_supported','Actual remote optional 2M capability',None,None,None,None,None,'4.6'),
            ('ble_remote_coded_supported','Actual remote optional coded PHY capability',None,None,None,None,None,'4.6'),
            ('ble_dle_supported','Actual data length extension support',None,None,None,None,None,'4.6.7 / 4.5.10'),
            ('ble_short_intervals_supported','Actual 6.2 shorter interval support',None,None,None,None,None,'4.5.1 / 5.1.32'),
            ('ble_subrating_supported','Actual subrating support',None,None,None,None,None,'4.5.1'),
            ('ble_interval_set','Connection interval baseline',None,['BASELINE','ROUNDED','EXTENDED'],None,None,'BASELINE','4.5.1'),
            ('ble_connection_interval_us','Connection interval','us',None,375,4000000,None,'4.5.1'),
            ('ble_peripheral_latency','Skipped subrated events','events',None,0,499,None,'4.5.1'),
            ('ble_subrate_factor','Connection subrate factor',None,None,1,500,1,'4.5.1 new connection'),
            ('ble_continuation_number','Continuation events',None,None,0,499,0,'4.5.1 new connection'),
            ('ble_supervision_timeout_ms','Connection supervision timeout','ms',None,100,32000,None,'4.5.2'),
            ('ble_ifs_us','ACL inter-frame space baseline','us',None,0,None,150,'4.1.1 / 5.1.30'),
            ('ble_encryption_active','Actual connection encryption state',None,None,None,None,None,'2.4 / 5.1.3'),
            ('ble_local_max_tx_octets','Local connection maximum TX payload','Byte',None,27,251,None,'4.5.10'),
            ('ble_local_max_rx_octets','Local connection maximum RX payload','Byte',None,27,251,None,'4.5.10'),
            ('ble_remote_max_tx_octets','Actual remote maximum TX payload','Byte',None,27,251,None,'4.5.10'),
            ('ble_remote_max_rx_octets','Actual remote maximum RX payload','Byte',None,27,251,None,'4.5.10'),
            ('ble_supported_max_tx_octets','Local hardware TX capability','Byte',None,27,251,None,'4.5.10'),
            ('ble_supported_max_rx_octets','Local hardware RX capability','Byte',None,27,251,None,'4.5.10'),
            ('ble_local_max_tx_time_us','Local connection maximum TX time','us',None,328,17040,None,'4.5.10 table 4.8'),
            ('ble_local_max_rx_time_us','Local connection maximum RX time','us',None,328,17040,None,'4.5.10 table 4.8'),
            ('ble_remote_max_tx_time_us','Actual remote maximum TX time','us',None,328,17040,None,'4.5.10 table 4.8'),
            ('ble_remote_max_rx_time_us','Actual remote maximum RX time','us',None,328,17040,None,'4.5.10 table 4.8'),
            ('ble_supported_max_tx_time_us','Local hardware TX timing capability','us',None,328,17040,None,'4.5.10 table 4.8'),
            ('ble_supported_max_rx_time_us','Local hardware RX timing capability','us',None,328,17040,None,'4.5.10 table 4.8'),
            ('ble_used_channel_count','Actual used data channels','channels',None,2,37,None,'1.4.1 / 4.5.8.1'),
            ('ble_central_node_id','Actual central node identity',None,None,None,None,None,'4.5'),
            ('ble_peripheral_node_id','Actual peripheral node identity',None,None,None,None,None,'4.5'),
            ('ble_cte_supported','Actual connection CTE support',None,None,None,None,None,'4.5.10 table 4.8'),
        ):
            is_boolean = key.endswith('_supported') or key == 'ble_encryption_active'
            item = field(key,label,'physical','network',unit=unit,options=options,
                         field_type='select' if options else 'boolean' if is_boolean else 'text' if key.endswith('_node_id') else 'number',
                         minimum=minimum,maximum=maximum,default=default,simulation_relevant=False)
            item.update(required=False,parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                        default_status='PROPOSED' if default is not None else 'UNKNOWN',source=ll_source,
                        source_revision='Bluetooth Core 6.2 Vol 6 Part B '+section+'; accessed 2026-10-01',
                        description='ACL baseline or actual peer configuration; optional advertising/isochronous/channel-sounding bearers require their own reviewed profile. A saved value does not execute the radio schedule.')
            if item['type'] == 'number':
                item['integer'] = True
            if key == 'ble_connection_interval_us':
                item.update(multiple_of=125,conditional_defaults=[
                    {'when':{'ble_interval_set':'BASELINE'},'value':7500},
                    {'when':{'ble_interval_set':'ROUNDED'},'value':1250},
                    {'when':{'ble_interval_set':'EXTENDED'},'value':375}],
                    description='Lowest selected interval-set proposal, not a universal controller default. Baseline >=7500 us / 1250-us grid; optional 6.2 extended >=375 us / 125-us grid. Must satisfy peer capability and supervision bound.')
            if key == 'ble_supervision_timeout_ms':
                item.update(multiple_of=10,description='Actual 100..32000 ms in 10-ms steps; strictly greater than 2 * interval * subrate * (latency+1). No independent 100-ms default valid for every connection.')
            if key == 'ble_ifs_us':
                item['description'] = 'Standard initial 150 us. Core 6.0+ frame-space update may negotiate per-direction/per-PHY values; no actual update or bidirectional equality is inferred.'
            fields.append(item)
    if technology_id in {'adc', 'dac'}:
        # Analogue input/output is not a framed transport. Device timing and
        # sample width/rate do not borrow CAN payload or network load defaults.
        applicable = {'cycle_ms', 'minimum_cycle_time_ms', 'deadline_ms', 'timeout_ms',
                      'maximum_latency_ms', 'jitter_ms', 'freshness_ms',
                      'source_processing_delay_ms', 'target_processing_delay_ms',
                      'propagation_delay_ms', 'required_reliability', 'traffic_class',
                      'clock_offset_ms', 'clock_drift_ppm', 'sync_precision_ms',
                      'sync_interval_ms', 'maximum_sync_error_ms',
                      'duration_s', 'seed', 'max_events', 'dropout_probability'}
        fields = [item for item in fields if item['key'] in applicable]
        for item in fields:
            item['description'] = f'NIS-Szenario bzw. Projektanforderung; kein {technology_id.upper()}-Standard oder bestätigter Gerätewert.'
            if item['key'] in {'seed', 'max_events'}:
                item['integer'] = True
    if technology_id == 'arinc429':
        source = REVIEW_RATE_PROPOSALS['arinc429']
        removed = {'qos_priority', 'sync_method', 'reserved_bandwidth_percent',
                   'retransmission_enabled', 'retransmission_rate', 'retry_limit', 'retransmission_delay_ms',
                   'gateway_maximum_throughput', 'gateway_input_buffer', 'gateway_output_buffer',
                   'gateway_maximum_routes', 'gateway_maximum_messages_s', 'packet_loss_probability',
                   'duplicate_probability', 'reordering_probability'}
        fields = [item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key'] == 'payload_bytes':
                item.update(label='Encoded ARINC word', min=4, max=4, default=4, integer=True,
                            parameter_origin='TRANSPORT_PROFILE', source=source['source'],
                            source_revision='AIM v2.2 July 2019, page 11, Word Formats',
                            description='Complete 32-bit word including label and parity, not four bytes of application data. Actual encoding requires the ICD.')
            if item['key'] == 'queue_policy':
                item.update(options=['FIFO', 'ROUND_ROBIN', 'CUSTOM'],
                            description='Abstract NIS transmitter queue; an actual periodic word schedule is separate evidence.')
            if item['key'] in {'queue_size', 'seed', 'max_events'}:
                item['integer'] = True
        for key, label, scope, unit, options, minimum, maximum, default, page in (
            ('arinc429_speed_mode', 'ARINC channel speed mode', 'network', None, ['LOW', 'HIGH'], None, None, 'LOW', 9),
            ('arinc429_gap_bit_times', 'Minimum NULL gap between words', 'network', 'bit times', None, 4, None, 4, 8),
            ('arinc429_direction', 'Channel direction', 'network', None, ['SIMPLEX'], None, None, 'SIMPLEX', 7),
            ('arinc429_parity', 'Word parity', 'message', None, ['ODD'], None, None, 'ODD', 11),
            ('arinc429_label', 'ICD label (decimal value of 8-bit label)', 'message', None, None, 0, 255, None, 11),
            ('arinc429_sdi', 'Optional Source/Destination Identifier', 'message', None, None, 0, 3, None, 15),
            ('arinc429_ssm', 'Sign/Status Matrix code', 'message', None, None, 0, 3, None, 12),
            ('arinc429_data_bits', 'Data bits after label and parity', 'message', 'bit', None, 0, 23, None, 11),
            ('arinc429_receiver_count', 'Actual sinks on this channel', 'network', 'receivers', None, 1, 20, None, 7),
            ('arinc429_transmitter_node_id', 'Single transmitting node', 'network', None, None, None, None, None, 7),
            ('arinc429_rise_time_us', 'Actual transmitter rise time', 'network', 'us', None, 1, 15, None, 10),
            ('arinc429_fall_time_us', 'Actual transmitter fall time', 'network', 'us', None, 1, 15, None, 10),
        ):
            item = field(key, label, 'physical', scope, unit=unit,
                         field_type='select' if options else 'text' if key.endswith('node_id') else 'number',
                         options=options, minimum=minimum, maximum=maximum, default=default,
                         simulation_relevant=False)
            item.update(required=False, parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                        default_status='PROPOSED' if default is not None else 'UNKNOWN',
                        source=source['source'], source_revision=f'AIM v2.2 July 2019, page {page}',
                        description='Source-backed word/channel constraint; actual device, ICD and schedule evidence remains separate.')
            if key in {'arinc429_label', 'arinc429_sdi', 'arinc429_ssm', 'arinc429_data_bits', 'arinc429_receiver_count'}:
                item['integer'] = True
            fields.append(item)
    if technology_id == 'amqp':
        transport_source = 'https://docs.oasis-open.org/amqp/core/v1.0/os/amqp-core-transport-v1.0-os.html'
        messaging_source = 'https://docs.oasis-open.org/amqp/core/v1.0/os/amqp-core-messaging-v1.0-os.html'
        removed = {'qos_priority', 'sync_method', 'reserved_bandwidth_percent',
                   'retransmission_enabled', 'retransmission_rate', 'retry_limit', 'retransmission_delay_ms',
                   'gateway_maximum_throughput', 'gateway_input_buffer', 'gateway_output_buffer',
                   'gateway_maximum_routes', 'gateway_maximum_messages_s', 'vlan_id', 'rate_limit_bit_s'}
        fields = [item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key'] == 'payload_bytes':
                item.pop('max', None)
                item.update(integer=True, description='Application body; AMQP messages can span transfer frames. Negotiated frame size is not a message-body limit.')
            if item['key'] == 'bitrate':
                item.update(source='https://www.ieee802.org/3/archive.html',
                            source_revision='Explicit Ethernet stack; IEEE 802.3 baseline link modes; RFC 894 10 Mbit/s baseline',
                            description='Underlying declared Ethernet link rate; not an AMQP bitrate. Confirm the actual transport independently.')
            if item['key'] == 'mtu_bytes':
                item.update(min=68, max=1500, default=1500, integer=True, parameter_origin='TRANSPORT_PROFILE',
                            source='https://www.rfc-editor.org/rfc/rfc894', source_revision='RFC 894 April 1984, Frame Format',
                            constraint_source='https://www.rfc-editor.org/rfc/rfc791.html', constraint_source_revision='RFC 791 September 1981, section 3.2, minimum forwardable IPv4 datagram',
                            description='Baseline IP-over-Ethernet MTU; not AMQP frame size or message limit. Other physical MTUs need a distinct verified link profile.')
            if item['key'] == 'duplex':
                item.pop('default', None)
                item.update(parameter_origin='DEVICE_CONFIGURATION', default_status='UNKNOWN',
                            source='https://www.ieee802.org/3/archive.html', source_revision='IEEE 802.3 PHY selection',
                            description='Actual physical Ethernet port mode; AMQP full-duplex byte stream does not set the Ethernet PHY mode.')
            if item['key'] == 'queue_policy':
                item.update(options=['FIFO', 'PRIORITY', 'CUSTOM'], description='Abstract NIS queue; AMQP settlement and link credit are separate. No native TAS/CBS scheduler is assumed.')
            if item['key'] in {'queue_size', 'seed', 'max_events'}:
                item['integer'] = True
        definitions = (
            ('amqp_version', 'AMQP version', None, ['1.0'], None, None, '1.0', '2.8.19', False),
            ('amqp_max_frame_size_bytes', 'AMQP receive maximum frame size', 'Byte', None, 512, 4294967295, 4294967295, '2.7.1', False),
            ('amqp_channel_max', 'AMQP highest channel number', None, None, 0, 65535, 65535, '2.7.1', False),
            ('amqp_idle_timeout_ms', 'AMQP idle timeout (0 = unset)', 'ms', None, 0, 4294967295, 0, '2.7.1', False),
            ('amqp_sender_settle_mode', 'Sender settlement', None, ['UNSETTLED', 'SETTLED', 'MIXED'], None, None, 'MIXED', '2.7.3; 2.8.2', False),
            ('amqp_receiver_settle_mode', 'Receiver settlement', None, ['FIRST', 'SECOND'], None, None, 'FIRST', '2.7.3; 2.8.3', False),
            ('amqp_incomplete_unsettled', 'Incomplete unsettled map', None, None, None, None, False, '2.7.3', False),
            ('amqp_link_credit', 'Actual current link credit', 'deliveries', None, 0, 4294967295, None, '2.7.4', False),
            ('amqp_message_priority', 'AMQP message priority', None, None, 0, 255, 4, '3.2.1', True),
            ('amqp_durable', 'Durable message required', None, None, None, None, False, '3.2.1', True),
            ('amqp_ttl_ms', 'AMQP message TTL (unset = no expiry)', 'ms', None, 0, 4294967295, None, '3.2.1', True),
        )
        for key, label, unit, options, minimum, maximum, default, section, messaging in definitions:
            item = field(key, label, 'reliability' if 'settle' in key or key == 'amqp_durable' else 'qos',
                         'message' if messaging else 'route' if key in {'amqp_link_credit', 'amqp_sender_settle_mode', 'amqp_receiver_settle_mode', 'amqp_incomplete_unsettled'} else 'network',
                         field_type='select' if options else 'boolean' if type(default) is bool else 'number',
                         unit=unit, minimum=minimum, maximum=maximum, options=options, default=default, simulation_relevant=False)
            item.update(required=False, integer=not options and type(default) is not bool,
                        parameter_origin='DEVICE_CONFIGURATION' if default is None else 'TRANSPORT_PROFILE',
                        default_status='PROPOSED' if default is not None else 'UNKNOWN',
                        source=messaging_source if messaging else transport_source,
                        source_revision='OASIS AMQP 1.0, 29 October 2012, section ' + section,
                        description='AMQP 1.0 field; protocol proposal is not negotiated peer capability or executable broker capacity evidence.')
            fields.append(item)
        item = field('amqp_max_message_size_bytes', 'AMQP maximum encoded message (0 = no imposed limit)',
                     'qos', 'route', field_type='text', unit='Byte', default='0', simulation_relevant=False)
        item.update(required=False, parameter_origin='TRANSPORT_PROFILE', default_status='PROPOSED',
                    source=transport_source, source_revision='OASIS AMQP 1.0 2012-10-29 section 2.7.3, ulong',
                    pattern=r'[0-9]+', integer_text_maximum=18446744073709551615,
                    description='Exact unsigned 64-bit decimal text avoids JavaScript number rounding. Bounds the entire encoded message, not only its body. Zero or unset imposes no link limit.')
        fields.append(item)
    if technology_id in {'bacnet_ip', 'bacnet_mstp', 'bacnet_sc'}:
        device_source = 'https://documentation.iconics.com/v10.98/Content/Apps/WBDT/BACnet/BACnet_Configuration_Via_Workbench.htm'
        ip_source = 'https://bacnet.org/wp-content/uploads/sites/4/2022/06/Building-Wide-Area-Networks-With-BACnet-Part-2.pdf'
        stack_source = 'https://github.com/bacnet-stack/bacnet-stack/blob/master/src/bacnet/config.h'
        removed = {'qos_priority', 'sync_method', 'reserved_bandwidth_percent',
                   'retransmission_enabled', 'retransmission_rate', 'retry_limit', 'retransmission_delay_ms',
                   'gateway_maximum_throughput', 'gateway_input_buffer', 'gateway_output_buffer',
                   'gateway_maximum_routes', 'gateway_maximum_messages_s', 'vlan_id', 'rate_limit_bit_s'}
        fields = [item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key'] == 'bitrate':
                item.update(source='https://www.ieee802.org/3/archive.html',
                            source_revision='Explicit Ethernet stack baseline; RFC 894 April 1984 10 Mbit/s',
                            description='Underlying Ethernet link rate; BACnet/IP has no independent 100 Mbit/s rate.')
                if technology_id == 'bacnet_mstp':
                    item.update(source=REVIEW_RATE_PROPOSALS['bacnet_mstp']['source'],
                                source_revision=REVIEW_RATE_PROPOSALS['bacnet_mstp']['source_revision'],
                                description='Selected common MS/TP baud rate; all actual station PHYs must support it. 9600 is the lowest mandatory baseline, not a capacity proof.')
                if technology_id == 'bacnet_sc':
                    item['description'] = 'Underlying explicitly declared Ethernet link rate; BACnet/SC over TCP/TLS/WebSocket has no independent PHY bitrate.'
            if item['key'] == 'payload_bytes':
                item.pop('default', None)
                item.update(label='Encoded BACnet APDU', min=1, max=1476, integer=True,
                            parameter_origin='DEVICE_CONFIGURATION', default_status='UNKNOWN',
                            source=stack_source, source_revision='BACnet-stack config.h MAX_APDU, accessed 2026-10-01',
                            description='Encoded APDU, including its header, not object values alone. Actual peer maximum and segmentation must be known; NPDU/BVLC/UDP/IP framing and fragmentation are separate.')
                if technology_id == 'bacnet_mstp':
                    item['description'] = 'Encoded APDU: classic maximum 480, extended maximum 1476 only with actual extended-frame support. Data field including NPDU is 501 / 1497; not an Ethernet or UDP payload.'
                if technology_id == 'bacnet_sc':
                    item.update(max=61325, source='https://bacnet.org/wp-content/uploads/sites/4/2022/08/Add-135-2016bj.pdf',
                                source_revision='Addendum 135-2016bj 2019-11-18, table 6-1 and clause 6.5.1',
                                description='Encoded APDU; registered SC routing baseline NPDU <=61327, at least two NPCI bytes. Actual routed NPCI, BVLC options, peer APDU/NPDU limits and TCP/TLS/WebSocket framing remain separate. Not a 65535-byte APDU guarantee.')
            if item['key'] == 'mtu_bytes':
                item.update(min=68, max=1500, default=1500, integer=True, parameter_origin='TRANSPORT_PROFILE',
                            source='https://www.rfc-editor.org/rfc/rfc894', source_revision='RFC 894 April 1984, Frame Format',
                            constraint_source='https://www.rfc-editor.org/rfc/rfc791.html', constraint_source_revision='RFC 791 September 1981, section 3.2',
                            description='IPv4-over-Ethernet baseline MTU; not the accepted APDU size.')
                if technology_id == 'bacnet_sc':
                    item['description'] = 'Declared IPv4-over-Ethernet baseline link MTU. TCP segmentation permits SC messages spanning packets; not the BVLC, NPDU or APDU maximum. IPv6 requires its own explicit link profile.'
            if item['key'] == 'duplex':
                item.pop('default', None)
                item.update(parameter_origin='DEVICE_CONFIGURATION', default_status='UNKNOWN',
                            source='https://www.ieee802.org/3/archive.html', source_revision='IEEE 802.3 actual PHY mode',
                            description='Actual Ethernet PHY mode; BACnet/IP does not select full duplex.')
                if technology_id == 'bacnet_sc':
                    item['description'] = 'Actual declared Ethernet PHY mode; bidirectional WebSocket connections do not specify a full-duplex physical port.'
            if item['key'] == 'queue_policy':
                item.update(options=['FIFO', 'PRIORITY', 'CUSTOM'], description='Abstract NIS queue, not BACnet transaction state or guaranteed device processing.')
            if item['key'] in {'queue_size', 'seed', 'max_events'}:
                item['integer'] = True
        definitions = (
            ('bacnet_udp_port', 'BACnet/IP UDP port', 'network', None, None, 1, 65535, 47808, ip_source, 'Bill Swan 1999, Annex J BACnet/IP'),
            ('bacnet_device_instance', 'Assigned BACnet device instance', 'network', None, None, 0, 4194302, None, 'https://github.com/bacnet-stack/bacnet-stack/blob/master/doc/README.faq', 'BACnet-stack FAQ Q10/Q11, accessed 2026-10-01'),
            ('bacnet_max_apdu_bytes', 'Actual accepted maximum APDU', 'route', 'Byte', None, 50, 1476, None, stack_source, 'BACnet-stack config.h MAX_APDU; FAQ actual device size 256; accessed 2026-10-01'),
            ('bacnet_segmentation', 'Actual device segmentation support', 'route', None, ['BOTH', 'TRANSMIT', 'RECEIVE', 'NONE'], None, None, None, stack_source, 'Actual PICS; compile-time stack defaults are not device capabilities'),
            ('bacnet_apdu_retries', 'Confirmed-service APDU retries', 'route', 'retries', None, 0, None, 3, device_source, 'ICONICS v10.98, Number_Of_APDU_Retries'),
            ('bacnet_apdu_timeout_modifiable', 'Device permits APDU timeout modification', 'route', None, None, None, None, None, device_source, 'ICONICS v10.98, APDU_Timeout conditional defaults'),
            ('bacnet_apdu_timeout_ms', 'Confirmed-service APDU timeout', 'route', 'ms', None, 0, None, None, device_source, 'ICONICS v10.98, APDU_Timeout'),
            ('bacnet_segment_timeout_ms', 'APDU segment timeout', 'route', 'ms', None, 0, None, 2000, device_source, 'ICONICS v10.98, APDU_Segment_Timeout'),
            ('bacnet_broadcast_role', 'Actual BVLC broadcast role', 'network', None, ['NORMAL', 'BBMD', 'FOREIGN'], None, None, None, ip_source, 'Bill Swan 1999, Annex J broadcast management / registration'),
            ('bacnet_foreign_device_ttl_s', 'Foreign-device registration TTL (0 = deregister)', 'network', 's', None, 0, 65535, None, 'https://raw.githubusercontent.com/bacnet-stack/bacnet-stack/master/src/bacnet/datalink/bvlc.c', 'BACnet-stack J.2.6, 2-octet TTL, accessed 2026-10-01'),
        )
        for key, label, scope, unit, options, minimum, maximum, default, source, revision in definitions:
            if technology_id != 'bacnet_ip' and key in {'bacnet_udp_port', 'bacnet_broadcast_role', 'bacnet_foreign_device_ttl_s'}:
                continue
            item = field(key, label, 'reliability' if 'timeout' in key or 'retries' in key else 'physical', scope,
                         field_type='select' if options else 'boolean' if key.endswith('_modifiable') else 'number',
                         unit=unit, options=options, minimum=minimum, maximum=maximum, default=default, simulation_relevant=False)
            item.update(required=False, parameter_origin='DEVICE_CONFIGURATION',
                        default_status='PROPOSED' if default is not None else 'UNKNOWN', source=source, source_revision=revision,
                        description='Literature proposal or actual device/PICS configuration; saving does not execute BACnet or establish capacity.')
            if item['type'] == 'number':
                item['integer'] = True
            if technology_id == 'bacnet_sc' and key == 'bacnet_max_apdu_bytes':
                item.update(max=61325, source='https://bacnet.org/wp-content/uploads/sites/4/2022/08/Add-135-2016bj.pdf',
                            source_revision='Addendum 135-2016bj table 6-1, clause 20.1.2.5 (1476 or larger)',
                            description='Actual accepted APDU size from device/PICS. SC can support more than 1476; registration uses the 61327-byte routed NPDU baseline minus minimum NPCI. No device size is assumed.')
            if key == 'bacnet_apdu_timeout_ms':
                item.update(conditional_defaults=[
                    {'when': {'bacnet_apdu_timeout_modifiable': True}, 'value': 3000},
                    {'when': {'bacnet_apdu_timeout_modifiable': False}, 'value': 60000}],
                    description='Literature default: 3000 ms if modifiable, otherwise 60000 ms. Device property remains unknown until this condition is known. Must be nonzero when retries are nonzero.')
            if key == 'bacnet_segment_timeout_ms':
                item['description'] = 'Literature proposal 2000 ms; applicable when segmentation is supported, not an application deadline. Actual device/PICS support is separate.'
            fields.append(item)
    if technology_id == 'bacnet_sc':
        source = 'https://bacnet.org/wp-content/uploads/sites/4/2022/08/Add-135-2016bj.pdf'
        crypto_source = 'https://bacnet.org/wp-content/uploads/sites/4/2023/10/135_2020_cd_20210831.pdf'
        for key, label, unit, options, minimum, maximum, default, section in (
            ('sc_connection_type', 'Connection purpose', None, ['HUB', 'DIRECT'], None, None, 'HUB', 'YY.1.1 / YY.1.6'),
            ('sc_websocket_subprotocol', 'WebSocket subprotocol', None, ['hub.bsc.bacnet.org', 'dc.bsc.bacnet.org'], None, None, None, 'YY.7.1'),
            ('sc_primary_hub_uri', 'Actual primary hub WSS URI', None, None, None, None, None, 'YY.1.5.1 / YY.5'),
            ('sc_failover_hub_uri', 'Optional failover hub WSS URI', None, None, None, None, None, 'YY.1.6 / YY.5'),
            ('sc_direct_peer_uri', 'Actual direct peer WSS URI', None, None, None, None, None, 'YY.4.1'),
            ('sc_vmac_kind', 'Virtual address origin', None, ['EUI_48', 'RANDOM_48'], None, None, None, 'H.7.X'),
            ('sc_vmac', 'Actual node VMAC (12 hex digits)', None, None, None, None, None, 'YY.1.5.2 / H.7.X'),
            ('sc_device_uuid', 'Persistent device UUID', None, None, None, None, None, 'YY.1.5.3'),
            ('sc_accept_direct_connections', 'Actual direct connection acceptance capability', None, None, None, None, None, 'YY.1.1.3 / YY.2.8'),
            ('sc_peer_max_bvlc_bytes', 'Actual peer maximum BVLC message', 'Byte', None, 1, 65535, None, 'YY.2.10 / YY.2.11'),
            ('sc_peer_max_npdu_bytes', 'Actual peer maximum NPDU', 'Byte', None, 1, 61327, None, 'Table 6-1 / YY.2.10 / YY.2.11'),
            ('sc_npdu_bytes', 'Actual encoded NPDU including APDU', 'Byte', None, 3, 61327, None, 'Table 6-1 / 6.5.1'),
            ('sc_npci_header_bytes', 'Actual NPCI octets for this APDU path', 'Byte', None, 2, 21, None, '6.5.1 / Table 6-2'),
            ('sc_bvlc_base_header_bytes', 'Actual BVLC header before options', 'Byte', ['4', '10', '16'], None, None, None, 'YY.2.1'),
            ('sc_destination_options_bytes', 'Actual encoded destination options', 'Byte', None, 0, 65535, None, 'YY.2.3'),
            ('sc_data_options_bytes', 'Actual encoded data options', 'Byte', None, 0, 65535, None, 'YY.2.3 / 6.6'),
            ('sc_reconnect_timeout_modifiable', 'Minimum reconnect timeout configurable', None, None, None, None, None, 'YY.6.1'),
            ('sc_min_reconnect_s', 'Minimum reconnect interval', 's', None, 2, 600, None, 'YY.6.1'),
            ('sc_max_reconnect_s', 'Actual maximum reconnect backoff', 's', None, 2, 600, None, 'YY.6.1'),
            ('sc_connect_wait_s', 'Connect wait timeout', 's', None, 5, None, 10, 'YY.6.2 (2020 errata terminology)'),
            ('sc_disconnect_wait_s', 'Actual disconnect wait timeout', 's', None, 0, None, None, 'YY.6.2 local matter'),
            ('sc_heartbeat_timeout_modifiable', 'Heartbeat timeout configurable', None, None, None, None, None, 'YY.6.3'),
            ('sc_heartbeat_s', 'Initiating peer heartbeat interval', 's', None, 3, None, None, 'YY.6.3'),
            ('sc_accept_heartbeat_s', 'Actual accepting peer inactivity limit', 's', None, 0, None, None, 'YY.6.3 / YY.7.5.4 local matter'),
            ('sc_tls_version', 'Baseline TLS version', None, ['1.3'], None, None, '1.3', 'YY.7.4'),
            ('sc_mutual_tls_required', 'Mutual TLS authentication required', None, [True], None, None, True, 'YY.7.4'),
            ('sc_cipher_suite', 'Required-to-implement TLS cipher suite', None, ['TLS_AES_128_GCM_SHA256'], None, None, 'TLS_AES_128_GCM_SHA256', 'AB.7.4'),
            ('sc_signature_algorithm', 'Required-to-implement signature algorithm', None, ['ecdsa_secp256r1_sha256'], None, None, 'ecdsa_secp256r1_sha256', 'AB.7.4'),
            ('sc_key_exchange_group', 'Required-to-implement key exchange group', None, ['secp256r1'], None, None, 'secp256r1', 'AB.7.4'),
            ('sc_operational_certificate_ref', 'Actual operational certificate reference', None, None, None, None, None, 'YY.7.4.1'),
            ('sc_ca_store_ref', 'Actual trusted site CA store reference', None, None, None, None, None, 'YY.7.4.1'),
        ):
            is_boolean = key.endswith('_modifiable') or key in {'sc_accept_direct_connections', 'sc_mutual_tls_required'}
            text = key.endswith('_uri') or key.endswith('_ref') or key in {'sc_vmac', 'sc_device_uuid'}
            item = field(key, label, 'reliability' if 'timeout' in key or '_s' == key[-2:] else 'physical',
                         'message' if key in {'sc_npdu_bytes', 'sc_npci_header_bytes', 'sc_bvlc_base_header_bytes', 'sc_destination_options_bytes', 'sc_data_options_bytes'} else 'network',
                         unit=unit, field_type='boolean' if is_boolean else 'select' if options else 'text' if text else 'number',
                         options=None if is_boolean else options, minimum=minimum, maximum=maximum, default=default, simulation_relevant=False)
            item.update(required=False, parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                        default_status='PROPOSED' if default is not None else 'UNKNOWN', source=source,
                        source_revision='Addendum 135-2016bj 2019-11-18, ' + section,
                        description='SC-specific baseline or actual installation fact; not Annex J UDP/BBMD, Ethernet MTU, or executable security/capacity evidence.')
            if item['type'] == 'number' and unit == 'Byte':
                item['integer'] = True
            if key == 'sc_bvlc_base_header_bytes':
                item.update(type='number', integer=True, min=4, max=16, allowed_values=[4, 10, 16])
                item.pop('options', None)
            if key.endswith('_uri'):
                item.update(format='WSS_URI', description='Actual secure WebSocket URI. RFC 6455 default port is 443 when omitted; no universal BACnet/SC port 47808 or vendor 50050 is assumed.')
            if key == 'sc_vmac':
                item.update(pattern=r'[0-9a-fA-F][02468aAcCeE][0-9a-fA-F]{10}', forbidden_values=['000000000000'],
                            description='Actual individual EUI-48 or Random-48 address, never zero/broadcast. Random-48 low nibble of first octet is 2. Identity and collision checking are not invented.')
            if key == 'sc_device_uuid':
                item['pattern'] = r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}'
            if key == 'sc_websocket_subprotocol':
                item['conditional_defaults'] = [{'when': {'sc_connection_type': 'HUB'}, 'value': 'hub.bsc.bacnet.org'},
                                                {'when': {'sc_connection_type': 'DIRECT'}, 'value': 'dc.bsc.bacnet.org'}]
            if key in {'sc_min_reconnect_s', 'sc_heartbeat_s'}:
                condition = 'sc_reconnect_timeout_modifiable' if key == 'sc_min_reconnect_s' else 'sc_heartbeat_timeout_modifiable'
                item.update(conditional_defaults=[{'when': {condition: True}, 'value': minimum},
                                                  {'when': {condition: False}, 'value': 10 if key == 'sc_min_reconnect_s' else 30}],
                            description='Lowest documented baseline proposal depends on actual configurability; no universal default is specified. A supported configurable range is not a device upper limit.')
            if key == 'sc_connect_wait_s':
                item.update(description='Recommended standard default 10 s; configurable support must cover at least 5..300 s. 300 is not a universal upper device limit.',
                            constraint_source='https://bacnet.org/wp-content/uploads/sites/4/2022/08/135-2016bj-Errata-2020-06-v5.pdf',
                            constraint_source_revision='135-2016bj errata July 6, 2020, item 2')
            if key == 'sc_mutual_tls_required':
                item['allowed_values'] = [True]
            if key in {'sc_cipher_suite', 'sc_signature_algorithm', 'sc_key_exchange_group'}:
                item.update(source=crypto_source, source_revision='Addendum 135-2020cd 2021-08-31, AB.7.4',
                            description='Mandatory baseline capability proposal; optional additional negotiated suites/algorithms need their own PICS profile. This field does not establish a TLS session.')
            fields.append(item)
    if technology_id == 'bacnet_mstp':
        source = 'https://raw.githubusercontent.com/bacnet-stack/bacnet-stack/master/src/bacnet/datalink/mstpdef.h'
        timing_source = 'https://raw.githubusercontent.com/bacnet-stack/bacnet-stack/master/src/bacnet/datalink/mstp.h'
        for key, label, unit, options, minimum, maximum, default in (
            ('mstp_frame_format', 'MS/TP frame baseline', None, ['CLASSIC', 'EXTENDED'], None, None, 'CLASSIC'),
            ('mstp_node_role', 'Actual station role', None, ['MASTER', 'SLAVE'], None, None, None),
            ('mstp_mac_address', 'Actual station MAC (255 = broadcast, not a station)', None, None, 0, 254, None),
            ('mstp_max_master', 'Highest allowed master station address', None, None, 0, 127, 127),
            ('mstp_max_master_modifiable', 'Device permits Max_Master modification', None, None, None, None, None),
            ('mstp_max_info_frames', 'Maximum information frames per token hold', 'frames', None, 1, None, 1),
            ('mstp_max_info_frames_modifiable', 'Device permits Max_Info_Frames modification', None, None, None, None, None),
            ('mstp_serial_format', 'Serial octet framing', None, ['8N1'], None, None, '8N1'),
            ('mstp_usage_timeout_ms', 'Token usage reply timeout', 'ms', None, 20, 35, 20),
            ('mstp_reply_timeout_ms', 'Confirmed data frame reply timeout', 'ms', None, 255, 300, 255),
            ('mstp_turnaround_bit_times', 'Minimum driver turnaround', 'bit times', None, 40, None, 40),
            ('mstp_no_token_ms', 'Loss-of-token silence threshold', 'ms', None, 500, 500, 500),
            ('mstp_poll_token_count', 'Poll-for-master token interval', 'tokens', None, 50, 50, 50),
            ('mstp_token_retries', 'Token transmission retries', 'retries', None, 1, 1, 1),
            ('mstp_frame_gap_bit_times', 'Maximum inter-octet transmit gap', 'bit times', None, 0, 20, 20),
            ('mstp_postdrive_bit_times', 'Maximum transmitter postdrive', 'bit times', None, 0, 15, 15),
            ('mstp_usage_delay_ms', 'Maximum token response delay', 'ms', None, 0, 15, 15),
            ('mstp_frame_abort_bit_times', 'Receive frame abort timeout', 'bit times', None, 60, None, 60),
            ('mstp_npdu_bytes', 'Actual complete data field including NPDU', 'Byte', None, 3, 1497, None),
        ):
            item = field(key, label, 'physical', 'network', unit=unit, options=options,
                         field_type='select' if options else 'boolean' if key.endswith('_modifiable') else 'number',
                         minimum=minimum, maximum=maximum, default=default, simulation_relevant=False)
            item.update(required=False, parameter_origin='DEVICE_CONFIGURATION',
                        default_status='PROPOSED' if default is not None else 'UNKNOWN', source=source,
                        source_revision='BACnet-stack MS/TP definitions, accessed 2026-10-01',
                        description='MS/TP protocol baseline or actual station configuration. Token control is separate from APDU retries. No executable schedule is registered.')
            if item['type'] == 'number':
                item['integer'] = True
            if key in {'mstp_usage_timeout_ms', 'mstp_reply_timeout_ms', 'mstp_turnaround_bit_times', 'mstp_frame_abort_bit_times'}:
                item.update(source=timing_source, source_revision='BACnet-stack normative timer comments; accessed 2026-10-01; not implementation DEFAULT_Treply_timeout=250',
                            description='Lowest documented standard bound proposed; actual timer and baud-dependent precision must be confirmed. Not application timeout.')
            if key in {'mstp_max_master', 'mstp_max_info_frames'}:
                item.update(source='https://reference.opcfoundation.org/specs/OPC-30030/8', source_revision='OPC 30030 sections 8.4.2.1 and 8.4.2.2',
                            description='Literature default 127 / 1 respectively. Read-only properties are fixed to these values; vendor maximum frame counts are not universal normative limits.')
            if key == 'mstp_serial_format':
                item.update(source='https://infosys.beckhoff.com/content/1033/el6861/4104700811.html', source_revision='Beckhoff 2021, Interface settings')
            if key == 'mstp_npdu_bytes':
                item.update(scope='message', description='Actual encoded NPDU plus APDU; at least two NPDU header bytes, routed headers may be longer. Classic bound 501 versus extended data bound 1497. No executable encoder or capacity proof is asserted.',
                            constraint_source='https://raw.githubusercontent.com/bacnet-stack/bacnet-stack/master/src/bacnet/npdu.c',
                            constraint_source_revision='BACnet-stack npdu_encode_pdu, minimum two header bytes, accessed 2026-10-01')
            fields.append(item)
    if technology_id == 'avb':
        source = 'https://www.ieee802.org/1/files/public/docs2013/avb-mjt-et-all-AVB-for-IEEE-Smart-Home-0213.pdf'
        revision = 'IEEE AVB Task Group authors, Heterogeneous Networks for Audio and Video, February 2013, sections II-IV'
        removed = {'reserved_bandwidth_percent', 'rate_limit_bit_s',
                   'retransmission_enabled', 'retransmission_rate', 'retry_limit', 'retransmission_delay_ms',
                   'gateway_maximum_throughput', 'gateway_input_buffer', 'gateway_output_buffer',
                   'gateway_maximum_routes', 'gateway_maximum_messages_s'}
        fields = [item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key'] in {'duplex', 'queue_policy', 'sync_method'}:
                choice = {'duplex': 'FULL', 'queue_policy': 'CBS', 'sync_method': 'GPTP'}[item['key']]
                item.update(default=choice, options=[choice], parameter_origin='TRANSPORT_PROFILE',
                            source=source, source_revision=revision, simulation_relevant=False,
                            description='AVB Ethernet baseline requirement; configured hardware capability and execution remain separate evidence.')
            if item['key'] in {'qos_priority', 'vlan_id'}:
                item.pop('default', None)
                item.update(integer=True, default_status='UNKNOWN', parameter_origin='DEVICE_CONFIGURATION',
                            source=source, source_revision=revision,
                            description='Actual class/priority mapping or stream VLAN assignment required; no generic PCP-3/VLAN-0 assumption.')
                if item['key'] == 'vlan_id':
                    item['min'] = 1
            if item['key'] in {'mtu_bytes', 'payload_bytes'}:
                item.update(integer=True, max=1500, source='https://www.rfc-editor.org/rfc/rfc894',
                            source_revision='RFC 894 April 1984, Ethernet data-field baseline')
                if item['key'] == 'mtu_bytes':
                    item.update(min=46, parameter_origin='TRANSPORT_PROFILE')
                else:
                    item.update(label='Encoded Ethernet data field', description='Includes the selected stream protocol headers; media samples are not an entire MAC data field.')
            if item['key'] in {'queue_size', 'seed', 'max_events'}:
                item['integer'] = True
        for key, label, unit, options, minimum, maximum, default in (
            ('avb_sr_class', 'Stream reservation class', None, ['A', 'B'], None, None, None),
            ('avb_measurement_interval_us', 'Class measurement interval', 'us', None, 125, 250, None),
            ('avb_stream_id', 'Stream ID (16 hexadecimal digits)', None, None, None, None, None),
            ('avb_max_frame_size_bytes', 'Actual advertised TSpec MaxFrameSize', 'Byte', None, 1, 1500, None),
            ('avb_max_interval_frames', 'Actual maximum frames per class interval', 'frames', None, 1, 65535, None),
            ('avb_idle_slope_bps', 'Configured CBS idle slope', 'bit/s', None, 0, None, None),
            ('avb_send_slope_bps', 'Configured CBS send slope', 'bit/s', None, None, 0, None),
            ('avb_accumulated_latency_ns', 'Observed SRP accumulated latency bound', 'ns', None, 0, 4294967295, None),
            ('avb_as_capable', 'Actual gPTP asCapable port state', None, None, None, None, None),
            ('avb_reservation_state', 'Actual stream reservation state', None, ['UNRESERVED', 'ADVERTISED', 'RESERVED', 'FAILED'], None, None, None),
            ('avb_stream_rank', 'Stream rank', None, ['EMERGENCY', 'NON_EMERGENCY'], None, None, None),
            ('avb_destination_mac', 'Stream destination MAC', None, None, None, None, None),
        ):
            item = field(key, label, 'qos', 'route', unit=unit, options=options,
                         field_type='select' if options else 'text' if key in {'avb_stream_id', 'avb_destination_mac'} else 'boolean' if key == 'avb_as_capable' else 'number',
                         minimum=minimum, maximum=maximum, default=default, simulation_relevant=False)
            item.update(required=False, parameter_origin='DEVICE_CONFIGURATION', default_status='UNKNOWN',
                        source=source, source_revision=revision,
                        description='Actual stream/port configuration or state. No reservation or end-to-end timing guarantee follows from this field alone.')
            if key in {'avb_max_frame_size_bytes', 'avb_max_interval_frames', 'avb_measurement_interval_us', 'avb_accumulated_latency_ns'}:
                item['integer'] = True
            if key == 'avb_stream_id':
                item['pattern'] = '[0-9a-fA-F]{16}'
            if key == 'avb_destination_mac':
                # SRP destinations must be multicast or locally administered.
                item['pattern'] = '[0-9a-fA-F][1235679abABdefDEF](?::[0-9a-fA-F]{2}){5}'
            if key in {'avb_max_interval_frames', 'avb_accumulated_latency_ns', 'avb_stream_id'}:
                item.update(source='https://github.com/Avnu/OpenAvnu/blob/master/daemons/mrpd/msrp.h',
                            source_revision='OpenAvnu MSRP FirstValue structures accessed 2026-10-01; uint16 TSpec, uint32 nanosecond latency, 8-byte stream ID')
            if key in {'avb_destination_mac', 'avb_stream_rank', 'avb_max_frame_size_bytes'}:
                item.update(source='https://avnu.org/wp-content/uploads/2014/05/AVnu_Stream-Reservation-Protocol-v1.pdf',
                            source_revision='AVnu Stream Reservation Protocol Best Practices v1, 2014, Talker Advertise fields')
            fields.append(item)
        item = field('avb_highest_class_delta_bandwidth_percent', 'Highest-class deltaBandwidth', 'qos', 'network',
                     unit='%', minimum=0, maximum=100, default=75, simulation_relevant=False)
        item.update(required=False, parameter_origin='TRANSPORT_PROFILE', default_status='PROPOSED',
                    source='https://grouper.ieee.org/groups/802/1/files/public/docs2021/dg-turner-Qschedules-0621-v04.pdf',
                    source_revision='IEEE contribution 2021-06-29 v04, section 5.3.1 citing 802.1Q 34.3.1',
                    description='Recommended highest-class deltaBandwidth proposal, not actual reserved stream bandwidth or a capacity guarantee. Other class budgets and total reservations require actual port configuration.')
        fields.append(item)
    if technology_id == 'afdx':
        source = REVIEW_RATE_PROPOSALS['afdx']
        removed = {'qos_priority', 'sync_method', 'reserved_bandwidth_percent',
                   'retransmission_enabled', 'retransmission_rate', 'retry_limit', 'retransmission_delay_ms',
                   'gateway_maximum_throughput', 'gateway_input_buffer', 'gateway_output_buffer',
                   'gateway_maximum_routes', 'gateway_maximum_messages_s', 'mtu_bytes', 'vlan_id', 'rate_limit_bit_s'}
        fields = [item for item in fields if item['key'] not in removed]
        for item in fields:
            if item['key'] == 'payload_bytes':
                item.update(min=1, max=1471, integer=True,
                            description='Application payload; framing and padding differ from Ethernet MTU. Configured LMAX limits this further.')
            elif item['key'] == 'duplex':
                item.update(options=['FULL'], default='FULL', parameter_origin='TRANSPORT_PROFILE',
                            source=source['source'], source_revision='Actel AC221 March 2005, page 2, Full duplex')
            elif item['key'] == 'queue_policy':
                item.update(options=['FIFO', 'ROUND_ROBIN'], description='Abstract NIS queue; ordered VL traffic and optional sub-VL round robin do not prove an AFDX schedule.')
            if item['key'] in {'queue_size', 'seed', 'max_events'}:
                item['integer'] = True
        for key, label, unit, options, minimum, maximum, default, section in (
            ('afdx_bag_ms', 'Virtual-Link BAG', 'ms', ['1', '2', '4', '8', '16', '32', '64', '128'], None, None, '1', 'page 3, BAG'),
            ('afdx_lmax_frame_bytes', 'VL maximum MAC frame including FCS', 'Byte', None, 64, 1518, None, 'page 5, Frame Format'),
            ('afdx_jitter_bound_us', 'Configured end-system jitter bound', 'us', None, 0, 500, None, 'page 4, Jitter'),
            ('afdx_vl_id', 'Virtual-Link ID', None, None, 0, 65535, None, 'page 5, Addressing'),
            ('afdx_redundancy', 'Redundant networks for this VL', None, ['A', 'B', 'BOTH'], None, None, 'BOTH', 'page 5, Redundancy'),
        ):
            item = field(key, label, 'physical' if key == 'afdx_redundancy' else 'qos', 'route',
                         field_type='select' if options else 'number', unit=unit, options=options,
                         minimum=minimum, maximum=maximum, default=default, simulation_relevant=False)
            item.update(required=False, parameter_origin='DEVICE_CONFIGURATION',
                        default_status='PROPOSED' if default is not None else 'UNKNOWN',
                        source=source['source'], source_revision='Actel AC221 March 2005, ' + section,
                        description='Integrator configuration required. BAG 1 ms is the lowest documented choice, not a universal configured BAG. Default redundancy BOTH is documented; actual path evidence is separate.')
            if key in {'afdx_vl_id', 'afdx_lmax_frame_bytes'}:
                item['integer'] = True
            fields.append(item)
    if technology_id == '5g':
        # TS 38.306 section 4.1.2 defines a configuration-dependent capability
        # calculation, not a fixed transmission speed or a device guarantee.
        nr_source = REVIEW_RATE_PROPOSALS['5g']
        # PCP 0..7, Ethernet sync methods, fixed gateway capacities and
        # retry controls are not a 5G radio resource/HARQ configuration.
        not_radio_parameters = {'qos_priority', 'sync_method', 'reserved_bandwidth_percent',
                                'retransmission_enabled', 'retransmission_rate', 'retry_limit', 'retransmission_delay_ms',
                                'gateway_maximum_throughput', 'gateway_input_buffer', 'gateway_output_buffer',
                                'gateway_maximum_routes', 'gateway_maximum_messages_s'}
        fields = [item for item in fields if item['key'] not in not_radio_parameters]
        for item in fields:
            if item['key'] == 'payload_bytes':
                item.pop('max', None)  # 1500 is not a universal NR transport-block limit.
            if item['key'] == 'bitrate':
                item['label'] = 'Konfigurierte 5G-Datenrate'
                item['description'] = nr_source['note']
        for key, label, unit, options, minimum in (
            ('nr_band', 'NR-Band / Bandkombination', None, None, None),
            ('nr_frequency_range', 'NR-Frequenzbereich', None, ['FR1', 'FR2'], None),
            ('nr_direction', 'Übertragungsrichtung', None, ['DL', 'UL'], None),
            ('nr_channel_bandwidth_mhz', 'Kanalbandbreite je Träger', 'MHz', None, 0.001),
            ('nr_subcarrier_spacing_khz', 'Unterträgerabstand der Nutzdaten', 'kHz', ['15', '30', '60', '120'], None),
            ('nr_mimo_layers', 'Unterstützte MIMO-Layer je Träger', 'Layer', None, 1),
            ('nr_modulation_order', 'Modulationsordnung je Träger', 'bit/symbol', ['2', '4', '6', '8'], None),
            ('nr_carrier_count', 'Aggregierte Komponententräger', 'Träger', None, 1),
            ('nr_scaling_factor', 'UE-Skalierungsfaktor', None, ['1', '0.8', '0.75', '0.4'], None),
        ):
            item = field(key, label, 'physical', 'network', unit=unit,
                         field_type='select' if options else 'text' if key == 'nr_band' else 'number',
                         options=options, minimum=minimum)
            item.update(required=False, parameter_origin='DEVICE_CONFIGURATION',
                        default_status='UNKNOWN', source=nr_source['source'],
                        source_revision=nr_source['source_revision'],
                        description='Geräte-/Netzkonfiguration erforderlich; kein universeller Standardwert. Optionen sind keine bestätigten Gerätefähigkeiten.',
                        validation_relevant=True, simulation_relevant=False)
            if key in {'nr_mimo_layers', 'nr_carrier_count'}:
                item['integer'] = True
            if key == 'nr_mimo_layers':
                item['max'] = 8
            if key == 'nr_subcarrier_spacing_khz':
                item['source'] = 'https://www.etsi.org/deliver/etsi_ts/138200_138299/138211/16.02.00_60/ts_138211v160200p.pdf'
                item['source_revision'] = '3GPP TS 38.211 v16.2.0 section 4.2; TS 38.101-1 v16.13.0 / -2 v16.12.0 table 5.3.2-1; 240 kHz SS/PBCH excluded'
            fields.append(item)
    return fields



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

