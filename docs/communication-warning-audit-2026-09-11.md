# Kommunikationswarnungen im Engineering-Modell

## Fehlerursache

Eine gespeicherte Routenfreigabe wurde bislang auch dann angezeigt, wenn der
konkrete physische Anschluss inzwischen abgetrennt war. Die Pfadsuche konnte
einen anderen Anschluss desselben Geräts als erreichbar finden. Beim Entfernen
einer Verbindung wurden außerdem nur die auf der Zeichenkante hinterlegten
Routen-IDs berücksichtigt; direkte Anschlussreferenzen anderer Routen fehlten.

Konkreter Fall: `RT-D81ECD53` (Kameraverarbeitung → Diagnose) verwendet den
Anschluss `855be640-5954-4204-ab97-ddbbc36af69c`, dessen `network_ref` leer ist.
Die Nachricht Kameraverarbeitung verweist ebenfalls auf diesen Anschluss.

## Umsetzung

- Alle sechs Objekttabellen bis einschließlich Signale besitzen unmittelbar
  nach Beschreibung die Spalte **Warnung**. Das Dreieck öffnet die Ursachen,
  die betroffenen Felder und die zugehörige Nachricht beziehungsweise Route.
- Ein gemeinsamer Abgleich prüft die aktuellen kanonischen Anschlüsse,
  Busreferenzen, Zeichnungsverbindungen, Eigentümer und Routenreferenzen.
  Anzeigenamen und gespeicherte Freigaben ersetzen keine Verknüpfung.
- Hinweise folgen Nachricht → Schnittstelle → Funktion → Hardware sowie den
  tatsächlich betroffenen Signalen. Bei einer nur teilweise gerouteten
  Signalauswahl werden andere Signale nicht durch den Routenfehler markiert.
  Ein fehlerhafter Nachrichtenanschluss betrifft hingegen alle enthaltenen
  Signale. Der Strukturbaum nutzt denselben Abgleich.
- Die Routenvalidierung kontrolliert den ausgewählten kanonischen Kanal und
  dessen aktuelle Buszuordnung. Das Entfernen eines Anschlusses oder einer
  Busmitgliedschaft findet auch Routen über ihre Endpunktreferenzen und setzt
  sie auf OUTDATED/PENDING. Weiter verbundene Zeichenport-Aliase bleiben gültig.

Dies ist eine Konsistenzprüfung des aktuellen Kommunikationsentwurfs, kein
Nachweis tatsächlich übertragener Laufzeitdaten oder funktionaler Timing-Eignung.
Signaldefinitionen, Zykluszeiten und physische Zuordnungen werden dabei nicht
automatisch geändert. Ein Strich in der Warnspalte bedeutet keine umfassende
Freigabe. Nach einer Korrektur werden abgeleitete Warnungen neu ermittelt;
gespeicherte fehlerhafte Routenbewertungen benötigen weiterhin eine Revalidierung.

## Prüfung im Projekt NIS Projekt 1

Zum Prüfzeitpunkt betroffen: 9 Hardware-Knoten, 11 physische Anschlüsse,
5 Funktionen, 6 Kommunikationsschnittstellen, 4 Nachrichten und 20 Signale.
Beim Kamerabeispiel erscheinen die Hinweise bei der Funktion, Schnittstelle,
Nachricht und allen fünf enthaltenen Signalen.

- Unit-Tests: Weitergabe, gesunde Nachbarn, selektive Signalnutzung, aktuelle
  Buszuordnung trotz anderer erreichbarer Anschlüsse, Auflösung von Port-IDs.
- PostgreSQL-Tests in einer separaten Testdatenbank: Löschen, erneutes Verbinden,
  Transaktions-Rollback sowie Invalidierung über Quell- und Zielanschlüsse.
- Browserprüfung: alle sechs Tabellen, Spaltenreihenfolge, Filter, Dialog,
  Schließen per Escape, Strukturbaum und unverändertes Projektmodell.
- Produktionsbuild einschließlich TypeScript-Prüfung erfolgreich.

Wiederholbare Browserprüfung:
`frontend/scripts/verify-communication-warnings.mjs`.
