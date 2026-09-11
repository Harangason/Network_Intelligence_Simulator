# Kommunikationsführung nach Änderungen im Netzwerkeditor

## Ergebnis

Der Reparatur-Agent in Engineering und Routing vergleicht die bisher gespeicherte
Kommunikationsführung mit der aktuellen physischen Verkabelung. „Neue Führung
übernehmen“ aktualisiert die betroffenen Nachrichtenbindungen und Routing-Einträge.
„Alte Führung wiederherstellen“ stellt eine aus der Anschlusshistorie belegbare
Systemanbindung tatsächlich wieder her und berechnet auch deren weitere betroffene
Routen neu. „Später entscheiden“ speichert keine Reparatur.

Die Vorschau enthält den bisherigen und künftigen Weg je Route. Die Auswahl gilt
nur für den geprüften Projektstand; bei zwischenzeitlichen Änderungen ist eine neue
Vorschau erforderlich. Veraltete Revisionen derselben Route werden nicht als weitere
aktive Kommunikation wiederhergestellt.

## Geprüftes Projekt

Quelle: `network-project-20260910042736034-d11591d0`, Stand 11.09.2026.
Die Live-Daten wurden nur gelesen. Beide Strategien wurden jeweils auf einer eigenen
Projektkopie in der separaten Datenbank `nis_bus_naming_tests` angewendet.

| Entscheidung | Routen | Nachrichtenbindungen | Zusätzliche Änderung |
| --- | ---: | ---: | --- |
| Neue Führung, erste Variante | 7 | 4 | Gerichtete Ethernet-Weiterleitung auf Fahrerassistenz bestätigen |
| Frühere Systemanbindung | 118 | 46 | Frühere Anschlüsse auf ETH_Fahrerassistenz_03; zusätzlichen Systemkanal planen |

Kamera, Radar und Ultraschall sind jetzt im lokalen Ethernet verbunden. Für die
weiterhin beabsichtigte Kommunikation zur Diagnose muss Fahrerassistenz zwischen
seinen beiden Ethernet-Anschlüssen weiterleiten. Die konkrete Richtung und beide
Port-/Netzwerkidentitäten werden im Modell bestätigt; der Gerätetyp bleibt ECU.
Diese Entwicklungsanforderung ersetzt keine Hardware-, Kapazitäts- oder Timingprüfung.

Die Wiederherstellung verändert einen Anschluss, den viele weitere Nachrichten
verwenden. Deshalb betrifft sie 118 aktuelle Routen. Der ursprüngliche Gatewaykanal
ist nicht mehr vorhanden; der Vorschlag legt dafür einen zusätzlichen Kanal an und
speichert dessen Ressourcenstatus als `PLANNING_REQUIRED` in den Port-Capabilities.

## Konsistenz und Prüfung

- Funktionen, logische Kommunikationsschnittstellen, Empfänger, Signaldefinitionen,
  Frame-IDs, DLC, Zykluszeiten, Payload und Routing-Policies bleiben erhalten.
- Gespeicherte physische Pfade referenzieren konkrete Ports und Leitungen. Eine
  entfernte Leitung wird auch dann erkannt, wenn ein anderer Weg noch erreichbar ist.
- CAN/LIN-ID-Kollisionen verhindern die Reparatur. Es erfolgt keine Umnummerierung.
- Alle Änderungen einschließlich neuer Ports und bestätigter Weiterleitungen werden
  gemeinsam zurückgerollt, wenn die abschließende Validierung scheitert.
- Geänderte Routen erhalten `PENDING` und benötigen eine neue Freigabe. Frühere
  Freigabebeziehungen werden entfernt; Folgebewertungen werden veraltet markiert.

Tests: 61 lokale Routing-/Reparaturtests bestanden, 3 SQL-Tests dort ausgelassen;
alle 18 Reparaturtests einschließlich der SQL-Tests in der separaten Datenbank
bestanden. Beide vollständigen Projektkopien anschließend ohne offene Reparaturfälle.
Zusätzlich geprüft: Rückrollen beider Strategien nach absichtlich gescheiterter
Validierung, Ablehnung veralteter Vorschauen und erneute Fehlererkennung nach
Widerruf einer Weiterleitungsbestätigung.

Die Browserprüfung auf dem lokalen Produktionsbuild ist ebenfalls bestanden:
echte Vergleichsdaten mit 7 bzw. 118 Routen, beide Auswahlaktionen, erneutes Laden
der Engineering- und Routing-Tabellen, Aufschieben ohne Änderung und Behandlung
einer veralteten Vorschau. Das Benutzerprojekt blieb dabei unverändert. TypeScript
und der Next.js-Produktionsbuild sind erfolgreich.

Reproduzierbare Prüfungen:

- `backend/tests/test_communication_repair.py`
- `scripts/run_repair_sql_isolated.py` / `scripts/verify_communication_repair_sql.py`
- `frontend/scripts/verify-communication-repair.mjs`: echte Vorschauen, kontrollierte
  Browser-Schreibantworten; keine Reparatur im Benutzerprojekt.
