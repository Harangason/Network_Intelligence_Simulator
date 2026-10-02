import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path.cwd()))
from backend.communication.technologies import iec61162
folder=Path('docs/implementation-workloads/technology-full-parameter-audit-20261001')
original=next(v for v in json.loads((folder/'inventory-before.json').read_text(encoding='utf-8'))if v['technology']=='iec61162')
keys={v['key']for v in original['form_parameters']}
removed={k:v for k,v in iec61162.REMOVED.items()if k in keys}
native={v['key']:v['description']for v in iec61162.DECLARATIONS}
native['payload_bytes']='Actual application encoding for selected part; serial inner79/wire82, classicCAN8/FastPacket223 and IP/binary fragment layouts differ. No global1500 or65535 maximum/default.'
spec={'technology':'iec61162','native':native,'removed':removed,'sources':list(iec61162.SOURCES),'revisions':list(iec61162.SOURCES.values()),
 'scope':'Every declared IEC61162 parameter individually reviewed: independent serial1/2, NMEA2000 CAN3, IP450 and450+460 paths; explicit edition/device/role/content binding, qualified legacy serial clock/proposals, sentence versus wire lengths, CAN PGN transport bounds, named-device multicast group/address/port consistency and actual security/physical/schedule facts.',
 'validation':{'isolated_sql':True,'suite':'full_parameter_audit + standard_defaults + profile_semantics + capacity_can_schedule + parameter_review + required_parameters + physical_profiles + serial_parameter_validity + unverified_technology_capacity + communication_dimensioning','passed':5459},
 'not_certified':['Current IEC and NMEA full normative specifications were not obtained. Public publisher scopes and indexed device tables do not verify complete all-edition conformance.',
 'Manufacturer PDF direct requests returned403; indexed primary specification excerpts were verified only for documented named device/legacy edition and cannot certify2024 electrical/codec/security tables.',
 'Fast Packet source report says31 frames for223 bytes, but complete first-frame/counter layout was not accessible. No fabricated frame-count maximum/default; normative encoding remains open.',
 'Actual unique CAN address/NAME, PGN/SFI, port/PHY/binding, listener loading, envelope/tags, security/trust, device services and multi-path arbitration/functional timing need canonical evidence.',
 '460 public add-on scope does not prove isolation/redundancy/authentication/collision-monitoring or full conformance of a named450-only device.',
 'Schema validation and operating proposals do not prove actual capacity or execute all part codecs/checksums/CAN/IP recovery/security; capacity remains MODEL_MISSING']}
Path('work/iec61162-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
