# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: equipment-inventory.spec.ts >> generic sensors expose separate measurement and connection choices without losing slot identity
- Location: e2e\equipment-inventory.spec.ts:4:1

# Error details

```
TimeoutError: locator.fill: Timeout 30000ms exceeded.
Call log:
  - waiting for locator('.engineering-agent-wizard-dialog').getByRole('textbox', { name: 'Projektbeschreibung', exact: true })

```

# Page snapshot

```yaml
- generic [ref=e1]:
  - main [ref=e2]:
    - generic [ref=e3]:
      - link "Communication Simulator Network trace studio" [ref=e4] [cursor=pointer]:
        - /url: /?project=nis-e2e-measurement-21b32293-4263-44ed-be02-77a1d8c0ecd5
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
          - /url: /studio/settings?project=nis-e2e-measurement-21b32293-4263-44ed-be02-77a1d8c0ecd5
        - generic "Backend-Build 92cf49ed741f; Frontend und Backend stimmen überein." [ref=e19]:
          - text: Python engine
          - generic [ref=e21]: · 92cf49ed741f
    - region "Verbindlicher Engineering-Workflow" [ref=e22]:
      - generic [ref=e23]:
        - generic [ref=e24]:
          - generic [ref=e25]: Project workflow
          - strong [ref=e26]: Define → Route → Connect → Configure → Calculate → Validate → Simulate → Analyze → Assess
        - 'generic "Technische Projekt-ID: nis-e2e-measurement-21b32293-4263-44ed-be02-77a1d8c0ecd5" [ref=e28]': "Projekt: nis-e2e-measurement-21b32293-4263-44ed-be02-77a1d8c0ecd5"
      - navigation [ref=e29]:
        - link "1 Engineering-Modell Leer" [ref=e30] [cursor=pointer]:
          - /url: /studio/engineering?project=nis-e2e-measurement-21b32293-4263-44ed-be02-77a1d8c0ecd5
          - generic [ref=e31]: "1"
          - generic [ref=e32]:
            - strong [ref=e33]: Engineering-Modell
            - generic [ref=e34]: Leer
        - link "2 Routing-Tabelle Leer" [ref=e36] [cursor=pointer]:
          - /url: /studio/routing?project=nis-e2e-measurement-21b32293-4263-44ed-be02-77a1d8c0ecd5
          - generic [ref=e37]: "2"
          - generic [ref=e38]:
            - strong [ref=e39]: Routing-Tabelle
            - generic [ref=e40]: Leer
        - link "3 Netzwerk-Editor Leer" [ref=e42] [cursor=pointer]:
          - /url: /studio?mode=network&project=nis-e2e-measurement-21b32293-4263-44ed-be02-77a1d8c0ecd5
          - generic [ref=e43]: "3"
          - generic [ref=e44]:
            - strong [ref=e45]: Netzwerk-Editor
            - generic [ref=e46]: Leer
        - link "4 Parameter Freigegeben" [ref=e48] [cursor=pointer]:
          - /url: /studio?mode=parameters&project=nis-e2e-measurement-21b32293-4263-44ed-be02-77a1d8c0ecd5
          - generic [ref=e49]: "4"
          - generic [ref=e50]:
            - strong [ref=e51]: Parameter
            - generic [ref=e52]: Freigegeben
        - link "5 Capacity & Timing Leer" [ref=e54] [cursor=pointer]:
          - /url: /studio/capacity?project=nis-e2e-measurement-21b32293-4263-44ed-be02-77a1d8c0ecd5
          - generic [ref=e55]: "5"
          - generic [ref=e56]:
            - strong [ref=e57]: Capacity & Timing
            - generic [ref=e58]: Leer
        - link "6 Validation / Preflight Leer" [ref=e60] [cursor=pointer]:
          - /url: /studio/validation?project=nis-e2e-measurement-21b32293-4263-44ed-be02-77a1d8c0ecd5
          - generic [ref=e61]: "6"
          - generic [ref=e62]:
            - strong [ref=e63]: Validation / Preflight
            - generic [ref=e64]: Leer
        - link "7 Simulation Leer" [ref=e66] [cursor=pointer]:
          - /url: /studio/simulation?project=nis-e2e-measurement-21b32293-4263-44ed-be02-77a1d8c0ecd5
          - generic [ref=e67]: "7"
          - generic [ref=e68]:
            - strong [ref=e69]: Simulation
            - generic [ref=e70]: Leer
        - link "8 Results / Analysis Leer" [ref=e72] [cursor=pointer]:
          - /url: /studio/results?project=nis-e2e-measurement-21b32293-4263-44ed-be02-77a1d8c0ecd5
          - generic [ref=e73]: "8"
          - generic [ref=e74]:
            - strong [ref=e75]: Results / Analysis
            - generic [ref=e76]: Leer
        - link "9 Data Science & Intelligence Leer" [ref=e78] [cursor=pointer]:
          - /url: /studio/intelligence?project=nis-e2e-measurement-21b32293-4263-44ed-be02-77a1d8c0ecd5
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
          - button "2" [ref=e140] [cursor=pointer]
          - button "3" [ref=e141] [cursor=pointer]
          - button "4" [disabled] [ref=e142] [cursor=pointer]
          - button "5" [ref=e143] [cursor=pointer]
        - group "Projekt benennen" [ref=e144]:
          - generic [ref=e146]:
            - generic [ref=e147]: Projektname
            - textbox "Projektname Die lesbare Bezeichnung wird im Projektkontext gespeichert. Die technische Projekt-ID bleibt unverändert." [active] [ref=e148]:
              - /placeholder: z. B. NIS Restbussimulation
              - text: Sensorfunktionen
            - generic [ref=e149]: Die lesbare Bezeichnung wird im Projektkontext gespeichert. Die technische Projekt-ID bleibt unverändert.
          - generic [ref=e150]:
            - generic [ref=e151]: Projektbeschreibung
            - textbox "Projektbeschreibung Diese Beschreibung ist zugleich der Aufgabentext für den Agenten. Änderungen auf beiden Seiten werden gemeinsam übernommen." [ref=e152]:
              - /placeholder: Was soll dieses Projekt leisten?
            - generic [ref=e153]: Diese Beschreibung ist zugleich der Aufgabentext für den Agenten. Änderungen auf beiden Seiten werden gemeinsam übernommen.
          - generic [ref=e154]:
            - generic [ref=e155]: Weitere Hinweise
            - textbox "Weitere Hinweise" [ref=e156]:
              - /placeholder: "Optional: besondere Protokolle, Safety, Timing oder Herstellerlogik ..."
          - generic [ref=e157] [cursor=pointer]:
            - button "Text, PDF, PowerPoint oder Bild hinzufügen Text/SVG wird direkt gelesen. PDF, Office und Bilder werden als Evidence in den Auftrag aufgenommen." [ref=e158]
            - generic [ref=e161]:
              - strong [ref=e162]: Text, PDF, PowerPoint oder Bild hinzufügen
              - generic [ref=e163]: Text/SVG wird direkt gelesen. PDF, Office und Bilder werden als Evidence in den Auftrag aufgenommen.
        - generic [ref=e164]:
          - button "Zurück" [disabled] [ref=e165]
          - generic [ref=e166]: Projektbeschreibung fehlt
  - complementary "Engineering-Assistent":
    - button "AI Assistant öffnen" [ref=e167] [cursor=pointer]
  - alert [ref=e169]
```

