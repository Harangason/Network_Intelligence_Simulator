# Automatische vollständige Auswertung großer Dokumente

Die Grenze von acht Auswertungsabschnitten entfällt. Jeder Abschnitt behält das bestehende lokale Qwen-Kontextfenster sowie die Grenzen für Quellenbefunde und Ausgabe. Nur zu dichte Abschnitte werden weiter zerlegt. Originalzeichen, Reihenfolge, Unicode und Quellhashes bleiben erhalten.

Die Aufnahme unterstützt durchgängig bis zu einer Million Unicode-Zeichen. Die vorhandene Dateigrößengrenze bleibt bestehen. HTTP erlaubt dazu einen begrenzten JSON-Umschlag, einschließlich Unicode-Escapes. Größen-/JSON-Fehler belegen keinen KI-Arbeitsplatz.

Die Gesamtprüfung verwendet denselben Quellen- und Semantikvalidator mit einer vollständigen Befundsammlung. Einzelaufrufe bleiben begrenzt; mehr als 60 Geräte-/Funktions-/Anforderungsbefunde und 32 Technologieangaben können in der Summe erhalten bleiben. Quellenprüfung, lokaler Provider, ausdrücklicher Start, menschlicher Review, Projekt-/Quellbindung und fehlende Schreibautorität bleiben bestehen. Ein später Fehler liefert keinen vollständigen Erfolg.

Validierung und Produktivstatus sind im workload.json, den Testberichten, der nativen Originaldateiauswertung und dem Release-Receipt dokumentiert. Ein laufender Check oder eine sichtbare Fortschrittsmeldung ist kein PASS.
