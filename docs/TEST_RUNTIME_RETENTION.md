# Temporäre Testdaten: Aufbewahrung und Bereinigung

Pytest legt je Sitzung einen eigenen `nis-test-runtime-*`-Ordner unter
`traces/temp` im Projekt an. Dies geschieht beim Teststart, nicht beim Öffnen
des Simulators.

Beim Start einer neuen Pytest-Sitzung werden verwaltete Testordner gelöscht,
deren letzter Schreibzugriff länger als **48 Stunden** zurückliegt. Der
Abschlussmarker startet diese Frist frühestens am Ende der Sitzung. Neuere
Dateien im Ordner verlängern die Aufbewahrung des gesamten Ordners.

Jede Sitzung hält eine Betriebssystem-Dateisperre. Gesperrte Verzeichnisse
werden unabhängig vom Alter erhalten. Bei einem Prozessabbruch gibt das
Betriebssystem die Sperre frei; die verbliebenen Dateien können nach Ablauf
der Frist beim nächsten Teststart bereinigt werden.

Es werden ausschließlich direkte `nis-test-runtime-*`-Unterordner mit gültigem
NIS-Eigentumsmarker behandelt. Fremde oder ältere unmarkierte Ordner sowie
symbolische Links/Junctions bleiben erhalten. Vor dem Löschen wird der gesamte
Unterbaum auf gültige Grenzen und Links geprüft. Fehler werden gemeldet und
verhindern die weitere Bereinigung des betreffenden Ordners.

Diese Regel betrifft keine Produktiv-Traces, keine Quelldateien und nicht den
allgemeinen Windows-Temp-Ordner. Ohne neue Teststarts läuft keine zeitgesteuerte
Bereinigung. Die bisherigen unmarkierten Bestände wurden separat auf ausdrücklichen
Nutzerauftrag bereinigt.
