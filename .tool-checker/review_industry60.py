"""Evidence review only. Does not replay agent operations or modify product data."""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
from run_industry60_jobs import cli, ROOT
from industry60_adapter import request

E = ROOT / '.tool-checker/evidence/industry60'
M = json.loads((ROOT / '.tool-checker/industry60.normalized.json').read_text(encoding='utf8'))
FINDINGS = [
 ('F09','P1',['S22','S28'],'Langlauf ohne verlässlichen Abschluss und wiederholte leere Fortsetzung','S22 beendet die Antwortverbindung nach fünf Arbeitsschritten; der History-Endpunkt bleibt leer. S28 persistiert zweimal dieselbe ERROR-Meldung Keine weitere Trace-Seite offen (13:23:29 und 13:27:34 UTC) und bleibt im Browser laufend. Ein erfolgreicher Abschluss wurde nicht beobachtet.','S22/agent.sse','S22/history-final.json','S28/conversation-final.json','S28/browser.txt'),
 ('F01','P1',['S24'],'Cache beschädigt strukturierte Antwort','Der ausgeführte Anschlussauftrag erzeugt im Browser eine ungültige Agentenantwort. backend.log belegt 19 Schemafehler: visualization.nodes wurden durch den String [Cache-Tiefe begrenzt] ersetzt. Persistierte Mutation und kaputte Ergebnisdarstellung widersprechen sich.','S24/browser.txt','backend.log'),
 ('F02','P1',['S30'],'Wizard-Modus überschreibt bestehenden Arbeitsauftrag','Architektur erstellen + Verbinde ParkAssist mit DriverAssistance, simuliere und analysiere erzeugt einen neuen Entwurf mit null Geräten. Die vorhandenen Funktionen werden nicht zum geforderten Verbindungsworkflow verwendet.','S30/browser.txt','S30/after.json'),
 ('F03','P1',['S33','S36'],'Normale Gateway-Hops als Routenwechsel gewertet','Die unveränderte Zwei-Hop-Route erzeugt 217 ROUTE_CHANGE-Beobachtungen im Fenster 11–16 s, bereits vor dem Fehlerbeginn bei 12 s. Der Vergleich nach Message-ID vermischt unterschiedliche Segmente. Insgesamt 500 Beobachtungen schöpfen das Limit aus.','trace/golden-comparison-http.json','trace/root-cause-browser.txt'),
 ('F04','P2',['S31'],'Fehlende Trace-Zeit wird nicht als Datenlücke gemeldet','MCP load_trace akzeptiert ein Ereignis ohne Zeit mit SUCCESS und ohne Warnung. Ein nichtnumerischer Zeitwert wird dagegen zurückgewiesen. Eine verlässliche Zeitbasis ist so nicht zugesichert.','trace/mcp-inline.json'),
 ('F05','P2',['S35','S40'],'Ausgewähltes Ereignis geht beim Reload verloren','Während Ansichtswechsel bleibt 12.502171 s ausgewählt. Nach Reload wählt die Seite wieder 12.500158 s aus dem unveränderten focus_s=12.5-Link. Ereignis-ID und Auswahl werden nicht im Deeplink fortgeschrieben.','trace/signals-browser.txt','trace/reload-settled-browser.txt'),
 ('F06','P1',['S39'],'Großer Import endet bei nicht fortsetzbarer Vorschau','Der echte HTTP-Import einer Datei mit 100501 Ereignissen liefert nur die ersten 2000, truncated=true, ohne Session-ID oder Fortsetzungscursor. Das bestehende Paging für Simulationsdateien behebt diesen Importpfad nicht.','trace/large-import-http.json','trace/large-window.json'),
 ('F07','P2',['S25'],'Schemafehler nicht feldweise strukturiert','INVALID_INPUT ist korrekt, aber field, reason und expected schema liegen nur als Pydantic-Fehlertext in findings.message vor. Die geforderte maschinenlesbare Feldstruktur fehlt.','mcp/protocol.json'),
 ('F08','P3',['S01-A'],'Prüfhinweis: PWM-Ventile nur mit Auf/Zu-Auswahl','Für explizite PWM-Ventile bietet Ventilbefehl nur Noch offen und Auf/Zu mit einem Bit. Eine proportionale PWM-Befehlssemantik ist in dieser Auswahl nicht abbildbar. Die Quelle legt keinen Stellbereich fest: daher Verbesserungshinweis, kein bewiesener fachlicher Fehler und keine automatische Umdeutung.','S01-A/browser.txt','S01-A/draft.json'),
]
DETAILS = {
 'S21':'Wizard-Schaltfläche, Eingabe und gespeicherter 8-Geräte-Entwurf im Browser geprüft. Offene Angaben nicht beantwortet; kein vollständiger Modellvorschlag freigegeben.',
 'S22':'181 reale MCP-Tools samt Input-/Outputschema, Version und Permission geprüft. Zusätzlicher Agentenauftrag endete im HTTP-Stream nach fünf Arbeitsschritten mit Verbindungsfehler; spätere Persistenz gesondert gespeichert. Kein Abschlussnachweis.',
 'S23':'Realer Browserauftrag löst beide Funktionen samt Controller, Port und Netz korrekt auf. Modellrevision vor/nach unverändert. Vollständige Einzel-Tool-Sequenz nicht unabhängig instrumentiert.',
 'S24':'Vorgegebene direkte CAN-FD-Entscheidung im Browser bestätigt. Anschluss und Route persistiert; Capacity/Timing/Preflight aktualisiert. Ergebnisdarstellung scheitert am Cache-Schema.',
 'S25':'Echte MCP-Fehlerantworten für unbekanntes Tool, ungültiges Argument und nicht unterstützte Technologie; Timeout per Transport-Fault-Injection, volle Kanäle per Core-Fixture. Kein vollständiger Browserfehlerpfad.',
 'S26':'Zwei Payload-Checkboxen und offene Bestätigung im Browser nachgewiesen. Weitere Architekturwahl gemäß Nutzeranweisung nicht beantwortet; keine vollständige Fortsetzung.',
 'S27':'Gespeichertes MotorRPM mit 4 Bit im Browser und realem MCP geprüft: mindestens 7 Bit, ERROR-Finding, kein neuer Signalgenerator. Weitere Visualisierungs-/Retryvarianten nicht vollständig geprüft.',
 'S28':'Trace-Wizard am echten Simulationsjob ausgeführt. Agent zeigt Keine weitere Trace-Seite offen als ERROR; finale vollständige Kausalkette nicht nachgewiesen. Fixture hat Gateway-Delay und Deadline-Miss, aber keinen belegten Queue-Aufbau; deshalb kein PASS für die geforderte Gesamtkette.',
 'S29':'Realer MCP/SQL-Test prüft gespeicherten Finding-Read, ACCEPTED_RISK und NEEDS_REVIEW nach Modelländerung. Zusätzliche HTTP-Negativprobe mit Gateway ohne gespeicherten Befund liefert korrekt INCOMPLETE. Browser-Gesamtkette mit Articulation-Point-Baseline fehlt.',
 'S30':'Original-Mehrschrittauftrag im Architektur-Wizard führt trotz vorhandener Funktionen in einen leeren Projektentwurf. Simulation/Trace/Findings der geforderten Kette nicht erreicht.',
 'S31':'Echter Simulationsjob als Trace-Session im Browser geladen; Import-/Fenster-Regressionsprüfungen und MCP-Negativproben. Fehler bei fehlender Zeit. Persistente Importsession und vollständige Metadaten nicht nachgewiesen.',
 'S32':'CAN-FD und Ethernet im Browser, Rohdaten, IP-/Portdetails und kanonische Deeplinks geprüft. DDS, Modbus, PROFINET und ARINC-Labelvarianten nicht durch diesen Lauf vollständig gedeckt.',
 'S33':'Echte Zwei-Hop-Simulation und Sequenzansicht; API bewahrt Segment-/Kausal-IDs. Ursachenanalyse verwechselt normale Hops mit Routenwechseln. Vollständige Hop-Delay-Darstellung fehlt in der beobachteten Sequenzansicht.',
 'S34':'Temperature wird mit Wert, Einheit und VALID angezeigt. Fünf geforderte Kanäle und sämtliche fehlerhaften Encodings nicht vollständig im Browser geprüft; bestehende Decoder-/Signalregressionen ergänzen nur Teilabdeckung.',
 'S35':'Ansichtswechsel Botschaften → Sequenz → Signale → Trace → Findings → Root Cause erhält ausgewähltes Ereignis. Reload verliert die genaue Auswahl. Keine vollständige Playhead-/Cursor-Abnahme.',
 'S36':'Gateway-Delay 12–15 s und Deadline-Miss in realem Simulationsjob und HTTP-Reasoning; Kausalkette bleibt wegen fehlendem kanonischem Snapshot unbestätigt. Zusätzlich falsche ROUTE_CHANGE-Flut. Kein Queue-Wachstum im Testaufbau, daher nicht als erfolgreich gewertet.',
 'S37':'Golden-/Fehlerjob, 100-ms-Abweichung und erste Abweichung bei 12.00217094 s über HTTP und Browser nachgewiesen. Zusätzliches Fehl-/Mehrereignis, Zustands- und Routenwechsel nicht alle unabhängig erzeugt.',
 'S38':'Reasoning prüft Fault-Hypothese und verwirft unbelegte Queue-Ursache. Die konkret geforderte CameraBurst→Queue→CAN-FD→MotorStatus-Kette wurde nicht aufgebaut; keine Ursachenfreigabe und kein PASS.',
 'S39':'100501 Datensätze: echte Import-API sowie Core-Fensterlesen mit 500er-Paging ab Sekunde 99. Import ist auf 2000 begrenzt. Browser-Dateiauswahl zweimal am Provider-Timeout gescheitert; kein Browser-Leistungsnachweis.',
 'S40':'Teilpfad aus kanonischen IDs, echten HTTP-Simulationen, Trace-Ansichten, Golden-Vergleich, Reasoning und Reload geprüft. Keine durchgängig freigegebene Route/Topology/Snapshot-Kette. Fehlender Snapshot korrekt als Datenlücke; Reload-Verlust zusätzlich belegt.',
}

