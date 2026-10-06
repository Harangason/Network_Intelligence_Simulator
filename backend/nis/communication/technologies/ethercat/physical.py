"""Technology-owned PHY definition and preserved realization rules."""
from json import loads
from pathlib import Path
from backend.nis.communication.core.physical import PhysicalLayerProfile, MediumAccessModel

METADATA = loads(Path(__file__).with_name('physical.json').read_text(encoding='utf-8'))
PHY_PAIRS = METADATA.get('phy_pairs', {})

def validate_medium(data, realization, profile, finding, expected_pairs, resolved_access, unresolved_modbus):
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
    return profile, expected_pairs, resolved_access, unresolved_modbus
