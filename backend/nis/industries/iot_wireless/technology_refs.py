"""Wireless and IoT transport ownership."""

from backend.nis.specializations.core import TechnologySpecialization

MANIFEST = TechnologySpecialization("wireless_iot", (
    "mqtt", "mqtt_sn", "sparkplug_b", "coap", "http", "websocket", "amqp",
    "wifi", "bluetooth_le", "zigbee", "thread", "matter", "lorawan", "lte_m",
    "nb_iot", "5g", "uwb", "nfc", "rfid",
), ("backend.nis.communication.catalog", "backend.nis.communication.core"))
__all__ = ["MANIFEST"]
