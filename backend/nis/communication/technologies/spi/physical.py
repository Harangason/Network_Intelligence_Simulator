"""Technology-owned PHY definition and preserved realization rules."""
from json import loads
from pathlib import Path
from backend.nis.communication.core.physical import PhysicalLayerProfile, MediumAccessModel

METADATA = loads(Path(__file__).with_name('physical.json').read_text(encoding='utf-8'))
PHY_PAIRS = METADATA.get('phy_pairs', {})

def validate_resources(data, realization, profile, finding, expected_pairs, resolved_access, unresolved_modbus):
    if profile.id == "SPI_SYNCHRONOUS":
        if realization.slave_count is None or realization.chip_select_count is None:
            finding("REVIEW", "SPI_RESOURCE_COUNT_UNKNOWN", "SPI slave and chip-select resources are not fully evidenced.")
        elif realization.chip_select_count < realization.slave_count:
            finding("BLOCKER", "SPI_CHIP_SELECT_EXHAUSTED", "More SPI slaves than available chip selects.")
    return profile, expected_pairs, resolved_access, unresolved_modbus
