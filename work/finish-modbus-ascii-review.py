"""Document the ASCII review with fresh isolated tests and primary PDF hashes."""
import hashlib,json,sys
from pathlib import Path
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import modbus_ascii as m
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001'
xml=folder/'individual/modbus_ascii-tests.xml'
for relative in ('backend/communication/technologies/modbus_ascii.py','backend/communication/technologies/catalog.py',
 'backend/communication/technologies/core/components.py','backend/tests/test_modbus_ascii_parameter_review.py'):
    assert xml.stat().st_mtime_ns >= (root/relative).stat().st_mtime_ns,('stale receipt',relative)
parsed=ET.parse(xml);suites=parsed.findall('.//testsuite')
assert suites and all(int(v.get(k,'0'))==0 for v in suites for k in ('failures','errors','skipped'))
cases=parsed.findall('.//testcase');native_count=sum('test_ascii_'in c.get('name','')for c in cases)
assert native_count>=172 and len({c.get('classname')for c in cases})==10
primary=root/'work/modbus-primary'
scopes={'serial':'V1.02 December20 2006 pages7-20 data-link/ASCII/master/addresses/error/baud; sections3.3.2/3.3.3 two/fourwire circuits and grounding read; pages26-28/32 RS232/cable/loads/termination/polarization; tablepage34 implementation classes; AppendixB page38 LRC algorithm. No obsolete1996 guide or RTU gap/CRC applied ASCII.',
 'application':'V1.1b3 April26 2012 sections4/5 pages3-11 PDU/endianness/address/category; pages11-12/15-19/20/22-23/29-30/38 quantity/length/diagnostic rules; pages43/47-49 MEI and exceptions. Variable advanced function codecs require actual function source; not all full function execution certified.'}
manifest={}
for key in ('serial','application'):
    entry=json.loads((primary/(key+'-source.json')).read_text());assert entry['sha256']==hashlib.sha256((primary/(key+'.pdf')).read_bytes()).hexdigest()
    entry.update(read_scope=scopes[key],individual_local_tests_completed=True);manifest[key]=entry
(primary/'ascii-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
original=next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='modbus_ascii')
before={v['key']for v in original['form_parameters']};after={v['key']for v in registry.parameter_fields('modbus_ascii')}
native={v['key']:v['description']for v in m.DECLARATIONS}
native.update(bitrate='Actual serial baud; V1.02 section3.2 required19200 default/9600 support, optional rates depend actual device configuration and calibrated baud. Required better-than1percent TX and2percent RX, no universal115200 cap or capacity from proposal.',
 payload_bytes='Actual complete function-specific binary data field0..252 bytes including addresses/counts/metadata. Function1 yields PDU1..253; serial address/LRC hex expansion and colon/CR/LF produce up to513ASCIIcharacters, each10wirebits.')
spec=dict(technology='modbus_ascii',native=native,removed={k:m.REMOVED[k]for k in before-after},sources=list(m.SOURCES),
 revisions=list(m.SOURCES.values()),scope=[
 'Every declared native parameter reviewed for meaning/applicability/types/units/bounds/dependencies/source/proposals/provenance; retained fields explicit NIS scenario/application policy. Industry-neutral ASCII independent RTU/TCP; no inherited CAN/IP queue/priority/retry/sync/gateway capacities.',
 'Modbus SerialV1.02 official primary PDF hash preserved; ASCII optional Regular class while generic device factory mode RTU. ASCII7data/start1/parity1/stop1 orNONE2 gives10wirebits. EVEN/19200 baseline proposals require selected actual endpoints; optional rates are not globally capped115200.',
 'Exact binary PDU1..253/functiondata0..252, address1/LRC1 expanded2characters each, colon1/CRLF2 yieldASCII9..513characters and90..5130wirebits. Uppercase hex even-body length versus decoded PDU, complete serialization versus gaps/processing distinguished.',
 'LRC8bit two-complement unsigned binary address/PDU sum before hex excludes colon/CRLF; zero/multiple256/overflow tested. No RTU CRC16 or 1.5/3.5 character gap inheritance. DefaultLF0A distinct documented FC8/sub3 changed delimiter. ASCII1000ms interchar baseline, documented longer WAN timer permitted; response/retry/broadcast turnaround application-dependent.',
 'One serial master/one pending transaction, master has no slave own address; slave1..247 unique,0broadcast and248..255reserved. Broadcast writing/qualified diagnostic commands no reply, listen-only/force-listen no reply. Request/normal response original function vs exception+128/data1 checked.',
 'Public assigned vs user65-72/100-110 and registered functions separated; exact coil/read register/write quantities and PDU bytecounts, ceilcoilpack/16bitbig-endian/FC5FF00literal/FC23read125/write121 versusFC16write123 and address-span limits checked. Used encoded PDU/count cannot hide absent quantity. Function-specific values rejected under other public functions; advanced variable codecs need actual source.',
 'RS4852W/4W actual common/shield and two trunk-end terminations per pair;4Wmultipoint notRS422. RS232pointtopoint2devices/no termination/cap2500pF rejects RS485 resistor/bias settings.32unrepeated baseline vs28with polarization and documented fractional-load exceptions remain distinct addresses.',
 'Bias single-location450..650ohm/5V and optional resistor150/.5W vsRC120/.25W/1nF/atleast10V are qualified proposals, not installed defaults. Cable/gauge/baud/layout constraints:<=9600/AWG26 1000m ormodified4W-as2W500m;CAT5max600m;drop20m and40m/n. Actual physical/source/load qualification remains required.',
 'Strict fractional exclusive upper/lower baud bounds use exact decimal comparisons; generic calculated recurring character/serialization times use existing numeric tolerance, while integer frame/LRC/coil count checks exact. No full frame encoder or schedule executor manufactured.',
 f'{len(cases)} isolated SQL tests passed including{native_count} ASCII tests and nine shared suites; confirmed9600/NONE2stops/4200ms/device17 retained after rejected stop-bit edit. Cumulative tests/release gate/production delivery still required.'
 ],validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native_count} ASCII and nine shared parameter/default/rate/physical/capacity suites',complete_release_gate='NOT_RUN'),not_certified=[
 'Actual installed device/PHY/cable qualification, address uniqueness, complete all-function ASCII/LRC encoder/decoder, request/reply/processing/retry schedule or runtime serial capacity; MODEL_MISSING remains explicit.',
 'Modbus TCP/RTU are separate sequential reviews, not certified by ASCII proof. ScalarVALID/source proposals do not prove physical traffic, observed calibrated trace or E2E functional/safety/security acceptance.'
 ])
(root/'work/modbus-ascii-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n')
print(json.dumps({'tests_passed':len(cases),'native_tests':native_count,'native_fields':len(native),'removed':len(before-after)}))
