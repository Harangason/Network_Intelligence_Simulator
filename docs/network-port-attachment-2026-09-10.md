# Ports und Buslinien verbinden

## Ursache

Der Netzwerk-Editor suchte beim Loslassen ausschließlich ein Port-Element und erlaubte nur zwei unbenutzte Ports. Das Ziehen eines angeschlossenen Ports wurde automatisch als Verschieben behandelt. Buslinien waren ausschließlich Layout-Griffe und wurden nicht als Verbindungsziele geprüft.

Ein bereits gespeicherter freier Port besitzt außerdem einen echten Hardwarekanal mit einer vorläufigen Netzbindung. Beim Anschluss an ein bestehendes Netz erzeugte die bisherige Materialisierung einen weiteren Kanal, statt diesen Anschluss neu zu binden.

## Umsetzung

- Port auf passenden Port, Busstamm oder Busabzweig ziehen. Auch ein angeschlossener Port darf eine Verbindung zu einem freien Anschluss beginnen. Passende Ziele werden hervorgehoben; die Trefferfläche bleibt bei unterschiedlichen Zoomstufen in Bildschirmpixeln ausreichend groß.
- Buslinie auf einen freien Port ziehen verbindet in umgekehrter Richtung. Beim Ablegen außerhalb eines Ports bleibt die bestehende Linienverschiebung erhalten. Die vorläufige Linienbewegung wird bei einer Verbindung verworfen.
- Umschalt+Ziehen versetzt weiterhin einen Port. Ein einfacher Klick erzeugt keine Verbindung.
- Loslassen öffnet den Beziehungsdialog mit Quelle, Ziel und Zielbus. Erst „Beziehung übernehmen“ speichert. Abbrechen und Escape während der Geste verwerfen die Vorschau.
- Bustypen müssen übereinstimmen. Doppelte Busmitgliedschaft, Selbstverbindungen und das Zusammenführen bereits verdrahteter separater Netze werden abgewiesen. Zum Umhängen bestehender Verbindungen bleibt der vorhandene Dialog „Bus umhängen“ zuständig.
- Der bestehende kanonische Speicherpfad synchronisiert Topologie und Beziehungen. Ein zuvor isolierter Port behält Hardware-Interface-ID, Kanalnummer und physischen Anschluss; nur seine Netzbindung wechselt. Aliase und bereits gemeinsam belegte Netze fallen nicht unter diese Wiederverwendung. Die Entscheidung verwendet den vorherigen gespeicherten Projektstand.

## Verifikation

- Frontend: 11 Tests für Verbindungsplanung, getrennte Busse, Duplikate, Liniengeometrie und Kreuzungen erfolgreich; TypeScript und Produktionsbuild erfolgreich.
- Backend: 12 lokale Tests erfolgreich. Zusätzlich zwei Tests in einer separaten PostgreSQL-Datenbank: echte API-Speicherung und Neuladen; absichtlich ausgelöster Fehler nach SQL-Schreibvorgängen rollt Topologie und Hardwarekanal vollständig zurück.
- Browser mit eigenem Testprojekt: Port → Bus, Bus → Port, belegter Port → freier Port, Busabzweig als Ziel, falscher Typ, doppelte Verbindung, Abbrechen, Speicherfehler und Wiederholen, Kanalidentität und Neuladen erfolgreich. Linienverschiebung und Umschalt+Portverschiebung bleiben reine Layoutänderungen. Keine Browserfehler.
- Schreibgeschützte Prüfung des großen Nutzerprojekts: Der Sensor „Test“ ist im zum Prüfzeitpunkt gespeicherten Stand bereits an Fahrerassistenz CAN FD angeschlossen. Ein erneutes Ziehen auf denselben Bus wird korrekt als vorhandene Verbindung erkannt. Das Modell wurde von dieser Prüfung nicht verändert.

Reproduzierbare Prüfungen: `frontend/scripts/verify-port-attachment.mjs`, `frontend/scripts/verify-port-attachment-project.mjs`, `scripts/verify_port_attachment_sql.py`. Ergebnisse liegen in `backend/runtime/port-attachment-browser-result.json` und `backend/runtime/port-attachment-project-result.json`. Die Browserskripte werden aus `frontend` gestartet. Die SQL-Prüfung benötigt pytest und verwendet ausschließlich `nis_port_attachment_tests`.
