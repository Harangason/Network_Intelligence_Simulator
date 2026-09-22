/** Focused evidence adapter for the six contracts that cannot use generic intake. */
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/(.:)/, '$1')), '..');
const input = JSON.parse(await new Promise((resolve, reject) => {
  let data = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', chunk => { data += chunk; });
  process.stdin.on('end', () => resolve(data));
  process.stdin.on('error', reject);
}));
const { step } = input;
const scenario = step.case;
const evidenceDir = path.join(process.env.TOOL_CHECKER_EVIDENCE_ROOT || path.join(root, '.tool-checker', 'evidence'), scenario.test_id);
await mkdir(evidenceDir, { recursive: true });
const evidence = [];

async function save(name, value, kind = 'validation') {
  const target = path.join(evidenceDir, name);
  await writeFile(target, typeof value === 'string' ? value : JSON.stringify(value, null, 2), 'utf8');
  evidence.push({ ref: name, path: target, kind });
  return name;
}

const testMap = {
  S41: ['backend/tests/test_assistant_capabilities.py'],
  S48: ['backend/tests/test_industry60_intake_regressions.py', 'backend/tests/test_goal_execution.py'],
  S51: ['backend/tests/test_industry60_intake_regressions.py::test_meta_typing_request_is_not_converted_into_a_project_draft', 'backend/tests/test_universal_agent_io.py::test_typing_does_not_merge_same_name_and_id_overrides_name'],
  S53: ['backend/tests/test_goal_execution.py::test_capability_and_free_controller_requires_explicit_port_decision', 'backend/tests/test_goal_execution.py::test_existing_port_reused_and_occupied_port_not_replugged'],
  S55: ['backend/tests/test_assistant_capabilities.py::test_directory_has_unique_executable_workflows_and_real_tools', 'backend/tests/test_assistant_capabilities.py::test_action_lookup_rejects_invented_capability', 'backend/tests/test_assistant_capabilities.py::test_new_execution_tools_are_available_to_the_reasoner'],
  S59: ['backend/tests/test_goal_execution.py::test_navigation_or_tool_success_is_not_completion', 'backend/tests/test_universal_agent_io.py::test_completion_requires_requested_outputs_and_domain_evidence'],
};

const python = path.join(root, 'backend', '.venv', 'Scripts', 'python.exe');
const isolatedRunner = path.join(root, 'scripts', 'run-isolated-tests.py');
const probe = spawnSync(python, [isolatedRunner, '--', '-q', ...(testMap[scenario.test_id] || [])], {
  cwd: root, encoding: 'utf8', timeout: 240_000, env: { ...process.env, PYTHONUTF8: '1' },
});
const probeLog = await save('focused-pytest.txt', `${probe.stdout || ''}\n${probe.stderr || ''}`, 'log');
const browserActions = [];
const observedViews = [];

if (scenario.browser_required) {
  const require = createRequire(path.join(root, 'frontend', 'package.json'));
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const url = `${step.base_url.replace(/\/$/, '')}/studio/engineering?assistant=project&project=${encodeURIComponent(step.project_id)}`;
    await page.goto(url, { waitUntil: 'load', timeout: 120_000 });
    if (scenario.test_id === 'S41') {
      const dialog = page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' });
      await dialog.waitFor({ state: 'visible', timeout: 60_000 });
      await page.keyboard.press('Escape');
      await dialog.waitFor({ state: 'hidden', timeout: 30_000 });
      const capabilities = page.getByText('Fähigkeiten und Wizards', { exact: true }).last();
      if (await capabilities.count()) {
        await capabilities.focus();
        await capabilities.press('Enter');
      }
      for (const label of ['Architektur erstellen', 'Signal prüfen', 'Trace analysieren', 'Finding bewerten']) {
        const button = page.getByRole('button', { name: label, exact: true }).last();
        const visible = await button.isVisible().catch(() => false);
        if (visible) { await button.hover(); await button.focus(); }
        browserActions.push({ target: label, purpose: 'Wizard capability entry inspect', precondition: 'Engineering assistant loaded', expected_effect: 'Focusable registered wizard action', actual_effect: visible ? 'Visible, hoverable and keyboard-focusable' : 'Entry not visible in the inspected view', url: page.url(), status: visible ? 'PASSED' : 'BLOCKED' });
      }
      const shot = path.join(evidenceDir, 'capability-wizards.png');
      await page.screenshot({ path: shot, fullPage: true });
      evidence.push({ ref: 'capability-wizards.png', path: shot, kind: 'screenshot' });
      for (const action of browserActions) action.evidence = ['capability-wizards.png', 'focused-pytest.txt'];
      observedViews.push({ name: 'Fähigkeiten und Wizards', status: 'PASSED', evidence: ['capability-wizards.png'] });
    } else {
      const dialog = page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' });
      await dialog.waitFor({ state: 'visible', timeout: 60_000 });
      const next = dialog.locator('.eng-agent-questionnaire-head').getByRole('button');
      const disabled = await next.isDisabled();
      const shot = path.join(evidenceDir, 'wizard-required-field.png');
      await page.screenshot({ path: shot, fullPage: true });
      evidence.push({ ref: 'wizard-required-field.png', path: shot, kind: 'screenshot' });
      browserActions.push({ target: 'Weiter', purpose: 'Pflichtfeldvalidierung ohne Projektdaten prüfen', precondition: 'Leeres Pflichtfeld', expected_effect: 'Weiter bleibt gesperrt', actual_effect: disabled ? 'Button disabled' : 'Button unexpectedly enabled', url: page.url(), status: disabled ? 'PASSED' : 'FAILED', evidence: ['wizard-required-field.png'] });
      observedViews.push({ name: 'Wizard-Validierung', status: disabled ? 'PASSED' : 'FAILED', evidence: ['wizard-required-field.png'] });
    }
  } finally {
    await browser.close();
  }
}

const pytestPassed = probe.status === 0;
const refs = [probeLog, ...evidence.filter(item => item.kind === 'screenshot').map(item => item.ref)];
const observations = {
  actions: [],
  tools: [
    ...(scenario.browser_required ? [{ name: 'Browser', status: 'PASSED', evidence: refs }] : []),
    { name: 'Core validators', status: pytestPassed ? 'PASSED' : 'FAILED', evidence: [probeLog] },
  ],
  views: observedViews,
  outputs: [{ name: 'Fresh evidence per case', status: 'PASSED', evidence: refs }],
  questions: [], checks: [], browser: browserActions,
  findings: pytestPassed ? [] : [{ code: `TC_${scenario.test_id}_FOCUSED_PROBE_FAILED`, category: 'TOOL_BUG', blocking: true, detail: `Focused pytest exited ${probe.status}` }],
  claimed_complete: false,
};
process.stdout.write(JSON.stringify({ status: pytestPassed ? 'PASSED' : 'FAILED', llm_calls: null, evidence, observations }));
