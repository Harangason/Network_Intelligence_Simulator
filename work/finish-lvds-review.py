"""Finish the LVDS audit only with a current real isolated regression receipt."""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import lvds as m

folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001'
xml=folder/'individual/lvds-tests.xml'
for relative in ('backend/communication/technologies/lvds.py','backend/communication/technologies/catalog.py',
                 'backend/communication/technologies/core/components.py','backend/tests/test_technology_full_parameter_audit.py'):
    assert xml.stat().st_mtime_ns >= (root/relative).stat().st_mtime_ns,('stale test receipt',relative)
suites=ET.parse(xml).findall('.//testsuite')
assert suites and all(int(v.get(k,'0'))==0 for v in suites for k in ('failures','errors','skipped'))
count=sum(int(v.get('tests','0'))for v in suites);assert count>8106,count
original=next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='lvds')
before={v['key']for v in original['form_parameters']};after={v['key']for v in registry.parameter_fields('lvds')}
native={v['key']:v['description']for v in m.DECLARATIONS}
native['payload_bytes']='Actual application/codec byte length, not an LVDS electrical frame, lane word width or universal8byte/65535byte standard. Non-byte word codecs require their own registered description; no physical payload maximum/default.'
spec=dict(technology='lvds',native=native,removed={k:m.REMOVED[k]for k in before-after},
 sources=list(m.SOURCES),revisions=list(m.SOURCES.values()),scope=[
  'Each declared field independently reviewed for meaning/applicability, scalar type/unit/bounds, source/revision and context-qualified proposal. Remaining NIS scenario requirements are not LVDS standards or board measurements.',
  'TI owners FourthEdition2008, SLLA108A2013 table1/full-load discussion and exact DS90LV047A/048A2016 revision tables/footnotes read. Numerical min/typ/max columns visually checked. Primary author summaries do not certify the full licensed TIA standards or future revisions.',
  '644 point-to-point,644A qualified multidrop and899 multipoint use distinct output/current/load/pin/leakage/transition envelopes and receiver types. SLLA108A offset prose conflicts with its table: exact1.125..1.375V table and corroborating device specifications used.32 DCfull-load fixtures are not commissioned population or at-speed capacity.',
  'Per-lane bit clock/UI, word clock/width, separate clock pairs and aggregate data rate independently checked. Start-stop2bits and8b/10b retain their own ratios; no universal7:1serializer, mandatory8b/10b,3000Mbit/s, frame/address/CRC or CANqueue/QoS/retry fallback.',
  'Single versus parallel end terminations, mid-line loading proof, actual current times resistance and receiver DCcommon-mode from TXoffset/ground shift/coupled noise independently modeled. Design100ohm and exact-chip3.3V are proposals, not installed measurements.',
  'Exact2016 four-channel chip supply/ambient/ACload/delay/skew bounds and guaranteed alternating-waveform fMAXminimum200MHz distinct from250MHztypical and actual word clock.400Mbit/s is the guaranteed reference envelope, not an absolute silicon speed maximum; higher measured operation requires separate qualification.',
  'Receiver ACcommon-mode depends on actual amplitude:200mV→0.1..2.3V,400mV→0.2..2.2V,800mV→0.4..2V. Exact decimal evaluation selected for these closed derived bounds; existing interpolation rules retain their arithmetic. Normal-data ACbounds do not apply to shorted/floating fault tests.',
  '047A DC-only requirements, ACstream balance/startup/idle proof,048fault-specific HIGH/no externally imposed shortedCM/10mVfloatingnoise and899Type2LOW/wiredORHIGH ownership distinguished. Electrical failsafe is not functional safety acceptance.',
  'Actual clock/voltage/current/noise/load/population/device identity/coding/fault/confirmation and capacity have no invented defaults. Qualified fixture/reference/design proposals carry exact source/revision/selectors.',
  f'Selected ten-file regression{count}PASS in isolated SQL; saved confirmed native settings preserved after rejected UI/bit-clock consistency edit. Complete release gate NOT_RUN.'
 ],validation=dict(status='PASS',tests_passed=count,isolated_sql=True,complete_release_gate='NOT_RUN'),not_certified=[
  'Full licensed current TIA644/644A/899 conformance, every silicon/FPGA/serializer/SerDes/CML/PECL/B-LVDS/LVDM revision and vendor timing/enable/setup/hold/skew/power/noise/EMI operating condition.',
  'Canonical proof provenance resolution or commissioned line geometry/impedance/capacitance/termination/clock/receiver startup/idle/coding/access/signal integrity. ScalarVALID and lexical proof references do not implement or certify a board.',
  'Actual complete encoded electrical stream, higher-layer framing/CRC/application codec, schedule/multipoint ownership/capacity, functional E2E and safety assurance.',
  'Consumer-wide wizard/UI/preflight/capacity/simulation/trace consistency, nine-stage E2E and exact production delivery.'
 ])
(root/'work/lvds-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'tests_passed':count,'native_fields':len(native),'removed':len(spec['removed'])}))
