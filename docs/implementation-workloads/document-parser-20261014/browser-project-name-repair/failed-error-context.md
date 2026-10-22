# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: document-intake.spec.ts >> document intake preserves complete requirements and reports unresolved scope @parser
- Location: e2e\document-intake.spec.ts:5:1

# Error details

```
TimeoutError: locator.click: Timeout 30000ms exceeded.
Call log:
  - waiting for getByRole('dialog', { name: 'Engineering-Auftrag erstellen' }).getByRole('button', { name: '4', exact: true })
    - locator resolved to <button class="" disabled type="button" title="Geräteumfang">4</button>
  - attempting click action
    2 × waiting for element to be visible, enabled and stable
      - element is not enabled
    - retrying click action
    - waiting 20ms
    2 × waiting for element to be visible, enabled and stable
      - element is not enabled
    - retrying click action
      - waiting 100ms
    48 × waiting for element to be visible, enabled and stable
       - element is not enabled
     - retrying click action
       - waiting 500ms

```

# Page snapshot

```yaml
- generic [ref=e1]:
  - main [ref=e2]:
    - generic [ref=e3]:
      - link "Communication Simulator Network trace studio" [ref=e4] [cursor=pointer]:
        - /url: /?project=nis-e2e-document-9d8ebd4b-ecbd-4433-9518-b7bbb6f048fb
        - generic [aria-hidden] [ref=e5]: CS
        - generic [ref=e6]:
          - strong [ref=e7]: Communication Simulator
          - generic [ref=e8]: Network trace studio
      - generic [ref=e9]:
        - generic [ref=e10]:
          - button "Clear" [ref=e11] [cursor=pointer]
          - button "Speichern" [ref=e12] [cursor=pointer]
          - button "Öffnen" [ref=e13] [cursor=pointer]
        - button "Importieren" [ref=e14] [cursor=pointer]
        - group "Erscheinungsbild" [ref=e15]:
          - button "Hell" [ref=e16] [cursor=pointer]
          - button "Dunkel" [pressed] [ref=e17] [cursor=pointer]
        - link "Einstellungen" [ref=e18] [cursor=pointer]:
          - /url: /studio/settings?project=nis-e2e-document-9d8ebd4b-ecbd-4433-9518-b7bbb6f048fb
        - generic "Backend-Build 19ebdcb753bb; Frontend und Backend stimmen überein." [ref=e19]:
          - text: Python engine
          - generic [ref=e21]: · 19ebdcb753bb
    - region "Verbindlicher Engineering-Workflow" [ref=e22]:
      - generic [ref=e23]:
        - generic [ref=e24]:
          - generic [ref=e25]: Project workflow
          - strong [ref=e26]: Define → Route → Connect → Configure → Calculate → Validate → Simulate → Analyze → Assess
        - 'generic "Technische Projekt-ID: nis-e2e-document-9d8ebd4b-ecbd-4433-9518-b7bbb6f048fb" [ref=e28]': "Projekt: nis-e2e-document-9d8ebd4b-ecbd-4433-9518-b7bbb6f048fb"
      - navigation [ref=e29]:
        - link "1 Engineering-Modell Leer" [ref=e30] [cursor=pointer]:
          - /url: /studio/engineering?project=nis-e2e-document-9d8ebd4b-ecbd-4433-9518-b7bbb6f048fb
          - generic [ref=e31]: "1"
          - generic [ref=e32]:
            - strong [ref=e33]: Engineering-Modell
            - generic [ref=e34]: Leer
        - link "2 Routing-Tabelle Leer" [ref=e36] [cursor=pointer]:
          - /url: /studio/routing?project=nis-e2e-document-9d8ebd4b-ecbd-4433-9518-b7bbb6f048fb
          - generic [ref=e37]: "2"
          - generic [ref=e38]:
            - strong [ref=e39]: Routing-Tabelle
            - generic [ref=e40]: Leer
        - link "3 Netzwerk-Editor Leer" [ref=e42] [cursor=pointer]:
          - /url: /studio?mode=network&project=nis-e2e-document-9d8ebd4b-ecbd-4433-9518-b7bbb6f048fb
          - generic [ref=e43]: "3"
          - generic [ref=e44]:
            - strong [ref=e45]: Netzwerk-Editor
            - generic [ref=e46]: Leer
        - link "4 Parameter Leer" [ref=e48] [cursor=pointer]:
          - /url: /studio?mode=parameters&project=nis-e2e-document-9d8ebd4b-ecbd-4433-9518-b7bbb6f048fb
          - generic [ref=e49]: "4"
          - generic [ref=e50]:
            - strong [ref=e51]: Parameter
            - generic [ref=e52]: Leer
        - link "5 Capacity & Timing Leer" [ref=e54] [cursor=pointer]:
          - /url: /studio/capacity?project=nis-e2e-document-9d8ebd4b-ecbd-4433-9518-b7bbb6f048fb
          - generic [ref=e55]: "5"
          - generic [ref=e56]:
            - strong [ref=e57]: Capacity & Timing
            - generic [ref=e58]: Leer
        - link "6 Validation / Preflight Leer" [ref=e60] [cursor=pointer]:
          - /url: /studio/validation?project=nis-e2e-document-9d8ebd4b-ecbd-4433-9518-b7bbb6f048fb
          - generic [ref=e61]: "6"
          - generic [ref=e62]:
            - strong [ref=e63]: Validation / Preflight
            - generic [ref=e64]: Leer
        - link "7 Simulation Leer" [ref=e66] [cursor=pointer]:
          - /url: /studio/simulation?project=nis-e2e-document-9d8ebd4b-ecbd-4433-9518-b7bbb6f048fb
          - generic [ref=e67]: "7"
          - generic [ref=e68]:
            - strong [ref=e69]: Simulation
            - generic [ref=e70]: Leer
        - link "8 Results / Analysis Leer" [ref=e72] [cursor=pointer]:
          - /url: /studio/results?project=nis-e2e-document-9d8ebd4b-ecbd-4433-9518-b7bbb6f048fb
          - generic [ref=e73]: "8"
          - generic [ref=e74]:
            - strong [ref=e75]: Results / Analysis
            - generic [ref=e76]: Leer
        - link "9 Data Science & Intelligence Leer" [ref=e78] [cursor=pointer]:
          - /url: /studio/intelligence?project=nis-e2e-document-9d8ebd4b-ecbd-4433-9518-b7bbb6f048fb
          - generic [ref=e79]: "9"
          - generic [ref=e80]:
            - strong [ref=e81]: Data Science & Intelligence
            - generic [ref=e82]: Leer
    - generic [ref=e84]:
      - generic [ref=e85]:
        - paragraph [ref=e86]: Engineering-Modell
        - heading "Hardware, Interfaces und Signale verwalten." [level=1] [ref=e87]
      - button "Übersicht aufklappen" [ref=e88] [cursor=pointer]:
        - generic [aria-hidden] [ref=e90]: ⌄
    - generic [ref=e92]:
      - generic [ref=e94]:
        - paragraph [ref=e95]: Kanonisches Modell
        - heading "Hardware-Knoten" [level=2] [ref=e96]
      - generic [ref=e97]:
        - tablist "Objekttypen" [ref=e98]:
          - tab "Hardware-Knoten" [selected] [ref=e99] [cursor=pointer]
          - tab "Physische Anschlüsse" [ref=e100] [cursor=pointer]
          - tab "Funktionen" [ref=e101] [cursor=pointer]
          - tab "Kommunikationsschnittstellen" [ref=e102] [cursor=pointer]
          - tab "Nachrichten" [ref=e103] [cursor=pointer]
          - tab "Signale" [ref=e104] [cursor=pointer]
          - tab "Structure Tree" [ref=e106] [cursor=pointer]
        - button "Reparatur-Agent" [ref=e107] [cursor=pointer]
      - generic [ref=e111]:
        - generic [ref=e112]:
          - paragraph [ref=e113]: Objekt-Wizard
          - strong [ref=e114]: Hardware-Knoten geführt anlegen
          - generic [ref=e115]: Identität → Zuordnung → technische Details → Prüfung
        - button "Wizard starten" [ref=e116] [cursor=pointer]
      - group "Hardware-Typ auswählen" [ref=e117]:
        - button "+ ECU" [ref=e118] [cursor=pointer]
        - button "+ Gateway" [ref=e119] [cursor=pointer]
        - button "+ Sensor" [ref=e120] [cursor=pointer]
        - button "+ Aktor" [ref=e121] [cursor=pointer]
      - generic [ref=e122]:
        - generic [ref=e123]: ◇
        - strong [ref=e124]: Keine Objekte vorhanden
        - paragraph [ref=e125]: Lege das erste Hardware-Knoten-Objekt an.
    - dialog [ref=e126]:
      - generic [ref=e127]:
        - generic [ref=e128]:
          - paragraph [ref=e129]: Geführte Anlage
          - heading "Engineering-Auftrag erstellen" [level=2] [ref=e130]
          - text: Technische Vorgaben festlegen und anschließend vom Agenten ausführen lassen.
        - button "Wizard schließen" [ref=e131] [cursor=pointer]: ×
      - region "Geführte Agent-Rückfrage" [ref=e132]:
        - generic [ref=e133]:
          - generic [ref=e134]:
            - strong [ref=e135]: Technische Vorgaben
            - generic [ref=e136]: "Projektname: Schritt 1 von 5"
          - button "Weiter" [disabled] [ref=e137]
        - generic "Rückfrage-Schritte" [ref=e138]:
          - button "1" [ref=e139] [cursor=pointer]
          - button "2" [disabled] [ref=e140] [cursor=pointer]
          - button "3" [disabled] [ref=e141] [cursor=pointer]
          - button "4" [disabled] [ref=e142] [cursor=pointer]
          - button "5" [ref=e143] [cursor=pointer]
        - group "Projekt benennen" [ref=e144]:
          - generic [ref=e146]:
            - generic [ref=e147]: Projektname
            - textbox "Projektname Die lesbare Bezeichnung wird im Projektkontext gespeichert. Die technische Projekt-ID bleibt unverändert." [active] [ref=e148]:
              - /placeholder: z. B. NIS Restbussimulation
            - generic [ref=e149]: Die lesbare Bezeichnung wird im Projektkontext gespeichert. Die technische Projekt-ID bleibt unverändert.
          - generic [ref=e150]:
            - generic [ref=e151]: Projektbeschreibung
            - textbox "Projektbeschreibung" [ref=e152]:
              - /placeholder: Was soll dieses Projekt leisten?
            - generic [ref=e153]: Die Beschreibung bleibt lesbar. Bestätigte Geräteanschlüsse, Messgrößen und Stellbefehle werden getrennt gespeichert und bei Korrekturen beibehalten.
          - generic [ref=e154]:
            - generic [ref=e155]: Weitere Hinweise
            - textbox "Weitere Hinweise" [ref=e156]:
              - /placeholder: "Optional: besondere Protokolle, Safety, Timing oder Herstellerlogik ..."
          - generic [ref=e157] [cursor=pointer]:
            - button "Text, PDF, PowerPoint oder Bild hinzufügen Text/SVG wird direkt gelesen. PDF, Office und Bilder werden als Evidence in den Auftrag aufgenommen." [ref=e158]
            - generic [ref=e161]:
              - strong [ref=e162]: Text, PDF, PowerPoint oder Bild hinzufügen
              - generic [ref=e163]: Text/SVG wird direkt gelesen. PDF, Office und Bilder werden als Evidence in den Auftrag aufgenommen.
          - button "Lokalen Qwen-Vorschlag erstellen" [ref=e164] [cursor=pointer]
          - list [ref=e165]:
            - listitem [ref=e166]:
              - generic [ref=e167]:
                - strong [ref=e168]: document-intake-vehicle.txt
                - generic [ref=e169]: text/plain · 20 KB
                - generic [ref=e170]: Aufgaben-Anlage · vollständig gelesen (19.088 Zeichen)
        - generic [ref=e171]:
          - button "Zurück" [disabled] [ref=e172]
          - generic [ref=e173]: Projektname fehlt
  - complementary "Engineering-Assistent":
    - button "AI Assistant öffnen" [ref=e174] [cursor=pointer]
  - alert [ref=e176]
```

