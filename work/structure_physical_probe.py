from pathlib import Path
import importlib.util
import itertools
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.nis.communication.core import physical
out = ROOT / 'docs/implementation-workloads/structure-completion-20261003'
path = out / 'before/physical-owners/backend/nis/communication/core/physical.py'
spec = importlib.util.spec_from_file_location('structure_before_physical', path)
old = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = old
spec.loader.exec_module(old)
technologies = sorted(set(old.PHYSICAL_PROFILES) | set(old.PROFILE_ALIASES) | {'unknown'})
variants = [None, '10BASE_T1S', '100BASE_T1', '1000BASE_T', '100BASE_FX', 'EBUS', 'RS485_2W', 'RS232', 'INVALID']
cases, differences = [], []
for technology, variant, duplex, full in itertools.product(technologies, variants, [None, 'FULL', 'HALF'], [False, True]):
    data = {'id': 'physical-equivalence', 'technology_id': technology, 'phy_variant': variant, 'duplex': duplex}
    if full:
        data.update(conductors=['CAN_H', 'CAN_L'], pair_count=1, topology='BUS', termination_count=2,
                    length_m=200, slave_count=3, chip_select_count=2, ccie_variant='FIELD',
                    mr_phy=variant, ma_phy=variant, eth_plca_enabled=False)
    expected = old.validate_physical_realization(data)
    actual = physical.validate_physical_realization(data)
    cases.append({'input': data, 'expected': expected})
    if expected != actual: differences.append({'input': data, 'expected': expected, 'actual': actual})
(out / 'physical-equivalence.json').write_text(json.dumps({'cases': len(cases), 'differences': differences}, indent=2))
(out / 'physical-reference.json').write_text(json.dumps(cases, indent=2))
print(json.dumps({'cases': len(cases), 'differences': len(differences)}))
assert not differences
