import json
from pathlib import Path
SOURCE='https://raw.githubusercontent.com/mz-automation/libiec61850/v1.6/src/goose/goose_publisher.c'
REVISION='libIEC61850 v1.6 publisher/server/config source and API1.6.0 read2026-10-01; IEC61850-8-1 Ed2.1 2020-02-21 publisher metadata, full licensed normative text not read'
declarations=[
 ('goose_profile','select',None,['LIBIEC61850_1_6_L2','DEVICE_SPECIFIC'],None,None,'Actual L2 GOOSE implementation/profile. Library-qualified proposals and bounds are not a universal IED profile or R-GOOSE UDP configuration.'),
 ('goose_edition','select',None,['ED1','ED2','ED2_1','DEVICE_SPECIFIC'],None,None,'Actual IEC edition and supported encoding/security extensions, unknown; edition alone does not select library firmware.'),
 ('goose_role','select',None,['PUBLISHER','SUBSCRIBER'],None,None,'Actual control-block role; publisher retransmission and subscriber loss/acceptance are distinct.'),
 ('goose_binding_source','text',None,None,None,None,'Required actual L2 MAC/PHY/port/VLAN/multicast path, not UDP/IP/MMS transport. Routed GOOSE needs an independent explicit transport path.'),
 ('goose_scl_source','text',None,None,None,None,'Required actual SCL/GoCB/dataset/member order and engineering revision, unknown.'),
 ('goose_device_source','text',None,None,None,None,'Required actual firmware/implementation/PIXIT/PICS/security and supported encoding source, unknown.'),
 ('goose_schedule_source','text',None,None,None,None,'Required actual state-change burst/retransmission/steady rates and competing LAN schedule source; link speed alone proves no event response time.'),
 ('goose_encoding','select',None,['ASN1_BER','FIXED_LENGTH','DEVICE_SPECIFIC'],None,None,'Actual GOOSE dataset/APDU encoding, unknown; reviewed library publisher uses BER, not universal fixed8-byte overhead for allData.'),
 ('goose_ethertype','number',None,None,0,65535,'Actual raw Ethernet GOOSE EtherType0x88B8=35000, distinct from Sampled Values, GSSE, IP or R-GOOSE.'),
 ('goose_appid','number',None,None,0,65535,'Actual uint16 header APPID in reviewed library API, unknown. Actual IEC edition allocation/publisher uniqueness remains SCL evidence, no arbitrary0x1000 installation default.'),
 ('goose_vlan_tag','boolean',None,None,None,None,'Actual L2 802.1Q tag presence, unknown; library createEx supports tag or no tag. PCP/VID apply only when tagged.'),
 ('goose_cb_ref','text',None,None,None,None,'Actual GoCB reference, unknown, matched to subscriber SCL; never universal65-char limit from an older IEC edition.'),
 ('goose_dataset_ref','text',None,None,None,None,'Actual dataset reference and stable member order, unknown.'),
 ('goose_id','text',None,None,None,None,'Actual optional GoID/reference from device/SCL, unknown; no manufactured project identifier.'),
 ('goose_conf_rev','number',None,None,0,4294967295,'Actual uint32 configuration revision, unknown; subscriber expected revision must match before operational acceptance.'),
 ('goose_expected_conf_rev','number',None,None,0,4294967295,'Actual commissioned subscriber expected configuration revision, unknown.'),
 ('goose_st_num','number',None,None,1,4294967295,'Actual state counter; reviewed library starts1, increments on state changes and skips0 on rollover. Initial1 is not a default for every observed frame.'),
 ('goose_sq_num','number',None,None,0,4294967295,'Actual sequence counter; reviewed library resets0 on state change, increments per publication and rolls over to1.'),
 ('goose_test','boolean',None,None,None,None,'Actual APDU test flag, unknown; distinct from edition-specific reserved-header simulation semantics and functional safety certification.'),
 ('goose_nds_com','boolean',None,None,None,None,'Actual needs-commissioning flag, unknown; no automatic false confirmation.'),
 ('goose_num_entries','number',None,None,0,4294967295,'Actual uint32 numDatSetEntries, unknown; must equal actual ordered allData element count.'),
 ('goose_actual_entries','number',None,None,0,4294967295,'Actual encoded allData element count, unknown; data type/quality and BER sizes need actual member evidence.'),
 ('goose_timestamp_bytes','number','Byte',None,8,8,'Reviewed library UTC timestamp content8 octets, before ASN.1 tag/length; clock accuracy/status bits remain actual device evidence.'),
 ('goose_all_data_bytes','number','Byte',None,0,None,'Actual encoded allData container bytes including BER tag/length, unknown. Cannot infer bytes from entry count alone.'),
 ('goose_apdu_bytes','number','Byte',None,1,None,'Actual full BER GOOSE APDU bytes, unknown, including references/counters/TAL/time/flags/allData and variable length encodings.'),
 ('goose_header_bytes','number','Byte',None,8,8,'Raw L2 APPID/Length/Reserved1/Reserved2 header8 octets, excluding APDU and Ethernet header/tags/padding/FCS.'),
 ('goose_length_bytes','number','Byte',None,8,65535,'Actual raw L2 Length =8+APDU octets, excluding Ethernet pad and FCS; must fit selected actual MAC-client MTU.'),
 ('goose_reserved1','number',None,None,0,65535,'Actual reserved header word1; reviewed library writes0. Edition/security simulation extensions need their own schema and source.'),
 ('goose_reserved2','number',None,None,0,65535,'Actual reserved header word2; reviewed library writes0. No blanket universal security-extension default.'),
 ('goose_phase','select',None,['STATE_CHANGE','EVENT_REPEAT','STABLE'],None,None,'Actual publisher state-change/event-repeat/steady phase, unknown; event repeats are not generic reliability retries.'),
 ('goose_schedule_origin','select',None,['SCL','STACK_FALLBACK','DEVICE_SPECIFIC'],None,None,'Actual interval source. Qualified library fallback defaults apply only when actual SCL MinTime/MaxTime are absent.'),
 ('goose_min_ms','number','ms',None,1,None,'Actual fast-repeat interval from SCL/device; library config fallback500ms only in explicit fallback profile, not universal4ms.'),
 ('goose_max_ms','number','ms',None,1,None,'Actual steady interval from SCL/device; library fallback5000ms only explicitly selected, not generic cycle100ms.'),
 ('goose_event_repeats','number','frame',None,0,None,'Actual library/configured fast-repeat count after state change; qualified config fallback2, no universal retry budget.'),
 ('goose_next_ms','number','ms',None,1,None,'Actual announced/selected next publication interval; must fit advertised TAL. Event transitions and actual source schedule remain explicit.'),
 ('goose_tal_basis_ms','number','ms',None,1,None,'Actual library MinTime/MaxTime basis chosen for this TAL by publisher state machine; no universal2-times-TAL convention.'),
 ('goose_tal_ms','number','ms',None,1,4294967295,'Actual uint32 timeAllowedToLive in milliseconds. Library server sets3 times selected MinTime/MaxTime; other IED PIXIT may differ.'),
 ('goose_operating_mode','select',None,['OPERATIONAL','TEST','MONITOR'],None,None,'Actual subscriber application mode, unknown; monitoring a test frame does not make it valid operational input.'),
 ('goose_accept_operational','boolean',None,None,None,None,'Actual operational acceptance, unknown; requires commissioned non-test data, matching revision/count, dataset/source evidence. No automatic acceptance from Ethernet rate.'),
 ('goose_acceptance_source','text',None,None,None,None,'Actual subscriber filter/control-block/dataset/test/loss/out-of-order/rollover and application acceptance evidence, unknown.'),
 ('goose_security_source','text',None,None,None,None,'Actual IEC62351/authentication/access assumptions and device support, unknown; sequence counters/CRC are not authentication or SIL certification.'),
]
folder=Path('docs/implementation-workloads/technology-full-parameter-audit-20261001')
eth=json.loads((folder/'individual/ethernet.json').read_text(encoding='utf-8'))
native={record['key']:record['meaning_and_applicability_review']+'; independently reviewed as explicit IEEE802.3 L2 transport for GOOSE, not a GOOSE-specific physical rate.'
        for record in eth['parameter_reviews'] if record['decision']=='NATIVE_OR_DECLARED_CONFIGURATION'}
