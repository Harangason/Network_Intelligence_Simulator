"""Bind completed evidence; never marks unfinished release/delivery as complete."""
import hashlib,json,re,runpy,subprocess,sys
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[2]
def ref(path):return {'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
receipt_path=Path(sys.argv[1]);receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
assert runpy.run_path(str(ROOT/'scripts/release_storage.py'))['complete_pass'](receipt)
native=json.loads((OUT/'native-large-document.json').read_text(encoding='utf-8'));production=json.loads((OUT/'production-verification.json').read_text(encoding='utf-8'))
assert native['status']==production['status']=='PASSED'
assert production['image_id']==receipt['image_id'] and production['source_sha256']==receipt['initial_source_sha256']
assert native['module_hashes']==production['module_verification']['module_hashes']
for path,digest in native['module_hashes'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
path=OUT/'workload.json';work=json.loads(path.read_text(encoding='utf-8'))
for f in work['files_changed']:assert (ROOT/f).read_bytes()==(OUT/'after'/f).read_bytes(),f
release_ref=ref(receipt_path);native_ref=ref(OUT/'native-large-document.json');prod_ref=ref(OUT/'production-verification.json');delivery_ref=ref(OUT/'release-and-deploy.log')
work['validations'].update({'native_large_document':{'status':'PASSED','evidence':[native_ref]},'full_release_gate':{'status':'PASSED','evidence':[release_ref]},'production_identity_health_function':{'status':'PASSED','evidence':[prod_ref,delivery_ref]}})
work['outcomes']['production_delivery']={'status':'PASSED','evidence':[release_ref,prod_ref,delivery_ref]}
work['outcomes']['automatic_complete_sections']['evidence'].append(native_ref)
work['outcomes']['complete_aggregate']['evidence'].append(native_ref)
work['delivery'].update({'tested_version':receipt['image_id'],'running_version':production['image_id'],'checks':{'release':{'status':'PASSED','evidence':[release_ref]},'deployment':{'status':'PASSED','evidence':[delivery_ref,prod_ref]},'health':{'status':'PASSED','evidence':[prod_ref]},'functional':{'status':'PASSED','evidence':[native_ref,prod_ref]}}})
work['preflight']['release_gate']='Complete PASS for exact deployed immutable image; prior storage FAIL preserved.'
work['validation']['native_large_document']={'status':'PASSED','characters':native['source_chars'],'sections':len(native['result']['segments']),'calls':len(native['calls']),'components':len(native['result']['interpretation']['components']),'database_access':False}
links_ref=ref(OUT/'production-links.json')
work['delivery']['checks']['health']['evidence'].append(links_ref)
work['validations']['production_identity_health_function']['evidence'].append(links_ref)
work['completion_status']='VALIDATING';work.pop('running_sessions',None);path.write_text(json.dumps(work,ensure_ascii=False,indent=2),encoding='utf-8')
guard=Path('F:/CodexOrdner/skills/lokaler-implementierungs-agent/scripts/implementation_guard.py')
result=subprocess.run([sys.executable,str(guard),'completion','--workload',str(path)],capture_output=True,text=True,check=True)
check=json.loads(result.stdout);assert check['status']=='COMPLETED',check
(OUT/'completion-guard.json').write_text(json.dumps(check,indent=2),encoding='utf-8');work['completion_status']='COMPLETED';path.write_text(json.dumps(work,ensure_ascii=False,indent=2),encoding='utf-8')
report=f'''# Vollständige Dokumentauswertung – Abschluss

Größere Dokumentquellen werden ohne die bisherige Acht-Abschnitt-Grenze vollständig und automatisch ausgewertet. Nur zu dichte Abschnitte werden weiter geteilt. Die begrenzten lokalen Modellaufrufe und alle Quellen-/Semantikprüfungen bleiben aktiv. Die vollständige Befundsammlung behält mehr als 60 Komponenten und 32 Technologieangaben. Eingabe: maximal eine Million Unicode-Zeichen, bestehende Dateigrößengrenze bleibt erhalten.

Deine Originaldatei D_INDUSTRIAL_ROBOTICS_054_063.md: {native['source_chars']} Zeichen, {len(native['result']['segments'])} Abschnitte, {len(native['calls'])} echte lokale Qwen-Aufrufe, {len(native['result']['interpretation']['components'])} zusammengeführte Befunde. Alle Originalzeichen und Abschnittshashes sind nachgewiesen. Keine Datenbank-/Modelländerung durch diese Auswertung.

92 gezielte Backendregressionen bestanden, sieben gezielte Frontend-/Transportprüfungen bestanden. Der vollständige Release-Gate ist PASS; Detailzahlen und Grenzen stehen in seinen Berichten. Das ist Dokumentaufnahme und Vorschlagserstellung, kein Nachweis eines neunphasigen Engineering-Workflows aus dieser Originaldatei.

Produktivimage: {receipt['image_id']}
Quellidentität: {receipt['initial_source_sha256']}
Receipt: {receipt_path}

Laufende Identität, Health, geänderte Module, vollständige Segmentierung im Container und ein echter lokaler Dokumentaufruf über die reguläre produktive HTTP-Schnittstelle wurden nach Auslieferung geprüft. Keine Geräte angelegt und kein Vorschlag freigegeben.

Der anfängliche Speicher-FAIL ist erhalten. Genau ein ungenutzter historischer FAIL-Kandidat wurde nach vollständiger Archivverifikation unter der stehenden Nutzerfreigabe mit docker image rm --no-prune entfernt. Archiv, Receipt, sämtliche Blobhashes, frischer Referenzabgleich und exakter Befehl bleiben im Workload dokumentiert.
'''
(OUT/'report.md').write_text(report,encoding='utf-8')
print(json.dumps({'status':'COMPLETED','image':receipt['image_id'],'sections':len(native['result']['segments']),'components':len(native['result']['interpretation']['components'])}),flush=True)
