import { test, expect } from 'playwright/test';
import { readFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';

const cases = JSON.parse(readFileSync(new URL('../../tests/fixtures/industry40.json', import.meta.url), 'utf8')).cases as {
  id: string; input: string; counts: Record<string, number | null>;
}[];
const labels: Record<string, string> = { sensors: 'Sensoren', actuators: 'Aktoren', ecus: 'Controller', gateways: 'Gateways' };

// Inventory/review-gate regressions, not nine-stage completion tests.
for (const scenario of cases) {
  test(`${scenario.id} retains requested scope in the real wizard @industry-inventory`, async ({ page }) => {
    await page.goto(`/studio/engineering?assistant=project&project=nis-e2e-${scenario.id}-${randomUUID()}`);
    const dialog = page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' });
    await dialog.getByTitle('Projektname', { exact: true }).click();
    await dialog.locator('#engineering-project-name').fill(`Inventar ${scenario.id}`);
    await dialog.getByTitle('Aufgabe', { exact: true }).click();
    await dialog.getByRole('textbox', { name: 'Aufgabentext', exact: true }).fill(scenario.input);
    await dialog.getByTitle('Geräteumfang', { exact: true }).click();
    for (const [key, count] of Object.entries(scenario.counts)) {
      if (count !== null) await expect(dialog.getByLabel(`${labels[key]}: verbindliche Anzahl`, { exact: true })).toHaveValue(String(count));
    }
    if (await dialog.getByRole('alert').filter({ hasText: 'Geräteumfang noch unvollständig' }).count()) {
      await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeDisabled();
    }
  });
}
