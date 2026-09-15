import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';

test('trace landing opens project tiles and creates a persisted trace project without the engineering wizard', async ({ page }) => {
  const project = 'nis-e2e-trace-gallery-' + randomUUID();
  const name = 'Trace-Prüfung ' + randomUUID().slice(0, 6);
  const response = await page.request.patch('/api/engineering/workflow/context?view=summary', {
    headers: { 'X-Project-ID': project }, data: { engineering_wizard_settings: { project_name: name, model_type: 'custom' } },
  });
  expect(response.ok()).toBe(true);
  await page.goto(`/?project=${project}`);
  await expect(page.getByRole('navigation', { name: 'Hauptnavigation' }).getByRole('link', { name: 'Open studio', exact: true })).toHaveCount(0);
  await page.getByRole('link', { name: 'Start Trace Analyse', exact: true }).click();
  await expect(page).toHaveURL(/\/trace-projects\?/);
  await expect(page.getByRole('heading', { name: 'Deine Trace-Projekte.' })).toBeVisible();
  await page.getByRole('searchbox').fill(name);
  const card = page.getByRole('link').filter({ has: page.getByRole('heading', { name, exact: true }) });
  await card.click();
  await expect(page).toHaveURL(new RegExp('/trace-analysis\\?project=' + project));
  await expect(page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' })).toHaveCount(0);
  await page.goto(`/trace-projects?project=${project}`);
  await page.getByRole('button', { name: /Neues Trace-Projekt/ }).click();
  await expect(page).toHaveURL(/\/trace-analysis\?/);
  await expect(page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' })).toHaveCount(0);
  const compact = new URL(page.url()).searchParams.get('project')!;
  const created = compact.startsWith('network-project-') ? compact : 'network-project-' + compact;
  expect(created).not.toBe(project);
  const saved = await (await page.request.get('/api/engineering/workflow?view=summary', { headers: { 'X-Project-ID': created } })).json();
  expect(saved.context.engineering_wizard_settings.project_name).toBe('Neues Trace-Projekt');
  await page.goto(`/trace-projects?project=${compact}`);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Neues Trace-Projekt', exact: true }).first()).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
