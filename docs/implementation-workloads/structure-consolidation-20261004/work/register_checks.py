import json
from edit_utils import ROOT, read, write, REMOVALS, apply

assert json.loads(read('backend/nis/compatibility.json'))['backend.communication.technologies.catalog'] == 'backend.nis.communication.catalog'
REMOVALS.append('backend/communication/technologies/catalog.py')
write('backend/tests/test_structure_consolidation.py', (ROOT / 'docs/implementation-workloads/structure-consolidation-20261004/work/consolidation_tests.py').read_text(encoding='utf-8'))
path = 'scripts/migrations/structure_mapping.py'
source = read(path)
old = "row['status'] = 'RETAINED_COMPATIBLE' if row['action'] == 'move-with-forwarding-entry' else"
new = "row['status'] = ('RETAINED_COMPATIBLE' if (root / source).is_file() else 'IMPORT_ALIAS_ONLY') if row['action'] == 'move-with-forwarding-entry' else"
assert old in source
write(path, source.replace(old,new))
path = 'docs/migrations/structure-checks.json'
cases = json.loads(read(path))
cases['purpose'] = 'Protect technology ownership, actual algorithms, empty scaffolding retirement and prior R1-R5 regressions; independent of historical EA campaign'
case = next(case for case in cases['test_cases'] if case['test_id'] == 'STRUCTURE_02')
case['execution_plan'][0]['pytest_targets'].append('backend/tests/test_structure_consolidation.py')
# Source ranges are fixed after writing this JSON below in a second guarded batch.
write(path,json.dumps(cases,indent=2,ensure_ascii=False) + '\n')
path = 'scripts/tests/structure_checker_preflight.py'
write(path, read(path).replace("for name in ['backend/tests/test_structure_completion.py',", "for name in ['backend/tests/test_structure_consolidation.py', 'backend/tests/test_structure_completion.py',"))
path = 'docs/architecture/project-structure.md'
write(path, read(path) + '''

## Consequent consolidation (2026-10-04)

Native CAN message construction, BLF/DBC generation, CRC/bit packing and routing
now live in `communication/technologies/can`, including the historical archived
example and its preserved message API. Ethernet owns full-duplex port queues,
occupancy, restbus sessions and native frame records. IP, UDP, TCP, SOME/IP and
SOME/IP-SD own their existing encoding primitives. Shared trace files only export
compatibility contracts or orchestrate technology implementations.

The existing registry resolves scheduling and parameter-evidence adapters from
its registered timing owner. LIN native-clock evidence, CAN-FD independent phase
evidence and serial device-clock consistency no longer live in the general
assessment service. LIN forwarded-poll waits and reserve findings likewise have
a technology owner. These are moves of existing functionality, not support claims.

103 redundant physical technology forwarding files, the catalog forwarding file,
16 placeholder/alias-only package files and two empty frontend routes were removed.
Exact legacy imports remain in `compatibility.json`; published executable file
entrypoints remain. Five generator names still alias BaseGenerator and therefore
share its existing parent package. Ten unused handler extension namespaces map to
the existing handler package. No independent general physics implementation was
present: its empty namespace is retired, and old root imports retain access to
the existing industry templates. Workflow stage and automation packages stay:
they expose consumed stage/capability metadata and are not empty implementations.

Explicit automotive native-export demonstrations reside in industry template JSON;
their rates remain export options and do not become validated project defaults.
The distinct frozen and mutable historical format records remain distinct API
contracts; they are not competing engineering domain models.

Evidence and outstanding delivery state are recorded in
`docs/implementation-workloads/structure-consolidation-20261004`.
''')
path = 'backend/nis/communication/technologies/README.md'
write(path,read(path) + '''

Weitere tatsächliche Eigentümer: CAN `encoding.py` und `formats/` (native
Beispiele, Routing, BLF/DBC/MDF); Ethernet `runtime.py`, `restbus.py` und
`formats/trace_model.py`; IP/UDP/TCP/SOME-IP `encoding.py`; LIN `runtime.py`,
`parameters.py` und `assessment.py`; CAN FD `parameters.py` und
`request_response.py`. Die Registry löst Assessmentadapter über den vorhandenen
Timing-Eigentümer auf. Diese Ablage behauptet keine neuen Transportfähigkeiten.
Die gemeinsamen Trace-Formatimporte sind ausschließlich Kompatibilitätsexporte.
Architekturschutz: `backend/tests/test_structure_consolidation.py`.
''')
apply('broader-architecture-checks')
