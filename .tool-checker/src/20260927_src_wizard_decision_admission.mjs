/** Original-contract admission only; no browser, HTTP, inference or model write. */
import { readFile } from 'node:fs/promises';
import path from 'node:path';

export function decisionAdmission(original) {
  const mode = original?.decision_mode;
  if (mode === 'INTERACTIVE') return {
    allowed: false, reason: 'NIS_INTERACTIVE_DECISION_BRIDGE_MISSING',
    detail: 'Original INTERACTIVE contract requires actual question/proposal/options and explicit user continuation. This executor only has scripted heuristics; no browser action or approval was performed.',
    decision_mode: mode,
  };
  if (mode !== 'SCRIPTED') return {
    allowed: false, reason: 'NIS_ORIGINAL_DECISION_MODE_UNSUPPORTED',
    detail: 'Missing or unknown original decision mode cannot authorize scripted answers or approvals.',
    decision_mode: mode ?? null,
  };
  return {
    allowed: false, reason: 'NIS_SCRIPTED_DECISION_BINDING_UNSUPPORTED',
    detail: 'This executor does not consume the exact original expected_decision as an action-specific answer. A nonempty value cannot authorize unrelated heuristic choices or approvals.',
    decision_mode: mode,
    expected_decision_present: Object.hasOwn(original, 'expected_decision'),
  };
}

export async function originalDecision(root, input) {
  const state = path.resolve(root, '.tool-checker/state');
  if (!/^job-[a-f0-9]{32}$/.test(input?.job_id ?? '') ||
      path.resolve(input?.output_directory ?? '') !== path.join(state, 'jobs', input.job_id)) {
    throw new Error('Native wizard decision admission requires an exact job evidence directory');
  }
  const job = JSON.parse(await readFile(path.join(input.output_directory, 'job.json'), 'utf8'));
  if (job.job_id !== input.job_id || job.run_id !== input.run_id ||
      !/^[a-zA-Z0-9_-]+$/.test(job.task_id ?? '') || !/^[a-zA-Z0-9_-]+$/.test(job.test_id ?? '') ||
      !job.plan.some(step => JSON.stringify(step) === JSON.stringify(input.step))) {
    throw new Error('Native wizard decision admission job/step binding mismatch');
  }
  const original = JSON.parse(await readFile(path.join(state, 'tasks', job.task_id, 'test_cases', job.test_id + '.json'), 'utf8'));
  if (original.test_id !== job.test_id || original.contract_hash !== job.contract_hash ||
      input.step.case.test_id !== job.test_id || input.step.case.decision_mode !== original.decision_mode) {
    throw new Error('Original wizard decision contract differs from native job/step');
  }
  return { original, job, result: decisionAdmission(original) };
}
