"""MIL-STD-1553C words, command ownership and qualified electrical envelopes."""

CORE = 'https://www.astronics.com/docs/default-source/ballard-technology/certificates/mil-std-1553c-dla.pdf?sfvrsn=17e2b258_2'
STATUS = 'https://quicksearch.dla.mil/qsDocDetails.aspx?ident_number=36973'
EDITION = 'MIL_STD_1553C_2018'
SOURCES = {CORE: 'DoD MIL-STD-1553C 28 February2018; sections3/4 and mandatory AppendixA; PDF10-51, tablesI/II and figures3/6-13',
           STATUS: 'DLA ASSIST36973 active revisionC/28February2018; status checked2026-10-02'}
DECLARATIONS = []


def d(key, kind, meaning, lo=None, hi=None, unit=None, options=None, integer=False):
    DECLARATIONS.append(dict(key='ms_'+key, type=kind, description=meaning, source=CORE,
        source_revision=SOURCES[CORE], min=lo, max=hi, unit=unit, options=options, integer=integer))


for key, meaning, options in [
    ('edition', 'Actual selected standard and revision;1553A/B or enhanced rate extensions require their own registered revision, not silent C equivalence.', [EDITION, 'REGISTERED_EDITION']),
    ('application', 'Actual basic C scope versus AppendixA.2 Army/Navy/AirForce dual-standby restrictions; industry selection does not choose this profile.', ['BASE_C', 'A2_ARMY', 'A2_NAVY', 'A2_AIR_FORCE', 'REGISTERED_APPLICATION']),
    ('role', 'Actual terminal acting as bus controller, remote terminal or passive monitor; only BC initiates command ownership.', ['BC', 'RT', 'BM']),
    ('message', 'Actual Figure6/7 command/response transfer format; application group names do not define broadcast.', ['BC_RT', 'RT_BC', 'RT_RT', 'BC_BROADCAST', 'RT_BROADCAST', 'MODE', 'MODE_BROADCAST']),
    ('condition', 'Actual normal completed transfer versus busy transmitter status-only reply; invalid commands/data require separate behavior evidence.', ['NORMAL', 'BUSY_TRANSMITTER']),
    ('coupling', 'Actual transformer versus direct stub at this terminal. Spec electrical limits depend on test point and coupling.', ['TRANSFORMER', 'DIRECT']),
    ('redundancy', 'Actual single, dual standby or separately qualified multiple path architecture; dual links are not concurrent aggregate throughput.', ['SINGLE', 'DUAL_STANDBY', 'MULTIPLE_REGISTERED']),
    ('stub_policy', 'Recommended short stub envelope versus documented installed longer exception allowed by4.5.1.5; no guessed bus length.', ['RECOMMENDED_SHORT', 'QUALIFIED_EXCEPTION']),
    ('encoding', 'ManchesterII bi-phase level, logic1positive/negative and0negative/positive; no CAN bit stuffing.', ['MANCHESTER_II_BIPHASE_L']),
    ('bit_order', 'MSB first within data word and highest precision word first; quantities can be bit packed.', ['MSB_FIRST']),
    ('parity', 'Odd parity over sixteen information bits, excluding three-bit sync waveform.', ['ODD']),
    ('measurement_point', 'Actual electrical/timing observation: terminal stubA versus loaded terminal test fixtureA versus transformerB; these are not interchangeable.', ['STUB_A', 'TERMINAL_FIXTURE_A', 'TRANSFORMER_B']),
    ('receiver_region', 'Actual valid-input versus required no-response low-level region; intermediate region has no guaranteed response.', ['RESPOND', 'NO_RESPONSE', 'INDETERMINATE']),
    ('power_state', 'Actual transmit, receive/power-off or startup/shutdown; different noise tests apply.', ['TRANSMIT', 'RECEIVE_OR_OFF', 'POWER_TRANSITION'])
]: d(key, 'select', meaning, options=options)

