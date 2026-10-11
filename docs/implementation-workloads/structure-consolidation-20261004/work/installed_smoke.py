"""Verify the built wheel without importing the checkout's backend."""
import hashlib
import importlib
import json
from pathlib import Path
import sys

installed = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
checkout = Path(__file__).resolve().parents[4]
verified_sources = 0
for path in (checkout/'backend/nis').rglob('*'):
    if path.is_file() and path.suffix in {'.py','.json'} and '__pycache__' not in path.parts:
        shipped = installed/path.relative_to(checkout)
        assert shipped.is_file(), path
        assert path.read_bytes().replace(b'\r\n',b'\n') == shipped.read_bytes().replace(b'\r\n',b'\n'), path
        verified_sources += 1
sys.path.insert(0,str(installed))
sys.path.insert(1,str(installed/'backend'))
import backend
assert Path(backend.__file__).resolve().is_relative_to(installed)
from backend.nis.compatibility import ALIASES
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
from backend.nis.traces.formats.common_trace import build_can_trace, build_ethernet_trace, build_udp_ipv4_ethernet_packet
from backend.nis.simulation.communication_generator import default_restbus_participants, build_restbus_routing_rows
assert len(DEFAULT_TECHNOLOGY_REGISTRY.profiles()) == 125
frames = build_can_trace(.1,2,1,'fd',42,1700000000)
ethernet = build_ethernet_trace(.1,2,42,1700000000)
assert len(frames) == 2 and len(ethernet) == 32
assert len(build_udp_ipv4_ethernet_packet(ethernet[0])) == 102
assert build_restbus_routing_rows(default_restbus_participants(2),2)
checked = []
for old,canonical in ALIASES.items():
    if old.startswith(('backend.communication.technologies','backend.specializations.technologies',
                       'communication.technologies','specializations.technologies')):
        assert importlib.import_module(old) is importlib.import_module(canonical)
        checked.append(old)
for folder in ('backend/communication/technologies','backend/specializations/technologies'):
    assert not (installed/folder).exists(), 'Retired source tree must not ship in the wheel'
from backend.nis.simulation.communication_simulator import _native_configuration
assert _native_configuration.__module__ == 'backend.nis.communication.technologies.can.formats.native_configuration'
wheel = installed.parent/'wheel/communication_simulator-0.1.0-py3-none-any.whl'
result = {'status':'PASS','installed_backend':str(Path(backend.__file__).resolve()),
          'canonical_source_files_exact':verified_sources,
          'source_checkout_imported':False,'wheel_sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),
          'profiles':125,'legacy_module_identities':len(checked),'can_frames':len(frames),'ethernet_frames':len(ethernet)}
output.write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
