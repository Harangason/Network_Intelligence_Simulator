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
  await expect(dialog.getByText(/Sensorik \(Radar, Kamera, Lidar, Ultraschall, IMU, Raddrehzahl\)/)).toBeVisible();
  await expect(dialog.getByRole('spinbutton', { name: 'Controller: verbindliche Anzahl', exact: true })).toHaveValue('5');
  await expect(dialog.getByText(/Aktorik \(Bremsaktuator, Lenkaktuator, Antriebsaktuator\)/)).toBeVisible();
  await expect(dialog.getByRole('spinbutton', { name: 'Aktoren: verbindliche Anzahl', exact: true })).toHaveValue('0');
  await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeDisabled();
  await expect(dialog.getByRole('table', { name: 'Kommunikationssysteme prüfen' })).not.toContainText('embedded_systems · adc');
  await expect(dialog).not.toContainText('degradieren /');
});
