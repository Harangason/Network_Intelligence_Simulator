/** Original-contract admission only; no browser, HTTP, inference or model write. */
import { readFile, writeFile, rename } from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';

export function decisionAdmission(original, input) {
  const mode = original?.decision_mode;
  if (mode === 'INTERACTIVE' && input?.automated_e2e === true) return {
    allowed: true, decision_mode: mode, bridge: 'AUTOMATED_E2E_UI',
    detail: 'Automated browser test actions require original-contract checks and provenance; no user answer is represented.',
  };
  if (mode === 'INTERACTIVE') return input?.interactive_decision_bridge === 1
    ? { allowed: true, decision_mode: mode, bridge: 'NATIVE_JOB_INTERACTIVE_V1' }
    : { allowed: false, reason: 'NIS_INTERACTIVE_DECISION_BRIDGE_MISSING',
      detail: 'Original INTERACTIVE contract requires a native question/proposal and explicit user answer.', decision_mode: mode };
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
      Boolean(job.automated_e2e) !== Boolean(input.automated_e2e) ||
      !job.plan.some(step => JSON.stringify(step) === JSON.stringify(input.step))) {
    throw new Error('Native wizard decision admission job/step binding mismatch');
  }
  const original = JSON.parse(await readFile(path.join(state, 'tasks', job.task_id, 'test_cases', job.test_id + '.json'), 'utf8'));
  if (original.test_id !== job.test_id || original.contract_hash !== job.contract_hash ||
      input.step.case.test_id !== job.test_id || input.step.case.decision_mode !== original.decision_mode ||
      input.step.case.input !== original.input ||
      JSON.stringify(input.step.case.user_inputs) !== JSON.stringify(original.user_inputs)) {
    throw new Error('Original wizard decision contract differs from native job/step');
  }
  return { original, job, result: decisionAdmission(original, input) };
}

export function interactiveDecisionBridge(input) {
  if (input?.interactive_decision_bridge !== 1) throw new Error('Native interactive bridge missing');
  let sequence = 0;
  return async function decide(question, options, proposal) {
    if (typeof question !== 'string' || !question.trim() || !Array.isArray(options)
        || options.length < 2 || new Set(options).size !== options.length
        || options.some(value => typeof value !== 'string' || !value)) {
      throw new Error('Invalid interactive decision contract');
    }
    sequence += 1;
    const revision = createHash('sha256').update(JSON.stringify(proposal ?? null)).digest('hex');
    const directory = input.output_directory;
    const request = path.join(directory, `adapter-decision-${sequence}.json`);
    const temporary = request + '.tmp';
    await writeFile(temporary, JSON.stringify({ sequence, question, options, proposal, revision }), { flag: 'wx' });
    await rename(temporary, request);
    const answerPath = path.join(directory, `answer-${input.step.step_id}-decision-${sequence}.json`);
    for (;;) {
      try {
        const answer = JSON.parse(await readFile(answerPath, 'utf8'));
        if (answer.step_id !== `${input.step.step_id}-decision-${sequence}` ||
            answer.decision_source !== 'INTERACTIVE' || !options.includes(answer.choice)) {
          throw new Error('Native interactive answer does not match pending options');
        }
        return { choice: answer.choice, revision, decision_source: 'INTERACTIVE' };
      } catch (error) {
        if (error.code !== 'ENOENT') throw error;
      }
      try { await readFile(path.join(directory, 'cancel.json')); throw new Error('Native job cancelled'); }
      catch (error) { if (error.code !== 'ENOENT') throw error; }
      await new Promise(resolve => setTimeout(resolve, 200));
    }
  };
}
