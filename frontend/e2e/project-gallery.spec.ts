import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';

test('landing opens persisted project tiles and the plus tile creates a new wizard project', async ({ page }) => {
  const project = 'nis-e2e-gallery-' + randomUUID();
  const name = 'Temperaturregelung ' + randomUUID().slice(0, 6);
  const response = await page.request.patch('/api/engineering/workflow/context?view=summary', {
    headers: { 'X-Project-ID': project }, data: { engineering_wizard_settings: { project_name: name, model_type: 'custom' } },
  });
  expect(response.ok()).toBe(true);
  await page.goto(`/?project=${project}`);
  const nav = page.getByRole('navigation', { name: 'Hauptnavigation' });
  for (const label of ['Neu', 'Clear', 'Speichern', 'Öffnen']) await expect(nav.getByRole('button', { name: label, exact: true })).toHaveCount(0);
  await page.getByRole('link', { name: 'Start simulating', exact: true }).click();
  await expect(page).toHaveURL(/\/projects\?/);
  const card = page.getByRole('link').filter({ has: page.getByRole('heading', { name, exact: true }) });
  await expect(card).toContainText('Modell, Kommunikation und Simulation');
  expect((await card.locator('svg').boundingBox())!.width).toBeLessThanOrEqual(20);
  expect((await card.boundingBox())!.height).toBeLessThan(400);
  await card.click();
  await expect(page).toHaveURL(new RegExp('project=' + project));
  await page.goto(`/projects?project=${project}`);
  await page.getByRole('button', { name: /Neues Projekt/ }).click();
  await expect(page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' })).toBeVisible();
  const created = new URL(page.url()).searchParams.get('project')!;
  expect(created).not.toBe(project);
  const createdId = created.startsWith('network-project-') ? created : 'network-project-' + created;
  const saved = await (await page.request.get('/api/engineering/workflow?view=summary', { headers: { 'X-Project-ID': createdId } })).json();
  expect(saved.context.engineering_wizard_settings.project_name).toBe('Neues Projekt');
  expect(saved.context.engineering_wizard_settings.model_type).toBe('custom');
  await page.goto(`/projects?project=${created}`);
  await page.reload();
  await expect(page.getByRole('link').filter({ has: page.getByRole('heading', { name: 'Neues Projekt', exact: true }) }).first()).toBeVisible();
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test('landing animations move, pause and respect reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/');
  const orbit = page.locator('.orbit-carrier-one');
  const bar = page.locator('.metrics .metric-line i').first();
  const initial = await orbit.evaluate(element => getComputedStyle(element).transform);
  await expect.poll(() => orbit.evaluate(element => getComputedStyle(element).transform)).not.toBe(initial);
  expect(await bar.evaluate(element => getComputedStyle(element).animationName)).toBe('landing-bar-flow');
  await page.getByLabel('Animationen pausieren').check();
  expect(await orbit.evaluate(element => getComputedStyle(element).animationPlayState)).toBe('paused');
  expect(await bar.evaluate(element => getComputedStyle(element).animationPlayState)).toBe('paused');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  expect(await orbit.evaluate(element => getComputedStyle(element).animationName)).toBe('none');
  expect(await bar.evaluate(element => getComputedStyle(element).animationName)).toBe('none');
});