def main():
 rows=[]
 for c in M['test_cases']:
  if len(sys.argv)>1 and c['test_id'] not in sys.argv[1:]:continue
  cid=c['test_id'];d=E/cid;d.mkdir(exist_ok=True);review=d/'review';review.mkdir(exist_ok=True)
  if (review/'finish.json').exists() and cid not in ['S01-A','S22','S28']:
   old=json.loads((review/'finish.json').read_text(encoding='utf8'));obs=json.loads((review/'observations.json').read_text(encoding='utf8'))
   rows.append({'id':cid,'status':old['status'],'run_id':obs['run_id'],'detail':obs['review_scope'],'findings':[f['code'] for f in obs['findings']],'evidence':str(d)})
   continue
  project=(c.get('execution_plan') or [{}])[0].get('project_id','nis-e2e-industry60-'+cid.lower())
  if int(cid[1:3])>=31 or cid=='S28':project='nis-e2e-industry60-trace'
  code,body=request('http://127.0.0.1:51576',project,'/api/engineering/workflow?view=summary');assert code==200
  current=json.loads(body);(review/'current.json').write_text(body,encoding='utf8')
  baseline={'model_revision':current['versions'],'workflow':current,'scope':'Baseline of evidence-review phase; original execution baselines remain in per-case evidence.'}
  (review/'baseline.json').write_text(json.dumps(baseline),encoding='utf8')
  plan=cli('tool_check.py','--task','industry60','dry-run',cid)[0]
  proof={'source_hash':plan['context']['source_hash'],'contract_hash':plan['context']['test']['contract_hash'],'project_path':str(ROOT),'checked_at':datetime.now(timezone.utc).isoformat(),
   'available_skills':['tool-checker'],'available_tools':['NIS HTTP API','Browser'],'available_views':['Engineering'],'browser':{'observed_working':True},'isolated_scope':'Review of disposable industry60 evidence; no operation replay'}
  for key in ['dependencies','application','project','permissions','test_data']:proof[key]={'status':'PASSED','evidence':'Recorded disposable-stack execution plus fresh current.json. Evidence-review scope only; incomplete source prerequisites remain in completion assessment.'}
  for key in ['preconditions','required_model_context']:proof[key]=[{'name':n,'status':'PASSED','evidence':'Original preflight/fixture where available; current.json confirms isolated scope. Scenario prerequisites and missing fixtures explicitly assessed in detail.'} for n in c[key]]
  (review/'preflight.json').write_text(json.dumps(proof),encoding='utf8')
  r=cli('tool_check.py','--task','industry60','run',cid,'--preflight',str(review/'preflight.json'),'--baseline',str(review/'baseline.json'))
  paths=[review/'current.json']
  paths += [p for p in d.iterdir() if p.is_file() and p.suffix in ['.json','.txt','.png','.sse']]
  related=[f for f in FINDINGS if cid in f[2]]
  for f in related:paths += [E/p for p in f[5:]]
  if int(cid[1:3])>=31 or cid=='S28':paths += [E/'trace/canonical-jobs.json',E/'trace/root-cause-http.json',E/'trace/golden-comparison-http.json',E/'trace-regressions.xml']
  if cid in ['S22','S25','S27','S29']:paths += [E/'mcp/protocol.json',E/'mcp/full-channels.json']
  refs=[]
  for p in dict.fromkeys(paths):
   if not p.exists():continue
   kind='screenshot' if p.suffix=='.png' else 'model' if p.suffix=='.json' else 'log'
   refs.append(cli('tool_check.py','evidence',r['run_id'],str(p),'--kind',kind)['id'])
  detail=DETAILS.get(cid,'Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt.')
  if cid=='S01-A':detail+=' PWM-Auswahlproblem F08 im Browser belegt.'
  actual={'run_id':r['run_id'],'actions':[],'tools':[{'name':'NIS HTTP API','status':'PASSED','evidence':refs}],
   'checks':[],'model_after':baseline,'claimed_complete':False,'findings':[{'code':f[0],'category':'AGENT_BUG','blocking':f[0]!='F08','detail':f[3]+': '+f[4],'evidence':refs} for f in related],
   'review_scope':detail,'evidence_review':True,'not_a_replay':True}
  (review/'observations.json').write_text(json.dumps(actual,ensure_ascii=False,indent=2),encoding='utf8')
  finished=cli('tool_check.py','finish',r['run_id'],'--observations',str(review/'observations.json'))
  (review/'finish.json').write_text(json.dumps(finished,ensure_ascii=False,indent=2),encoding='utf8')
  rows.append({'id':cid,'status':finished['status'],'run_id':r['run_id'],'detail':detail,'findings':[f[0] for f in related],'evidence':str(d)})
  print(cid,finished['status'],flush=True)
 if len(sys.argv)>1:
  old=json.loads((ROOT/'.tool-checker/reports/industry60-report-20260916.json').read_text(encoding='utf8'))
  replacements={r['id']:r for r in rows};rows=[replacements.get(r['id'],r) for r in old['cases']]
 report={'task':'industry60','source_hash':M['source_hash'],'build':'c16f447ee305','image':'sha256:366382afb7c34efeb2b2c689d7016ad752130368c195e264e3fff2cda1dfbde2','counts':dict(Counter(x['status'] for x in rows)),'cases':rows,'findings':[{'id':f[0],'priority':f[1],'cases':f[2],'title':f[3],'detail':f[4],'evidence':list(f[5:])} for f in FINDINGS]}
 (ROOT/'.tool-checker/reports/industry60-report-20260916.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
 print(report['counts'])

if __name__=='__main__':main()
