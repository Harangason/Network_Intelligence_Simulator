import json,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from backend.communication.technologies import tcp as R
spec=dict(technology='tcp',source_manifest='work/tcp-primary/manifest.json',source_read_scopes={
 R.BASE:'Original RFC9293 August2022 HTML, selected sections2 and3.1-3.8: header/options/pseudoheader/checksum, byte sequence, MSS, flowcontrol, state and base timer behavior. No full operating-system stack certification.',
 R.WS:'Original RFC7323 September2014 cached HTML, sections2-5: both SYN offers, SYN unscaled, shift14 receiver clamp, timestamp negotiation/clock recycle and 24day PAWS reset.',
 R.RTO:'Original RFC6298 June2011 HTML sections2-5: initial/floor SHOULD, first/subsequent RTT with oldSRTT, Karn, optional cap≥60s, backoff.',
 R.RENO:'Original RFC5681 September2009 HTML sections2-4: cwnd/rwnd/flight distinctions, SMSS IW2/3/4 exact boundaries, timeout and selected slowstart/avoidance increments.',
 R.CUBIC:'Original28-page RFC9438 August2023 PDF, selected sections3/4/5.1; printed9 visually read equations Wcubic and signed K, sourceunit SMSS-segments, target nextRTT clamp and recommended C=.4/beta=.7.',
 R.IW10:'Original RFC6928 April2013 HTML sections1/2; explicit EXPERIMENTAL IW10 upperbound; experiment EthernetMTU1500 never a transport default.'},additional_field_meanings={'payload_bytes':'Actual application stream bytes with separate segment MSS, IP reassembly limits and application framing. No65535byte application cap or clock inferred from TCP.'},scope=[
 'Every exported TCP field individually reviewed, own industryneutral explicit IP path. Foreign CAN/Ethernet timing/MTU/bitrate fields removed; parameter evidence EXPLICIT_LAYER and native scope avoids silently qualifying actual lower layers.',
 'Typed segment header/options/pseudoheader/checksum and modulo sequence relations; absent MSS fallback depends IPv4/IPv6, effective sendbudget accounts actual peer and IP options. WS/TS require negotiation; SYN windows unscaled, received shifts clamp14, timestamps monotonic notUTC.',
 'Actual RTT samples, oldSRTT-before-RTTVAR update, Karn timestamp condition, sourcebaseline1second floor, optional actual cap, initial and timeout rules. Nagle/keepalive configurable; one lost probe not connection death. No guessed LAN granularity or two-minute actual path bound.',
 'Reno and optional IW10 separate; flight vs cwnd vs rwnd. CUBIC own segment units, signed epoch-root relation and cubic/nextRTT target clamping; no Reno growth rule applied to CUBIC.',
 'Sourceconditional header/RTO/weights/MSS/keepalive/Nagle/CUBIC proposals do not confirm actual sockets, addresses, negotiated windows, sample clocks or capacity. Complete source+transport+consumer functional timing and consuming freshness remain independently required.'
 ],not_certified=['No full TCP OS/wire state-machine, all registered congestion/ECN/SACK extensions or IP/PHY/congestion/loss bound certified. Optional relations require actual evidence; runtime MODEL_MISSING and parameter validity does not prove delivery, application message framing, capacity or consumer acceptance.','Remaining individual/global reviews, cumulative release gate and production delivery pending.'])
Path('work/tcp-finish-spec.json').write_text(json.dumps(spec,indent=2)+'\n')
