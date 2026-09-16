import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';

test('generic sensors expose separate measurement and connection choices without losing slot identity', async ({ page }) => {
  await page.goto(`/studio/engineering?assistant=project&project=nis-e2e-measurement-${randomUUID()}`);
  const dialog = page.locator('.engineering-agent-wizard-dialog');
  await dialog.getByTitle('Projektname', { exact: true }).click();
  await dialog.locator('#engineering-project-name').fill('Sensorfunktionen');
  await dialog.getByTitle('Aufgabe', { exact: true }).click();
  await dialog.getByRole('textbox', { name: 'Aufgabentext', exact: true }).fill('3 Sensoren und ein RaspberryPi');
  await dialog.getByTitle('Netzarchitektur', { exact: true }).click();
  await dialog.getByRole('radio', { name: /Variante 0/ }).check();
  await dialog.getByTitle('Geräteumfang', { exact: true }).click();
  await expect(dialog.getByLabel('Sensor1: Anschluss', { exact: true })).toBeDisabled();
  await dialog.getByLabel('Sensor 2: Messgröße', { exact: true }).selectOption('torque');
  await dialog.getByLabel('Sensor2: Anschluss', { exact: true }).selectOption('I2C');
  await dialog.getByLabel('Sensor 1: Messgröße', { exact: true }).selectOption('temperature');
  await dialog.getByLabel('Sensor 3: Messgröße', { exact: true }).selectOption('speed');
  await expect(dialog.getByLabel('Sensor 2: Messgröße', { exact: true })).toHaveValue('torque');
  await expect(dialog.getByLabel('Sensor2: Anschluss', { exact: true })).toHaveValue('I2C');
  await dialog.getByLabel('Sensor 2: Messgröße', { exact: true }).selectOption('pressure');
  await expect(dialog.getByLabel('Sensor2: Anschluss', { exact: true })).toHaveValue('I2C');
  for (const name of ['Sensor1', 'Sensor3', 'RaspberryPi']) await dialog.getByLabel(`${name}: Anschluss`, { exact: true }).selectOption('I2C');
  await expect(dialog.locator('.agent-equipment-list')).toContainText('Sensoren · 3 erkannt / 3 vorgegeben');
  await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeEnabled();
});

test('temperature purpose inventory permits review without a spurious controller repair', async ({ page }) => {
  await page.goto(`/studio/engineering?assistant=project&project=nis-e2e-temperature-${randomUUID()}`);
  const dialog = page.locator('.engineering-agent-wizard-dialog');
  await dialog.getByTitle('Projektname', { exact: true }).click();
  await dialog.locator('#engineering-project-name').fill('Temperaturregelung');
  await dialog.getByTitle('Aufgabe', { exact: true }).click();
  await dialog.getByRole('textbox', { name: 'Aufgabentext', exact: true }).fill('2 Aktoren für Ventile, 4 Sensoren für Temperaturen, und ein RaspberryPi');
  await dialog.getByTitle('Geräteumfang', { exact: true }).click();
  await expect(dialog.locator('.agent-equipment-list')).toContainText('Sensoren · 4 erkannt / 4 vorgegeben');
  await expect(dialog.getByRole('alert').filter({ hasText: 'Geräteumfang noch unvollständig' })).toHaveCount(0);
  await expect(dialog.getByRole('region', { name: 'Controller ergänzen', exact: true })).toHaveCount(0);
  await expect(dialog.locator('.agent-equipment-clusters').getByRole('listitem').filter({ hasText: /Temperatursensor/ })).toHaveCount(4);
  await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeDisabled();
  for (const name of ['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3', 'Temperatursensor4', 'Ventilaktor1', 'Ventilaktor2']) {
    await dialog.getByLabel(`${name}: Anschluss`, { exact: true }).selectOption('I2C');
  }
  await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeEnabled();
});

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
  await expect(dialog.locator('.agent-questionnaire-nav')).toContainText('Anzahlen, erkannte Geräte, Anschlüsse, Busse und Controller-Zuordnung prüfen');
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
