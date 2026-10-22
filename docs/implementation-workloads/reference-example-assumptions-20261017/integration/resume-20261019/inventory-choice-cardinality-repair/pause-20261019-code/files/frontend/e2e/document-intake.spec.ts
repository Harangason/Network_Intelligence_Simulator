import { test, expect } from 'playwright/test';
import { createHash, randomUUID } from 'node:crypto';
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


test('typed document handoff retains source facts and asks for a function host @document-contract', async ({ page }) => {
  // Deterministic response contract test, not evidence of native Qwen extraction.
  const source = '# Test robot\n## Architecture\nHauptrechner\nEncoder\n## Functions\nMotion Control\n## Requirements\nREQ-TEST-001: The system shall detect a sensor fault.';
  await page.route('**/api/engineering/agent/document-intake', async route => {
    const request = route.request().postDataJSON();
    const components = [
      { name: 'Hauptrechner', kind: 'INSTANCE', role: 'CONTROLLER', quantity: 1, source_quote: 'Hauptrechner', source_context: ['Test robot', 'Architecture'] },
      { name: 'Encoder', kind: 'CATEGORY', role: 'SENSOR', quantity: null, source_quote: 'Encoder', source_context: ['Test robot', 'Architecture'] },
      { name: 'Motion Control', kind: 'FUNCTION', role: 'OTHER', quantity: null, source_quote: 'Motion Control', source_context: ['Test robot', 'Functions'] },
      { name: 'REQ-TEST-001', kind: 'REQUIREMENT', role: 'OTHER', quantity: null, source_quote: 'REQ-TEST-001: The system shall detect a sensor fault.', source_context: ['Test robot', 'Requirements'] },
    ];
    await route.fulfill({ json: { success: true, data: { status: 'REVIEW_REQUIRED', source_name: request.source_name,
      source_sha256: createHash('sha256').update(request.source).digest('hex'), source_request_id: request.source_request_id,
      source_chars: Array.from(request.source).length, source_complete: true, canonical_writes: false,
      model: 'contract-fixture', provider: 'local_ollama', interpretation: { summary: 'Controlled handoff contract',
        components, technologies: [], proposed_task: 'This summary must not replace the original.', assumptions: [], open_questions: [] } } } });
  });
  await page.goto(`/studio/engineering?assistant=project&project=nis-e2e-typed-document-${randomUUID()}`);
  const dialog = page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' });
  await dialog.locator('#engineering-project-name').fill('Typed document contract');
  const description = dialog.getByPlaceholder('Was soll dieses Projekt leisten?');
  await description.fill(source);
  await dialog.getByRole('button', { name: 'Lokalen Qwen-Vorschlag erstellen', exact: true }).click();
  await expect(dialog.getByText('Controlled handoff contract')).toBeVisible();
  await dialog.getByRole('button', { name: 'Geprüfte Dokumentangaben übernehmen', exact: true }).click();
  await expect(description).toHaveValue(source);
  await dialog.getByRole('button', { name: '4', exact: true }).click();
  const evidence = dialog.getByRole('region', { name: 'Übernommene Dokumentbefunde' });
  await expect(evidence).toContainText('4 Befunde übernommen');
  await expect(evidence).toContainText('1 Funktionsbefunde');
  await expect(evidence).toContainText('1 Anforderungs-IDs');
  await evidence.getByText('Übernommene Aussagen und Quellen', { exact: true }).click();
  await expect(evidence.locator('[data-document-kind="REQUIREMENT"] blockquote')).toHaveText('REQ-TEST-001: The system shall detect a sensor fault.');
  await expect(dialog.getByRole('spinbutton', { name: 'Controller: verbindliche Anzahl', exact: true })).toHaveValue('1');
  await expect(dialog.getByRole('spinbutton', { name: 'Sensoren: verbindliche Anzahl', exact: true })).toHaveValue('0');
  const host = dialog.getByRole('combobox', { name: 'Controller für Funktion Motion Control', exact: true });
  await expect(host).toHaveValue('');
  await host.selectOption('Hauptrechner');
  await dialog.getByRole('button', { name: 'Funktionszuordnungen übernehmen', exact: true }).click();
  await expect(host).toHaveValue('Hauptrechner');
  await expect(dialog.getByRole('spinbutton', { name: 'Anzahl Encoder', exact: true })).toHaveValue('');
  await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeDisabled();
});
