# Vollständige Technologie-Abdeckungsmatrix (25.09.2026)

Quellstand `ef08e18d`; die Spalten bezeichnen direkt belegte Codepfade, keine Normkonformität. `missing` kann bei Anwendungsschichten durch einen bestätigten Stack ergänzt werden; `UNVERIFIED` bedeutet keinen deterministischen Zeitnachweis. Detailbewertung: [Prüfbericht](BUS_TECHNOLOGY_COMPLETENESS_AUDIT_2026-09-25.md).

| ID | Bereich | Schicht | Katalogstatus | Rate-Modell | PHY | Routing | Rahmenmodell | Zeitplan | Mechanismen |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ethernet | generic_networking | DATA_LINK | IMPLEMENTED | explicit | direct | ETHERNET | spezifischer Zweig | Zweig vorhanden | present |
| ip | generic_networking | NETWORK | IMPLEMENTED | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| udp | generic_networking | TRANSPORT | IMPLEMENTED | inherited_or_na | missing | UDP | spezifischer Zweig | UNVERIFIED | missing |
| tcp | generic_networking | TRANSPORT | IMPLEMENTED | inherited_or_na | missing | TCP | spezifischer Zweig | UNVERIFIED | missing |
| can | automotive | DATA_LINK | IMPLEMENTED | explicit | direct | CAN | spezifischer Zweig | Zweig vorhanden | present |
| can_fd | automotive | DATA_LINK | IMPLEMENTED | explicit | alias | CAN_FD | spezifischer Zweig | Zweig vorhanden | present |
| can_xl | automotive | DATA_LINK | EXPERIMENTAL | generic_bitrate | missing | CAN_XL | CAN_FD_PHASE_ESTIMATE (CAN_XL alias) | UNVERIFIED | missing |
| lin | automotive | DATA_LINK | IMPLEMENTED | explicit | direct | LIN | spezifischer Zweig | Zweig vorhanden | present |
| flexray | automotive | DATA_LINK | PARTIAL | generic_bitrate | missing | FLEXRAY | spezifischer Zweig | UNVERIFIED | missing |
| most | automotive | DATA_LINK | LEGACY | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| canopen | automotive | APPLICATION | IMPLEMENTED | generic_bitrate | alias | missing | GENERIC_ESTIMATE | UNVERIFIED | present |
| j1939 | automotive | APPLICATION | PARTIAL | generic_bitrate | alias | missing | GENERIC_ESTIMATE | UNVERIFIED | present |
| isobus | automotive | INDUSTRY_PROFILE | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| uds | automotive | APPLICATION | PLANNED | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| xcp | automotive | APPLICATION | PLANNED | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| ccp | automotive | APPLICATION | LEGACY | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| someip | automotive | APPLICATION | IMPLEMENTED | inherited_or_na | missing | SOME_IP | spezifischer Zweig | UNVERIFIED | missing |
| someip_sd | automotive | APPLICATION | PLANNED | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| doip | automotive | APPLICATION | PLANNED | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| obd2 | automotive | INDUSTRY_PROFILE | PLANNED | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| avb | automotive | INDUSTRY_PROFILE | PLANNED | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| tsn | generic_networking | INDUSTRY_PROFILE | PLANNED | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| profinet | industrial_automation | INDUSTRY_PROFILE | IMPLEMENTED | explicit | alias | PROFINET | GENERIC_ESTIMATE | UNVERIFIED | present |
| ethercat | industrial_automation | INDUSTRY_PROFILE | IMPLEMENTED | explicit | alias | ETHERCAT | GENERIC_ESTIMATE | UNVERIFIED | present |
| ethernet_ip | industrial_automation | APPLICATION | PARTIAL | generic_bitrate | alias | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| modbus_tcp | industrial_automation | APPLICATION | IMPLEMENTED | explicit | alias | MODBUS_TCP | GENERIC_ESTIMATE | UNVERIFIED | present |
| modbus_rtu | industrial_automation | APPLICATION | IMPLEMENTED | explicit | alias | MODBUS_RTU | GENERIC_ESTIMATE | UNVERIFIED | present |
| modbus_ascii | industrial_automation | APPLICATION | LEGACY | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| profibus_dp | industrial_automation | INDUSTRY_PROFILE | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| profibus_pa | process_industry | INDUSTRY_PROFILE | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| devicenet | industrial_automation | INDUSTRY_PROFILE | PLANNED | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| interbus | industrial_automation | INDUSTRY_PROFILE | LEGACY | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| cc_link | industrial_automation | INDUSTRY_PROFILE | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| cc_link_ie | industrial_automation | INDUSTRY_PROFILE | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| sercos_iii | industrial_automation | INDUSTRY_PROFILE | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| powerlink | industrial_automation | INDUSTRY_PROFILE | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| io_link | industrial_automation | INDUSTRY_PROFILE | PARTIAL | generic_bitrate | missing | IO_LINK | GENERIC_ESTIMATE | UNVERIFIED | missing |
| io_link_wireless | industrial_automation | INDUSTRY_PROFILE | EXPERIMENTAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| opc_ua | industrial_automation | APPLICATION | PARTIAL | inherited_or_na | missing | OPC_UA | GENERIC_ESTIMATE | UNVERIFIED | missing |
| opc_ua_pubsub | industrial_automation | APPLICATION | PARTIAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| mqtt | iot_wireless | APPLICATION | EXPERIMENTAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| sparkplug_b | industrial_automation | INDUSTRY_PROFILE | PLANNED | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| dds | robotics_ros | APPLICATION | IMPLEMENTED | inherited_or_na | missing | DDS | spezifischer Zweig | UNVERIFIED | present |
| ros2 | robotics_ros | INDUSTRY_PROFILE | IMPLEMENTED | inherited_or_na | missing | ROS_2 | spezifischer Zweig | UNVERIFIED | missing |
| arinc429 | aerospace | DATA_LINK | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| afdx | aerospace | INDUSTRY_PROFILE | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| mil_std_1553 | aerospace | DATA_LINK | PARTIAL | generic_bitrate | missing | MIL_STD_1553 | GENERIC_ESTIMATE | UNVERIFIED | missing |
| can_aerospace | aerospace | INDUSTRY_PROFILE | PLANNED | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| spacewire | aerospace | DATA_LINK | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| tte | aerospace | INDUSTRY_PROFILE | PLANNED | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| mvb | rail | DATA_LINK | PARTIAL | generic_bitrate | missing | MVB | GENERIC_ESTIMATE | UNVERIFIED | missing |
| wtb | rail | DATA_LINK | PARTIAL | generic_bitrate | missing | WTB | GENERIC_ESTIMATE | UNVERIFIED | missing |
| etb | rail | INDUSTRY_PROFILE | PLANNED | generic_bitrate | missing | ETB | GENERIC_ESTIMATE | UNVERIFIED | missing |
| trdp | rail | APPLICATION | PARTIAL | generic_bitrate | missing | TRDP | GENERIC_ESTIMATE | UNVERIFIED | missing |
| nmea0183 | marine | APPLICATION | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| nmea2000 | marine | INDUSTRY_PROFILE | PARTIAL | generic_bitrate | alias | missing | GENERIC_ESTIMATE | UNVERIFIED | present |
| iec61162 | marine | INDUSTRY_PROFILE | PLANNED | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| bacnet_ip | building_automation | APPLICATION | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | present |
| bacnet_mstp | building_automation | APPLICATION | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| bacnet_sc | building_automation | APPLICATION | EXPERIMENTAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| knx_tp | building_automation | INDUSTRY_PROFILE | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| knx_ip | building_automation | INDUSTRY_PROFILE | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| knx_rf | building_automation | INDUSTRY_PROFILE | PLANNED | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| lonworks | building_automation | INDUSTRY_PROFILE | LEGACY | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| dali | building_automation | APPLICATION | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| m_bus | building_automation | APPLICATION | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| wireless_m_bus | building_automation | APPLICATION | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| iec61850 | energy | INDUSTRY_PROFILE | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| mms | energy | APPLICATION | PLANNED | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| goose | energy | APPLICATION | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| sampled_values | energy | APPLICATION | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| dnp3 | energy | APPLICATION | PARTIAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| iec60870_5_101 | energy | APPLICATION | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| iec60870_5_104 | energy | APPLICATION | PARTIAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| sunspec_modbus | energy | INDUSTRY_PROFILE | PLANNED | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| ocpp | energy | APPLICATION | PLANNED | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| hart | process_industry | INDUSTRY_PROFILE | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| wirelesshart | process_industry | INDUSTRY_PROFILE | PLANNED | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| foundation_fieldbus_h1 | process_industry | INDUSTRY_PROFILE | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| i2c | embedded_systems | DATA_LINK | PARTIAL | generic_bitrate | direct | I2C | GENERIC_ESTIMATE | UNVERIFIED | missing |
| i3c | embedded_systems | DATA_LINK | EXPERIMENTAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| spi | embedded_systems | DATA_LINK | PARTIAL | generic_bitrate | direct | SPI | GENERIC_ESTIMATE | UNVERIFIED | missing |
| uart | embedded_systems | DATA_LINK | PARTIAL | generic_bitrate | missing | UART | GENERIC_ESTIMATE | UNVERIFIED | missing |
| rs232 | embedded_systems | PHYSICAL | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| rs422 | embedded_systems | PHYSICAL | PARTIAL | generic_bitrate | direct | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| rs485 | embedded_systems | PHYSICAL | PARTIAL | generic_bitrate | direct | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| one_wire | embedded_systems | DATA_LINK | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| usb | embedded_systems | DATA_LINK | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| pcie | embedded_systems | DATA_LINK | PARTIAL | generic_bitrate | missing | PCIE | GENERIC_ESTIMATE | UNVERIFIED | missing |
| mipi_csi2 | embedded_systems | DATA_LINK | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| mipi_dsi | embedded_systems | DATA_LINK | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| lvds | embedded_systems | PHYSICAL | PARTIAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| gpio | embedded_systems | PHYSICAL | PARTIAL | inherited_or_na | missing | direct_signal_exception | GENERIC_ESTIMATE | UNVERIFIED | missing |
| pwm | embedded_systems | PHYSICAL | PARTIAL | inherited_or_na | missing | direct_signal_exception | GENERIC_ESTIMATE | UNVERIFIED | missing |
| adc | embedded_systems | PHYSICAL | PARTIAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| dac | embedded_systems | PHYSICAL | PARTIAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| mqtt_sn | iot_wireless | APPLICATION | EXPERIMENTAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| coap | iot_wireless | APPLICATION | EXPERIMENTAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| http | iot_wireless | APPLICATION | EXPERIMENTAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| websocket | iot_wireless | APPLICATION | EXPERIMENTAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| amqp | iot_wireless | APPLICATION | EXPERIMENTAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| wifi | iot_wireless | DATA_LINK | EXPERIMENTAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| bluetooth_le | iot_wireless | DATA_LINK | EXPERIMENTAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| zigbee | iot_wireless | INDUSTRY_PROFILE | EXPERIMENTAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| thread | iot_wireless | INDUSTRY_PROFILE | EXPERIMENTAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| matter | iot_wireless | APPLICATION | EXPERIMENTAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| lorawan | iot_wireless | INDUSTRY_PROFILE | EXPERIMENTAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| lte_m | iot_wireless | DATA_LINK | EXPERIMENTAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| nb_iot | iot_wireless | DATA_LINK | EXPERIMENTAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| 5g | iot_wireless | DATA_LINK | EXPERIMENTAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| uwb | iot_wireless | DATA_LINK | EXPERIMENTAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| nfc | iot_wireless | DATA_LINK | EXPERIMENTAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| rfid | iot_wireless | INDUSTRY_PROFILE | EXPERIMENTAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| profisafe | industrial_automation | INDUSTRY_PROFILE | PLANNED | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| cip_safety | industrial_automation | INDUSTRY_PROFILE | PLANNED | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| fsoe | industrial_automation | INDUSTRY_PROFILE | PLANNED | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| opensafety | industrial_automation | INDUSTRY_PROFILE | PLANNED | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| generic_serial | custom | DATA_LINK | EXPERIMENTAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| generic_can | custom | DATA_LINK | EXPERIMENTAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| generic_ethernet | custom | DATA_LINK | EXPERIMENTAL | generic_bitrate | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| custom_udp | custom | APPLICATION | EXPERIMENTAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| custom_tcp | custom | APPLICATION | EXPERIMENTAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| custom_binary | custom | APPLICATION | EXPERIMENTAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| custom_text | custom | APPLICATION | EXPERIMENTAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
| custom_protocol | custom | APPLICATION | EXPERIMENTAL | inherited_or_na | missing | missing | GENERIC_ESTIMATE | UNVERIFIED | missing |
