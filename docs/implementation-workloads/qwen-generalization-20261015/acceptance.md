# Vorab festgelegter Prüfbereich

Sieben unveränderte Originaldateien aus `C:\Users\marti\PycharmProjects\Benchmark_Modelle` werden vollständig an den installierten lokalen Qwen-Dokumentplaner übergeben. Dies prüft Dokumentverständnis und Vorschlagsqualität. Es prüft weder den vollständigen Wizard-Ablauf noch Simulation, technische Freigabe oder EIP-Integration.

Die Tests verwenden keine Datenbank, kein Mock-Modell, keine aufgezeichneten Antworten als Eingabe und keinen Cloud-Dienst. Jede echte Anfrage und Antwort, Originaldatei, Laufzeit und Quellhash werden gespeichert. Ein erfolgreiches Schema allein ist kein fachlicher Erfolg.

| Datei | Unabhängige Erwartungen aus dem Original |
| --- | --- |
| Intelligentes HLK-Regelsystem | Gebäudeautomation und Raumregelung erhalten; Raumcontroller, Sensorik und Aktoren als unquantifizierten Architekturumfang behandeln. Komfort/Energie/Fernzugriff als Anforderungen, keine bestätigten Busse oder Stückzahlen erfinden. |
| Chemieanlagen-Modul | Prozessmodul, Prozesssensorik, Aktoren und SPS/DCS berücksichtigen; Rezepturablauf, Regelkreise und Alarme als Funktionen; Druckabschaltung als Test-/Sicherheitsverhalten. Keine Stückzahl aus „Beispiel 11“, keine automatische CAN-/Automotive-Auswahl. |
| Kollaborativer Roboterarm | Gelenkaktuatoren, Kraft-/Momentensensorik und Sicherheitssteuerung erhalten; Bahnplanung und Kollisionsüberwachung als Funktionen. „Beispiel 14“ ist keine Gerätezahl. Fehlende Stückzahlen und Anschlüsse klären. |
| Infusionspumpe | Pumpenmechanik, Fluss-/Luftsensorik und Embedded Controller berücksichtigen; Förderprofilsteuerung, Okklusionserkennung, Alarmierung als Funktionen. Toleranz und Stoppfunktion als Anforderungen; keine erfundene Gerätezahl oder medizinische Freigabe. |
| 5G-RAN-Komponente | Funkmodul und Architekturkontext erhalten; Baseband-Processing und Scheduling nicht in physische Geräte umdeuten. Der Projekttitel belegt keinen konkret ausgeführten Geräteanschluss; offene Fronthaul-/Backhaul-Realisierung klären. Keine Automotive-Vorlage. |
| Satelliten-Avionik | On-Board-Computer, Power Control Unit, Sensortypen und Reaktionsräder berücksichtigen; FDIR/Mode Management/Telecommand als Funktionen und F-/NF-REQ als Anforderungen. CAN separat erhalten; SpaceWire und „UART-ähnlich“ nicht ohne Prüfung als bestätigte physische Anschlüsse übernehmen. Keine Mengen aus REQ-/TC-Nummern. |
| Mobiler Service-Roboter | Raspberry Pi 5 als benannten Hauptrechner von beispielhaften/alternativen Geräten unterscheiden. Unquantifizierte Typen, 4–6 Räder und 8–12 Ultraschallsensoren bleiben offene Mengenbereiche, keine erfundene exakte Stückzahl. CAN, I²C, UART und explizite Schnittstellen erhalten; WiFi/Bluetooth/CSI/Serial nach Registry und Quelle behandeln. Anforderungs- und Testnummern, Freiheitsgrade, Frequenzen und Spannungen sind keine Geräteanzahlen. Gesamtvorschlag darf frühen und späten Dokumentabschnitten nicht widersprechen. |

Gemeinsame Abnahme: Vollständiger Originaltext muss in den tatsächlichen Modellanfragen nachweisbar sein. Fakten müssen Quellenstellen besitzen; Vorschlag und Fragen müssen zur jeweiligen Branche und zu den fehlenden Angaben passen. Fehler werden als Fehler dokumentiert, auch wenn die eingebaute Validierung sie durchlässt. Eine Rückfrage ist ein zulässiges Ergebnis bei unvollständigen Beschreibungen.
