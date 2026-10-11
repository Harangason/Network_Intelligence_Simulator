from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path.cwd()))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as r
from backend.communication.technologies.core.components import validate_parameter_rule_syntax
rows=[]
for p in r.profiles():
 validate_parameter_rule_syntax(p)
 fields=r.parameter_fields(p['id'])
 rows.append({'technology':p['id'],'layer':p['layer'],'fields':len(fields),'constraints':len(p.get('parameter_constraints')or[]),'wide_integers':[f['key']for f in fields if f.get('numeric_encoding')=='DECIMAL_STRING'],'capacity':p['capacity_evidence']['status'],'default_stack':p['default_stack']})
folder=Path('docs/implementation-workloads/technology-full-parameter-audit-20261001')
(folder/'consumer-schema-inventory.json').write_text(json.dumps({'scope':'125 profile schemas and rule vocabulary; parameter semantics refer to individual source reviews, no hardware certification','profiles':rows,'total_fields':sum(x['fields']for x in rows),'total_constraints':sum(x['constraints']for x in rows),'production_delivered':False,'release_gate':'PENDING'},indent=2)+'\n',encoding='utf-8')
(folder/'consumer-findings.md').write_text('''# Gemeinsame Datenwege nach den Einzelprüfungen

- Die Registry ist die Quelle für 125 Profile, 14.133 Editorfelder und 24.138 Regeln. Unbekannte Regeloperatoren, Schlüssel und nicht skalare Bedingungen werden vor der Registrierung abgewiesen. Die detaillierte Inventarliste steht in consumer-schema-inventory.json.
- Fehlende tatsächliche Stack-Konfiguration bleibt unbestätigt. Insbesondere fordert eine noch nicht konfigurierte IP-Schicht keine beliebige Ethernet-Frequenz; NMEA 2000 behält sein eigenes CAN-basiertes Profil.
- Große Integerwerte werden als Dezimaltext im Browser gelesen, bearbeitet, mit identischer Provenance gespeichert und erneut geladen. Die zentrale Python-Prüfung verwendet exakte Ganzzahlen für Integerabhängigkeiten und weist bereits gerundete unsichere Floatwerte zurück.
- Bedingte Literaturvorschläge berücksichtigen bekannte Voraussetzungen und Abhängigkeiten in beliebiger Schema-Reihenfolge. Bestätigte tatsächliche Werte bleiben bestehen. Fehlende Adressen, Verkabelung, Slave-/Controlleridentität, Transaktionsumfang und gemessene Verzögerungen werden nicht erfunden.
- Geräteanschlüsse nutzen profilgebundene lokale Evidence und die Unterscheidung Controller-Port / Target-Port / Transaktion. Die vollständige Kapazitätsprüfung verlangt weiter tatsächliche, bestätigte Quellen; eine Standardfrequenz ist kein Kapazitätsnachweis.
- M-Bus, Matter, MIL-STD-1553 und weitere Profile ohne ausführbaren PHY-/Schedule-/Security-Pfad bleiben MODEL_MISSING. Native Parametersemantik oder ein Textverweis installiert keinen Executor. Die Verbraucher weisen fehlende Modelle aus; ein CAN-/Ethernet-Ersatz ist unzulässig.
- Simulation und Trace verwenden denselben kanonischen Snapshot, Scope und Technologie-Nachweis wie Kapazität und Preflight. Die vollständige Prüfung dieser Integration erfolgt im Release-Gate einschließlich echter isolierter Neuanlage, Änderung, persistierter Simulation, Neustart und großer Referenzanforderung.
- Der genaue Satz „ein Aktor zum proportional schließen eines Ventil“ erzeugt einen konkreten Ventilaktor auch im Backend. Die vorhandene Frontend-Regressionsprüfung desselben Wortlauts bleibt erhalten. Anschluss und Hardwarefähigkeiten werden damit nicht automatisch bestätigt.
- README.md beschreibt alle registrierten Verbindungstypen nach Protokollschichten. Branchen sind Empfehlungen und Vorlagen; die Technologieauswahl bleibt vollständig und neutral. MODEL_MISSING, PARTIAL und EXPERIMENTAL werden fachlich erklärt.

## Abnahmestatus

Die Einzelprüfungen und die Quellenkorrekturen sind dokumentiert. Die gemeinsame vollständige Abnahme und exakte produktive Übernahme sind bis zum vorhandenen PASS-/Deployment-Nachweis offen. Einzeltests und diese Inventarliste allein sind kein neunphasiger E2E-PASS.
''',encoding='utf-8')
print({'profiles':len(rows),'wide_fields':sum(len(x['wide_integers'])for x in rows)})
