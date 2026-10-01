"""Hand decisions for CAN XL; shared physical concepts were independently checked."""
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
can = json.loads((folder/'can-review-decisions.json').read_text(encoding='utf-8'))
native = {key:value for key,value in can['native'].items() if key in {
    'queue_policy','can_ack_receiver_count','can_termination_ohms','can_bus_length_m','can_stub_length_m'}}
native.update({
 'arbitration_bitrate':'Actual nominal arbitration bit rate positive numeric <=1M for declared high-speed CAN baseline. No universal minimum mode or500k default. Distinct from CAN XL data-phase rate and transceiver capability.',
 'data_bitrate':'Actual XL data-phase positive numeric rate unknown. Historical10M removed.20M is the explicitly selected Bosch X_CAN3.9 capability, not a generic ceiling; CiA describes20M and beyond with suitable physical design.',
 'payload_bytes':'Actual XL Data field1..2048 bytes, every byte length possible. Encoded DLC is length minus one. No CAN FD padding table, no default full2048-byte message or automatic optional fragmentation.',
 'can_controller_profile':'Actual controller DEVICE_SPECIFIC or X_CAN_3_9 unknown. Bosch manual3.9 Feb2024 implements CiA610-1 and CC/FD ISO2015; field limits do not certify finalISO2024 hardware conformance or imply actual installed controller.',
 'can_clock_hz':'Actual dedicated CAN controller clockHz unknown. Not CPU clock or default160MHz. Known clock/prescaler/segments must reproduce both configured phases; SoC limits require actual datasheet.',
 'can_prescaler':'Actual nominal functional prescaler positive integer unknown. X_CAN3.9 BRP raw0..31 maps1..32 and is shared by all three hardware configurations; not M_CAN nominal1..512.',
 'can_tseg1_tq':'Actual nominal functional Prop_Seg+Phase_Seg1 unknown. Explicit X_CAN3.9 NTSEG1 raw1..511 maps2..512; generic controller limits remain unknown.',
 'can_tseg2_tq':'Actual nominal functional Phase_Seg2 unknown. X_CAN3.9 raw1..127 maps2..128. Complete actual timing tuple required; not controller reset values.',
 'can_sjw_tq':'Actual nominal synchronization jump unknown positive <=both actual segments. X_CAN3.9 raw0..127 maps1..128. No installed oscillator or propagation tolerance proof.',
 'sample_point_percent':'Actual nominal sample point strictly0..100 percent unknown. Equals100*(1+TSEG1)/(1+TSEG1+TSEG2) when actual segments known; historical80% is not universal.',
 'can_xl_revision':'Registered XL wire baseline ISO11898-1:2024 proposed. Named earlier controller manual supplies only explicit register constraints, not finalISO conformance certification.',
 'can_xl_priority_id':'Actual11-bit uniquely assigned arbitration priority0..2047 unknown. Separate from32-bit acceptance/address field; identical priorities of competing transmitters need collision review.',
 'can_xl_acceptance_field':'Actual32-bit acceptance/address/content field0..4294967295 unknown. Does not determine wire priority; semantics depend on explicit upper-layer service/SDT.',
 'can_xl_sdt':'Actual8-bit service data unit type0..255 unknown. CiA611-1 assigns higher-layer meanings. No invented defaultcode, Ethernet tunneling or CANopen identification from industry alone.',
 'can_xl_vcid':'Actual8-bit logical network ID0..255 unknown, allowing256 virtual networks. Does not split physical bandwidth or provide isolation/capacity proof.',
 'can_xl_dlc':'Actual encoded11-bit XL DLC0..2047 unknown, exact Data field lengthDLC+1 (PEAKPCANBasic.NET5.1 official table). CAN FD code9=12 does not apply: XL code9=10.',
 'can_xl_rrs':'Actual Remote Request Substitution bit unknown boolean. CAN XL uses data frames, not CC remote payload. X_CAN arbitration scan includesRRS after priority ID; no automaticdefault.',
 'can_xl_sec':'Actual Simple Extended Content bit unknown boolean. Optional CANsec/fragmentation upper-layer extensions require their own revision/encoding; no implicit implementation or confirmedsecurity.',
 'can_xl_pcrc_bits':'Fixed13-bit preface CRC sequence, baseline proposal13. Protects control/DLC; does not include all CRC field overhead or implement bit-exactencoding.',
 'can_xl_fcrc_bits':'Fixed32-bit frame CRC sequence baseline proposal32, cascaded withPCRC and protects whole frame. Not CAN FD17/21 or EthernetFCS substitution.',
 'can_xl_phy':'Actual HS/SIC/SIC_XL transceiver family unknown. CAN XL supports several families; high-rate capability requires actual transceiver/topology. No default automotive industry or20M on every PHY.',
 'can_xl_mode_switching':'Actual optional SIC XL transceiver mode switch unknown. Requires connected SIC_XL family when knowntrue; arbitration/dataTX/dataRX modes need explicit actual compatibility.',
 'can_xl_transceiver_max_bps':'Actual selected transceiver/topology data capability unknown positive integer bit/s. Constrains configureddata phase; no universal2M/8M/20M value or certification.',
 'can_xl_data_prescaler':'Actual XL data functional prescaler unknown. ExplicitX_CAN3.9 shares nominalBRP1..32; othercontrollers need independent actual limits.',
 'can_xl_data_tseg1_tq':'Actual XL data Prop_Seg+Phase_Seg1 unknown. X_CAN3.9 XTSEG1 raw0..255 maps1..256, not M_CANFD1..32 and not nominal2..512.',
 'can_xl_data_tseg2_tq':'Actual XL data Phase_Seg2 unknown. ExplicitX_CAN3.9 raw1..127 maps2..128. Independentdata clock tuplechecked againstdata rate.',
 'can_xl_data_sjw_tq':'Actual XL data sync jump unknown positive <=dataTSEG1/TSEG2. ExplicitX_CAN3.9 raw0..127 maps1..128.',
 'can_xl_data_sample_point_percent':'Actual XL data sample point strictly0..100 percent unknown. Completeactualdata segments must matchformula. No nominalsamplepoint copy.',
 'can_xl_xtdco_clocks':'Actual explicitX_CAN3.9 XL secondary sample offset raw0..255 clockperiods unknown. Addedto measuredCAN_TX/RX delay, not ordinarysamplepercentage or M_CAN7-bitTDCO.',
 'can_xl_tdc_enabled':'Actual transmitter delay compensation unknown boolean. No assumed false or universalenable default; actual delay measurement/topology required.',
 'can_xl_pwm_short_clocks':'Actual explicitX_CAN PWM short phase functional1..64 clocks unknown fromraw0..63+1. Symbolduration includesboth shortandlong.',
 'can_xl_pwm_long_clocks':'Actual explicitX_CAN PWM long phase functional1..64 clocks unknown. Notdata bit period; actualPMAduty constraints need selectedtransceiver source.',
 'can_xl_pwm_offset_clocks':'Actual explicitX_CAN rawPWMO0..63 clocks unknown, strictlyless than sumfunctionalshort+long whenPWMactive. Rawoffsetis notincremented unlikephase counters.',
 'can_xl_error_signalling_disabled':'Actual optionalX_CAN errorflagdisable unknownboolean. WhenenabledonlyXL transmitted,CC/FD arbitrationformatdifferences becomeformerrors anderrorcounters stopincrementing. No copiedCC healthy-state default or provenmixed compatibility.'
})
removed = {**can['removed'],
 'bitrate':'Single CAN-like bitrate removed. XL requires separate explicit nominal and data phase rates, neither has universal default.',
 'retransmission_enabled':'Generic host retry switch removed. Actual XL error-signalling and controller state require explicit hardware behavior; no probability or finite retransmission bound implied.'}
