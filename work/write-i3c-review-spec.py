import json
from pathlib import Path
from backend.communication.technologies import i3c
folder=Path('docs/implementation-workloads/technology-full-parameter-audit-20261001')
original=next(item for item in json.loads((folder/'inventory-before.json').read_text(encoding='utf-8')) if item['technology']=='i3c')
keys={f['key'] for f in original['form_parameters']}
native={f['key']:f['description'] for f in i3c.DECLARATIONS}
native['payload_bytes']='Actual meaningful data; absent negotiated MRL/MWL is not a65535-byte universal cap. Read/write direction uses its own accepted limit; HDR padding and command/IBI/layout overhead remain separate.'
spec={'technology':'i3c','native':native,'removed':{key:meaning for key,meaning in i3c.REMOVED.items() if key in keys},
 'sources':list(i3c.REVISIONS),'revisions':list(i3c.REVISIONS.values()),
 'scope':'Each I3C form field reviewed independently. Seven version/flavour identities, separate OD/PP/legacy/initial clocks, qualified SDK factory proposals, actual addressing/capability/PHY/transaction facts. SDR baseline does not confirm physical installation or capacity.',
 'validation':{'isolated_sql':True,'suite':'full_parameter_audit + standard_defaults + profile_semantics + capacity_can_schedule + parameter_review + required_parameters + physical_profiles + serial_parameter_validity + unverified_technology_capacity + communication_dimensioning','passed':0},
 'not_certified':['Public MIPI FAQ and exact vendor documents support declared rules, not full-version normative conformance; complete specification/errata and peer datasheets remain required',
 'Microchip online tables require exact device PDF comparison; these declarations are qualified proposals/constraints, not board measurements',
 'Actual voltage/keeper/pull-up/drive/edge/capacitance/stub/turnaround and phase clocks require hardware evidence; STM32 and PIC limits do not transfer to arbitrary chips',
 'Full SDR/HDR/ML codecs, parity/CRC/state-machine execution, actual DAA/IBI/handoff/recovery schedule, correlated E2E safety and capacity remain MODEL_MISSING',
 'Actual address uniqueness, negotiated lengths/rejected values/CCC formats and revision-dependent capability register semantics require canonical device evidence']}
Path('work/i3c-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
