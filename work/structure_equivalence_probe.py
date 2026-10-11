"""Independent before/after observations for existing technology behavior."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.engineering.capacity.calculators import estimate_frame, can_frame_time_bound_ms

results = {}
for protocol in ['CAN', 'CAN_CLASSIC', 'CAN_FD', 'CANFD', 'LIN', 'ETHERNET', 'I2C', 'SPI',
                 'PWM', 'GPIO', 'CUSTOM', 'MODBUS_RTU', 'AUTOMOTIVE_ETHERNET']:
    for payload in [0, 1, 8, 9, 12, 64, 65, 1500]:
        for rate in [0, 19200, 500000, 2000000]:
            for options in [{}, {'can_fd_brs': False, 'can_frame_format': 'BASE_11'},
                            {'can_fd_brs': True, 'can_fd_dlc': 9, 'data_bitrate': 2000000},
                            {'eth_payload_layer': 'MAC_CLIENT', 'eth_upper_header_bytes': 0,
                             'eth_vlan_tags': 0, 'mtu_bytes': 1500, 'eth_ifg_bits': 96,
                             'eth_frame_profile': 'BASIC_MAC', 'duplex': 'FULL'}]:
                parameters = {'bitrate': rate, **options}
                key = json.dumps([protocol, payload, parameters], sort_keys=True)
                try:
                    results[key] = {'frame': estimate_frame(protocol, payload, parameters).to_dict(),
                                    'can_bound': can_frame_time_bound_ms(protocol, payload, parameters)}
                except Exception as error:
                    results[key] = {'error': type(error).__name__, 'message': str(error)}
results['profiles'] = hashlib.sha256(json.dumps(registry.profiles(), sort_keys=True).encode()).hexdigest()
output = ROOT / 'docs/implementation-workloads/structure-completion-20261003'
output.mkdir(parents=True, exist_ok=True)
label = sys.argv[1]
(output / f'equivalence-{label}.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
if label == 'after':
    before = json.loads((output / 'equivalence-before.json').read_text())
    differences = [key for key in results if results[key] != before.get(key)]
    (output / 'equivalence-comparison.json').write_text(json.dumps({'cases': len(results)-1,
        'profiles_equal': results['profiles']==before['profiles'], 'differences': differences}, indent=2))
    print('differences', len(differences), differences[:3])
    raise SystemExit(bool(differences))
print('observed cases', len(results)-1)
