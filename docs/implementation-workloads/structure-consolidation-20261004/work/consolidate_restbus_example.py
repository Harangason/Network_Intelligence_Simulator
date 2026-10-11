import ast
import json
from edit_utils import read, write, extract, apply

path = 'backend/nis/simulation/communication_generator.py'
source = read(path)
data = {}
lines = source.splitlines(keepends=True)
nodes = [node for node in ast.parse(source).body if isinstance(node,ast.Assign) and any(getattr(t,'id','') in {'DEFAULT_RESTBUS_PARTICIPANTS','ROLE_CYCLE_FALLBACK_MS'} for t in node.targets)]
for node in nodes:
    data[node.targets[0].id] = ast.literal_eval(node.value)
for node in reversed(nodes):
    del lines[node.lineno-1:node.end_lineno]
source = ''.join(lines)
write('backend/nis/industries/automotive/templates/restbus-example.json', json.dumps(data,ensure_ascii=False,indent=2) + '\n')
names = {'RestbusParticipant','clamp_channel','normalize_service_names','normalize_restbus_participant','default_restbus_participants','restbus_participants_from_request','participant_service_pairs','route_cycle_ms','build_restbus_routing_rows','restbus_interface_summary'}
chunk, source = extract(source, names)
write('backend/nis/communication/technologies/can/formats/restbus_example.py', '''"""Historical CAN-channel restbus example contract; no project defaults."""
from __future__ import annotations
import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple
from backend.nis.traces.trace_support import safe_identifier, parse_optional_int
from backend.nis.traces.trace_realism import contains_external_signal_records, external_signal_records
from backend.nis.communication.technologies.can.formats.routing import normalized_routing_row
from backend.nis.industries.automotive.templates import trace_example
_example = json.loads(Path(trace_example.__file__).with_name('restbus-example.json').read_text(encoding='utf-8'))
DEFAULT_RESTBUS_PARTICIPANTS = _example['DEFAULT_RESTBUS_PARTICIPANTS']
ROLE_CYCLE_FALLBACK_MS = _example['ROLE_CYCLE_FALLBACK_MS']
''' + '\n' + chunk)
source = source.replace('COMMON_NOMINAL_BITRATES =', 'from backend.nis.communication.technologies.can.formats.restbus_example import (' + ', '.join(sorted(names)) + ', DEFAULT_RESTBUS_PARTICIPANTS, ROLE_CYCLE_FALLBACK_MS)\n\nCOMMON_NOMINAL_BITRATES =',1)
chunk, source = extract(source, {'load_routing_table','write_routing_template'})
path_routing = 'backend/nis/communication/technologies/can/formats/routing.py'
write(path_routing, read(path_routing) + '\nimport csv\nfrom pathlib import Path\nfrom typing import Dict, List\nfrom backend.nis.communication.technologies.can.formats.trace_model import DEFAULT_ROUTING_ROWS\n\n' + chunk)
source = source.replace('import normalized_routing_row', 'import normalized_routing_row, load_routing_table, write_routing_template',1)
write(path, source)
apply('restbus-example-owner')
