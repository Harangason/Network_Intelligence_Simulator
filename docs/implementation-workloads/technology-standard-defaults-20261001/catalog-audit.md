# Prüfung aller Technologieparameter – 2026-10-01

125 registrierte Technologien; alle deklarierten Formularparameter auf Vorschlagswert, Datentyp, Grenzwerte und Auswahl geprüft. 13.392 unterschiedliche Technologiepaare auf fremde bestätigte Transportwerte geprüft.

Die Prüfung beschreibt registrierte Profile und Vorschläge. Sie ist kein vollständiger Geräte-, PHY-, Normkonformitäts- oder Kapazitätsnachweis. Geräteabhängige Werte bleiben offen. Bestätigte Nutzerwerte bleiben erhalten.

I²C: Standardmodus 100.000 bit/s (NXP UM10204 Rev. 7). Dies ist die Obergrenze dieses Modus, keine physikalische Mindestfrequenz. SPI besitzt keinen universellen Gerätestandardtakt. NMEA 2000 verwendet seine eigene CAN-basierte feste Rate 250.000 bit/s; Ethernet-Raten werden dort abgewiesen.

Zeit-/Zyklus-/Queue-/Fehlerparameter sind NIS-Analyse-/Simulationsvorschläge, keine vom Busstandard garantierten Funktionsanforderungen. Historische Katalogwerte werden ausdrücklich als Katalogkandidaten geführt.

Quellen: https://cache.nxp.com/docs/en/user-guide/UM10204.pdf ; https://continuouswave.com/whaler/reference/NMEA2000/NMEAPastPresentFuture.pdf (NMEA-Präsentation), https://www.nmea.org/nmea-2000.html

## Ergebnisgruppen

- CATALOG_REVIEW_CANDIDATE: 72
- NOT_APPLICABLE: 16
- LOWEST_PROFILE_MODE: 27
- PROFILE_MINIMUM: 5
- PROFILE_PHASE_DEFAULTS: 1
- FIXED_PROFILE_RATE: 2
- STANDARD_MODE: 1
- DEVICE_DEPENDENT: 1

## Katalog

