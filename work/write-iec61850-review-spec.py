import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path.cwd()))
from backend.communication.technologies import iec61850
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as r
folder=Path('docs/implementation-workloads/technology-full-parameter-audit-20261001')
original=next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='iec61850')
keys={v['key']for v in original['form_parameters']};after={v['key']for v in r.parameter_fields('iec61850')}
removed={k:v for k,v in iec61850.REMOVED.items()if k in keys}
if 'rate_limit_bit_s'in keys-after:removed['rate_limit_bit_s']='Removed inherited Ethernet shaping parameter; actual selected ACSI service has an independent registered transport/link profile, no universal physical/shaper clock.'
native={v['key']:v['description']for v in iec61850.DECLARATIONS}
native['payload_bytes']='Actual selected ACSI application encoding; MMS BER PDU, L2 GOOSE/SV,90-5 routing/security and XML/XMPP have independent sizes and accepted mapping-specific bounds, no global1500 or65535.'
spec={'technology':'iec61850','native':native,'removed':removed,'sources':list(iec61850.SOURCES),'revisions':list(iec61850.SOURCES.values()),
 'scope':'Every declared IEC61850 form parameter individually reviewed; selected ACSI service/SCSM and SCL/edition/firmware scope independent from industry. MMS reporting/control/file/log/setting groups, direct GOOSE/SV, routed90-5 and XMPP require separate explicit bindings/evidence. Factory settings only source-qualified by implementation/build/role; addresses/model/state remain unknown.',
 'validation':{'isolated_sql':True,'suite':'full_parameter_audit + standard_defaults + profile_semantics + capacity_can_schedule + parameter_review + required_parameters + physical_profiles + serial_parameter_validity + unverified_technology_capacity + communication_dimensioning','passed':5614},
 'not_certified':['Public IEC scopes/metadata/SCL preview and pinned primary library sources were verified; full all-edition normative ACSI/SCSM/SCL/IEC62351 specifications not obtained.',
 'Pinned v1.6 upstream code inspected read-only as evidence, not imported/executed as NIS codec/runtime. Qualified implementation factory settings are unconfirmed proposals.',
 'API report bitmasks differ from raw wire bit ordering; no general ACSI wire mask or full BER/XML codec is inferred from them.',
 'Full object/dataset/service conformance, actual PICS/PIXIT, SCL schema/mixed-version rights and canonical selected lower path need separate proof.',
 'GOOSE/SV and90-5 require their own registered service parameters/encoding/address/clock/security schedule; family selection does not prove these paths. Pinned library marks routable services BETA and does not implement XMPP.',
 'Actual identity/addresses/quality/time/trust/authorization, report retention/segmentation and functional control termination/latency/safety remain unverified; capacity MODEL_MISSING, no complete E2E guarantee']}
Path('work/iec61850-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
