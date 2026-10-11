"""Preserve the stopped gate and the new independent consumer repair evidence."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'docs/implementation-workloads/technology-full-parameter-audit-20261001'
def ref(path):return {'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
receipt_path=ROOT/'backend/test-output/release-gates/delivery-b15de1555200/57306d730242/receipt.json'
receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
assert receipt['status']=='FAIL' and 'image_id' not in receipt
backend=ROOT/'work/pwm-local-schema-backend.txt'
browser=ROOT/'work/pwm-local-schema-browser.txt'
coverage=ROOT/'work/parameter-review-coverage.json'
assert '168 passed' in backend.read_text(encoding='utf-8-sig')
assert '1 passed' in browser.read_text(encoding='utf-8-sig')
assert json.loads(coverage.read_text(encoding='utf-8'))['status']=='PASSED'
path=FOLDER/'individual/pwm.json'
record=json.loads(path.read_text(encoding='utf-8'))
record['consumer_followup']={
 'first_failing_layer':'Catalog local_timing_schema still published three loose PWM bounds while the native waveform profile rejects local_timing_evidence.',
 'decision':'Remove those obsolete editor fields. Native source-qualified PWM driver/waveform fields remain intact and existing port capabilities are preserved.',
 'retired_local_fields':['local_timing_evidence.pwm_frequency_hz','local_timing_evidence.update_bound_ms','local_timing_evidence.capture_bound_ms'],
 'after_local_timing_schema':[],
 'source_revisions':record['source_revisions'],
 'evidence':[ref(backend),ref(browser)],'production_delivered':False,
}
path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
path=FOLDER/'progress.json'
progress=json.loads(path.read_text(encoding='utf-8'))
progress['complete_release_gate']='FOURTH_GATE_STOPPED_PWM_CONSUMER_REPAIRED_AWAITING_FULL_RERUN'
progress.setdefault('release_history',[]).append({'status':'FAIL','evidence':ref(receipt_path),
 'cause':'Intentionally stopped before build/deployment after independent current-field coverage found obsolete PWM local editor fields.',
 'scope':'Storage, TypeScript and 556 frontend tests PASS; backend round interrupted and not counted as complete.'})
path.write_text(json.dumps(progress,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
path=FOLDER/'consumer-findings.md'
text=path.read_text(encoding='utf-8')
marker='\nDie Einzelprüfungen und die Quellenkorrekturen sind dokumentiert.'
assert marker in text
text=text.replace(marker,
 '\n- Ein abschließender Katalog-/Einzelbefund-Abgleich fand drei übriggebliebene lokale PWM-Felder, die das native Treiber-/Waveform-Profil bereits ablehnte. Der vierte Release-Lauf wurde deshalb bewusst vor Imagebau und Übernahme beendet; sein unvollständiger Backend-Lauf zählt nicht als PASS. Die veralteten Felder sind aus dem Geräteeditor entfernt, die nativen PWM-Vorgaben und vorhandenen Anschlussfähigkeiten bleiben erhalten. 168 isolierte PWM-Tests, die echte Browserbearbeitung mit Persistenz und der erneute Abgleich jedes aktuellen Feldes aller 125 Profile sind bestanden. Belege: work/pwm-local-schema-backend.txt, work/pwm-local-schema-browser.txt, work/parameter-review-coverage.json.\n'+marker)
path.write_text(text,encoding='utf-8')
print(json.dumps({'status':'PWM_CONSUMER_REPAIRED_AWAITING_FULL_RERUN','backend_passed':168,'browser_passed':1,'production_delivered':False}))
