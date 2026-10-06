"""Technology-owned PHY definition and preserved realization rules."""
from json import loads
from pathlib import Path
from backend.nis.communication.core.physical import PhysicalLayerProfile, MediumAccessModel

METADATA = loads(Path(__file__).with_name('physical.json').read_text(encoding='utf-8'))
PHY_PAIRS = METADATA.get('phy_pairs', {})

def expected_pairs(data, realization, profile, finding, expected_pairs, resolved_access, unresolved_modbus):
    expected_pairs = PHY_PAIRS.get(realization.phy_variant) if profile.id == "ETHERNET_PHY_EXPLICIT" else profile.pair_count
    return profile, expected_pairs, resolved_access, unresolved_modbus

def validate_access(data, realization, profile, finding, expected_pairs, resolved_access, unresolved_modbus):
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
    return profile, expected_pairs, resolved_access, unresolved_modbus

def validate_phy_selection(data, realization, profile, finding, expected_pairs, resolved_access, unresolved_modbus):
    if profile.id == "ETHERNET_PHY_EXPLICIT" and not realization.phy_variant:
        finding("REVIEW", "ETHERNET_PHY_UNKNOWN", "Ethernet PHY variant is not evidenced.")
    elif profile.id == "ETHERNET_PHY_EXPLICIT" and expected_pairs is None:
        finding("BLOCKER", "ETHERNET_PHY_UNSUPPORTED", "Ethernet PHY variant is not registered.")
    return profile, expected_pairs, resolved_access, unresolved_modbus

def allowed_topologies(realization, profile):
    allowed_topologies = (("BUS", "LINE") if realization.phy_variant == "10BASE_T1S"
                          and profile.id == "ETHERNET_PHY_EXPLICIT" else profile.allowed_topologies)
    return allowed_topologies
