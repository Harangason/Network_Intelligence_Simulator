"""Technology-owned PHY definition and preserved realization rules."""
from json import loads
from pathlib import Path
from backend.nis.communication.core.physical import PhysicalLayerProfile, MediumAccessModel

METADATA = loads(Path(__file__).with_name('physical.json').read_text(encoding='utf-8'))
PHY_PAIRS = METADATA.get('phy_pairs', {})
from backend.nis.communication.technologies.ethernet.physical import PHY_PAIRS

def resolve_profile(data, realization, profile):
    unresolved_modbus = False
    if profile and profile.id=='CCLINK_IE_VARIANT_EXPLICIT':
        variant=data.get('ccie_variant')
        phy=realization.phy_variant or data.get('ccie_phy')
        if variant in {'CONTROLLER','FIELD','FIELD_BASIC','TSN'} and phy in {'100BASE_TX','1000BASE_T','1000BASE_SX','SI_POF','SI_HPCF'}:
            topologies=('RING',) if variant=='CONTROLLER' and phy=='1000BASE_SX' else ('LINE','STAR','LINE_STAR') if variant=='FIELD_BASIC' else ('LINE','STAR','LINE_STAR','RING')
            access=MediumAccessModel.TOKEN_PASSING if variant in {'CONTROLLER','FIELD'} else MediumAccessModel.MASTER_SCHEDULED if variant=='FIELD_BASIC' else MediumAccessModel.VARIANT_DEPENDENT
            profile=PhysicalLayerProfile(profile.id,'cc_link_ie','TWISTED_PAIRS' if phy in PHY_PAIRS else 'OPTICAL_FIBER',(),
                                         PHY_PAIRS.get(phy),phy in PHY_PAIRS,'FULL_DUPLEX',topologies,None,access)
    return profile, unresolved_modbus

def validate_variant(data, realization, profile, finding, expected_pairs, resolved_access, unresolved_modbus):
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
    return profile, expected_pairs, resolved_access, unresolved_modbus
