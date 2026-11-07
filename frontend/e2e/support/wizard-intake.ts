import { expect, type Locator } from 'playwright/test';

/** Review navigation remains available while the actual START gate stays strict. */
export async function expectIntakeStartReady(dialog: Locator, ready: boolean) {
  const next = dialog.locator('.eng-agent-questionnaire-head').getByRole('button');
  await expect(next).toHaveText('Weiter');
  await expect(next).toBeEnabled();
  await next.click();
  const start = dialog.getByRole('button', { name: 'Auftrag starten', exact: true });
  if (ready) await expect(start).toBeEnabled();
  else await expect(start).toBeDisabled();
  await dialog.getByTitle('Geräteumfang', { exact: true }).click();
}

export async function startReviewedIntake(dialog: Locator) {
  await dialog.locator('.eng-agent-questionnaire-head').getByRole('button', { name: 'Weiter', exact: true }).click();
  await dialog.getByRole('button', { name: 'Auftrag starten', exact: true }).click();
}
