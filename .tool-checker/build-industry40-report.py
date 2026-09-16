import json,re,collections
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parents[1]
base=root/'.tool-checker/evidence/industry40-live-ai'
cases=json.loads((root/'.tool-checker/industry40.normalized.json').read_text(encoding='utf-8'))['test_cases']
parser={r['test_id']:r['result'] for r in json.loads((root/'.tool-checker/parser-results.json').read_text(encoding='utf-8'))}
expected=[(3,4,1,0),(2,2,1,0),(2,2,1,1),(4,3,1,1),(3,2,1,1),(12,8,3,1),(8,6,None,None),(16,8,4,1),(20,12,4,1),(18,10,3,None),(24,8,None,1),(15,10,5,1),(12,10,4,1),(20,12,6,1),(18,10,5,1),(24,16,8,1),(10,0,2,1),(16,12,2,1),(100,100,50,1),(100,100,50,1)]
rows=[]
for c in cases:
    tid=c['test_id'];n=int(tid[1:3]);p=parser[tid]; directory=base/tid
    ex=dict(zip(['sensors','actuators','ecus','gateways'],expected[n-1]))
    if c['variant']=='B' and n not in [1,2,9]:ex['gateways']=None # central coupling is not automatically physical gateway
    errors=[f'{k}: {p["targetCounts"].get(k)} statt {v}' for k,v in ex.items() if v is not None and p['targetCounts'].get(k)!=v]
    events=[]; outcome='AUSSTEHEND';text=''; seconds=None
    if (directory/'agent-events.json').exists():
        events=[e.get('data',e) for e in json.loads((directory/'agent-events.json').read_text(encoding='utf-8'))['events']]
        meaningful=[e for e in events if e.get('type') in ['RESULT','ERROR','QUESTION','SINGLE_SELECT','MULTI_SELECT','APPROVAL','FINDING','error']]
        text='\n\n'.join(max([str(e.get('text',e.get('errorText','')))]+[str(o.get('content','')) for o in e.get('outputs',[]) if o.get('output_type')=='CHAT'],key=len) for e in meaningful)
        outcome='TEILPRÜFUNG'
        if any(e.get('type') in ['ERROR','error'] or (e.get('type')=='FINDING' and e.get('severity')=='ERROR') for e in events):outcome='FEHLER'
        if re.search(r'Wähle die vorhandene Hardware|sollten Sie die Eingabe für den Tool-Aufruf|Bitte die fehlenden Angaben oder verfügbaren Werkzeuge prüfen',text):outcome='FEHLER'
        try:
            # Request is written immediately before POST; wire response immediately
            # after receiving the body. Include frontend timeout, even without a
            # timestamp on its error event. Do not mistake heartbeat/event span
            # for the actual user-visible wait.
            seconds=round((directory/'agent.sse').stat().st_mtime-(directory/'request.json').stat().st_mtime,1)
        except ValueError:pass
    summary=json.loads((directory/'summary.json').read_text(encoding='utf-8')) if (directory/'summary.json').exists() else {}
    snapshot=json.loads((directory/'after.json').read_text(encoding='utf-8')) if (directory/'after.json').exists() else {}
    structured_questions=[e for e in events if e.get('type') in ['QUESTION','SINGLE_SELECT','MULTI_SELECT']]
    approvals=[e for e in events if e.get('type')=='APPROVAL']
    invalid_proposals=[e.get('proposal',{}) for e in approvals if e.get('proposal',{}).get('validation_result',{}).get('valid') is False]
    tool_errors=[e for e in events if e.get('type')=='FINDING' and e.get('severity')=='ERROR']
    result_statuses=[e.get('status') for e in events if e.get('type')=='RESULT']
    claim_checks={'structured_questions':len(structured_questions),'approval_events':len(approvals),'tool_error_events':len(tool_errors),'result_statuses':result_statuses,'persisted_counts':snapshot.get('workflow',{}).get('artifact_checks',{}).get('engineering_model',{}).get('counts'),'persisted_analyses':list(snapshot.get('workflow',{}).get('latest_analyses',{})), 'unbacked_calculation_claim':tid=='S08-A' and '5,12' in text,'unperformed_goal_marked_answered':tid=='S07-A' and 'ANSWERED' in result_statuses,'capacity_validated':None,'functional_timing_validated':None,'reuse_validated':None,'simulation_trace_validated':None}
    if claim_checks['unbacked_calculation_claim'] or claim_checks['unperformed_goal_marked_answered']:outcome='FEHLER'
    claim_checks['invalid_proposals']=invalid_proposals
    if (directory/'workflow-full.json').exists():claim_checks['full_workflow']=json.loads((directory/'workflow-full.json').read_text(encoding='utf-8'))
    if (directory/'workload.json').exists():claim_checks['workload']=json.loads((directory/'workload.json').read_text(encoding='utf-8'))
    conversation=json.loads((directory/'conversation.json').read_text(encoding='utf-8')).get('data',{}) if (directory/'conversation.json').exists() else {}
    claim_checks['stored_open_questions']=[q for q in conversation.get('questions',{}).values() if q.get('status')=='OPEN']
    continuation=directory/'continuation'
    if (continuation/'finished.json').exists():
        claim_checks['continuation_result']=json.loads((continuation/'finished.json').read_text(encoding='utf-8'))
        if (continuation/'after.json').exists():claim_checks['continuation_workflow']=json.loads((continuation/'after.json').read_text(encoding='utf-8'))['workflow']
        if (continuation/'proposal-after.json').exists():claim_checks['continued_proposal']=json.loads((continuation/'proposal-after.json').read_text(encoding='utf-8'))
        if (continuation/'agent-events.json').exists():claim_checks['continuation_events']=json.loads((continuation/'agent-events.json').read_text(encoding='utf-8'))
    if invalid_proposals:outcome='FEHLER'
    if structured_questions and not errors and not any(e.get('type') in ['ERROR','error'] for e in events):outcome='ENTSCHEIDUNG OFFEN'
    if (continuation/'conversation.json').exists():
        follow_state=json.loads((continuation/'conversation.json').read_text(encoding='utf-8')).get('data',{})
        answered=follow_state.get('answered_questions',{})
        repeated=[q for q in follow_state.get('questions',{}).values() if q.get('status')=='OPEN' and q.get('decision_key') in answered]
        claim_checks['repeated_answered_questions']=repeated
        if repeated:outcome='FEHLER'
    if errors and outcome!='AUSSTEHEND':outcome='FEHLER'
    if any(e.get('data',e).get('type') in ['ERROR','error'] for e in claim_checks.get('continuation_events',{}).get('events',[])):outcome='FEHLER'
    if tid=='S10-A' and 'create_objects_via_proposal' in text and not approvals:
        claim_checks['tool_call_printed_instead_of_executed']=True
        outcome='FEHLER'
    rows.append(dict(test_id=tid,title=c['title'],architecture=c['architecture_variant'],outcome=outcome,parser_count_findings=errors,expected_counts=ex,requested=p['targetCounts'],identified_chains=len(p['chains']),agent_text=text,agent_seconds=seconds,claim_checks=claim_checks,summary=summary,evidence_dir=str(directory)))
