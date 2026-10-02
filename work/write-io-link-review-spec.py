import json,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from backend.communication.technologies import io_link as rules
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as r
folder=Path('docs/implementation-workloads/technology-full-parameter-audit-20261001')
original=next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='io_link')
keys={v['key']for v in original['form_parameters']};after={v['key']for v in r.parameter_fields('io_link')}
native={v['key']:v['description']for v in rules.DECLARATIONS}
native['payload_bytes']='Actual application data; directional cyclic PD max32 octets, indexed record data max232, full encoded ISDU max238 and direct page16 apply in separate explicitly selected channels.'
spec={'technology':'io_link','native':native,'removed':{k:v for k,v in rules.REMOVED.items()if k in keys-after},
 'sources':list(rules.SOURCES),'revisions':list(rules.SOURCES.values()),
 'scope':'Every declared wired IO-Link parameter individually reviewed against publisher V1.1.5 October2025 chapters4/5/7/10/AnnexA,B,F. COM discovery, port class, SIO, M-sequence, cycle encoding, process/ISDU/direct/event layouts and actual IODD/device sources remain separate; operating proposals never confirm capabilities.',
 'validation':{'isolated_sql':True,'suite':'full_parameter_audit + standard_defaults + profile_semantics + capacity_can_schedule + parameter_review + required_parameters + physical_profiles + serial_parameter_validity + unverified_technology_capacity + communication_dimensioning','passed':5905},
 'not_certified':['Publisher full PDF downloaded and relevant declared parameter chapters inspected; this does not certify every state-machine/codec/electrical/conformance clause.',
 'Only explicitly reviewed specification1.1.5; older wire protocol1.0 requires actual legacy source and has no automatically certified full legacy path. Draft2026 and wireless editions not inherited.',
 'IODD verification/hash/schema, actual port binding resolution, complete state-machine/ISDU/PDU codecs and master multi-port scheduling remain separate evidence requirements.',
 'Recommended TableA.11 TYPE_2_1 cycle proposals are not universal device minima. MinCycleTime code0 stays unknown and full estimate includes UART/interoctet/response/idle terms without capacity guarantee.',
 'Reserved/extension index ranges and physical current/Power2 checks do not prove actual device support, simultaneity, derating, isolation or complete normative compatibility.',
 'Real functional timing, observed trace, safety and complete E2E remain unverified; capacity MODEL_MISSING']}
Path('work/io-link-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