spec = {'technology':'can_xl','native':native,'removed':removed,
 'sources':['https://www.can-cia.org/can-knowledge/can-xl',
            'https://www.can-cia.org/can-knowledge/cia-610-series-can-xl-specification-and-test-plans',
            'https://www.bosch-semiconductors.com/media/ip_modules/pdf_2/x_can/xcan_user_manual_v390.pdf',
            'https://www.bosch-semiconductors.com/products/ip-modules/can-ip-modules/can-xl.html',
            'https://www.peak-system.com/documentation/API/PCAN-Basic.Net/html/3ac7b0e3-f9df-c30e-d4fe-bcb63e5295bb.htm',*can['sources']],
 'revisions':['ISO11898-1:2024 /11898-2:2024 status fromBosch/CiA accessed2026-10-01',
              'BoschX_CAN UserManual3.9 2024-02-28 sections1.4.5.6 /1.5.4.2.4 /1.6.4',
              'CiA610-1/610-3 2023 versionswithdrawn (supersededbyISO); notclaimedcurrentnormativebaseline',
              'PEAKPCAN-Basic.NET5.1 official DLC/length table accessed2026-10-01'],
 'scope':'EachregisteredCANXL parameter, two rates, addressing/priority/DLC/CRC and explicitly named X_CAN timing/PWM limits, type/range/dependency tests and isolatedSQL preservation. No CAN FD rules or industryfallback.',
 'validation':{'isolated_sql':True,'suite':'full_parameter_audit + standard_defaults + profile_semantics + capacity_can_schedule + parameter_review + required_parameters','passed':0},
 'not_certified':['ExecutableCANXL capacity/frame/schedule model remainsMODEL_MISSING',
                  'FinalISO2024 hardware conformance ofearlierX_CAN3.9 manual',
                  'Actualinstalledclock/transceiver/topology/PWM/TDC/ACK andmixedCC/FD/XL compatibility',
                  'Bit-exactPCRC/FCRC/encoding/faultconfinement orfiniteerror-inclusivebound',
                  'CANsec/LLCfragmentation/SDTupper-layerconfiguration andactualaddresses']}
(folder/'can_xl-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