| Technologie | Vorschlag in bit/s | Herkunft | Kapazitätsmodell |
| --- | --- | --- | --- |
| 5g | bitrate_bps=10000000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| adc | Offen / nicht anwendbar | NOT_APPLICABLE | NOT_APPLICABLE |
| afdx | bitrate_bps=100000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| amqp | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| arinc429 | bitrate_bps=100000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| avb | bitrate_bps=1000000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| bacnet_ip | bitrate_bps=100000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| bacnet_mstp | bitrate_bps=115200 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| bacnet_sc | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| bluetooth_le | bitrate_bps=2000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| can | bitrate_bps=10000 | PROFILE_MINIMUM | MODEL_AVAILABLE |
| can_aerospace | bitrate_bps=1000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| can_fd | nominal_bitrate_bps=500000, data_bitrate_bps=2000000 | PROFILE_PHASE_DEFAULTS | MODEL_AVAILABLE |
| can_xl | bitrate_bps=10000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| canopen | bitrate_bps=500000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| cc_link | bitrate_bps=10000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| cc_link_ie | bitrate_bps=1000000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| ccp | bitrate_bps=500000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| cip_safety | Offen / nicht anwendbar | NOT_APPLICABLE | MODEL_MISSING |
| coap | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| custom_binary | Offen / nicht anwendbar | NOT_APPLICABLE | MODEL_MISSING |
| custom_protocol | Offen / nicht anwendbar | NOT_APPLICABLE | MODEL_MISSING |
| custom_tcp | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| custom_text | Offen / nicht anwendbar | NOT_APPLICABLE | MODEL_MISSING |
| custom_udp | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| dac | Offen / nicht anwendbar | NOT_APPLICABLE | NOT_APPLICABLE |
| dali | bitrate_bps=1200 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| dds | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| devicenet | bitrate_bps=500000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| dnp3 | Offen / nicht anwendbar | NOT_APPLICABLE | MODEL_MISSING |
| doip | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| etb | bitrate_bps=100000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| ethercat | bitrate_bps=100000000 | FIXED_PROFILE_RATE | MODEL_MISSING |
| ethernet | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_AVAILABLE |
| ethernet_ip | bitrate_bps=100000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| flexray | bitrate_bps=10000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| foundation_fieldbus_h1 | bitrate_bps=31250 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| fsoe | bitrate_bps=100000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| generic_can | bitrate_bps=500000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| generic_ethernet | bitrate_bps=1000000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| generic_serial | Offen / nicht anwendbar | NOT_APPLICABLE | MODEL_MISSING |
| goose | bitrate_bps=100000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| gpio | Offen / nicht anwendbar | NOT_APPLICABLE | NOT_APPLICABLE |
| hart | bitrate_bps=1200 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| http | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| i2c | bitrate_bps=100000 | STANDARD_MODE | MODEL_AVAILABLE |
| i3c | bitrate_bps=12500000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| iec60870_5_101 | bitrate_bps=115200 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| iec60870_5_104 | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| iec61162 | Offen / nicht anwendbar | NOT_APPLICABLE | MODEL_MISSING |
| iec61850 | bitrate_bps=100000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| interbus | bitrate_bps=500000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| io_link | bitrate_bps=230400 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| io_link_wireless | bitrate_bps=1000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| ip | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| isobus | bitrate_bps=250000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| j1939 | bitrate_bps=250000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| knx_ip | bitrate_bps=100000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| knx_rf | bitrate_bps=16384 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| knx_tp | bitrate_bps=9600 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| lin | bitrate_bps=9600 | LOWEST_PROFILE_MODE | MODEL_AVAILABLE |
| lonworks | bitrate_bps=78000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| lorawan | bitrate_bps=50000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| lte_m | bitrate_bps=1000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| lvds | bitrate_bps=3000000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| m_bus | bitrate_bps=9600 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| matter | Offen / nicht anwendbar | NOT_APPLICABLE | MODEL_MISSING |
| mil_std_1553 | bitrate_bps=1000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| mipi_csi2 | bitrate_bps=2500000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| mipi_dsi | bitrate_bps=2500000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| mms | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| modbus_ascii | bitrate_bps=19200 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| modbus_rtu | bitrate_bps=1200 | PROFILE_MINIMUM | MODEL_MISSING |
| modbus_tcp | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| most | bitrate_bps=150000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| mqtt | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| mqtt_sn | Offen / nicht anwendbar | NOT_APPLICABLE | MODEL_MISSING |
| mvb | bitrate_bps=1500000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| nb_iot | bitrate_bps=250000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| nfc | bitrate_bps=424000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| nmea0183 | bitrate_bps=4800 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| nmea2000 | bitrate_bps=250000 | FIXED_PROFILE_RATE | MODEL_MISSING |
| obd2 | bitrate_bps=10000 | PROFILE_MINIMUM | MODEL_MISSING |
| ocpp | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| one_wire | bitrate_bps=16300 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| opc_ua | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| opc_ua_pubsub | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| opensafety | Offen / nicht anwendbar | NOT_APPLICABLE | MODEL_MISSING |
| pcie | bitrate_bps=8000000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| powerlink | bitrate_bps=100000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| profibus_dp | bitrate_bps=12000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| profibus_pa | bitrate_bps=31250 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| profinet | bitrate_bps=100000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| profisafe | Offen / nicht anwendbar | NOT_APPLICABLE | MODEL_MISSING |
| pwm | Offen / nicht anwendbar | NOT_APPLICABLE | NOT_APPLICABLE |
| rfid | Offen / nicht anwendbar | NOT_APPLICABLE | MODEL_MISSING |
| ros2 | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| rs232 | bitrate_bps=115200 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| rs422 | bitrate_bps=10000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| rs485 | bitrate_bps=10000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| sampled_values | bitrate_bps=100000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| sercos_iii | bitrate_bps=100000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| someip | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| someip_sd | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| spacewire | bitrate_bps=200000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| sparkplug_b | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| spi | Offen / nicht anwendbar | DEVICE_DEPENDENT | MODEL_AVAILABLE |
| sunspec_modbus | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| tcp | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| thread | bitrate_bps=250000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| trdp | bitrate_bps=100000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| tsn | bitrate_bps=1000000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| tte | bitrate_bps=1000000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| uart | bitrate_bps=115200 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| udp | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| uds | bitrate_bps=10000 | PROFILE_MINIMUM | MODEL_MISSING |
| usb | bitrate_bps=480000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| uwb | bitrate_bps=27000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| websocket | bitrate_bps=10000000 | LOWEST_PROFILE_MODE | MODEL_MISSING |
| wifi | bitrate_bps=1000000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| wireless_m_bus | bitrate_bps=100000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| wirelesshart | bitrate_bps=250000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| wtb | bitrate_bps=1000000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
| xcp | bitrate_bps=10000 | PROFILE_MINIMUM | MODEL_MISSING |
| zigbee | bitrate_bps=250000 | CATALOG_REVIEW_CANDIDATE | MODEL_MISSING |
