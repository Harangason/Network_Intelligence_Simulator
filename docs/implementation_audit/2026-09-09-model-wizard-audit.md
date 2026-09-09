# NIS: Datenmodell, Structure Tree und Wizard-Zuordnungen

Prüfstand: 9. September 2026. Projekt `network-project-20260909082213746-780a13ef`, kanonisches Repository `I:/PycharmProjects/My_first_Network_Simulator`.

**Ergebnis:** Die drei markierten Probleme sind nachvollziehbare Inkonsistenzen zwischen dem gültigen Backend-Modell und seinen Oberflächen. Die 199 als „nicht zugeordnet“ angezeigten Interfaces haben sämtlich einen gültigen Hardware-Elternknoten. 215 Signale besitzen nach der vorgesehenen Geräteklassifizierung bewusst keine separate Funktion. Zusätzlich weichen 41 im Structure Tree abgeleitete Systemrahmen von den gespeicherten, akzeptierten Wizard-Zuordnungen ab. Bei 14 physischen Hardware-Interfaces weist die generierte Topologie dieselbe Interface-ID mehreren getrennten physischen Netzen zu.

Es wurden keine Projektobjekte, Quellcodefunktionen oder Freigaben geändert. Die Prüfung verwendet den vom Hauptaudit gesicherten Projekt-Export und lesende API-Aufrufe. Der Export bleibt eine lokale Prüfgrundlage.

## Prüfgrundlage und reproduzierbare Zahlen

| Objekt oder Prüfung | Ergebnis |
| --- | ---: |
| Hardware | 260 |
| Funktionen | 61 |
| Physische Hardware-Interfaces | 326 |
| Logische Interfaces | 326 |
| Nachrichten | 309 |
| Signale | 520 |
| Interfaces direkt an Hardware, ohne Funktion | 199 |
| Davon tatsächlich ohne existierenden Hardware-Elternknoten | 0 |
| Signale ohne Funktion in ihrer Eigentümerkette | 215 |
| Geräteklasse dieser Signalquellen | ausschließlich Klasse 1 |
| Explizite `identity.system_owner_id` in Hardware | 0 |
| Explizite `systemOwnerId` in gespeicherter Topologie | 0 |
| Akzeptierte eindeutige Wizard-Zuordnungen | 209 |
| Abweichungen zwischen Tree-Systemrahmen und akzeptierter Wizard-Zuordnung | 41 |
| Physische Interface-IDs in mehreren getrennten Topologienetzen | 14 |
| Bestehende kanonische Nachrichten mit abweichendem Hardware-Eigentümer zwischen logischem Interface und physischem Port | 0 |

Der Reproducer [2026-09-09-model-projection-audit.cjs](I:/PycharmProjects/My_first_Network_Simulator/docs/implementation_audit/verification/2026-09-09-model-projection-audit.cjs) extrahiert und transpiliert die tatsächlichen TypeScript-Funktionen des Structure Tree, führt sie auf dem vollständigen Export aus und vergleicht das Ergebnis mit Topologie und Wizard-Feedback. Er verändert nur seine eigene Ergebnisdatei. Aufruf vom Projektverzeichnis:

```powershell
node docs/implementation_audit/verification/2026-09-09-model-projection-audit.cjs
```

Alle 41 Abweichungen, alle 14 Portfälle und der vollständige EGR-Nachweis stehen in [2026-09-09-model-projection-audit.json](I:/PycharmProjects/My_first_Network_Simulator/docs/implementation_audit/verification/2026-09-09-model-projection-audit.json). Die reine bestehende Strukturrulesuite wurde zusätzlich ausgeführt: `python -m pytest backend/tests/test_structure_rules.py -q -p no:cacheprovider` → **9 bestanden**. Diese Tests decken die jetzt nachgewiesenen UI-Vertragsbrüche nicht ab.

## 1. P1: Der Structure Tree stellt gültige Sensor- und Aktor-Interfaces als unzugeordnet dar

Der Generator unterscheidet Geräteklassen. Ein einfacher Sensor oder Aktor der Klasse 0–2 erhält keine künstliche Funktion. Ein komplexes Gerät erhält ein Funktionsmodell. Der aktuelle EGR-Sensor ist Klasse 1.

Der Datenfluss ist korrekt implementiert:

