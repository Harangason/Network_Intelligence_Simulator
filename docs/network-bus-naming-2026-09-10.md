# Physische Busnamen bearbeiten

Aktueller Stand: Build `14ab0e6f3706`, 10.09.2026, 22:47 Uhr MESZ.

Der Text auf der Buslinie stammt vom physischen Netz. Das bisherige Bearbeiten einer Beziehung änderte nur den Beziehungs- beziehungsweise Interface-Namen. Ein eigenes Eingabefeld für den Busnamen fehlte.

Doppelklick auf die Busbeschriftung oder die Auswahl einer Linie und „Bus umbenennen“ öffnet jetzt das Namensfeld. Derselbe Aufruf ist im Verbindungsdialog beim physischen Bus verfügbar. Der Dialog unterstützt Enter, Escape, Abbrechen sowie einen erhaltenen Entwurf mit Fehlermeldung und erneutem Speichern bei einem fehlgeschlagenen Request.

Die Änderung wird atomar in `parameters.networks[].name`, den Busnamensreferenzen der Ports und Kanten sowie der gespeicherten Szene übernommen. `name_source=user` beziehungsweise `physicalNetworkNameSource=user` erhalten die ausdrückliche Benutzerbenennung beim Materialisieren und Neuzeichnen, einschließlich eines Namens mit dem Präfix des Systemrahmens. Technische IDs, individuell vergebene Anschlussnamen, Teilnehmer, Portpositionen, Liniengeometrie, Kommunikationseinstellungen, Freigaben und Ergebnisversionen bleiben erhalten. Bestehende Ergebnis-Snapshots werden als historische Stände nicht umgeschrieben.

Der Request prüft die aktuelle Topologie- und Parameterversion unter einer Datenbanksperre. Die schlanke Netzwerkansicht liefert beide Versionskennungen. Fremde beziehungsweise fehlende Netz-IDs, veraltete Stände und ungültige Namen werden abgelehnt.

Automatisch aus dem Netz abgeleitete Interface-Namen werden ebenfalls übernommen: Ports einschließlich mehrerer Anker desselben Hardwarekanals, Quell-/Ziel-Interface-Namen aller betroffenen Verbindungen und die kanonischen HardwareNetworkInterface-Datensätze. Die Bindung wird mit `nameSource=network` beziehungsweise `capabilities.name_source=network` festgehalten. Für Altdaten wird die Bindung nur aus exakter Übereinstimmung mit der Netz-ID oder dem bisherigen Busnamen abgeleitet. Explizite Interface-Umbenennungen erhalten `nameSource=user` und folgen späteren Busumbenennungen nicht. Eigentümer und Netzzuordnung werden vor dem Schreiben geprüft; ein Kanal darf nicht mehrere physische Netze vertreten.

Das bereits offene Verbindungsfenster übernimmt nach erfolgreichem Bus-Rename die vom Server gespeicherten Anschlussnamen. Ein anschließendes „Beziehung übernehmen“ kann damit keine alten Namen zurückschreiben. Alle kanonischen Änderungen erfolgen in derselben Transaktion wie die Workflow-Daten; Fehler rollen beides zurück.

Bestehendes Projekt `network-project-20260910042736034-d11591d0` abgeglichen:

- Fünf Anschlussnamen im Kameranetz folgen jetzt `ETH_Kameraverarbeitung_01`.
- Drei Anschlussnamen im Radarnetz folgen jetzt `ETH_Radarverarbeitung_01`.
- `ETH_Fahrerassistenz_01` und `ETH_Fahrerassistenz_02` sind eigenständige physische Netze. Ihre Teilnehmer wurden nicht anderen Netzen zugeordnet.
- Der Abgleich nutzt die aktuellen Versionstoken, legt Sicherungen ab und prüft Datenbanknamen, Identitäten, vollständige Topologie gegen den Änderungsplan sowie unveränderte Parameter, Routingdaten, Freigaben und Ergebnisversionen.

Verifikation:

- 41 lokale Python-Prüfungen bestanden; drei SQL-Prüfungen lokal übersprungen und anschließend in PostgreSQL ausgeführt.
- 10 Prüfungen in separater PostgreSQL-Datenbank bestanden: mehrfache Umbenennung, Alias-Anker, individuelle Namen, materialisierte Anschlüsse, vollständiger Rollback und Konflikterkennung.
- TypeScript-Prüfung und Produktionsbuild erfolgreich.
- Browserprojekt `network-project-bus-naming-ui-1789073288499`: Netzabhängige Anschlussnamen über alle Anker übernommen, kanonische Speicherung, sofort aktualisiertes Verbindungsfenster, anschließende Beziehungsspeicherung und Neuladen erfolgreich.
- Browserprojekt `network-project-bus-naming-ui-1789073309139`: Individuelle Anschlussnamen bleiben unverändert. In beiden Browserläufen funktionieren Beschriftung, Toolbar, Verbindungsdialog, Abbrechen/Escape, Eingabeprüfung, Konflikt mit Wiederholung, Enter und Neuzeichnen; keine JavaScript-Seitenfehler.

Prüfskripte: `frontend/scripts/verify-bus-naming.mjs` (zusätzlich mit `VERIFY_INHERITED_NAMES=1`), `scripts/verify_bus_naming_sql.py`.

Projektabgleich: `scripts/reconcile_bus_interface_names.py`; Beleg und Sicherungspfade: `backend/runtime/bus-interface-names-reconciled.json`.


Weiterentwicklung: Die automatische Ethernet-Erzeugung und der Bestandsabgleich
folgen jetzt `NETWORK_NAMING_CONTRACT.md` (Build `e8475e1422fb`). Der beschriebene
manuelle Umbenennungsablauf und der Erhalt individueller Namen gelten weiterhin.
