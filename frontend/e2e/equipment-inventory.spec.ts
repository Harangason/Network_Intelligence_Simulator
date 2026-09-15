import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';

test('equipment inventory distinguishes requested sensors from identified devices and recovers after clarification', async ({ page }) => {
  await page.goto(`/studio/engineering?assistant=project&project=nis-e2e-inventory-${randomUUID()}`);
  const dialog = page.locator('.engineering-agent-wizard-dialog');
  await expect(dialog.getByRole('heading', { name: 'Engineering-Auftrag erstellen' })).toBeVisible();
  await dialog.getByTitle('Projektname', { exact: true }).click();
  await dialog.locator('#engineering-project-name').fill('Sensorinventar prüfen');
  await dialog.getByTitle('Aufgabe', { exact: true }).click();
  await dialog.getByRole('textbox', { name: 'Aufgabentext', exact: true }).fill('Ein kleines Projekt mit einem Raspberry Pi, drei Sensoren und drei Ventilen.');
  await dialog.getByTitle('Geräteumfang', { exact: true }).click();
  await expect(dialog.locator('.agent-equipment-list')).toContainText('Sensoren · 0 erkannt / 3 vorgegeben');
  await expect(dialog.getByRole('alert').filter({ hasText: 'Geräteumfang noch unvollständig' })).toContainText('Sensoren: 0 erkannt, 3 vorgegeben');
  await expect(dialog.locator('.agent-questionnaire-nav')).toContainText('Anzahlen, erkannte Geräte, Busse und Controller-Zuordnung prüfen');
  await expect(dialog.locator('.agent-questionnaire-nav')).not.toContainText('Sollzahlen, Busse und Controller-Zuordnung bereit');
  await dialog.getByTitle('Aufgabe', { exact: true }).click();
  await dialog.getByRole('textbox', { name: 'Aufgabentext', exact: true }).fill('Ein kleines Projekt mit einem Raspberry Pi, drei Temperatursensoren und drei Ventilen.');
  await dialog.getByTitle('Geräteumfang', { exact: true }).click();
  await expect(dialog.locator('.agent-equipment-list')).toContainText('Sensoren · 3 erkannt / 3 vorgegeben');
  await expect(dialog.getByRole('alert').filter({ hasText: 'Geräteumfang noch unvollständig' })).toHaveCount(0);
  const cluster = dialog.locator('.agent-equipment-clusters');
  await expect(cluster.getByRole('listitem').filter({ hasText: /Temperatursensor/ })).toHaveCount(3);
  for (let index = 1; index <= 3; index++) await expect(cluster.getByRole('listitem').filter({ hasText: `Temperatursensor${index}` })).toBeVisible();
});
