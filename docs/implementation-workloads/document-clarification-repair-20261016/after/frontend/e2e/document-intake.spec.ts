import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';

test('document intake preserves complete requirements and reports unresolved scope @parser', async ({ page }) => {
  await page.goto(`/studio/engineering?assistant=project&project=nis-e2e-document-${randomUUID()}`);
  const dialog = page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' });
  await expect(dialog).toBeVisible();
  await dialog.locator('#engineering-project-name').fill('Dokumentaufnahme Fahrzeug');
  await dialog.locator('fieldset.agent-project-name-step input[type=file]').setInputFiles(
    fileURLToPath(new URL('./fixtures/document-intake-vehicle.txt', import.meta.url)));
  await expect(dialog.getByText(/vollständig gelesen \(19\.088 Zeichen\)/)).toBeVisible();
  await dialog.getByRole('button', { name: '4', exact: true }).click();
  await expect(dialog.getByRole('heading', { name: 'Geräteumfang aus dem Dokument noch offen' })).toBeVisible();
  await expect(dialog.getByRole('spinbutton', { name: 'Anzahl Kamera', exact: true })).toHaveValue('');
  await expect(dialog.getByRole('spinbutton', { name: 'Anzahl IMU', exact: true })).toHaveValue('');
  await expect(dialog.getByRole('spinbutton', { name: 'Controller: verbindliche Anzahl', exact: true })).toHaveValue('5');
  await expect(dialog.getByRole('spinbutton', { name: 'Anzahl Bremsaktuator', exact: true })).toHaveValue('');
  await expect(dialog.getByRole('spinbutton', { name: 'Aktoren: verbindliche Anzahl', exact: true })).toHaveValue('0');
  await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeDisabled();
  await expect(dialog.getByRole('table', { name: 'Kommunikationssysteme prüfen' })).not.toContainText('embedded_systems · adc');
  await expect(dialog).not.toContainText('degradieren /');
});

test('document scope answers enter inventory without hiding unanswered sensor types @parser', async ({ page }) => {
  await page.goto(`/studio/engineering?assistant=project&project=nis-e2e-clarification-${randomUUID()}`);
  const dialog = page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' });
  await dialog.locator('#engineering-project-name').fill('Dokument-Rückfragen');
  await dialog.locator('fieldset.agent-project-name-step input[type=file]').setInputFiles(
    fileURLToPath(new URL('./fixtures/document-intake-vehicle.txt', import.meta.url)));
  await dialog.getByRole('button', { name: '4', exact: true }).click();
  await dialog.getByRole('spinbutton', { name: 'Anzahl Kamera', exact: true }).fill('2');
  await dialog.getByRole('checkbox', { name: /Angaben sind ein Mindestumfang/ }).check();
  await dialog.getByRole('button', { name: 'Geprüfte Dokumentangaben übernehmen', exact: true }).click();
  await expect(dialog.getByRole('spinbutton', { name: 'Sensoren: verbindliche Anzahl', exact: true })).toHaveValue('2');
  await expect(dialog.getByRole('alert', { name: 'Offene Gerätegruppen' })).toContainText('IMU');
  await expect(dialog.getByRole('alert', { name: 'Offene Gerätegruppen' })).toContainText('Radar');
  await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeDisabled();
  await expect(dialog.getByRole('spinbutton', { name: 'Anzahl Kamera', exact: true })).toHaveValue('2');
});
