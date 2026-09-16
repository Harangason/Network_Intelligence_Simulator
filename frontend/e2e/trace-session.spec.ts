import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';

test('imported trace persists all pages and the exact selected event after reload', async ({ page }) => {
  const project = 'nis-e2e-import-' + randomUUID();
  await page.goto(`/trace-analysis?project=${project}`);
  const buffer = Buffer.from(Array.from({length: 2501}, (_, i) => JSON.stringify({time_s: i / 1000, message_id: `sample-${i}`})).join('\n'));
  await page.locator('input[type=file]').setInputFiles({name: 'samples.jsonl', mimeType: 'application/octet-stream', buffer});
  await expect(page).toHaveURL(/import=/);
  await page.getByRole('button', {name: 'Nächstes Fenster', exact: true}).click();
  const event = page.getByRole('button', {name: '2.002000 s', exact: true});
  await expect(event).toBeVisible();
  await event.click();
  await expect(event).toHaveAttribute('aria-pressed', 'true');
  await expect(page).toHaveURL(/event=/);
  await page.reload();
  await expect(page.getByRole('button', {name: '2.002000 s', exact: true})).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByLabel('Gemeinsamer Trace-Kontext')).toContainText('sample-2002');
});
