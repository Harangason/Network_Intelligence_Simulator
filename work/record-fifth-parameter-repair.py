"""Record the full backend freeze and the obsolete PWM positive-case repair."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'docs/implementation-workloads/technology-full-parameter-audit-20261001'
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
receipt_path=ROOT/'backend/test-output/release-gates/delivery-200756b25f6a/cc5ce4e520fe/receipt.json'
receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
assert receipt['status']=='FAIL'
check=ROOT/'work/pwm-dimensioning-consumer-check.txt'
assert '185 passed' in check.read_text(encoding='utf-8-sig')
path=FOLDER/'progress.json'
progress=json.loads(path.read_text(encoding='utf-8'))
progress['complete_release_gate']='FIFTH_GATE_PWM_LEGACY_TEST_REPAIRED_AWAITING_FULL_RERUN'
progress.setdefault('release_history',[]).append({'status':'FAIL','evidence':ref(receipt_path),
 'scope':'Complete backend: 21519 passed, 1 obsolete positive-case expectation failed, 2 skipped, 56 subtests passed; 556 frontend tests PASS. No image/deployment.',
 'cause':'Legacy PWM hardware_review_proposal expected three fields that native PWM now correctly rejects. Retained UNVERIFIED/no packet load assertions; explicit legacy-evidence negative case added.',
 'targeted_repair_evidence':ref(check)})
path.write_text(json.dumps(progress,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
path=FOLDER/'individual/pwm.json'
record=json.loads(path.read_text(encoding='utf-8'))
record['consumer_followup']['dimensioning_followup']={'decision':'PWM has no loose local hardware review proposal; actual native waveform/driver evidence remains required. Even confirmed legacy frequency/update/capture values cannot release timing.',
 'evidence':ref(check),'passed':185}
path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
path=FOLDER/'consumer-findings.md'
text=path.read_text(encoding='utf-8'); marker='\nDie Einzelprüfungen und die Quellenkorrekturen sind dokumentiert.'
assert marker in text
text=text.replace(marker,'\n- Die nächste vollständige Backend-Runde bestand 21.519 Fälle; einzig der alte gemeinsame PWM/I²C/SPI-Proposal-Test erwartete die bereits fachlich entfernten PWM-Felder. Der PWM-Fall ist jetzt getrennt und prüft ausdrücklich UNVERIFIED, keine Paketbuslast und keine Freigabe durch bestätigte lose Legacy-Frequenz-/Update-/Capture-Angaben. Die Assertions der übrigen Profile bleiben vollständig erhalten. Alle 185 betroffenen isolierten Fälle sind bestanden; neuer vollständiger Release-Lauf erforderlich.\n'+marker)
path.write_text(text,encoding='utf-8')
print(json.dumps({'status':'WAITING_FOR_COMPLETE_RELEASE_RERUN','targeted_passed':185}))
