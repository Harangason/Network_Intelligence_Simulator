from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
root=Path.cwd();sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import opc_ua_pubsub as n
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/opc_ua_pubsub-tests.xml'
for path in('backend/communication/technologies/opc_ua_pubsub.py','backend/tests/test_opc_ua_pubsub_parameter_review.py','backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
 assert xml.stat().st_mtime_ns>=(root/path).stat().st_mtime_ns,('stale',path)
p=ET.parse(xml);s=p.findall('.//testsuite');assert s and all(int(v.get(k,'0'))==0 for v in s for k in('failures','errors','skipped'))
cases=p.findall('.//testcase');native=sum(c.get('classname','').endswith('test_opc_ua_pubsub_parameter_review')for c in cases)
assert native>=len(registry.parameter_fields('opc_ua_pubsub'))+10 and len({c.get('classname')for c in cases})==10
primary=root/'work/opc-pubsub-primary';manifest=json.loads((primary/'manifest.json').read_text())
for entry in manifest:
 assert hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()==entry['sha256']
 entry.update(revision='v1.05.06',read_scope='Scoped official HTML common configuration/UADP/JSON/sequence/UDP-DTLS/Ethernet/MQTT/topic/default/timing sections. AnnexB informative; no whole-specification or hardware certification.')
(primary/'reviewed-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
before={v['key']for v in next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='opc_ua_pubsub')['form_parameters']};after={v['key']for v in registry.parameter_fields('opc_ua_pubsub')}
meanings={v['key']:v['description']for v in n.DECLARATIONS}
meanings['payload_bytes']='Actual application byte count distinct DataSet/NetworkMessage/metadata/security/padding/bearer/MQTT packet. No universal8byte payload or65507byte UDP ceiling on all mappings.'
spec=dict(technology='opc_ua_pubsub',native=meanings,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES),revisions=list(n.SOURCES.values()),
 scope=['Every declaredfield meaning/type/unit/bounds/dependencies/applicability/source/default provenance reviewed. Current publisherPart14v1.05.06 (not assumed identicalClient/ServerPart4/6v1.05.07), scopedHTML downloaded/hashed/read. InformativeAnnexB/registeredtransport not advertised as universalnormativebehaviour.',
 'Industry-neutral application withactualUDP/DTLS/directEthernet/MQTT andUADP/JSON mappings. No genericEthernet/IP/UDPstack, physical10Mrate, CAN8byte or universal65507payloadlimit. Ownapplicationfields distinct bearer andnativeClient/ServerSession/SecureChannel parameters. Actualsource-qualified physicalservicecapacity remainsMODEL_MISSING.',
 'NonzeroPublisherId Byte/UInt16/UInt32/UInt64losslessdecimaltext underwidth-specificmaxima versusStringidentity; UInt64<=18446744073709551615. Genericconditionaldecimalmaximum addedwithout floatconversion. NoMAC/port/actualidentity fabricated. WriterGroupIdandDataSetWriterIdexternal1..32767versusinternal32768..65535 withindependentallocators; writer identity andreaderfilteractualmetadata/source.',
 'Cyclickeyframe>=1 versusacyclic0/heartbeat1. PublishingInterval0requireskeyframe0; keepalivepositiveand>=actualpublish; no100msfrequencyfromCAN. Heartbeatconfigurationversions0; metadata andfunctionalacceptance explicit. UADPversion1proposal, ConfiguredSize0dynamic/offset0dynamic/orderingUndefined source defaults.',
 'IPMTUbudget andcompleteEthernetframebudget distinct; actualUDP8/IPheader/options/DTLSrecordtagpadding separateMAC/FCS. IPv4min20versusIPv6min40 not mixed; no guessedDTLSoverhead. Datagrammessage/totalwire65535outerbounddistinctactualheader-reducedlimit; no70000NetworkMessageacceptedforUDP. UDPport4840/DTLS4843 proposalsallowactualotherports. DiscoveryeffectiveUDP4096, announcement0probe-onlyandrepeat0disabled proposals, not CANretry. DirectEthernet EtherTypeB62C/complete1522 source constraint, noIP/UDPfields.',
 'ActualUDPunicastWriterGroupaddress vsmulticast/broadcastabsentWriterGroupaddress; actualmulticastsubscriberIGMP/MLD membershipandselectedinterfacewhenmultiple. DTLS1.3unicastonly, not MQTT or multicast andnotapplicationauthorization. Actualper-message securitygroup distinct transportTLS/DTLS, secrets never defaulted.',
 'MQTTBestAvailable selectiondistinctnegotiated3.1.1/5.0. ActualrequestedguaranteeQoS0/1/2 mapping, JSON/UADPContentType, topicnowildcards, brokercompletepacketlimitsnotapplicationbytes. ClassspecificRETAINmetadata/discoverytrueversusdatafalseproposal; actualdataretainedoverrideexplicit. MQTTKeepAliveseconds greaterthanmaximumgroupkeepalive ms, not copiedsameunit.',
 'Sequencewidth16UADP/32JSON, start0andincrementwithmodularwrap. Receiver(new-1-last)mod2^N, lower/upperquarterrangeexactnew/invalid/oldboundary tests, correlationwriter/metadata notUASCtokenrenew. UADPFlags1 actualvalid/encoding/sequencepresencedecoded; reservedencoding3invalid. FixedDataSetSizepadsorinvalidates, no silenttruncate; invalidoversizeobservation maybedescribed butcannotfunctionallyaccepted.',
 'UADP sampling/receive/processingoffsetsnegativeunset; orderedPublishingOffsetnumericJSONarray withactualcount, no zero-latencyfake. StrictfiniteDouble JSONnumbers rejectsbool/string/object/nonfinite/overflow/underflow/malformed arrays. Arrayorderpreserved, no CAN timingfallback; wholepipeline/scheduler notimplementedby parameter checks.',
 f'{len(cases)} isolatedSQLtests PASS; {native} native andnine sharedsuites. Confirmedpublish42/keyframe3/receive150/300applicationbytes preservedafterforeignCANrate rejected.'],
 validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native}OPC-UA-PubSub andnine sharedsuites',complete_release_gate='NOT_RUN'),
 not_certified=['FullDataSet/NetworkMessage codec/security/broker/metadata/state-machine execution, allheaderlayouts/optionalprofiles andactualphysicalbrokerlinkcapacity/E2E certification. Actualdevicesource/schedule/capabilities are not synthesized.','Cumulativeconsumers,README,releasegateandexactimageproductionremainpending.'])
(root/'work/opc-pubsub-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n');print(dict(tests=len(cases),native=native,fields=len(meanings),removed=len(before-after)))