out=root/'.tool-checker/reports';out.mkdir(exist_ok=True)
(out/'industry40-results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
counts=collections.Counter(r['outcome'] for r in rows)
lines=['# Industrieneutrale Agentenprüfung – 40 Szenarien','',f'Stand: {datetime.now(timezone.utc).isoformat()}','',
'Quelle: `NETWORK_SIMULATOR_40_INDUSTRY_NEUTRAL_AGENT_TEST_SCENARIOS.md`, SHA-256 `5f3d9eecb6339412c5deb40d17d7a1504562e1142f4a7db3d29038c50da95aeb`.','',
'Getesteter Build: `311549ffd1e3`, unveränderliches Image `sha256:a0116ccca7c892334441ff11440f7652644179ae6709d2666598549df5ce6f6d`. Eigene PostgreSQL-/Runtime-Instanz; keine Produktmodelle geändert.','',
'## Tatsächlicher Umfang','',
'Alle 40 Originaleingaben wurden zusätzlich durch den echten Frontend-Parser geprüft. Die laufende Hauptmatrix verwendet den echten HTTP-Agenten mit lokalem Ollama sowie Playwright/Chromium für den Wizard. Originalantworten, Gesprächspersistenz, kanonische Inventare, Versionsstände, Eingaben und Screenshots bleiben gespeichert. Es werden keine erfolgreichen Schreibantworten simuliert und keine Modellzeilen direkt eingesetzt.','',
'Die Hauptläufe erfassen die erste Agentenantwort und den Geräteumfang. Sie behaupten keine abgeschlossene neunphasige Ausführung. Ungeprüfte Wiederverwendung, Kapazität, funktionales Timing, Preflight, Simulation und Trace bleiben offen. Fehlende technische Entscheidungen werden nicht erfunden. Die ersten Adapter-/Offline-Kalibrierungsversuche sind getrennt archiviert und zählen nicht zur Hauptmatrix.','',
f'Ergebnisstand: {dict(counts)}. Kein vollständiger E2E-PASS.','',
'## Bereits belegte Hauptbefunde','',
'1. **Mengen und Gerätetypen:** Die separat ausgeführte Mengenregression meldet 27 Fehler und 13 bestandene Teilprüfungen. Unter anderem gehen zusammengesetzte Typbezeichnungen und qualifizierte Controllerbezeichnungen verloren. Die 13 Ergebnisse sind keine bestandenen Gesamtszenarien.','',
'2. **Auftragserkennung:** S01-A wird als Funktionserzeugung für bereits ausgewählte Hardware behandelt. Der genannte Raspberry Pi führt nicht zum angeforderten Gesamtentwurf; stattdessen wird manuelle Hardwareanlage verlangt.','',
'3. **Werkzeugaufrufe:** S02-A und S05-A enthalten `new_hardware` als Zeichenkette statt Objekt. S03-B fragt erfundene Kennungen wie `uuid_4` ab. Die Backendvalidierung weist diese Aufrufe zurück; der Agent liefert anschließend keine brauchbare Reparatur oder gezielte Fachfrage.','',
'4. **Freigabe des Geräteumfangs:** S03-A zeigt nur ein Gateway und null Controller/Sensoren/Aktoren, obwohl die Eingabe diese ausdrücklich nennt. Trotzdem ist „Übernehmen“ aktiv. Das ist noch keine Übernahme ins kanonische Modell, aber eine fehlerhafte Freigabe der Vorstufe.','',
'5. **Antwortlimit:** S02-B und S06-A enden an der HTTP-Grenze von etwa 290 Sekunden mit einer allgemeinen Fehlermeldung. Die Zeitangaben unten beruhen auf den Zeitstempeln der unmittelbar vor/nach dem HTTP-Aufruf gespeicherten Dateien.','',
'6. **Nicht belegte Berechnungswerte:** S08-A nennt 5,12 % Modbus-Buslast nach mehreren fehlgeschlagenen Netzwerkaufrufen. Der gespeicherte Zustand hat leere Parameter, keine Analysen und keine Modellobjekte. Der Wert ist damit kein nachgewiesenes Ergebnis des Simulators.','',
'## Umsetzungsvorschläge aus dem Befund','',
'- Zuerst Mengen, Gerätefunktion und Technologie getrennt aus der vollständigen Anforderung erfassen; Compound-Namen, englische Typnamen und Gruppenlisten als Regression aufnehmen. Unaufgelöste Geräte bleiben mit ihrer genannten Anzahl sichtbar.','- Projektanlage und Einzelobjektbearbeitung anhand des Auftrags und des vorhandenen Modells unterscheiden. Ein neuer Gesamtentwurf darf keine vorhandene ausgewählte Hardware voraussetzen.','- Werkzeugargumente strikt typisiert erzeugen und vor Ausführung prüfen. Nach einem Fehler muss der Agent den konkreten Aufruf korrigieren oder eine fachliche Frage stellen; interne Aufruffehler gehören nicht zum Nutzerauftrag.','- Freigabe gegen die ursprünglichen Sollmengen und Rollen prüfen, nicht ausschließlich gegen bereits verkleinerte Parserergebnisse.','- Freie Agentenaufträge als fortsetzbare Arbeitspakete mit gespeicherten Ergebnissen führen. Danach dieselben 40 Fälle erneut prüfen und erst anschließend Routing, Capacity/Timing, Simulation und Trace vollständig abnehmen.','',
'- Numerische Engineering-Ergebnisse an erfolgreiche Berechnungsartefakte der passenden Modellrevision binden. Fehlgeschlagene Werkzeugaufrufe dürfen nicht als Beleg einer Berechnung dienen.','',
'## Matrix','',
'| Fall | Architektur laut Quelle | Befund | Parser: ausdrücklich genannte Mengen | Agentzeit | Übernehmen aktiv |',
'|---|---|---|---|---|---|']
for r in rows:
    lines.append(f'| {r["test_id"]} | {r["architecture"]} | {r["outcome"]} | {"; ".join(r["parser_count_findings"]) or "Keine Abweichung der geprüften Mengen; keine Gesamtfreigabe"} | {r["agent_seconds"] if r["agent_seconds"] is not None else "—"} s | {r["summary"].get("adopt_enabled", "—")} |')
lines+=['','## Bewertungsgrenzen','',
'Die Mengenprüfung unterscheidet Hardware-Gateway und abstrakte zentrale Kopplung: Letztere wird in B nicht automatisch als Gateway vorausgesetzt. Bei Robot/Edge/Industrial-PC bleiben nicht eindeutig gleichzusetzende Controllerkategorien in dieser Zahlenprüfung unbewertet. S17 nennt ausdrücklich zehn Smart Sensor Nodes und zwei Edge Controller beziehungsweise Edge-Rechner; diese Mengen werden als Sensoren und Controller geprüft. Die übrigen Source-Anforderungen bleiben im vollständigen Manifest erhalten.','',
'PARTIAL in den Tool-Checker-Rohläufen bedeutet fehlende Pflichtnachweise, nicht fachlich bestanden. Die Matrix oben ergänzt die semantische Bewertung der beobachteten Parser- und Agentenfehler.','',
'## Einzelantworten und Belege','']
for r in rows:
    directory=Path(r['evidence_dir'])
    links=' · '.join(f'[{label}]({(directory/name).as_posix()})' for name,label in [('agent-events.json','Originalantwort'),('wizard.png','Wizard-Screenshot'),('after.json','Modellzustand')] if (directory/name).exists())
    lines += [f'### {r["test_id"]} – {r["title"]}', '',r['agent_text'] or 'Agentenantwort noch ausstehend.', '',links or 'Noch keine Hauptlauf-Nachweise.','']
review=['## Ergänzende Persistenz- und Fortsetzungsprüfung','',
'Alle 40 Hauptfälle wurden tatsächlich angestoßen. Die Originalblöcke aus der Datei wurden unverändert als Benutzerauftrag gesendet; die übergeordneten Qualitätsregeln dienen als Prüforakel und wurden nicht zusätzlich als Systemprompt injiziert. Das ist eine Prüfung des vorhandenen Agentenverhaltens, kein Training.','',
'**Offene Entscheidungen:** Der Nutzer hat für S07-B ausdrücklich CAN-FD für Echtzeit und Ethernet für große Daten gewählt. Weitere Architekturentscheidungen bleiben auf ausdrücklichen Nutzerwunsch offen. In S02-B, S06-A, S08-B, S09-B, S11-B und S17-B wurden nach dem HTTP-Timeout dennoch Fragen gespeichert. Das ist kein erfolgreicher Chatabschluss; es belegt eine Abweichung zwischen sichtbarer Antwort und dauerhaftem Zustand. Die Fragen sind in den jeweiligen `conversation.json` erhalten.','',
'**Widersprüchliche Auswahl:** S08-B empfiehlt „3 lokale Cluster“, beschreibt dabei aber vier lokale Steuerungen mit jeweils eigenem Cluster. Diese Auswahl wurde nicht übernommen.','',
'**Auftragszerlegung S19-A:** Der gespeicherte Workload fordert nur 20 thermische Signalobjekte, statt den Gesamtauftrag mit 100 Sensoren, 100 Aktoren und 50 Controllern in passende Pakete zu zerlegen. Er ist mit `INSUFFICIENT_DOMAIN_KNOWLEDGE` blockiert (10 Katalogsignale gegenüber 20 angeforderten).','',
'**Rückfrageschleife S07-B:** Die bestätigte Auswahl steht unter `answered_questions.robot_bus_strategy`. Die Fortsetzung erzeugt eine neue offene Frage mit demselben Entscheidungsschlüssel und derselben empfohlenen Option. Die bereits beantwortete Entscheidung wird nicht wirksam für den nächsten Schritt verwendet.','',
'## Abdeckung der geforderten Qualitätsmetriken','',
'| Metrik | Tatsächlich belegter Stand |','|---|---|',
'| Typisierung / Geräteklassifikation | Mengenregression 13 bestanden, 27 fehlgeschlagen; keine vollständige Typing-Accuracy berechnet |',
'| Bestehende Objekte wiederverwenden / Duplikate | Hauptfälle starten leer; Wiederverwendung nicht vollständig geprüft |',
'| Architektur / Technologien / Ports | Erste Vorschläge und Parserbefunde geprüft; keine vollständige Architekturvalidierung |',
'| Richtige / unnötige Fragen | Gespeicherte Fragen geprüft; wiederholte beantwortete Frage und widersprüchliche Option belegt; weitere Entscheidungen bleiben offen |',
'| Routing / Transport | Vollständigkeit nicht erreicht |',
'| Capacity / funktionales Timing | Keine erfolgreiche Endprüfung; unbelegte Zahlen in S08-A |',
'| Blocking Findings / Completion | Werkzeugfehler, blockierter Workload, Teilvorschläge und leeres Modell geprüft |',
'| Erfundene Objekte | Platzhalterkennungen und Mengen als Objekt-IDs beobachtet; keine pauschale Fehlerquote behauptet |',
'| Simulation / Trace | Nicht erreicht; kein neunphasiger E2E-PASS |','',
'Die HTTP-Zeitgrenze und lokale Inferenzleistung gehören zu den Testbedingungen. Ein Timeout allein beweist keinen domänenspezifischen Rechenfehler. Die belegten Schema-, Mengen-, Zustands- und Auftragsfehler werden davon getrennt bewertet.','',
'## Fortsetzungen gültiger Teilvorschläge','']
for r in rows:
    follow=Path(r['evidence_dir'])/'continuation'
    if not (follow/'finished.json').exists():continue
    status=r['claim_checks'].get('continued_proposal',{}).get('data',{}).get('status','Entscheidungsantwort')
    changes=r['claim_checks'].get('continued_proposal',{}).get('data',{}).get('changes',[])
    details='; '.join(f'{c.get("object_type")}: {c.get("data",{}).get("name")}' for c in changes)
    review += [f'- {r["test_id"]}: {status}. {details} [Fortsetzungsnachweise]({(follow/"observations.json").as_posix()}).']
    for e in r['claim_checks'].get('continuation_events',{}).get('events',[]):
        e=e.get('data',e)
        if e.get('type') in ['RESULT','ERROR','error','SINGLE_SELECT','QUESTION']:
            content=max([str(e.get('text',e.get('errorText','')))]+[str(o.get('content','')) for o in e.get('outputs',[])],key=len)
            review += ['',content,'']
index=lines.index('## Einzelantworten und Belege');lines[index:index]=review+['']
if (out/'cleanup.json').exists():
    lines += ['','## Abschluss und Testumgebung','',
    'Die zwei eigens angelegten Testcontainer sowie ihr Testnetz und Runtime-Volume wurden nach Prüfung der Wegwerf-Labels entfernt. Vollständige Workflow-Snapshots, Gesprächszustände, Screenshots, HTTP-Antworten und Containerlogs bleiben lokal erhalten. Produktcontainer und Produktdaten wurden nicht verändert. Offene Testentscheidungen wurden nicht automatisch beantwortet.','',
    'Die formalen Tool-Checker-Läufe bleiben PARTIAL, weil die vollständigen Abschlusskriterien nicht nachgewiesen sind. Die semantische Matrix weist zusätzlich die belegten Fehler aus. Weder PARTIAL noch eine bestandene Mengenprüfung gilt als Freigabe. Es wurden keine Produktkorrekturen implementiert oder ausgerollt.','',
    f'[Bereinigungsnachweis]({(out/"cleanup.json").as_posix()}) · [Mengenregression]({(out/"parser-tests.tap").as_posix()}) · [Maschinenlesbare Ergebnisse]({(out/"industry40-results.json").as_posix()})']
(out/'industry40-report.md').write_text('\n'.join(lines).replace('Die laufende Hauptmatrix','Die Hauptmatrix'),encoding='utf-8')
print(json.dumps(dict(counts),ensure_ascii=False))
