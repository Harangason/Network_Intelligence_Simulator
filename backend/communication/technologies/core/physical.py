"""Explicit PHY and medium-access models; missing hardware never becomes a default."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Any


class MediumAccessModel(StrEnum):
    BITWISE_PRIORITY = "BITWISE_PRIORITY"
    MASTER_SCHEDULED = "MASTER_SCHEDULED"
    FULL_DUPLEX_SWITCHED = "FULL_DUPLEX_SWITCHED"
    MASTER_SLAVE = "MASTER_SLAVE"
    WIRED_AND_ARBITRATION = "WIRED_AND_ARBITRATION"
    POINT_TO_POINT = "POINT_TO_POINT"
    PLCA = "PLCA"
    TOKEN_PASSING = "TOKEN_PASSING"
    CENTRAL_SCHEDULED_FREQUENCY_HOPPING = "CENTRAL_SCHEDULED_FREQUENCY_HOPPING"
    VARIANT_DEPENDENT = 'VARIANT_DEPENDENT'
    CSMA_CD = 'CSMA_CD'


@dataclass(frozen=True)
class ArbitrationModel:
    id: str
    access: MediumAccessModel
    priority_source: str | None = None
    non_destructive: bool = False
    deterministic: bool = False
    worst_case_delay_model: str | None = None


@dataclass(frozen=True)
class PhysicalLayerProfile:
    id: str
    technology_id: str
    medium_type: str
    required_conductors: tuple[str, ...]
    pair_count: int | None
    differential: bool
    duplex_mode: str
    allowed_topologies: tuple[str, ...]
    termination_count: int | None
    access_model: MediumAccessModel
    arbitration: ArbitrationModel | None = None
    phy_variant: str | None = None


@dataclass(frozen=True)
class PhysicalRealization:
    id: str
    connection_id: str
    technology_id: str
    conductors: tuple[str, ...] | None
    pair_count: int | None
    topology: str | None
    termination_count: int | None
    phy_variant: str | None
    length_m: float | None
    chip_select_count: int | None
    slave_count: int | None
    available_channel_count: int | None
    used_channel_count: int | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PhysicalRealization:
        def integer(name: str) -> int | None:
            value = data.get(name)
            return value if isinstance(value, int) and not isinstance(value, bool) else None

        conductors = data.get("conductors")
        return cls(
            id=str(data.get("id") or ""), connection_id=str(data.get("connection_id") or ""),
            technology_id=str(data.get("technology_id") or data.get("technology") or "").lower().replace("-", "_"),
            conductors=tuple(str(value).upper() for value in conductors) if isinstance(conductors, list) else None,
            pair_count=integer("pair_count"), topology=str(data["topology"]).upper() if data.get("topology") else None,
            termination_count=integer("termination_count"),
            phy_variant=str(data["phy_variant"]).upper() if data.get("phy_variant") else None,
            length_m=float(data["length_m"]) if isinstance(data.get("length_m"), (int, float)) and not isinstance(data["length_m"], bool) else None,
            chip_select_count=integer("chip_select_count"), slave_count=integer("slave_count"),
            available_channel_count=integer("available_channel_count"), used_channel_count=integer("used_channel_count"),
        )


CAN_ARBITRATION = ArbitrationModel("CAN_NON_DESTRUCTIVE", MediumAccessModel.BITWISE_PRIORITY,
                                   priority_source="CAN_IDENTIFIER", non_destructive=True,
                                   deterministic=False, worst_case_delay_model="HIGHER_PRIORITY_INTERFERENCE")

PHYSICAL_PROFILES: dict[str, PhysicalLayerProfile] = {
    **{key:PhysicalLayerProfile('MODBUS_SERIAL_PHY_EXPLICIT',key,'EXPLICIT_SERIAL',(),None,
        False,'PHY_DEPENDENT',('BUS','LINE','POINT_TO_POINT'),None,MediumAccessModel.MASTER_SLAVE)
       for key in ('modbus_rtu','modbus_ascii')},
    'ethercat':PhysicalLayerProfile('ETHERCAT_CLASSIC_PHY_EXPLICIT','ethercat','EXPLICIT_ETHERNET_OR_EBUS',(),None,
                                   True,'FULL_DUPLEX',('LINE','RING','TREE','STAR'),None,MediumAccessModel.FULL_DUPLEX_SWITCHED),
    'cc_link_ie': PhysicalLayerProfile('CCLINK_IE_VARIANT_EXPLICIT','cc_link_ie','EXPLICIT_ETHERNET_OR_FIBER',(),None,
                                      False,'FULL_DUPLEX',('LINE','STAR','LINE_STAR','RING'),None,MediumAccessModel.VARIANT_DEPENDENT),
    'cc_link': PhysicalLayerProfile('CCLINK_DEDICATED_EIA485','cc_link','SHIELDED_THREE_CORE',('DA','DB','DG','SLD'),
                                    None,True,'HALF_DUPLEX',('BUS','LINE','T_BRANCH'),None,MediumAccessModel.MASTER_SCHEDULED,
                                    ArbitrationModel('CCLINK_BROADCAST_POLLING',MediumAccessModel.MASTER_SCHEDULED,deterministic=False)),
    'bluetooth_le': PhysicalLayerProfile('LE_RADIO_ACL', 'bluetooth_le', 'RADIO', (), None, False,
                                        'HALF_DUPLEX', ('POINT_TO_POINT','STAR','PICONET'), None,
                                        MediumAccessModel.CENTRAL_SCHEDULED_FREQUENCY_HOPPING,
                                        ArbitrationModel('LE_CENTRAL_ACL_EVENTS', MediumAccessModel.CENTRAL_SCHEDULED_FREQUENCY_HOPPING,
                                                         deterministic=False)),
    'bacnet_mstp': PhysicalLayerProfile('BACNET_MSTP_EIA485', 'bacnet_mstp', 'TWISTED_PAIR', ('A', 'B'),
                                      1, True, 'HALF_DUPLEX', ('BUS', 'LINE'), 2,
                                      MediumAccessModel.TOKEN_PASSING,
                                      ArbitrationModel('BACNET_MSTP_TOKEN', MediumAccessModel.TOKEN_PASSING,
                                                       deterministic=False)),
    "can": PhysicalLayerProfile("CAN_DIFFERENTIAL_PAIR", "can", "TWISTED_PAIR", ("CAN_H", "CAN_L"),
                                1, True, "HALF_DUPLEX", ("BUS", "LINE"), 2,
                                MediumAccessModel.BITWISE_PRIORITY, CAN_ARBITRATION),
    "can_xl": PhysicalLayerProfile("CAN_XL_PHY_EXPLICIT", "can_xl", "TWISTED_PAIR", ("CAN_H","CAN_L"),
                                   1, True, "HALF_DUPLEX", ("BUS","LINE"), 2,
                                   MediumAccessModel.BITWISE_PRIORITY,
                                   ArbitrationModel("CAN_XL_PRIORITY_11", MediumAccessModel.BITWISE_PRIORITY,
                                                    priority_source="CAN_XL_PRIORITY_ID",non_destructive=True,deterministic=False)),
    "lin": PhysicalLayerProfile("LIN_SINGLE_WIRE", "lin", "SINGLE_WIRE", ("LIN",),
                                0, False, "HALF_DUPLEX", ("BUS", "LINE"), None,
                                MediumAccessModel.MASTER_SCHEDULED),
    "i2c": PhysicalLayerProfile("I2C_SDA_SCL", "i2c", "PCB_TRACES", ("SDA", "SCL"),
                                0, False, "HALF_DUPLEX", ("BUS", "LINE"), None,
                                MediumAccessModel.WIRED_AND_ARBITRATION),
    "spi": PhysicalLayerProfile("SPI_SYNCHRONOUS", "spi", "PCB_TRACES", ("SCLK", "MOSI", "MISO"),
                                0, False, "FULL_DUPLEX", ("STAR", "POINT_TO_POINT"), None,
                                MediumAccessModel.MASTER_SLAVE),
    "rs485": PhysicalLayerProfile("RS485_DIFFERENTIAL", "rs485", "TWISTED_PAIR", ("A", "B"),
                                  1, True, "HALF_DUPLEX", ("BUS", "LINE"), 2,
                                  MediumAccessModel.MASTER_SLAVE),
    "rs422": PhysicalLayerProfile("RS422_DUAL_DIFFERENTIAL", "rs422", "TWISTED_PAIRS",
                                  ("TX+", "TX-", "RX+", "RX-"), 2, True, "FULL_DUPLEX",
                                  ("POINT_TO_POINT",), None, MediumAccessModel.POINT_TO_POINT),
    "ethernet": PhysicalLayerProfile("ETHERNET_PHY_EXPLICIT", "ethernet", "PHY_DEPENDENT", (), None,
                                     True, "PHY_DEPENDENT", ("STAR", "POINT_TO_POINT", "LINE"), None,
                                     MediumAccessModel.VARIANT_DEPENDENT),
}

PHY_PAIRS = {"10BASE_T1S": 1, "100BASE_T1": 1, "1000BASE_T1": 1,
             "10BASE_T":2,"100BASE_TX": 2, "1000BASE_T": 4,"2_5GBASE_T":4,"5GBASE_T":4,"10GBASE_T":4}

PROFILE_ALIASES = {
    'ble':'bluetooth_le', 'bluetoothle':'bluetooth_le', 'bluetooth_low_energy':'bluetooth_le',
    "can_fd": "can", "canopen": "can", "ccp": "can", "j1939": "can", "nmea2000": "can",
    "profinet": "ethernet",
    "ethernet_ip": "ethernet",
    "automotive_ethernet": "ethernet",
}


def physical_profile(technology_id: str) -> PhysicalLayerProfile | None:
    normalized = str(technology_id or "").lower().replace("-", "_")
    return PHYSICAL_PROFILES.get(PROFILE_ALIASES.get(normalized, normalized))


def validate_physical_realization(data: dict[str, Any]) -> dict[str, Any]:
    realization = PhysicalRealization.from_dict(data)
    profile = physical_profile(realization.technology_id)
    unresolved_modbus=False
    if profile and profile.id=='MODBUS_SERIAL_PHY_EXPLICIT':
        prefix='mr_' if realization.technology_id=='modbus_rtu' else 'ma_'
        phy=data.get(prefix+'phy') or realization.phy_variant
        modes={
            'RS485_2W':(('D0','D1','COMMON'),1,True,'HALF_DUPLEX',('BUS','LINE'),2),
            'RS485_4W':(('TXD0','TXD1','RXD0','RXD1','COMMON'),2,True,'FULL_DUPLEX',('BUS','LINE'),4),
            'RS232':(('TXD','RXD','COMMON'),0,False,'FULL_DUPLEX',('POINT_TO_POINT',),0),
        }
        if phy in modes:
            wires,pairs,differential,duplex,topologies,terminations=modes[phy]
            profile=PhysicalLayerProfile(profile.id,realization.technology_id,'SHIELDED_SERIAL',wires,pairs,
                differential,duplex,topologies,terminations,MediumAccessModel.MASTER_SLAVE,phy_variant=phy)
        else:unresolved_modbus=True
    if profile and profile.id=='CCLINK_IE_VARIANT_EXPLICIT':
        variant=data.get('ccie_variant')
        phy=realization.phy_variant or data.get('ccie_phy')
        if variant in {'CONTROLLER','FIELD','FIELD_BASIC','TSN'} and phy in {'100BASE_TX','1000BASE_T','1000BASE_SX','SI_POF','SI_HPCF'}:
            topologies=('RING',) if variant=='CONTROLLER' and phy=='1000BASE_SX' else ('LINE','STAR','LINE_STAR') if variant=='FIELD_BASIC' else ('LINE','STAR','LINE_STAR','RING')
            access=MediumAccessModel.TOKEN_PASSING if variant in {'CONTROLLER','FIELD'} else MediumAccessModel.MASTER_SCHEDULED if variant=='FIELD_BASIC' else MediumAccessModel.VARIANT_DEPENDENT
            profile=PhysicalLayerProfile(profile.id,'cc_link_ie','TWISTED_PAIRS' if phy in PHY_PAIRS else 'OPTICAL_FIBER',(),
                                         PHY_PAIRS.get(phy),phy in PHY_PAIRS,'FULL_DUPLEX',topologies,None,access)
    findings: list[dict[str, str]] = []
    resolved_access=profile.access_model.value if profile else None

    def finding(severity: str, code: str, message: str) -> None:
        findings.append({"severity": severity, "code": code, "message": message})

    if profile is None:
        finding("REVIEW", "PHYSICAL_PROFILE_MISSING", "No registered physical profile for this technology.")
    else:
        if unresolved_modbus:
            finding('REVIEW','MODBUS_SERIAL_PHY_UNKNOWN','Actual RS4852W/4W or RS232 must be selected; RTU does not imply RS485.')
        supplied_duplex={'FULL':'FULL_DUPLEX','HALF':'HALF_DUPLEX'}.get(data.get('duplex'),data.get('duplex'))
        if profile.id=='MODBUS_SERIAL_PHY_EXPLICIT' and not unresolved_modbus and supplied_duplex not in {None,profile.duplex_mode}:
            finding('BLOCKER','MODBUS_SERIAL_DUPLEX_MISMATCH','Duplex belongs to another selected serial electrical path.')
        if profile.id=='CCLINK_IE_VARIANT_EXPLICIT':
            variant=data.get('ccie_variant')
            phy=realization.phy_variant or data.get('ccie_phy')
            if variant not in {'CONTROLLER','FIELD','FIELD_BASIC','TSN'}:
                finding('REVIEW','CCLINK_IE_VARIANT_UNKNOWN','Actual CC-Link IE variant is required.')
            if phy not in {'100BASE_TX','1000BASE_T','1000BASE_SX','SI_POF','SI_HPCF'}:
                finding('REVIEW','CCLINK_IE_PHY_UNKNOWN','Actual CC-Link IE copper/fiber PHY is required.')
            valid_media={'CONTROLLER':{'1000BASE_T','1000BASE_SX'},'FIELD':{'1000BASE_T'},'FIELD_BASIC':{'100BASE_TX','1000BASE_T'},
                         'TSN':{'100BASE_TX','1000BASE_T','1000BASE_SX','SI_POF','SI_HPCF'}}
            if variant in valid_media and phy and phy not in valid_media[variant]:
                finding('BLOCKER','CCLINK_IE_PHY_NOT_APPLICABLE','PHY belongs to another CC-Link IE variant.')
            if phy in {'1000BASE_SX','SI_POF','SI_HPCF'} and realization.conductors:
                finding('BLOCKER','PHYSICAL_CONDUCTOR_MISMATCH','Optical media do not carry electrical bus conductors.')
            limits={'100BASE_TX':100,'1000BASE_T':100,'1000BASE_SX':550,'SI_POF':20,'SI_HPCF':100}
            if phy in limits and realization.length_m is not None and realization.length_m>limits[phy]:
                finding('BLOCKER','CCLINK_IE_LINK_LENGTH_EXCEEDED','Link length exceeds the selected medium baseline.')
            if variant=='TSN':
                finding('REVIEW','CCLINK_IE_TSN_SCHEDULE_UNKNOWN','Actual TSN class, clock and per-port gate/polling schedule remain required.')
        if profile.medium_type == 'RADIO' and realization.conductors:
            finding('BLOCKER','PHYSICAL_CONDUCTOR_MISMATCH','Radio links do not use wired bus conductors.')
        if realization.conductors is None and profile.required_conductors:
            finding("REVIEW", "PHYSICAL_CONDUCTORS_UNKNOWN", "Conductor assignment is not evidenced.")
        elif realization.conductors is not None:
            missing = set(profile.required_conductors) - set(realization.conductors)
            if missing:
                finding("BLOCKER", "PHYSICAL_CONDUCTOR_MISMATCH", f"Required conductors missing: {', '.join(sorted(missing))}.")
            if len(realization.conductors) != len(set(realization.conductors)):
                finding("BLOCKER", "PHYSICAL_CONDUCTOR_DUPLICATE", "Conductor names must be unique.")
        expected_pairs = PHY_PAIRS.get(realization.phy_variant) if profile.id == "ETHERNET_PHY_EXPLICIT" else profile.pair_count
        if profile.id=='ETHERCAT_CLASSIC_PHY_EXPLICIT':
            phy=realization.phy_variant
            if phy is None:
                finding('REVIEW','ETHERCAT_PHY_UNKNOWN','Actual classic EtherCAT100TX/100FX/EBUS/EtherCATP is required.')
            elif phy not in {'100BASE_TX','100BASE_FX','EBUS','ETHERCAT_P'}:
                finding('BLOCKER','ETHERCAT_PHY_NOT_APPLICABLE','Selected PHY is not registered for classic100M EtherCAT.')
            if phy=='100BASE_TX': expected_pairs=2
            if phy=='100BASE_FX' and realization.conductors:
                finding('BLOCKER','PHYSICAL_CONDUCTOR_MISMATCH','OpticalEtherCAT doesnot carry electrical bus conductors.')
            if data.get('duplex') not in {None,'FULL'}:
                finding('BLOCKER','ETHERCAT_DUPLEX_MISMATCH','Classic EtherCAT requires full-duplex.')
        if profile.id=='ETHERNET_PHY_EXPLICIT':
            duplex=data.get('duplex')
            if realization.phy_variant=='10BASE_T1S':
                plca=data.get('eth_plca_enabled',data.get('plca_enabled'))
                if type(plca) is not bool:
                    finding('REVIEW','ETHERNET_ACCESS_UNKNOWN','10BASE-T1S PLCA enable state is not evidenced; pure CSMA/CD is possible.')
                else:
                    resolved_access=MediumAccessModel.PLCA.value if plca else MediumAccessModel.CSMA_CD.value
                if duplex not in {None,'HALF'}:
                    finding('BLOCKER','ETHERNET_DUPLEX_MISMATCH','Reviewed10BASE-T1S operates half-duplex, not switched full-duplex.')
            elif realization.phy_variant in {'100BASE_T1','1000BASE_T1'}:
                resolved_access=MediumAccessModel.FULL_DUPLEX_SWITCHED.value
                if duplex not in {None,'FULL'}:
                    finding('BLOCKER','ETHERNET_DUPLEX_MISMATCH','Selected single-pair PHY requires full-duplex.')
            elif duplex in {'FULL','HALF'}:
                resolved_access=MediumAccessModel.FULL_DUPLEX_SWITCHED.value if duplex=='FULL' else MediumAccessModel.CSMA_CD.value
                if duplex=='HALF' and realization.phy_variant in {'2_5GBASE_T','5GBASE_T','10GBASE_T'}:
                    finding('BLOCKER','ETHERNET_DUPLEX_MISMATCH','Reviewedmulti-gigabit PHY requires full-duplex.')
            else:
                finding('REVIEW','ETHERNET_DUPLEX_UNKNOWN','Actual negotiated/forced duplex is not evidenced.')
        if profile.id == "ETHERNET_PHY_EXPLICIT" and not realization.phy_variant:
            finding("REVIEW", "ETHERNET_PHY_UNKNOWN", "Ethernet PHY variant is not evidenced.")
        elif profile.id == "ETHERNET_PHY_EXPLICIT" and expected_pairs is None:
            finding("BLOCKER", "ETHERNET_PHY_UNSUPPORTED", "Ethernet PHY variant is not registered.")
        if expected_pairs is not None:
            if realization.pair_count is None:
                finding("REVIEW", "PHYSICAL_PAIR_COUNT_UNKNOWN", "Physical pair count is not evidenced.")
            elif realization.pair_count != expected_pairs:
                finding("BLOCKER", "PHYSICAL_PAIR_COUNT_MISMATCH", "Pair count is incompatible with the physical profile.")
        allowed_topologies = (("BUS", "LINE") if realization.phy_variant == "10BASE_T1S"
                              and profile.id == "ETHERNET_PHY_EXPLICIT" else profile.allowed_topologies)
        if realization.topology is None:
            finding("REVIEW", "PHYSICAL_TOPOLOGY_UNKNOWN", "Physical topology is not evidenced.")
        elif realization.topology not in allowed_topologies:
            finding("BLOCKER", "PHYSICAL_TOPOLOGY_INVALID", "Topology is incompatible with the physical profile.")
        if profile.termination_count is not None:
            if realization.termination_count is None:
                finding("REVIEW", "PHYSICAL_TERMINATION_UNKNOWN", "Termination count is not evidenced.")
            elif realization.termination_count != profile.termination_count:
                finding("BLOCKER", "PHYSICAL_TERMINATION_INVALID", "Termination count is incompatible with the bus profile.")
        if profile.id == "SPI_SYNCHRONOUS":
            if realization.slave_count is None or realization.chip_select_count is None:
                finding("REVIEW", "SPI_RESOURCE_COUNT_UNKNOWN", "SPI slave and chip-select resources are not fully evidenced.")
            elif realization.chip_select_count < realization.slave_count:
                finding("BLOCKER", "SPI_CHIP_SELECT_EXHAUSTED", "More SPI slaves than available chip selects.")
    if realization.length_m is not None and (not isfinite(realization.length_m) or realization.length_m < 0):
        finding("BLOCKER", "PHYSICAL_LENGTH_INVALID", "Physical length must be a finite non-negative value.")
    if (realization.used_channel_count is not None and realization.available_channel_count is not None and
            realization.used_channel_count > realization.available_channel_count):
        finding("BLOCKER", "PHYSICAL_CHANNEL_LIMIT_EXCEEDED", "Used physical channels exceed hardware capability.")
    return {
        "realization_id": realization.id, "technology_id": realization.technology_id,
        "physical_layer_profile_id": profile.id if profile else None,
        "resolved_medium_access_model": resolved_access,
        "status": "INVALID" if any(item["severity"] == "BLOCKER" for item in findings) else
                  "REVIEW_REQUIRED" if findings else "VALID",
        "findings": findings,
    }
