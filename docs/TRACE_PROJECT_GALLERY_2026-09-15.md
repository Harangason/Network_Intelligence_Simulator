# Projekteinstieg fuer Trace-Analyse

`Start Trace Analyse` oeffnet `/trace-projects`. Die Seite verwendet dieselben
gespeicherten Projekte wie die Simulator-Uebersicht und bietet Suche, kurze
Projektinformationen, Aenderungsdatum und die vorhandene Projektloeschung.
Projektkacheln oeffnen `/trace-analysis` mit der richtigen Projekt-ID.

Die Plus-Kachel erzeugt persistent ein `Neues Trace-Projekt` und oeffnet den
vorhandenen Trace-Arbeitsbereich zum Laden eigener Dateien. Dabei wird kein
Engineering-Wizard angefordert. Bei einer fehlgeschlagenen Anlage verwendet
der erneute Versuch dieselbe Projekt-ID. Die bestehende Simulator-Plus-Kachel
oeffnet weiterhin den Engineering-Wizard.

Der `Open studio`-Button wurde aus der gemeinsamen Marketing-Navigation
entfernt. Die uebrigen inhaltlichen Einstiege bleiben bestehen.

Gezielte Browserpruefung: drei Tests bestanden, darunter persistierte
Trace-Projektanlage, Oeffnen vorhandener Projekte, Neuladen, schmale Ansicht
sowie der bestehende Simulator-Einstieg und Animationen. Keine erfolgreichen
Schreibantworten wurden gemockt. Die bestehende lokale Trace-Importvorschau
wurde durch diese Navigationsaenderung nicht um eine Dateipersistenz erweitert.

Vollstaendige Release-Pruefung `5e16fad573de`: PASS. TypeScript,
341 Frontend-Tests, 1655 Backend-Tests (3 uebersprungen), 23 Browserfaelle
sowie kleine und grosse HTTP-Durchlaeufe sind bestanden.
Das exakt getestete Image
`sha256:4aad01f3efc0906926fb4a5be9ae9fedb67a79bab3c2b26ce6c6503f0c5eaa54`
wurde bereitgestellt. Alle 18 Nachpruefungen zu Identitaet, Erreichbarkeit,
Speicher und Einstellungen sind PASS. Die fuenf bestehenden Projekte mit
5025 kanonischen Modelldatensaetzen sind unveraendert.
