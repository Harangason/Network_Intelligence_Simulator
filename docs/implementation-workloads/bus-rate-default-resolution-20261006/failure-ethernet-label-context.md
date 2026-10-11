# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: technology-parameter-review.spec.ts >> manual ETHERNET port creation uses its native defaults and preserves edited assumptions @technology-review
- Location: e2e\technology-parameter-review.spec.ts:8:4

# Error details

```
TimeoutError: locator.selectOption: Timeout 30000ms exceeded.
Call log:
  - waiting for locator('form.eng-object-wizard').locator('#technology')
    - locator resolved to <select required="" id="technology" name="technology">…</select>
  - attempting select option action
    2 × waiting for element to be visible and enabled
      - did not find some options
    - retrying select option action
    - waiting 20ms
    2 × waiting for element to be visible and enabled
      - did not find some options
    - retrying select option action
      - waiting 100ms
    58 × waiting for element to be visible and enabled
       - did not find some options
     - retrying select option action
       - waiting 500ms

```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - main [ref=e2]:
    - generic [ref=e3]:
      - link "Communication Simulator Network trace studio" [ref=e4] [cursor=pointer]:
        - /url: /?project=nis-e2e-create-rates-26530c98-ae9d-4886-ae00-ce5db4a43eea
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
          - /url: /studio/settings?project=nis-e2e-create-rates-26530c98-ae9d-4886-ae00-ce5db4a43eea
        - generic "Backend-Build 04a066a61581; Frontend und Backend stimmen überein." [ref=e19]:
          - text: Python engine
          - generic [ref=e21]: · 04a066a61581
    - region "Verbindlicher Engineering-Workflow" [ref=e22]:
      - generic [ref=e23]:
        - generic [ref=e24]:
          - generic [ref=e25]: Project workflow
          - strong [ref=e26]: Define → Route → Connect → Configure → Calculate → Validate → Simulate → Analyze → Assess
        - 'generic "Technische Projekt-ID: nis-e2e-create-rates-26530c98-ae9d-4886-ae00-ce5db4a43eea" [ref=e28]': "Projekt: nis-e2e-create-rates-26530c98-ae9d-4886-ae00-ce5db4a43eea"
      - navigation [ref=e29]:
        - link "1 Engineering-Modell In Arbeit" [ref=e30] [cursor=pointer]:
          - /url: /studio/engineering?project=nis-e2e-create-rates-26530c98-ae9d-4886-ae00-ce5db4a43eea
          - generic [ref=e31]: "1"
          - generic [ref=e32]:
            - strong [ref=e33]: Engineering-Modell
            - generic [ref=e34]: In Arbeit
        - link "2 Routing-Tabelle Leer" [ref=e36] [cursor=pointer]:
          - /url: /studio/routing?project=nis-e2e-create-rates-26530c98-ae9d-4886-ae00-ce5db4a43eea
          - generic [ref=e37]: "2"
          - generic [ref=e38]:
            - strong [ref=e39]: Routing-Tabelle
            - generic [ref=e40]: Leer
        - link "3 Netzwerk-Editor Leer" [ref=e42] [cursor=pointer]:
          - /url: /studio?mode=network&project=nis-e2e-create-rates-26530c98-ae9d-4886-ae00-ce5db4a43eea
          - generic [ref=e43]: "3"
          - generic [ref=e44]:
            - strong [ref=e45]: Netzwerk-Editor
            - generic [ref=e46]: Leer
        - link "4 Parameter Leer" [ref=e48] [cursor=pointer]:
          - /url: /studio?mode=parameters&project=nis-e2e-create-rates-26530c98-ae9d-4886-ae00-ce5db4a43eea
          - generic [ref=e49]: "4"
          - generic [ref=e50]:
            - strong [ref=e51]: Parameter
            - generic [ref=e52]: Leer
        - link "5 Capacity & Timing Leer" [ref=e54] [cursor=pointer]:
          - /url: /studio/capacity?project=nis-e2e-create-rates-26530c98-ae9d-4886-ae00-ce5db4a43eea
          - generic [ref=e55]: "5"
          - generic [ref=e56]:
            - strong [ref=e57]: Capacity & Timing
            - generic [ref=e58]: Leer
        - link "6 Validation / Preflight Leer" [ref=e60] [cursor=pointer]:
          - /url: /studio/validation?project=nis-e2e-create-rates-26530c98-ae9d-4886-ae00-ce5db4a43eea
          - generic [ref=e61]: "6"
          - generic [ref=e62]:
            - strong [ref=e63]: Validation / Preflight
            - generic [ref=e64]: Leer
        - link "7 Simulation Leer" [ref=e66] [cursor=pointer]:
          - /url: /studio/simulation?project=nis-e2e-create-rates-26530c98-ae9d-4886-ae00-ce5db4a43eea
          - generic [ref=e67]: "7"
          - generic [ref=e68]:
            - strong [ref=e69]: Simulation
            - generic [ref=e70]: Leer
        - link "8 Results / Analysis Leer" [ref=e72] [cursor=pointer]:
          - /url: /studio/results?project=nis-e2e-create-rates-26530c98-ae9d-4886-ae00-ce5db4a43eea
          - generic [ref=e73]: "8"
          - generic [ref=e74]:
            - strong [ref=e75]: Results / Analysis
            - generic [ref=e76]: Leer
        - link "9 Data Science & Intelligence Leer" [ref=e78] [cursor=pointer]:
          - /url: /studio/intelligence?project=nis-e2e-create-rates-26530c98-ae9d-4886-ae00-ce5db4a43eea
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
        - heading "Physische Anschlüsse" [level=2] [ref=e96]
      - generic [ref=e97]:
        - tablist "Objekttypen" [ref=e98]:
          - tab "Hardware-Knoten" [ref=e99] [cursor=pointer]
          - tab "Physische Anschlüsse" [selected] [ref=e100] [cursor=pointer]
          - tab "Funktionen" [ref=e101] [cursor=pointer]
          - tab "Kommunikationsschnittstellen" [ref=e102] [cursor=pointer]
          - tab "Nachrichten" [ref=e103] [cursor=pointer]
          - tab "Signale" [ref=e104] [cursor=pointer]
          - tab "Structure Tree" [ref=e106] [cursor=pointer]
        - button "Reparatur-Agent" [ref=e107] [cursor=pointer]
      - paragraph [ref=e111]: Physische Anschlüsse verbinden ein Gerät über einen konkreten Kanal mit einem Netzwerk. Eine Nachricht verwendet einen solchen Anschluss.
      - generic [ref=e112]:
        - generic [ref=e113]:
          - paragraph [ref=e114]: Objekt-Wizard
          - strong [ref=e115]: Physische Anschlüsse geführt anlegen
          - generic [ref=e116]: Identität → Zuordnung → technische Details → Prüfung
        - button "Wizard starten" [ref=e117] [cursor=pointer]
      - dialog [ref=e118]:
        - generic [ref=e119]:
          - generic [ref=e120]:
            - paragraph [ref=e121]: Objekt-Wizard
            - heading "Physische Anschlüsse anlegen" [level=3] [ref=e122]
            - text: Das Objekt wird nach der Prüfung im kanonischen Engineering-Modell gespeichert.
          - button "Abbrechen" [ref=e123] [cursor=pointer]
        - generic [ref=e124]:
          - button "01 Identität" [ref=e125]:
            - generic [ref=e126]: "01"
            - text: Identität
          - button "02 Zuordnung" [ref=e127]:
            - generic [ref=e128]: "02"
            - text: Zuordnung
          - button "03 Details" [ref=e129]:
            - generic [ref=e130]: "03"
            - text: Details
          - button "04 Prüfen" [ref=e131]:
            - generic [ref=e132]: "04"
            - text: Prüfen
        - generic [ref=e133]:
          - generic [ref=e134]:
            - generic [ref=e135]: "Enthalten in: Hardware-Knoten"
            - 'combobox "Enthalten in: Hardware-Knoten" [ref=e136]':
              - option "Native default" [selected]
          - generic [ref=e137]:
            - generic [ref=e138]: Technologie
            - combobox "Technologie" [ref=e139]:
              - option "Technologie auswählen" [selected]
              - option "CAN"
              - option "CANopen"
              - option "CAN_FD"
              - option "CAN_XL"
              - option "LIN"
              - option "FlexRay"
              - option "Ethernet"
              - option "EtherCAT"
              - option "ProfiNET"
              - option "ModbusTCP"
              - option "ModbusRTU"
              - option "RS232"
              - option "RS485"
              - option "SPI"
              - option "I2C"
              - option "UART"
              - option "IO_LINK"
              - option "GPIO"
              - option "PWM"
              - option "ADC"
              - option "DAC"
              - option "USB"
              - option "PCIe"
              - option "MQTT"
              - option "OPCUA"
              - option "WiFi"
              - option "BLE"
              - option "DDS"
              - option "ROS2"
              - option "ARINC"
              - option "MIL_STD_1553"
              - option "MVB"
              - option "WTB"
              - option "ETB"
              - option "TRDP"
              - option "Other"
        - generic [ref=e140]:
          - button "Zurück" [ref=e141] [cursor=pointer]
          - button "Weiter" [disabled] [ref=e142]
      - generic [ref=e143]:
        - generic [ref=e144]: ◇
        - strong [ref=e145]: Keine Objekte vorhanden
        - paragraph [ref=e146]: Lege das erste Physische Anschlüsse-Objekt an.
  - complementary "Engineering-Assistent":
    - button "AI Assistant öffnen" [ref=e147] [cursor=pointer]
  - alert [ref=e149]
