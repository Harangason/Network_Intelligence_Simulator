// dc199953cc3a98447b163f37cf9727710b416a99
import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';

// First actionable reply test allowance: backend/SSE 290s + one history PUT 8s + UI expect 30s.
// Sources: src/app/api/agent/chat/route.ts, playwright.config.ts; not a whole-stream bound or SLA.
const ENGINEERING_REPLY_BUDGET_MS = 290000 + 8000 + 30000;
test('native wizard preserves its complete source while adopting an edited shared draft @project-draft', async ({
  page
}) => {
  var _persisted$context, _persisted$data;
  const project = 'nis-e2e-shared-native-' + randomUUID();
  const run = randomUUID();
  const graph = [{
    cluster_id: 'drive',
    label: 'Regelung',
    network_id: 'can_fd',
    network_label: 'CAN-FD',
    bus_name: 'Regelung',
    controllers: [{
      ecu: 'Motorsteuerung',
      sensors: [],
      actuators: []
    }, {
      ecu: 'Anzeige',
      sensors: [],
      actuators: []
    }]
  }];
  const prompt = `Strukturierte Vorgaben fuer den Engineering-Agenten:
- Lauf-ID: ${run}
- Industrie: Automotive
- Netzwerktechnologien: CAN-FD (can_fd)
- Hardware-Sollwerte: {"gateways":1,"ecus":2,"sensors":0,"actuators":0}
- Systemcluster-Graph: ${JSON.stringify(graph)}
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
Erzeuge Motorsteuerung und Anzeige mit einem Gateway System.`;
  const started = await page.request.post('/api/engineering/agent/chat', {
    headers: {
      'X-Project-ID': project
    },
    timeout: 120000,
    data: {
      prompt,
      wizard_command: {
        action: 'START',
        run_id: run,
        operation_id: randomUUID(),
        target: 'engineering_model',
        wizard_context: {
          project_id: project,
          run_id: run,
          project_name: 'Gemeinsamer nativer Auftrag',
          scope_ids: ['engineering_model'],
          mode: 'full',
          process_ids: ['defaults', 'review_gate'],
          task: 'Motorsteuerung und Anzeige an System'
        }
      }
    }
  });
  expect(started.ok(), await started.text()).toBe(true);
  const initial = await (await page.request.get('/api/engineering/agent/project-draft', {
    headers: {
      'X-Project-ID': project
    }
  })).json();
  expect(initial.data.source_format).toBe('WIZARD_V2');
  expect(initial.data.structured_source.prompt).toBe(prompt);
  await page.goto(`/studio/engineering?assistant=project&project=${project}`);
  const dialog = page.getByRole('dialog', {
    name: 'Engineering-Auftrag erstellen'
  });
  await dialog.getByRole('button', {
    name: 'Ergänzen',
    exact: true
  }).click();
  await dialog.getByText('Gemeinsamen Projektentwurf bearbeiten', {
    exact: true
  }).click();
  const editor = dialog.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  });
  await expect(editor.getByRole('textbox', {
    name: 'Projektbeschreibung',
    exact: true
  })).toHaveValue(prompt);
  await editor.getByRole('textbox', {
    name: 'Anforderung ergänzen',
    exact: true
  }).fill('Die Modellbeschreibung soll den lokalen Regelungszweck dokumentieren.');
  await editor.getByRole('button', {
    name: 'Ergänzung speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 2 gespeichert');
  await dialog.getByRole('button', {
    name: 'Gespeicherten Entwurf im Auftrag übernehmen',
    exact: true
  }).click();
  await expect(editor).not.toBeVisible({
    timeout: 120000
  });
  const persisted = await (await page.request.get('/api/engineering/workflow', {
    headers: {
      'X-Project-ID': project
    }
  })).json();
  const state = (_persisted$context = persisted.context) !== null && _persisted$context !== void 0 ? _persisted$context : (_persisted$data = persisted.data) === null || _persisted$data === void 0 ? void 0 : _persisted$data.context;
  expect(state.agent_wizard_status.run_id).toBe(run);
  expect(state.agent_wizard_status.engineering_draft_ref).toEqual({
    draft_id: initial.data.draft_id,
    revision: 2
  });
  expect(state.wizard_request.prompt).toContain(JSON.stringify(graph));
  await page.reload();
  await expect(page.getByRole('dialog', {
    name: 'Engineering-Auftrag erstellen'
  })).toBeVisible();
});
test('conflicting edits retain input and load the current revision without overwriting it @project-draft', async ({
  page
}) => {
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const project = 'network-project-' + compact;
  await page.goto(`/studio/agent?project=${compact}`);
  await page.getByRole('textbox', {
    name: 'Nachricht an den Engineering-Assistenten'
  }).fill('Erstelle ein Projekt mit Raspberry Pi und drei Temperatursensoren.');
  await page.locator('.eng-agent-composer').getByRole('button', {
    name: 'Senden',
    exact: true
  }).click();
  const editor = page.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  });
  await expect(editor).toContainText('Revision 1', {
    timeout: ENGINEERING_REPLY_BUDGET_MS
  });
  await editor.getByRole('textbox', {
    name: 'Name',
    exact: true
  }).first().fill('MeineRegelung');
  const session = await (await page.request.get('/api/engineering/agent/review-session')).json();
  const remote = await page.request.post('/api/engineering/agent/project-draft', {
    headers: {
      'X-Project-ID': project,
      'X-Human-Review': 'confirmed',
      'X-Review-CSRF': session.csrf_token
    },
    data: {
      action: 'RESOLVE',
      operation_id: randomUUID(),
      revision: 1,
      industry: 'building_automation'
    }
  });
  expect(remote.ok()).toBe(true);
  await editor.getByRole('button', {
    name: 'Angaben speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('region', {
    name: 'Entwurfskonflikt'
  })).toContainText('Revision 2');
  await expect(editor.getByRole('textbox', {
    name: 'Name',
    exact: true
  }).first()).toHaveValue('MeineRegelung');
  await editor.getByRole('button', {
    name: 'Aktuellen Stand laden und Eingabekopie behalten',
    exact: true
  }).click();
  await expect(editor.getByRole('textbox', {
    name: 'Einsatzbereich',
    exact: true
  })).toHaveValue('building_automation');
  await expect(editor.getByRole('textbox', {
    name: 'Name',
    exact: true
  }).first()).toHaveValue('RaspberryPi');
  await expect(editor.getByRole('textbox', {
    name: 'Erhaltene Eingaben vor dem Konflikt',
    exact: true
  })).toHaveValue(/MeineRegelung/);
  await editor.getByRole('textbox', {
    name: 'Name',
    exact: true
  }).first().fill('MeineRegelung');
  await editor.getByRole('button', {
    name: 'Angaben speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 3 gespeichert');
});
test('draft recovers a lost save response and survives application restart @project-draft', async ({
  page
}) => {
  const container = process.env.NIS_E2E_APP_CONTAINER;
  expect(container).toMatch(/^nis-e2e-app-[a-f0-9]+$/);
  const docker = process.env.NIS_TEST_DOCKER || 'docker';
  expect(execFileSync(docker, ['inspect', container, '--format', '{{index .Config.Labels "networkis.test"}}'], {
    encoding: 'utf8'
  }).trim()).toBe('disposable');
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const project = 'network-project-' + compact;
  await page.goto(`/studio/agent?project=${compact}`);
  await page.getByRole('textbox', {
    name: 'Nachricht an den Engineering-Assistenten'
  }).fill('Erstelle ein Projekt mit Raspberry Pi und drei Temperatursensoren.');
  await page.locator('.eng-agent-composer').getByRole('button', {
    name: 'Senden',
    exact: true
  }).click();
  const editor = page.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  });
  await expect(editor).toContainText('4 Geräte', {
    timeout: ENGINEERING_REPLY_BUDGET_MS
  });
  await editor.getByRole('textbox', {
    name: 'Anschlusstechnologie',
    exact: true
  }).first().fill('ethernet');
  let dropped = false;
  await page.route('**/api/engineering/agent/project-draft', async route => {
    if (route.request().method() !== 'POST' || dropped) return route.continue();
    // Execute the real server write, but lose its transport response.
    const response = await route.fetch();
    expect(response.ok()).toBe(true);
    dropped = true;
    await route.abort('connectionreset');
  });
  await editor.getByRole('button', {
    name: 'Angaben speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('alert')).toBeVisible();
  await expect(editor.getByRole('textbox', {
    name: 'Anschlusstechnologie',
    exact: true
  }).first()).toHaveValue('ethernet');
  const read = async () => (await (await page.request.get('/api/engineering/agent/project-draft', {
    headers: {
      'X-Project-ID': project
    }
  })).json()).data;
  const accepted = await read();
  expect(accepted.revision).toBe(2);
  await editor.getByRole('button', {
    name: 'Angaben speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 2 gespeichert');
  expect(await read()).toEqual(accepted);
  execFileSync(docker, ['restart', container], {
    timeout: 60000
  });
  await expect.poll(async () => {
    try {
      return (await page.request.get('/api/ready', {
        timeout: 2000
      })).ok();
    } catch {
      return false;
    }
  }, {
    timeout: 120000
  }).toBe(true);
  await page.reload();
  await expect(editor).toContainText('Revision 2');
  expect(await read()).toEqual(accepted);
});
test('removing a draft device survives save, amendment and reload @project-draft', async ({
  page
}) => {
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  await page.goto(`/studio/agent?project=${compact}`);
  await page.getByRole('textbox', {
    name: 'Nachricht an den Engineering-Assistenten'
  }).fill('Erstelle ein Projekt mit einem Raspberry Pi und drei Temperatursensoren.');
  const send = page.locator('.eng-agent-composer').getByRole('button', {
    name: 'Senden',
    exact: true
  });
  await expect(send).toBeEnabled({
    timeout: 120000
  });
  await send.click();
  const editor = page.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  });
  await expect(editor).toContainText('4 Geräte', {
    timeout: ENGINEERING_REPLY_BUDGET_MS
  });
  await editor.getByRole('group', {
    name: 'Temperatursensor3 · SENSOR',
    exact: true
  }).getByRole('button', {
    name: 'Aus Entwurf entfernen',
    exact: true
  }).click();
  await editor.getByRole('button', {
    name: 'Angaben speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 2 gespeichert');
  await editor.getByRole('textbox', {
    name: 'Anforderung ergänzen',
    exact: true
  }).fill('Zusätzlich zwei Drucksensoren.');
  await editor.getByRole('button', {
    name: 'Ergänzung speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 3 gespeichert');
  await page.reload();
  await expect(editor).toContainText('5 Geräte');
  await expect(editor.getByRole('group', {
    name: 'Temperatursensor3 · SENSOR',
    exact: true
  })).toHaveCount(0);
  await expect(editor.getByRole('group', {
    name: 'Drucksensor2 · SENSOR',
    exact: true
  })).toBeVisible();
});
for (const mode of ['chat', 'wizard']) test(`missing controller can be added in ${mode} and the requirement remains editable @project-draft`, async ({
  page
}) => {
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const project = 'network-project-' + compact;
  await page.goto(`/studio/agent?project=${compact}`);
  const input = page.getByRole('textbox', {
    name: 'Nachricht an den Engineering-Assistenten'
  });
  await input.fill('Ein neues Projekt mit drei Sensoren.');
  await page.locator('.eng-agent-composer').getByRole('button', {
    name: 'Senden',
    exact: true
  }).click();
  let editor = page.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  }).last();
  await expect(editor).toContainText('3 Geräte', {
    timeout: ENGINEERING_REPLY_BUDGET_MS
  });
  await editor.getByText('Offene Angaben', {
    exact: false
  }).click();
  await expect(editor).toContainText('Controller ergänzen');
  if (mode === 'wizard') {
    await page.getByRole('button', {
      name: /Im Wizard bearbeiten/
    }).click();
    await expect(page.getByRole('dialog', {
      name: 'Engineering-Auftrag erstellen'
    })).toBeVisible();
    editor = page.getByRole('region', {
      name: 'Gespeicherter Projektentwurf'
    }).last();
    await expect(page.getByRole('button', {
      name: 'Auftrag starten',
      exact: true
    })).toBeDisabled();
    await editor.getByRole('textbox', {
      name: 'Anforderung ergänzen',
      exact: true
    }).fill('Ergänze einen Raspberry Pi.');
    await editor.getByRole('button', {
      name: 'Ergänzung speichern',
      exact: true
    }).click();
  } else {
    await input.fill('Ergänze einen Raspberry Pi.');
    await page.locator('.eng-agent-composer').getByRole('button', {
      name: 'Senden',
      exact: true
    }).click();
  }
  await expect(editor).toContainText('4 Geräte', mode === 'chat' ? {
    timeout: ENGINEERING_REPLY_BUDGET_MS
  } : undefined);
  await page.reload();
  editor = page.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  }).last();
  await expect(editor).toContainText('Revision 2');
  const owners = editor.getByRole('combobox', {
    name: 'Verarbeitender Controller',
    exact: true
  });
  await expect(owners).toHaveCount(3);
  for (const field of await owners.all()) await field.selectOption({
    label: 'RaspberryPi'
  });
  const tasks = editor.getByRole('textbox', {
    name: 'Messgröße oder Geräteaufgabe',
    exact: true
  });
  await expect(tasks).toHaveCount(4);
  for (let index = 1; index < 4; index++) await tasks.nth(index).fill('Temperatur messen');
  for (const field of await editor.getByRole('textbox', {
    name: 'Anschlusstechnologie',
    exact: true
  }).all()) await field.fill('ethernet');
  await editor.getByRole('combobox', {
    name: 'Technische Parameter',
    exact: true
  }).selectOption('defaults');
  await editor.getByRole('button', {
    name: 'Angaben speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 3 gespeichert');
  const response = await page.request.get('/api/engineering/agent/project-draft', {
    headers: {
      'X-Project-ID': project
    }
  });
  const draft = (await response.json()).data;
  expect(draft.devices.map(device => device.name).sort()).toEqual(['RaspberryPi', 'Sensor1', 'Sensor2', 'Sensor3']);
  expect(draft.issues).toEqual([]);
  expect(draft.original_requirement).toBe('Ein neues Projekt mit drei Sensoren.');
  await expect(page.getByRole('dialog', {
    name: 'Engineering-Auftrag erstellen'
  })).toHaveCount(mode === 'wizard' ? 1 : 0);
});
for (const valveCount of [2, 5]) test(`chat creates and applies the real model with ${valveCount} valves without opening the wizard @project-draft`, async ({
  page
}) => {
  var _ref, _payload$items;
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const project = 'network-project-' + compact;
  await page.goto(`/studio/agent?project=${compact}`);
  await page.getByRole('textbox', {
    name: 'Nachricht an den Engineering-Assistenten'
  }).fill(`Ich möchte ein kleines Projekt mit einem Raspberry-Pi, drei Temperatursensoren und ${valveCount} Ventilen.`);
  await page.locator('.eng-agent-composer').getByRole('button', {
    name: 'Senden',
    exact: true
  }).click();
  const editor = page.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  });
  await expect(editor).toContainText(`${4 + valveCount} Geräte`, {
    timeout: ENGINEERING_REPLY_BUDGET_MS
  });
  await expect(page.getByRole('dialog', {
    name: 'Engineering-Auftrag erstellen'
  })).toHaveCount(0);
  const technologies = editor.getByRole('textbox', {
    name: 'Anschlusstechnologie',
    exact: true
  });
  const owners = editor.getByRole('combobox', {
    name: 'Verarbeitender Controller',
    exact: true
  });
  const commands = editor.getByRole('combobox', {
    name: 'Ventilbefehl',
    exact: true
  });
  await expect(technologies).toHaveCount(4 + valveCount);
  await expect(owners).toHaveCount(3 + valveCount);
  await expect(commands).toHaveCount(valveCount);
  for (const field of await technologies.all()) await field.fill('ethernet');
  for (const field of await owners.all()) await field.selectOption({
    label: 'RaspberryPi'
  });
  for (const field of await commands.all()) await field.selectOption('OPEN_CLOSE');
  await editor.getByRole('combobox', {
    name: 'Technische Parameter',
    exact: true
  }).selectOption('defaults');
  await editor.getByRole('button', {
    name: 'Angaben speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 2 gespeichert');
  await page.reload();
  await expect(editor).toContainText('Revision 2');
  await expect(editor.getByLabel('Anschlusstechnologie', {
    exact: true
  }).first()).toHaveValue('ethernet');
  await editor.getByRole('button', {
    name: 'Modellvorschlag erstellen',
    exact: true
  }).click();
  await page.getByRole('button', {
    name: 'Vorschlag freigeben',
    exact: true
  }).click();
  await page.getByRole('button', {
    name: 'Ins Modell übernehmen',
    exact: true
  }).click();
  await expect(page.getByText(/Modellobjekte bestätigt/)).toBeVisible();
  await expect(page.getByRole('dialog', {
    name: 'Engineering-Auftrag erstellen'
  })).toHaveCount(0);
  const response = await page.request.get('/api/engineering/hardware-nodes', {
    headers: {
      'X-Project-ID': project
    }
  });
  expect(response.ok()).toBe(true);
  const payload = await response.json();
  const nodes = Array.isArray(payload) ? payload : (_ref = (_payload$items = payload.items) !== null && _payload$items !== void 0 ? _payload$items : payload.data) !== null && _ref !== void 0 ? _ref : [];
  expect(nodes.map(node => node.name).sort()).toEqual(['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3', ...Array.from({
    length: valveCount
  }, (_, index) => `Ventilaktor${index + 1}`)].sort());
  const controller = nodes.find(node => node.name === 'RaspberryPi');
  for (const node of nodes.filter(node => node.id !== controller.id)) expect(node.identity.system_owner_id).toBe(controller.id);
  await page.reload();
  await expect(page.getByText(/Modellobjekte bestätigt/)).toBeVisible();
});
test('new project is created from the saved draft without moving the original project @project-draft', async ({
  page
}) => {
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const origin = 'network-project-' + compact;
  await page.goto(`/studio/agent?project=${compact}`);
  await page.getByRole('textbox', {
    name: 'Nachricht an den Engineering-Assistenten'
  }).fill('Ein neues Projekt mit Raspberry Pi und drei Temperatursensoren.');
  await page.locator('.eng-agent-composer').getByRole('button', {
    name: 'Senden',
    exact: true
  }).click();
  const editor = page.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  });
  await expect(editor).toContainText('4 Geräte', {
    timeout: ENGINEERING_REPLY_BUDGET_MS
  });
  const before = await page.request.get('/api/engineering/agent/project-draft', {
    headers: {
      'X-Project-ID': origin
    }
  });
  const originalDraft = (await before.json()).data;
  await editor.getByText('Als neues Projekt verwenden', {
    exact: true
  }).click();
  await editor.getByRole('textbox', {
    name: 'Neuer Projektname',
    exact: true
  }).fill('Temperaturregelung');
  await editor.getByRole('button', {
    name: 'Neues Projekt anlegen und öffnen',
    exact: true
  }).click();
  await expect(page).toHaveURL(/\/studio\/agent\?draft=.+&project=.+/);
  const target = new URL(page.url()).searchParams.get('project');
  expect(target.replace('network-project-', '')).not.toBe(compact);
  await expect(editor).toContainText('4 Geräte');
  await page.reload();
  await expect(editor).toContainText('4 Geräte');
  const after = await page.request.get('/api/engineering/agent/project-draft', {
    headers: {
      'X-Project-ID': origin
    }
  });
  expect((await after.json()).data).toEqual(originalDraft);
  const targetResponse = await page.request.get('/api/engineering/agent/project-draft', {
    headers: {
      'X-Project-ID': target.startsWith('network-project-') ? target : 'network-project-' + target
    }
  });
  const targetDraft = (await targetResponse.json()).data;
  expect(targetDraft.draft_id).not.toBe(originalDraft.draft_id);
  expect(targetDraft.devices).toEqual(originalDraft.devices);
});
test('the saved inline draft produces and applies a real model proposal @project-draft', async ({
  page
}) => {
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const project = 'network-project-' + compact;
  await page.goto(`/studio/agent?project=${compact}`);
  await page.getByRole('textbox', {
    name: 'Nachricht an den Engineering-Assistenten'
  }).fill('Ein neues Projekt mit Raspberry Pi und drei Temperatursensoren.');
  await page.locator('.eng-agent-composer').getByRole('button', {
    name: 'Senden',
    exact: true
  }).click();
  const editor = page.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  });
  await expect(editor).toContainText('4 Geräte', {
    timeout: ENGINEERING_REPLY_BUDGET_MS
  });
  for (const field of await editor.getByRole('textbox', {
    name: 'Anschlusstechnologie',
    exact: true
  }).all()) await field.fill('ethernet');
  for (const field of await editor.getByRole('combobox', {
    name: 'Verarbeitender Controller',
    exact: true
  }).all()) await field.selectOption({
    label: 'RaspberryPi'
  });
  await editor.getByRole('combobox', {
    name: 'Technische Parameter',
    exact: true
  }).selectOption('defaults');
  await editor.getByRole('button', {
    name: 'Angaben speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 2 gespeichert');
  await expect(editor).toContainText('Revision 2');
  await expect(page.getByRole('dialog', {
    name: 'Engineering-Auftrag erstellen'
  })).toHaveCount(0);
  await editor.getByRole('button', {
    name: 'Modellvorschlag erstellen',
    exact: true
  }).click();
  const proposal = page.getByRole('region', {
    name: 'Engineering-Vorschlag'
  });
  await expect(proposal).toContainText('Freigabe offen');
  await proposal.getByRole('button', {
    name: 'Vorschlag freigeben',
    exact: true
  }).click();
  await proposal.getByRole('button', {
    name: 'Ins Modell übernehmen',
    exact: true
  }).click();
  await expect.poll(async () => {
    var _ref2, _payload$items2;
    const response = await page.request.get('/api/engineering/hardware-nodes', {
      headers: {
        'X-Project-ID': project
      }
    });
    expect(response.ok()).toBe(true);
    const payload = await response.json();
    const nodes = Array.isArray(payload) ? payload : (_ref2 = (_payload$items2 = payload.items) !== null && _payload$items2 !== void 0 ? _payload$items2 : payload.data) !== null && _ref2 !== void 0 ? _ref2 : [];
    return nodes.map(node => node.name).sort();
  }).toEqual(['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3'].sort());
  await page.reload();
  await expect(editor).toContainText('Revision 2');
  await expect(page.getByText(/Modellobjekte bestätigt/)).toBeVisible();
});
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJuYW1lcyI6WyJ0ZXN0IiwiZXhwZWN0IiwicmFuZG9tVVVJRCIsImV4ZWNGaWxlU3luYyIsIkVOR0lORUVSSU5HX1JFUExZX0JVREdFVF9NUyIsInBhZ2UiLCJfcGVyc2lzdGVkJGNvbnRleHQiLCJfcGVyc2lzdGVkJGRhdGEiLCJwcm9qZWN0IiwicnVuIiwiZ3JhcGgiLCJjbHVzdGVyX2lkIiwibGFiZWwiLCJuZXR3b3JrX2lkIiwibmV0d29ya19sYWJlbCIsImJ1c19uYW1lIiwiY29udHJvbGxlcnMiLCJlY3UiLCJzZW5zb3JzIiwiYWN0dWF0b3JzIiwicHJvbXB0IiwiSlNPTiIsInN0cmluZ2lmeSIsInN0YXJ0ZWQiLCJyZXF1ZXN0IiwicG9zdCIsImhlYWRlcnMiLCJ0aW1lb3V0IiwiZGF0YSIsIndpemFyZF9jb21tYW5kIiwiYWN0aW9uIiwicnVuX2lkIiwib3BlcmF0aW9uX2lkIiwidGFyZ2V0Iiwid2l6YXJkX2NvbnRleHQiLCJwcm9qZWN0X2lkIiwicHJvamVjdF9uYW1lIiwic2NvcGVfaWRzIiwibW9kZSIsInByb2Nlc3NfaWRzIiwidGFzayIsIm9rIiwidGV4dCIsInRvQmUiLCJpbml0aWFsIiwiZ2V0IiwianNvbiIsInNvdXJjZV9mb3JtYXQiLCJzdHJ1Y3R1cmVkX3NvdXJjZSIsImdvdG8iLCJkaWFsb2ciLCJnZXRCeVJvbGUiLCJuYW1lIiwiZXhhY3QiLCJjbGljayIsImdldEJ5VGV4dCIsImVkaXRvciIsInRvSGF2ZVZhbHVlIiwiZmlsbCIsInRvQ29udGFpblRleHQiLCJub3QiLCJ0b0JlVmlzaWJsZSIsInBlcnNpc3RlZCIsInN0YXRlIiwiY29udGV4dCIsImFnZW50X3dpemFyZF9zdGF0dXMiLCJlbmdpbmVlcmluZ19kcmFmdF9yZWYiLCJ0b0VxdWFsIiwiZHJhZnRfaWQiLCJyZXZpc2lvbiIsIndpemFyZF9yZXF1ZXN0IiwidG9Db250YWluIiwicmVsb2FkIiwiY29tcGFjdCIsInJlcGxhY2VBbGwiLCJzbGljZSIsImxvY2F0b3IiLCJmaXJzdCIsInNlc3Npb24iLCJyZW1vdGUiLCJjc3JmX3Rva2VuIiwiaW5kdXN0cnkiLCJjb250YWluZXIiLCJwcm9jZXNzIiwiZW52IiwiTklTX0UyRV9BUFBfQ09OVEFJTkVSIiwidG9NYXRjaCIsImRvY2tlciIsIk5JU19URVNUX0RPQ0tFUiIsImVuY29kaW5nIiwidHJpbSIsImRyb3BwZWQiLCJyb3V0ZSIsIm1ldGhvZCIsImNvbnRpbnVlIiwicmVzcG9uc2UiLCJmZXRjaCIsImFib3J0IiwicmVhZCIsImFjY2VwdGVkIiwicG9sbCIsInNlbmQiLCJ0b0JlRW5hYmxlZCIsInRvSGF2ZUNvdW50IiwiaW5wdXQiLCJsYXN0IiwidG9CZURpc2FibGVkIiwidW5kZWZpbmVkIiwib3duZXJzIiwiZmllbGQiLCJhbGwiLCJzZWxlY3RPcHRpb24iLCJ0YXNrcyIsImluZGV4IiwibnRoIiwiZHJhZnQiLCJkZXZpY2VzIiwibWFwIiwiZGV2aWNlIiwic29ydCIsImlzc3VlcyIsIm9yaWdpbmFsX3JlcXVpcmVtZW50IiwidmFsdmVDb3VudCIsIl9yZWYiLCJfcGF5bG9hZCRpdGVtcyIsInRlY2hub2xvZ2llcyIsImNvbW1hbmRzIiwiZ2V0QnlMYWJlbCIsInBheWxvYWQiLCJub2RlcyIsIkFycmF5IiwiaXNBcnJheSIsIml0ZW1zIiwibm9kZSIsImZyb20iLCJsZW5ndGgiLCJfIiwiY29udHJvbGxlciIsImZpbmQiLCJmaWx0ZXIiLCJpZCIsImlkZW50aXR5Iiwic3lzdGVtX293bmVyX2lkIiwib3JpZ2luIiwiYmVmb3JlIiwib3JpZ2luYWxEcmFmdCIsInRvSGF2ZVVSTCIsIlVSTCIsInVybCIsInNlYXJjaFBhcmFtcyIsInJlcGxhY2UiLCJhZnRlciIsInRhcmdldFJlc3BvbnNlIiwic3RhcnRzV2l0aCIsInRhcmdldERyYWZ0IiwicHJvcG9zYWwiLCJfcmVmMiIsIl9wYXlsb2FkJGl0ZW1zMiJdLCJzb3VyY2VzIjpbInByb2plY3QtZHJhZnQuc3BlYy50cyJdLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyB0ZXN0LCBleHBlY3QgfSBmcm9tICdwbGF5d3JpZ2h0L3Rlc3QnO1xuaW1wb3J0IHsgcmFuZG9tVVVJRCB9IGZyb20gJ25vZGU6Y3J5cHRvJztcbmltcG9ydCB7IGV4ZWNGaWxlU3luYyB9IGZyb20gJ25vZGU6Y2hpbGRfcHJvY2Vzcyc7XG5cbi8vIEZpcnN0IGFjdGlvbmFibGUgcmVwbHkgdGVzdCBhbGxvd2FuY2U6IGJhY2tlbmQvU1NFIDI5MHMgKyBvbmUgaGlzdG9yeSBQVVQgOHMgKyBVSSBleHBlY3QgMzBzLlxuLy8gU291cmNlczogc3JjL2FwcC9hcGkvYWdlbnQvY2hhdC9yb3V0ZS50cywgcGxheXdyaWdodC5jb25maWcudHM7IG5vdCBhIHdob2xlLXN0cmVhbSBib3VuZCBvciBTTEEuXG5jb25zdCBFTkdJTkVFUklOR19SRVBMWV9CVURHRVRfTVMgPSAyOTBfMDAwICsgOF8wMDAgKyAzMF8wMDA7XG5cbnRlc3QoJ25hdGl2ZSB3aXphcmQgcHJlc2VydmVzIGl0cyBjb21wbGV0ZSBzb3VyY2Ugd2hpbGUgYWRvcHRpbmcgYW4gZWRpdGVkIHNoYXJlZCBkcmFmdCBAcHJvamVjdC1kcmFmdCcsIGFzeW5jICh7IHBhZ2UgfSkgPT4ge1xuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtc2hhcmVkLW5hdGl2ZS0nICsgcmFuZG9tVVVJRCgpO1xuICBjb25zdCBydW4gPSByYW5kb21VVUlEKCk7XG4gIGNvbnN0IGdyYXBoID0gW3sgY2x1c3Rlcl9pZDogJ2RyaXZlJywgbGFiZWw6ICdSZWdlbHVuZycsIG5ldHdvcmtfaWQ6ICdjYW5fZmQnLCBuZXR3b3JrX2xhYmVsOiAnQ0FOLUZEJywgYnVzX25hbWU6ICdSZWdlbHVuZycsXG4gICAgY29udHJvbGxlcnM6IFt7IGVjdTogJ01vdG9yc3RldWVydW5nJywgc2Vuc29yczogW10sIGFjdHVhdG9yczogW10gfSwgeyBlY3U6ICdBbnplaWdlJywgc2Vuc29yczogW10sIGFjdHVhdG9yczogW10gfV0gfV07XG4gIGNvbnN0IHByb21wdCA9IGBTdHJ1a3R1cmllcnRlIFZvcmdhYmVuIGZ1ZXIgZGVuIEVuZ2luZWVyaW5nLUFnZW50ZW46XG4tIExhdWYtSUQ6ICR7cnVufVxuLSBJbmR1c3RyaWU6IEF1dG9tb3RpdmVcbi0gTmV0endlcmt0ZWNobm9sb2dpZW46IENBTi1GRCAoY2FuX2ZkKVxuLSBIYXJkd2FyZS1Tb2xsd2VydGU6IHtcImdhdGV3YXlzXCI6MSxcImVjdXNcIjoyLFwic2Vuc29yc1wiOjAsXCJhY3R1YXRvcnNcIjowfVxuLSBTeXN0ZW1jbHVzdGVyLUdyYXBoOiAke0pTT04uc3RyaW5naWZ5KGdyYXBoKX1cbktvbmtyZXRlIEF1ZmdhYmUgZGVzIE51dHplcnMsIHBlciBXaXphcmQtVWViZXJuZWhtZW4gYmVzdGFldGlndDpcbkVyemV1Z2UgTW90b3JzdGV1ZXJ1bmcgdW5kIEFuemVpZ2UgbWl0IGVpbmVtIEdhdGV3YXkgU3lzdGVtLmA7XG4gIGNvbnN0IHN0YXJ0ZWQgPSBhd2FpdCBwYWdlLnJlcXVlc3QucG9zdCgnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jaGF0JywgeyBoZWFkZXJzOiB7ICdYLVByb2plY3QtSUQnOiBwcm9qZWN0IH0sIHRpbWVvdXQ6IDEyMF8wMDAsXG4gICAgZGF0YTogeyBwcm9tcHQsIHdpemFyZF9jb21tYW5kOiB7IGFjdGlvbjogJ1NUQVJUJywgcnVuX2lkOiBydW4sIG9wZXJhdGlvbl9pZDogcmFuZG9tVVVJRCgpLCB0YXJnZXQ6ICdlbmdpbmVlcmluZ19tb2RlbCcsXG4gICAgICB3aXphcmRfY29udGV4dDogeyBwcm9qZWN0X2lkOiBwcm9qZWN0LCBydW5faWQ6IHJ1biwgcHJvamVjdF9uYW1lOiAnR2VtZWluc2FtZXIgbmF0aXZlciBBdWZ0cmFnJywgc2NvcGVfaWRzOiBbJ2VuZ2luZWVyaW5nX21vZGVsJ10sXG4gICAgICAgIG1vZGU6ICdmdWxsJywgcHJvY2Vzc19pZHM6IFsnZGVmYXVsdHMnLCAncmV2aWV3X2dhdGUnXSwgdGFzazogJ01vdG9yc3RldWVydW5nIHVuZCBBbnplaWdlIGFuIFN5c3RlbScgfSB9IH0gfSk7XG4gIGV4cGVjdChzdGFydGVkLm9rKCksIGF3YWl0IHN0YXJ0ZWQudGV4dCgpKS50b0JlKHRydWUpO1xuICBjb25zdCBpbml0aWFsID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvamVjdC1kcmFmdCcsIHsgaGVhZGVyczogeyAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCB9IH0pKS5qc29uKCk7XG4gIGV4cGVjdChpbml0aWFsLmRhdGEuc291cmNlX2Zvcm1hdCkudG9CZSgnV0laQVJEX1YyJyk7XG4gIGV4cGVjdChpbml0aWFsLmRhdGEuc3RydWN0dXJlZF9zb3VyY2UucHJvbXB0KS50b0JlKHByb21wdCk7XG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpby9lbmdpbmVlcmluZz9hc3Npc3RhbnQ9cHJvamVjdCZwcm9qZWN0PSR7cHJvamVjdH1gKTtcbiAgY29uc3QgZGlhbG9nID0gcGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJyB9KTtcbiAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnRXJnw6RuemVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgYXdhaXQgZGlhbG9nLmdldEJ5VGV4dCgnR2VtZWluc2FtZW4gUHJvamVrdGVudHd1cmYgYmVhcmJlaXRlbicsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgY29uc3QgZWRpdG9yID0gZGlhbG9nLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAnR2VzcGVpY2hlcnRlciBQcm9qZWt0ZW50d3VyZicgfSk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IuZ2V0QnlSb2xlKCd0ZXh0Ym94JywgeyBuYW1lOiAnUHJvamVrdGJlc2NocmVpYnVuZycsIGV4YWN0OiB0cnVlIH0pKS50b0hhdmVWYWx1ZShwcm9tcHQpO1xuICBhd2FpdCBlZGl0b3IuZ2V0QnlSb2xlKCd0ZXh0Ym94JywgeyBuYW1lOiAnQW5mb3JkZXJ1bmcgZXJnw6RuemVuJywgZXhhY3Q6IHRydWUgfSkuZmlsbCgnRGllIE1vZGVsbGJlc2NocmVpYnVuZyBzb2xsIGRlbiBsb2thbGVuIFJlZ2VsdW5nc3p3ZWNrIGRva3VtZW50aWVyZW4uJyk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0VyZ8Okbnp1bmcgc3BlaWNoZXJuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvci5nZXRCeVJvbGUoJ3N0YXR1cycpKS50b0NvbnRhaW5UZXh0KCdSZXZpc2lvbiAyIGdlc3BlaWNoZXJ0Jyk7XG4gIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0dlc3BlaWNoZXJ0ZW4gRW50d3VyZiBpbSBBdWZ0cmFnIMO8YmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvcikubm90LnRvQmVWaXNpYmxlKHsgdGltZW91dDogMTIwXzAwMCB9KTtcbiAgY29uc3QgcGVyc2lzdGVkID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cnLCB7IGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHByb2plY3QgfSB9KSkuanNvbigpO1xuICBjb25zdCBzdGF0ZSA9IHBlcnNpc3RlZC5jb250ZXh0ID8/IHBlcnNpc3RlZC5kYXRhPy5jb250ZXh0O1xuICBleHBlY3Qoc3RhdGUuYWdlbnRfd2l6YXJkX3N0YXR1cy5ydW5faWQpLnRvQmUocnVuKTtcbiAgZXhwZWN0KHN0YXRlLmFnZW50X3dpemFyZF9zdGF0dXMuZW5naW5lZXJpbmdfZHJhZnRfcmVmKS50b0VxdWFsKHsgZHJhZnRfaWQ6IGluaXRpYWwuZGF0YS5kcmFmdF9pZCwgcmV2aXNpb246IDIgfSk7XG4gIGV4cGVjdChzdGF0ZS53aXphcmRfcmVxdWVzdC5wcm9tcHQpLnRvQ29udGFpbihKU09OLnN0cmluZ2lmeShncmFwaCkpO1xuICBhd2FpdCBwYWdlLnJlbG9hZCgpO1xuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJyB9KSkudG9CZVZpc2libGUoKTtcbn0pO1xuXG50ZXN0KCdjb25mbGljdGluZyBlZGl0cyByZXRhaW4gaW5wdXQgYW5kIGxvYWQgdGhlIGN1cnJlbnQgcmV2aXNpb24gd2l0aG91dCBvdmVyd3JpdGluZyBpdCBAcHJvamVjdC1kcmFmdCcsIGFzeW5jICh7IHBhZ2UgfSkgPT4ge1xuICBjb25zdCBjb21wYWN0ID0gJzIwMjYwOTE1MDAwMDAwMDAwLScgKyByYW5kb21VVUlEKCkucmVwbGFjZUFsbCgnLScsICcnKS5zbGljZSgwLCA4KTtcbiAgY29uc3QgcHJvamVjdCA9ICduZXR3b3JrLXByb2plY3QtJyArIGNvbXBhY3Q7XG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpby9hZ2VudD9wcm9qZWN0PSR7Y29tcGFjdH1gKTtcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdOYWNocmljaHQgYW4gZGVuIEVuZ2luZWVyaW5nLUFzc2lzdGVudGVuJyB9KS5maWxsKCdFcnN0ZWxsZSBlaW4gUHJvamVrdCBtaXQgUmFzcGJlcnJ5IFBpIHVuZCBkcmVpIFRlbXBlcmF0dXJzZW5zb3Jlbi4nKTtcbiAgYXdhaXQgcGFnZS5sb2NhdG9yKCcuZW5nLWFnZW50LWNvbXBvc2VyJykuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdTZW5kZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xuICBjb25zdCBlZGl0b3IgPSBwYWdlLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAnR2VzcGVpY2hlcnRlciBQcm9qZWt0ZW50d3VyZicgfSk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IpLnRvQ29udGFpblRleHQoJ1JldmlzaW9uIDEnLCB7IHRpbWVvdXQ6IEVOR0lORUVSSU5HX1JFUExZX0JVREdFVF9NUyB9KTtcbiAgYXdhaXQgZWRpdG9yLmdldEJ5Um9sZSgndGV4dGJveCcsIHsgbmFtZTogJ05hbWUnLCBleGFjdDogdHJ1ZSB9KS5maXJzdCgpLmZpbGwoJ01laW5lUmVnZWx1bmcnKTtcbiAgY29uc3Qgc2Vzc2lvbiA9IGF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Jldmlldy1zZXNzaW9uJykpLmpzb24oKTtcbiAgY29uc3QgcmVtb3RlID0gYXdhaXQgcGFnZS5yZXF1ZXN0LnBvc3QoJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvamVjdC1kcmFmdCcsIHsgaGVhZGVyczoge1xuICAgICdYLVByb2plY3QtSUQnOiBwcm9qZWN0LCAnWC1IdW1hbi1SZXZpZXcnOiAnY29uZmlybWVkJywgJ1gtUmV2aWV3LUNTUkYnOiBzZXNzaW9uLmNzcmZfdG9rZW4sXG4gIH0sIGRhdGE6IHsgYWN0aW9uOiAnUkVTT0xWRScsIG9wZXJhdGlvbl9pZDogcmFuZG9tVVVJRCgpLCByZXZpc2lvbjogMSwgaW5kdXN0cnk6ICdidWlsZGluZ19hdXRvbWF0aW9uJyB9IH0pO1xuICBleHBlY3QocmVtb3RlLm9rKCkpLnRvQmUodHJ1ZSk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0FuZ2FiZW4gc3BlaWNoZXJuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvci5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ0VudHd1cmZza29uZmxpa3QnIH0pKS50b0NvbnRhaW5UZXh0KCdSZXZpc2lvbiAyJyk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IuZ2V0QnlSb2xlKCd0ZXh0Ym94JywgeyBuYW1lOiAnTmFtZScsIGV4YWN0OiB0cnVlIH0pLmZpcnN0KCkpLnRvSGF2ZVZhbHVlKCdNZWluZVJlZ2VsdW5nJyk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0FrdHVlbGxlbiBTdGFuZCBsYWRlbiB1bmQgRWluZ2FiZWtvcGllIGJlaGFsdGVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvci5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdFaW5zYXR6YmVyZWljaCcsIGV4YWN0OiB0cnVlIH0pKS50b0hhdmVWYWx1ZSgnYnVpbGRpbmdfYXV0b21hdGlvbicpO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yLmdldEJ5Um9sZSgndGV4dGJveCcsIHsgbmFtZTogJ05hbWUnLCBleGFjdDogdHJ1ZSB9KS5maXJzdCgpKS50b0hhdmVWYWx1ZSgnUmFzcGJlcnJ5UGknKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvci5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdFcmhhbHRlbmUgRWluZ2FiZW4gdm9yIGRlbSBLb25mbGlrdCcsIGV4YWN0OiB0cnVlIH0pKS50b0hhdmVWYWx1ZSgvTWVpbmVSZWdlbHVuZy8pO1xuICBhd2FpdCBlZGl0b3IuZ2V0QnlSb2xlKCd0ZXh0Ym94JywgeyBuYW1lOiAnTmFtZScsIGV4YWN0OiB0cnVlIH0pLmZpcnN0KCkuZmlsbCgnTWVpbmVSZWdlbHVuZycpO1xuICBhd2FpdCBlZGl0b3IuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdBbmdhYmVuIHNwZWljaGVybicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IuZ2V0QnlSb2xlKCdzdGF0dXMnKSkudG9Db250YWluVGV4dCgnUmV2aXNpb24gMyBnZXNwZWljaGVydCcpO1xufSk7XG5cbnRlc3QoJ2RyYWZ0IHJlY292ZXJzIGEgbG9zdCBzYXZlIHJlc3BvbnNlIGFuZCBzdXJ2aXZlcyBhcHBsaWNhdGlvbiByZXN0YXJ0IEBwcm9qZWN0LWRyYWZ0JywgYXN5bmMgKHsgcGFnZSB9KSA9PiB7XG4gIGNvbnN0IGNvbnRhaW5lciA9IHByb2Nlc3MuZW52Lk5JU19FMkVfQVBQX0NPTlRBSU5FUiE7XG4gIGV4cGVjdChjb250YWluZXIpLnRvTWF0Y2goL15uaXMtZTJlLWFwcC1bYS1mMC05XSskLyk7XG4gIGNvbnN0IGRvY2tlciA9IHByb2Nlc3MuZW52Lk5JU19URVNUX0RPQ0tFUiB8fCAnZG9ja2VyJztcbiAgZXhwZWN0KGV4ZWNGaWxlU3luYyhkb2NrZXIsIFsnaW5zcGVjdCcsIGNvbnRhaW5lciwgJy0tZm9ybWF0JywgJ3t7aW5kZXggLkNvbmZpZy5MYWJlbHMgXCJuZXR3b3JraXMudGVzdFwifX0nXSwgeyBlbmNvZGluZzogJ3V0ZjgnIH0pLnRyaW0oKSkudG9CZSgnZGlzcG9zYWJsZScpO1xuICBjb25zdCBjb21wYWN0ID0gJzIwMjYwOTE1MDAwMDAwMDAwLScgKyByYW5kb21VVUlEKCkucmVwbGFjZUFsbCgnLScsICcnKS5zbGljZSgwLCA4KTtcbiAgY29uc3QgcHJvamVjdCA9ICduZXR3b3JrLXByb2plY3QtJyArIGNvbXBhY3Q7XG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpby9hZ2VudD9wcm9qZWN0PSR7Y29tcGFjdH1gKTtcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdOYWNocmljaHQgYW4gZGVuIEVuZ2luZWVyaW5nLUFzc2lzdGVudGVuJyB9KS5maWxsKCdFcnN0ZWxsZSBlaW4gUHJvamVrdCBtaXQgUmFzcGJlcnJ5IFBpIHVuZCBkcmVpIFRlbXBlcmF0dXJzZW5zb3Jlbi4nKTtcbiAgYXdhaXQgcGFnZS5sb2NhdG9yKCcuZW5nLWFnZW50LWNvbXBvc2VyJykuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdTZW5kZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xuICBjb25zdCBlZGl0b3IgPSBwYWdlLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAnR2VzcGVpY2hlcnRlciBQcm9qZWt0ZW50d3VyZicgfSk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IpLnRvQ29udGFpblRleHQoJzQgR2Vyw6R0ZScsIHsgdGltZW91dDogRU5HSU5FRVJJTkdfUkVQTFlfQlVER0VUX01TIH0pO1xuICBhd2FpdCBlZGl0b3IuZ2V0QnlSb2xlKCd0ZXh0Ym94JywgeyBuYW1lOiAnQW5zY2hsdXNzdGVjaG5vbG9naWUnLCBleGFjdDogdHJ1ZSB9KS5maXJzdCgpLmZpbGwoJ2V0aGVybmV0Jyk7XG4gIGxldCBkcm9wcGVkID0gZmFsc2U7XG4gIGF3YWl0IHBhZ2Uucm91dGUoJyoqL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9qZWN0LWRyYWZ0JywgYXN5bmMgcm91dGUgPT4ge1xuICAgIGlmIChyb3V0ZS5yZXF1ZXN0KCkubWV0aG9kKCkgIT09ICdQT1NUJyB8fCBkcm9wcGVkKSByZXR1cm4gcm91dGUuY29udGludWUoKTtcbiAgICAvLyBFeGVjdXRlIHRoZSByZWFsIHNlcnZlciB3cml0ZSwgYnV0IGxvc2UgaXRzIHRyYW5zcG9ydCByZXNwb25zZS5cbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IHJvdXRlLmZldGNoKCk7XG4gICAgZXhwZWN0KHJlc3BvbnNlLm9rKCkpLnRvQmUodHJ1ZSk7XG4gICAgZHJvcHBlZCA9IHRydWU7XG4gICAgYXdhaXQgcm91dGUuYWJvcnQoJ2Nvbm5lY3Rpb25yZXNldCcpO1xuICB9KTtcbiAgYXdhaXQgZWRpdG9yLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnQW5nYWJlbiBzcGVpY2hlcm4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yLmdldEJ5Um9sZSgnYWxlcnQnKSkudG9CZVZpc2libGUoKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvci5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdBbnNjaGx1c3N0ZWNobm9sb2dpZScsIGV4YWN0OiB0cnVlIH0pLmZpcnN0KCkpLnRvSGF2ZVZhbHVlKCdldGhlcm5ldCcpO1xuICBjb25zdCByZWFkID0gYXN5bmMgKCkgPT4gKGF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb2plY3QtZHJhZnQnLCB7IGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHByb2plY3QgfSB9KSkuanNvbigpKS5kYXRhO1xuICBjb25zdCBhY2NlcHRlZCA9IGF3YWl0IHJlYWQoKTtcbiAgZXhwZWN0KGFjY2VwdGVkLnJldmlzaW9uKS50b0JlKDIpO1xuICBhd2FpdCBlZGl0b3IuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdBbmdhYmVuIHNwZWljaGVybicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IuZ2V0QnlSb2xlKCdzdGF0dXMnKSkudG9Db250YWluVGV4dCgnUmV2aXNpb24gMiBnZXNwZWljaGVydCcpO1xuICBleHBlY3QoYXdhaXQgcmVhZCgpKS50b0VxdWFsKGFjY2VwdGVkKTtcbiAgZXhlY0ZpbGVTeW5jKGRvY2tlciwgWydyZXN0YXJ0JywgY29udGFpbmVyXSwgeyB0aW1lb3V0OiA2MF8wMDAgfSk7XG4gIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IHtcbiAgICB0cnkgeyByZXR1cm4gKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvcmVhZHknLCB7IHRpbWVvdXQ6IDIwMDAgfSkpLm9rKCk7IH0gY2F0Y2ggeyByZXR1cm4gZmFsc2U7IH1cbiAgfSwgeyB0aW1lb3V0OiAxMjBfMDAwIH0pLnRvQmUodHJ1ZSk7XG4gIGF3YWl0IHBhZ2UucmVsb2FkKCk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IpLnRvQ29udGFpblRleHQoJ1JldmlzaW9uIDInKTtcbiAgZXhwZWN0KGF3YWl0IHJlYWQoKSkudG9FcXVhbChhY2NlcHRlZCk7XG59KTtcblxudGVzdCgncmVtb3ZpbmcgYSBkcmFmdCBkZXZpY2Ugc3Vydml2ZXMgc2F2ZSwgYW1lbmRtZW50IGFuZCByZWxvYWQgQHByb2plY3QtZHJhZnQnLCBhc3luYyAoeyBwYWdlIH0pID0+IHtcbiAgY29uc3QgY29tcGFjdCA9ICcyMDI2MDkxNTAwMDAwMDAwMC0nICsgcmFuZG9tVVVJRCgpLnJlcGxhY2VBbGwoJy0nLCAnJykuc2xpY2UoMCwgOCk7XG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpby9hZ2VudD9wcm9qZWN0PSR7Y29tcGFjdH1gKTtcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdOYWNocmljaHQgYW4gZGVuIEVuZ2luZWVyaW5nLUFzc2lzdGVudGVuJyB9KS5maWxsKCdFcnN0ZWxsZSBlaW4gUHJvamVrdCBtaXQgZWluZW0gUmFzcGJlcnJ5IFBpIHVuZCBkcmVpIFRlbXBlcmF0dXJzZW5zb3Jlbi4nKTtcbiAgY29uc3Qgc2VuZCA9IHBhZ2UubG9jYXRvcignLmVuZy1hZ2VudC1jb21wb3NlcicpLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnU2VuZGVuJywgZXhhY3Q6IHRydWUgfSk7XG4gIGF3YWl0IGV4cGVjdChzZW5kKS50b0JlRW5hYmxlZCh7IHRpbWVvdXQ6IDEyMF8wMDAgfSk7XG4gIGF3YWl0IHNlbmQuY2xpY2soKTtcbiAgY29uc3QgZWRpdG9yID0gcGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ0dlc3BlaWNoZXJ0ZXIgUHJvamVrdGVudHd1cmYnIH0pO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yKS50b0NvbnRhaW5UZXh0KCc0IEdlcsOkdGUnLCB7IHRpbWVvdXQ6IEVOR0lORUVSSU5HX1JFUExZX0JVREdFVF9NUyB9KTtcbiAgYXdhaXQgZWRpdG9yLmdldEJ5Um9sZSgnZ3JvdXAnLCB7IG5hbWU6ICdUZW1wZXJhdHVyc2Vuc29yMyDCtyBTRU5TT1InLCBleGFjdDogdHJ1ZSB9KVxuICAgIC5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0F1cyBFbnR3dXJmIGVudGZlcm5lbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0FuZ2FiZW4gc3BlaWNoZXJuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvci5nZXRCeVJvbGUoJ3N0YXR1cycpKS50b0NvbnRhaW5UZXh0KCdSZXZpc2lvbiAyIGdlc3BlaWNoZXJ0Jyk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdBbmZvcmRlcnVuZyBlcmfDpG56ZW4nLCBleGFjdDogdHJ1ZSB9KS5maWxsKCdadXPDpHR6bGljaCB6d2VpIERydWNrc2Vuc29yZW4uJyk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0VyZ8Okbnp1bmcgc3BlaWNoZXJuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvci5nZXRCeVJvbGUoJ3N0YXR1cycpKS50b0NvbnRhaW5UZXh0KCdSZXZpc2lvbiAzIGdlc3BlaWNoZXJ0Jyk7XG4gIGF3YWl0IHBhZ2UucmVsb2FkKCk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IpLnRvQ29udGFpblRleHQoJzUgR2Vyw6R0ZScpO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yLmdldEJ5Um9sZSgnZ3JvdXAnLCB7IG5hbWU6ICdUZW1wZXJhdHVyc2Vuc29yMyDCtyBTRU5TT1InLCBleGFjdDogdHJ1ZSB9KSkudG9IYXZlQ291bnQoMCk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IuZ2V0QnlSb2xlKCdncm91cCcsIHsgbmFtZTogJ0RydWNrc2Vuc29yMiDCtyBTRU5TT1InLCBleGFjdDogdHJ1ZSB9KSkudG9CZVZpc2libGUoKTtcbn0pO1xuXG5mb3IgKGNvbnN0IG1vZGUgb2YgWydjaGF0JywgJ3dpemFyZCddKSB0ZXN0KGBtaXNzaW5nIGNvbnRyb2xsZXIgY2FuIGJlIGFkZGVkIGluICR7bW9kZX0gYW5kIHRoZSByZXF1aXJlbWVudCByZW1haW5zIGVkaXRhYmxlIEBwcm9qZWN0LWRyYWZ0YCwgYXN5bmMgKHsgcGFnZSB9KSA9PiB7XG4gIGNvbnN0IGNvbXBhY3QgPSAnMjAyNjA5MTUwMDAwMDAwMDAtJyArIHJhbmRvbVVVSUQoKS5yZXBsYWNlQWxsKCctJywgJycpLnNsaWNlKDAsIDgpO1xuICBjb25zdCBwcm9qZWN0ID0gJ25ldHdvcmstcHJvamVjdC0nICsgY29tcGFjdDtcbiAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvL2FnZW50P3Byb2plY3Q9JHtjb21wYWN0fWApO1xuICBjb25zdCBpbnB1dCA9IHBhZ2UuZ2V0QnlSb2xlKCd0ZXh0Ym94JywgeyBuYW1lOiAnTmFjaHJpY2h0IGFuIGRlbiBFbmdpbmVlcmluZy1Bc3Npc3RlbnRlbicgfSk7XG4gIGF3YWl0IGlucHV0LmZpbGwoJ0VpbiBuZXVlcyBQcm9qZWt0IG1pdCBkcmVpIFNlbnNvcmVuLicpO1xuICBhd2FpdCBwYWdlLmxvY2F0b3IoJy5lbmctYWdlbnQtY29tcG9zZXInKS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ1NlbmRlbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGxldCBlZGl0b3IgPSBwYWdlLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAnR2VzcGVpY2hlcnRlciBQcm9qZWt0ZW50d3VyZicgfSkubGFzdCgpO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yKS50b0NvbnRhaW5UZXh0KCczIEdlcsOkdGUnLCB7IHRpbWVvdXQ6IEVOR0lORUVSSU5HX1JFUExZX0JVREdFVF9NUyB9KTtcbiAgYXdhaXQgZWRpdG9yLmdldEJ5VGV4dCgnT2ZmZW5lIEFuZ2FiZW4nLCB7IGV4YWN0OiBmYWxzZSB9KS5jbGljaygpO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yKS50b0NvbnRhaW5UZXh0KCdDb250cm9sbGVyIGVyZ8OkbnplbicpO1xuICBpZiAobW9kZSA9PT0gJ3dpemFyZCcpIHtcbiAgICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAvSW0gV2l6YXJkIGJlYXJiZWl0ZW4vIH0pLmNsaWNrKCk7XG4gICAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSkpLnRvQmVWaXNpYmxlKCk7XG4gICAgZWRpdG9yID0gcGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ0dlc3BlaWNoZXJ0ZXIgUHJvamVrdGVudHd1cmYnIH0pLmxhc3QoKTtcbiAgICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0F1ZnRyYWcgc3RhcnRlbicsIGV4YWN0OiB0cnVlIH0pKS50b0JlRGlzYWJsZWQoKTtcbiAgICBhd2FpdCBlZGl0b3IuZ2V0QnlSb2xlKCd0ZXh0Ym94JywgeyBuYW1lOiAnQW5mb3JkZXJ1bmcgZXJnw6RuemVuJywgZXhhY3Q6IHRydWUgfSkuZmlsbCgnRXJnw6RuemUgZWluZW4gUmFzcGJlcnJ5IFBpLicpO1xuICAgIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0VyZ8Okbnp1bmcgc3BlaWNoZXJuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgfSBlbHNlIHtcbiAgICBhd2FpdCBpbnB1dC5maWxsKCdFcmfDpG56ZSBlaW5lbiBSYXNwYmVycnkgUGkuJyk7XG4gICAgYXdhaXQgcGFnZS5sb2NhdG9yKCcuZW5nLWFnZW50LWNvbXBvc2VyJykuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdTZW5kZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xuICB9XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IpLnRvQ29udGFpblRleHQoJzQgR2Vyw6R0ZScsIG1vZGUgPT09ICdjaGF0JyA/IHsgdGltZW91dDogRU5HSU5FRVJJTkdfUkVQTFlfQlVER0VUX01TIH0gOiB1bmRlZmluZWQpO1xuICBhd2FpdCBwYWdlLnJlbG9hZCgpO1xuICBlZGl0b3IgPSBwYWdlLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAnR2VzcGVpY2hlcnRlciBQcm9qZWt0ZW50d3VyZicgfSkubGFzdCgpO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yKS50b0NvbnRhaW5UZXh0KCdSZXZpc2lvbiAyJyk7XG4gIGNvbnN0IG93bmVycyA9IGVkaXRvci5nZXRCeVJvbGUoJ2NvbWJvYm94JywgeyBuYW1lOiAnVmVyYXJiZWl0ZW5kZXIgQ29udHJvbGxlcicsIGV4YWN0OiB0cnVlIH0pO1xuICBhd2FpdCBleHBlY3Qob3duZXJzKS50b0hhdmVDb3VudCgzKTtcbiAgZm9yIChjb25zdCBmaWVsZCBvZiBhd2FpdCBvd25lcnMuYWxsKCkpIGF3YWl0IGZpZWxkLnNlbGVjdE9wdGlvbih7IGxhYmVsOiAnUmFzcGJlcnJ5UGknIH0pO1xuICBjb25zdCB0YXNrcyA9IGVkaXRvci5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdNZXNzZ3LDtsOfZSBvZGVyIEdlcsOkdGVhdWZnYWJlJywgZXhhY3Q6IHRydWUgfSk7XG4gIGF3YWl0IGV4cGVjdCh0YXNrcykudG9IYXZlQ291bnQoNCk7XG4gIGZvciAobGV0IGluZGV4ID0gMTsgaW5kZXggPCA0OyBpbmRleCsrKSBhd2FpdCB0YXNrcy5udGgoaW5kZXgpLmZpbGwoJ1RlbXBlcmF0dXIgbWVzc2VuJyk7XG4gIGZvciAoY29uc3QgZmllbGQgb2YgYXdhaXQgZWRpdG9yLmdldEJ5Um9sZSgndGV4dGJveCcsIHsgbmFtZTogJ0Fuc2NobHVzc3RlY2hub2xvZ2llJywgZXhhY3Q6IHRydWUgfSkuYWxsKCkpIGF3YWl0IGZpZWxkLmZpbGwoJ2V0aGVybmV0Jyk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2NvbWJvYm94JywgeyBuYW1lOiAnVGVjaG5pc2NoZSBQYXJhbWV0ZXInLCBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ2RlZmF1bHRzJyk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0FuZ2FiZW4gc3BlaWNoZXJuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvci5nZXRCeVJvbGUoJ3N0YXR1cycpKS50b0NvbnRhaW5UZXh0KCdSZXZpc2lvbiAzIGdlc3BlaWNoZXJ0Jyk7XG4gIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9qZWN0LWRyYWZ0JywgeyBoZWFkZXJzOiB7ICdYLVByb2plY3QtSUQnOiBwcm9qZWN0IH0gfSk7XG4gIGNvbnN0IGRyYWZ0ID0gKGF3YWl0IHJlc3BvbnNlLmpzb24oKSkuZGF0YTtcbiAgZXhwZWN0KGRyYWZ0LmRldmljZXMubWFwKChkZXZpY2U6IHsgbmFtZTogc3RyaW5nIH0pID0+IGRldmljZS5uYW1lKS5zb3J0KCkpLnRvRXF1YWwoWydSYXNwYmVycnlQaScsICdTZW5zb3IxJywgJ1NlbnNvcjInLCAnU2Vuc29yMyddKTtcbiAgZXhwZWN0KGRyYWZ0Lmlzc3VlcykudG9FcXVhbChbXSk7XG4gIGV4cGVjdChkcmFmdC5vcmlnaW5hbF9yZXF1aXJlbWVudCkudG9CZSgnRWluIG5ldWVzIFByb2pla3QgbWl0IGRyZWkgU2Vuc29yZW4uJyk7XG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5Um9sZSgnZGlhbG9nJywgeyBuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcnN0ZWxsZW4nIH0pKS50b0hhdmVDb3VudChtb2RlID09PSAnd2l6YXJkJyA/IDEgOiAwKTtcbn0pO1xuXG5mb3IgKGNvbnN0IHZhbHZlQ291bnQgb2YgWzIsIDVdKSB0ZXN0KGBjaGF0IGNyZWF0ZXMgYW5kIGFwcGxpZXMgdGhlIHJlYWwgbW9kZWwgd2l0aCAke3ZhbHZlQ291bnR9IHZhbHZlcyB3aXRob3V0IG9wZW5pbmcgdGhlIHdpemFyZCBAcHJvamVjdC1kcmFmdGAsIGFzeW5jICh7IHBhZ2UgfSkgPT4ge1xuICBjb25zdCBjb21wYWN0ID0gJzIwMjYwOTE1MDAwMDAwMDAwLScgKyByYW5kb21VVUlEKCkucmVwbGFjZUFsbCgnLScsICcnKS5zbGljZSgwLCA4KTtcbiAgY29uc3QgcHJvamVjdCA9ICduZXR3b3JrLXByb2plY3QtJyArIGNvbXBhY3Q7XG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpby9hZ2VudD9wcm9qZWN0PSR7Y29tcGFjdH1gKTtcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdOYWNocmljaHQgYW4gZGVuIEVuZ2luZWVyaW5nLUFzc2lzdGVudGVuJyB9KS5maWxsKFxuICAgIGBJY2ggbcO2Y2h0ZSBlaW4ga2xlaW5lcyBQcm9qZWt0IG1pdCBlaW5lbSBSYXNwYmVycnktUGksIGRyZWkgVGVtcGVyYXR1cnNlbnNvcmVuIHVuZCAke3ZhbHZlQ291bnR9IFZlbnRpbGVuLmApO1xuICBhd2FpdCBwYWdlLmxvY2F0b3IoJy5lbmctYWdlbnQtY29tcG9zZXInKS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ1NlbmRlbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGNvbnN0IGVkaXRvciA9IHBhZ2UuZ2V0QnlSb2xlKCdyZWdpb24nLCB7IG5hbWU6ICdHZXNwZWljaGVydGVyIFByb2pla3RlbnR3dXJmJyB9KTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvcikudG9Db250YWluVGV4dChgJHs0ICsgdmFsdmVDb3VudH0gR2Vyw6R0ZWAsIHsgdGltZW91dDogRU5HSU5FRVJJTkdfUkVQTFlfQlVER0VUX01TIH0pO1xuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJyB9KSkudG9IYXZlQ291bnQoMCk7XG4gIGNvbnN0IHRlY2hub2xvZ2llcyA9IGVkaXRvci5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdBbnNjaGx1c3N0ZWNobm9sb2dpZScsIGV4YWN0OiB0cnVlIH0pO1xuICBjb25zdCBvd25lcnMgPSBlZGl0b3IuZ2V0QnlSb2xlKCdjb21ib2JveCcsIHsgbmFtZTogJ1ZlcmFyYmVpdGVuZGVyIENvbnRyb2xsZXInLCBleGFjdDogdHJ1ZSB9KTtcbiAgY29uc3QgY29tbWFuZHMgPSBlZGl0b3IuZ2V0QnlSb2xlKCdjb21ib2JveCcsIHsgbmFtZTogJ1ZlbnRpbGJlZmVobCcsIGV4YWN0OiB0cnVlIH0pO1xuICBhd2FpdCBleHBlY3QodGVjaG5vbG9naWVzKS50b0hhdmVDb3VudCg0ICsgdmFsdmVDb3VudCk7XG4gIGF3YWl0IGV4cGVjdChvd25lcnMpLnRvSGF2ZUNvdW50KDMgKyB2YWx2ZUNvdW50KTtcbiAgYXdhaXQgZXhwZWN0KGNvbW1hbmRzKS50b0hhdmVDb3VudCh2YWx2ZUNvdW50KTtcbiAgZm9yIChjb25zdCBmaWVsZCBvZiBhd2FpdCB0ZWNobm9sb2dpZXMuYWxsKCkpIGF3YWl0IGZpZWxkLmZpbGwoJ2V0aGVybmV0Jyk7XG4gIGZvciAoY29uc3QgZmllbGQgb2YgYXdhaXQgb3duZXJzLmFsbCgpKSBhd2FpdCBmaWVsZC5zZWxlY3RPcHRpb24oeyBsYWJlbDogJ1Jhc3BiZXJyeVBpJyB9KTtcbiAgZm9yIChjb25zdCBmaWVsZCBvZiBhd2FpdCBjb21tYW5kcy5hbGwoKSkgYXdhaXQgZmllbGQuc2VsZWN0T3B0aW9uKCdPUEVOX0NMT1NFJyk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2NvbWJvYm94JywgeyBuYW1lOiAnVGVjaG5pc2NoZSBQYXJhbWV0ZXInLCBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ2RlZmF1bHRzJyk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0FuZ2FiZW4gc3BlaWNoZXJuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvci5nZXRCeVJvbGUoJ3N0YXR1cycpKS50b0NvbnRhaW5UZXh0KCdSZXZpc2lvbiAyIGdlc3BlaWNoZXJ0Jyk7XG4gIGF3YWl0IHBhZ2UucmVsb2FkKCk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IpLnRvQ29udGFpblRleHQoJ1JldmlzaW9uIDInKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvci5nZXRCeUxhYmVsKCdBbnNjaGx1c3N0ZWNobm9sb2dpZScsIHsgZXhhY3Q6IHRydWUgfSkuZmlyc3QoKSkudG9IYXZlVmFsdWUoJ2V0aGVybmV0Jyk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ01vZGVsbHZvcnNjaGxhZyBlcnN0ZWxsZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnVm9yc2NobGFnIGZyZWlnZWJlbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdJbnMgTW9kZWxsIMO8YmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KC9Nb2RlbGxvYmpla3RlIGJlc3TDpHRpZ3QvKSkudG9CZVZpc2libGUoKTtcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSkpLnRvSGF2ZUNvdW50KDApO1xuICBjb25zdCByZXNwb25zZSA9IGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvaGFyZHdhcmUtbm9kZXMnLCB7IGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHByb2plY3QgfSB9KTtcbiAgZXhwZWN0KHJlc3BvbnNlLm9rKCkpLnRvQmUodHJ1ZSk7XG4gIGNvbnN0IHBheWxvYWQgPSBhd2FpdCByZXNwb25zZS5qc29uKCk7XG4gIGNvbnN0IG5vZGVzID0gQXJyYXkuaXNBcnJheShwYXlsb2FkKSA/IHBheWxvYWQgOiBwYXlsb2FkLml0ZW1zID8/IHBheWxvYWQuZGF0YSA/PyBbXTtcbiAgZXhwZWN0KG5vZGVzLm1hcCgobm9kZTogeyBuYW1lOiBzdHJpbmcgfSkgPT4gbm9kZS5uYW1lKS5zb3J0KCkpLnRvRXF1YWwoXG4gICAgWydSYXNwYmVycnlQaScsICdUZW1wZXJhdHVyc2Vuc29yMScsICdUZW1wZXJhdHVyc2Vuc29yMicsICdUZW1wZXJhdHVyc2Vuc29yMycsXG4gICAgICAuLi5BcnJheS5mcm9tKHsgbGVuZ3RoOiB2YWx2ZUNvdW50IH0sIChfLCBpbmRleCkgPT4gYFZlbnRpbGFrdG9yJHtpbmRleCArIDF9YCldLnNvcnQoKSk7XG4gIGNvbnN0IGNvbnRyb2xsZXIgPSBub2Rlcy5maW5kKChub2RlOiB7IG5hbWU6IHN0cmluZyB9KSA9PiBub2RlLm5hbWUgPT09ICdSYXNwYmVycnlQaScpO1xuICBmb3IgKGNvbnN0IG5vZGUgb2Ygbm9kZXMuZmlsdGVyKChub2RlOiB7IGlkOiBzdHJpbmcgfSkgPT4gbm9kZS5pZCAhPT0gY29udHJvbGxlci5pZCkpIGV4cGVjdChub2RlLmlkZW50aXR5LnN5c3RlbV9vd25lcl9pZCkudG9CZShjb250cm9sbGVyLmlkKTtcbiAgYXdhaXQgcGFnZS5yZWxvYWQoKTtcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KC9Nb2RlbGxvYmpla3RlIGJlc3TDpHRpZ3QvKSkudG9CZVZpc2libGUoKTtcbn0pO1xuXG50ZXN0KCduZXcgcHJvamVjdCBpcyBjcmVhdGVkIGZyb20gdGhlIHNhdmVkIGRyYWZ0IHdpdGhvdXQgbW92aW5nIHRoZSBvcmlnaW5hbCBwcm9qZWN0IEBwcm9qZWN0LWRyYWZ0JywgYXN5bmMgKHsgcGFnZSB9KSA9PiB7XG4gIGNvbnN0IGNvbXBhY3QgPSAnMjAyNjA5MTUwMDAwMDAwMDAtJyArIHJhbmRvbVVVSUQoKS5yZXBsYWNlQWxsKCctJywgJycpLnNsaWNlKDAsIDgpO1xuICBjb25zdCBvcmlnaW4gPSAnbmV0d29yay1wcm9qZWN0LScgKyBjb21wYWN0O1xuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8vYWdlbnQ/cHJvamVjdD0ke2NvbXBhY3R9YCk7XG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCd0ZXh0Ym94JywgeyBuYW1lOiAnTmFjaHJpY2h0IGFuIGRlbiBFbmdpbmVlcmluZy1Bc3Npc3RlbnRlbicgfSkuZmlsbChcbiAgICAnRWluIG5ldWVzIFByb2pla3QgbWl0IFJhc3BiZXJyeSBQaSB1bmQgZHJlaSBUZW1wZXJhdHVyc2Vuc29yZW4uJyk7XG4gIGF3YWl0IHBhZ2UubG9jYXRvcignLmVuZy1hZ2VudC1jb21wb3NlcicpLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnU2VuZGVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgY29uc3QgZWRpdG9yID0gcGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ0dlc3BlaWNoZXJ0ZXIgUHJvamVrdGVudHd1cmYnIH0pO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yKS50b0NvbnRhaW5UZXh0KCc0IEdlcsOkdGUnLCB7IHRpbWVvdXQ6IEVOR0lORUVSSU5HX1JFUExZX0JVREdFVF9NUyB9KTtcbiAgY29uc3QgYmVmb3JlID0gYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9qZWN0LWRyYWZ0JywgeyBoZWFkZXJzOiB7ICdYLVByb2plY3QtSUQnOiBvcmlnaW4gfSB9KTtcbiAgY29uc3Qgb3JpZ2luYWxEcmFmdCA9IChhd2FpdCBiZWZvcmUuanNvbigpKS5kYXRhO1xuICBhd2FpdCBlZGl0b3IuZ2V0QnlUZXh0KCdBbHMgbmV1ZXMgUHJvamVrdCB2ZXJ3ZW5kZW4nLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdOZXVlciBQcm9qZWt0bmFtZScsIGV4YWN0OiB0cnVlIH0pLmZpbGwoJ1RlbXBlcmF0dXJyZWdlbHVuZycpO1xuICBhd2FpdCBlZGl0b3IuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdOZXVlcyBQcm9qZWt0IGFubGVnZW4gdW5kIMO2ZmZuZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xuICBhd2FpdCBleHBlY3QocGFnZSkudG9IYXZlVVJMKC9cXC9zdHVkaW9cXC9hZ2VudFxcP2RyYWZ0PS4rJnByb2plY3Q9LisvKTtcbiAgY29uc3QgdGFyZ2V0ID0gbmV3IFVSTChwYWdlLnVybCgpKS5zZWFyY2hQYXJhbXMuZ2V0KCdwcm9qZWN0JykhO1xuICBleHBlY3QodGFyZ2V0LnJlcGxhY2UoJ25ldHdvcmstcHJvamVjdC0nLCAnJykpLm5vdC50b0JlKGNvbXBhY3QpO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yKS50b0NvbnRhaW5UZXh0KCc0IEdlcsOkdGUnKTtcbiAgYXdhaXQgcGFnZS5yZWxvYWQoKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvcikudG9Db250YWluVGV4dCgnNCBHZXLDpHRlJyk7XG4gIGNvbnN0IGFmdGVyID0gYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9qZWN0LWRyYWZ0JywgeyBoZWFkZXJzOiB7ICdYLVByb2plY3QtSUQnOiBvcmlnaW4gfSB9KTtcbiAgZXhwZWN0KChhd2FpdCBhZnRlci5qc29uKCkpLmRhdGEpLnRvRXF1YWwob3JpZ2luYWxEcmFmdCk7XG4gIGNvbnN0IHRhcmdldFJlc3BvbnNlID0gYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9qZWN0LWRyYWZ0Jywge1xuICAgIGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHRhcmdldC5zdGFydHNXaXRoKCduZXR3b3JrLXByb2plY3QtJykgPyB0YXJnZXQgOiAnbmV0d29yay1wcm9qZWN0LScgKyB0YXJnZXQgfSxcbiAgfSk7XG4gIGNvbnN0IHRhcmdldERyYWZ0ID0gKGF3YWl0IHRhcmdldFJlc3BvbnNlLmpzb24oKSkuZGF0YTtcbiAgZXhwZWN0KHRhcmdldERyYWZ0LmRyYWZ0X2lkKS5ub3QudG9CZShvcmlnaW5hbERyYWZ0LmRyYWZ0X2lkKTtcbiAgZXhwZWN0KHRhcmdldERyYWZ0LmRldmljZXMpLnRvRXF1YWwob3JpZ2luYWxEcmFmdC5kZXZpY2VzKTtcbn0pO1xuXG50ZXN0KCd0aGUgc2F2ZWQgaW5saW5lIGRyYWZ0IHByb2R1Y2VzIGFuZCBhcHBsaWVzIGEgcmVhbCBtb2RlbCBwcm9wb3NhbCBAcHJvamVjdC1kcmFmdCcsIGFzeW5jICh7IHBhZ2UgfSkgPT4ge1xuICBjb25zdCBjb21wYWN0ID0gJzIwMjYwOTE1MDAwMDAwMDAwLScgKyByYW5kb21VVUlEKCkucmVwbGFjZUFsbCgnLScsICcnKS5zbGljZSgwLCA4KTtcbiAgY29uc3QgcHJvamVjdCA9ICduZXR3b3JrLXByb2plY3QtJyArIGNvbXBhY3Q7XG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpby9hZ2VudD9wcm9qZWN0PSR7Y29tcGFjdH1gKTtcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdOYWNocmljaHQgYW4gZGVuIEVuZ2luZWVyaW5nLUFzc2lzdGVudGVuJyB9KS5maWxsKFxuICAgICdFaW4gbmV1ZXMgUHJvamVrdCBtaXQgUmFzcGJlcnJ5IFBpIHVuZCBkcmVpIFRlbXBlcmF0dXJzZW5zb3Jlbi4nKTtcbiAgYXdhaXQgcGFnZS5sb2NhdG9yKCcuZW5nLWFnZW50LWNvbXBvc2VyJykuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdTZW5kZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xuICBjb25zdCBlZGl0b3IgPSBwYWdlLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAnR2VzcGVpY2hlcnRlciBQcm9qZWt0ZW50d3VyZicgfSk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IpLnRvQ29udGFpblRleHQoJzQgR2Vyw6R0ZScsIHsgdGltZW91dDogRU5HSU5FRVJJTkdfUkVQTFlfQlVER0VUX01TIH0pO1xuICBmb3IgKGNvbnN0IGZpZWxkIG9mIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdBbnNjaGx1c3N0ZWNobm9sb2dpZScsIGV4YWN0OiB0cnVlIH0pLmFsbCgpKSBhd2FpdCBmaWVsZC5maWxsKCdldGhlcm5ldCcpO1xuICBmb3IgKGNvbnN0IGZpZWxkIG9mIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2NvbWJvYm94JywgeyBuYW1lOiAnVmVyYXJiZWl0ZW5kZXIgQ29udHJvbGxlcicsIGV4YWN0OiB0cnVlIH0pLmFsbCgpKSBhd2FpdCBmaWVsZC5zZWxlY3RPcHRpb24oeyBsYWJlbDogJ1Jhc3BiZXJyeVBpJyB9KTtcbiAgYXdhaXQgZWRpdG9yLmdldEJ5Um9sZSgnY29tYm9ib3gnLCB7IG5hbWU6ICdUZWNobmlzY2hlIFBhcmFtZXRlcicsIGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbignZGVmYXVsdHMnKTtcbiAgYXdhaXQgZWRpdG9yLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnQW5nYWJlbiBzcGVpY2hlcm4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yLmdldEJ5Um9sZSgnc3RhdHVzJykpLnRvQ29udGFpblRleHQoJ1JldmlzaW9uIDIgZ2VzcGVpY2hlcnQnKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvcikudG9Db250YWluVGV4dCgnUmV2aXNpb24gMicpO1xuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJyB9KSkudG9IYXZlQ291bnQoMCk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ01vZGVsbHZvcnNjaGxhZyBlcnN0ZWxsZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xuICBjb25zdCBwcm9wb3NhbCA9IHBhZ2UuZ2V0QnlSb2xlKCdyZWdpb24nLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1Wb3JzY2hsYWcnIH0pO1xuICBhd2FpdCBleHBlY3QocHJvcG9zYWwpLnRvQ29udGFpblRleHQoJ0ZyZWlnYWJlIG9mZmVuJyk7XG4gIGF3YWl0IHByb3Bvc2FsLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnVm9yc2NobGFnIGZyZWlnZWJlbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGF3YWl0IHByb3Bvc2FsLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnSW5zIE1vZGVsbCDDvGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvaGFyZHdhcmUtbm9kZXMnLCB7IGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHByb2plY3QgfSB9KTtcbiAgICBleHBlY3QocmVzcG9uc2Uub2soKSkudG9CZSh0cnVlKTtcbiAgICBjb25zdCBwYXlsb2FkID0gYXdhaXQgcmVzcG9uc2UuanNvbigpO1xuICAgIGNvbnN0IG5vZGVzID0gQXJyYXkuaXNBcnJheShwYXlsb2FkKSA/IHBheWxvYWQgOiBwYXlsb2FkLml0ZW1zID8/IHBheWxvYWQuZGF0YSA/PyBbXTtcbiAgICByZXR1cm4gbm9kZXMubWFwKChub2RlOiB7IG5hbWU6IHN0cmluZyB9KSA9PiBub2RlLm5hbWUpLnNvcnQoKTtcbiAgfSkudG9FcXVhbChbJ1Jhc3BiZXJyeVBpJywgJ1RlbXBlcmF0dXJzZW5zb3IxJywgJ1RlbXBlcmF0dXJzZW5zb3IyJywgJ1RlbXBlcmF0dXJzZW5zb3IzJ10uc29ydCgpKTtcbiAgYXdhaXQgcGFnZS5yZWxvYWQoKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvcikudG9Db250YWluVGV4dCgnUmV2aXNpb24gMicpO1xuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoL01vZGVsbG9iamVrdGUgYmVzdMOkdGlndC8pKS50b0JlVmlzaWJsZSgpO1xufSk7XG4iXSwibWFwcGluZ3MiOiJBQUFBLFNBQVNBLElBQUksRUFBRUMsTUFBTSxRQUFRLGlCQUFpQjtBQUM5QyxTQUFTQyxVQUFVLFFBQVEsYUFBYTtBQUN4QyxTQUFTQyxZQUFZLFFBQVEsb0JBQW9COztBQUVqRDtBQUNBO0FBQ0EsTUFBTUMsMkJBQTJC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