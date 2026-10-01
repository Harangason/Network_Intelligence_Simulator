import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';

const project = 'network-project-20260910042736034-d11591d0';
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const context = await browser.newContext({ viewport: { width: 1819, height: 1272 } });
const page = await context.newPage();
page.setDefaultTimeout(20000);
const calls = [], errors = [], checks = [];
let history = [], releaseResponse, delay = false;
page.on('pageerror', error => errors.push(error.message));
await page.route('**/api/agent/history?*', async route => {
  if (route.request().method() === 'PUT') history = route.request().postDataJSON().messages ?? [];
  await route.fulfill({ json: { messages: history } });
});
await page.route('**/api/agent/chat', async route => {
  calls.push(route.request().postDataJSON());
  if (delay) await new Promise(resolve => { releaseResponse = resolve; });
  const event = { type: 'data-engineering', id: `reply-${calls.length}`, data: { type: 'TEXT', text: 'Geprüfte Testantwort. LIN 50 ms.', id: `event-${calls.length}`, created_at: new Date().toISOString() } };
  await route.fulfill({ contentType: 'text/event-stream', headers: { 'x-vercel-ai-ui-message-stream': 'v1' }, body: `data: ${JSON.stringify(event)}\n\ndata: [DONE]\n\n` });
});
// Keep all test messages and workflow context writes inside this isolated browser.
await page.route('**/api/engineering/workflow/context?*', async route => {
  if (route.request().method() === 'PATCH') {
    const response = await page.request.get(`http://127.0.0.1:13500/api/engineering/workflow?view=summary`, { headers: { 'X-Project-ID': project } });
    await route.fulfill({ json: await response.json() });
  } else await route.continue();
});
await page.route('**/api/engineering/routing?*', async route => {
  const response = await route.fetch(); const body = await response.json();
  body.items = body.items.map(item => ({ ...item, approval_state: 'APPROVED', status: 'APPROVED', validation: { ...item.validation, valid: true } }));
  await route.fulfill({ json: body });
});
await page.route('**/api/engineering/workflow?view=summary', async route => {
  const response = await route.fetch(); const body = await response.json();
  delete body.context.agent_wizard_status;
  body.statuses.simulation = 'NOT_STARTED'; body.statuses.data_science_intelligence = 'NOT_STARTED';
  await route.fulfill({ json: body });
});
const panel = page.locator('.agent-widget-panel');
const input = panel.getByRole('textbox', { name: 'Nachricht an den Engineering-Assistenten' });
const send = panel.getByRole('button', { name: 'Senden', exact: true });
async function composerVisible() {
  assert.ok(await input.isVisible()); assert.ok(await input.isEnabled());
  const outer = await panel.boundingBox(), form = await panel.locator('.eng-agent-composer').boundingBox();
  assert.ok(form.y >= outer.y && form.y + form.height <= outer.y + outer.height + 1, 'Entire composer must stay inside panel');
}
try {
  await page.goto(`http://127.0.0.1:13500/studio?mode=network&project=${project}`);
  await page.getByRole('button', { name: 'AI Assistant öffnen', exact: true }).click();
  await panel.getByRole('button', { name: 'Signal prüfen', exact: true }).waitFor();
  await composerVisible();
  // Opening + a real 30-second poll + focus must never dispatch work.
  await page.waitForTimeout(process.env.AGENT_SMOKE_SKIP_IDLE ? 1000 : 31000);
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  assert.equal(calls.length, 0);
  assert.equal(await page.evaluate(() => sessionStorage.getItem('networkis:pending-agent-task')), null);
  checks.push(process.env.AGENT_SMOKE_SKIP_IDLE ? 'Opening and focus start no analysis (long idle check skipped)' : 'Opening, 30-second status poll and focus start no analysis');
  for (const label of ['Architektur erstellen', 'Signal prüfen', 'Trace analysieren', 'Finding bewerten']) {
    await panel.getByRole('button', { name: label, exact: true }).click();
    assert.equal(await input.inputValue(), label); assert.equal(calls.length, 0);
  }
  checks.push('All four quick questions remain selectable and only prepare a draft');
  await input.fill('Welche Zykluszeit steht in den Dokumenten?');
  await panel.locator('input[type=file]').setInputFiles([
    { name: 'Vorgabe.dbc', mimeType: 'text/plain', buffer: Buffer.from('SG_ Federweg 12 Bit; LIN 50 ms') },
    { name: 'Vorgabe.pdf', mimeType: 'application/pdf', buffer: await fs.readFile('../backend/runtime/agent-document-smoke.pdf') },
    { name: 'Vorgabe.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', buffer: await fs.readFile('../backend/runtime/agent-document-smoke.docx') },
  ]);
  await page.waitForFunction(() => document.querySelectorAll('.agent-widget-panel .eng-agent-attachment').length === 3);
  assert.equal(await panel.locator('.eng-agent-attachment').count(), 3);
  assert.match(await panel.locator('.eng-agent-attachments').textContent(), /LIN Zyklus: 50 ms/);
  assert.match(await panel.locator('.eng-agent-attachments').textContent(), /Fahrersitz links/);
  assert.equal(calls.length, 0, 'Reading files must not start analysis');
  delay = true; await send.click();
  await page.waitForFunction(() => document.querySelector('.eng-agent-composer button[type=submit]')?.textContent.includes('läuft'));
  await input.fill('Meine nächste Frage bleibt editierbar.'); await composerVisible();
  assert.equal(calls.length, 1);
  const sources = calls[0].messages.at(-1).parts.filter(p => p.type === 'data-attachment');
  assert.equal(sources.length, 3); assert.ok(sources.every(p => p.data.text.length > 10));
  delay = false; releaseResponse(); await send.waitFor();
  assert.equal(await input.inputValue(), 'Meine nächste Frage bleibt editierbar.');
  checks.push('Actual PDF, DOCX and DBC extraction; submit includes text; composer editable during response');
  await panel.getByRole('button', { name: 'Engineering-Assistent schließen' }).click();
  await page.getByRole('button', { name: 'AI Assistant öffnen', exact: true }).click();
  assert.equal(await input.inputValue(), 'Meine nächste Frage bleibt editierbar.'); assert.equal(calls.length, 1);
  // Stored tasks are offered on mount, never automatically consumed.
  await page.evaluate(project => sessionStorage.setItem('networkis:pending-agent-task', JSON.stringify({ text: 'Prüfe nur den aktuellen Stand.', source: 'external', projectId: project })), project);
  await page.reload(); await page.getByRole('button', { name: 'AI Assistant öffnen', exact: true }).click();
  await panel.getByRole('button', { name: 'Auftrag starten', exact: true }).waitFor();
  assert.equal(calls.length, 1);
  await composerVisible(); await panel.getByRole('button', { name: 'Auftrag starten', exact: true }).click();
  await page.waitForTimeout(1500); assert.equal(calls.length, 2);
  assert.equal(await panel.locator('.eng-agent-pending-task').count(), 0);
  checks.push('Stored task waits on reopening and submits exactly once after explicit Start');
  // File errors and truncation are visible before sending.
  await panel.locator('input[type=file]').setInputFiles({ name: 'bad.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('unsupported') });
  await panel.getByRole('alert').waitFor(); assert.equal(calls.length, 2);
  await panel.locator('input[type=file]').setInputFiles({ name: 'Auszug.txt', mimeType: 'text/plain', buffer: Buffer.from('a'.repeat(17000)) });
  await panel.locator('.eng-agent-attachment summary').waitFor();
  assert.match(await panel.locator('.eng-agent-attachment summary').innerText(), /Auszug/);
  await panel.getByRole('button', { name: 'Auszug.txt entfernen' }).click();
  assert.equal(await panel.locator('.eng-agent-attachment').count(), 0);
  checks.push('Unsupported file, explicit excerpt and remove attachment');
  await panel.screenshot({ path: '../backend/runtime/agent-composer-desktop.png' });
  const resize = panel.getByRole('button', { name: 'Breite und Höhe des Assistentenfensters ändern' });
  await resize.focus(); for (let i = 0; i < 20; i++) await resize.press('ArrowDown');
  await composerVisible();
  await page.setViewportSize({ width: 390, height: 700 }); await composerVisible();
  await panel.screenshot({ path: '../backend/runtime/agent-composer-mobile.png' });
  checks.push('Composer visible at minimum panel height and on mobile');
  // First-open handoff must not be lost by lazy mounting the chat.
  await page.reload();
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('engineering-agent:ask', { detail: 'Warum ist diese Route ungültig?' })));
  await input.waitFor(); assert.equal(await input.inputValue(), 'Warum ist diese Route ungültig?');
  assert.equal(calls.length, 2);
  checks.push('External question survives first open as an editable draft');
  assert.deepEqual(errors, []);
  const build = await (await fetch('http://127.0.0.1:13500/build-info.json')).json();
  await fs.writeFile('../backend/runtime/agent-composer-browser-result.json', JSON.stringify({ build: build.build_id, idlePollChecked: !process.env.AGENT_SMOKE_SKIP_IDLE, checks, errors, explicitChatRequests: calls.length }, null, 2));
  console.log(JSON.stringify({ checks, errors, explicitChatRequests: calls.length }, null, 2));
} catch (error) {
  console.error(error); console.error({ errors, checks, calls: calls.length });
  await page.screenshot({ path: '../backend/runtime/agent-composer-failure.png' });
  throw error;
} finally {
  releaseResponse?.();
  await Promise.race([page.unrouteAll({ behavior: 'ignoreErrors' }), new Promise(resolve => setTimeout(resolve, 5000))]);
  // Ask the owned Chrome instance to exit itself. Killing its process tree can
  // be denied by Windows even though the automation session owns the browser.
  if (browser.isConnected()) {
    const session = await browser.newBrowserCDPSession();
    await session.send('Browser.close').catch(() => {});
  }
  await Promise.race([browser.close(), new Promise(resolve => setTimeout(resolve, 5000))]);
}
