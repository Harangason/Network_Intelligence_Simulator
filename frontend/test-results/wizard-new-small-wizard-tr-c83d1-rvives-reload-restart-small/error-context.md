# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: wizard.spec.ts >> new small wizard traverses all nine stages and survives reload/restart @small
- Location: e2e\wizard.spec.ts:109:1

# Error details

```
TimeoutError: page.waitForResponse: Timeout 180000ms exceeded while waiting for event "response"
```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - main [ref=e2]:
    - generic [ref=e3]:
      - link "Communication Simulator Network trace studio" [ref=e4] [cursor=pointer]:
        - /url: /?project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
        - generic [aria-hidden] [ref=e5]: CS
        - generic [ref=e6]:
          - strong [ref=e7]: Communication Simulator
          - generic [ref=e8]: Network trace studio
      - button "Zurück zum Auftrag" [ref=e10] [cursor=pointer]:
        - generic [aria-hidden] [ref=e11]: ←
        - text: Zurück zum Auftrag
      - generic [ref=e12]:
        - generic [ref=e13]:
          - button "Neu" [ref=e14] [cursor=pointer]
          - button "Clear" [ref=e15] [cursor=pointer]
          - button "Speichern" [ref=e16] [cursor=pointer]
          - button "Öffnen" [ref=e17] [cursor=pointer]
          - button "Projekt aktualisieren" [ref=e18] [cursor=pointer]
        - button "Loggen an" [ref=e19] [cursor=pointer]
        - button "Importieren" [ref=e21] [cursor=pointer]
        - link "Einstellungen" [ref=e22] [cursor=pointer]:
          - /url: /studio/settings?project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
        - generic "Backend-Build 66310df778f1; Frontend und Backend stimmen überein." [ref=e23]:
          - text: Python engine
          - generic [ref=e25]: · 66310df778f1
    - region "Verbindlicher Engineering-Workflow" [ref=e26]:
      - generic [ref=e27]:
        - generic [ref=e28]:
          - generic [ref=e29]: Project workflow
          - strong [ref=e30]: Define → Route → Connect → Configure → Calculate → Validate → Simulate → Analyze → Assess
        - 'generic "Technische Projekt-ID: nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e" [ref=e32]': "Projekt: E2E small"
      - navigation [ref=e33]:
        - link "1 Engineering-Modell Vollständig" [ref=e34] [cursor=pointer]:
          - /url: /studio/engineering?project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
          - generic [ref=e35]: "1"
          - generic [ref=e36]:
            - strong [ref=e37]: Engineering-Modell
            - generic [ref=e38]: Vollständig
        - link "2 Routing-Tabelle Leer" [ref=e40] [cursor=pointer]:
          - /url: /studio/routing?project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
          - generic [ref=e41]: "2"
          - generic [ref=e42]:
            - strong [ref=e43]: Routing-Tabelle
            - generic [ref=e44]: Leer
        - link "3 Netzwerk-Editor Leer" [ref=e46] [cursor=pointer]:
          - /url: /studio?mode=network&project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
          - generic [ref=e47]: "3"
          - generic [ref=e48]:
            - strong [ref=e49]: Netzwerk-Editor
            - generic [ref=e50]: Leer
        - link "4 Parameter In Arbeit" [ref=e52] [cursor=pointer]:
          - /url: /studio?mode=parameters&project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
          - generic [ref=e53]: "4"
          - generic [ref=e54]:
            - strong [ref=e55]: Parameter
            - generic [ref=e56]: In Arbeit
        - link "5 Capacity & Timing Leer" [ref=e58] [cursor=pointer]:
          - /url: /studio/capacity?project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
          - generic [ref=e59]: "5"
          - generic [ref=e60]:
            - strong [ref=e61]: Capacity & Timing
            - generic [ref=e62]: Leer
        - link "6 Validation / Preflight Leer" [ref=e64] [cursor=pointer]:
          - /url: /studio/validation?project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
          - generic [ref=e65]: "6"
          - generic [ref=e66]:
            - strong [ref=e67]: Validation / Preflight
            - generic [ref=e68]: Leer
        - link "7 Simulation Leer" [ref=e70] [cursor=pointer]:
          - /url: /studio/simulation?project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
          - generic [ref=e71]: "7"
          - generic [ref=e72]:
            - strong [ref=e73]: Simulation
            - generic [ref=e74]: Leer
        - link "8 Results / Analysis Leer" [ref=e76] [cursor=pointer]:
          - /url: /studio/results?project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
          - generic [ref=e77]: "8"
          - generic [ref=e78]:
            - strong [ref=e79]: Results / Analysis
            - generic [ref=e80]: Leer
        - link "9 Data Science & Intelligence Leer" [ref=e82] [cursor=pointer]:
          - /url: /studio/intelligence?project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
          - generic [ref=e83]: "9"
          - generic [ref=e84]:
            - strong [ref=e85]: Data Science & Intelligence
            - generic [ref=e86]: Leer
    - generic [ref=e88]:
      - generic [ref=e89]:
        - paragraph [ref=e90]: Engineering-Modell
        - heading "Hardware, Interfaces und Signale verwalten." [level=1] [ref=e91]
      - button "Übersicht aufklappen" [ref=e92] [cursor=pointer]:
        - generic [aria-hidden] [ref=e94]: ⌄
    - generic [ref=e96]:
      - generic [ref=e98]:
        - paragraph [ref=e99]: Kanonisches Modell
        - heading "Hardware-Knoten" [level=2] [ref=e100]
      - generic [ref=e101]:
        - tablist "Objekttypen" [ref=e102]:
          - tab "Hardware-Knoten" [selected] [ref=e103] [cursor=pointer]
          - tab "Physische Anschlüsse" [ref=e104] [cursor=pointer]
          - tab "Funktionen" [ref=e105] [cursor=pointer]
          - tab "Kommunikationsschnittstellen" [ref=e106] [cursor=pointer]
          - tab "Nachrichten" [ref=e107] [cursor=pointer]
          - tab "Signale" [ref=e108] [cursor=pointer]
          - tab "Structure Tree" [ref=e110] [cursor=pointer]
        - button "Reparatur-Agent" [ref=e111] [cursor=pointer]
      - generic [ref=e115]:
        - generic [ref=e116]:
          - paragraph [ref=e117]: Objekt-Wizard
          - strong [ref=e118]: Hardware-Knoten geführt anlegen
          - generic [ref=e119]: Identität → Zuordnung → technische Details → Prüfung
        - button "Wizard starten" [ref=e120] [cursor=pointer]
      - group "Hardware-Typ auswählen" [ref=e121]:
        - button "+ ECU" [ref=e122] [cursor=pointer]
        - button "+ Gateway" [ref=e123] [cursor=pointer]
        - button "+ Sensor" [ref=e124] [cursor=pointer]
        - button "+ Aktor" [ref=e125] [cursor=pointer]
      - generic [ref=e126]:
        - table [ref=e127]:
          - rowgroup [ref=e128]:
            - row [ref=e129]:
              - columnheader [ref=e130]:
                - button "Name sortieren" [ref=e131] [cursor=pointer]:
                  - generic [ref=e132]: Name
                  - generic [aria-hidden] [ref=e133]: ↕
              - columnheader [ref=e134]:
                - button "Gerätetyp sortieren" [ref=e135] [cursor=pointer]:
                  - generic [ref=e136]: Gerätetyp
                  - generic [aria-hidden] [ref=e137]: ↕
              - columnheader [ref=e138]:
                - button "Diagnoseadresse sortieren" [ref=e139] [cursor=pointer]:
                  - generic [ref=e140]: Diagnoseadresse
                  - generic [aria-hidden] [ref=e141]: ↕
              - columnheader [ref=e142]:
                - button "Class sortieren" [ref=e143] [cursor=pointer]:
                  - generic [ref=e144]: Class
                  - generic [aria-hidden] [ref=e145]: ↕
              - columnheader [ref=e146]:
                - button "Typisierung sortieren" [ref=e147] [cursor=pointer]:
                  - generic [ref=e148]: Typisierung
                  - generic [aria-hidden] [ref=e149]: ↕
              - columnheader [ref=e150]:
                - button "Domäne sortieren" [ref=e151] [cursor=pointer]:
                  - generic [ref=e152]: Domäne
                  - generic [aria-hidden] [ref=e153]: ↕
              - columnheader [ref=e154]:
                - button "Beschreibung sortieren" [ref=e155] [cursor=pointer]:
                  - generic [ref=e156]: Beschreibung
                  - generic [aria-hidden] [ref=e157]: ↕
              - columnheader [ref=e158]:
                - button "Warnung sortieren" [ref=e159] [cursor=pointer]:
                  - generic [ref=e160]: Warnung
                  - generic [aria-hidden] [ref=e161]: ↕
            - row [ref=e162]:
              - columnheader [ref=e163]:
                - searchbox "Name filtern" [ref=e164]
              - columnheader [ref=e165]:
                - searchbox "Gerätetyp filtern" [ref=e166]
              - columnheader [ref=e167]:
                - searchbox "Diagnoseadresse filtern" [ref=e168]
              - columnheader [ref=e169]:
                - searchbox "Class filtern" [ref=e170]
              - columnheader [ref=e171]:
                - searchbox "Typisierung filtern" [ref=e172]
              - columnheader [ref=e173]:
                - searchbox "Domäne filtern" [ref=e174]
              - columnheader [ref=e175]:
                - searchbox "Beschreibung filtern" [ref=e176]
              - columnheader [ref=e177]:
                - searchbox "Warnung filtern" [ref=e178]
          - rowgroup [ref=e179]:
            - row [ref=e180] [cursor=pointer]:
              - cell "Drehmomentkoordination" [ref=e181]
              - cell "ECU" [ref=e182]
              - cell "0x0002" [ref=e183]
              - cell "4" [ref=e184]
              - cell "Intelligent Subsystem" [ref=e185]
              - cell "—" [ref=e186]
              - cell "Aus dem geforderten Automotive-Skalierungsziel abgeleiteter Systemrahmen mit Rolle ECU." [ref=e187]
              - cell [ref=e188]:
                - button "Kommunikationswarnungen für Drehmomentkoordination" [ref=e189]:
                  - generic [ref=e192]: "2"
            - row [ref=e193] [cursor=pointer]:
              - cell "FrontLeftWheelSpeed" [ref=e194]
              - cell "Sensor Controller" [ref=e195]
              - cell "nicht adressierbar" [ref=e196]
              - cell "1" [ref=e197]
              - cell "Basic Sensor" [ref=e198]
              - cell "—" [ref=e199]
              - cell "Aus dem geforderten Automotive-Skalierungsziel abgeleiteter Systemrahmen mit Rolle SensorController." [ref=e200]
              - cell [ref=e201]:
                - button "Kommunikationswarnungen für FrontLeftWheelSpeed" [ref=e202]:
                  - generic [ref=e205]: "2"
            - row [ref=e206] [cursor=pointer]:
              - cell "KuehlkreislaufsteuerungStellglied" [ref=e207]
              - cell "Actuator Controller" [ref=e208]
              - cell "nicht adressierbar" [ref=e209]
              - cell "1" [ref=e210]
              - cell "Basic Actuator" [ref=e211]
              - cell "—" [ref=e212]
              - cell "Aus dem geforderten Automotive-Skalierungsziel abgeleiteter Systemrahmen mit Rolle ActuatorController." [ref=e213]
              - cell [ref=e214]:
                - button "Kommunikationswarnungen für KuehlkreislaufsteuerungStellglied" [ref=e215]:
                  - generic [ref=e218]: "2"
            - row [ref=e219] [cursor=pointer]:
              - cell "Stabilitaetsregelung" [ref=e220]
              - cell "ECU" [ref=e221]
              - cell "0x0003" [ref=e222]
              - cell "4" [ref=e223]
              - cell "Intelligent Subsystem" [ref=e224]
              - cell "—" [ref=e225]
              - cell "Aus dem geforderten Automotive-Skalierungsziel abgeleiteter Systemrahmen mit Rolle ECU." [ref=e226]
              - cell [ref=e227]:
                - button "Kommunikationswarnungen für Stabilitaetsregelung" [ref=e228]:
                  - generic [ref=e231]: "3"
            - row [ref=e232] [cursor=pointer]:
              - cell "Kuehlkreislaufsteuerung" [ref=e233]
              - cell "ECU" [ref=e234]
              - cell "0x0001" [ref=e235]
              - cell "4" [ref=e236]
              - cell "Intelligent Subsystem" [ref=e237]
              - cell "—" [ref=e238]
              - cell "Aus dem geforderten Automotive-Skalierungsziel abgeleiteter Systemrahmen mit Rolle ECU." [ref=e239]
              - cell [ref=e240]:
                - button "Kommunikationswarnungen für Kuehlkreislaufsteuerung" [ref=e241]:
                  - generic [ref=e244]: "5"
            - row [ref=e245] [cursor=pointer]:
              - cell "System" [ref=e246]
              - cell "Gateway" [ref=e247]
              - cell "0x0004" [ref=e248]
              - cell "4" [ref=e249]
              - cell "Intelligent Subsystem" [ref=e250]
              - cell "—" [ref=e251]
              - cell "Aus dem geforderten Automotive-Skalierungsziel abgeleiteter Systemrahmen mit Rolle Gateway." [ref=e252]
              - cell [ref=e253]:
                - button "Kommunikationswarnungen für System" [ref=e254]:
                  - generic [ref=e257]: "3"
        - generic [ref=e258]:
          - generic [ref=e259]: 1-6 von 6 Einträgen · 50 pro Seite
          - generic [ref=e260]:
            - button "Zurück" [disabled] [ref=e261]
            - generic [ref=e262]: Seite 1 von 1
            - button "Weiter" [disabled] [ref=e263]
    - dialog [ref=e264]:
      - generic [ref=e265]:
        - generic [ref=e266]:
          - paragraph [ref=e267]: Geführte Anlage
          - heading "Engineering-Auftrag erstellen" [level=2] [ref=e268]
          - text: Technische Vorgaben festlegen und anschließend vom Agenten ausführen lassen.
        - button "Wizard schließen" [ref=e269] [cursor=pointer]: ×
      - region "Geführte Agent-Rückfrage" [ref=e270]:
        - generic [ref=e271]:
          - generic [ref=e272]:
            - strong [ref=e273]: Technische Vorgaben
            - generic [ref=e274]: "Statusübersicht: Schritt 6 von 6"
          - generic [ref=e275]: Angehalten
        - generic "Rückfrage-Schritte" [ref=e277]:
          - button "1" [disabled] [ref=e278] [cursor=pointer]
          - button "2" [disabled] [ref=e279] [cursor=pointer]
          - button "3" [disabled] [ref=e280] [cursor=pointer]
          - button "4" [disabled] [ref=e281] [cursor=pointer]
          - button "5" [disabled] [ref=e282] [cursor=pointer]
          - button "6" [disabled] [ref=e283] [cursor=pointer]
        - region "Statusübersicht des Engineering-Auftrags" [ref=e284]:
          - generic [ref=e285]:
            - generic [ref=e286]:
              - generic [ref=e287]: Erste Analyse
              - strong [ref=e288]: Auftrag angehalten
              - generic "Gefundene Engineering-Objekte" [ref=e289]:
                - generic [ref=e290]:
                  - generic [ref=e291]: Gateways
                  - generic [ref=e292]: "1"
                  - emphasis: 1 erkannte Hardware-Teilnehmer. Die Device Class entscheidet, ob daraus eine eigene Funktion wird.
                - generic [ref=e293]:
                  - generic [ref=e294]: Controller
                  - generic [ref=e295]: "3"
                  - emphasis: 3 erkannte Hardware-Teilnehmer. Die Device Class entscheidet, ob daraus eine eigene Funktion wird.
                - generic [ref=e296]:
                  - generic [ref=e297]: Sensoren
                  - generic [ref=e298]: "1"
                  - emphasis: 1 erkannte Hardware-Teilnehmer. Die Device Class entscheidet, ob daraus eine eigene Funktion wird.
                - generic [ref=e299]:
                  - generic [ref=e300]: Aktoren
                  - generic [ref=e301]: "1"
                  - emphasis: 1 erkannte Hardware-Teilnehmer. Die Device Class entscheidet, ob daraus eine eigene Funktion wird.
                - generic [ref=e302]:
                  - generic [ref=e303]: Funktionen
                  - generic [ref=e304]: "4"
                  - emphasis: Soll nach Class-Modell nur fuer Class 3/4 automatisch entstehen. Basic/Passive Sensoren und Aktoren bleiben ohne kuenstliche Function.
                - generic [ref=e305]:
                  - generic [ref=e306]: Interfaces
                  - generic [ref=e307]: "8"
                  - emphasis: Logische Interfaces werden je Teilnehmer oder Subsystem erzeugt. Direkte Hardware-Interfaces zaehlen separat im Hardware-Interface-Modell.
                - generic [ref=e308]:
                  - generic [ref=e309]: Nachrichten
                  - generic [ref=e310]: "7"
                  - emphasis: Gepackte Kommunikationsobjekte. Mehrere Signale koennen eine Nachricht teilen, wenn Bus, Zyklus und Producer passen.
                - generic [ref=e311]:
                  - generic [ref=e312]: Signale
                  - generic [ref=e313]: "24"
                  - emphasis: Einzelne Werte, Statuscodes, Commands oder Datenindikatoren innerhalb der Nachrichten.
                - generic [ref=e314]:
                  - generic [ref=e315]: Netzverbindungen
                  - generic [ref=e316]: "4"
                  - emphasis: Geplante physische oder logische Netzpfade aus Architektur, Clustern und Teilnehmerumfang.
                - generic [ref=e317]:
                  - generic [ref=e318]: Routen
                  - generic [ref=e319]: "0"
                  - emphasis: Vorbereitete Routing-Pfade, die vor der Uebernahme validiert und freigegeben werden muessen.
              - generic "Angelegte Geräte" [ref=e320]:
                - group [ref=e321]:
                  - generic "Gateways · 1" [ref=e322] [cursor=pointer]
                - group [ref=e323]:
                  - generic "Controller · 3" [ref=e324] [cursor=pointer]
                - group [ref=e325]:
                  - generic "Sensoren · 1" [ref=e326] [cursor=pointer]
                - group [ref=e327]:
                  - generic "Aktoren · 1" [ref=e328] [cursor=pointer]
              - button "Ergänzen" [ref=e330] [cursor=pointer]
            - generic [ref=e331]:
              - strong [ref=e332]: 11 %
              - generic [ref=e333]: Gesamtfortschritt
              - progressbar "Gesamtfortschritt 11 Prozent" [ref=e334]
          - generic [ref=e335]:
            - generic [ref=e336]:
              - term [ref=e337]: Aktueller Schritt
              - definition [ref=e338]: Routing-Tabelle
            - generic [ref=e339]:
              - term [ref=e340]: Projektname
              - definition [ref=e341]: E2E small
            - generic [ref=e342]:
              - term [ref=e343]: Parameter
              - definition [ref=e344]: Technologie-Defaults verwenden
            - generic [ref=e345]:
              - term [ref=e346]: Arbeitsweise
              - definition [ref=e347]: Leere Pflichtfelder mit technologieabhängigen Defaults füllen · Selbstständig bis zum Human-Review-Gate arbeiten · Nach einer menschlichen Freigabe valide Vorschläge direkt übernehmen
            - generic [ref=e348]:
              - term [ref=e349]: Lauf-ID
              - definition [ref=e350]: e80248b1-543e-46af-8c9c-0e3f7463109b
          - generic "Fortschritt der neun Workflow-Ansichten" [ref=e351]:
            - link "Engineering-Modell öffnen, Status Vollständig, 100 Prozent" [ref=e352] [cursor=pointer]:
              - /url: /studio/engineering?project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
              - generic [ref=e353]:
                - generic [ref=e354]: "1"
                - strong [ref=e355]: Engineering-Modell
                - generic [ref=e356]: 100 %
              - 'progressbar "Engineering-Modell: 100 Prozent" [ref=e357]'
              - generic [ref=e358]: Vollständig · im Auftrag
            - link "Routing-Tabelle öffnen, Status Angehalten, 0 Prozent" [ref=e359] [cursor=pointer]:
              - /url: /studio/routing?project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
              - generic [ref=e360]:
                - generic [ref=e361]: "2"
                - strong [ref=e362]: Routing-Tabelle
                - generic [ref=e363]: 0 %
              - 'progressbar "Routing-Tabelle: 0 Prozent" [ref=e364]'
              - generic [ref=e365]: Angehalten · im Auftrag
            - link "Netzwerk-Editor öffnen, Status Leer, 0 Prozent" [ref=e366] [cursor=pointer]:
              - /url: /studio?mode=network&project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
              - generic [ref=e367]:
                - generic [ref=e368]: "3"
                - strong [ref=e369]: Netzwerk-Editor
                - generic [ref=e370]: 0 %
              - 'progressbar "Netzwerk-Editor: 0 Prozent" [ref=e371]'
              - generic [ref=e372]: Leer · im Auftrag
            - link "Parameter öffnen, Status In Arbeit, 0 Prozent" [ref=e373] [cursor=pointer]:
              - /url: /studio?mode=parameters&project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
              - generic [ref=e374]:
                - generic [ref=e375]: "4"
                - strong [ref=e376]: Parameter
                - generic [ref=e377]: 0 %
              - 'progressbar "Parameter: 0 Prozent" [ref=e378]'
              - generic [ref=e379]: In Arbeit · im Auftrag
            - link "Capacity & Timing öffnen, Status Leer, 0 Prozent" [ref=e380] [cursor=pointer]:
              - /url: /studio/capacity?project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
              - generic [ref=e381]:
                - generic [ref=e382]: "5"
                - strong [ref=e383]: Capacity & Timing
                - generic [ref=e384]: 0 %
              - 'progressbar "Capacity & Timing: 0 Prozent" [ref=e385]'
              - generic [ref=e386]: Leer · im Auftrag
            - link "Validation / Preflight öffnen, Status Leer, 0 Prozent" [ref=e387] [cursor=pointer]:
              - /url: /studio/validation?project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
              - generic [ref=e388]:
                - generic [ref=e389]: "6"
                - strong [ref=e390]: Validation / Preflight
                - generic [ref=e391]: 0 %
              - 'progressbar "Validation / Preflight: 0 Prozent" [ref=e392]'
              - generic [ref=e393]: Leer · im Auftrag
            - link "Simulation öffnen, Status Leer, 0 Prozent" [ref=e394] [cursor=pointer]:
              - /url: /studio/simulation?project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
              - generic [ref=e395]:
                - generic [ref=e396]: "7"
                - strong [ref=e397]: Simulation
                - generic [ref=e398]: 0 %
              - 'progressbar "Simulation: 0 Prozent" [ref=e399]'
              - generic [ref=e400]: Leer · im Auftrag
            - link "Results / Analysis öffnen, Status Leer, 0 Prozent" [ref=e401] [cursor=pointer]:
              - /url: /studio/results?project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
              - generic [ref=e402]:
                - generic [ref=e403]: "8"
                - strong [ref=e404]: Results / Analysis
                - generic [ref=e405]: 0 %
              - 'progressbar "Results / Analysis: 0 Prozent" [ref=e406]'
              - generic [ref=e407]: Leer · im Auftrag
            - link "Data Science & Intelligence öffnen, Status Leer, 0 Prozent" [ref=e408] [cursor=pointer]:
              - /url: /studio/intelligence?project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e
              - generic [ref=e409]:
                - generic [ref=e410]: "9"
                - strong [ref=e411]: Data Science & Intelligence
                - generic [ref=e412]: 0 %
              - 'progressbar "Data Science & Intelligence: 0 Prozent" [ref=e413]'
              - generic [ref=e414]: Leer · im Auftrag
          - generic [ref=e416]:
            - generic [ref=e417]: Rückfragen
            - strong [ref=e418]: Auftrag angehalten
            - generic [ref=e419]: "Der serverseitige Routing-Generator konnte den bestätigten Auftrag nicht umsetzen. Stabilitaetsregelung: logische Schnittstelle ist mehrdeutig (Stabilitaetsregelung_CAN_FD_IO, Stabilitaetsregelung). Empfangende Funktion/Schnittstelle explizit auswählen."
            - button "Auftrag fortsetzen" [ref=e420] [cursor=pointer]
          - region "Engineering-Vorschlag" [ref=e421]:
            - strong [ref=e422]: Übernommen
            - paragraph [ref=e423]: "Engineering-Modell aus bestätigten Wizard-Vorgaben: 62 vorgeschlagene Änderungen. Noch keine Änderungen am kanonischen Modell; Freigabe und Übernahme sind erforderlich."
            - paragraph [ref=e424]: 62 Änderungen
            - group [ref=e425]:
              - generic "Änderungen prüfen" [ref=e426] [cursor=pointer]
            - group [ref=e427]:
              - generic "Annahmen (5)" [ref=e428] [cursor=pointer]
            - navigation "Betroffene Modellobjekte" [ref=e429]:
              - link "Kuehlkreislaufsteuerung" [ref=e430] [cursor=pointer]:
                - /url: /studio/engineering?project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e&resource=hardware-nodes&object=8b24825f-5e4d-428f-8852-a3c5b36d3430
              - link "Drehmomentkoordination" [ref=e431] [cursor=pointer]:
                - /url: /studio/engineering?project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e&resource=hardware-nodes&object=2c841c0b-973d-4d86-ab34-06bd28974ab7
              - link "Stabilitaetsregelung" [ref=e432] [cursor=pointer]:
                - /url: /studio/engineering?project=nis-e2e-small-ed4c2ee7-8cf2-45d3-8e1b-961af011443e&resource=hardware-nodes&object=886b7428-42e1-41cc-836e-9471b3df6a4d
              - group [ref=e433]:
                - generic "59 weitere Objekte" [ref=e434] [cursor=pointer]
            - paragraph [ref=e435]: 62 Modellobjekte bestätigt.
          - generic "Aktuelle Containerauslastung" [ref=e436]:
            - generic [ref=e437]:
              - generic [ref=e438]: CPU · Container
              - strong [ref=e439]: 1.5 %
            - generic [ref=e440]:
              - generic [ref=e441]: RAM · Container
              - strong [ref=e442]: 8.8 %
            - generic [ref=e443]:
              - generic [ref=e444]: GPU · PC
              - strong [ref=e445]: nicht verfügbar
            - generic [ref=e446]:
              - generic [ref=e447]: VRAM · PC
              - strong [ref=e448]: nicht verfügbar
            - generic [ref=e449]:
              - generic [ref=e450]: Analyse
              - strong [ref=e451]: Regelwerk + KI bei Bedarf
            - generic [ref=e452]:
              - generic [ref=e453]: LLM
              - strong [ref=e454]: "Standby: qwen3.8:27b"
          - generic [ref=e455]:
            - generic [ref=e456]: "TXT-Protokolle aktiv: Workflow · Rückfragen · Performance · Fehler"
            - generic [ref=e457]:
              - button "Abbrechen" [ref=e458] [cursor=pointer]
              - button "Fertig stellen" [disabled] [ref=e459]
  - complementary "Engineering-Assistent":
    - button "AI Assistant öffnen" [ref=e460] [cursor=pointer]
  - alert [ref=e462]
