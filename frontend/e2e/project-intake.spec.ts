import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';

for (const entry of ['workspace', 'sidebar']) {
test(`natural small project request from ${entry} reaches editable wizard through the real agent @project-intake`, async ({ page }) => {
  const compact = '20260914000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const project = 'network-project-' + compact;
  const requirement = 'ich möchte ein kleines Projekt: ich habe drei sensoren die temperatur messen und ein respary pi und aktoren die ventile steuern';
  await page.goto(`/studio/${entry === 'sidebar' ? 'engineering' : 'agent'}?project=${compact}`);
  if (entry === 'sidebar') await page.getByTitle('AI Assistant öffnen', { exact: true }).click();
  await page.getByRole('textbox', { name: 'Nachricht an den Engineering-Assistenten' }).fill(requirement);
  const savedHistory = page.waitForResponse(response => response.url().includes('/api/agent/history')
    && response.request().method() === 'PUT' && response.ok());
  await page.locator('.eng-agent-composer').getByRole('button', { name: 'Senden', exact: true }).click();
  const action = page.getByRole('button', { name: /Projektentwurf ausarbeiten/ });
  await expect(action).toBeVisible();
  await expect(page.getByText(/Wie viele Ventile sollen gesteuert werden/)).toBeVisible();
  // Persisted responses must retain the requirement, not only the streamed card.
  await savedHistory;
  await page.reload();
  if (entry === 'sidebar' && await page.getByTitle('AI Assistant öffnen', { exact: true }).isVisible())
    await page.getByTitle('AI Assistant öffnen', { exact: true }).click();
  await expect(action).toBeVisible();
  await action.click();
  await expect(page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' })).toBeVisible();
  const description = page.getByRole('textbox', { name: 'Projektbeschreibung', exact: false });
  await expect(description).toHaveValue(requirement);
  await page.getByRole('dialog').getByTitle('Statusübersicht', { exact: true }).click();
  await expect(page.getByRole('region', { name: 'Auftrag vor dem Start prüfen' })).toContainText(requirement);
  await expect(page.getByText('Die Anzahl der Ventile bzw. Aktoren ist noch offen.', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Auftrag starten', exact: true })).toBeDisabled();
  await page.getByRole('dialog').getByTitle('Projektname', { exact: true }).click();
  const field = page.getByPlaceholder('Beschreibe das konkrete Ziel, z. B. arbeite bis zur Simulation ...');
  await page.getByPlaceholder('z. B. NIS Restbussimulation').fill('Temperatur und Ventile');
  await page.getByRole('dialog').getByTitle('Aufgabe', { exact: true }).click();
  await expect(field).toHaveValue(requirement);
  await page.getByRole('dialog').getByTitle('Geräteumfang', { exact: true }).click();
  await expect(page.getByRole('spinbutton', { name: 'Sensoren: verbindliche Anzahl', exact: true })).toHaveValue('3');
  await expect(page.getByRole('spinbutton', { name: 'Aktoren: verbindliche Anzahl', exact: true })).toHaveValue('');
  await expect(page.getByText('Ventile oder Aktoren sind genannt, ihre Anzahl ist noch offen.', { exact: false })).toBeVisible();
  await page.getByRole('dialog').getByTitle('Aufgabe', { exact: true }).click();
  await field.fill(requirement + '\nZwei Ventile, zunächst manuell schalten.');
  await expect(field).toHaveValue(/Zwei Ventile/);
  await page.reload();
  await page.getByPlaceholder('z. B. NIS Restbussimulation').fill('Temperatur und Ventile');
  await page.getByRole('dialog').getByTitle('Aufgabe', { exact: true }).click();
  await expect(field).toHaveValue(requirement + '\nZwei Ventile, zunächst manuell schalten.');
  expect(new URL(page.url()).searchParams.get('project')).toBe(compact);
  const response = await page.request.get('/api/engineering/hardware-nodes', { headers: { 'X-Project-ID': project } });
  expect(response.ok()).toBe(true);
  const model = await response.json();
  expect(Array.isArray(model) ? model : model.items ?? model.data ?? []).toHaveLength(0);
});
}