for key, meaning in [
    ('revision', 'Actual standard edition, installed terminal revision, options and applicable AppendixA.2 scope.'),
    ('registered_source', 'Actual independently registered edition/application/redundancy schema, not a rate guess.'),
    ('binding_source', 'Actual canonical BC/RT/BM identities, active bus, unique address map and physical ownership.'),
    ('device_source', 'Actual terminal implemented subaddresses/counts/mode/status/broadcast/self-test and failsafe hardware capabilities.'),
    ('encoding_source', 'Actual complete command/data/status codec, packed signal bits, unused zero bits, sync and odd-parity qualification.'),
    ('schedule_source', 'Actual controller command schedule, periods, response and no-response paths, retry/bus switch traffic; C specifies no universal retry count.'),
    ('physical_source', 'Actual cable/termination/stub/coupler/connector/load/fault topology and worst-case signal integrity.'),
    ('measurement_source', 'Actual calibrated test points, fixture loads, frequency/amplitude/temperature and measured bounds.'),
    ('capacity_source', 'Actual full message sequence including both RT responses, gap references, BC ownership, failures and retries.'),
    ('acceptance_source', 'Actual functional E2E/freshness/safety acceptance; odd parity and800us hardware timeout do not prove application safety.'),
    ('stub_exception_source', 'Actual signal integrity and fault qualification for a longer-than-recommended stub.'),
    ('redundancy_source', 'Actual isolated alternate paths, single-event routing and allowed bus handover behavior.'),
    ('command_bus_id', 'Actual bus carrying this command, not arbitrary A/B default.'),
    ('target_bus_id', 'Actual redundant transmitter affected by shutdown/override; must differ from command bus.'),
    ('mode_source', 'Actual RT support for this mode and associated data word; reserved modes cannot be redefined.'),
    ('emc_source', 'Actual applicable MIL-STD-464 edition and EMC qualification; this profile does not implement that external test standard.'),
    ('noise_test_source', 'Actual continuous random-word AWGN test and TableII acceptance/rejection record, not a reliability probability default.'),
    ('address_wiring_source', 'Actual AppendixA.2 external address wiring, power-up validation and single-point-failure protection.'),
    ('wrap_source', 'Actual wrap-around receive/transmit buffers and no-intervening-command sequence qualification.'),
]: d(key, 'text', meaning)

