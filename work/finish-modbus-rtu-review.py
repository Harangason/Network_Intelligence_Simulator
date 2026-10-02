"""Fresh RTU audit receipt, with explicit shared application declarations and native serial timing."""
import hashlib,json,sys
from pathlib import Path
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import modbus_rtu as m
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/modbus_rtu-tests.xml'
for path in ('backend/communication/technologies/modbus_rtu.py','backend/tests/test_modbus_rtu_parameter_review.py',
 'backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py',
 'backend/communication/technologies/core/physical.py','backend/engineering/capacity/service.py','backend/tests/test_technology_standard_defaults.py'):
    assert xml.stat().st_mtime_ns >= (root/path).stat().st_mtime_ns,('stale receipt',path)
parsed=ET.parse(xml);suites=parsed.findall('.//testsuite')
assert suites and all(int(s.get(k,'0'))==0 for s in suites for k in ('failures','errors','skipped'))
cases=parsed.findall('.//testcase');native=sum('test_rtu_'in c.get('name','')for c in cases)
assert native>=178 and len({c.get('classname')for c in cases})==10
primary=root/'work/modbus-primary';manifest={}
for key in ('serial','application'):
    entry=json.loads((primary/(key+'-source.json')).read_text());assert entry['sha256']==hashlib.sha256((primary/(key+'.pdf')).read_bytes()).hexdigest()
    entry.update(read_scope=('Serial V1.02 sections2.1-2.6 and3.2-3.6/pages7-20/26-28/32/34/39: RTU 8data/11bits, parity, baud-dependent gaps, CRC algorithm, role/address and separately qualified physical line. Class table Basic9600/19200-if-implemented versus Regular.'
      if key=='serial'else'ApplicationV1.1b3 pages3-11/11-12/15-19/20/22-23/29-30/38/43/47-49: exact PDU/function/address/quantity/exception namespaces. Shared application declarations and electrical rules explicitly allowlisted, independently exercised through RTU.'),individual_local_tests_completed=True)
    manifest[key]=entry
(primary/'rtu-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
original=next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='modbus_rtu')
before={v['key']for v in original['form_parameters']};after={v['key']for v in registry.parameter_fields('modbus_rtu')}
native_fields={v['key']:v['description']for v in m.DECLARATIONS}
native_fields.update(bitrate='Actual supported/calibrated serial baud;19200 source proposal if implemented, Basic9600 fallback. No universal1200minimum or115200maximum; optional rates depend actual devices. Positive scalar alone not capacity.',
 payload_bytes='Actual complete binary Modbus function data0..252, not register-only values; function1 adds PDU<=253. RTU address1 andCRC2 form ADU4..256, each octet11wirebits; gaps/processing separate.')
spec=dict(technology='modbus_rtu',native=native_fields,removed={k:m.REMOVED[k]for k in before-after},sources=list(m.SOURCES),revisions=list(m.SOURCES.values()),
 scope=[
 'Every declared parameter reviewed for meaning/applicability/types/units/bounds/dependencies/source/proposals/provenance. Explicit shared Modbus application/serial electrical allowlist does not inherit ASCII frames/LRC/1000ms timeout, CAN priorities or Ethernet PHY defaults.',
 'RTU8data/start1/parity1/stop1 orNONE2 yields11wirebits. Basic EVEN and2W485/RS232; Regular supports9600/19200/optional rates; selected literature19200 proposal versus actual Basic9600 fallback if19200 absent. Rate not globally capped1200..115200; strict better-than1percent TX and2percentRX verified.',
 'Binary PDU1..253/data0..252 versus address/PDU/CRC ADU4..256 and44..2816wirebits; lengths exact, gap/processing separate. CRC16 initFFFF/reflectedA001/LSB-shift on actual address/PDU octets, low-octet-first checked against known wire vectors and actual header fields. This scoped CRC verification is not a complete runtime Modbus decoder.',
 'Baud<=19200 inclusive strictly character timer1.5/3.5*11bit-times;>19200 recommendedfixed750us/1750us. Alternative high-baud character driver requires actual deviation evidence. Observed interchar atthreshold accepted/above discarded; interframe atthreshold accepted/below blocked. No ASCII1000ms or CAN retransmission copied.',
 'One serial master and outstanding request; slave address1..247 actual, broadcast0 writes/no reply; master has no fabricated slave address. RTU excludes ASCII FC8sub3 delimiter command. Application PDU public/user-defined functions, exceptions+128, quantity/read/write/address spans and actual vendor mappings independently exercised.',
 'Actual RS4852W/4W orRS232 physical choice replaces former forcedRS485alias. Conductors/common/pair count/topology and two terminations per differential pair checked,4Wtotal4 vs2Wtotal2 andRS232zero. Common line/cable/load/bias/drop qualification rules use same source, not RS422fallback; unknownselected path remains REVIEW.',
 'Invalid/unverified rate values are validated before capacity resolution even when rate evidence alreadyfalse; rejected transport values removed from calculation input, saved confirmations unchanged. Confirmed9600/NONE2stops/character-timers/device17 survive rejected foreign fast-gap edit.',
 f'{len(cases)} isolated SQL tests passed including{native} RTU tests and nine shared suites. Scalar validity and source proposals remain distinct installed hardware, capacity, E2E or safety/security acceptance.'
 ],validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} RTU and nine shared suites',complete_release_gate='NOT_RUN'),
 not_certified=['Complete all-function runtime RTU codec, actual calibrated endpoints/PHY/address uniqueness/transaction schedule/capacity/observed trace; MODEL_MISSING remains explicit.',
 'Full cumulative tests, release gate and production delivery pending; ASCII/TCP separate sequential source reviews.'])
(root/'work/modbus-rtu-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n')
print(json.dumps({'tests':len(cases),'native':native,'native_fields':len(native_fields),'removed':len(before-after)}))