```

# Test source

```ts
  1   | import { test, expect, type Page } from 'playwright/test';
  2   | import { readFile } from 'node:fs/promises';
  3   | import { randomUUID } from 'node:crypto';
  4   | import { execFileSync } from 'node:child_process';
  5   | 
  6   | const steps = ['engineering_model', 'routing', 'network_editor', 'parameters', 'capacity_timing',
  7   |   'validation', 'simulation', 'results_analysis', 'data_science_intelligence'];
  8   | const done = new Set(['COMPLETE', 'APPROVED', 'WARNING']);
  9   | 
  10  | async function readProject(page: Page, project: string, path: string) {
  11  |   const result = await page.request.get(path, { headers: { 'X-Project-ID': project }, timeout: 60_000 });
  12  |   expect(result.ok(), await result.text()).toBeTruthy();
  13  |   return result.json();
  14  | }
  15  | 
  16  | async function openWizard(page: Page, project: string) {
  17  |   await page.goto(`/studio/engineering?assistant=project&project=${project}`, { waitUntil: 'load' });
  18  |   const dialog = page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' });
  19  |   await expect(dialog).toBeVisible();
  20  |   return dialog;
  21  | }
  22  | 
  23  | async function verifyArtifacts(page: Page, project: string, minimumSignals: number) {
  24  |   const workflow = await readProject(page, project, '/api/engineering/workflow?view=summary');
  25  |   expect(Object.keys(workflow.statuses).sort()).toEqual([...steps].sort());
  26  |   for (const step of steps) expect(done.has(workflow.statuses[step]), `${step}: ${workflow.statuses[step]}`).toBeTruthy();
  27  |   const jobs = (await readProject(page, project, '/api/simulations')).jobs;
  28  |   expect(jobs).toHaveLength(1);
  29  |   expect(jobs[0].status).toBe('completed');
  30  |   const snapshots = await readProject(page, project, '/api/engineering/workflow/snapshots');
  31  |   const snapshot = snapshots.simulations.find((item: { job_id: string }) => item.job_id === jobs[0].id);
  32  |   expect(snapshot).toBeTruthy();
  33  |   const full = await readProject(page, project, `/api/engineering/workflow/simulation-snapshots/${snapshot.id}`);
  34  |   const assessment = full.result.assessment;
  35  |   expect(assessment.scope_coverage.scope_mode).toBe('ALL');
  36  |   expect(assessment.scope_coverage.complete).toBe(true);
  37  |   expect(assessment.conformance).toBe('PASS');
  38  |   expect(assessment.failed_route_count).toBe(0);
  39  |   expect(assessment.observed_signal_count).toBeGreaterThanOrEqual(minimumSignals);
  40  |   for (const key of ['missing_observed_signal_ids', 'missing_observed_route_ids', 'missing_observed_network_ids']) expect(assessment[key]).toEqual([]);
  41  |   const trace = await readProject(page, project, `/api/simulations/${jobs[0].id}/trace-window?limit=10`);
  42  |   expect(trace.count).toBeGreaterThan(0);
  43  |   expect(trace.events.some((item: { signals?: unknown[] }) => item.signals && Object.keys(item.signals).length)).toBeTruthy();
  44  |   return { workflow, job: jobs[0].id, assessment };
  45  | }
  46  | 
  47  | async function completeThroughWizard(page: Page, project: string, restart: boolean) {
  48  |   let reviewCount = 0;
  49  |   let runId: string | undefined;
  50  |   const reviewed = new Set<string>();
  51  |   for (let checkpoint = 0; checkpoint < 16; checkpoint++) {
  52  |     let workflow: any;
  53  |     await expect.poll(async () => {
  54  |       workflow = await readProject(page, project, '/api/engineering/workflow?view=summary');
  55  |       return steps.every(step => done.has(workflow.statuses[step]))
  56  |         || ['REVIEW_REQUIRED', 'READY_TO_CONTINUE', 'BLOCKED', 'FAILED', 'INCOMPLETE'].includes(workflow.context.agent_execution?.state);
  57  |     }, { timeout: 240_000, intervals: [500, 1000, 2000] }).toBe(true);
  58  |     runId ??= workflow.context.agent_execution?.run_id;
  59  |     expect(workflow.context.agent_execution?.run_id).toBe(runId);
  60  |     if (steps.every(step => done.has(workflow.statuses[step]))) return { runId, reviewed: [...reviewed] };
  61  |     const execution = workflow.context.agent_execution;
  62  |     const dialog = page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' });
  63  |     if (['BLOCKED', 'FAILED', 'INCOMPLETE'].includes(execution?.state)) {
  64  |       const conversation = await readProject(page, project, '/api/engineering/agent/conversation');
  65  |       const id = conversation.data?.active_proposal;
  66  |       const proposal = id ? await readProject(page, project, `/api/engineering/agent/proposals/${id}`) : null;
  67  |       throw new Error(JSON.stringify({ execution, proposal: proposal?.data?.validation_result, visible: await dialog.innerText() }));
  68  |     }
  69  |     if (execution?.state === 'READY_TO_CONTINUE') {
  70  |       const button = dialog.getByRole('button', { name: 'Auftrag fortsetzen', exact: true });
  71  |       await expect(button).toBeEnabled();
  72  |       await button.click();
  73  |       await expect.poll(async () => (await readProject(page, project, '/api/engineering/workflow?view=summary')).context.agent_execution?.updated_at,
  74  |         { timeout: 60_000 }).not.toBe(execution.updated_at);
  75  |       continue;
  76  |     }
  77  |     const conversation = await readProject(page, project, '/api/engineering/agent/conversation');
  78  |     const proposalId = conversation.data.active_proposal;
  79  |     expect(reviewed.has(proposalId), 'The same proposal must not request review twice.').toBe(false);
> 80  |     const applyResponse = page.waitForResponse(response => response.url().includes(`/proposals/${proposalId}/apply`) && response.request().method() === 'POST', { timeout: 180_000 });
      |                                ^ TimeoutError: page.waitForResponse: Timeout 180000ms exceeded while waiting for event "response"
  81  |     const approval = dialog.getByRole('button', { name: /^(Freigeben, übernehmen & fortfahren|Übernehmen & fortfahren)$/ });
  82  |     await expect(approval).toBeEnabled({ timeout: 60_000 });
  83  |     await approval.click();
  84  |     const applied = await applyResponse;
  85  |     expect(applied.ok(), await applied.text()).toBeTruthy();
  86  |     expect((await applied.json()).data.status).toBe('APPLIED');
  87  |     reviewed.add(proposalId); reviewCount++;
  88  |     if (reviewCount === 1) await openWizard(page, project); // Durable reload after a real commit.
  89  |     if (restart && reviewCount === 2) {
  90  |       const container = process.env.NIS_E2E_APP_CONTAINER!;
  91  |       expect(container).toMatch(/^nis-e2e-app-[a-f0-9]+$/);
  92  |       const docker = process.env.NIS_TEST_DOCKER || 'docker';
  93  |       const label = execFileSync(docker, ['inspect', container, '--format', '{{index .Config.Labels "networkis.test"}}'], { encoding: 'utf8' }).trim();
  94  |       expect(label).toBe('disposable');
  95  |       execFileSync(docker, ['restart', container]);
  96  |       await expect.poll(async () => {
  97  |         try { return (await page.request.get('/api/ready', { timeout: 2000 })).ok(); } catch { return false; }
  98  |       }, { timeout: 120_000 }).toBe(true);
  99  |       await openWizard(page, project);
  100 |     }
  101 |     await expect.poll(async () => {
  102 |       const current = await readProject(page, project, '/api/engineering/workflow?view=summary');
  103 |       return current.context.agent_execution?.updated_at !== execution.updated_at;
  104 |     }, { timeout: 60_000 }).toBe(true);
  105 |   }
  106 |   throw new Error('Wizard exceeded 16 review/continuation checkpoints.');
  107 | }
  108 | 
  109 | test('new small wizard traverses all nine stages and survives reload/restart @small', async ({ page }, testInfo) => {
  110 |   const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  111 |   const project = 'nis-e2e-small-' + randomUUID();
  112 |   const dialog = await openWizard(page, project);
  113 |   await dialog.getByTitle('Projektname', { exact: true }).click();
  114 |   await dialog.locator('#engineering-project-name').fill('E2E small');
  115 |   await dialog.getByTitle('Aufgabe', { exact: true }).click();
  116 |   await dialog.getByLabel('Aufgabentext', { exact: true }).fill('Erzeuge ein Automotive CAN-FD Netzwerk mit einem Gateway System, den ECUs Motorsteuerung und Anzeige, einem Sensor MotorTemperature und einem Aktor MotorValve. MotorTemperature wird von Motorsteuerung ausgewertet. Motorsteuerung steuert MotorValve. Statuswerte werden an Anzeige und System übermittelt. Prüfe und arbeite bis Data Science & Intelligence.');
  117 |   await dialog.getByLabel('Weitere Hinweise', { exact: true }).fill('- Aktor-Befehle: {"MotorValve":{"length_bits":1,"data_type":"boolean","factor":1,"unit":"code","min_value":0,"max_value":1,"semantic":{"semantic_type":"BOOLEAN"},"data":{"enum_values":{"CLOSE":0,"OPEN":1}}}}');
  118 |   await dialog.getByTitle('Geräteumfang', { exact: true }).click();
  119 |   for (const [label, value] of [['Gateways', '1'], ['Controller', '2'], ['Sensoren', '1'], ['Aktoren', '1']]) await dialog.getByLabel(`${label}: verbindliche Anzahl`, { exact: true }).fill(value);
  120 |   // Use the same visible questionnaire navigation a user uses; never inject generated model rows.
  121 |   for (let step = 0; step < 10; step++) {
  122 |     const submit = dialog.locator('.eng-agent-questionnaire-head').getByRole('button');
  123 |     await expect(submit).toBeEnabled();
  124 |     const name = await submit.innerText();
  125 |     await submit.click();
  126 |     if (name === 'Übernehmen') break;
  127 |     if (step === 9) throw new Error('Questionnaire did not offer submit.');
  128 |   }
  129 |   const continuity = await completeThroughWizard(page, project, true);
  130 |   const artifacts = await verifyArtifacts(page, project, 5);
  131 |   await openWizard(page, project);
  132 |   expect((await readProject(page, project, '/api/simulations')).jobs).toHaveLength(1);
  133 |   expect(errors).toEqual([]);
  134 |   await testInfo.attach('evidence', { body: JSON.stringify({ project, ...continuity, ...artifacts }), contentType: 'application/json' });
  135 | });
  136 | 
  137 | test('exact confirmed 50/250/250 request completes through real wizard review @large', async ({ page }, testInfo) => {
  138 |   const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  139 |   const project = 'nis-e2e-large-' + randomUUID();
  140 |   const runId = randomUUID();
  141 |   const original = await readFile(new URL('./fixtures/wizard-large-50-250-250.txt', import.meta.url), 'utf8');
  142 |   const metadata = JSON.parse(await readFile(new URL('./fixtures/wizard-large-50-250-250.json', import.meta.url), 'utf8'));
  143 |   const prompt = original.replace(/^- Lauf-ID:.*$/m, '- Lauf-ID: ' + runId);
  144 |   // Replay the captured, already confirmed input through the normal START API.
  145 |   // All proposal inspection, approval, continuation and reloads below use UI.
  146 |   const started = await page.request.post('/api/engineering/agent/chat', {
  147 |     headers: { 'X-Project-ID': project }, timeout: 240_000,
  148 |     data: { prompt, wizard_command: { action: 'START', run_id: runId, operation_id: randomUUID(),
  149 |       target: 'data_science_intelligence', wizard_context: { ...metadata.wizard_context, project_id: project, run_id: runId } } },
  150 |   });
  151 |   expect(started.ok(), await started.text()).toBeTruthy();
  152 |   await openWizard(page, project);
  153 |   const continuity = await completeThroughWizard(page, project, false);
  154 |   expect(continuity.runId).toBe(runId);
  155 |   const artifacts = await verifyArtifacts(page, project, 1404);
  156 |   expect(errors).toEqual([]);
  157 |   await testInfo.attach('evidence', { body: JSON.stringify({ project, fixture: metadata.request_sha256, ...continuity, ...artifacts }), contentType: 'application/json' });
  158 | });
  159 | 
```