# Test source

```ts
  1  | import { test, expect } from 'playwright/test';
  2  | import { randomUUID } from 'node:crypto';
  3  | import { fileURLToPath } from 'node:url';
  4  | 
  5  | test('document intake preserves complete requirements and reports unresolved scope @parser', async ({ page }) => {
  6  |   await page.goto(`/studio/engineering?assistant=project&project=nis-e2e-document-${randomUUID()}`);
  7  |   const dialog = page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' });
  8  |   await expect(dialog).toBeVisible();
  9  |   await dialog.locator('fieldset.agent-project-name-step input[type=file]').setInputFiles(
  10 |     fileURLToPath(new URL('./fixtures/document-intake-vehicle.txt', import.meta.url)));
  11 |   await expect(dialog.getByText(/vollständig gelesen \(19\.088 Zeichen\)/)).toBeVisible();
> 12 |   await dialog.getByRole('button', { name: '4', exact: true }).click();
     |                                                                ^ TimeoutError: locator.click: Timeout 30000ms exceeded.
  13 |   await expect(dialog.getByRole('heading', { name: 'Geräteumfang aus dem Dokument noch offen' })).toBeVisible();
  14 |   await expect(dialog.getByText(/Sensorik \(Radar, Kamera, Lidar, Ultraschall, IMU, Raddrehzahl\)/)).toBeVisible();
  15 |   await expect(dialog.getByRole('spinbutton', { name: 'Controller: verbindliche Anzahl', exact: true })).toHaveValue('5');
  16 |   await expect(dialog.getByText(/Aktorik \(Bremsaktuator, Lenkaktuator, Antriebsaktuator\)/)).toBeVisible();
  17 |   await expect(dialog.getByRole('spinbutton', { name: 'Aktoren: verbindliche Anzahl', exact: true })).toHaveValue('0');
  18 |   await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeDisabled();
  19 |   await expect(dialog.getByRole('table', { name: 'Kommunikationssysteme prüfen' })).not.toContainText('embedded_systems · adc');
  20 |   await expect(dialog).not.toContainText('degradieren /');
  21 | });
  22 | 
```