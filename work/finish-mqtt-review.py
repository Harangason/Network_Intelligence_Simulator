import hashlib,json,sys
from pathlib import Path
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import mqtt as m
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/mqtt-tests.xml'
for path in ('backend/communication/technologies/mqtt.py','backend/tests/test_mqtt_parameter_review.py',
             'backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
    assert xml.stat().st_mtime_ns >= (root/path).stat().st_mtime_ns,('stale receipt',path)
parsed=ET.parse(xml);suites=parsed.findall('.//testsuite')
assert suites and all(int(s.get(k,'0'))==0 for s in suites for k in ('failures','errors','skipped'))
cases=parsed.findall('.//testcase');native=sum(c.get('classname','').endswith('test_mqtt_parameter_review')for c in cases)
assert native>=213 and len({c.get('classname')for c in cases})==10
primary=root/'work/mqtt-primary';manifest=json.loads((primary/'manifest.json').read_text())
for entry in manifest:
    assert entry['sha256']==hashlib.sha256((primary/(entry['version']+'.html')).read_bytes()).hexdigest()
    entry.update(read_scope=m.SOURCES[{'3.1.1':m.P3,'5.0':m.P5,'3.1.1-errata01':m.E3}[entry['version']]],individual_local_tests_completed=True)
(primary/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
original=next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='mqtt')
before={v['key']for v in original['form_parameters']};after={v['key']for v in registry.parameter_fields('mqtt')}
native_fields={v['key']:v['description']for v in m.DECLARATIONS}
native_fields['payload_bytes']='Actual PUBLISH application bytes, excluding UTF8TopicName, identifier and version5properties. RemainingLengthmax268435455 includes variableheader andbody; actual full-packet receivercap plus lowertransport separate. No EthernetMTU/ownclock or8byte CANproposal.'
spec=dict(technology='mqtt',native=native_fields,removed={k:m.REMOVED[k]for k in before-after},sources=list(m.SOURCES),revisions=list(m.SOURCES.values()),
scope=[
 'Every declared parameter separately reviewed for meaning/applicability/type/unit/bounds/dependencies/source/proposals/provenance. OASIS3.1.1 October2014 protocollevel4 versus5.0 March2019 level5, no crossrevision properties. Industry-neutral explicit ordered lossless bidirectional TCP/TLS/WS/WSS/registered stream; bareUDP invalid, MQTT-SN separate.',
 'Removed own Ethernet10M/MTU/duplex/VLAN and CAN queues/retry/gateway defaults. TCP1883/TLS8883 conditional proposals only; actual WS/WSS port/security/binding references. No fixed keepalive60seconds, brokerqueues, retryperiod or constructed ClientID/credentials. Native scalar validity not broker/codec/TLS runtime evidence.',
 'RemainingLength0..268435455 includes header+packetpayload, minimalVBI1..4 across127/16383/2097151 thresholds; totalpacket1+VBI+remaining<=268435460. Approved Errata01 December2015 section2.1 reviewed: decoder pseudocode range-check correction permits fourthbyte; NIS scalar boundary validation tests both revisions above2097151, not a complete packet decoder. PropertyVBI distinct; exact PUBLISH UTF8topic2bytes plus optionalidentifier2 plus5properties andbody. Fixedheader flags bykind/QoS/DUP/RETAIN, direction andAUTHversion restrictions. Complete arbitrary packet serializer/parser and all property tables not certified.',
 'QoS0 noidentifier/noDUP/ReceiveMaximum doesnotcount it. QoS1/2 actual directional pendingID1..65535/newIDunused; response same original ID/currentconnection/pendingmatch. ReceiveMaximum1..65535, quota may0 andothercontrolscontinue; peerfullpacket cap nonzero uint32, independent payload limit. MaximumQoSproperty encoded0/1 versusabsence2; subscriptionrequestedQoS2 remains permitted even server supports0.',
 'Native MQTTUTF8strings0..65535 octets require noU+0000/surrogates, preserveBOM/whitespace/case, packetTopic no+#. Control/noncharacter policy is normativeSHOULD/MAY, no unreviewed universal ban. Topicfilters +wholelevel/#lastwholelevel andempty levels; shared$share/group/filter andNoLocalFalse. Empty5PUBLISHtopic requires nonzero receiveraccepted currentconnectionmappedalias;3 requires nonempty. UTF8payload maycontainNULL distinct from MQTTstring.',
 'ClientIDportablealphanumeric1..23byte support vsactualextendedbroker andzero serverassignment. Version3 zeroClientID requiresCleanSessionTrue andpasswordrequiresusernameflag;5cleanstart/uint32expiry independent andpasswordmaystandalone. Noexpiry FFFFFFFF andmessageexpiry0 preserved. WillFalseforcesQoS0/RetainFalse/noencodedwillfields. Version5 enhancedAuthmethod/data mustmatchCONNECTmethod actualreference.',
 'Absence defaults conditional on actual version5propertypresence: ReceiveMaximum65535, MaximumQoS2, TopicAliasMax0, SessionExpiry0, WillDelay0, PayloadFormat0, RetainAvailableTrue, requestresponseFalse/problemTrue. Actual known propertyabsence not fabricated; no universal session/Will/credential/keepalive defaults. Server keepalive overridesincluding0; nonzero silencebound1.5*effectiveinterval distinct applicationdeadline.',
 'MQTT5 re-delivery only reconnect existing session/CleanStartFalse/originalID andDUPTrue; version3 CleanSessionFalse separate historicalretry scope. QoS exactlyonce is one sender-receiver hop, no E2Efunctional/safetycertificate. Explicit allow_empty_text applies only registered string constraints so emptyClientID orwhitespaceTopic not treated as missing evidence sources.',
 f'{len(cases)} isolated SQL tests passed including{native} MQTT andnine shared suites. ConfirmedUTF8/BOM topic, zeroKeepAlive, uint32noexpiry andID65535 preserved after rejected inheritedEthernet clock.'
],validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} MQTT and nine shared suites',complete_release_gate='NOT_RUN'),
not_certified=['Complete broker/client packet codec, runtime MQTT properties, flow persistence/retransmission/Will/alias/subscription matching, authentication/TLS, actual lowernetwork capacity and E2E acceptance. MODEL_MISSING remains explicit.',
 'Full cumulative consumer tests, release gate and production delivery pending.'])
(root/'work/mqtt-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n')
print(json.dumps(dict(tests=len(cases),native=native,fields=len(native_fields),removed=len(before-after))))
