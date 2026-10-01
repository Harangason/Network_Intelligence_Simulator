"""Record independently researched ISO CAN FD decisions and explicit shared CAN physical rules."""
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
can = json.loads((folder / 'can-review-decisions.json').read_text(encoding='utf-8'))
native = {key:value for key,value in can['native'].items() if key not in {'bitrate','can_dlc','can_phy'}}
native.update({
    'arbitration_bitrate':'Actual nominal CAN FD rate unknown, positive numeric bit/s <=1M. No universal500k default; topology/controller/PHY sampling determines installed rate. Shared CAN nominal clock/prescaler/segments are checked against this phase, not against data rate.',
    'data_bitrate':'Actual configured data-phase rate unknown, positive numeric bit/s. No universal2M default or generic8M hardware ceiling. Actual transceiver ceiling constrains it; explicit M_CAN requires >=nominal. Required for known BRS true or unresolved BRS; known false uses nominal timing and needs no second rate.',
    'payload_bytes':'Actual logical message payload0..64 bytes unknown. Wire Data field may be padded according to DLC; actual known wire length must cover logical bytes. Nine logical bytes require at least12 wire bytes. Larger actual DLC must be counted, never silently reduced to logical length.',
    'can_frame_type':'CAN FD has DATA only, no remote-request frame. CC compatibility requires a separately identified classic frame and its own DLC/CRC/timing rules.',
    'can_fd_revision':'ISO11898-1:2015/2024 FD baseline proposed. Non-ISO pre-standard CRC/stuffing differs and is not silently accepted or simulated by this registered profile.',
    'can_fd_brs':'BRS false baseline proposal uses nominal bit timing throughout frame; true switches at BRS sample point and back at CRC delimiter. Actual frame bit unknown until user/device review. Unknown BRS uses slower whole-frame rate for conservative estimates, never silently enables fast data phase.',
    'can_fd_dlc':'Actual integer encoded DLC0..15 unknown. Maps to wire bytes0..8,12,16,20,24,32,48,64. This code differs from logical payload and classic DLC; known mismatching code/wire length is rejected.',
    'can_fd_wire_data_bytes':'Actual complete CAN FD Data field including padding unknown, restricted to DLC lengths0..8/12/16/20/24/32/48/64. Registry/capacity/frame/schedule consumers use actual declared padding; no full64-byte default.',
    'can_fd_error_passive':'Actual ESI indicator unknown boolean; false error-active and true error-passive. Known controller state and ESI must agree. Static check does not implement fault-confinement transitions or establish healthy bus.',
    'can_fd_crc_bits':'ISO CRC sequence17 bits for actual wire data<=16 bytes,21 for>16. Unknown until actual wire length known. Not CRC field total length: SBC/parity/fixed stuffing add bits. Conservative frame budget reserves these without claiming bit-exact CRC execution.',
    'can_fd_transceiver_max_bps':'Actual selected transceiver data-phase limit unknown, positive numeric integer configuration. CiA states limit depends on transceiver characteristics; no universal8M or CAN XL20M bound imported. Actual topology/sample-point/loop-delay evidence remains required.',
    'can_fd_data_prescaler':'Actual functional data prescaler unknown, not raw zero-based register. Explicit M_CAN3.3.1 allows1..32; with TDC enabled only1..2. Other controller families need their own profile and limits.',
    'can_fd_data_tseg1_tq':'Actual functional data Prop_Seg+Phase_Seg1 unknown. M_CAN3.3.1 allows1..32. Distinct from nominal TSEG1 and its2..256 M_CAN limit. Complete tuple verifies data rate and sample point.',
    'can_fd_data_tseg2_tq':'Actual functional data Phase_Seg2 unknown. Explicit M_CAN3.3.1 allows2..16; not nominal2..128. Unknown other controller limits are not manufactured.',
    'can_fd_data_sjw_tq':'Actual functional data resynchronization jump unknown, positive <=actual dataTSEG1/TSEG2. Explicit M_CAN3.3.1 <=16, separate from nominalSJW<=128.',
    'can_fd_data_sample_point_percent':'Actual data sample point unknown, strictly0..100 percent; known segments require100*(1+dataTSEG1)/(1+dataTSEG1+dataTSEG2). No universal80% default or nominal87.5% copied to data phase.',
    'can_fd_tdc_enabled':'Actual transmitter delay compensation state unknown; no generic checkbox false confirmation. M_CAN hardware constraint/data prescaler limits apply only with explicit controller and known enabled condition.',
    'can_fd_mcan_delay_mtq':'Actual M_CAN measured transmit-to-receive delay unknown in minimum clock quanta,0..127 representable. Hardware continually measures delay for FD with TDC; this is not a universal static delay default.',
    'can_fd_mcan_tdco_mtq':'Actual explicit M_CAN offset unknown,0..127 minimum clock quanta. Adds to measured delay for secondary sample position; not ordinary data sampling percentage.',
    'can_fd_mcan_tdcf_mtq':'Actual M_CAN filter window unknown,0..127mtq. Feature effective when TDCF>TDCO; smaller configured value may validly disable filter and is not forced to an invented relation.',
    'can_fd_mcan_ssp_mtq':'Actual M_CAN secondary sample position unknown, equals measured delay+TDCO when all supplied. <=127mtq and with TDC enabled strictly less than6 data bit times. Saturation is not accepted as proof that intended sample position remains within hardware bound.'
})
spec = {'technology':'can_fd','native':native,'removed':can['removed'],
    'sources':['https://www.can-cia.org/can-knowledge/can-fd-the-basic-idea',
               'https://www.can-cia.org/can-knowledge/physical-layer-options',
               'https://www.bosch-semiconductors.com/products/ip-modules/can-protocols/can-fd/',
               'https://www.bosch-semiconductors.com/media/ip_modules/pdf_2/m_can/mcan_users_manual_v331.pdf',
               'https://www.bosch-semiconductors.com/media/ip_modules/pdf_2/papers/icc_2015_mutter_1.pdf',
               'https://www.bosch-semiconductors.com/media/ip_modules/pdf_2/papers/icc14_2013_paper_hartwich_1.pdf',*can['sources']],
    'revisions':['CiA CAN FD/PMA knowledge accessed2026-10-01, ISO11898-1:2015/2024 distinction and BRS semantics',
                 'Bosch M_CAN3.3.1 2023-03-11 sections2.3.4/2.3.8/2.3.15/3.1.4/Table54',
                 'Bosch Mutter iCC2015 Advantages of CAN FD error detection mechanisms',
                 'Bosch Hartwich iCC2013 Bit Time Requirements for CAN FD',*can['revisions']],
    'scope':'Every registered ISO CAN FD form field, DLC/body/wire/CRC/ESI, independent nominal/data controller timing and optional BRS. Conservative successful-frame phase envelope, DLC padding and registered timing/load consumers plus SQL persistence. Type/default/constraint verification is distinct from actual hardware, bit-exact protocol execution and capacity assurance.',
    'validation':{'isolated_sql':True,'suite':'full_parameter_audit + standard_defaults + profile_semantics + capacity_can_schedule + parameter_review + required_parameters','passed':0},
    'not_certified':['Actual transceiver/topology/clock/oscillator/ACK/controller state',
        'Bit-exact ISO CRC/SBC/dynamic and fixed stuffing encoding',
        'Non-ISO CAN FD, CAN FD light, CAN XL or industry-specific higher layers',
        'Actual TDC measurement or fault-inclusive finite retransmission schedule',
        'Installed mixed CC/FD compatibility and complete functional E2E acceptance']}
(folder / 'can_fd-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
