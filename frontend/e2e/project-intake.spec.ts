import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';

for (const entry of ['workspace', 'sidebar']) {
test(`natural small project request from ${entry} creates a persistent editable project draft @project-intake`, async ({ page }) => {
  const compact = '20260914000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const project = 'network-project-' + compact;
  const requirement = 'ich möchte ein kleines Projekt: ich habe drei sensoren die temperatur messen und ein respary pi und aktoren die ventile steuern';
  await page.goto(`/studio/${entry === 'sidebar' ? 'engineering' : 'agent'}?project=${compact}`);
  if (entry === 'sidebar') await page.getByTitle('AI Assistant öffnen', { exact: true }).click();
  await page.getByRole('textbox', { name: 'Nachricht an den Engineering-Assistenten' }).fill(requirement);
  await page.locator('.eng-agent-composer').getByRole('button', { name: 'Senden', exact: true }).click();
  const editor = page.getByRole('region', { name: 'Gespeicherter Projektentwurf' }).last();
  await expect(editor).toContainText('4 Geräte');
  await editor.getByText(/Offene Angaben \(/).click();
  await expect(editor.getByText(/Wie viele Ventile/)).toBeVisible();
  // Persisted responses must retain the requirement, not only the streamed card.
  await page.reload();
  if (entry === 'sidebar' && await page.getByTitle('AI Assistant öffnen', { exact: true }).isVisible())
    await page.getByTitle('AI Assistant öffnen', { exact: true }).click();
  await expect(editor).toContainText('4 Geräte');
  await expect(page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' })).toHaveCount(0);
  await editor.getByRole('textbox', { name: 'Anforderung ergänzen', exact: true }).fill('Zwei Ventile, zunächst manuell schalten.');
  await editor.getByRole('button', { name: 'Ergänzung speichern', exact: true }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 2 gespeichert');
  await expect(editor).toContainText('6 Geräte');
  await page.reload();
  if (entry === 'sidebar' && await page.getByTitle('AI Assistant öffnen', { exact: true }).isVisible())
    await page.getByTitle('AI Assistant öffnen', { exact: true }).click();
  await expect(editor).toContainText('Revision 2');
  await expect(editor).toContainText('6 Geräte');
  expect(new URL(page.url()).searchParams.get('project')).toBe(compact);
  const response = await page.request.get('/api/engineering/hardware-nodes', { headers: { 'X-Project-ID': project } });
  expect(response.ok()).toBe(true);
  const model = await response.json();
  expect(Array.isArray(model) ? model : model.items ?? model.data ?? []).toHaveLength(0);
});
}

