# Busanschluss innerhalb eines Clusters umhängen

Im Netzwerk-Editor öffnet ein Doppelklick auf eine Verbindung den bestehenden
Verbindungsdialog. **Bus umhängen …** öffnet die Geräte- und Zielbusauswahl.
Die Zielbusse sind alphabetisch mit numerischer Sortierung angeordnet.

Der Wechsel betrifft den physischen Anschluss des gewählten Geräts. Als Ziele
werden andere Busse desselben Typs und Clusters angeboten. Bei lokalen Bussen
muss außerdem der Systemrahmen übereinstimmen. Bustypänderungen bleiben über
das separate Feld **Bustyp** möglich.

Vor dem Speichern prüft der Server Teilnehmergrenzen, Anschlüsse, Nachrichten-
kennungen und Kommunikationspfade. Die Vorschau nennt betroffene Nachrichten
und Routen. Vorschau- und Bearbeitungstoken verhindern das Speichern auf Basis
veralteter Daten. Noch nicht gespeicherte Änderungen im Verbindungsdialog
müssen zuerst übernommen werden.

Die bestehende SQL-Transaktion für Netzwerkzuordnungen übernimmt Anschluss,
Nachrichtenbindungen, Routenversionen, Modellbeziehungen und gespeicherte
Ansicht gemeinsam. Geänderte Routen werden validiert und zur erneuten Freigabe
bereitgestellt. Ein Fehler rollt die gesamte Änderung zurück. Fachliche
Zuordnungen und interne Busse eines umgehängten Steuergeräts bleiben erhalten.
Multicast-Befehle an lokale Empfänger werden bei Bedarf in Routen für die
jeweiligen physischen Busse aufgeteilt; die gemeinsame Nachricht bleibt erhalten.

## Prüfung am 10. September 2026

- 234 Frontendtests erfolgreich.
- 72 Backendtests für Buswechsel, Systemzuordnung, Netzwerkansicht, Bustypwechsel,
  physische Anschlüsse und Routingkonsistenz erfolgreich.
- SQL/API-Integrationstest in einem separaten `pytest-*`-Projekt erfolgreich:
  veraltete Vorschau abgewiesen; erzwungener Fehler nach den SQL-Schreibvorgängen
  vollständig zurückgerollt; erfolgreicher Wechsel nach Neuladen vorhanden;
  geänderte Route anschließend erneut freigegeben; Wiederholung mit altem
  Bearbeitungstoken abgewiesen.
- 23 Tests einschließlich dieses Integrationstests nochmals im finalen
  laufenden Container erfolgreich (überlappen mit den oben genannten Tests).
- Produktionsbuild einschließlich TypeScript-Prüfung erfolgreich.
- Browserprüfung im Build `64b4bb82808b`: Fahrersitz bietet den Wechsel von
  `Karosserie_Komfort_02` nach `Karosserie_Komfort_01` an. Vorschau: eine
  Nachricht und eine Route. Abbruch ohne Änderung der Verbindung geprüft.

Im Benutzerprojekt wurde kein Busanschluss durch diese Prüfung umgehängt.
