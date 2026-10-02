import hashlib,json,sys
from pathlib import Path
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import mqtt_sn as m
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/mqtt_sn-tests.xml'
for path in ('backend/communication/technologies/mqtt_sn.py','backend/tests/test_mqtt_sn_parameter_review.py',
             'backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
    assert xml.stat().st_mtime_ns >= (root/path).stat().st_mtime_ns,('stale receipt',path)
parsed=ET.parse(xml);suites=parsed.findall('.//testsuite')
assert suites and all(int(s.get(k,'0'))==0 for s in suites for k in ('failures','errors','skipped'))
cases=parsed.findall('.//testcase');native=sum(c.get('classname','').endswith('test_mqtt_sn_parameter_review')for c in cases)
assert native>=190 and len({c.get('classname')for c in cases})==10
primary=root/'work/mqtt-sn-primary';manifest=json.loads((primary/'manifest.json').read_text())
assert manifest[0]['sha256']==hashlib.sha256((primary/'MQTT-SN_spec_v1.2.pdf').read_bytes()).hexdigest()
manifest[0].update(read_scope='Full1.2 message tables pp6-19, gateway/session/topic/QoS/sleep pp20-26, recommendations p27; source28pages includesfrontmatter offset1',individual_local_tests_completed=True)
(primary/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
original=next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='mqtt_sn')
before={v['key']for v in original['form_parameters']};after={v['key']for v in registry.parameter_fields('mqtt_sn')}
native_fields={v['key']:v['description']for v in m.DECLARATIONS}
native_fields['payload_bytes']='Actual PUBLISH Data bytes. Ordinary shortheader2+flags/topic/msgID5 gives<=248payload within255; extendedheader4+5 gives<=65526 within65535. Actual qualified lower datagram cap governs, no MQTT-SN fragmentation or radio/CAN/Ethernet default.'
spec=dict(technology='mqtt_sn',native=native_fields,removed={k:m.REMOVED[k]for k in before-after},sources=list(m.SOURCES),revisions=list(m.SOURCES.values()),
scope=[
 'Every declared parameter separately reviewed for meaning/applicability/type/unit/bounds/dependencies/source/proposals/provenance. IBM1.2 November2013 fully public input specification pinned OASIS repository1f1fd60538cce4f6d8cf76f9a54c9c166c628367. MQTT-SN2.0 June2026 working-draft announcement reviewed for revision distinction only; no2.0 conformance asserted.',
 'Industry-neutral explicit bidirectional datagram/lower network/gateway path, no own wireless250k/PHY/MTU or inherited Ethernet/CANqueue/retry defaults. UDPport actual, no unverified universal1884; legacyIBM2013ZigBeeAPS60octet qualifier not every modern APS network. MQTT-SN no fragmentation/reassembly, lower supported datagram afterits overhead governs.',
 'Ordinary Length1or3octets includes itself andMsgType/variablepart. Extendedmarker01/16bitbigendian max65535; legalextended smallframes not rejected for nonminimal encoding. PUBLISH2or4+5+payload, MsgIDzeroencodedQoS0/minus1 distinct MQTTidentifierabsence. Actualencoded hex headerlength/type/PUBLISHflags optional consistency; not complete decoder.',
 'Topicnormal/predefined operational1..65534 with actualperclient/gateway acceptedmapping. ClientREGISTER usesTopicIdzero, acceptednormalREGACK nonreserved, wildcardSUBACK useszero. Shorttopic exactly2UTF8octets, not2Unicodecharacters; éaccepted/threebyte or fourbyte topicinvalid. NormalREGISTER topic and subscriptionfilter separate; +wholelevel/#terminal, noMQTT5sharedsubscription/alias fields.',
 'QoSminus1 onlyclientpublishes predefined/short to actualapriori gateway address, no connection setup requirement or subscription/registration invented. QoS0/minus1 MsgIDzero; QoS1/2 nonzero. Client onepending REGISTER/onependingQoS1or2PUBLISH/oneSUBorUNSUB transaction andatmostone connectedGW. ACKsameactualclient/gateway/requestID andPUBACKTopicId. Scalarchecks do not implementruntime state.',
 'CONNECTProtocolId01 flagsWill/Clean independently scoped; ClientID1..23Unicode scalar characters with exactUTF8octets separate, actualsourcequalification needed. Willprompt transferredseparately; emptyWILLTOPIC/UPD exactheaderonly2bytes noflags deletesboth Willfields. NonemptywillflagsQoS0/1/2 andretain; WillMsgopaque noMQTTstringprefix. Plannedunusedflagbitszero policy is not a complete receivingparser.',
 'ADVERTISErequiresactualconnected/integratedserver/broadcast, SEARCHGWradius0allnodes versus1..255, GWINFOaddressincludedfromotherclient andabsentfromGW. TransparentGW perclient backendconnection counts; QoSminus1 supportdedicatedextra connection versusaggregation. Actualbackend source remains, noresource/schedule/capacity certificate.',
 'SleepingDISCONNECToptional16bitduration sendsclient->gateway, normaldisconnect noDuration. WakingPINGREQ carriesactualClientID; PINGRESP closesbuffered delivery. Activetimerkeepalive andasleepsleep separated, watchdogactualpolicy. Recommendedtolerance1.5below60seconds/1.1above60; exactly60 not invented. No forced MQTT1.5 forlongsleep or universal60secondkeepalive.',
 'LiteratureTable30 recommendations conditionalselectedpolicy: search/gwinfo5s, retry10..15s/proposal10, retransmissions3..5/proposal3, missedadvertisements2..3/proposal2. Advertise strictly>900s andcongestionwait>300s showbounds without fabricatedexactstandarddefault. Registeredactualcustomtimer evidence can differ; recommendations are not deployedconfirmation.',
 'Forwarder exception Length1octet coversprefix3+opaquenodeID only, excludesinnercompleteMQTTSNmessage. Actualwholepacketprefix+inner fitslowerMTU; Ctrl2radiusbits not8bitSearchradius. No unqualifiedrecursiveencapsulation. Actualhexsize/prefix/type/Ctrlchecks andnodebytes, no completeinnercodec guarantee.',
 f'{len(cases)} isolatedSQL tests passed including{native} native andnine sharedsuites. Confirmedgateway255/Unicodeclient/QoSminus1 zeroMsgId/custom22secondretry retainedafterrejectedforeignradio rate.'
],validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} MQTT-SN and nine shared suites',complete_release_gate='NOT_RUN'),
not_certified=['Complete deployedMQTT-SN/gateway/MQTT runtime codecs, state transitions, discovery, retry, sleepingbuffer, actualradio/network/broker capacity/security andE2Eacceptance. MODEL_MISSING remains explicit.',
 'Full cumulative consumer tests, release gate and production delivery pending.'])
(root/'work/mqtt-sn-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n')
print(json.dumps(dict(tests=len(cases),native=native,fields=len(native_fields),removed=len(before-after))))