for key, meaning, lo, hi, unit, integer in [
    ('observed_bitrate_bps', 'Actual measured information bit clock999000..1001000; nominal1M and short-term stability are distinct.', 999000, 1001000, 'bit/s', True),
    ('short_stability_hz', 'Actual magnitude of one-second short-term clock stability, at most100Hz; not an arbitrary ppm default.', 0, 100, 'Hz', False),
    ('word_info_bits', 'Sixteen information bits in each command/data/status word.', 16, 16, 'bit', True),
    ('sync_bit_times', 'Invalid Manchester sync spans three bit times; it is not three ordinary data bits.', 3, 3, 'UI', True),
    ('parity_bits', 'One odd parity bit per word.', 1, 1, 'bit', True),
    ('word_bit_times', 'Twenty serialized bit times per word including sync and parity.', 20, 20, 'UI', True),
    ('command_address', 'Actual five-bit first receive/mode command target;31 only broadcast and never a unique RT.', 0, 31, None, True),
    ('source_rt_address', 'Actual unique transmitting RT address for RT_BC/RT_RT/RT_BROADCAST, not31.', 0, 30, None, True),
    ('subaddress', 'Actual five-bit subaddress;0/31 exclusively mode control,1..30 data, no default installed address.', 0, 31, None, True),
    ('tr_bit', 'Actual first command transmit/receive bit:0receive,1transmit; mode meanings follow TableI.', 0, 1, None, True),
    ('requested_data_words', 'Actual normal command count1..32; encoded count0means32, never zero data.', 1, 32, 'word', True),
    ('count_code', 'Actual five-bit data count field for non-mode commands, not a CAN DLC.', 0, 31, None, True),
    ('data_words', 'Actual serialized data words, excluding command/status; busy transmitter or no-data mode can carry0.', 0, 32, 'word', True),
    ('mode_code', 'Actual TableI defined mode;9..15/22..31 reserved and unavailable.', 0, 31, None, True),
    ('command_words', 'Actual one BC command, or two contiguous commands for RT-to-RT formats.', 1, 2, 'word', True),
    ('status_words', 'Actual response count; receiving broadcast RTs suppress status but transmitting RT still responds.', 0, 2, 'word', True),
    ('response_count', 'Actual RT turnaround intervals: RT_RTnormal2,RTbroadcast1,BCbroadcast0; no Ethernet ACK heuristic.', 0, 2, None, True),
    ('total_words', 'Actual sum of command/data/status words, before sync/parity expansion.', 1, 36, 'word', True),
    ('wire_bit_times', 'Actual20times totalwords; Manchester transitions do not double this information bit clock.', 20, 720, 'UI', True),
    ('data_octets', 'Actual two encoded data octets per serialized data word; not application payload guarantee.', 0, 64, 'byte', True),
    ('response1_us', 'Actual first RT response midpoint-to-mid-sync at that RT pointA,4..12us. It is not idle duration or E2E latency.', 4, 12, 'us', False),
    ('response2_us', 'Actual second receiving-RT response for normal RT_RT only,4..12us at that RTpointA.', 4, 12, 'us', False),
    ('intermessage_gap_us', 'Actual last parity mid-bit to next command mid-sync at BCpointA,at least4us; excludes neither propagation nor reference offsets automatically.', 4, None, 'us', False),
    ('no_response_timeout_us', 'Actual terminal no-response wait,at least14us from its own last parity midpoint to expected status midsync; not500ms scenario timeout.', 14, None, 'us', False),
    ('hardware_failsafe_us', 'Actual implemented transmitter hardware timeout no greater800us and must permit correct commanded transmission.', 0, 800, 'us', False),
    ('active_controllers', 'Only one terminal in active control of each bus at a time; backup BCs are not simultaneous arbiters.', 1, 1, None, True),
    ('bus_count', 'Actual physical redundant paths, independent from connected terminal count.', 1, None, None, True),
    ('active_bus_count', 'Normal dual-standby behavior has one active path; superseding commands are separately qualified exceptions.', 1, None, None, True),
    ('interbus_isolation_db', 'Measured active-to-inactive terminal output isolation at fixtureA,at least45dB.', 45, None, 'dB', False),
    ('retry_attempts', 'Actual controller retry policy count from workload/schedule; no standard universalzero/three.', 0, None, None, True),
    ('retry_delay_us', 'Actual controller retry/bus switch timing from schedule,not CAN retry or exponential IPbackoff.', 0, None, 'us', False),
    ('instrumentation_bit', 'Status instrumentation bit always zero, including when option unused.', 0, 0, None, True),
    ('reserved_status_bits', 'Three status reserved bits always zero.', 0, 0, None, True),
    ('cable_nominal_ohm', 'Selected cable nominal differential impedance70..85ohm at1MHz,not universal78ohm.', 70, 85, 'ohm', False),
    ('cable_actual_ohm', 'Actual measured differential impedance70..85ohm for AppendixA.2 at1MHz.', 0, None, 'ohm', False),
    ('cable_pf_ft', 'Actual wire-to-wire distributed cable capacitance no greater30pF/ft.', 0, 30, 'pF/ft', False),
    ('twists_ft', 'Actual360degree twists per foot,minimum4.', 4, None, '1/ft', False),
    ('cable_shield_percent', 'Actual cable shield coverage:base>=75percent,AppendixA.2>=90.', 75, 100, '%', False),
    ('junction_shield_percent', 'Actual continuous connector/coupler/junction shielding coverage>=75percent.', 75, 100, '%', False),
    ('attenuation_db_100ft', 'Measured cable loss at1MHz,maximum1.5dB/100ft.', 0, 1.5, 'dB/100ft', False),
    ('termination_ohm', 'Actual end termination within selected nominalZo+-2percent; neither a universal120ohm nor78ohm.', 0, None, 'ohm', False),
    ('termination_count', 'Both main cable ends are terminated.', 2, 2, None, True),
    ('stub_ft', 'Actual stub length including internal cable;recommended transformer<=20ft/direct<=1ft, qualified longer exceptions allowed.', 0, None, 'ft', False),
    ('isolation_resistor_ohm', 'Actual each series resistor:transformer0.75Zo+-2percent;direct55ohm+-2percent.', 0, None, 'ohm', False),
    ('fault_impedance_ohm', 'Actual failed-branch reflected bus load>=1.5Zo for transformer or110ohm direct.', 0, None, 'ohm', False),
    ('turns_ratio', 'Actual high-turn isolation-resistor side to low-turn ratio1.41+-3percent,not1:1.', 0, None, None, False),
    ('transformer_open_ohm', 'Coupling transformerB open-circuit impedance strictly>3000ohm at75kHz..1MHz,1Vrms sine.', 3000, None, 'ohm', False),
    ('transformer_droop_percent', 'TransformerB droop<=20percent at250kHz27Vpp square input and360ohm+-5percent fixture.', 0, 20, '%', False),
    ('transformer_ringing_v', 'Magnitude of transformerB overshoot/ringing strictly<1Vpeak in specified test.', 0, 1, 'Vpeak', False),
    ('transformer_cmrr_db', 'Coupling transformer common-mode rejection strictly>45dB at1MHz.', 45, None, 'dB', False),
    ('fixture_ohm', 'Actual terminal fixture load70ohm+-2percent transformer or35ohm+-2percent direct.', 0, None, 'ohm', False),
    ('stub_vpp', 'Actual loaded installed stubA voltage:transformer1..14Vpp,direct1.4..20Vpp including fault/worstTX.', 0, None, 'Vpp', False),
    ('tx_vpp', 'Measured terminal fixtureA transmitter output:transformer18..27Vpp,direct6..9Vpp.', 0, None, 'Vpp', False),
    ('tx_crossing_ns', 'Magnitude of transmitter zero-crossing deviation from previous ideal crossing<=25ns.', 0, 25, 'ns', False),
    ('tx_rise_ns', 'Actual10..90percent output transition100..300ns,not propagation delay.', 100, 300, 'ns', False),
    ('tx_fall_ns', 'Actual90..10percent output transition100..300ns.', 100, 300, 'ns', False),
    ('tx_ringing_mv', 'Magnitude of fixtureA transmitter distortion<=900mVpeak transformer/300direct.', 0, None, 'mVpeak', False),
    ('off_noise_mvrms', 'Receiving or power-off fixtureA noise<=14mVrms transformer/5direct.', 0, None, 'mVrms', False),
    ('symmetry_mv', 'Magnitude of residual output2.5us after parity midpoint,<=250mVpeak transformer/90direct; six specified patterns up to33words.', 0, None, 'mVpeak', False),
    ('rx_vpp', 'Actual input amplitude at stubA with response/no-response region; unknown intermediate region is not guaranteed.', 0, None, 'Vpp', False),
    ('rx_crossing_ns', 'Magnitude of acceptable input zero-crossing deviation<=150ns.', 0, 150, 'ns', False),
    ('rx_input_ohm', 'Nontransmitting/power-off terminal input impedance at75kHz..1MHz:transformer>=1000/direct>=2000ohm.', 0, None, 'ohm', False),
    ('rx_common_mode_v', 'Qualified peak input line-to-ground common mode tolerance at least10V overDC..2MHz.', 10, None, 'Vpeak', False),
    ('noise_awgn_mvrms', 'Actual prescribed AWGN test140mVrms transformer/200direct over1kHz..4MHz.', 0, None, 'mVrms', False),
    ('noise_input_vpp', 'Actual prescribed noise-test input2.1Vpp transformer/3Vpp direct atstubA.', 0, None, 'Vpp', False),
    ('noise_word_error_rate', 'Qualified maximum word error rate1e-7 under prescribed AWGN test; not universal undetected-bit risk or application reliability.', 0, .0000001, None, False),
    ('reset_bound_ms', 'Actual AppendixA.2 reset complete within5ms after status parity midpoint; not universal operating-cycle default.', 0, None, 'ms', False),
    ('self_test_bound_ms', 'Actual AppendixA.2 implemented initiate-self-test completion/results within100ms.', 0, None, 'ms', False),
    ('rt_rt_validation_us', 'Actual AppendixA.2 receiving RT first-data validation threshold57+-3us referenced to receive-command parity midpoint.', 0, None, 'us', False),
    ('wrap_subaddress', 'Actual implemented wrap-around subaddress1..30;30is desired,not an assigned installed address.', 1, 30, None, True),
]: d(key, 'number', meaning, lo, hi, unit, integer=integer)

