import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';

test('free chat creates and applies the exact three-device project structure @engineering-assistant', async ({ page }) => {
  const compact = '20260925000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const project = `network-project-${compact}`;
  await page.goto(`/studio/agent?project=${compact}`);
  await page.getByRole('textbox', { name: 'Nachricht an den Engineering-Assistenten' }).fill(
    'Erstelle ein einfaches Projekt mit einem Controller, einem Druck Sensor und einem Ventil Aktor.');
  await page.locator('.eng-agent-composer').getByRole('button', { name: 'Senden', exact: true }).click();
  const proposal = page.getByRole('region', { name: 'Engineering-Vorschlag' });
  await expect(proposal).toContainText('7 Änderungen', { timeout: 120_000 });
  await expect(proposal).toContainText('Freigabe offen');
  await proposal.getByRole('button', { name: 'Vorschlag freigeben', exact: true }).click();
  await proposal.getByRole('button', { name: 'Ins Modell übernehmen', exact: true }).click();
  await expect(proposal).toContainText('7 Modellobjekte bestätigt');
  await expect.poll(async () => {
    const response = await page.request.get('/api/engineering/hardware-nodes',
      { headers: { 'X-Project-ID': project } });
    expect(response.ok()).toBe(true);
    const payload = await response.json();
    const nodes = Array.isArray(payload) ? payload : payload.items ?? payload.data ?? [];
    return nodes.map((node: { name: string }) => node.name).sort();
  }).toEqual(['Controller1', 'Drucksensor1', 'Ventilaktor1']);
  await page.reload();
  await expect(page.getByText('7 Modellobjekte bestätigt')).toBeVisible();
});
