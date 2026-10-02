import json,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from backend.communication.technologies import interbus as native_rules
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as r
folder=Path('docs/implementation-workloads/technology-full-parameter-audit-20261001')
original=next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='interbus')
keys={v['key']for v in original['form_parameters']};after={v['key']for v in r.parameter_fields('interbus')}
removed={k:v for k,v in native_rules.REMOVED.items()if k in keys-after}
native={v['key']:v['description']for v in native_rules.DECLARATIONS}
native['payload_bytes']='Actual selected process-data/PCP application bytes; directional image and rounded ID-register width are independent from service-size/peer limits and local PLC storage.'
spec={'technology':'interbus','native':native,'removed':removed,'sources':list(native_rules.SOURCES),'revisions':list(native_rules.SOURCES.values()),
 'scope':'Every declared INTERBUS form field individually reviewed. Qualified BC4000, AXC F IL ADAPT and PCI SC system coupler manuals have separate clock, fieldbus/local PLC, count, process image, PCP and factory-setting constraints; unspecified devices require actual own evidence.',
 'validation':{'isolated_sql':True,'suite':'full_parameter_audit + standard_defaults + profile_semantics + capacity_can_schedule + parameter_review + required_parameters + physical_profiles + serial_parameter_validity + unverified_technology_capacity + communication_dimensioning','passed':5736},
 'not_certified':['Full normative IEC61158 INTERBUS/PCP codecs and all controller/firmware variants not verified.',
 'BC4000 introduction has contradictory global256/512 station claims; neither becomes a universal ring default. Named equipment counts are qualified; master evidence remains actual.',
 'Other BC8x00 serial and BC9000 register columns excluded. Modelled BC ring formula applies only500k and does not include controller/master/K-bus/full functional response.',
 'Factory proposals are not project identity, discovery order, measured cable/power, actual firmware, confirmation or schedule evidence.',
 'PCI SC different master/slave rings and process/PCP words remain separate; no inferred universal246-byte process image or whole-system capacity.',
 'Canonical ring/binding resolution, hardware conformance and complete timing proof remain pending; capacity MODEL_MISSING']}
Path('work/interbus-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
