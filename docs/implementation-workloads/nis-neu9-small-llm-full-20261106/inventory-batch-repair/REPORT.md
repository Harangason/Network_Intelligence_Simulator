# Begrenzte Quelleninventar-Bündel und belastbarer Fortschritt

## Ursache und Änderung

Der normale Referenzcursor forderte pro Antwort genau eine bereits bekannte ursprüngliche Geräteidentität an. Auch vollständig aufgelöste Instanznamen liefen dadurch seriell einzeln. Der laufende Gesamtrequest 6618 wurde auf ausdrückliche Nutzerfreigabe regulär abgebrochen. Client-Exit1, normaler Serverstatus REFERENCE_CANCELED/CANCELED, tatsächliches Treiberende und freier Hauptworker sind getrennt belegt. Das ist kein nativer Modellfehler und keine Originalabnahme.

Jetzt fordert derselbe normale Pfad maximal acht exakt bestimmte ursprüngliche Namen an. Das private Ausgabeschema enthält jeden Namen als Pflichtschlüssel mit einer passenden NEW-Identität oder zulässigen EXISTING-Bindung. Öffentlicher Validator, unveränderliche Identitäten, Quellenbindungen, Mengen und Merge-Gates bleiben erhalten. Ungelöste Kategorien und funktionale Hardwareentscheidungen behalten ihre vollständige Fortsetzung. Der Mechanismus ist modellunabhängig; Modell, Kontextmaximum, Ausgabelimit und Timeout bleiben unverändert.

Der Fortschritt nennt bereits intern gebundene Quellgeräte, die tatsächliche Sollzahl und die angeforderte Bündelgröße. Er behauptet keine Modellfreigabe. Bei unbekannter Gesamtanzahl bleibt diese ausdrücklich offen.

Die angrenzende Regression deckte einen separaten Widerspruch auf: Explizite Typenlisten wie „Sensortypen (...)“ waren für die Pflichtgruppenvalidierung bekannt, hatten in der gemeinsamen Rollenpolicy aber keine entsprechende Kategorie. Die gemeinsame, verankerte Typenlistenregel klassifiziert jetzt solche Sensor-/Aktortypenlisten konsistent. Anforderungen, Funktionen, unbekannte Begriffe und explizite Mengen behalten ihre bisherigen Prioritäten. Keine bestehenden Testassertionen wurden abgeschwächt.

## Belege und Grenzen

- Erster red.xml: Importfehler bei Testaufbau; ausdrücklich kein Verhaltens-RED.
- red-behavior.xml: neun echte Fehler am vorherigen Ein-Gerät-Pfad; green.xml danach neun PASS.
- regression.xml: 182 PASS und fünf FAIL an derselben Typenlisten-Policy. Diese Originalfehlerdatei bleibt erhalten.
- progress-types-red.xml: 15 PASS und zwei neue FAIL; progress-types-green.xml: 22 PASS einschließlich aller fünf zuvor fehlgeschlagenen Fälle.
- Der normale Mock-Transport-Prüffall liefert 17 Quellsensoren in den Bündeln 8/8/1; Anzahl, Identität und Bindung bleiben vollständig.
- Echte Gegenprobe Session84425: llama3.1:8b, ein tatsächlicher Modellrequest, acht Geräte, normale Schema/Public/Scoped-Merge-Prüfung PASS, regulärer Exit0. 181,887 Sekunden Gesamtzeit, 261 Eingabetokens und 1048 Ausgabetokens. Hauptworker danach tatsächlich idle. Dies ist ein unabhängiger Gegenfall, kein Original- oder Simulationsnachweis und kein gemessener Original-Speedup.
- Finale kombinierte isolierte Regression Session5844 regulär Exit0: 596 PASS, keine Fehler oder übersprungenen Fälle, eine bestehende Pydantic-Namenswarnung, 1540,47 Sekunden. Freeze Session30674 regulär Exit0; source-scope-proof.json bindet Quell- und Verifikationsidentität.

## Lieferung

Original neu 9.txt und die ausdrückliche Ergänzung „25 LIN-Netze“ bleiben unverändert hashgebunden. Alle sieben Originalziele und sieben Prüfpflichten bleiben offen erhalten. Der bisherige PREPARED-Kandidat 3459083ad348 enthält diese Reparatur nicht. Nach vollständigen lokalen Prüfungen: exakte Quellenidentität einfrieren, obsolete eigene Diagnose-Ressourcen recoverbar archivieren und stilllegen, einmal neuen normalen Kandidaten vorbereiten, vollständige koordinierte native neu9-Prüfung bis gespeicherter ALL-Simulation, vollständiges Releasegate und exakte produktive Übernahme. Produktion enthält diese Änderung noch nicht.