- [device_classification.py:143](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/device_classification.py:143): Klasse 0–2 bekommt keine `requires_function_model`-Freigabe; für Klasse 3 und höher wird sie gesetzt.
- [wizard_generation.py:247](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/agent_tools/wizard_generation.py:247): Funktion nur erstellen, wenn das Profil sie verlangt; andernfalls das Interface über `hardware_node_id` direkt an Hardware binden.
- [repository.py:230](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/repository.py:230): `parent_link_for_payload` kennt beide gültigen Beziehungen: `Function → Interface` und `HardwareNode → Interface`.

Die UI verwendet dagegen eine starre Kette `Hardware → Funktion → Interface → Nachricht → Signal`. [structure-tree-workbench.tsx:45](I:/PycharmProjects/My_first_Network_Simulator/frontend/src/components/structure-tree-workbench.tsx:45) legt für ein Interface ausschließlich `function_id` als Elternfeld fest. [Zeile 334](I:/PycharmProjects/My_first_Network_Simulator/frontend/src/components/structure-tree-workbench.tsx:334) erklärt jeden fehlenden Eintrag in diesem Feld zum Waisenobjekt. Das vorhandene `hardware_node_id` wird dabei ignoriert. Genau daraus entstehen die **199** sichtbaren „nicht zugeordnet“-Einträge.

**Lösung:** Eine gemeinsame, typabhängige Elternauflösung verwenden. Bei Interfaces zuerst eine gültige Funktion auflösen, sonst die direkte Hardware-Zuordnung. Der Baum muss beide zulässigen Pfade darstellen. Ein Orphan ist nur ein Objekt ohne irgendeinen zulässigen, existierenden Elternknoten. Dabei keine 199 Hilfsfunktionen erzeugen: Das würde die gewollte Geräteklassifizierung umgehen.

**Abnahme:** Das aktuelle Projekt zeigt 0 echte Interface-Waisen. `EGRValvePosition_1` erscheint direkt unter Hardware `EGRValvePosition`; Nachricht und `AGRVentilstellung` bleiben darunter. Ein gezielt defektes Interface ohne gültige Hardware oder Funktion erscheint weiterhin mit konkretem Fehlergrund als unzugeordnet. Projektwechsel und vollständige Pagination werden mitgeprüft.

## 2. P2: Die Signalspalte „Funktion“ verschweigt den Unterschied zwischen „nicht erforderlich“ und „fehlend“

[engineering-workbench.tsx:312](I:/PycharmProjects/My_first_Network_Simulator/frontend/src/components/engineering-workbench.tsx:312) löst die Funktion ausschließlich über `Signal.message_id → Message.interface_id → Interface.function_id` auf. Fehlt sie, erscheint `—`. Deshalb stehen bei EGR-Ventilstellung, Abgastemperatur, Harnstofffüllstand und den einfachen Aktoren Striche.

Im vollständigen Projekt betrifft dies **215 von 520 Signalen**, ausschließlich Quellen der Geräteklasse 1. Die Nachrichten, Interfaces und Hardware-Eltern existieren. Der Strich bedeutet in diesen Fällen keine verlorenen Signaldaten, keine Byte-Lücke und keine fehlende Systemzuordnung. Die Oberfläche vermittelt aber genau diesen Eindruck.

**Lösung:** In der Tabelle eine eindeutige Quellenangabe anbieten: System, Quellgerät und gegebenenfalls Funktion. Wenn keine Funktion erforderlich ist, etwa `Direkt am Sensor · EGRValvePosition` anzeigen. Eine tatsächlich abgebrochene Referenzkette erhält eine eigene Fehlermeldung mit Reparaturziel. Die nutzende ECU-Funktion ist eine zusätzliche fachliche Beziehung; sie darf nicht stillschweigend als Eigentümerfunktion des Sensors ausgegeben werden.

**Abnahme:** `AGRVentilstellung` zeigt als Quelle EGR-Sensor, als System Abgasnachbehandlung und den Status „direkt am Gerät“. Ein Steuergerätsignal behält seine tatsächliche Funktion. Ein fehlendes Nachrichtenobjekt ist sichtbar als Datenfehler unterscheidbar. Filter und Sortierung arbeiten auf diesen fachlichen Werten.

## 3. P1: Die akzeptierte Wizard-Zuordnung wird im Structure Tree erneut geraten

Das Projekt enthält in `workflow.context.equipment_assignment_feedback` **209 akzeptierte Endpoint-Zuordnungen**. Für den konkret markierten Sensor lautet der gespeicherte Beleg:

```json
{
  "endpoint_name": "EGRValvePosition",
  "controller_name": "Abgasnachbehandlung",
  "accepted": true,
  "source": "wizard-submission",
  "recorded_at": "2026-09-09T10:27:37.43158+02:00"
}
```

