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

test('trace chart distributions and time buckets link to exact original findings', async ({ page }) => {
  const project = 'nis-e2e-trace-charts-' + randomUUID();
  await page.goto(`/trace-analysis?project=${project}`);
  const buffer = Buffer.from(Array.from({ length: 20 }, (_, i) => JSON.stringify({
    time_s: i, time_basis: i === 19 ? 'clock-b' : 'clock-a', message_name: 'Statusbericht',
    source_name: 'Sensor', destination_names: ['Controller'],
    status: [5, 15, 19].includes(i) ? 'dropped' : 'transmitted',
    faults: i === 19 ? ['MESSAGE_LOSS'] : [5, 15].includes(i) ? ['BUS_OFF'] : [],
  })).join('\n'));
  await page.locator('input[type=file]').setInputFiles({ name: 'charts.jsonl', mimeType: 'application/octet-stream', buffer });
  await expect(page).toHaveURL(/import=/);
  const url = new URL(page.url());
  const importId = url.searchParams.get('import');
  url.searchParams.set('view', 'charts');
  await page.goto(url.toString());
  const charts = page.getByLabel('Trace-Diagramme mit Daten- und Ursachenbezug', { exact: true });
  await expect(charts).toContainText('20 Ereignisse · 3 mit Fehlern / Befunden');
  await expect(charts).toContainText('ECU-Auswertung benötigt dokumentierte Hardware-IDs');
  await charts.getByRole('button', { name: 'BUS_OFF: 2 Ereignisse; Daten öffnen', exact: true }).click();
  const evidence = charts.getByLabel('Daten und Ursachen zur Diagrammauswahl', { exact: true });
  await expect(evidence.locator('tbody tr')).toHaveCount(2);
  await expect(evidence).toContainText(`${importId}:5`);
  await expect(evidence).toContainText(`${importId}:15`);
  await charts.getByRole('button', { name: /BUS_OFF; .*; 1 Ereignisse; Daten öffnen/ }).first().click();
  await expect(evidence.locator('tbody tr')).toHaveCount(1);
  await expect(evidence).toContainText(`${importId}:5`);
  await charts.getByRole('button', { name: 'dropped: 3 Ereignisse; Daten öffnen', exact: true }).click();
  await expect(evidence.locator('tbody tr')).toHaveCount(3);
  await expect(evidence.getByRole('button', { name: 'Ursachen-Kontext', exact: true }).first()).toBeDisabled();
  await charts.getByRole('combobox', { name: 'Zeitbasis', exact: true }).selectOption('clock-b');
  await expect(charts).toContainText('1 Ereignisse in Zeitbasis clock-b');
  await expect(charts).toContainText('Nur ein belegter Zeitpunkt');
  await charts.getByRole('button', { name: 'BUS_OFF: 2 Ereignisse; Daten öffnen', exact: true }).click();
  await evidence.getByRole('button', { name: 'Befunde', exact: true }).first().click();
  await expect(page).toHaveURL(/view=findings/);
  await expect(page.locator('.trace-chart-selected').first()).toContainText(`${importId}:5`);
  await expect(page.getByLabel('Gemeinsamer Trace-Kontext', { exact: true })).toContainText('Sensor');
});

test('trace analysis keeps late channels, original samples and technical properties accessible', async ({ page }) => {
  const project = 'nis-e2e-signal-analysis-' + randomUUID();
  const messageId = '8a3254f8-8244-45e6-8c0e-634348d56cd4';
  await page.goto(`/trace-analysis?project=${project}`);
  const buffer = Buffer.from(Array.from({ length: 1205 }, (_, i) => JSON.stringify({
    event_id: `analysis-${i}`, time_s: i / 1000, time_basis: 'trace-relative', message_ids: [messageId],
    message_name: 'Temperaturbericht', source_name: 'Sensor', destination_names: ['Controller'],
    signals: [{ signal_id: `channel-${i % 150}`, signal: `Kanal ${String(i % 150).padStart(3, '0')}`, value: i, unit: 'V', quality: 'VALID' }],
  })).join('\n'));
  await page.locator('input[type=file]').setInputFiles({ name: 'analysis.jsonl', mimeType: 'application/octet-stream', buffer });
  await expect(page).toHaveURL(/import=/);
  const url = new URL(page.url()); url.searchParams.set('view', 'signals');
  await page.goto(url.toString());
  const analysis = page.getByLabel('Signal-Analyse', { exact: true });
  await expect(analysis).toContainText('150 Kanäle');
  await analysis.locator('.trace-signal-picker > summary').click();
  await analysis.getByLabel('Trace-Signale suchen', { exact: true }).fill('Kanal 149');
  await analysis.getByRole('checkbox', { name: 'Kanal 149 V', exact: true }).check();
  await expect(analysis.getByLabel('Signalverlauf: Kanal 149', { exact: true })).toBeVisible();
  await analysis.getByRole('button', { name: 'Alle Signale auswählen', exact: true }).click();
  await expect(analysis).toContainText('150 ausgewählt');
  const values = analysis.getByRole('navigation', { name: 'Trace-Signalwerte durchblättern', exact: true });
  await values.getByLabel('Trace-Signalwerte: Seite auswählen').selectOption('12');
  await expect(analysis.getByRole('button', { name: '1.204000 s', exact: true })).toBeVisible();
  await analysis.getByRole('button', { name: '1.204000 s', exact: true }).click();
  const context = page.getByLabel('Gemeinsamer Trace-Kontext', { exact: true });
  await expect(context).toContainText('Temperaturbericht');
  await expect(context.locator('tbody').first().locator('td')).toHaveText(['Sensor', 'Controller']);
  await context.getByRole('button', { name: 'Eigenschaften: Temperaturbericht', exact: true }).click();
  const properties = page.getByRole('dialog', { name: 'Trace-Eigenschaften: Temperaturbericht', exact: true });
  await expect(properties).toContainText(messageId);
  // Imported identity is session_id:source_record_index (trace_sessions.py).
  await expect(properties).toContainText(`${url.searchParams.get('import')}:1204`);
  await expect(properties).toContainText('"source_record_index": 1204');
  await properties.getByRole('button', { name: 'Schließen', exact: true }).click();
  await analysis.getByRole('button', { name: 'Auswahl leeren', exact: true }).click();
  await expect(analysis).toContainText('0 ausgewählt');
  await expect(analysis.locator('.trace-signal-plot')).toHaveCount(0);
});