```

# Test source

```ts
  1   | import { test, expect } from 'playwright/test';
  2   | import { randomUUID } from 'node:crypto';
  3   | 
  4   | for (const scenario of [
  5   |   {technology:'LIN',id:'lin',rate:'19200',key:'lin_bitrate_bps'},
  6   |   {technology:'CAN_FD',id:'can_fd',rate:'500000',key:'arbitration_bitrate',data:'2000000'},
  7   |   {technology:'ETHERNET',id:'ethernet',rate:'1000000000',key:'bitrate'},
  8   | ]) test(`manual ${scenario.technology} port creation uses its native defaults and preserves edited assumptions @technology-review`, async ({page}) => {
  9   |   const project='nis-e2e-create-rates-'+randomUUID(),headers={'X-Project-ID':project};
  10  |   const nodeResponse=await page.request.post('/api/engineering/hardware-nodes',{headers,
  11  |     data:{name:'Native default controller',device_type:'EmbeddedController'}});
  12  |   expect(nodeResponse.ok(),await nodeResponse.text()).toBe(true);
  13  |   const node=await nodeResponse.json(), name='Native '+scenario.technology+' port';
  14  |   await page.goto(`/studio/engineering?project=${project}&resource=hardware-interfaces&parent=${node.id}&create=1`);
  15  |   const dialog=page.locator('form.eng-object-wizard');
  16  |   await expect(dialog).toBeVisible();
  17  |   await dialog.locator('#name').fill(name);
  18  |   await dialog.getByRole('button',{name:'Weiter',exact:true}).click();
> 19  |   await dialog.locator('#technology').selectOption(scenario.technology);
      |                                       ^ TimeoutError: locator.selectOption: Timeout 30000ms exceeded.
  20  |   await expect(dialog.getByRole('button',{name:'Weiter',exact:true})).toBeEnabled();
  21  |   await dialog.getByRole('button',{name:'Weiter',exact:true}).click();
  22  |   await expect(dialog.locator('#bitrate')).toHaveValue(scenario.rate);
  23  |   if (scenario.data) await expect(dialog.locator('#data_bitrate')).toHaveValue(scenario.data);
  24  |   else await expect(dialog.locator('#data_bitrate')).toHaveCount(0);
  25  |   await dialog.getByRole('button',{name:'Weiter',exact:true}).click();
  26  |   await expect(dialog.locator('.proposal-wizard-review').getByText(/SIMULATIONSANNAHME/)).toBeVisible();
  27  |   const createdResponse=page.waitForResponse(response=>response.url().endsWith('/api/engineering/hardware-interfaces')&&response.request().method()==='POST');
  28  |   await dialog.getByRole('button',{name:'Objekt anlegen',exact:true}).click();
  29  |   const response=await createdResponse;
  30  |   expect(response.ok(),await response.text()).toBe(true);
  31  |   const port=await response.json();
  32  |   expect(port.bitrate).toBeNull();expect(port.data_bitrate).toBeNull();
  33  |   const group=port.capabilities.simulation_parameter_assumptions[scenario.id];
  34  |   expect(group.values[scenario.key]).toBe(Number(scenario.rate));
  35  |   expect(group.provenance[scenario.key]).toMatchObject({source:'NIS_SIMULATION_ASSUMPTION',technology:scenario.id,hardware_evidence:false});
  36  |   await page.goto(`/studio/engineering?project=${project}&resource=hardware-interfaces&object=${port.id}&edit=1`);
  37  |   await expect(page.locator('#edit_bitrate')).toHaveValue(scenario.rate);
  38  |   if (scenario.id==='lin') {
  39  |     await page.locator('#edit_bitrate').fill('9600');
  40  |     await page.getByRole('button',{name:'Änderungen speichern',exact:true}).click();
  41  |     await expect(page.locator('#edit_technology')).toHaveCount(0);
  42  |     await page.reload();
  43  |     await expect(page.locator('#edit_bitrate')).toHaveValue('9600');
  44  |     const saved=await (await page.request.get(`/api/engineering/hardware-interfaces/${port.id}`,{headers})).json();
  45  |     expect(saved.bitrate).toBeNull();
  46  |     expect(saved.capabilities.simulation_parameter_assumptions.lin.values.lin_bitrate_bps).toBe(9600);
  47  |   }
  48  | });
  49  | 
  50  | test('native simulation rates load and persist without manual rate entry or central-default writes @technology-review', async ({page}) => {
  51  |   const project='nis-e2e-native-defaults-'+randomUUID();
  52  |   const headers={'X-Project-ID':project};
  53  |   const before=await (await page.request.get('/api/engineering/workflow/parameters',{headers})).json();
  54  |   const setup=await page.request.patch('/api/engineering/workflow/parameters',{headers,data:{expected_token:before.edit_token,
  55  |     parameters:{industry:'automotive',technology:'can_fd',networks:[{id:'lin-default',technology:'LIN'},
  56  |       {id:'can-default',technology:'CAN_FD'},{id:'eth-default',technology:'ETHERNET'}]}}});
  57  |   expect(setup.ok()).toBe(true);
  58  |   await page.goto(`/studio?mode=parameters&project=${project}&technology=lin`);
  59  |   await expect(page.locator('input[name="lin_bitrate_bps"]')).toHaveValue('19200');
  60  |   await expect(page.getByRole('region',{name:'Aktuelle Parameterbefunde'})).toBeVisible();
  61  |   const defaultSave = page.waitForResponse(response => response.url().endsWith('/api/engineering/workflow/parameters/defaults')
  62  |     && response.request().method() === 'POST');
  63  |   await page.getByRole('button',{name:'Fehlende Simulationsvorgaben im Projekt speichern',exact:true}).click();
  64  |   const defaultResponse = await defaultSave;
  65  |   expect(defaultResponse.ok(), await defaultResponse.text()).toBe(true);
  66  |   await expect(page.getByText(/Parameterherkunft · [1-9]\d* gespeicherte Simulationsannahmen/)).toBeVisible();
  67  |   const saved=await (await page.request.get('/api/engineering/workflow/parameters',{headers})).json();
  68  |   const assumptions=saved.parameters.simulation_parameter_assumptions;
  69  |   expect(assumptions.lin.values.lin_bitrate_bps).toBe(19200);
  70  |   expect(assumptions.can_fd.values.arbitration_bitrate).toBe(500000);
  71  |   expect(assumptions.can_fd.values.data_bitrate).toBe(2000000);
  72  |   expect(assumptions.can_fd.values.can_fd_brs).toBe(true);
  73  |   expect(assumptions.ethernet.values.bitrate).toBe(1000000000);
  74  |   expect(assumptions.can_fd.provenance.data_bitrate.hardware_evidence).toBe(false);
  75  |   expect(saved.parameter_storage.source).toBe('PROJECT_USER_DEFINED_VALUES');
  76  |   const stored=await page.request.get('/api/engineering/workflow/parameters/user-defined-values',{headers});
  77  |   expect(stored.ok()).toBe(true);
  78  |   await page.goto(`/studio?mode=parameters&project=${project}&technology=can_fd`);
  79  |   await expect(page.locator('input[name="arbitration_bitrate"]')).toHaveValue('500000');
  80  |   await expect(page.locator('input[name="data_bitrate"]')).toHaveValue('2000000');
  81  |   await expect(page.locator('input[name="can_fd_brs"]')).toBeChecked();
  82  |   await page.reload();
  83  |   await expect(page.locator('input[name="data_bitrate"]')).toHaveValue('2000000');
  84  |   await page.goto(`/studio?mode=parameters&project=${project}&technology=ethernet`);
  85  |   await expect(page.locator('input[name="bitrate"]')).toHaveValue('1000000000');
  86  | });
  87  | 
  88  | // Real isolated persistence and parameter-view regressions; not nine-stage completion proof.
  89  | test('unconfirmed project can select every registered bus without an Automotive fallback @technology-review', async ({ page }) => {
  90  |   const project = 'nis-e2e-catalog-' + randomUUID();
  91  |   const headers = { 'X-Project-ID': project };
  92  |   const catalog = await (await page.request.get('/api/technologies')).json();
  93  |   await page.goto(`/studio?mode=parameters&project=${project}`);
  94  |   await expect(page.getByRole('heading', { name: 'Branche und Technologie auswählen' })).toBeVisible();
  95  |   await expect(page.getByLabel('Anwendungsbereich auswählen')).toHaveValue('');
  96  |   const bus = page.getByLabel('Bus / Protokoll auswählen');
  97  |   await expect(bus.locator('option')).toHaveCount(catalog.technology_count + 1);
  98  |   const search = page.getByRole('searchbox', { name: 'Bus / Protokoll suchen' });
  99  |   await search.fill('CANFD');
  100 |   await expect(bus.locator('option[value="can_fd"]')).toHaveCount(1);
  101 |   await search.fill('profnet');
  102 |   await expect(bus.locator('option[value="profinet"]')).toHaveCount(1);
  103 |   await search.clear();
  104 |   await expect(bus.locator('option')).toHaveCount(catalog.technology_count + 1);
  105 |   await bus.selectOption('i2c');
  106 |   await page.getByLabel('Anwendungsbereich auswählen').selectOption('custom');
  107 |   await expect(page.locator('#domain')).toHaveValue('custom');
  108 |   await expect(page.locator('#technology')).toHaveValue('i2c');
  109 |   const selectedBus = page.locator('#technology');
  110 |   const selectBox = await selectedBus.boundingBox();
  111 |   const searchBox = await search.boundingBox();
  112 |   expect(selectBox && searchBox && searchBox.x >= selectBox.x + selectBox.width - 1).toBe(true);
  113 |   await search.fill('profnet');
  114 |   await expect(selectedBus.locator('option[value="profinet"]')).toHaveCount(1);
  115 |   await expect(selectedBus).toHaveValue('i2c');
  116 |   await search.fill('zzzzzz');
  117 |   await expect(selectedBus).toHaveValue('i2c');
  118 |   await expect(selectedBus.locator('option[value="__no_matches"]')).toHaveCount(1);
  119 |   await search.clear();
```