Auch die gespeicherte freigegebene Route heißt `EGRValvePosition → Abgasnachbehandlung`, ist gültig und führt auf die korrekte ECU. Der Nutzer erinnert sich hier richtig: Die Zuordnung wurde tatsächlich bestätigt.

Trotzdem wird keine explizite Eigentümerbeziehung in den Hardware-Identitäten oder Topologieknoten materialisiert. Die Hardware-Erzeugung schreibt nur Name, Gerätetyp, Klasse und Beschreibung ([wizard_generation.py:243](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/agent_tools/wizard_generation.py:243)). Der bestätigte Graph wird für lokale Netze ausgewertet ([Zeile 606](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/agent_tools/wizard_generation.py:606)), aber bei der Topologieknotenerzeugung keine Systemowner-ID gespeichert ([Zeile 760](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/agent_tools/wizard_generation.py:760)).

Der Structure Tree lädt nur Engineering-Objekte, keine gespeicherte Topologie oder Wizard-Zuordnungen ([structure-tree-workbench.tsx:254](I:/PycharmProjects/My_first_Network_Simulator/frontend/src/components/structure-tree-workbench.tsx:254)). Er gruppiert die Hardware anhand von Namensregeln und optionaler `identity.system_owner_id` ([Zeile 139](I:/PycharmProjects/My_first_Network_Simulator/frontend/src/components/structure-tree-workbench.tsx:139)). Der Backend-Resolver verwendet dagegen zusätzlich explizite Topologiefelder und physische Nachbarschaft ([system_clusters.py:47](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/system_clusters.py:47)). Das sind getrennte Entscheidungen für dieselbe fachliche Frage.

Auf dem tatsächlichen Stand weichen **41** Tree-Zuordnungen von der gespeicherten Topologie ab. Bei **allen 41** bestätigt das akzeptierte Wizard-Feedback genau die Topologieseite. Beispiele: `FrontLeftWheelLoad` wurde Stabilitätsregelung zugeordnet, erscheint per Namensregel bei Fahrwerk; `FrontLeftBrakeTemperature` wurde Bremsregelung zugeordnet, erscheint bei Thermomanagement. Das ist ein Widerspruch zur bestätigten Nutzereingabe; damit ist noch keine unabhängig geprüfte Aussage verbunden, welche technische Systemzuordnung fachlich optimal wäre.

**Lösung:** Die akzeptierte Zuordnung als eine projektbezogene Beziehung mit Hardware-IDs, Ursprung und Version speichern. Bestehende Projekte können aus den akzeptierten Wizard-Einträgen migriert werden, wenn die Namen eindeutig zu vorhandenen IDs auflösbar sind. Tree, Wizard, Netzwerkeditor, Kapazitätsansicht und Agent müssen denselben Resolver verwenden. Namensheuristiken dürfen nur fehlende Zuordnungen vorschlagen und müssen als Vorschlag erkennbar sein. Änderung der Verkabelung darf eine bestätigte funktionale Systemzugehörigkeit nicht stillschweigend überschreiben.

**Abnahme:** Alle 209 akzeptierten Zuordnungen stimmen nach Neuladen und Export/Import in allen Ansichten überein. EGR bleibt bei Abgasnachbehandlung, auch nach Umbenennung des Sensors. Mehrdeutige Namen blockieren die automatische Migration für den jeweiligen Eintrag. Bestehende manuelle Zuordnungen werden erhalten. Ein Umstecken zum Gateway ändert die physische Verbindung, nicht automatisch die fachliche Systemzugehörigkeit.

## 4. P1: Bearbeiten und Structure Wizard können die gültige direkte Beziehung nicht ausdrücken

Der Fehler betrifft mehr als die Darstellung:

- Das Formular verlangt bei jedem Interface eine Funktion ([engineering-workbench.tsx:1702](I:/PycharmProjects/My_first_Network_Simulator/frontend/src/components/engineering-workbench.tsx:1702)). Die Ressourcenhierarchie kennt nur Funktionen als Interface-Eltern ([Zeile 118](I:/PycharmProjects/My_first_Network_Simulator/frontend/src/components/engineering-workbench.tsx:118)).
- Der Structure Wizard verlangt in jeder Stufe mindestens ein Objekt, also auch eine Funktion ([structure.py:75](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/structure.py:75)).
- Bewertung und Übernahme verwenden das statische `PARENT_LINKS` anstelle der bereits vorhandenen dynamischen Elternauflösung ([structure.py:89](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/structure.py:89), [Zeile 229](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/structure.py:229)). `HardwareNode → Interface` wird dadurch als ungültige Hierarchiekante abgewiesen.
- Drag-and-drop kann ebenfalls nur die statische Elternebene bedienen ([structure-tree-workbench.tsx:365](I:/PycharmProjects/My_first_Network_Simulator/frontend/src/components/structure-tree-workbench.tsx:365)).

