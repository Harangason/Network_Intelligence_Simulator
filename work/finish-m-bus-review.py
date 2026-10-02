"""Record M-Bus only after the current isolated regression really passes."""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import m_bus as m
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001'
xml=folder/'individual/m_bus-tests.xml'
for relative in ('backend/communication/technologies/m_bus.py','backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py','backend/tests/test_technology_full_parameter_audit.py'):
 assert xml.stat().st_mtime_ns >= (root/relative).stat().st_mtime_ns,('stale receipt',relative)
suites=ET.parse(xml).findall('.//testsuite')
assert suites and all(int(v.get(k,'0'))==0 for v in suites for k in ('failures','errors','skipped'))
count=sum(int(v.get('tests','0'))for v in suites);assert count>8276,count
original=next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='m_bus')
before={v['key']for v in original['form_parameters']};after={v['key']for v in registry.parameter_fields('m_bus')}
native={v['key']:v['description']for v in m.DECLARATIONS}
native['bitrate']='Actual current transaction baud independently bounded by both commissioned endpoint capabilities; OMS300/2400 mandatory and optional9600/19200/38400 hierarchical.300 is the lowest standard proposal, not measured current baud or requested future rate.'
native['payload_bytes']='Actual application bytes; FT1.2 user area also contains transport/security/record overhead. No universal8byte or252application-byte capacity/default; actual encoded lengths require their own proof.'
spec=dict(technology='m_bus',native=native,removed={k:m.REMOVED[k]for k in before-after},sources=list(m.SOURCES),revisions=list(m.SOURCES.values()),scope=[
 'Every declared field reviewed for its own meaning/applicability/type/unit/scalar bound/dependencies/source/revision and conditional proposal. Remaining explicit NIS scenario requirements do not become wiredM-Bus standards.',
 'OMS5.0.1/AnnexP-C1.1.3 source-selected scope: allP.1/P.2/P.3 read; newer normativeP.2 and informative quotedEN2018 constraints distinguished. Full licensed current EN13757-2:2018+A1:2023 unavailable and not certified.',
 'Wired voltage-modulated master downlink and current-modulated slave uplink, single-master half-duplex polling and primary/secondary/enhanced selection modeled independently from wirelessM-Bus/CAN/Ethernet/I2C.',
 'Minimum standard proposal300baud; each endpoint300/2400 and optional higher-rate hierarchy, automatic slave baud detection and independently registered additional baud distinct. Current transaction, requested rate change and peer maxima are separate parameters.',
 'Unit-load current bands1..4, actual totalUL/master capacity/current/drop/mark-space range and line/source resistance checked without invented36/24V,250device, termination or cable-length operating defaults. NormativeP.2 voltage-delta12inclusive takes precedence over informativeP.3 strict-space phrasing.',
 'Inrush<100mA, charge/discharge ratio>30, recovery<3s, no-load versus loaded half-bit edges and master receive-current MARK/SPACE thresholds conditioned on explicit pulse<50ms and duty<0.92. Current-detection ambiguity and collision thresholds remain separate; fixture validity is not capacity proof.',
 'Primary0/1..250 versus FDselection/FEtest/FFno-reply and actual eight-digit secondary identity distinguished. Reply ownPA uses normativeVol2 despite illustrativeFDh AnnexN example. Adapters do not freely change manufacturer/version.',
 'All43 allowed OMS CI rows individually tested for direction/transport header;17 wired-excluded wireless ELL/MBAL/CI values rejected. AFL90 needs independently described inner layers/continuations.',
 'FT1.2 ACK/short/control/long whole-wire lengths, Lfield and user area including TPL/AFL/security/records,11-bit8E1LSB UARTserialization and baud-dependent11..330bit+50msreply window distinguished from app payload and functional deadline. No generated identities/keys/actual timers/confirmation.',
 'Selected TSS721A2010 slave hardware has its own9600baud operating envelope, RX10.8V/TX12V..42V, BAT2.5..3.8VandSTC−1V, RRIDD13..80kohm/RRISminimum100ohm,−25..85C,100ohmcurrent fixture11.5..19.5mA. Absolute50V,typicals and ordering/package qualification are not generic operating defaults.',
 f'Selected ten-file regression{count}PASS in isolated SQL, including persistence of confirmed native address/rate/CI after rejected wirelessCIedit; complete release gateNOT_RUN.'
],validation=dict(status='PASS',tests_passed=count,isolated_sql=True,complete_release_gate='NOT_RUN'),not_certified=[
 'Full licensed current EN13757 and every newer OMS/device/master/repeater/transceiver edition and hardware/EMC/conformance fixture. Device-specific UART pin, peak detector, silicon/cable fault and application-data details need actual equipment qualification.',
 'Canonical provenance-reference resolution, complete FT1.2 encoder/parser/checksum or crypto/AFL/TPL/application command implementation and commissioned polling/collision/retry/search schedule/capacity; lexical sources and scalar VALID are not those proofs.',
 'Consumer-wide wizard/UI/preflight/capacity/simulation/trace consistency, nine-stage E2E and exact production delivery.'
])
(root/'work/m-bus-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'tests_passed':count,'native_fields':len(native),'removed':len(spec['removed'])}))
