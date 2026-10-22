"""Contract-only browser regression; native original-file acceptance is separate."""
from pathlib import Path

OUT = Path(__file__).parent
REL = 'frontend/e2e/document-intake.spec.ts'
text = (OUT / 'before' / REL).read_text(encoding='utf-8')
text = text.replace("import { randomUUID }", "import { createHash, randomUUID }", 1)
text += '''

test('typed document handoff retains source facts and asks for a function host @document-contract', async ({ page }) => {
  // Deterministic response contract test, not evidence of native Qwen extraction.
  const source = '# Test robot\\n## Architecture\\nHauptrechner\\nEncoder\\n## Functions\\nMotion Control\\n## Requirements\\nREQ-TEST-001: The system shall detect a sensor fault.';
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
'''
(OUT / 'staged' / REL).write_text(text, encoding='utf-8')
print('Staged browser contract regression; native acceptance remains separate.')
