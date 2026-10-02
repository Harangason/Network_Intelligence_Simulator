"""Record 1553 review only after fresh isolated test evidence exists."""
import hashlib,json,sys
from pathlib import Path
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import mil_std_1553 as m
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001'
xml=folder/'individual/mil_std_1553-tests.xml'
for relative in ('backend/communication/technologies/mil_std_1553.py','backend/communication/technologies/catalog.py',
                 'backend/tests/test_technology_full_parameter_audit.py'):
    assert xml.stat().st_mtime_ns >= (root/relative).stat().st_mtime_ns,('stale receipt',relative)
suites=ET.parse(xml).findall('.//testsuite')
assert suites and all(int(v.get(k,'0'))==0 for v in suites for k in ('failures','errors','skipped'))
count=sum(int(v.get('tests','0')) for v in suites);assert count>=8991,count
manifest_path=root/'work/mil1553-primary/manifest.json'
manifest=json.loads(manifest_path.read_text())
assert manifest['sha256']==hashlib.sha256((manifest_path.parent/'MIL-STD-1553C.pdf').read_bytes()).hexdigest()
manifest.update(read_scope='PDF10-51 fully read: sections1-6 and mandatory AppendixA; TableI and Figure8 rendered and inspected. TableII numerics read, full device/EMC conformance tests not performed.',
                actual_agent_agreement_acceptance=False,individual_local_tests_completed=True)
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
original=next(v for v in json.loads((folder/'inventory-before.json').read_text()) if v['technology']=='mil_std_1553')
before={v['key']for v in original['form_parameters']};after={v['key']for v in registry.parameter_fields('mil_std_1553')}
native={v['key']:v['description']for v in m.DECLARATIONS}
native.update(bitrate='Nominal1Mbit/s for actualMIL-STD-1553C2018, distinct observed999000..1001000 and one-second100Hzstability. Conditional source-qualified proposal, never Ethernet/CAN mode fallback or commissioned confirmation.',
              payload_bytes='Actual application encoded bytes fit two octets per actual data word1..32, at most64. Mode words manage bus hardware rather than application payload; busy transmitting RT emits status only. Word sync/parity and command/status are separate.')
spec=dict(technology='mil_std_1553',native=native,removed={k:m.REMOVED[k]for k in before-after},sources=list(m.SOURCES),
    revisions=list(m.SOURCES.values()),scope=[
        'Each declared field reviewed for meaning, role/application applicability, type/unit/bounds/dependencies, source/revision, conditional standard proposal and actual evidence. Every retained NIS scenario field remains application policy rather than a1553 standard value.',
        'MIL-STD-1553C2018 primary DoD text obtained from manufacturer hosted ASSISTcopy; current edition verified against active DLA36973. PDF10-51 read including mandatory AppendixA; modeTableI and timingFigure8 visually verified; manifest hash/readscope inwork/mil1553-primary.',
        'Nominal fixed1Mbit/s standard proposal distinct observedclock+-1000Hz/shortstability100Hz and Manchestertransitions.20bit-timesword=3sync+16info+oddparity;MSBfirst/highprecisionwordfirst/unusedzerobits,commandwordcount0means32. No inheritedCAN8bytepayload,queue,priority,retry,IP QoS or gateway transport default.',
        'NormalBC_RT/RT_BC/RT_RT and broadcast forms have own1or2commands,0/1/2statuses and0/1/2responseintervals. UniqueRT0..30 vsbroadcast31, data subaddresses1..30 vsmode0/31, explicit TableI modes/directions/dataword/broadcast permissions; reserved9..15/22..31 rejected. Busy transmittingRTstatus-only distinct advertisedcount.',
        'Response4..12us,intermessagegap>=4us,no-response>=14us referenced to paritymidpoint/midsync at actualspecified terminalA, not raw idle duration. No unconditional serialization+response occupancy formula asserted across differing terminal references/propagation. Hardwaretransmitfailsafe<=800us notfunctional safety proof.',
        'OnlyoneactiveBC;normaldualstandbyoneactivebus andisolation>=45dB, alternatecommand/targetbus required forshutdown. Multiplebusandactualretry/schedule evidence separately qualified. Dynamiccontrolacceptance not randomarbitration.',
        'AppendixA.2Army/Navy/AirForce scope explicitlyselected apart fromindustry. Dualstandby/externaladdresspowerupvalidation,requiredmode/formcapabilities,AirForcenoDBC,onlymodebroadcastallowed,reset<=5ms,selftest<=100ms,RT_RT57+-3us,90percentcableshield. Army/AirForce transformeronly versusNavybothconnectors; baseC75percent anddatabroadcastremain distinct.',
        'ActualnominalZo70..85ohm@1MHz/twists>=4perft/capacitance<=30pFperft/loss<=1.5dB100ft, twoendterminationsZo+-2percent. Transformerresistor.75Zo+-2percent/fault>=1.5Zo/1.41ratio+-3percent vsdirect55+-2percent/fault110ohm.20ft/1ftstub recommendations allow qualifiedexceptions,not inventedbuslengths.',
        'TransformerBopenimpedance>3000/CMRR>45/ringing<1/droop<=20 with exact fixtures; loadedstubA1..14vs1.4..20Vpp differs terminalfixtureA18..27vs6..9Vpp at70vs35ohm. TX25nscrossing/100..300transition, RX150ns/response.86..14vs1.2..20/noresponse<=.20vs.28/impedance1000vs2000;noise/ringing/symmetry/qualifiedcommonmode separated by point/coupling/power envelope.',
        'NoiseAWGN140vs200mVrms and2.1vs3Vpp atspecified bandwidth withTableIIqualified source distinct1e-7worderror limit, not generic undetectedbit/applicationreliability probability. No electrical measurement, address, workload,source confirmation or fullMIL464proof manufactured.',
        f'{count} selected ten-file regressions passed inisolated SQL, including confirmed27/13RTaddresses,999750clock and11.5/8.75usinterval preservation after invalidbroadcastaddress edit. Complete releasegateNOT_RUN.'
    ],validation=dict(status='PASS',tests_passed=count,isolated_sql=True,complete_release_gate='NOT_RUN'),not_certified=[
        'Complete physical/EMC/noise/temperature/singlefailure conformance, terminaldevice test certification, fullwordcodec/BCscheduler/dynamiccontrol/supersession/invalidcommand/data behavior executors or redundanthandover traces.',
        'Local declared scalarVALID is not resolvedsource provenance, actualcanonical address uniqueness/BCownership, runtimecapacity, fullE2E acceptance or production. KeepMODEL_MISSINGuntilcomplete executable evidence path passes its gate.'
    ])
(root/'work/mil1553-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n')
print(json.dumps({'tests_passed':count,'native_fields':len(native),'removed':len(before-after)}))