# Test source

```ts
  1  | import { test, expect } from 'playwright/test';
  2  | import { randomUUID } from 'node:crypto';
  3  | 
  4  | test('generic sensors expose separate measurement and connection choices without losing slot identity', async ({ page }) => {
  5  |   await page.goto(`/studio/engineering?assistant=project&project=nis-e2e-measurement-${randomUUID()}`);
  6  |   const dialog = page.locator('.engineering-agent-wizard-dialog');
  7  |   await dialog.getByTitle('Projektname', { exact: true }).click();
  8  |   await dialog.locator('#engineering-project-name').fill('Sensorfunktionen');
> 9  |   await dialog.getByRole('textbox', { name: 'Projektbeschreibung', exact: true }).fill('3 Sensoren und ein RaspberryPi');
     |                                                                                   ^ TimeoutError: locator.fill: Timeout 30000ms exceeded.
  10 |   await dialog.getByTitle('Netzarchitektur', { exact: true }).click();
  11 |   await dialog.getByRole('radio', { name: /Variante 0/ }).check();
  12 |   await dialog.getByTitle('Geräteumfang', { exact: true }).click();
  13 |   await expect(dialog.getByLabel('Sensor1: Anschluss', { exact: true })).toBeDisabled();
  14 |   await dialog.getByLabel('Sensor 2: Messgröße', { exact: true }).selectOption('torque');
  15 |   await dialog.getByLabel('Sensor2: Anschluss', { exact: true }).selectOption('I2C');
  16 |   await dialog.getByLabel('Sensor 1: Messgröße', { exact: true }).selectOption('temperature');
  17 |   await dialog.getByLabel('Sensor 3: Messgröße', { exact: true }).selectOption('speed');
  18 |   await expect(dialog.getByLabel('Sensor 2: Messgröße', { exact: true })).toHaveValue('torque');
  19 |   await expect(dialog.getByLabel('Sensor2: Anschluss', { exact: true })).toHaveValue('I2C');
  20 |   await dialog.getByLabel('Sensor 2: Messgröße', { exact: true }).selectOption('pressure');
  21 |   await expect(dialog.getByLabel('Sensor2: Anschluss', { exact: true })).toHaveValue('I2C');
  22 |   for (const name of ['Sensor1', 'Sensor3', 'RaspberryPi']) await dialog.getByLabel(`${name}: Anschluss`, { exact: true }).selectOption('I2C');
  23 |   await expect(dialog.getByRole('button', { name: 'Anschlüsse übernehmen und Auftrag starten', exact: true })).toBeEnabled();
  24 |   await expect(dialog.locator('.agent-equipment-list')).toContainText('Sensoren · 3 erkannt / 3 vorgegeben');
  25 |   await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeEnabled();
  26 | });
  27 | 
  28 | test('temperature purpose inventory permits review without a spurious controller repair', async ({ page }) => {
  29 |   await page.goto(`/studio/engineering?assistant=project&project=nis-e2e-temperature-${randomUUID()}`);
  30 |   const dialog = page.locator('.engineering-agent-wizard-dialog');
  31 |   await dialog.getByTitle('Projektname', { exact: true }).click();
  32 |   await dialog.locator('#engineering-project-name').fill('Temperaturregelung');
  33 |   await dialog.getByRole('textbox', { name: 'Projektbeschreibung', exact: true }).fill('2 Aktoren für Ventile, 4 Sensoren für Temperaturen, und ein RaspberryPi');
  34 |   await dialog.getByTitle('Geräteumfang', { exact: true }).click();
  35 |   await expect(dialog.locator('.agent-equipment-list')).toContainText('Sensoren · 4 erkannt / 4 vorgegeben');
  36 |   await expect(dialog.getByRole('alert').filter({ hasText: 'Geräteumfang noch unvollständig' })).toHaveCount(0);
  37 |   await expect(dialog.getByRole('region', { name: 'Controller ergänzen', exact: true })).toHaveCount(0);
  38 |   await expect(dialog.locator('.agent-equipment-clusters').getByRole('listitem').filter({ hasText: /Temperatursensor/ })).toHaveCount(4);
  39 |   await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeDisabled();
  40 |   await expect(dialog.getByRole('button', { name: 'Anschlüsse übernehmen und Auftrag starten', exact: true })).toBeDisabled();
  41 |   for (let index = 1; index <= 4; index++) {
  42 |     await expect(dialog.getByLabel(`Sensor ${index}: Messgröße`, { exact: true })).toHaveValue('temperature');
  43 |   }
  44 |   for (const name of ['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3', 'Temperatursensor4', 'Ventilaktor1', 'Ventilaktor2']) {
  45 |     await dialog.getByLabel(`${name}: Anschluss`, { exact: true }).selectOption('I2C');
  46 |   }
  47 |   await dialog.getByTitle('Projektname', { exact: true }).click();
  48 |   await expect(dialog.getByRole('textbox', { name: 'Projektbeschreibung', exact: true })).toHaveValue(/- Sensor-Messgrößen: \{"Temperatursensor1":"temperature","Temperatursensor2":"temperature","Temperatursensor3":"temperature","Temperatursensor4":"temperature"\}/);
  49 |   await dialog.getByTitle('Geräteumfang', { exact: true }).click();
  50 |   await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeDisabled();
  51 |   await dialog.getByLabel('Ventilaktor1: Stellbefehl', { exact: true }).selectOption('OPEN_CLOSE');
  52 |   await expect(dialog.getByLabel('Ventilaktor2: Stellbefehl', { exact: true })).toHaveValue('');
  53 |   await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeDisabled();
  54 |   await dialog.getByLabel('Ventilaktor2: Stellbefehl', { exact: true }).selectOption('POSITION');
  55 |   await expect(dialog.getByRole('button', { name: 'Anschlüsse übernehmen und Auftrag starten', exact: true })).toBeEnabled();
  56 |   await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeEnabled();
  57 | });
  58 | 
  59 | test('equipment inventory distinguishes requested sensors from identified devices and recovers after clarification', async ({ page }) => {
  60 |   await page.goto(`/studio/engineering?assistant=project&project=nis-e2e-inventory-${randomUUID()}`);
  61 |   const dialog = page.locator('.engineering-agent-wizard-dialog');
  62 |   await expect(dialog.getByRole('heading', { name: 'Engineering-Auftrag erstellen' })).toBeVisible();
  63 |   await dialog.getByTitle('Projektname', { exact: true }).click();
  64 |   await dialog.locator('#engineering-project-name').fill('Sensorinventar prüfen');
  65 |   await dialog.getByRole('textbox', { name: 'Projektbeschreibung', exact: true }).fill('Ein kleines Projekt mit einem Raspberry Pi, drei Sensoren und drei Ventilen.');
  66 |   await dialog.getByTitle('Geräteumfang', { exact: true }).click();
  67 |   await expect(dialog.locator('.agent-equipment-list')).toContainText('Sensoren · 0 erkannt / 3 vorgegeben');
  68 |   await expect(dialog.getByRole('alert').filter({ hasText: 'Geräteumfang noch unvollständig' })).toContainText('Sensoren: 0 erkannt, 3 vorgegeben');
  69 |   await expect(dialog.locator('.agent-questionnaire-nav')).toContainText('Anzahlen, erkannte Geräte, Anschlüsse, Busse und Controller-Zuordnung prüfen');
  70 |   await expect(dialog.locator('.agent-questionnaire-nav')).not.toContainText('Sollzahlen, Busse und Controller-Zuordnung bereit');
  71 |   await dialog.getByTitle('Projektname', { exact: true }).click();
  72 |   await dialog.getByRole('textbox', { name: 'Projektbeschreibung', exact: true }).fill('Ein kleines Projekt mit einem Raspberry Pi, drei Temperatursensoren und drei Ventilen.');
  73 |   await dialog.getByTitle('Geräteumfang', { exact: true }).click();
  74 |   await expect(dialog.locator('.agent-equipment-list')).toContainText('Sensoren · 3 erkannt / 3 vorgegeben');
  75 |   await expect(dialog.getByRole('alert').filter({ hasText: 'Geräteumfang noch unvollständig' })).toHaveCount(0);
  76 |   const cluster = dialog.locator('.agent-equipment-clusters');
  77 |   await expect(cluster.getByRole('listitem').filter({ hasText: /Temperatursensor/ })).toHaveCount(3);
  78 |   for (let index = 1; index <= 3; index++) await expect(cluster.getByRole('listitem').filter({ hasText: `Temperatursensor${index}` })).toBeVisible();
  79 | });
  80 | 
```