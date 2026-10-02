import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.communication.technologies import iec104
folder=Path('docs/implementation-workloads/technology-full-parameter-audit-20261001')
original=next(v for v in json.loads((folder/'inventory-before.json').read_text(encoding='utf-8'))if v['technology']=='iec60870_5_104')
keys={v['key']for v in original['form_parameters']}
removed={k:v for k,v in iec104.REMOVED.items()if k in keys}
removed['rate_limit_bit_s']='Removed inherited Ethernet shaper rate; IEC104 application has no physical bit-rate/shaper default. Actual lower transport/link shaping must be declared and verified in its own bound profile.'
native={v['key']:v['description']for v in iec104.DECLARATIONS}
native['payload_bytes']='Actual encoded application data; ASDU249, APCI lengthL253 and fullAPDU255 are separate limits, not TCP segment/Ethernet MTU/security overhead or generic payload255.'
spec={'technology':'iec60870_5_104','native':native,'removed':removed,
 'sources':list(iec104.SOURCES),'revisions':list(iec104.SOURCES.values()),
 'scope':'Every IEC104 form parameter individually reviewed; independently bound TCP/TLS path, source-qualified baseline versus constructor/vendor timers, I/S/U framing,15-bit APCI sequences/windows, ASDU address/VSQ encoding, actual device/redundancy/command evidence. No serial IEC101 or automatic Ethernet rate/default path.',
 'validation':{'isolated_sql':True,'suite':'full_parameter_audit + standard_defaults + profile_semantics + capacity_can_schedule + parameter_review + required_parameters + physical_profiles + serial_parameter_validity + unverified_technology_capacity + communication_dimensioning','passed':5325},
 'not_certified':['Pinned implementation and vendor interoperability document support these declarations, not full all-edition IEC/TLS/IEC62351 conformance; complete specifications and actual device/revision remain required',
 'Read-only upstream fact verification, no upstream codec/state machine imported or executed by NIS',
 'IANA UDP registration does not provide an executable UDP IEC104 model; only explicitly bound TCP/TLS paths are modeled here',
 'COM600 Maximum Message Length230 default retained as its own vendor setting; ambiguous wire scope is never silently converted to ASDU or APDU length',
 'Actual address/type/quality/time/security keys/trust/authorization, lower link/MTU/route, C ABI, redundancy assignment, buffer retention and TCP/APCI/application schedules require canonical evidence',
 'Length/sequence/window rules do not execute full TCP recovery/TLS record security/APCI state/redundancy behavior or prove functional ACT_CON/ACT_TERM/E2E acceptance; capacity remains MODEL_MISSING']}
Path('work/iec104-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
