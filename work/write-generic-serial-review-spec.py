import json
from pathlib import Path
SOURCE='https://ww1.microchip.com/downloads/en/Appnotes/TB3216-Getting-Started-with-USART-90003216B.pdf'
REVISION='Microchip TB3216 DS90003216B 2019 sections2/3/6; Arduino official Serial.begin reference master read2026-10-01; AVR USART frame-format documentation7.1.1 section15.5'
declarations=[
 ('gs_mode','select',None,['ASYNC_UART','SYNC_SERIAL','USB_CDC','CUSTOM_STREAM'],None,None,'Actual serial mechanism, unknown. A stream/COM-port name alone selects neither UART nor synchronous clocks nor native USB CDC.'),
 ('gs_transport_binding','text',None,None,None,None,'Required actual registered serial/USB/PHY port and direction topology reference; no silent RS232/RS485/SPI binding.'),
 ('gs_implementation_source','text',None,None,None,None,'Required device/firmware/clock/driver capabilities and revision, unknown. Generic Serial is an NIS abstraction, not a normative serial bus.'),
 ('gs_framing_source','text',None,None,None,None,'Required actual message encoding/framing/escaping/integrity and byte/character boundary source, unknown; stream chunks are not necessarily complete messages.'),
 ('gs_uart_profile','select',None,['TB3216_8N1','AVR_FRAME_FORMATS','DEVICE_SPECIFIC'],None,None,'Explicit source-qualified async UART framing profile, unknown. TB3216 tutorial supplies conditional9600/8N1 proposals, not universal baud minimum.'),
 ('gs_baud_rate','number','Bd',None,1,None,'Actual async binary UART symbol rate, unknown until matched clock/divisor/configuration;9600 is conditional tutorial proposal, not generic minimum.'),
 ('gs_peer_baud_rate','number','Bd',None,1,None,'Actual peer configured baud rate; must agree with selected UART configuration. Clock error/oversampling tolerance needs actual device proof.'),
 ('gs_data_bits','number','bit',None,1,None,'Actual data bits per UART character; reviewed AVR5..9, tutorial8. Not application octets or USB packet size.'),
 ('gs_parity','select',None,['NONE','EVEN','ODD','MARK','SPACE','DEVICE_SPECIFIC'],None,None,'Actual UART parity; reviewed AVR NONE/EVEN/ODD only, tutorial NONE. Other devices require their own source.'),
 ('gs_start_bits','number','bit',None,1,None,'Actual UART start bits; reviewed AVR/tutorial1. Unknown device-specific layouts are not verified using AVR limits.'),
 ('gs_stop_bits','number','bit',None,0.5,None,'Actual UART stop-bit periods; reviewed AVR1 or2, tutorial1. Fractional stop periods are device-dependent.'),
 ('gs_char_bits','number','bit',None,1,None,'Actual start+data+parity+stop bit-periods per character. Tutorial8N1=10, AVR parity adds1. Not8 useful bits.'),
 ('gs_encoded_characters','number','character',None,1,None,'Actual serialized character count including framing/encoding/escaping/flow characters as applicable, unknown; not blindly equal to application payload octets.'),
 ('gs_wire_bits','number','bit',None,1,None,'Actual UART occupied bit-period count = encoded characters times character bits; start/stop/parity included.'),
 ('gs_serialization_us','number','us',None,0,None,'Actual UART serialization time = wire bit periods / binary UART baud times1e6, excluding actual gaps/flow stalls.'),
 ('gs_gap_bound_us','number','us',None,0,None,'Actual aggregate character/message/turnaround idle bound, unknown; zero only when explicitly justified.'),
 ('gs_flow_control','select',None,['NONE','RTS_CTS','XON_XOFF','DEVICE_SPECIFIC'],None,None,'Actual UART flow control and peer support, unknown. No automatic disabled flow-control assumption.'),
 ('gs_flow_bound_us','number','us',None,0,None,'Actual bounded UART flow-control blocking from both endpoints, unknown. Unbounded peer stalls do not prove capacity.'),
 ('gs_wire_bound_us','number','us',None,0,None,'Actual complete UART transfer bound at least serialization+aggregate idle+flow stalls, unknown; driver/application processing remains separate.'),
 ('gs_clock_hz','number','Hz',None,1,None,'Actual synchronous serial clock, unknown. Encoding/bits per clock/edge/role/word lengths supplied by actual bound port; never UART baud or USB speed.'),
 ('gs_cdc_line_coding_role','select',None,['NATIVE_ADVISORY','BRIDGE_UART','DEVICE_SPECIFIC'],None,None,'Actual CDC implementation interpretation of line coding, unknown. Arduino native CDC ignores Serial.begin baud for wire speed; USB-to-UART bridges require separate real UART binding.'),
 ('gs_framing','select',None,['NONE','FIXED_LENGTH','LENGTH_PREFIX','DELIMITER','DEVICE_SPECIFIC'],None,None,'Actual application message framing, unknown; optional line delimiters in TB3216 example are not mandatory for all serial streams.'),
 ('gs_message_bytes','number','Byte',None,0,None,'Actual application-message octets, unknown. Not API read/write chunk, UART characters, USB packets or encoded wire count.'),
 ('gs_max_message_bytes','number','Byte',None,1,None,'Actual implementation/application-message limit, unknown.65535 is not a generic serial standard maximum.'),
]
removed={
 'queue_size':'No universal256 serial queue; actual driver/controller buffers and scheduling are transport-specific.',
 'queue_policy':'No universal FIFO transport guarantee; actual serial driver/port scheduling is required.',
 'qos_priority':'No intrinsic generic serial priority3 or eight universal classes.',
 'reserved_bandwidth_percent':'No universal serial reservation0; actual port scheduling supplies capacity.',
 'sync_method':'UART bit framing is not universal NTP/PTP/network synchronization.',
 'retransmission_enabled':'No automatic serial retryfalse; actual application/error protocol decides.',
 'retransmission_rate':'No universal zero retry probability.',
 'retry_limit':'No universal serial retry limit0.',
 'retransmission_delay_ms':'No universal retry delay0ms.',
 'gateway_maximum_throughput':'No universal100M serial gateway throughput.',
 'gateway_input_buffer':'No universal256 serial gateway input buffer.',
 'gateway_output_buffer':'No universal256 serial gateway output buffer.',
 'gateway_maximum_routes':'No universal10000 serial gateway routes.',
 'gateway_maximum_messages_s':'No universal100000 serial gateway messages/s.',
}
native={key:meaning for key,_,_,_,_,_,meaning in declarations}
native['payload_bytes']='Actual application or API stream-chunk octets, explicitly qualified by framing source. No8 default or universal65535 ceiling; full message and serialized UART characters remain separate.'
spec={'technology':'generic_serial','native':native,'removed':removed,
 'sources':[SOURCE,'https://onlinedocs.microchip.com/oxy/GUID-173AD72D-41FE-4760-A93C-7078A02BD908-en-US-7.1.1/GUID-585072A2-2328-4EDD-B24F-E2E7672632B5.html','https://github.com/arduino/reference-en/blob/master/Language/Functions/Communication/Serial/begin.adoc'],
 'revisions':[REVISION,'NIS explicit generic serial binding policy; no universal serial bus default'],
 'scope':'Every original generic serial field reviewed individually. Explicit async UART/synchronous/native CDC/custom stream binding; conditional TB3216 tutorial9600/8N1 proposals and AVR framing, actual character serialization/gaps/flow bounds separate from API chunks and application messages.',
 'validation':{'isolated_sql':True,'suite':'full_parameter_audit + standard_defaults + profile_semantics + capacity_can_schedule + parameter_review + required_parameters + physical_profiles','passed':0},
 'not_certified':['Actual registered transport lookup/execution/PHY/clock-divisor/tolerance/peer flow-control bounds and encoded application framing; source references alone do not prove device timing',
 'USB CDC class descriptors and transfers, synchronous/custom/device-specific implementations; no borrowed UART or CAN model, MODEL_MISSING remains',
 'Full capacity/schedule and functional timing acceptance, actual field measurement, all device-specific serial conformance']}
(Path(__file__).parent/'generic-serial-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
