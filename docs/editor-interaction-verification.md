# Netzwerk-Editor: Bedienung und Buswechsel

Stand: 10.09.2026, Build `fab70713680f`.

- Freie Zeichenfläche mit gedrückter linker Maustaste ziehen: horizontales und vertikales Scrollen. Geräte, Gruppen, Anschlüsse und deren gespeicherte Positionen bleiben davon unabhängig.
- Generierte Backbone-Namen erscheinen als `Antriebsstrang_01`, `Antriebsstrang_02`; senkrechte Beschriftung ist von rechts lesbar. Technische IDs bleiben stabil.
- Doppelte Endpunkte in SVG-Pfaden werden entfernt. Bidirektionale Pfeilspitzen sind kleiner und von Knotenpunkten abgesetzt.
- Der Verbindungsdialog verwendet einen Bustyp-Dropdown und kurze Anschlussnamen. Er zeigt die Auswirkungen auf gekoppelte Busse, Geräte, Nachrichten und Routen vor dem Speichern an. Bei kleiner Fensterhöhe ist sein Inhalt scrollbar, die Schaltflächen bleiben erreichbar.
- Ein Buswechsel aktualisiert physische Anschlüsse, logische Schnittstellen, Transportverträge, Signalbindungen, Busparameter, Topologie, Relations und Routing in einer Transaktion. Mehrfach gesendete Nachrichten ziehen alle zugehörigen Busse in die Vorschau ein. IDs und Signalbedeutung bleiben erhalten.
- Unpassende Payload-Größen werden abgewiesen. Veraltete Vorschauen werden durch einen Fingerprint erkannt. Bestehende Kanalnummern und Busnamen werden bei der Vergabe berücksichtigt. Gemeinsame Anschlüsse behalten in allen Verbindungen denselben Namen.
- Routing verwendet den gespeicherten Bustyp, auch wenn eine stabile technische ID noch den früheren Bustyp enthält. Geänderte Routen werden erneut validiert und müssen erneut freigegeben werden.

## Nachweise

73 Backend-Tests und 220 Frontend-Tests bestanden; Produktionsbuild einschließlich TypeScript-Prüfung erfolgreich.

HTTP-Test auf einer isolierten Projektkopie: zwei gekoppelte Busse, vier Geräte, vier Nachrichten und fünf Routen umgestellt; IDs unverändert; erneut freigegeben. Ein absichtlich ungültiger Beziehungstyp nach Beginn der Modelländerung führte zum vollständigen Rollback. Eine veraltete Vorschau wurde mit HTTP 409 abgewiesen.

Browser-Test: 300 Pixel horizontal und 150 Pixel vertikal verschoben, gespeicherte Topologie unverändert. Dropdown-Wechsel zurück auf LIN durchgeführt und anschließend anhand gespeicherter Daten geprüft; fünf Routen erneut freigegeben. Falsche Rückänderungsvorschläge nach einem Technologiewechsel sind behoben.

Testdaten und Ergebnisse: `docs/editor-bus-change-acceptance.json`; reproduzierbarer HTTP-Test: `scripts/verify-editor-bus-change.py`. Der Test arbeitet ausschließlich in `editor-bus-acceptance-20260910`. Das Originalprojekt wurde für den Buswechsel nicht verändert; seine Zeichnungsansicht wurde auf Szenenversion 3 aktualisiert, ohne Modellversionen oder manuelle Positionen zu ändern.
