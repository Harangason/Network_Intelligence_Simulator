import hashlib,json,sys
from pathlib import Path
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import most as m
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/most-tests.xml'
for path in ('backend/communication/technologies/most.py','backend/tests/test_most_parameter_review.py',
             'backend/communication/technologies/catalog.py'):
    assert xml.stat().st_mtime_ns >= (root/path).stat().st_mtime_ns,('stale receipt',path)
parsed=ET.parse(xml);suites=parsed.findall('.//testsuite')
assert suites and all(int(s.get(k,'0'))==0 for s in suites for k in ('failures','errors','skipped'))
cases=parsed.findall('.//testcase');native=sum(c.get('classname','').endswith('test_most_parameter_review')for c in cases)
assert native>=124 and len({c.get('classname')for c in cases})==10
primary=root/'work/most-primary';manifest=json.loads((primary/'manifest.json').read_text())
for entry in manifest:
    if entry['name'] in ('os81050','os81092'):
        assert entry['sha256']==hashlib.sha256((primary/(entry['name']+'.pdf')).read_bytes()).hexdigest()
        entry['read_scope']=m.SOURCES[m.P25 if entry['name']=='os81050' else m.P50]
    else:
        entry['read_scope']=m.SOURCES[m.P150]
        assert entry['status']=='DOWNLOAD_UNAVAILABLE'
    entry['individual_local_tests_completed']=True
(primary/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
original=next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='most')
before={v['key']for v in original['form_parameters']};after={v['key']for v in registry.parameter_fields('most')}
native_fields={v['key']:v['description']for v in m.DECLARATIONS}
native_fields.update(bitrate='Actual complete carrier frame bits times qualified generation/device targetFs; MOST25 baseline44100Hz produces22579200bit/s, not a rounded25M or universal150M. Host MediaLB/I2C/SPI/USB and usable channel allocation remain separate.',
 payload_bytes='Actual channel application bytes, distinct complete port/PMP message and carrier allocation. OS81050/OS81092 MDP host-qualified50byteI2C versus1014byteMediaLB bounds; no universal1500Byte maximum.')
spec=dict(technology='most',native=native_fields,removed={k:m.REMOVED[k]for k in before-after},sources=list(m.SOURCES),revisions=list(m.SOURCES.values()),
scope=[
 'Each declared parameter individually reviewed for meaning, applicability, type/unit/bounds/dependencies/proposals/source/provenance. Industry-neutral registered path; device-qualified25/50 versus explicitly limited150 public excerpts. Full proprietary normative/API/device tables unavailable, no universal conformance claim.',
 'Generation25/50/150 carrier64/128/384bytes with exact512/1024/3072bits times selected Fs; OS81050 targets44100/48000 versusOS81092/OS81118 target48000, rate22579200/24576000/49152000/147456000 not rounded speedgrade150M. Observedclock tolerance distinct nominal mode; carrier allocation excludes actualoverhead/control/stream/packet. Multiframepacket fragmentceil and actual usableallocation distinct grossclock.',
 'Control arbitration, asynchronous packet and single-source/multiple-sink granted streams separated; actual mapping/API/codec/device clock/physical/schedule/acceptance sources required. Threeframe locksettle only qualified25/50, actual oscillator256Fs vs384Fs. Isochronous/embeddedEthernet channels excluded25/50; no runtimecapacity proof from VALID.',
 'HostMediaLB3 clocks256/512/1024Fs and5pin256/512Fs distinct carrier. STREAMING left/right 16/24-bit sample/socketpacking; sequential25 clocks64/128/256 vs50 additional8/16/32. Exact selectedport clock/socket and sources; partial/full pin coexistence and implementation buffer qualification not inferred.',
 'MDPapplication max1014 MediaLB versus50I2C selected25/50. PortMessage PML16bit excludes own2bytes; bodyPML-PMHL-1 distinct frame64/128/384. No fabricated MOST API node-address width or identity, actual firmware/API address mapping remains required.',
 'ActualMOST50UTPcable100..140ohm nominal130 vsdevicecore1.8V; MOST25optical/core2.5V. Operating junction-40..125 excludesabsolute150C. OS81092 I2Cmaster only verifiedC1Dor-later; OS81118AFintegratedcoax versusBFoptical, full-duplexcoax daisychain needs actualOS81119 companion/topology source. NoEthernet/CAN PHY or retry/queue defaults.',
 f'{len(cases)} isolated SQL tests passed including{native} MOST and nine shared suites. Confirmed49152000clock/address1234/actual120ohm retained after rejected rounded150M edit.'
],validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} MOST and nine shared suites',complete_release_gate='NOT_RUN'),
not_certified=['Complete MOST normative specification, INIC proprietary API, hardware timing/PHY qualification, pin-sharing configuration or executable channel/arbitration schedule. MOST150 full PDF unavailable; public indexed pages13/59/78/89 and current manufacturer product description only. MODEL_MISSING explicit.',
 'Full cumulative consumer tests, release gate and production delivery pending.'])
(root/'work/most-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n')
print(json.dumps(dict(tests=len(cases),native=native,fields=len(native_fields),removed=len(before-after))))
