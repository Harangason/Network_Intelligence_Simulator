import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';

test('studio commands are removed and agent logging persists through settings', async ({ page }) => {
  const project = 'nis-e2e-settings-' + randomUUID();
  const created = await page.request.patch('/api/engineering/workflow/context', {
    headers: { 'X-Project-ID': project }, data: {},
  });
  expect(created.ok()).toBe(true);
  const status = await page.request.get('/api/agent/diagnostics?agentLog=status');
  expect(status.ok()).toBe(true);
  const initial = (await status.json()).enabled as boolean;
  try {
    await page.goto(`/studio/engineering?project=${project}`);
    const header = page.locator('header.topbar');
    await expect(header.getByRole('button', { name: 'Neu', exact: true })).toHaveCount(0);
    await expect(header.getByRole('button', { name: 'Projekt aktualisieren', exact: true })).toHaveCount(0);
    await expect(header.getByRole('button', { name: /Loggen/ })).toHaveCount(0);
    await header.getByRole('link', { name: 'Einstellungen', exact: true }).click();
    const returnLink = page.getByRole('link', { name: 'Zum Projekt' });
    await expect(returnLink).toHaveAttribute('href', `/studio?mode=network&project=${project}`);
    const systemInfo = page.getByRole('complementary', { name: 'Daten & Laufzeit' });
    await expect(systemInfo).toBeVisible();
    await expect.poll(() => systemInfo.evaluate((element) => {
      const main = element.previousElementSibling;
      if (!main) return false;
      return element.getBoundingClientRect().top >= main.getBoundingClientRect().bottom;
    })).toBe(true);
    const toggle = page.getByRole('switch', { name: /Agent-Ereignisse protokollieren/ });
    await expect(toggle).toBeEnabled();
    await expect(toggle).toBeChecked({ checked: initial });
    await toggle.click();
    await expect(toggle).toBeEnabled();
    await expect(toggle).toBeChecked({ checked: !initial });
    await page.reload();
    await expect(toggle).toBeEnabled();
    await expect(toggle).toBeChecked({ checked: !initial });
    const persisted = await page.request.get('/api/agent/diagnostics?agentLog=status');
    expect((await persisted.json()).enabled).toBe(!initial);
    await returnLink.click();
    await expect(page).toHaveURL(new RegExp(`/studio\\?mode=network&project=${project}$`));
  } finally {
    await page.request.post('/api/agent/diagnostics', {
      data: { action: 'agent-log', enabled: initial, projectId: project, runId: 'settings-test-cleanup' },
    });
  }
});
