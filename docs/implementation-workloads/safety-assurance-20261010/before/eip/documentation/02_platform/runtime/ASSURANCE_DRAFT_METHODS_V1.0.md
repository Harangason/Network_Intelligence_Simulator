# Quellengebundene Draft-Analysen V1.0

Stand: 26.09.2026. Status: ausdrücklich beauftragte Implementierung; noch keine Abnahme.

Der Benutzer hat FMEA, FTA, STRIDE und Attack Tree als Draft-Analysen mit separater
Prüfung freigegeben. Sie ergänzen die bestehenden Safety-/Security-Arbeitsflächen.
Analysen werden als `AssuranceAnalysis` im vorhandenen PostgreSQL-Core gespeichert.
Quellreferenzen und Originalrevisionen, Eingaben, Methodenfassung und abgeleitete
Ergebnisse gehören zum selben auditierten Objekt. Es entsteht keine separate
Datei- oder Board-Wahrheit.

FMEA erfasst Ausfallart, Ursache, lokale und übergeordnete Wirkung sowie Entdeckung
und Maßnahmen. Optionale S/O/D-Werte verwenden eine ausdrücklich als lokale
1–10-Skala bezeichnete Eingabe; nur drei vorhandene Werte ergeben das Produkt RPN.
Die Skala ist keine normative Branchenbewertung. Fehlende Angaben bleiben Gaps.
FTA untersucht ein explizites Top-Ereignis über benannte AND-/OR-Gatter und belegte
Basisereignisse. Der erste Umfang berechnet begrenzte qualitative minimale
Ereignismengen, keine Ausfallwahrscheinlichkeiten. Die unterschiedliche Richtung
von FMEA und FTA folgt der [NASA-Methodeneinordnung](https://s3vi.ndc.nasa.gov/ssri-kb/topics/16/).

STRIDE ordnet vom Bearbeiter beschriebene Bedrohungen den sechs Kategorien zu;
fehlende Kategorien gelten als nicht untersucht. Grundlage ist die
[Microsoft-SDL-Beschreibung](https://www.microsoft.com/en-us/securityengineering/sdl/practices/secure-by-design).
Attack Trees behandeln ein explizites Bedrohungsziel mit AND-/OR-Zerlegung;
Ergebnisse sind qualitative Szenarien, keine Erfolgswahrscheinlichkeiten.
Systemgrenze, Quellen und getrennte Bewertung orientieren sich am
[OWASP Threat Modeling Guide](https://cheatsheetseries.owasp.org/cheatsheets/Threat_Modeling_Cheat_Sheet.html).

Jede Speicherung prüft aktuelle Projekt-Schreibrechte, erwartete Analyse- und
Quellrevisionen und Idempotenz. Bestehende geprüfte/freigegebene Objekte werden
nicht überschrieben. Fachliches Review nutzt den vorhandenen unabhängigen
Reviewvertrag; Selbstfreigabe ist nicht Teil dieses Ablaufs. Geänderte Quellen
werden als veraltet sichtbar. Eine strukturell gültige Analyse ist weder ein
Risikonachweis noch eine Releasefreigabe. Methodenspezifische Prüfungen und echte
Browser-/Persistenznachweise werden vor einer Abnahme ergänzt.

## Implementierter Umfang und Grenzen

`POST /api/v1/projects/{projectId}/assurance/drafts` verwendet `If-Match` (0 für
Neuanlage), einen stabilen `Idempotency-Key` und aktuelle persönliche Schreibrechte.
Der bestehende Review-Endpunkt übernimmt die originalen Analysequellen automatisch.
Ein getrenntes Review verändert weder Risikofreigabe noch Releasezustand.

Die erste Oberfläche erfasst je Draft einen FMEA-Eintrag, ein STRIDE-Szenario oder
ein AND-/OR-Gatter mit bis zu 16 Basisereignissen einer gewählten Core-Quelle.
Der Service validiert bis zu 64 Einträge/Baumknoten und 20 Quellrevisionen; komplexe
mehrstufige Baum- und Mehrquelleneditoren sind noch nicht Teil der Oberfläche.
Die Ergebnisliste zeigt höchstens 50 aktive Analysen mit sichtbarer Gesamtzahl.
Bearbeitung bestehender Drafts ist serverseitig revisionsgeschützt vorbereitet;
die Oberfläche bietet bisher Neuanlage, Lesen und separate Review-Anforderung.

EDS-Komponente: `assurance.drafts.v1`. Fehlende Quellen, ungültige Eingaben,
Revisionskonflikte, unbestätigte Transportversuche und veraltete Quellen bleiben
sichtbar. Wiederholungen behalten den ursprünglichen Payload und Versuchsschlüssel.

Gezielter Laufzeitnachweis vom 26.09.2026: 63 Methoden-/PostgreSQL-/Review-/
Projektionsprüfungen, ausführbare Frontendverträge und Produktionsbuild bestanden.
Alle vier Draft-Methoden wurden im persönlichen Browser erstellt und erneut gelesen;
separate Review-Anforderung und verweigerte Selbstentscheidung wurden geprüft.
API und Core bestätigen Persistenz, Idempotenz sowie 400-/412-Negativfälle.
Tool-Checker-Delivery `9ca54d355768493588379362b46b6e15` ist
`CONFIRMED_BY_RUNTIME`. Die vollständige Kampagnen-Folgerunde bleibt offen.
Eine unabhängige menschliche Fachfreigabe wurde nicht durchgeführt.
