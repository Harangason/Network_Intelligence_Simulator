import json
from pathlib import Path
SOURCE='https://www.can-cia.org/can-knowledge/can-data-link-layer-generations'
REVISION='CiA primary CAN generation, CAN FD and CAN XL descriptions read2026-10-01; ISO11898-1:2024 referenced, full licensed text not read'
declarations=[
 ('gcan_family','select',None,['CAN_CC','CAN_FD','CAN_XL'],None,None,'Actual transmitted frame family, unknown. A CAN FD/XL-capable controller may send CC frames, so controller capability does not select this family.'),
 ('gcan_transport_binding','text',None,None,None,None,'Required actual registered can/can_fd/can_xl link/controller/PHY/bit-timing configuration reference, unknown. Generic wrapper has no independent physical rate.'),
 ('gcan_implementation_source','text',None,None,None,None,'Required actual encoding/edition/controller/device capability reference, unknown. Generic CAN is an NIS abstraction, not a fourth normative CAN generation.'),
 ('gcan_schedule_source','text',None,None,None,None,'Required actual identifier ownership/traffic/interference/error/queue schedule reference, unknown. Family shape does not prove arbitration response time.'),
 ('gcan_frame_format','select',None,['STANDARD','EXTENDED','XL'],None,None,'Actual CC/FD11-bit or29-bit frame format, or XL separated priority/acceptance format. No inferred standard format.'),
 ('gcan_frame_kind','select',None,['DATA','REMOTE'],None,None,'Actual DATA/REMOTE frame. Only CC supports remote requests; remote wire data is empty even when requested data length is nonzero.'),
 ('gcan_identifier','number',None,None,0,536870911,'Actual CC/FD arbitration identifier, unknown. Standard11-bit ceiling2047, extended29-bit ceiling536870911. Not XL acceptance or priority field.'),
 ('gcan_priority_id','number',None,None,0,2047,'Actual XL11-bit priority ID, unknown. Not a CAN CC/FD application identifier or generic QoS priority3.'),
 ('gcan_acceptance_field','number',None,None,0,4294967295,'Actual XL32-bit acceptance field, unknown, separate from arbitration priority.'),
 ('gcan_requested_bytes','number','Byte',None,0,8,'Actual CC remote requested length0..8, unknown; not transmitted remote payload or FD/XL data length.'),
]
removed={
 'bitrate':'Remove unsourced500k proposal; wrapper requires actual explicit registered CAN family transport/PHY/bit timing, no separate fixed generic rate.',
 'qos_priority':'Identifier arbitration/XL priority differs from generic priority3.',
 'reserved_bandwidth_percent':'Actual interference/traffic/arbitration instead of universal reservation0.',
 'sync_method':'Actual upper-layer/device synchronization differs from universal NONE/PTP/NTP.',
 'retransmission_enabled':'Actual CAN controller retry/error behavior is not a generic switchfalse.',
 'retransmission_rate':'No universal retry probability0.','retry_limit':'No universal bounded CAN retries0.',
 'retransmission_delay_ms':'No universal retry delay0ms.',
 'gateway_maximum_throughput':'No universal100M generic CAN gateway throughput.',
 'gateway_input_buffer':'No universal256 gateway buffer.','gateway_output_buffer':'No universal256 gateway buffer.',
 'gateway_maximum_routes':'No universal10000 route capacity.','gateway_maximum_messages_s':'No universal100000 CAN messages/s.',
 'queue_policy':'Actual controller queues/identifier arbitration require matched transport, not generic FIFO certification.',
 'queue_size':'No universal256 CAN transmit queue.'}
native={k:meaning for k,_,_,_,_,_,meaning in declarations}
native['payload_bytes']='Actual on-wire data-field octets. CC0..8, FD discrete0..8/12/16/20/24/32/48/64, XL1..2048. CC REMOTE has0 wire data. Application encoding/padding and selected lower link remain actual configuration, no8 proposal.'
spec={'technology':'generic_can','native':native,'removed':removed,
 'sources':[SOURCE,'https://www.can-cia.org/can-knowledge/can-fd-the-basic-idea','https://www.can-cia.org/can-knowledge/can-xl'],
 'revisions':[REVISION,'NIS abstraction/policy: transport family reference, not independent generic CAN normative standard'],
 'scope':'Every original generic CAN parameter reviewed individually. Unsourced500k/8-byte defaults removed; explicit family/link/implementation/schedule required, CC/FD/XL actual wire payload and address format scoped independently.',
 'validation':{'isolated_sql':True,'suite':'full_parameter_audit + standard_defaults + profile_semantics + capacity_can_schedule + parameter_review + required_parameters + physical_profiles','passed':0},
 'not_certified':['Actual binding lookup/execution against registered can/can_fd/can_xl port/PHY/rates/clock/error/PMA/encoding/device profile; references alone do not resolve hardware',
 'Complete encoded DLC/CRC/stuffing/padding/error/interference/queue/arbitration response and application acceptance; generic wrapper has no own executable capacity model, MODEL_MISSING remains',
 'Full ISO11898 and controller conformance; CC/FD/XL registered profiles remain separately reviewed, no transport default is invented for the generic wrapper']}
(Path(__file__).parent/'generic-can-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
