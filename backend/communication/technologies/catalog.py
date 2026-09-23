"""As-built technology documentation catalog.

Registration and implementation status are deliberately independent.  The
catalog is broad; only technologies with executable core support are marked
IMPLEMENTED/PARTIAL/EXPERIMENTAL/LEGACY by ``technology_definitions``.
"""

from __future__ import annotations

from typing import Any

from .core.physical import physical_profile


TECHNOLOGY_SEMANTICS: dict[str, dict[str, Any]] = {
    "lin": {
        "rate_model": {"type": "SINGLE_BITRATE", "fields": ["bitrate_bps"], "minimum_bps": 1, "maximum_bps": 20_000, "typical_bps": [9_600, 19_200]},
        "mechanisms": {"integrity": ["PID_PARITY", "LIN_CHECKSUM"], "addressing": ["FRAME_IDENTIFIER"], "diagnostics": ["LIN_DIAGNOSTIC_TRANSPORT"], "supervision": ["RESPONSE_TIMEOUT", "SCHEDULE_MONITORING"]},
    },
    "can": {
        "rate_model": {"type": "SINGLE_BITRATE", "fields": ["bitrate_bps"], "minimum_bps": 10_000, "maximum_bps": 1_000_000},
        "mechanisms": {"integrity": ["CAN_CRC"], "addressing": ["CAN_IDENTIFIER"], "supervision": ["ERROR_COUNTER", "BUS_OFF"]},
    },
    "can_fd": {
        "rate_model": {"type": "MULTI_PHASE_BITRATE", "fields": ["nominal_bitrate_bps", "data_bitrate_bps"], "defaults_bps": {"nominal_bitrate_bps": 500_000, "data_bitrate_bps": 2_000_000}, "nominal_maximum_bps": 1_000_000, "data_maximum_bps": 8_000_000},
        "mechanisms": {"integrity": ["CAN_FD_CRC"], "addressing": ["CAN_IDENTIFIER"], "supervision": ["ERROR_COUNTER", "ERROR_ACTIVE", "ERROR_PASSIVE", "BUS_OFF"]},
    },
    "ethernet": {
        "rate_model": {"type": "ETHERNET_LINK_RATE", "fields": ["bitrate_bps"], "allowed_bps": [10_000_000, 100_000_000, 1_000_000_000, 10_000_000_000]},
        "mechanisms": {"integrity": ["ETHERNET_FCS"], "addressing": ["MAC_ADDRESS"], "address_resolution": ["ARP", "IPV6_NDP"]},
    },
    "ethercat": {
        "rate_model": {"type": "FIXED_LINK_RATE", "fields": ["bitrate_bps"], "fixed_bps": 100_000_000},
        "mechanisms": {"integrity": ["ETHERNET_FCS", "WORKING_COUNTER"], "addressing": ["AUTO_INCREMENT_ADDRESS", "CONFIGURED_STATION_ADDRESS"], "diagnostics": ["AL_STATUS", "COE"], "supervision": ["WORKING_COUNTER"]},
    },
    "profinet": {
        "rate_model": {"type": "ETHERNET_LINK_RATE", "fields": ["bitrate_bps"], "allowed_bps": [100_000_000, 1_000_000_000]},
        "mechanisms": {"integrity": ["ETHERNET_FCS"], "addressing": ["MAC_ADDRESS", "STATION_NAME", "IP_ADDRESS"], "discovery": ["PROFINET_DCP"], "diagnostics": ["PROFINET_DIAGNOSTICS"]},
    },
    "modbus_rtu": {
        "rate_model": {"type": "SINGLE_BITRATE", "fields": ["bitrate_bps"], "minimum_bps": 1_200, "maximum_bps": 115_200},
        "mechanisms": {"integrity": ["MODBUS_CRC16"], "addressing": ["SLAVE_ADDRESS"], "diagnostics": ["MODBUS_DIAGNOSTICS", "EXCEPTION_CODES"]},
    },
    "modbus_tcp": {
        "rate_model": {"type": "ETHERNET_LINK_RATE", "fields": ["bitrate_bps"], "allowed_bps": [10_000_000, 100_000_000, 1_000_000_000, 10_000_000_000]},
        "mechanisms": {"integrity": ["ETHERNET_FCS", "TCP_CHECKSUM"], "addressing": ["IP_ADDRESS", "TCP_PORT_502", "UNIT_IDENTIFIER"]},
    },
    "j1939": {"mechanisms": {"addressing": ["SOURCE_ADDRESS", "NAME", "PGN"], "address_resolution": ["J1939_ADDRESS_CLAIM"], "diagnostics": ["J1939_DM"]}},
    "canopen": {"mechanisms": {"integrity": ["CAN_CRC"], "addressing": ["NODE_ID"], "diagnostics": ["CANOPEN_EMCY", "CANOPEN_SDO"], "supervision": ["HEARTBEAT", "NMT"]}},
    "dds": {"mechanisms": {"discovery": ["DDS_PARTICIPANT_DISCOVERY", "DDS_ENDPOINT_DISCOVERY"], "supervision": ["LIVELINESS", "DEADLINE"]}},
    "bacnet_ip": {"mechanisms": {"discovery": ["BACNET_WHO_IS_I_AM", "BACNET_WHO_HAS_I_HAVE"]}},
    "nmea2000": {"mechanisms": {"addressing": ["SOURCE_ADDRESS", "NAME", "PGN"], "address_resolution": ["NMEA2000_ADDRESS_CLAIM"]}},
}


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
    return {
        "id": technology_id,
        "label": label,
        "domain": domain,
        "layer": layer,
        "transport_unit": transport_unit,
        "payload_element_types": list(payload_types),
        "hardware_interface": hardware_interface,
        "default_stack": list(stack or (technology_id,)),
        "default_bitrate": bitrate,
        "rate_model": rate_model,
        "parameter_schema": {
            field: {"type": "integer", "unit": "bit/s", "minimum": 1}
            for field in rate_model.get("fields", [])
        },
        "mechanisms": semantics.get("mechanisms", {}),
        "physical_layer_profile_id": physical.id if physical else None,
        "medium_access_model": physical.access_model.value if physical else None,
        "arbitration_model_id": physical.arbitration.id if physical and physical.arbitration else None,
        "max_payload_bytes": payload,
        "capabilities": _capabilities(*capabilities),
        "deterministic": deterministic,
        "overhead_bytes": overhead_bytes,
        "implementation_status": _status(technology_id),
        "components": {
            "binding": f"{technology_id}.binding",
            "generator": f"{technology_id}.generator",
            "validator": f"{technology_id}.validator",
            "timing_model": f"{technology_id}.timing",
            "load_model": f"{technology_id}.load",
            "encoder": f"{technology_id}.encoder",
            "decoder": f"{technology_id}.decoder",
        },
        "known_limitations": limitations,
    }


