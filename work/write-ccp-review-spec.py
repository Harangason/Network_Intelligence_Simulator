"""Individual CCP2.1 decisions using ASAM and implementation-author sources."""
import json
from pathlib import Path

folder=Path(__file__).resolve().parent
can=json.loads((folder/'can-review-decisions.json').read_text(encoding='utf-8'))
native=dict(can['native'])
native.update({
 'bitrate':'Actual uniform CAN CC rate positive finite numeric<=1M, from A2L/controller/PHY. CCP defines no universal500k orminimum mode. No CANopen10k list, J1939application250k or XCP CANFD phase borrowing.',
 'payload_bytes':'Actual complete CCP CAN Data field1..8, includes native overhead. CRO/CRM/event fixed8; DAQ onePID plus0..7data. Memory-transferlogicalsize separate, notCANFD64 or8applicationbytesalways.',
 'can_frame_type':'CCP uses CAN CC DATAframes only, notCANopenlegacyRTR. Actual CAN identifier/DLC/timing/error state is lower transport proof, notCCP session/DAQ proof.',
 'ccp_revision':'RegisteredCCP2.1baselineproposal fromASAM1999-02-18. Legacyprotocol isdomainneutral; no XCP1.x features assumed.',
 'ccp_object':'Actual CRO/CRM/EVENT/DAQ type unknown. CROtoDevice, response/event/DAQtoHost. Each hasdifferent native overhead/rules; no onebroadcast/PDO default.',
 'ccp_station_address':'Actual16bitlogicalstationaddress0..65535unknown,CONNECTwireIntelorder. Mustbeuniqueamongdevices sharingCRO/DTOIDs. NotCANarbitrationID,node1defaultorCANopen7bitNodeID.',
 'ccp_station_byte_order':'CCPCONNECTstationaddress LITTLE_ENDIAN standardproposal, independentofactualECUdataendianness. Doesnotconfirmselectedaddress.',
 'ccp_byte_order':'ActualECU/A2L LITTLE_ENDIAN/BIG_ENDIANunknown; neverderivenetworkbyteorderfromCANorCONNECTstationencoding.',
 'ccp_cro_id':'ActualCROCANID0..2^29-1unknown. CANstandard11bitselectionlimits2047;no6FA/CCPexampleIDdefault.',
 'ccp_cro_id_format':'ActualCROBASE11/EXT29unknown; differentdevices/objects mayuse differentregisteredCANIDs. Notautoextendedfromindustry.',
 'ccp_dto_id':'Actualresponse/eventDTOCANID0..2^29-1unknown,not6FBexampledefault. Sessionlogicalconnection neededwithsharedIDs.',
 'ccp_dto_id_format':'ActualDTOBASE11/EXT29unknown; explicitly limitsactualID11bitifselected. NotinheritCROformatwithoutconfirmation.',
 'ccp_daq_can_id':'ActualselectedDAQlistCANIDunknown. Canbefixed/variable/sameDTOdependingdevice/A2L. NI default-1 isAPIinheritancesentinel, notactualonwireCANID.',
 'ccp_daq_can_id_format':'ActualDAQCANIDBASE11/EXT29unknown. LowerCANdataframe mustmatchselectedactualobjectID;scalarvaliditydoesnotderivefullDAQmapping.',
 'ccp_command':'ActualCROCMDuint8unknown. Command-specificparameterlayout/optionalcapability requiredevice/specverification; rangealone doesnotcertifycommandimplementation. No automaticdownload/flash/unlockoperation.',
 'ccp_command_counter':'ActualCROCTRuint8unknown; CRM mustmirrorit. NotCANdataDLC/PID/eventcounter. Wraparound mustbelinkedactualrequest/response sequence.',
 'ccp_response_counter':'ActualobservedCRMCTRuint8unknown. CheckedagainstknownactualCROCTR;EVENTcounterundefined/ignored andrejectedasmeaningfulEVENTfield.',
 'ccp_pid':'ActualDTOuint8PIDunknown. DAQ0..253,EVENT254,CRM255;CROusesCMDnotPID. NI narrative253messagecountconflictswithinclusive254PIDvalues; no copied253maximumlistcount.',
 'ccp_error_code':'ActualCRM/eventerroroctetunknownuint8; notDAQdata/automaticerrorzero confirmation. Specificreturncodes andcommandcorrelationstillrequired.',
 'ccp_data_bytes':'Actualnativeparameter/dataoctetsunknown0..7. CROspace<=6,CRM/event<=5,DAQ<=7 plusPID; notcomplete8wirebytes orfullmemoryblock.',
 'ccp_memory_address':'Actualu32ECUmemorypointerunknown. Access/region/alignment/type fromA2L/device; numericalrangealone provesno validaddressorpermission.',
 'ccp_address_extension':'Actualu8memorybank/segmentextensionunknown. ECU-specificmeaning,notdefault0 orCANstationaddr.',
 'ccp_transfer_bytes':'Actualcompletememoryblocksizeunknownnonnegativeinteger; canrequiremanyCRO/CRMframes. No8/65535 cap,downloaduses5bytechunksperNI butcommand/native variantsneedexplicitexecutionmodel.',
 'ccp_response_timeout_ms':'Actualhostcommandtimeoutunknownpositivefinite milliseconds. Novendor40ms/universal100ms. Deviceboundmustfitknownactualtimeout; nominalbusfrequency doesnotproveit.',
 'ccp_response_bound_ms':'Actualdeviceresponseboundunknownfinite>=0ms. Doesnotdefaultzero orincludeCANarbitration/hostqueueswithoutcorrelatedevidence.',
 'ccp_daq_list':'ActualselectedDAQlistindexunknownnonnegativeinteger. Actualavailablelistelements aredevice/A2L-defined; NIu32APIisnotuniformwirefieldmaximum.',
 'ccp_daq_odt':'ActualODTwithinselectedDAQlistunknownnonnegativeinteger. PIDs/addresses/entrysizesmappingneedactualODTtable, notjustODTnumber.',
 'ccp_daq_prescaler':'Actualeventreductionfactorunknownpositiveinteger>=1. Noautomatic1actualrate; fulldevice/nativewiremaximum mustbefromactualsupportedprofile, notassumedNIu32 orCCP16bitwithoutreadspec.',
 'ccp_event_period_ms':'Actualperiodiceventintervalunknownpositivefinite milliseconds, notNIScycle100ms asactualDAQrate. Event-drivenmode hasno universalperiod; unknownevent-arrivalboundneedsactualsource.',
 'ccp_event_mode':'Actualperiodic/eventdrivenDAQ modeunknown. HostDAQreadresamplerate independentfromECUevent/wireproduction; noasynchronouspollingresponse usedassynchronousDAQproof.',
 'ccp_connected':'Actualobservedlogicalsessionunknownboolean. NoTrueproposal. SharedCRO/DTOsetpermitsoneconnectedslave atatime; realCONNECT/status/DAQstatemachinenotimplemented.',
 'ccp_resource_protection':'Actualunprotected/seedkey/device-specificcapabilityunknown. Calibration/DAQ/programming resources maydiffer; no storedkey orautomaticunlock. Fullresource-specificmodelremaining.',
 'ccp_a2l_source':'Actualdevice/A2Lconfigurationreferenceunknowntext. Notinventedlibrarysource asactualdeviceprovenance; requires matchingrevision/model andmemory/transportdefinitions.'
})
spec={'technology':'ccp','native':native,'removed':can['removed'],
 'sources':['https://www.asam.net/standards/detail/mcd-1-ccp/',
            'https://download.ni.com/support/manuals/371601f.pdf',
            'https://www.csselectronics.com/pages/ccp-xcp-on-can-bus-calibration-protocol',*can['sources']],
 'revisions':['ASAM MCD-1 CCP2.1.0 February18 1999 officialcatalog; notclaiminglicensedfullspecificationread',
              'NI ECUMeasurement/Calibration371601F September2008 appendixA /4-5/4-6/nativeAPI references',
              'CSS Electronics authoredCCP packet-trace/CONNECTencoding accessed2026-10-01'],
 'scope':'Every registeredCCPfield andCANCCbearer, nativepacket/CRMcounter/DAQsize andIDconstraints; independentSQLretention andforeignprofile rejection.',
 'validation':{'isolated_sql':True,'suite':'full_parameter_audit + standard_defaults + profile_semantics + capacity_can_schedule + parameter_review + required_parameters','passed':0},
 'not_certified':['ExecutableCCP command/response/session/DAQODT/scheduling andcapacitymodel remainMODEL_MISSING',
                  'Fulloptionalcommands/returncodes/prescalerwirebounds/nativeper-commandmemorylayout requirefullspecandactualdevice/A2Lrevision',
                  'Actualdevicecapabilities/resources/memorypermissions/protectionandobservedcounter/sessionstate',
                  'ActualtopologysharedCANIDs/stationuniqueness/DAQPIDmapping/correlatedtimeouts andcommand/DAQinterference']}
(folder/'ccp-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
