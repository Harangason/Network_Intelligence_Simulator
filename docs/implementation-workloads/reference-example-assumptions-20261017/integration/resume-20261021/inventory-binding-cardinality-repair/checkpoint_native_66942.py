"""Save actual normal preparation, source import and live native continuation."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
BASE = OUT.parents[1]
STATE = BASE / 'native-single-choice-vehicle/state.json'
RECEIPT = ROOT / 'backend/test-output/release-gates/joint-single-inventory-originals-61c7649a933d/6d41919070e2/receipt.json'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


state = read(STATE)
receipt = read(RECEIPT)
result = read(OUT / 'candidate-prepare-result.json')
assert state['status'] == 'NATIVE_PLAN_REFERENCE_RUNNING'
assert receipt['status'] == 'PREPARED' and result['exit_code'] == 0
assert state['image_id'] == receipt['image_id']
assert read(OUT / 'independent-current-transfer-review.json')['response_hashes_checked'] == 16
assert read(OUT / 'pre-native-main-provider-read.json')['status'] == 'READY_FOR_SINGLE_NATIVE_REQUEST'
now = datetime.now(timezone.utc).isoformat()
snapshot = OUT / 'native-start-state-66942.json'
assert not snapshot.exists()
shutil.copy2(STATE, snapshot)
record = {'at_utc': now, 'status': 'NATIVE_VEHICLE_REFERENCE_66942_ACTIVE',
          'session': 66942, 'driver_process_ids': [65292, 59712],
          'state_path': str(STATE), 'events_path': str(STATE.parent / 'plan-reference/events.ndjson'),
          'start_state_snapshot': ref(snapshot), 'receipt': ref(RECEIPT),
          'image_id': receipt['image_id'], 'image_tag': receipt['image_tag'], 'base_url': receipt['base_url'],
          'source_sha256': receipt['initial_source_sha256'], 'commit_id': receipt['initial_commit_id'],
          'verification_sha256': receipt['verification_sha256'],
          'preparation_session': 99722, 'preparation_exit_code': 0, 'preparation_process_ended': True,
          'preparation_result': ref(OUT / 'candidate-prepare-result.json'),
          'independent_transfer': ref(OUT / 'independent-current-transfer-review.json'),
          'provider_and_product_observation': ref(OUT / 'pre-native-main-provider-read.json'),
          'eip_current_explicit_confirmation': ref(OUT / 'eip-current-confirmation.json'),
          'not_an_internal_inventory_resume': True, 'fresh_complete_intake_claimed': False,
          'actual_historical_intake_origin': state['document_origin'],
          'current_ui_progress_is_not_model_acceptance': state.get('ui_progress'),
          'all_15_outcomes_15_validations_preserved': True,
          'full_original_models_all_simulations_full_gate_product_delivery_pending': True,
          'production_image_unchanged': 'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'}
write(OUT / 'checkpoint-native-66942.json', record)
for path in (OUT / 'checkpoint.json', OUT.parent / 'checkpoint.json'):
    cp = read(path)
    cp.setdefault('initial_repair_source_identity', cp.get('source_identity'))
    cp.update(at_utc=now, status=record['status'], active_test_session=None, active_operator_session=None,
              active_native_session=66942, active_state=str(STATE),
              source_sha256=record['source_sha256'], source_identity=read(OUT / 'prepared-current-identity.json'),
              head=record['commit_id'], verification_sha256=record['verification_sha256'],
              image_id=record['image_id'], image_tag=record['image_tag'], base_url=record['base_url'],
              receipt_status='PREPARED', new_candidate_built=True, image_count=74,
              preparation_session=None, preparation_exit_code=0,
              current_native_checkpoint=ref(OUT / 'checkpoint-native-66942.json'),
              continuation_watch={'id': 'nis-nach-fahrzeugpr-fung-fortsetzen', 'status': 'ACTIVE_ONLY_NATIVE_66942'},
              next='Monitor only the complete native66942 request. Require terminal state/result/error plus actual process end. Pause monitor before actual source-bound response review and normal hash-bound workflow continuation. No duplicate inference/tests/build/release.')
    if 'native_driver_exit_code' in cp:
        cp['previous_61930_driver_exit_code'] = cp['native_driver_exit_code']
        cp['native_driver_exit_code'] = None
        cp['native_process_ended'] = False
    write(path, cp)
path = OUT / 'workload.json'
work = read(path)
work.update(status=record['status'], current_native_checkpoint=ref(OUT / 'checkpoint-native-66942.json'),
            current_candidate={'receipt':ref(RECEIPT),'image_id':record['image_id'],'status':'PREPARED','full_release_pass':False})
write(path, work)
path = BASE / 'resume-20261020/eip-inference-coordination.json'
coord = read(path)
coord.update(active_native_session=66942, active_native_state=str(STATE), native_request_terminal=False,
             inference_owner='NIS', latest_native_checkpoint=ref(OUT / 'checkpoint-native-66942.json'))
write(path, coord)
parent = BASE / 'workload.json'
work = read(parent)
assert len(work['required_outcomes']) == len(work['validation_requirements']) == 15
work['current_execution_checkpoint'] = ref(OUT / 'checkpoint-native-66942.json')
write(parent, work)
next_path = OUT / 'NEXT.md'
shutil.copy2(next_path, OUT / 'NEXT-history-before-native-66942.md')
text = '''# Aktuelle Fortsetzung: nativer Fahrzeugrequest66942

Nur dieser Chat, keine neuen Chats/Unteragenten; Altchats ruhen. Nur kanonisches
I:/PycharmProjects/My_first_Network_Simulator. Zuerst kompakt echten Prozess,
integration/native-single-choice-vehicle/state.json und plan-reference/events.ndjson
prüfen. Session66942, Pythonprozesse65292/59712, normaler
native_original_document_driver.py --state <dieserState> --stage plan-reference.
Ein ganzer regulärer frischer Request; keine Wiederaufnahme interner Inventare.
Solange aktiv keine zweite Inferenz, Tests, Builds, Releases oder Appquelländerungen.
Keine Routinemeldungen, DONT_NOTIFY. NiedrigeCPU/Fortschritt/fehlender Handle sind
kein Ende. Terminaler State samt normalem RESULT/Response/Fehler und tatsächlichem
Prozessende müssen zusammenpassen. Bei verlorenem Client und gespeicherterRUNNING-
Generation echte Worker-/Providerlage prüfen, keinen doppelten Request starten.
Nach verifiziertem Ende Automation vor Folgearbeit pausieren. Bei bereits direkt
arbeitendem Hauptchat nur doppelten Wecklauf pausieren.

AGENTS.md, TODO.md, integration/workload.json mit allen unveränderten15Outcomes/
15Validations, dieses workload.json/REPORT.md und checkpoint-native-66942.json
lesen. Source61c7649a933dc0fae72c85586bb07db43a4875ec3ed0fc09a97cca52050b89fc,
HEAD70f0c160bc4f08bd23437f6b3c175523d1e5859c,
Verification6a937cf1717fd5e739801dcda34dea04f079221d1282c31cb3f1a8c1722f97ba.
Normaler Kandidat networkis:candidate-6d41919070e2,
Imagesha256:189ca2794ddf3f6b6ae320f830f2dd9de8096c9707725e71cf2dabaa4fcfb639,
isoliert127.0.0.1:62244. Receipt backend/test-output/release-gates/
joint-single-inventory-originals-61c7649a933d/6d41919070e2/receipt.json ist nur
PREPARED.99722 regulär Exit0/Prozessende, Produktionsbuild/TypeScript/Start und
Speicher-/Image-/Stackgates bestanden. Wiederverwenden, keinen unnötigen Neubau.

258 verschiedene gezielte Fälle aus103+155 in ZWEI Läufen bestanden, fünf neue
Gegenproben vorherRED; zusätzlich38 getrennte Hostrelease-Toolprüfungen bestanden.
Keine vollständige Originalmodell-/Simulations-/Vollgateabnahme daraus ableiten.
Allgemeine native Inventarbindungskorrektur: höchstens eine Identitätsentscheidung
jeAntwort, unveränderte reguläre vollständige Fortsetzung für alle Fakten/Geräte;
strikte öffentliche/Identitäts-/Merge-Gates und sämtliche Texte/Budgets erhalten.
61930 ist historisch regulär terminal INVALID_INPUT/Exit1, nicht aktiv; exakte
letzteRohantwort fehlt, unbekannte versus doppelteID nicht erfinden.

Bereinigung vollständig erledigt, keine weitere Entfernung nötig.75ccb exakt
freigegeben/archiviert/entfernt; separate26Altimage/28Containerbereinigung belegt.
Überholten6d6Stack vollständig mit Dump/TOC/Runtime/Logs/Projektexporten und23Blob-
Imagearchiv gesichert und exakt stillgelegt, seinImage/Receipt erhalten.
32weitere verwaiste Runtimevolumes mit25.025.054.720Archivbytes und Dateihashes
gesichert und mit3leerenTestnetzen einzeln stillgelegt;20657Exit0/finalerBeleg.
60762Metadatenprüffehler war vor ersterEntfernung. KeinePrune/Force-Operationen;
Produktion/DB/Rollback/fremdeRessourcen/Originalreceipts erhalten. Alle früheren
Vorbereitungsstopps und113cIdentity separat unverändert gesichert. Aktuelle74Images.

Beide Source-only-Projekte über echte normale APIs ins neueImage übertragen;
16Antworten/2exakteImportrequests unabhängig gehasht und alle kanonischen Tabellen/
Jobs leer geprüft. Siehe independent-current-transfer-review.json und Child-
transfer-operator-workload.json. NeueStates integration/native-single-choice-
{vehicle,robot}/state.json. UnveränderteOriginale und tatsächliche historische36f-
Qwen-Intakeherkunft bleiben erhalten, keine frische vollständige61cIntake behaupten.
Snapshot native-start-state-66942.json hält den tatsächlichen Start fest;
laufendeStatefiles sind erwartungsgemäß veränderlich, keine neuen Intakebelege.

EIP hat seit07:30:16Vorladeende/INFERENZ ZURÜCK erneut ausdrücklich bestätigt:
kein neuer Besitzwechsel/Modellrequest/Neustart und kein beanspruchtes Fenster,
NIS besitzt es weiter. eip-current-confirmation.json. DirekteAbstimmung mit
EIP neu starten Thread01a11fb3-c627-7580-8623-9220505981fd ist menschlich autorisiert.
Vor diesemStart Hauptworkeridle/echtesQwenModell/effektive unveränderte131072-
Kontext/1200s-Konfiguration und aktuelleProduktprojekt-Draft/Workloadbelegung
rein lesend geprüft. AltesProduktimage unterstützt den GET-Referenzstatus nicht
(400 unknownresource agent); nicht als neueKandidatenstörung oder vollständige
globale Queueenumeration darstellen. Kein EIP-Privatprovider verändert/abgefragt.
Nur lokalqwen3.8:27b und einModellrequest gleichzeitig. Vor spätererInferenz
neuere tatsächliche Besitzmeldungen/Provider-/Produktbelegung prüfen.

Nach vollständiger echterAntwort quellengebunden fachlich prüfen. Interne
Inventare sind kein fertiger Entwurf. Normale hashgebundeneReview/Accept/Start/
Apply/Continue über native_original_workflow_driver.py verwenden; reguläre
fachlich geprüfteNISVorschläge anzunehmen ist autorisiert. Echte offeneFachfragen
gezielt erfragen. Keine manuellenModelle/Routen/Signale/Ports/Parameter/SQL-
Korrekturen oder erfundenen Hardware/Safety/WCET/Timingbelege. Bei Fehler die
tatsächliche Ursache belegen und allgemein reparieren, RED/GREEN/isolierte
Regressionen sichern, keineGates/Budgets lockern. Historischenative63930 und
Teiltests nicht als aktuellenPASS darstellen.

Beide unverändertenOriginale bleiben Pflicht: Fahrzeug komplett.txt Projekt
20261018160006106-ee6625c9 und D_INDUSTRIAL_ROBOTICS_054_063.md Projekt
20261018160157264-5f0fa2a4. Alle10Robotikprofile054–063/Anforderungen erhalten;
korrigierten lesenden root/verify_robot_saved_model.py mit exakt gehashtem
reviewed-intake verwenden. KameraObjektdaten an echteFahrerassistenz, PDC-
Messquellen/HMI und vollständige Sensor-Verarbeitung-Verbraucher-Steuerung-
Aktor-Feedbackketten müssen vonNIS erzeugt werden. Gateway nurTransport.
Neu9/Nutzerantworten feldgebundeneErgänzungen, keinePrimärmengenersetzung.

Erst beide tatsächlichen vollständigen gespeicherten kanonischenModelle mit
echten Jobs/Snapshots/ALLScope/PASSKonformität/0fehlgeschlagenenRouten/vollen
Traceseiten, dann sämtliche Pflichtprüfungen und vollständiges Releasegate
am exakt finalen normalenImage. Danach scripts/release-and-deploy.py mit
vollständigem passendemPASSreceipt bis zur ausdrücklich autorisierten
produktivenÜbernahme; laufendeIdentität/Gesundheit/betroffeneFunktion prüfen.
Produktion3792 gesund/unverändert, neueKorrektur noch nicht produktiv.
Alle15/15Nachweise/Abschlussguard sichern. Erst tatsächlichen Gesamtabschluss
melden, zugehörigeAutomationen löschen und ArbeitfürdenTag beenden. KeinShutdown
ohne erneutenAuftrag. RoutinewartenDONT_NOTIFY; nur neue materielleFehler,
erforderlicheNutzerentscheidung oder tatsächlichenGesamtabschluss melden.
'''
# Preserve the real historical request number in the handoff.
text = text.replace('native63930', 'native61930')
next_path.write_text(text, encoding='utf-8')
note = '''## Aktuell: vollständiger nativer Fahrzeugrequest66942 läuft

Reguläre Vorbereitung99722 endete mit Exit0 und PREPARED, Image189ca2794ddf
auf Quelle61c7649a933d, Verification6a937cf1717f, isoliert127.0.0.1:62244.
16normale Source-only-Antworten/2exakteImportrequests beiderOriginale unabhängig
gehasht; keine kanonischen Modelle/Jobs importiert und keine neue61cIntakebehauptung.
Frische EIP-Bestätigung, tatsächlicher Hauptworkeridle und Produktprojektbelegung
geprüft. Genau ein neuer vollständiger Fahrzeug-Referenzrequest läuft mit lokalem
qwen3.8:27b, Session66942, aktuelleState/Events unter native-single-choice-vehicle.
Kein fertiger Entwurf/Modell/Simulation/Vollgate/ProduktivPASS. Aktueller maßgeblicher
Fortsetzungspunkt: checkpoint-native-66942.json und neu konsolidierte NEXT.md.
Alle früheren laufend-Markierungen im folgenden Verlauf sind historisch.

'''
for path in (OUT / 'REPORT.md', OUT.parents[2] / 'TODO.md'):
    path.write_text(note + path.read_text(encoding='utf-8'), encoding='utf-8')
print(json.dumps({'status': record['status'], 'image_id': receipt['image_id'], 'prepared_only':True}))
