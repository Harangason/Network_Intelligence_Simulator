"""Individual Generic Ethernet review using the previously verified IEEE schema."""
import json
from pathlib import Path
folder=Path('docs/implementation-workloads/technology-full-parameter-audit-20261001')
ethernet=json.loads((folder/'individual/ethernet.json').read_text(encoding='utf-8'))
native={record['key']:record['meaning_and_applicability_review']+
        '; independently assessed applicability to explicit IEEE802.3 Generic Ethernet: same MAC/PHY definition, not a CAN/custom transport fallback.'
        for record in ethernet['parameter_reviews'] if record['decision']=='NATIVE_OR_DECLARED_CONFIGURATION'}
removed={record['key']:record['meaning_and_applicability_review']+
         '; independently removed from Generic Ethernet; actual endpoint/higher-layer feature remains separate.'
         for record in ethernet['parameter_reviews'] if record['decision']=='REMOVED_NOT_APPLICABLE'}
spec={'technology':'generic_ethernet','native':native,'removed':removed,
 'sources':ethernet['sources'],'revisions':ethernet['source_revisions']+
 ['NIS Generic Ethernet explicitly represents IEEE802.3 using a shared reviewed schema, separately verified2026-10-01'],
 'scope':'All original and newly declared Generic Ethernet fields independently assessed. Reuses existing verified Ethernet field meanings/PHY/rates/MAC/client/tag/padding/flow/PLCA limits and dependencies; no duplicate guessed1G/8-byte/queue/sync defaults. Confirmed gigabit and jumbo configurations retain their own source-qualified actual values.',
 'validation':{'isolated_sql':True,'suite':'full_parameter_audit + standard_defaults + profile_semantics + capacity_can_schedule + parameter_review + required_parameters + physical_profiles','passed':0},
 'not_certified':['Generic Ethernet capacity/physical/queue executor wiring is not automatically aliased by shared parameter schema; MODEL_MISSING remains until explicit integration and independent actual link evidence',
 'Actual peer negotiation/up/duplex/flow/EEE/PLCA/path/queue source and runtime behavior; literature proposals are not confirmation',
 'Full normative IEEE802.3/802.1Q conformance and manufacturer extensions; source-qualified Ethernet review limits apply']}
(Path(__file__).parent/'generic-ethernet-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
