# Beispieldokument in der Wizard-Vorschau

Status: vollständig geprüft, exakt getestetes Image produktiv übernommen und geprüft.

Der markierte Nutzerentwurf im Projekt `20261106093746010-f2585546` zeigt 13
Anschlussfragen, darunter „Funktion [1. Systemumfang]“ und gekürzte Controllernamen
mit Kapitelüberschriften. Eine reine Gegenprobe mit der erhaltenen `neu 9.txt`
reproduziert alle 13 Namen und insgesamt 251 projizierte Geräte. Die Datei hat
11578 Zeichen und SHA-256
`32c864c91ac85c2884ef0c3c9e62456e6ade59cc2a22cae384bdfe5a2e2eff60`.
Name, Länge und Fehlbild stimmen mit der Browseranzeige überein. Nach dem Leeren
des Browser-Dateieingabefelds war dessen exakter Dateihash nicht verfügbar;
Bytegleichheit der Browserdatei wird deshalb nicht allein daraus behauptet.

Der Fehler liegt vor einer übernommenen KI-Interpretation: Die Vorschau verwendete
lexikalische Textfunde und die beispielhafte Geräteexpansion wie ein konkretes
Geräteinventar. Kapitelbezeichnungen wurden dabei an vermeintliche Gerätenamen
angehängt. Die UI bezeichnete auch die ergänzten Vorlagengeräte als konkret und
forderte Anschlüsse für diese ungeprüften Identitäten an.

Die vorhandene Spezifikationsextraktion erhält nun einen ausdrücklichen
Vorschaumodus. Gegliederte Beispieldokumente liefern darin ihren genannten
Sollumfang und ihre Technologien, zunächst aber keine aus Prosa oder Templates
materialisierten Geräte. Der Wizard zeigt die notwendige Dokumentprüfung und
führt zur vorhandenen ausdrücklichen lokalen KI-Auswertung. Erst übernommene
typisierte Quellenbefunde oder ein angenommener Referenzentwurf öffnen den normalen
Geräteweg. Kurze strukturierte Aufträge und bestätigte Erzeugungsaufträge behalten
ihren bisherigen Weg. Vorhandene Mengen-/Anschluss-/Reviewprüfungen bleiben aktiv.

Es gibt keine automatische Inferenz oder START-Operation. Der offene Nutzerentwurf
wurde nur angesehen und auf seine ursprüngliche Statusseite zurückgestellt;
Quelle und Eingabefelder wurden nicht bearbeitet und die Seite nicht neu geladen.
Normale Status-GETs belegen für den Projektzeitpunkt: alle neun Schritte EMPTY,
keine Ausführung, kein aktiver Vorschlag, kein gespeicherter Draft und keine Jobs.

Lokale Nachweise: ursprüngliches RED mit zwei fehlgeschlagenen und zwei
bestandenen Gegenproben; anschließend vier gezielte Fälle PASS. `npm test` hat
720 Fälle bestanden, TypeScript Exit 0. Der kanonische Releaseweg sammelt mehr
Frontenddateien rekursiv und hat 725 Fälle bestanden. Die überlappenden Sätze
werden nicht addiert. Der neue Browserfall verwendet den unveränderten erhaltenen
Quelltext als eigenes festes Fixture; er ist eine Vorschauprüfung, keine native
LLM- oder vollständige historische Originalabnahme.

Abgeschlossener Releaseweg: Session 36741, normaler Exit 0 / DEPLOYED.
Receipt `backend/test-output/release-gates/delivery-6127991a9e47/4310b821dab9/receipt.json` ist vollständig PASS.
Image `sha256:c7edda158398ce6c13b5563f56df70575aa61345539fbc23a5aeb847164fca33`.
Source `45147bdc7086d19a587b6704ad2943e7d79ec3d866fb26d4546c8e055a921c44`.
Verification `b6cce320a038ff9bf35c543167c2ab21f7a06f60caed2b9c69e4c5eea7a2eb26`.

Vollständige kanonische Prüfungen: Speicherprüfungen und TypeScript Exit 0;
725 Frontendfälle PASS; 22670 Backendfälle PASS, 2 SKIP, 56 Subtests PASS,
eine Feldnamenwarnung. Alle 122 Browserfälle PASS, keine Wiederholung und kein
übersprungener Browserfall. Beide kontrollierten HTTP-Vergleichsfälle haben
PASS-Konformität, vollständige Scopeabdeckung und null fehlgeschlagene Routen.
Vorhandene fachliche Warnungen bleiben in den Originalreports sichtbar.

Die produktive Containeridentität entspricht dem getesteten Image. Normale
Ready-/Build-GETs auf 13500, 15050 und LAN sowie dieselbe Projektseite auf Lokal
und LAN sind geprüft. Die reinen Komponenten aus dem tatsächlich laufenden
Produktimage bestehen die vollständige quellengebundene Vorschau-Gegenprobe;
es wurde dafür weder eine Inferenz noch ein Projektauftrag gestartet. Details:
`release-summary.json`, `delivery-terminal.json`, `live-before.json`,
`live-components.json`, `live-frontend-bundle.json`, `live-after.json` und `completion-guard.json`.
Das tatsächlich ausgelieferte JavaScript mit der neuen Vorschau stimmt lokal
und über LAN bytegenau mit dem kompilierten Artefakt im laufenden Image überein.
Alle sieben eingefrorenen Änderungsdateien sind unverändert. Abschlussguard:
COMPLETED, fünf Ziele und fünf Validierungen belegt, keine offenen Befunde.

Der ungesendete alte Browserentwurf wurde nicht neu geladen. Für den neuen
Client muss der Nutzer selbst neu laden und seine tatsächliche Datei erneut
anhängen. Der gespeicherte Nutzerprojektstatus wurde nach der Übernahme nur
gelesen; keine manuelle Änderung von Geräten, Anschlüssen oder Anforderungen.
Diese Abnahme umfasst die Vorschaukorrektur und das normale Releasegate;
sie ersetzt keine historischen nativen Fahrzeug-/Robotik-Originalprüfungen.