native.update({key:meaning for key,_,_,_,_,_,meaning in declarations})
native['payload_bytes']='Actual underlying MAC-client GOOSE header+APDU octets, excluding pad/tags/FCS; allData and full APDU are separate native counts. No8-byte GOOSE application default.'
native['qos_priority']='Actual tagged PCP integer0..7; source-qualified libIEC61850/IEC recommendation4 proposal only for selected tagged library profile. Not a reservation or guaranteed response time.'
native['vlan_id']='Actual VID0 priority-tag or1..4094 VLAN. Library configured fallback0 is conditional explicit tagged implementation proposal; actual SCL/network assignment overrides it.'
removed={record['key']:record['meaning_and_applicability_review']+'; no universal GOOSE device guarantee.'
         for record in eth['parameter_reviews'] if record['decision']=='REMOVED_NOT_APPLICABLE'}
spec={'technology':'goose','native':native,'removed':removed,
 'sources':[SOURCE,'https://raw.githubusercontent.com/mz-automation/libiec61850/v1.6/src/iec61850/server/mms_mapping/mms_goose.c',
            'https://raw.githubusercontent.com/mz-automation/libiec61850/v1.6/config/stack_config.h',
            'https://support.mz-automation.de/doc/libiec61850/c/latest/group__goose__api__group.html',
            'https://libiec61850.com/documentation/stack-configuration-options/',
            'https://webstore.iec.ch/en/publication/66585',*eth['sources']],
 'revisions':[REVISION,*eth['source_revisions']],
 'scope':'Each original GOOSE field and every new native/shared Ethernet field reviewed individually. Actual raw L2 binding/SCL/edition/implementation and BER/state/retransmission/subscriber facts; explicit IEEE802.3 canonical transport, no UDP/IP/MMS or universal100M/8-byte/4ms assumption.',
 'validation':{'isolated_sql':True,'suite':'full_parameter_audit + standard_defaults + profile_semantics + capacity_can_schedule + parameter_review + required_parameters + physical_profiles','passed':0},
 'not_certified':['Complete licensed IEC61850-8-1 Ed2.1 normative field allocation/encoding/conformance; R-GOOSE/IEC62351/security/fixed-length/edition-specific extensions need separate verified profiles',
 'Actual SCL/GoCB/BER members and variable lengths, event burst/rollover/loss behavior and peer filtering; reviewed library source is not executed as a NIS publisher/subscriber',
 'Actual PHY/forwarding/interference/direction/multicast/VLAN scheduling and functional/safety acceptance; MODEL_MISSING remains']}
(Path(__file__).parent/'goose-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