Das ist besonders ungünstig: Der Generator erzeugt einen gültigen Zustand, den die Verwaltungsoberfläche anschließend nicht in gleicher Form bearbeiten kann. Die Agent-Validierung formuliert sogar ausdrücklich, für Klasse 0–2 keine künstliche Funktion zu erzeugen ([validation.py:57](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/agent_tools/validation.py:57)).

**Lösung:** Elternwahl und Wizard-Schritte aus dem Geräteprofil und einem gemeinsamen Beziehungsschema ableiten. Für einfache Geräte die Funktion überspringen. Bestehende direkte Bindung beim Bearbeiten erhalten. Systemmitgliedschaft und Verschieben eines kommunizierenden Objekts als unterschiedliche Aktionen behandeln. Bei einem wirklichen Eigentümerwechsel sämtliche betroffenen Nachrichten- und Portbindungen vor Übernahme prüfen.

**Zusätzliches, noch nicht durch Mutation reproduziertes Risiko:** Ein Verschieben eines Interfaces unter eine fremde Funktion setzt dessen `hardware_node_id` auf die andere ECU ([repository.py:697](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/repository.py:697)), ohne in diesem Pfad die darunterliegenden `Message.hardware_interface_id` neu zu binden. Das kann logische und physische Eigentümer auseinanderziehen. Der aktuelle Projektbestand weist diesen Schaden noch nicht auf; es handelt sich um einen konkreten Prüfbedarf vor Freigabe der Reparaturfunktion.

**Abnahme:** Klasse-1-Sensor vollständig ohne Funktion anlegen, bearbeiten und neu laden; Interface direkt zwischen zulässigen Hardware-Eltern zuordnen; Klasse-4-ECU mit Funktion unverändert unterstützen. Ein Verschieben über Hardwaregrenzen erhält einen vollständigen Vorschlag für Port-/Nachrichtenanpassung oder wird mit genauer Begründung abgewiesen. Keine stille Erzeugung von Hilfsfunktionen.

## 5. P1: Topologie-Ports ignorieren die bereits bestätigte konkrete Portbindung

[wizard_generation.py:730](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/agent_tools/wizard_generation.py:730) erzeugt einen Topologieport je Gerät, Technologie und physischem Netzwerk. Für die kanonische Port-ID wählt die Funktion jedoch `matching[0]`: den ersten Port desselben Geräts mit passender Technologie. Die konkrete `port_id` der Route und `network_ref` werden bei dieser Wahl nicht berücksichtigt.

**Konkrete Rekonstruktion Abgasnachbehandlung:**

1. Das kanonische Modell besitzt `Abgasnachbehandlung_1` für den übergeordneten CAN-FD-Anschluss und `Abgasnachbehandlung_CAN_FD_IO` für den lokalen Anschluss.
2. Die freigegebene EGR-Route nennt als ECU-Zielport ausdrücklich `145458d6-5a9c-4ac8-b3da-8f7766bbe49f`, also `Abgasnachbehandlung_CAN_FD_IO`.
3. Der erzeugte lokale Topologieport für `Antriebsstrang_01-IO-abgasnachbehandlung-can-fd-S01` referenziert stattdessen den zuerst gefundenen Port `Abgasnachbehandlung_1`.
4. Dieselbe Port-ID wird damit für das getrennte Backbone `Antriebsstrang_01-S01` und den lokalen I/O-Bus verwendet.

Insgesamt betrifft diese Mehrfachverwendung **14 kanonische Hardware-Interfaces**. Bei LIN treten außerdem Fälle auf, in denen ein `LIN_IO`-Interface zugleich die separat erzeugten Segmente `S01` und `S02` vertritt. Die vollständigen IDs und Netze sind in der Ergebnisdatei dokumentiert.

**Auswirkung:** Die Topologie sieht segmentiert aus, während ihre kanonische Portbindung teilweise mehrere Segmente zusammenfasst oder den falschen Port auswählt. Dies ist eine Inkonsistenz mit Konsequenzen für Portauslastung, Kanalanzahl, Routingprüfung und Simulation. Welche konkreten Kapazitätswerte dadurch bereits verfälscht sind, muss die übergreifende Transport-/Workflow-Prüfung feststellen.

