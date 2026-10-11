import {test, expect} from 'playwright/test';
import {randomUUID} from 'node:crypto';

test('safety requirement persists with explicit profile and remains unapproved @safety-assurance', async ({page}) => {
  const project = 'nis-e2e-safety-' + randomUUID(), headers = {'X-Project-ID': project};
  const nodeResponse = await page.request.post('/api/engineering/hardware-nodes', {headers, data: {name: 'Lenkung', device_type: 'ECU'}});
  expect(nodeResponse.ok()).toBeTruthy(); const node = await nodeResponse.json();
  const functionResponse = await page.request.post('/api/engineering/functions', {headers, data: {name: 'Lenkung regeln', hardware_node_id: node.id}});
  expect(functionResponse.ok()).toBeTruthy(); const owner = await functionResponse.json();
  const routeResponse = await page.request.post('/api/engineering/routing', {headers, data: {name: 'Lenkungspfad', source: {node_id: node.id}, destinations: [{node_id: node.id}]}});
  expect(routeResponse.ok()).toBeTruthy(); const route = await routeResponse.json();
  await page.goto(`/studio/intelligence?project=${encodeURIComponent(project)}`);
  const panel = page.getByRole('region', {name: 'Sicherheitsanforderungen und Prüfbelege'});
  await expect(panel).toBeVisible();
  await expect(panel).toContainText('Keine Sicherheitsanforderungen erfasst');
  await panel.getByRole('button', {name: 'Anforderung erfassen', exact: true}).click();
  await panel.getByLabel('Name', {exact: true}).fill('Explizite Safety-Anforderung');
  await panel.getByRole('combobox', {name: 'Funktion', exact: true}).selectOption(owner.id);
  await panel.getByLabel('Versionierte Konfiguration').fill(JSON.stringify({
    profile: {standard: 'ISO 26262', edition: '2018', domain: 'road_vehicle', applicability: 'UNRESOLVED', reason: 'Fachliches Review erforderlich'},
    hazard_ref: 'H-1', safety_goal_ref: 'SG-1', route_ids: [route.id], criteria: {deadline_ms: 20, required_protections: [], fault_cases: []}
  }));
  await panel.getByRole('button', {name: 'Anforderung speichern', exact: true}).click();
  await expect(panel.getByRole('cell', {name: 'Explizite Safety-Anforderung', exact: true})).toBeVisible();
  await page.reload(); await expect(panel.getByRole('cell', {name: 'Explizite Safety-Anforderung', exact: true})).toBeVisible();
  const records = await (await page.request.get('/api/engineering/safety-requirements', {headers})).json();
  expect(records.items[0].approval_state).toBe('pending');
  expect(records.items[0].version).toBe(1);
  const report = await (await page.request.get('/api/engineering/intelligence/safety?download=1', {headers})).json();
  expect(report.payload.release_approved).toBe(false);
  expect(report.payload.assessment.technical_status).toBe('NOT_EVALUATED');
  await panel.getByRole('button', {name: 'Bearbeiten', exact: true}).click();
  await panel.getByLabel('Name', {exact: true}).fill('Geprüfter Änderungsentwurf');
  await panel.getByRole('button', {name: 'Anforderung speichern', exact: true}).click();
  await expect(panel.getByRole('cell', {name: 'Geprüfter Änderungsentwurf', exact: true})).toBeVisible();
  const updated = await (await page.request.get('/api/engineering/safety-requirements', {headers})).json();
  expect(updated.items[0].version).toBe(2);
});

test('norm references appear in the NIS source directory without bus or release claims @safety-assurance', async ({page}) => {
  await page.goto('/sources?project=' + encodeURIComponent('nis-e2e-sources-' + randomUUID()));
  await page.getByLabel('Fuzzy-Suche').fill('26262');
  await expect(page.getByText('SAFETY / REGULATORY', {exact: true})).toBeVisible();
  await page.getByRole('group').filter({has: page.getByText('2 Quellen anzeigen', {exact: true})}).locator('summary').click();
  await expect(page.getByText('ISO 26262-1:2018 – Functional safety / Vocabulary', {exact: true})).toBeVisible();
  await expect(page.getByText('Normreferenz · keine Sicherheitsfreigabe', {exact: true})).toBeVisible();
});
