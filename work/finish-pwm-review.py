from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
root=Path.cwd();sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import pwm as n
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/pwm-tests.xml'
for path in('backend/communication/technologies/pwm.py','backend/tests/test_pwm_parameter_review.py','backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
 assert xml.stat().st_mtime_ns>=(root/path).stat().st_mtime_ns,('stale',path)
p=ET.parse(xml);s=p.findall('.//testsuite');assert s and all(int(v.get(k,'0'))==0 for v in s for k in('failures','errors','skipped'))
cases=p.findall('.//testcase');native=sum(c.get('classname','').endswith('test_pwm_parameter_review')for c in cases)
assert native>=len(registry.parameter_fields('pwm'))+10 and len({c.get('classname')for c in cases})==10
primary=root/'work/pwm-primary';reviewed=[]
scopes={'linux618-doc':'Actual6.18 overview: arguments/requestedstate/disabledlevel/atomic apply/capture, not blanketimpossibilityofhardwaregetter.',
 'linux618-header':'Actualv6.18state/waveform/capturetypes, args, pwm_init_state0/False, hardwaregetter/channel/drivercapabilities.',
 'linux618-core':'Actualv6.18pwm_wf_valid/state_valid/rounding/wf-stateconversion/standardDTtranslator; disabledstateignoresotherstatevalues while disabledwaveform requiresduty0/offset0.',
 'linux618-dt':'Actualv6.18standardflag bit0inverted; notuniversalhardwarepolarity.'}
for entry in json.loads((primary/'manifest.json').read_text()):
 assert hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()==entry['sha256']
 reviewed.append({**entry,'read_scope':scopes[Path(entry['path']).stem]})
reviewed.append(dict(url=n.ST,kind='PRIMARY_BROWSER_PDF_READ',read_scope='Public original AN4013 Rev14 February2026 48pages read through browser: printed10-17/19/24/32-34. LocalHTTPdownload timedout; no invented originalhash. No fulldevice/reference-manualcertification.'))
(primary/'reviewed-manifest.json').write_text(json.dumps(reviewed,indent=2)+'\n')
before={v['key']for v in next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='pwm')['form_parameters']};after={v['key']for v in registry.parameter_fields('pwm')}
meanings={v['key']:v['description']for v in n.DECLARATIONS};meanings['payload_bytes']='Applicationcodec metadata only; directPWM defines no1byteframe/bitrate/CRC/packetqueue. Actualperiod/duty/polarity/value mapping requiresdevice/peripheral/consumer sources.'
spec=dict(technology='pwm',native=meanings,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES),revisions=list(n.SOURCES.values()),
 scope=['Everydeclared nativeparameter meaning/type/unit/bound/dependency/source/default individuallycheckedagainstpinnedLinux6.18andpublicSTM32AN4013Rev14source. Actualdevicecapabilities/clock/wiring/consumerconstraints unknownwithouttheirsource.',
 'DirectPWM carrierfrequency notbitrate, activefraction notalwaysHIGHfraction; normal/inversed Linuxpolarity separateSTMOC1/2 andpinpolarity. No universalservo50Hz/3.3V/queue/byteframe proposal.',
 'Linuxstate UInt64nanoseconds enabledperiod>0/duty<=period; disabledstateignoresotherfields anddoesnotguaranteeinactiveoutput. Separatewaveform S64_MAXperiod, duty<=period andoffset0orstrict<period; wrappedactivewindowvalid.',
 'Platforminitduty0/usage_powerFalse conditionalonlyexplicitLinuxinitialization; standardDT0/1flagqualifiednotallhardware. Actualchannel<npwm/exclusiveconsumer andatomicchipcapabilityrequired.',
 'Requestedsoftwarestate nothardware/capture evidence; exact integer-ns request doesnotcertifyfractionalsub-nserrorzero. Actualimplementedwaveformbounds/latch/source/capability/freshness requiredforfunctionalacceptance.',
 'STMregularTIM16/32bit actualregisterlimits,PSC+1/RCR+1dividers; fullperiodARR+1edge/2ARRcenter separateupdateeventbothoverflowandunderflow. RCRdividesUEV notPWMcycle; PSC/RCR0 stillvaliddivide1.',
 'Capturedperiod/activepair andcounterclock deriveactualfrequency/duty; LinuxcaptureUInt32ns andtimeoutms notUInt64state. Advanced/complementary/break needactualdevice capability/registeredlayout; preloadedsettings needobservedUEVlatch.',
 'ElectricalHIGH/LOW againstactualreceiver thresholds, correlatedwaveform/exclusiveowner/value mapping/age/update requirements separatevalidconfiguration. DisableLOW notsafe-statecertificate; breakprecludesnormalacceptance. Confirmed500Hz/35%inverseexample preserved.',
 f'{len(cases)} isolated tests PASS, {native} native andnine shared suites. DirectPWMpacketcapacityNOT_APPLICABLEdoesnotcertifyphysicalexecution.'],
 validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} PWM native andnine shared suites',complete_release_gate='NOT_RUN'),
 not_certified=['Actualdriver/peripheralPWMexecutor, voltage/load/safe-state/hardwaretiming and fullconsumerE2Eacceptance remainactualevidence/runtimework; directpacketcapacityNOT_APPLICABLE isnotanexecutioncertificate.',
 'Remainingprofiles/cumulativeconsumerconsistency/README/releasegate/exacttestedimageproduction remainpending.'])
(root/'work/pwm-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n');print(dict(tests=len(cases),native=native,fields=len(meanings),removed=len(before-after)))
