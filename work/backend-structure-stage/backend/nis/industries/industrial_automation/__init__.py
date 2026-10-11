"""Industrial fieldbus and real-time Ethernet ownership."""

from backend.nis.specializations.core import TechnologySpecialization

MANIFEST = TechnologySpecialization("industrial_automation", (
    "profinet", "ethercat", "ethernet_ip", "modbus_tcp", "modbus_rtu",
    "modbus_ascii", "profibus_dp", "profibus_pa", "interbus", "cc_link",
    "cc_link_ie", "sercos_iii", "powerlink", "io_link", "io_link_wireless",
    "opc_ua", "opc_ua_pubsub", "profisafe", "cip_safety", "fsoe", "opensafety",
), ("backend.nis.communication.catalog", "backend.nis.communication.core"))
__all__ = ["MANIFEST"]
