"""Record the sole live normal preparation and its mandatory continuation."""
from datetime import datetime, timezone
import hashlib
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = Path.cwd()
SESSION = int(sys.argv[1])


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


freeze = read(OUT / 'candidate-prepare-freeze.json')
assert read(OUT / 'retire-6d6-stack/retirement.json')['status'] == 'EXACT_OBSOLETE_STACK_RETIRED'
assert read(OUT / 'host-verification-reconciliation.json')['status'] == 'TESTED_HOST_VERIFICATION_REFROZEN'
assert not (OUT / 'candidate-prepare-result.json').exists()
now = datetime.now(timezone.utc).isoformat()
status = f'NORMAL_PREPARATION_{SESSION}_ACTIVE'
for path in (OUT / 'checkpoint.json', OUT.parent / 'checkpoint.json'):
    data = read(path)
    data.update(at_utc=now, status=status, active_test_session=None, active_native_session=None,
                preparation_session=SESSION, preparation_exit_code=None,
                current_application_source_sha256=freeze['identity']['source_sha256'],
                current_verification_sha256=freeze['identity']['verification_sha256'],
                obsolete_stack_retirement=ref(OUT / 'retire-6d6-stack/retirement.json'),
                host_verification_reconciliation=ref(OUT / 'host-verification-reconciliation.json'),
                preparation_freeze=ref(OUT / 'candidate-prepare-freeze.json'),
                continuation_watch={'id': 'nis-nach-fahrzeugpr-fung-fortsetzen', 'status': f'ACTIVE_ONLY_PREPARATION_{SESSION}'},
                next=f'Monitor only the existing{SESSION} preparation. Verify final result/receipt plus process end. Pause monitor before transfer and actual original checks; no duplicate build or old failed native continuation.')
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
work_path = OUT / 'workload.json'
work = read(work_path)
work.update(status=status, candidate_preparation={'session':SESSION,'freeze':ref(OUT / 'candidate-prepare-freeze.json'), 'full_release_pass':False})
work_path.write_text(json.dumps(work, indent=2) + '\n', encoding='utf-8')
note = '''## Fortsetzung: reguläre Vorbereitung57322 läuft

Die gezielten103+155=258 verschiedenen Fälle aus zwei Läufen sind bestanden.
Die getrennte Hostbereinigung ist abgeschlossen:26 alte vollständig archivierte
PREPARED-Images und28 gestoppte Testcontainer entfernt,73 Images geschützt.
Die38 Hostwerkzeugfälle und die echte lesende Wiederverwendung/Sperrprüfung
sind bestanden. Diese38 sind keine zusätzlichen Original-/Modellfälle.

Der eigene überholte6d6-Teststack wurde danach vollständig gesichert und exakt
stillgelegt. Frischer Custom-Dump149254Bytes mit geprüftem Inhaltsverzeichnis,
Laufzeitvolume mit Dateihashes, Logs, normale Exporte beider Projekte und ein
vollständiges23Blob-Imagearchiv liegen recoverbar vor. Das6d6-Image und sein
ursprünglichesPREPARED-Receipt sind erhalten. Produktion3792, Produktdatenbank
und Rückfallimage blieben identisch. Siehe retire-6d6-stack/retirement.json.

Die vorherige Vorbereitung90140 stoppte vor jedem Build wegen der geänderten
Host-Verification. Originalfreeze113c bleibt separat erhalten; die unveränderte
Quelle61c7649a933d/HEAD70f ist mit den38 geprüften Hostwerkzeugfällen an
Verification6a937cf1717f gebunden, ohne Budget-/Gate-/Sperrumgehung. Siehe
host-verification-reconciliation.json. Keine neue menschliche Freigabe fehlt.

Aktuell läuft genau eine normale Vorbereitung:Session57322, prepare_candidate.py,
offizielles scripts/run-release-gate.py --prepare. Freeze/log/result stehen hier,
Ausgabe backend/test-output/release-gates/joint-single-inventory-originals-61c7649a933d.
Keinen weiteren Build/Prepare/Test/Originalrequest parallel starten. Zuerst
Prozess und candidate-prepare-result.json sowie das tatsächliche Receipt prüfen.
Nur terminales Ergebnis samt Prozessende zählt. Vor Folgearbeit Monitor pausieren.
Ein PREPARED-Ergebnis ist weiterhin kein vollständigerPASS.

Danach den bestehenden Source-only-API-Transfer mit --inventory-cardinality-repair-dir
auf das tatsächliche neue Receipt ausführen;16Antworten/2Importrequests unabhängig
hashen und die Child-Operator-Evidence sichern. NeueStates native-single-choice-*
behalten die unveränderten Originale und die tatsächliche historische36f-Qwen-
Intakeherkunft. Erst nach neuer EIP-/Provider-/Produktqueue-Prüfung echte frische
Originalreferenzoperationen beginnen; keine Wiederaufnahme interner Inventare.
Dann beide vollständigen Modelle/ALL-Simulationen und alle15/15 Pflichtziele,
vollständiges finales Releasegate und exakt getestete produktive Übernahme.

'''.replace('57322', str(SESSION))
for path in (OUT / 'NEXT.md', OUT / 'REPORT.md', OUT.parents[2] / 'TODO.md'):
    path.write_text(note + path.read_text(encoding='utf-8'), encoding='utf-8')
print(json.dumps({'status':status,'source':freeze['identity']['source_sha256'],'verification':freeze['identity']['verification_sha256']}))
