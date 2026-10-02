import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.communication.technologies import iec101
folder=Path('docs/implementation-workloads/technology-full-parameter-audit-20261001')
original=next(v for v in json.loads((folder/'inventory-before.json').read_text(encoding='utf-8'))if v['technology']=='iec60870_5_101')
keys={v['key']for v in original['form_parameters']}
native={v['key']:v['description']for v in iec101.DECLARATIONS}
native['payload_bytes']='Actual encoded application data; separate type/header/IOA, FT1.2 control/link address/L/checksum/start/stop lengths and agreed device limits. No255-byte universal application payload or inherited Ethernet MTU.'
spec={'technology':'iec60870_5_101','native':native,'removed':{k:v for k,v in iec101.REMOVED.items()if k in keys},
 'sources':list(iec101.SOURCES),'revisions':list(iec101.SOURCES.values()),
 'scope':'Every IEC101 form parameter individually reviewed; balanced/unbalanced serial addressing, FT1.2 fixed/variable/E5 wire layout, separate ASDU/IOA/COT lengths and SQ encoding, actual serial/physical/schedule/command facts. Constructor and ABB defaults are implementation-qualified proposals.',
 'validation':{'isolated_sql':True,'suite':'full_parameter_audit + standard_defaults + profile_semantics + capacity_can_schedule + parameter_review + required_parameters + physical_profiles + serial_parameter_validity + unverified_technology_capacity + communication_dimensioning','passed':5178},
 'not_certified':['Pinned implementation source and ABB interoperability/settings support declarations, not complete all-edition IEC normative conformance; full applicable specification and device/firmware interoperability evidence remain required',
 'Source files stored for read-only fact verification; no upstream codec/state machine has been copied into or executed by NIS',
 'Actual link addresses/CA/IOA/type/quality/time encoding, serial wiring/parity/clock/modem/turnaround and polling/retry/queue schedule require canonical device evidence',
 'Frame-type/size constraints do not execute FT1.2 checksum/state/retransmission or ASDU commands, functional ACT_CON/ACT_TERM acceptance or correlated E2E capacity; runtime remains MODEL_MISSING',
 'A device setting outside normal8-bit FT1.2 serialization requires an explicitly proven encoding; vendor maxima/defaults are not arbitrary device guarantees']}
Path('work/iec101-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
