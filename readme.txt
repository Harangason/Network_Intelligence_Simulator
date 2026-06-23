Die vier Optionen steuern, wie die Nutzdaten/Signalwerte in den Botschaften befüllt werden. Also nicht nur welche CAN-/ETH-Dateien erzeugt werden, sondern ob die Werte technisch plausibel, roh, zufällig oder gestört wirken.
1. Berechnete Werte mit Counter, CRC, Zeitverlauf und Fehlerlogik Das ist der Default und für realistische Simulationen am sinnvollsten.
Die Werte werden abhängig von Zeit, Frame-ID, Zyklus, Signalposition und Manöver berechnet. Dazu gehören typischerweise:
•
Alive Counter: zählt pro Botschaft sauber hoch
•
CRC: wird passend zum Payload berechnet
•
Zeitverlauf: Geschwindigkeit, Lenkwinkel, Bremsdruck usw. ändern sich plausibel über die Simulationszeit
•
Fehlerlogik: bei Fault-Szenarien können CRC, Counter, Timing oder Statuswerte gezielt abweichen
Gut für:
•
Restbussimulation
•
HIL/SIL-nahe Tests
•
Manöver wie Spurwechsel, AEB, ACC, Parken
•
Plausible Botschaften statt nur Datenrauschen
2. Rohdatenorientiert Hier stehen rohe Payloads im Vordergrund. Die Werte sind weniger semantisch interpretiert.
Das bedeutet:
•
Bytes/Signale werden eher technisch gefüllt
•
weniger physikalischer Verlauf
•
weniger Abhängigkeit vom Manöver
•
eher geeignet, wenn du Payload-Strukturen, Parser oder Decoder testen willst
Gut für:
•
Decoder-Tests
•
Format-/Datenbankprüfung
•
DBC/ARXML/FIBEX Validierung
•
Payload-Kompatibilität
3. Seeded Random innerhalb der Signalgrenzen Die Werte werden zufällig erzeugt, aber mit festem Seed reproduzierbar.
Das bedeutet:
•
gleiche Eingabe erzeugt wieder gleiche Zufallswerte
•
Werte bleiben innerhalb definierter Grenzen
•
weniger realistische Zeitverläufe
•
gut zum schnellen Abdecken vieler Signalbereiche
Gut für:
•
Robustheitstests
•
Parser-Fuzzing light
•
Grenzbereichsabdeckung
•
große Datenmengen ohne echte Fahrphysik
4. Hybrid: berechnet plus Rauschen/Störungen Das ist eine Mischung aus Option 1 und gezielter Varianz.
Basis ist ein berechneter plausibler Verlauf, darauf kommen:
•
Sensorrauschen
•
kleine Jitter-Effekte
•
sporadische Störungen
•
Fault Injection
•
Ausreißer oder degradierte Signale
Gut für:
•
realistischere Sensordaten
•
Fehler- und Robustheitstests
•
ADAS-Szenarien mit gestörter Kamera/Radar/IMU
•
Tests, bei denen Werte plausibel, aber nicht perfekt sauber sein sollen