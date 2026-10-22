# Wiederherstellung der am 21.10.2026 ausgemusterten Teststände

Diese Archive enthalten ausschließlich die im `cleanup-plan.json` genannten
alten Testkandidaten und Testdaten. Produktion, Rückfallimages, der aktuelle
Teststack und alle Images mit PASS oder ungeklärtem Status bleiben installiert.
Die ursprünglichen PREPARED-Receipts werden nicht umgeschrieben. Die ausdrückliche
Bereinigungsfreigabe dieses Chats ersetzt keine Releaseabnahme.

Das gemeinsame Imagearchiv liegt unter
`F:\CodexOrdner\visualizations\2026\10\21\01a15ce5-2b16-7d01-844d-6232dd03f254\nis-cleanup-archives\retired-prepared-images.tar`.
`image-archive-audit.json` enthält seinen SHA-256 und die geprüften Index-,
Konfigurations- und Layeridentitäten. Mit `docker image load --input <Archiv>`
können die ursprünglichen Kandidaten wiederhergestellt werden; anschließend
die erwarteten unveränderlichen IDs aus `cleanup-plan.json` vergleichen.
Das Laden ist keine Freigabe zur Produktivbereitstellung.

Im selben Archivordner liegt je entferntem Laufzeitvolume eine TAR-Datei mit
dem ursprünglichen Volumenamen. `stack-backup-audit.json` bindet Archive und
Logs per SHA-256 und führt die Dateihashes der Volumensicherungen auf. Zur
Wiederherstellung ein neues, ausdrücklich isoliertes Testvolume erstellen,
seine TAR-Datei dort sicher entpacken und Dateihashes vergleichen. Niemals in
Produktionsvolumes entpacken. Die zugehörigen ursprünglichen Ressourcen und
Imagezuordnungen stehen im Plan; ein alter Containername allein ist kein
vollständiger Wiederanlaufnachweis.

Die alten Datenbanken verwendeten tmpfs. Ihre bereits vor dieser Bereinigung
gestoppten Inhalte sind durch Stop/Neustart verloren; ein Image- oder
Laufzeitvolume-Archiv enthält diese PostgreSQL-Daten nicht. Vorhandene frühere
Datenbank-Dumps, Projektexporte und Testnachweise werden unverändert erhalten.
Eine benötigte alte Datenbank ausschließlich aus dem passenden vorhandenen Dump
in einer neuen isolierten Testdatenbank wiederherstellen. Keine alten
Testdatenbanken werden zur Bereinigung gestartet.

`removal-result.json` protokolliert jeden einzelnen entfernten Container, jedes
Netzwerk, Volume und Kandidatentag. Docker erhält dabei weder `--force` noch
einen Prune-Aufruf. Die Imageentfernung verwendet ausschließlich `--no-prune`.