for key, meaning in [
    ('broadcast_supported', 'Actual destination RT implements broadcast; not inferred from data multicast labels.'),
    ('dynamic_control_supported', 'Actual RT supports offered control and acceptance bit; handover occurs after its status completes.'),
    ('address_valid', 'Actual external address validated at power-up for AppendixA.2;false prevents any RT response.'),
    ('both_mode_subaddresses', 'Actual AppendixA.2 both0and31same-mode semantics capability.'),
    ('required_modes_supported', 'Actual AppendixA.2 RT minimum2/4/5/8mode capability and BC all TableI modes.'),
    ('minimum_formats_supported', 'Actual AppendixA.2 required RT data+mode formats and BC allformats.'),
    ('busy_bit', 'Actual status busy condition; busy transmitting RT sends only status, no requested data.'),
    ('message_error_bit', 'Actual word/count/continuity error state; invalid receive data suppresses status and invalidates whole message.'),
    ('broadcast_received_bit', 'Actual previous validated command broadcast state; not a confirmation of all receivers.'),
    ('service_request_bit', 'Actual implemented exception service request; ORed subsystem requests need separate identifying data.'),
    ('subsystem_flag', 'Actual associated subsystem fault, not a generated safety assurance.'),
    ('terminal_flag', 'Actual RT self-test/fault indication,not application data validity proof.'),
    ('dynamic_control_acceptance', 'Actual control offer accepted/rejected in status; unsupported function staysfalse.'),
    ('dual_terminal_connectors', 'Actual Navy AppendixA.2 both transformer/direct external connectors capability.'),
    ('positive_center_pin', 'Actual AppendixA.2 concentric connector center pin carries positive Manchester and ring negative.'),
    ('failsafe_hardware', 'Actual hardware implemented transmitter timeout, not software-only assumption.'),
    ('unused_bits_zero', 'Actual every unused information bit encodedzero, including bit-packed signals.'),
]: d(key, 'boolean', meaning)

