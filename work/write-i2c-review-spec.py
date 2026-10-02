import json
from pathlib import Path
from backend.communication.technologies import i2c
native={row[0]:row[-1] for row in i2c.DECLARATIONS}
native.update({'local_timing_evidence.'+f['key']:f['description'] for f in i2c.local_fields()})
native['payload_bytes']='Actual application/encoded data octets, no255-byte I2C maximum or8-byte default. Complete transaction includes all address/register/ninth-clock/repeatedSTART and optionalHS-entry phases.'
native['bitrate']='Actual mode-specific active I2C clock; 100000 bit/s Standard is a literature proposal, not a minimum clock or confirmed transaction/capacity. Sm/Fm/Fm+/HS/UFm have separate rate and physical constraints.'
inventory=json.loads(Path('docs/implementation-workloads/technology-full-parameter-audit-20261001/inventory-before.json').read_text(encoding='utf-8'))
original={f['key'] for item in inventory if item['technology']=='i2c' for f in item['form_parameters']}
spec={'technology':'i2c','native':native,'removed':{key:meaning for key,meaning in i2c.REMOVED.items() if key in original},
 'sources':[i2c.SOURCE],'revisions':[i2c.REVISION],
 'scope':'Each I2C form and local device field reviewed independently. Five operating categories and load-dependentHS timing. Port roles differ from target addressing and complete transaction proof.100k Standard is a review proposal, not capacity evidence. No CAN/SMBus/Ethernet fallback.',
 'validation':{'isolated_sql':True,'suite':'full_parameter_audit + standard_defaults + profile_semantics + capacity_can_schedule + parameter_review + required_parameters + physical_profiles','passed':0},
 'not_certified':['Actual datasheets/pins/voltage/load/pullup/unique addresses, HS mixed-mode/load timing, reserved services and switch/buffer topology require installation evidence',
 'Local bound validation sizes declared transaction clocks and HS entry only; not a byte-level ACK/address/arbitration/recovery state-machine simulator or electrical proof',
 'Complete device/register/combined layouts, actual retry/stretch/competing-controller schedules, correlated E2E timing and safety acceptance are not inferred from default frequency']}
Path('work/i2c-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
