"""Finish this individual audit only after its real isolated regression passes."""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import lte_m as m

folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001'
xml=folder/'individual/lte_m-tests.xml'
for relative in ('backend/communication/technologies/lte_m.py','backend/communication/technologies/catalog.py',
                 'backend/tests/test_technology_full_parameter_audit.py'):
    assert xml.stat().st_mtime_ns >= (root/relative).stat().st_mtime_ns, ('stale test receipt',relative)
tree=ET.parse(xml)
suites=tree.findall('.//testsuite')
assert suites and all(int(v.get(k,'0'))==0 for v in suites for k in ('failures','errors','skipped'))
count=sum(int(v.get('tests','0'))for v in suites)
assert count>7848,count
original=next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='lte_m')
before={v['key']for v in original['form_parameters']}
after={v['key']for v in registry.parameter_fields('lte_m')}
native={v['key']:v['description']for v in m.DECLARATIONS}
native['payload_bytes']='Actual encoded application length, not PHY transport-block bits, MAC/RLC/PDCP segmented length, serving-carrier capacity or a universal8/1500byte default. Application/transport codec needs independent source.'
spec=dict(technology='lte_m',native=native,removed={k:m.REMOVED[k]for k in before-after},
 sources=list(m.SOURCES),revisions=list(m.SOURCES.values()),scope=[
  'Each declared field reviewed independently for meaning/applicability, scalar type/unit/bounds, exact source/revision and conditional proposals. Retained NIS scenario fields are explicit application requirements, not radio standards.',
  'All37eligible Release18 LTE-M bands reviewed separately against RF5.5E and visually checked band/channel tables; FDD/TDD, allowed serving-carrier bandwidths, carrier PRB mappings and UL/DL frequency intervals remain distinct from category bandwidth. Band106 supports only1.4/3MHz; M2max=min(5,maxBand).',
  'CatM1/M2 DL/UL TBS, soft bits, L2 capability buffers, optional1736/2984 features and matched category pair reviewed from TS36.306; capability maxima are not actual device support, grant, application payload or throughput. Optional ModeA capability does not prohibit smaller ModeB operation.',
  'ModeB UL remains1.4MHz/sixPRBs; optional DL64QAM requires connected non-repeated unicast ModeA and capability. No UL64/256QAM or NB-IoT3.75kHz/NR numerology fallback.',
  'Frame10ms/subframe1ms/15kHzslot0.5ms/regular12subcarrier PRB180kHz and CP-qualified ULsymbols checked. DLwideband uses available one/two/four narrowbands rather than unconditional24PRBs. TDD assignments and special-subframe proof distinct from HD-FDD typeB guards.',
  'Actual wide PUSCH/PDSCH grants constrained to24PRBs, not a25PRB serving5MHzcarrier. Source5.3.4 permits eligible odd-center UL PRB:3MHzcarrier therefore ULmax13 versus DLmax12. Wide grants require qualified network C/SPS-C-RNTI configuration, connected/unicast/optional wideband ability and ULModeA; generic BL/CE20MHz/96PRB cases are not M1/M2 permission.',
  'Bands28/71 UL20MHz footnote intervals, band66 DLcarrier-aggregation range and missing6.2.2Epower-row, band74band11/21 capability requirements checked independently. Power-class nominal maxima and actual controlled power/tolerance/MPR are separate; class2 onlybands31/72HD-FDD. Measured frequency error qualified by64ms duration,1GHz boundary and duplex, not assigned as a standard measured value.',
  'Actual radio/category/band/address/grants/optional abilities/subscription credentials/output/error/PSM/eDRX timers and confirmation have no invented defaults. Where a source supplies a qualified minimum carrier bandwidth or fixed PHY/category value, a context-qualified source proposal is declared.',
  f'Selected ten-file regression{count}PASS in isolated SQL; confirmed native fields survive rejected band1065MHz edit. Complete release gate NOT_RUN.'
 ],validation=dict(status='PASS',tests_passed=count,isolated_sql=True,complete_release_gate='NOT_RUN'),not_certified=[
  'Complete conformance with other releases/categories, actual modem/eNodeB firmware/certification, current licensed jurisdiction deployment, CA/UL-MIMO/power reduction, every spectral/sensitivity/RF operating condition.',
  'Complete TS36.213/321/322/331 and NAS24.301/24.008 executor/timer/PSM/eDRX/security conformance. Optional sub-PRB/modulation/multicast features require their own qualified codecs and scheduler; source-reference declarations do not implement them.',
  'Canonical proof-source provenance resolution, actual shared-cell/MCS/coding/repetition/retuning/control/HD/TDD schedule, core/backhaul/server capacity, cryptography or functional/safety acceptance. Category peak and scalarVALID do not certify capacity.',
  'Consumer-wide wizard/UI/preflight/capacity/simulation/trace consistency, nine-stage E2E or exact production delivery.'
 ])
(root/'work/lte-m-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'tests_passed':count,'native_fields':len(native),'removed':len(spec['removed'])}))