REQUIRED = ('edition', 'application', 'role', 'message', 'condition', 'revision', 'binding_source', 'device_source',
            'encoding_source', 'schedule_source', 'physical_source', 'capacity_source', 'acceptance_source')
REMOVED = {k: 'No universal MIL1553 field: actual BC schedule/options/device buffers/retries/physical scope must be explicitly qualified, not inherited CAN/IP queue/priority/gateway defaults.'
           for k in ('queue_size', 'queue_policy', 'qos_priority', 'traffic_class', 'reserved_bandwidth_percent',
                     'rate_limit_bit_s', 'retransmission_enabled', 'retransmission_rate', 'retry_limit', 'retransmission_delay_ms',
                     'sync_method', 'gateway_maximum_throughput', 'gateway_input_buffer', 'gateway_output_buffer',
                     'gateway_maximum_routes', 'gateway_maximum_messages_s')}
MODES = {0:(1,0,False),1:(1,0,True),2:(1,0,False),3:(1,0,True),4:(1,0,True),5:(1,0,True),
         6:(1,0,True),7:(1,0,True),8:(1,0,True),16:(1,1,False),17:(0,1,True),18:(1,1,False),
         19:(1,1,False),20:(0,1,True),21:(0,1,True)}


def semantics():
    rules = []
    def r(key, when=None, **kw):
        raw = key in ('bitrate_bps', 'payload_bytes', 'local_timing_evidence')
        rules.append(dict(when={'ms_edition':EDITION, **{'ms_'+k:v for k,v in (when or {}).items()}},
                          parameter=key if raw else 'ms_'+key, source=CORE, source_revision=SOURCES[CORE], **kw))
    r('bitrate_bps', allowed=[1000000])
    r('local_timing_evidence', allowed=[])
    for selector in ('edition','application','redundancy'):
        for value in ('REGISTERED_EDITION','REGISTERED_APPLICATION','MULTIPLE_REGISTERED'):
            if selector=='edition' and value=='REGISTERED_EDITION':
                rules.append(dict(when={'ms_edition':value},parameter='ms_registered_source',required=True,source=CORE,source_revision=SOURCES[CORE]))
            elif (selector,value) in (('application','REGISTERED_APPLICATION'),('redundancy','MULTIPLE_REGISTERED')):
                r('registered_source',{selector:value},required=True)
    for key, value in [('word_info_bits',16),('sync_bit_times',3),('parity_bits',1),('word_bit_times',20),
                       ('active_controllers',1),('termination_count',2),('instrumentation_bit',0),('reserved_status_bits',0)]:r(key,allowed=[value])
    r('encoding', allowed=['MANCHESTER_II_BIPHASE_L']);r('bit_order',allowed=['MSB_FIRST']);r('parity',allowed=['ODD'])
    r('unused_bits_zero',allowed=[True]);r('failsafe_hardware',when_present=['ms_hardware_failsafe_us'],allowed=[True],required=True)
    r('hardware_failsafe_us',exclusive_minimum=0)
    r('count_code',equal_expression={'integer_remainder':['ms_requested_data_words',32]})
    r('requested_data_words',when_present=['ms_count_code'],required=True)
    r('data_octets',equal_expression={'product':['ms_data_words',2]})
    r('payload_bytes',maximum_parameter='ms_data_octets')
    r('data_words',when_present=['payload_bytes'],required=True);r('data_octets',when_present=['payload_bytes'],required=True)
    r('total_words',equal_expression={'sum':['ms_command_words','ms_status_words','ms_data_words']})
    for key in ('command_words','status_words','data_words'):r(key,when_present=['ms_total_words'],required=True)
    r('wire_bit_times',equal_expression={'product':['ms_total_words',20]})
    r('total_words',when_present=['ms_wire_bit_times'],required=True)
    table={'BC_RT':(1,1,1,0),'RT_BC':(1,1,1,1),'RT_RT':(2,2,2,0),
           'BC_BROADCAST':(1,0,0,0),'RT_BROADCAST':(2,1,1,0)}
    for message,(commands,status,responses,tr) in table.items():
        r('command_words',{'message':message},allowed=[commands]);r('tr_bit',{'message':message},allowed=[tr])
        r('status_words',{'message':message,'condition':'NORMAL'},allowed=[status])
        r('response_count',{'message':message,'condition':'NORMAL'},allowed=[responses])
        r('subaddress',{'message':message},minimum=1,maximum=30,required=True)
        r('requested_data_words',{'message':message},required=True)
        r('count_code',{'message':message},required=True)
        r('data_words',{'message':message,'condition':'NORMAL'},equal_parameter='ms_requested_data_words')
    for message in ('BC_RT','RT_BC','RT_RT','MODE'):
        r('command_address',{'message':message},maximum=30,required=True)
    for message in ('BC_BROADCAST','RT_BROADCAST','MODE_BROADCAST'):
        r('command_address',{'message':message},allowed=[31],required=True)
        r('broadcast_supported',{'message':message},allowed=[True],required=True)
    for message in ('RT_BC','RT_RT','RT_BROADCAST'):
        r('source_rt_address',{'message':message},required=True)
    r('source_rt_address',{'message':'RT_BC'},equal_parameter='ms_command_address')
    r('source_rt_address',{'message':'RT_RT'},not_equal_parameter='ms_command_address')
    r('busy_bit',{'condition':'BUSY_TRANSMITTER'},allowed=[True],required=True)
    r('message',{'condition':'BUSY_TRANSMITTER'},allowed=['RT_BC','RT_RT','RT_BROADCAST','MODE'])
    r('data_words',{'condition':'BUSY_TRANSMITTER'},allowed=[0])
    r('busy_bit',{'condition':'NORMAL'},allowed=[False])
    # Receiving RT status after a busy transmitting RT is implementation/message-error dependent;
    # no unconditional second-response/count proposal is manufactured for that state.
    r('status_words',{'condition':'BUSY_TRANSMITTER'},minimum=1)
    for message in ('MODE','MODE_BROADCAST'):
        r('subaddress',{'message':message},allowed=[0,31],required=True)
        r('mode_code',{'message':message},allowed=list(MODES),required=True)
        r('mode_source',{'message':message},required=True)
        r('command_words',{'message':message},allowed=[1]);r('payload_bytes',{'message':message},allowed=[0])
        for key in ('requested_data_words','count_code'):r(key,{'message':message},allowed=[])
        for code,(tr,data,broadcast) in MODES.items():
            w={'message':message,'mode_code':code}
            r('tr_bit',w,allowed=[tr],required=True)
            r('data_words',{**w,'condition':'NORMAL'},allowed=[data])
            r('status_words',{**w,'condition':'NORMAL'},allowed=[1 if message=='MODE' else 0])
            r('response_count',{**w,'condition':'NORMAL'},allowed=[1 if message=='MODE' else 0])
            if message=='MODE_BROADCAST' and not broadcast:r('mode_code',w,allowed=[])
    for key in ('response1_us','response2_us'):r(key,{'response_count':0},allowed=[])
    r('response2_us',{'response_count':1},allowed=[])
    r('message',when_present=['ms_response2_us'],allowed=['RT_RT'])
    for key in ('response1_us','response2_us','intermessage_gap_us','no_response_timeout_us',
                'observed_bitrate_bps','short_stability_hz','hardware_failsafe_us'):
        r('measurement_source',when_present=['ms_'+key],required=True)
    for value,count in [('SINGLE',1),('DUAL_STANDBY',2)]:r('bus_count',{'redundancy':value},allowed=[count])
    r('active_bus_count',{'redundancy':'DUAL_STANDBY'},allowed=[1])
    r('redundancy_source',{'redundancy':'DUAL_STANDBY'},required=True)
    for code in (4,5):r('redundancy',{'mode_code':code},allowed=['DUAL_STANDBY'])
    for code in (20,21):r('bus_count',{'mode_code':code},minimum=3)
    for code in (4,5,20,21):
        r('target_bus_id',{'mode_code':code},not_equal_parameter='ms_command_bus_id',required=True)
        r('command_bus_id',{'mode_code':code},required=True)
    r('dynamic_control_supported',{'mode_code':0},allowed=[True],required=True)
    r('dynamic_control_acceptance',{'dynamic_control_supported':False},allowed=[False])
    r('broadcast_received_bit',{'broadcast_supported':False},allowed=[False])
    for application in ('A2_ARMY','A2_NAVY','A2_AIR_FORCE'):
        w={'application':application}
        r('redundancy',w,allowed=['DUAL_STANDBY'])
        r('cable_actual_ohm',w,minimum=70,maximum=85)
        r('cable_shield_percent',w,minimum=90)
        r('reset_bound_ms',w,maximum=5);r('self_test_bound_ms',w,maximum=100)
        r('rt_rt_validation_us',w,minimum=54,maximum=60)
        r('message',w,forbidden=['BC_BROADCAST','RT_BROADCAST'])
        for key in ('both_mode_subaddresses','required_modes_supported','minimum_formats_supported','positive_center_pin'):
            r(key,w,allowed=[True])
        r('address_wiring_source',{**w,'role':'RT'},required=True)
        r('address_valid',{**w,'role':'RT'},allowed=[True],required=True)
        if application!='A2_NAVY':r('coupling',w,allowed=['TRANSFORMER'])
        else:r('dual_terminal_connectors',w,allowed=[True])
    r('mode_code',{'application':'A2_AIR_FORCE'},forbidden=[0])
    r('termination_ohm',minimum_expression={'product':['ms_cable_nominal_ohm',.98]},
      maximum_expression={'product':['ms_cable_nominal_ohm',1.02]},exact_decimal_bounds=True)
    r('cable_nominal_ohm',when_present=['ms_termination_ohm'],required=True)
    for coupling,recommended in [('TRANSFORMER',20),('DIRECT',1)]:
        w={'coupling':coupling};r('stub_ft',{**w,'stub_policy':'RECOMMENDED_SHORT'},maximum=recommended)
        r('stub_policy',w,when_present=['ms_stub_ft'],required=True)
        r('stub_exception_source',{**w,'stub_policy':'QUALIFIED_EXCEPTION'},required=True)
        if coupling=='TRANSFORMER':
            r('isolation_resistor_ohm',w,minimum_expression={'product':['ms_cable_nominal_ohm',.75,.98]},
              maximum_expression={'product':['ms_cable_nominal_ohm',.75,1.02]},exact_decimal_bounds=True)
            r('cable_nominal_ohm',w,when_present=['ms_isolation_resistor_ohm'],required=True)
            r('fault_impedance_ohm',w,minimum_expression={'product':['ms_cable_nominal_ohm',1.5]},exact_decimal_bounds=True)
            r('cable_nominal_ohm',w,when_present=['ms_fault_impedance_ohm'],required=True)
            r('turns_ratio',w,minimum=1.3677,maximum=1.4523,exact_decimal_bounds=True)
        else:
            r('isolation_resistor_ohm',w,minimum=53.9,maximum=56.1,exact_decimal_bounds=True)
            r('fault_impedance_ohm',w,minimum=110)
            for key in ('turns_ratio','transformer_open_ohm','transformer_droop_percent','transformer_ringing_v','transformer_cmrr_db'):r(key,w,allowed=[])
        fixture,stublo,stubhi,txlo,txhi,distortion,noise,symmetry,rxlo,rxhi,nothi,impedance,awgn,testinput=(
            (70,1,14,18,27,900,14,250,.86,14,.20,1000,140,2.1) if coupling=='TRANSFORMER'
            else (35,1.4,20,6,9,300,5,90,1.2,20,.28,2000,200,3))
        r('fixture_ohm',w,minimum=fixture*.98,maximum=fixture*1.02,exact_decimal_bounds=True)
        r('stub_vpp',w,minimum=stublo,maximum=stubhi)
        r('tx_vpp',w,minimum=txlo,maximum=txhi)
        r('tx_ringing_mv',w,maximum=distortion);r('off_noise_mvrms',w,maximum=noise);r('symmetry_mv',w,maximum=symmetry)
        r('rx_vpp',{**w,'receiver_region':'RESPOND'},minimum=rxlo,maximum=rxhi)
        r('rx_vpp',{**w,'receiver_region':'NO_RESPONSE'},maximum=nothi)
        r('receiver_region',w,when_present=['ms_rx_vpp'],required=True)
        r('rx_input_ohm',w,minimum=impedance)
        r('noise_awgn_mvrms',w,allowed=[awgn]);r('noise_input_vpp',w,allowed=[testinput])
    r('transformer_open_ohm',exclusive_minimum=3000)
    r('transformer_ringing_v',exclusive_maximum=1)
    r('transformer_cmrr_db',exclusive_minimum=45)
    for key in ('fixture_ohm','stub_vpp','tx_vpp','tx_crossing_ns','tx_rise_ns','tx_fall_ns','tx_ringing_mv',
                'off_noise_mvrms','symmetry_mv','rx_vpp','rx_crossing_ns','rx_input_ohm','rx_common_mode_v',
                'transformer_open_ohm','transformer_droop_percent','transformer_ringing_v','transformer_cmrr_db',
                'turns_ratio','interbus_isolation_db','cable_actual_ohm'):
        r('measurement_source',when_present=['ms_'+key],required=True)
        r('coupling',when_present=['ms_'+key],required=True)
    for key in ('tx_vpp','fixture_ohm','tx_ringing_mv','off_noise_mvrms','symmetry_mv','interbus_isolation_db'):
        r('measurement_point',when_present=['ms_'+key],allowed=['TERMINAL_FIXTURE_A'],required=True)
    for key in ('stub_vpp','rx_vpp','rx_input_ohm','rx_common_mode_v'):
        r('measurement_point',when_present=['ms_'+key],allowed=['STUB_A'],required=True)
    for key in ('transformer_open_ohm','transformer_droop_percent','transformer_ringing_v'):
        r('measurement_point',when_present=['ms_'+key],allowed=['TRANSFORMER_B'],required=True)
    for key in ('noise_awgn_mvrms','noise_input_vpp','noise_word_error_rate'):r('noise_test_source',when_present=['ms_'+key],required=True)
    r('wrap_source',when_present=['ms_wrap_subaddress'],required=True)
    return dict(rate_model={'type':'FIXED_LINK_RATE','fields':['bitrate_bps'],'fixed_bps':1000000},
        required_parameters=['ms_'+k for k in REQUIRED], native_parameter_prefixes=['ms_'], parameter_evidence_scope='EXPLICIT_LAYER',
        parameter_constraints=rules, defaults_review={'values':{},'source':CORE,'source_revision':SOURCES[CORE],'status':'PROPOSED'},
        physical_layer_profile_id='mil1553_actual_cable_stub_and_terminal_test_points',
        medium_access_model='ONE_ACTIVE_BC_COMMAND_RESPONSE', arbitration_model_id='BC_SCHEDULE_AND_VALID_COMMAND_SUPERSESSION',
        mechanisms={'encoding':['MANCHESTER_II_MSB_ODD_PARITY_20_BIT_TIME_WORD'],
            'medium_access':['BC_COMMAND_RESPONSE_HALF_DUPLEX_NOT_CAN_ARBITRATION'],
            'timing':['PARITY_MIDPOINT_TO_SYNC_MIDPOINT_NOT_RAW_IDLE'],
            'redundancy':['ACTUAL_SINGLE_OR_DUAL_STANDBY_OR_REGISTERED_MULTI_BUS'],
            'integrity':['ODD_WORD_PARITY_NOT_AUTHENTICATION_OR_FUNCTIONAL_SAFETY']})


def fields():
    result=[]
    constants={'word_info_bits':16,'sync_bit_times':3,'parity_bits':1,'word_bit_times':20,
               'encoding':'MANCHESTER_II_BIPHASE_L','bit_order':'MSB_FIRST','parity':'ODD',
               'active_controllers':1,'termination_count':2,'instrumentation_bit':0,'reserved_status_bits':0,'unused_bits_zero':True}
    for spec in DECLARATIONS:
        item={k:v for k,v in spec.items() if v is not None}; key=spec['key'].removeprefix('ms_')
        item.update(label=key.replace('_',' '),category='physical',scope='network',editable=True,
            required=key in REQUIRED,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',
            validation_relevant=True,simulation_relevant=False)
        if item['type'] in ('number','boolean'):item['schema_when']={'ms_edition':EDITION}
        if key in constants:
            item.update(default_status='PROPOSED_CONDITIONAL',conditional_defaults=[dict(when={'ms_edition':EDITION},
                value=constants[key],source=CORE,source_revision=SOURCES[CORE])])
        # Standard boundary limits are not installed timing/voltage/address/retry defaults.
        result.append(item)
    return result
