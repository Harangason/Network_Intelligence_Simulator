"""Technology-owned PHY definition and preserved realization rules."""
from json import loads
from pathlib import Path
from backend.nis.communication.core.physical import PhysicalLayerProfile, MediumAccessModel

METADATA = loads(Path(__file__).with_name('physical.json').read_text(encoding='utf-8'))
PHY_PAIRS = METADATA.get('phy_pairs', {})

def resolve_profile(data, realization, profile):
    unresolved_modbus = False
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
    return profile, unresolved_modbus

def validate_duplex(data, realization, profile, finding, expected_pairs, resolved_access, unresolved_modbus):
    if unresolved_modbus:
        finding('REVIEW','MODBUS_SERIAL_PHY_UNKNOWN','Actual RS4852W/4W or RS232 must be selected; RTU does not imply RS485.')
    supplied_duplex = {'FULL':'FULL_DUPLEX','HALF':'HALF_DUPLEX'}.get(data.get('duplex'),data.get('duplex'))
    if profile.id=='MODBUS_SERIAL_PHY_EXPLICIT' and not unresolved_modbus and supplied_duplex not in {None,profile.duplex_mode}:
        finding('BLOCKER','MODBUS_SERIAL_DUPLEX_MISMATCH','Duplex belongs to another selected serial electrical path.')
    return profile, expected_pairs, resolved_access, unresolved_modbus