**Lösung:** Die freigegebenen Routing-Port-IDs unverändert in die Topologie übernehmen. Wenn physische Segmentierung zusätzliche Hardwarekanäle verlangt, diese als eigenständige kanonische Hardware-Interfaces mit Netzwerkbindung und Fähigkeiten vorschlagen und vor Topologieerzeugung validieren. Kein Fallback auf einen beliebigen anderen Port, wenn die passende Bindung fehlt. Falls mehrere Netze auf einem Port tatsächlich ein bewusstes Multiplexing-Konzept darstellen sollen, muss dieses explizit modelliert und überprüfbar sein.

**Abnahme:** Beim EGR-Beispiel stimmt die ECU-Port-ID in Route, Topologie, Hardware-Interface-Tabelle und Kapazitätsansicht exakt überein. Jeder getrennte Buskanal ist im Hardwaremodell vorhanden. Bestehende Mehrfachverwendungen sind entweder explizit als unterstützte gemeinsame Nutzung modelliert oder verschwinden. Änderungen an der Reihenfolge der Hardware-Interfaces dürfen die Topologie nicht verändern.

## 6. P2: Zwei Interface-Begriffe sind berechtigt, werden aber unzureichend erklärt

Die **326 Hardware-Interfaces** und **326 logischen Interfaces** sind nicht allein aufgrund ihrer gleichen Anzahl Dubletten. Im aktuellen Modell haben sie verschiedene Aufgaben:

- **Physischer Anschluss / Hardware-Interface:** Welches Gerät kommuniziert über welchen Kanal, welche Technologie, Bitrate und welches Netzwerk?
- **Logischer Kommunikationszugang / Interface:** Zu welcher Funktion oder zu welchem direkten Gerät gehört eine Gruppe von Nachrichten?
- Eine Nachricht bindet beide Seiten über `interface_id` und `hardware_interface_id` zusammen ([wizard_generation.py:252](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/agent_tools/wizard_generation.py:252)).

Im Screenshot ist `Abgasnachbehandlung 1` der logische Kommunikationszugang der Steuerungsfunktion. `CAN FD IO` und `LIN IO` sind zusätzliche logische Zugänge für die lokale Kommunikation. Der Structure Tree zeigt die Hardware-Interface-Ebene überhaupt nicht, obwohl direkt daneben ein gleich klingender Reiter steht. Hinzu kommen generische Namen wie `_1`, die weder Richtung noch Aufgabe erklären.

**Lösung:** Einheitlich „Physische Anschlüsse“ und „Logische Schnittstellen“ verwenden, jeweils mit kurzem Hilfetext. In Nachrichten die konkrete Verbindung beider Ebenen zeigen. In der Standardansicht Hardware/System und Signale verständlich gruppieren; technische Schnittstellenebenen bei Bedarf aufklappen. Namen um Zweck und Netzwerk ergänzen, ohne technische IDs umzubenennen. Nicht jede mögliche Schicht als verpflichtende Stufe eines einzigen linearen Baums präsentieren.

**Abnahme:** Ein Nutzer kann vom EGR-Signal die Quelle, die zugehörige ECU, die Nachricht und den tatsächlichen Busanschluss erreichen. Derselbe fachliche Pfad erscheint in Wizard, Tree und Tabellen mit denselben Bezeichnungen und IDs.

## Empfohlene Umsetzungsreihenfolge

1. Gemeinsamen Beziehungskontrakt und Resolver festlegen: direkte Hardware-Eltern, Funktions-Eltern und unabhängige Systemmitgliedschaft.
2. Tree, Signalspalte, Formulare und Structure Wizard auf diesen Vertrag umstellen; sichtbare falsche Waisen beseitigen.
3. Akzeptierte Wizard-Zuordnungen eindeutig in versionierte ID-Beziehungen überführen und alle Ansichten daraus bedienen.
4. Route-/Topologie-/Portbindung korrigieren und die 14 dokumentierten Fälle als Regressionstests verwenden.
5. Den vollständigen exemplarischen Pfad EGR-Sensor → Abgas-ECU → reale Portbindung → Nachrichten/Signale → Simulation → Agentenänderung mit erneuter Validierung abnehmen. Die übergreifende Agenten- und Workflowprüfung liefert die zusätzlichen Kriterien dafür.

Die vorhandenen Einzelsuites sollten um Tests erweitert werden, die denselben Export durch mehrere Oberflächen und Dienste verfolgen. Die jetzt gefundenen Fehler liegen überwiegend zwischen bereits einzeln funktionierenden Komponenten.