# id, label, domain, layer, unit, elements, interface, stack, bitrate, payload, capabilities, deterministic
ROWS: tuple[tuple[Any, ...], ...] = (
    # Generic layered foundations
    ("ethernet", "Ethernet", "generic_networking", "DATA_LINK", "FRAME", ("FIELD", "RAW_DATA"), "ethernet_port", (), 1_000_000_000, 1500, ("objects", "streams", "multicast", "redundancy", "time_sync", "qos"), False),
    ("ip", "Internet Protocol", "generic_networking", "NETWORK", "PACKET", ("FIELD", "RAW_DATA"), "ethernet_port", ("ethernet", "ip"), None, 65535, ("objects", "streams", "multicast", "fragmentation", "qos"), False),
    ("udp", "UDP", "generic_networking", "TRANSPORT", "DATAGRAM", ("FIELD", "RAW_DATA"), "ethernet_port", ("ethernet", "ip", "udp"), None, 65507, ("objects", "streams", "multicast", "segmentation"), False),
    ("tcp", "TCP", "generic_networking", "TRANSPORT", "STREAM_CHUNK", ("FIELD", "RAW_DATA"), "ethernet_port", ("ethernet", "ip", "tcp"), None, 65535, ("objects", "streams", "request_response", "segmentation", "fragmentation", "qos"), False),
    # Automotive / vehicle
    ("can", "CAN 2.0A/B", "automotive", "DATA_LINK", "FRAME", ("SIGNAL", "STATUS"), "can_controller", (), 500_000, 8, ("multicast", "safety"), True),
    ("can_fd", "CAN-FD", "automotive", "DATA_LINK", "FRAME", ("SIGNAL", "STATUS"), "can_fd_controller", (), 2_000_000, 64, ("multicast", "safety", "segmentation"), True),
    ("can_xl", "CAN XL", "automotive", "DATA_LINK", "FRAME", ("SIGNAL", "FIELD", "RAW_DATA"), "can_xl_controller", (), 10_000_000, 2048, ("objects", "multicast", "segmentation", "qos"), True),
    ("lin", "LIN", "automotive", "DATA_LINK", "FRAME", ("SIGNAL", "STATUS"), "lin_channel", (), 19_200, 8, (), True),
    ("flexray", "FlexRay", "automotive", "DATA_LINK", "FRAME", ("SIGNAL", "STATUS"), "flexray_controller", (), 10_000_000, 254, ("multicast", "redundancy", "time_sync", "safety"), True),
    ("most", "MOST", "automotive", "DATA_LINK", "STREAM_CHUNK", ("AUDIO", "RAW_DATA"), "most_interface", (), 150_000_000, 1500, ("streams", "time_sync"), True),
    ("canopen", "CANopen", "automotive", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "SIGNAL"), "can_controller", ("can", "canopen"), 500_000, 8, ("objects", "pubsub", "request_response", "safety"), True),
    ("j1939", "SAE J1939", "automotive", "APPLICATION", "MESSAGE", ("FIELD", "SIGNAL"), "can_controller", ("can", "j1939"), 250_000, 1785, ("multicast", "segmentation"), True),
    ("isobus", "ISO 11783 / ISOBUS", "automotive", "INDUSTRY_PROFILE", "MESSAGE", ("FIELD", "SIGNAL"), "can_controller", ("can", "j1939", "isobus"), 250_000, 1785, ("objects", "multicast", "segmentation"), True),
    ("uds", "UDS", "automotive", "APPLICATION", "SERVICE_REQUEST", ("COMMAND", "STATUS", "RAW_DATA"), "can_or_ethernet_interface", ("can", "uds"), None, 4095, ("request_response", "segmentation"), False),
    ("xcp", "XCP", "automotive", "APPLICATION", "SERVICE_REQUEST", ("COMMAND", "DATA_OBJECT"), "can_or_ethernet_interface", ("can", "xcp"), None, 65535, ("objects", "request_response", "segmentation"), False),
    ("ccp", "CCP", "automotive", "APPLICATION", "SERVICE_REQUEST", ("COMMAND", "DATA_OBJECT"), "can_controller", ("can", "ccp"), 500_000, 8, ("objects", "request_response"), False),
    ("someip", "SOME/IP", "automotive", "APPLICATION", "SERVICE_EVENT", ("FIELD", "DATA_OBJECT"), "ethernet_port", ("ethernet", "ip", "udp", "someip"), None, 65535, ("objects", "pubsub", "request_response", "segmentation", "qos"), False),
    ("someip_sd", "SOME/IP-SD", "automotive", "APPLICATION", "SERVICE_EVENT", ("FIELD", "STATUS"), "ethernet_port", ("ethernet", "ip", "udp", "someip_sd"), None, 1400, ("objects", "multicast", "pubsub"), False),
    ("doip", "DoIP", "automotive", "APPLICATION", "PDU", ("COMMAND", "STATUS", "RAW_DATA"), "ethernet_port", ("ethernet", "ip", "tcp", "doip"), None, 4096, ("request_response", "segmentation"), False),
    ("obd2", "OBD-II", "automotive", "INDUSTRY_PROFILE", "SERVICE_REQUEST", ("COMMAND", "STATUS"), "can_or_ethernet_interface", ("can", "uds", "obd2"), None, 4095, ("request_response",), False),
    ("avb", "AVB", "automotive", "INDUSTRY_PROFILE", "STREAM_CHUNK", ("AUDIO", "RAW_DATA"), "ethernet_port", ("ethernet", "avb"), 1_000_000_000, 1500, ("streams", "multicast", "time_sync", "qos"), True),
    ("tsn", "Time-Sensitive Networking", "generic_networking", "INDUSTRY_PROFILE", "FRAME", ("FIELD", "RAW_DATA"), "ethernet_port", ("ethernet", "tsn"), 1_000_000_000, 1500, ("objects", "streams", "multicast", "redundancy", "time_sync", "safety", "qos"), True),
    # Industrial / PLC
    ("profinet", "PROFINET RT/IRT", "industrial_automation", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS", "QUALITY"), "ethernet_port", ("ethernet", "profinet"), 100_000_000, 1440, ("objects", "pubsub", "cyclic", "time_sync", "safety", "qos"), True),
    ("ethercat", "EtherCAT", "industrial_automation", "INDUSTRY_PROFILE", "DATAGRAM", ("FIELD", "REGISTER", "STATUS"), "ethercat_port", ("ethernet", "ethercat"), 100_000_000, 1486, ("objects", "pubsub", "time_sync", "safety", "qos"), True),
    ("ethernet_ip", "EtherNet/IP", "industrial_automation", "APPLICATION", "PROCESS_DATA", ("FIELD", "DATA_OBJECT"), "ethernet_port", ("ethernet", "ip", "udp", "ethernet_ip"), 100_000_000, 1400, ("objects", "pubsub", "request_response", "safety", "qos"), True),
    ("modbus_tcp", "Modbus TCP", "industrial_automation", "APPLICATION", "PDU", ("REGISTER", "COIL"), "ethernet_port", ("ethernet", "ip", "tcp", "modbus_tcp"), 100_000_000, 253, ("request_response", "segmentation"), False),
    ("modbus_rtu", "Modbus RTU", "industrial_automation", "APPLICATION", "PDU", ("REGISTER", "COIL"), "rs485_port", ("modbus_rtu",), 115_200, 253, ("request_response",), True),
    ("modbus_ascii", "Modbus ASCII", "industrial_automation", "APPLICATION", "PDU", ("REGISTER", "COIL"), "rs485_port", ("modbus_ascii",), 19_200, 252, ("request_response",), False),
    ("profibus_dp", "PROFIBUS DP", "industrial_automation", "INDUSTRY_PROFILE", "TELEGRAM", ("FIELD", "STATUS"), "profibus_interface", (), 12_000_000, 244, ("pubsub", "request_response", "safety"), True),
    ("profibus_pa", "PROFIBUS PA", "process_industry", "INDUSTRY_PROFILE", "TELEGRAM", ("FIELD", "STATUS", "QUALITY"), "profibus_interface", (), 31_250, 244, ("pubsub", "request_response", "safety"), True),
    ("devicenet", "DeviceNet", "industrial_automation", "INDUSTRY_PROFILE", "MESSAGE", ("DATA_OBJECT", "SIGNAL"), "can_controller", ("can", "devicenet"), 500_000, 8, ("objects", "pubsub", "request_response"), True),
    ("interbus", "INTERBUS", "industrial_automation", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS"), "interbus_interface", (), 500_000, 246, ("pubsub",), True),
    ("cc_link", "CC-Link", "industrial_automation", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS"), "cc_link_interface", (), 10_000_000, 256, ("pubsub",), True),
    ("cc_link_ie", "CC-Link IE", "industrial_automation", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS"), "ethernet_port", ("ethernet", "cc_link_ie"), 1_000_000_000, 1500, ("objects", "pubsub", "time_sync", "qos"), True),
    ("sercos_iii", "Sercos III", "industrial_automation", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS"), "ethernet_port", ("ethernet", "sercos_iii"), 100_000_000, 1500, ("pubsub", "time_sync", "safety"), True),
    ("powerlink", "POWERLINK", "industrial_automation", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS"), "ethernet_port", ("ethernet", "powerlink"), 100_000_000, 1500, ("pubsub", "time_sync", "safety"), True),
    ("io_link", "IO-Link", "industrial_automation", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS", "QUALITY"), "io_link_master_port", (), 230_400, 32, ("request_response",), True),
    ("io_link_wireless", "IO-Link Wireless", "industrial_automation", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS", "QUALITY"), "wireless_interface", (), 1_000_000, 32, ("request_response", "time_sync"), True),
    ("opc_ua", "OPC UA Client/Server", "industrial_automation", "APPLICATION", "SERVICE_RESPONSE", ("DATA_OBJECT", "STRUCT", "STATUS", "QUALITY"), "ethernet_port", ("ethernet", "ip", "tcp", "opc_ua"), None, 65535, ("objects", "request_response", "segmentation", "qos"), False),
    ("opc_ua_pubsub", "OPC UA PubSub", "industrial_automation", "APPLICATION", "DATAGRAM", ("DATA_OBJECT", "STRUCT", "STATUS", "QUALITY"), "ethernet_port", ("ethernet", "ip", "udp", "opc_ua_pubsub"), None, 65507, ("objects", "multicast", "pubsub", "time_sync", "qos"), True),
    ("mqtt", "MQTT", "iot_wireless", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "RAW_DATA"), "ethernet_or_wireless_interface", ("ethernet", "ip", "tcp", "mqtt"), None, 268435455, ("objects", "pubsub", "qos", "segmentation"), False),
    ("sparkplug_b", "Sparkplug B", "industrial_automation", "INDUSTRY_PROFILE", "MESSAGE", ("DATA_OBJECT", "STATUS", "QUALITY"), "ethernet_port", ("ethernet", "ip", "tcp", "mqtt", "sparkplug_b"), None, 268435455, ("objects", "pubsub", "qos", "segmentation"), False),
    # Robotics
    ("dds", "DDS / RTPS", "robotics_ros", "APPLICATION", "TOPIC_SAMPLE", ("DATA_OBJECT", "STRUCT", "ARRAY", "IMAGE", "POINT_CLOUD"), "ethernet_port", ("ethernet", "ip", "udp", "dds"), None, 65507, ("objects", "streams", "multicast", "pubsub", "redundancy", "time_sync", "fragmentation", "qos"), True),
    ("ros2", "ROS 2", "robotics_ros", "INDUSTRY_PROFILE", "TOPIC_SAMPLE", ("DATA_OBJECT", "STRUCT", "ARRAY", "IMAGE", "POINT_CLOUD"), "ethernet_port", ("ethernet", "ip", "udp", "dds", "ros2"), None, 65507, ("objects", "streams", "multicast", "pubsub", "request_response", "fragmentation", "qos"), False),
    # Aerospace
    ("arinc429", "ARINC 429", "aerospace", "DATA_LINK", "WORD", ("FIELD", "STATUS"), "arinc429_interface", (), 100_000, 4, (), True),
    ("afdx", "ARINC 664 / AFDX", "aerospace", "INDUSTRY_PROFILE", "PACKET", ("FIELD", "RAW_DATA"), "afdx_ethernet_port", ("ethernet", "ip", "udp", "afdx"), 100_000_000, 1471, ("multicast", "redundancy", "qos"), True),
    ("mil_std_1553", "MIL-STD-1553B", "aerospace", "DATA_LINK", "WORD", ("COMMAND", "FIELD", "STATUS"), "mil1553_interface", (), 1_000_000, 64, ("multicast", "redundancy"), True),
    ("can_aerospace", "CAN Aerospace", "aerospace", "INDUSTRY_PROFILE", "MESSAGE", ("SIGNAL", "STATUS"), "can_controller", ("can", "can_aerospace"), 1_000_000, 8, ("multicast",), True),
    ("spacewire", "SpaceWire", "aerospace", "DATA_LINK", "PACKET", ("FIELD", "RAW_DATA"), "spacewire_interface", (), 200_000_000, 65535, ("objects", "streams", "time_sync", "fragmentation"), True),
    ("tte", "Time-Triggered Ethernet", "aerospace", "INDUSTRY_PROFILE", "FRAME", ("FIELD", "RAW_DATA"), "ethernet_port", ("ethernet", "tte"), 1_000_000_000, 1500, ("multicast", "redundancy", "time_sync", "safety", "qos"), True),
    # Rail / marine / heavy vehicle
    ("mvb", "MVB", "rail", "DATA_LINK", "PROCESS_DATA", ("SIGNAL", "STATUS"), "mvb_interface", (), 1_500_000, 32, ("multicast", "time_sync"), True),
    ("wtb", "WTB", "rail", "DATA_LINK", "PROCESS_DATA", ("SIGNAL", "STATUS"), "wtb_interface", (), 1_000_000, 128, ("multicast", "redundancy", "time_sync"), True),
    ("etb", "Ethernet Train Backbone", "rail", "INDUSTRY_PROFILE", "FRAME", ("FIELD", "RAW_DATA"), "ethernet_port", ("ethernet", "etb"), 100_000_000, 1500, ("objects", "streams", "multicast", "redundancy", "qos"), True),
    ("trdp", "TRDP", "rail", "APPLICATION", "PROCESS_DATA", ("FIELD", "STATUS"), "ethernet_port", ("ethernet", "ip", "udp", "trdp"), 100_000_000, 65507, ("objects", "multicast", "pubsub", "request_response", "qos"), True),
    ("nmea0183", "NMEA 0183", "marine", "APPLICATION", "TELEGRAM", ("FIELD", "STATUS"), "rs422_port", (), 4_800, 82, ("no_cyclic",), False),
    ("nmea2000", "NMEA 2000", "marine", "INDUSTRY_PROFILE", "MESSAGE", ("FIELD", "SIGNAL"), "can_controller", ("can", "nmea2000"), 250_000, 223, ("multicast", "segmentation"), True),
    ("iec61162", "IEC 61162", "marine", "INDUSTRY_PROFILE", "TELEGRAM", ("FIELD", "STATUS"), "serial_or_ethernet_interface", (), None, 65535, ("objects", "multicast"), False),
    # Building automation
    ("bacnet_ip", "BACnet/IP", "building_automation", "APPLICATION", "PDU", ("DATA_OBJECT", "FIELD"), "ethernet_port", ("ethernet", "ip", "udp", "bacnet_ip"), 100_000_000, 1476, ("objects", "multicast", "request_response", "segmentation"), False),
    ("bacnet_mstp", "BACnet MS/TP", "building_automation", "APPLICATION", "PDU", ("DATA_OBJECT", "FIELD"), "rs485_port", (), 115_200, 501, ("objects", "request_response", "segmentation"), True),
    ("bacnet_sc", "BACnet/SC", "building_automation", "APPLICATION", "PDU", ("DATA_OBJECT", "FIELD"), "ethernet_port", ("ethernet", "ip", "tcp", "bacnet_sc"), None, 65535, ("objects", "request_response", "qos"), False),
    ("knx_tp", "KNX TP", "building_automation", "INDUSTRY_PROFILE", "TELEGRAM", ("DATA_OBJECT", "FIELD"), "knx_tp_interface", (), 9_600, 255, ("objects", "multicast", "pubsub"), True),
    ("knx_ip", "KNX IP", "building_automation", "INDUSTRY_PROFILE", "TELEGRAM", ("DATA_OBJECT", "FIELD"), "ethernet_port", ("ethernet", "ip", "udp", "knx_ip"), 100_000_000, 1476, ("objects", "multicast", "pubsub"), False),
    ("knx_rf", "KNX RF", "building_automation", "INDUSTRY_PROFILE", "TELEGRAM", ("DATA_OBJECT", "FIELD"), "wireless_interface", (), 16_384, 255, ("objects", "multicast", "pubsub"), False),
    ("lonworks", "LonWorks", "building_automation", "INDUSTRY_PROFILE", "MESSAGE", ("DATA_OBJECT", "FIELD"), "lonworks_interface", (), 78_000, 228, ("objects", "pubsub"), True),
    ("dali", "DALI", "building_automation", "APPLICATION", "TELEGRAM", ("COMMAND", "STATUS"), "dali_interface", (), 1_200, 2, ("request_response",), True),
    ("m_bus", "M-Bus", "building_automation", "APPLICATION", "TELEGRAM", ("FIELD", "STATUS"), "m_bus_interface", (), 9_600, 252, ("request_response",), False),
    ("wireless_m_bus", "Wireless M-Bus", "building_automation", "APPLICATION", "TELEGRAM", ("FIELD", "STATUS"), "wireless_interface", (), 100_000, 255, ("no_cyclic",), False),
    # Energy and process
    ("iec61850", "IEC 61850", "energy", "INDUSTRY_PROFILE", "MESSAGE", ("DATA_OBJECT", "STRUCT", "STATUS", "QUALITY"), "ethernet_port", ("ethernet", "iec61850"), 100_000_000, 1500, ("objects", "multicast", "pubsub", "request_response", "redundancy", "time_sync", "safety", "qos"), True),
    ("mms", "MMS", "energy", "APPLICATION", "SERVICE_RESPONSE", ("DATA_OBJECT", "STRUCT"), "ethernet_port", ("ethernet", "ip", "tcp", "mms"), None, 65535, ("objects", "request_response", "segmentation"), False),
    ("goose", "GOOSE", "energy", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "STATUS", "QUALITY"), "ethernet_port", ("ethernet", "goose"), 100_000_000, 1500, ("objects", "multicast", "pubsub", "redundancy", "time_sync", "safety", "qos"), True),
    ("sampled_values", "IEC 61850 Sampled Values", "energy", "APPLICATION", "TOPIC_SAMPLE", ("ARRAY", "QUALITY"), "ethernet_port", ("ethernet", "sampled_values"), 100_000_000, 1500, ("objects", "streams", "multicast", "pubsub", "time_sync", "safety", "qos"), True),
    ("dnp3", "DNP3", "energy", "APPLICATION", "PDU", ("DATA_OBJECT", "STATUS", "QUALITY"), "serial_or_ethernet_interface", (), None, 2048, ("objects", "request_response", "segmentation"), False),
    ("iec60870_5_101", "IEC 60870-5-101", "energy", "APPLICATION", "TELEGRAM", ("DATA_OBJECT", "STATUS", "QUALITY"), "serial_port", (), 115_200, 255, ("objects", "request_response"), False),
    ("iec60870_5_104", "IEC 60870-5-104", "energy", "APPLICATION", "PDU", ("DATA_OBJECT", "STATUS", "QUALITY"), "ethernet_port", ("ethernet", "ip", "tcp", "iec60870_5_104"), None, 255, ("objects", "request_response", "segmentation"), False),
    ("sunspec_modbus", "SunSpec Modbus", "energy", "INDUSTRY_PROFILE", "REGISTER_BLOCK", ("REGISTER", "STATUS"), "ethernet_or_rs485_interface", ("modbus_tcp", "sunspec_modbus"), None, 253, ("objects", "request_response"), False),
    ("ocpp", "OCPP", "energy", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "COMMAND", "STATUS"), "ethernet_or_wireless_interface", ("ethernet", "ip", "tcp", "ocpp"), None, 65535, ("objects", "request_response", "qos"), False),
    ("hart", "HART", "process_industry", "INDUSTRY_PROFILE", "TELEGRAM", ("FIELD", "STATUS", "QUALITY"), "hart_interface", (), 1_200, 255, ("request_response",), False),
    ("wirelesshart", "WirelessHART", "process_industry", "INDUSTRY_PROFILE", "MESSAGE", ("FIELD", "STATUS", "QUALITY"), "wireless_interface", (), 250_000, 127, ("multicast", "time_sync", "qos"), True),
    ("foundation_fieldbus_h1", "FOUNDATION Fieldbus H1", "process_industry", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS", "QUALITY"), "fieldbus_interface", (), 31_250, 251, ("objects", "pubsub", "time_sync", "safety"), True),
    # Embedded interfaces
    ("i2c", "I2C", "embedded_systems", "DATA_LINK", "MESSAGE", ("REGISTER", "RAW_DATA"), "i2c_controller", (), 400_000, 255, ("request_response",), True),
    ("i3c", "I3C", "embedded_systems", "DATA_LINK", "MESSAGE", ("REGISTER", "RAW_DATA"), "i3c_controller", (), 12_500_000, 65535, ("request_response", "event"), True),
    ("spi", "SPI / QSPI", "embedded_systems", "DATA_LINK", "STREAM_CHUNK", ("REGISTER", "RAW_DATA"), "spi_controller", (), 50_000_000, 65535, ("streams",), True),
    ("uart", "UART / USART", "embedded_systems", "DATA_LINK", "STREAM_CHUNK", ("RAW_DATA",), "serial_port", (), 115_200, 65535, ("streams",), False),
    ("rs232", "RS-232", "embedded_systems", "PHYSICAL", "STREAM_CHUNK", ("RAW_DATA",), "rs232_port", (), 115_200, 65535, ("streams",), False),
    ("rs422", "RS-422", "embedded_systems", "PHYSICAL", "STREAM_CHUNK", ("RAW_DATA",), "rs422_port", (), 10_000_000, 65535, ("streams",), False),
    ("rs485", "RS-485", "embedded_systems", "PHYSICAL", "STREAM_CHUNK", ("RAW_DATA",), "rs485_port", (), 10_000_000, 65535, ("streams",), False),
    ("one_wire", "1-Wire", "embedded_systems", "DATA_LINK", "MESSAGE", ("REGISTER", "RAW_DATA"), "one_wire_interface", (), 16_300, 255, ("request_response",), True),
    ("usb", "USB", "embedded_systems", "DATA_LINK", "PACKET", ("RAW_DATA", "STREAM_CHUNK"), "usb_controller", (), 480_000_000, 1024, ("objects", "streams", "segmentation", "qos"), True),
    ("pcie", "PCIe", "embedded_systems", "DATA_LINK", "PACKET", ("RAW_DATA", "DATA_OBJECT"), "pcie_interface", (), 8_000_000_000, 4096, ("objects", "streams", "qos"), True),
    ("mipi_csi2", "MIPI CSI-2", "embedded_systems", "DATA_LINK", "STREAM_CHUNK", ("IMAGE", "RAW_DATA"), "mipi_csi2_interface", (), 2_500_000_000, 65535, ("streams",), True),
    ("mipi_dsi", "MIPI DSI", "embedded_systems", "DATA_LINK", "STREAM_CHUNK", ("IMAGE", "RAW_DATA"), "mipi_dsi_interface", (), 2_500_000_000, 65535, ("streams",), True),
    ("lvds", "LVDS", "embedded_systems", "PHYSICAL", "STREAM_CHUNK", ("RAW_DATA",), "lvds_interface", (), 3_000_000_000, 65535, ("streams",), True),
    ("gpio", "GPIO", "embedded_systems", "PHYSICAL", "PROCESS_DATA", ("SIGNAL", "STATUS"), "gpio_port", (), None, 1, (), True),
    ("pwm", "PWM", "embedded_systems", "PHYSICAL", "PROCESS_DATA", ("SIGNAL",), "pwm_output", (), None, 1, (), True),
    ("adc", "ADC", "embedded_systems", "PHYSICAL", "PROCESS_DATA", ("SIGNAL",), "analog_input", (), None, 4, (), True),
    ("dac", "DAC", "embedded_systems", "PHYSICAL", "PROCESS_DATA", ("SIGNAL",), "analog_output", (), None, 4, (), True),
    # IoT / wireless
    ("mqtt_sn", "MQTT-SN", "iot_wireless", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "RAW_DATA"), "wireless_interface", (), None, 65535, ("objects", "pubsub", "qos"), False),
    ("coap", "CoAP", "iot_wireless", "APPLICATION", "PDU", ("DATA_OBJECT", "RAW_DATA"), "ethernet_or_wireless_interface", ("ethernet", "ip", "udp", "coap"), None, 1152, ("objects", "multicast", "request_response"), False),
    ("http", "HTTP", "iot_wireless", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "RAW_DATA"), "ethernet_or_wireless_interface", ("ethernet", "ip", "tcp", "http"), None, 65535, ("objects", "streams", "request_response", "segmentation"), False),
    ("websocket", "WebSocket", "iot_wireless", "APPLICATION", "STREAM_CHUNK", ("DATA_OBJECT", "RAW_DATA"), "ethernet_or_wireless_interface", ("ethernet", "ip", "tcp", "websocket"), None, 65535, ("objects", "streams", "pubsub", "segmentation"), False),
    ("amqp", "AMQP", "iot_wireless", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "RAW_DATA"), "ethernet_or_wireless_interface", ("ethernet", "ip", "tcp", "amqp"), None, 65535, ("objects", "pubsub", "request_response", "qos"), False),
    ("wifi", "Wi-Fi", "iot_wireless", "DATA_LINK", "FRAME", ("FIELD", "RAW_DATA"), "wireless_interface", (), 1_000_000_000, 2304, ("objects", "streams", "multicast", "qos"), False),
    ("bluetooth_le", "Bluetooth LE", "iot_wireless", "DATA_LINK", "PDU", ("FIELD", "DATA_OBJECT"), "wireless_interface", (), 2_000_000, 251, ("objects", "pubsub", "request_response"), False),
    ("zigbee", "Zigbee", "iot_wireless", "INDUSTRY_PROFILE", "PACKET", ("DATA_OBJECT", "FIELD"), "wireless_interface", (), 250_000, 127, ("objects", "multicast", "pubsub"), False),
    ("thread", "Thread", "iot_wireless", "INDUSTRY_PROFILE", "PACKET", ("DATA_OBJECT", "FIELD"), "wireless_interface", (), 250_000, 127, ("objects", "multicast", "pubsub"), False),
    ("matter", "Matter", "iot_wireless", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "COMMAND", "STATUS"), "ethernet_or_wireless_interface", (), None, 65535, ("objects", "multicast", "pubsub", "request_response"), False),
    ("lorawan", "LoRaWAN", "iot_wireless", "INDUSTRY_PROFILE", "PACKET", ("FIELD", "DATA_OBJECT"), "wireless_interface", (), 50_000, 242, ("objects", "no_cyclic", "qos"), False),
    ("lte_m", "LTE-M", "iot_wireless", "DATA_LINK", "PACKET", ("FIELD", "RAW_DATA"), "wireless_interface", (), 1_000_000, 1500, ("objects", "streams", "qos"), False),
    ("nb_iot", "NB-IoT", "iot_wireless", "DATA_LINK", "PACKET", ("FIELD", "RAW_DATA"), "wireless_interface", (), 250_000, 1500, ("objects", "qos"), False),
    ("5g", "5G", "iot_wireless", "DATA_LINK", "PACKET", ("FIELD", "RAW_DATA"), "wireless_interface", (), 10_000_000_000, 1500, ("objects", "streams", "multicast", "qos"), False),
    ("uwb", "UWB", "iot_wireless", "DATA_LINK", "FRAME", ("FIELD", "RAW_DATA"), "wireless_interface", (), 27_000_000, 1023, ("objects", "time_sync"), False),
    ("nfc", "NFC", "iot_wireless", "DATA_LINK", "MESSAGE", ("DATA_OBJECT", "RAW_DATA"), "wireless_interface", (), 424_000, 255, ("objects", "request_response"), False),
    ("rfid", "RFID", "iot_wireless", "INDUSTRY_PROFILE", "MESSAGE", ("DATA_OBJECT", "RAW_DATA"), "wireless_interface", (), None, 255, ("objects", "request_response"), False),
    # Safety profiles and custom
    ("profisafe", "PROFIsafe", "industrial_automation", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS", "QUALITY"), "ethernet_or_profibus_interface", (), None, 1440, ("safety", "time_sync", "qos"), True),
    ("cip_safety", "CIP Safety", "industrial_automation", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS", "QUALITY"), "ethernet_or_can_interface", (), None, 1400, ("safety", "qos"), True),
    ("fsoe", "FSoE", "industrial_automation", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS", "QUALITY"), "ethercat_port", ("ethernet", "ethercat", "fsoe"), 100_000_000, 1486, ("safety", "time_sync"), True),
    ("opensafety", "openSAFETY", "industrial_automation", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS", "QUALITY"), "generic_network_interface", (), None, 1500, ("safety", "redundancy"), True),
    ("generic_serial", "Generic Serial", "custom", "DATA_LINK", "STREAM_CHUNK", ("RAW_DATA",), "serial_port", (), None, 65535, ("streams",), False),
    ("generic_can", "Generic CAN", "custom", "DATA_LINK", "FRAME", ("SIGNAL", "RAW_DATA"), "can_controller", (), 500_000, 8, ("multicast",), True),
    ("generic_ethernet", "Generic Ethernet", "custom", "DATA_LINK", "FRAME", ("FIELD", "RAW_DATA"), "ethernet_port", (), 1_000_000_000, 1500, ("objects", "streams", "multicast", "qos"), False),
    ("custom_udp", "Custom UDP", "custom", "APPLICATION", "DATAGRAM", ("RAW_DATA", "DATA_OBJECT"), "ethernet_or_wireless_interface", ("ethernet", "ip", "udp", "custom_udp"), None, 65507, ("objects", "streams", "multicast"), False),
    ("custom_tcp", "Custom TCP", "custom", "APPLICATION", "STREAM_CHUNK", ("RAW_DATA", "DATA_OBJECT"), "ethernet_or_wireless_interface", ("ethernet", "ip", "tcp", "custom_tcp"), None, 65535, ("objects", "streams", "segmentation"), False),
    ("custom_binary", "Custom Binary", "custom", "APPLICATION", "MESSAGE", ("RAW_DATA",), "generic_network_interface", (), None, 65535, ("streams", "segmentation"), False),
    ("custom_text", "Custom Text", "custom", "APPLICATION", "MESSAGE", ("RAW_DATA",), "generic_network_interface", (), None, 65535, ("streams", "segmentation"), False),
    ("custom_protocol", "Custom Protocol", "custom", "APPLICATION", "MESSAGE", ("RAW_DATA", "DATA_OBJECT"), "generic_network_interface", (), None, 65535, ("objects", "streams", "segmentation"), False),
)


def technology_definitions() -> list[dict[str, Any]]:
    return [_spec(*row) for row in ROWS]
