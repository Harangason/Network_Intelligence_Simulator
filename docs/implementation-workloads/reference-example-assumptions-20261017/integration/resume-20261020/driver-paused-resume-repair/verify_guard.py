"""Exercise the actual pause guard and preserve all unrelated operator AST."""
import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import difflib
import hashlib
import json
from pathlib import Path
import shutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]
DRIVER = ROOT / 'docs/implementation-workloads/reference-example-assumptions-20261017/integration/resume-20261018/native_original_document_driver.py'
CHECKPOINT = OUT.parent / 'verified-paused-reference-checkpoint.json'
STATE = ROOT / 'docs/implementation-workloads/reference-example-assumptions-20261017/integration/native-tagged-vehicle/state.json'
before = ast.parse((OUT / 'before.py').read_text(encoding='utf-8'))
after = ast.parse(DRIVER.read_text(encoding='utf-8'))
function = next(row for row in after.body if getattr(row, 'name', None) == 'verify_paused_reference_resume')
environment = dict(Path=Path, json=json, hashlib=hashlib, datetime=datetime, timezone=timezone)
exec(compile(ast.Module(body=[function], type_ignores=[]), str(DRIVER), 'exec'), environment)
guard = environment[function.name]
checkpoint = json.loads(CHECKPOINT.read_text(encoding='utf-8'))
state = json.loads(STATE.read_text(encoding='utf-8'))
pending = checkpoint['pending_generation']
now = datetime.fromisoformat(checkpoint['at_utc']) + timedelta(seconds=1)
assert guard(pending, state, CHECKPOINT, now=now) == checkpoint
results = [{'case': 'actual_verified_user_pause_and_restart', 'status': 'PASSED'}]


def reject(name, change):
    case = OUT / 'counterexamples' / name
    case.mkdir(parents=True, exist_ok=False)
    cp, st, generation = deepcopy(checkpoint), deepcopy(state), deepcopy(pending)
    proofs = {}
    for key in ('pause_evidence', 'stop_evidence', 'restarted_app_evidence', 'peer_observation'):
        proofs[key] = json.loads(Path(cp[key]['path']).read_text(encoding='utf-8'))
    extra = {'now': now, 'checkpoint_missing': False, 'corrupt_hash': False}
    change(cp, st, generation, proofs, extra)
    for key, value in proofs.items():
        path = case / (key + '.json')
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        cp[key] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    if extra['corrupt_hash']:
        cp['pause_evidence']['sha256'] = '0' * 64
    path = case / 'checkpoint.json'
    path.write_text(json.dumps(cp, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    try:
        guard(generation, st, None if extra['checkpoint_missing'] else path, now=extra['now'])
    except (AssertionError, ValueError, KeyError, TypeError):
        results.append({'case': name, 'status': 'PASSED', 'invalid_resume_rejected': True})
    else:
        raise AssertionError('Invalid resume accepted: ' + name)


reject('default_running_without_checkpoint', lambda c,s,g,p,e: e.update(checkpoint_missing=True))
for key in ('project_id', 'image_id', 'source_sha256', 'original_sha256'):
    reject('different_' + key, lambda c,s,g,p,e,k=key: s.update({k: 'different'}))
reject('changed_pending_token', lambda c,s,g,p,e: g.update(token='different'))
reject('different_pending_original', lambda c,s,g,p,e: (g.update(source_sha256='different'), c.update(pending_generation=deepcopy(g))))
reject('stale_checkpoint', lambda c,s,g,p,e: e.update(now=now + timedelta(seconds=301)))
reject('future_checkpoint', lambda c,s,g,p,e: e.update(now=now - timedelta(seconds=2)))
reject('unverified_hash', lambda c,s,g,p,e: e.update(corrupt_hash=True))
reject('live_peer', lambda c,s,g,p,e: p['peer_observation'].update(native_driver_processes=[{'ProcessId': 123}]))
reject('stale_peer_observation', lambda c,s,g,p,e: p['peer_observation'].update(at_utc=(now - timedelta(seconds=301)).isoformat()))
reject('not_an_explicit_user_pause', lambda c,s,g,p,e: p['pause_evidence'].update(status='FAILED'))
reject('different_saved_image', lambda c,s,g,p,e: p['pause_evidence'].update(candidate_image_id='different'))
reject('different_restarted_image', lambda c,s,g,p,e: p['restarted_app_evidence'].update(Image='different'))
reject('production_app_as_target', lambda c,s,g,p,e: p['restarted_app_evidence'].update(Name='/NetworkIS'))
reject('wrong_network', lambda c,s,g,p,e: p['restarted_app_evidence']['HostConfig'].update(NetworkMode='production'))
reject('app_not_running', lambda c,s,g,p,e: p['restarted_app_evidence']['State'].update(Running=False))
reject('app_never_restarted_after_pause', lambda c,s,g,p,e: p['restarted_app_evidence']['State'].update(StartedAt='2026-10-18T00:00:00Z'))
reject('old_app_was_not_stopped', lambda c,s,g,p,e: p['stop_evidence']['after']['nis-e2e-app-7f7e56f67ca2']['state'].update(Running=True))
reject('cleanup_instead_of_pause', lambda c,s,g,p,e: p['stop_evidence'].update(no_removals=False))


class NormalizeResumeGuard(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        return None if node.name == function.name else self.generic_visit(node)

    def visit_Expr(self, node):
        if (isinstance(node.value, ast.Call) and node.value.args
                and isinstance(node.value.args[0], ast.Constant)
                and node.value.args[0].value == '--resume-checkpoint'):
            return None
        return self.generic_visit(node)

    def visit_If(self, node):
        if (len(node.body) == 2 and isinstance(node.body[0], ast.Assign)
                and isinstance(node.body[0].value, ast.Call)
                and isinstance(node.body[0].value.func, ast.Name)
                and node.body[0].value.func.id == function.name):
            return ast.parse("assert not pending or (pending.get('reference_generation') or {}).get('status') != 'RUNNING'").body[0]
        return self.generic_visit(node)


assert ast.dump(before) == ast.dump(NormalizeResumeGuard().visit(deepcopy(after)))
shutil.copy2(DRIVER, OUT / 'after.py')
(OUT / 'changes.diff').write_text(''.join(difflib.unified_diff(
    (OUT / 'before.py').read_text(encoding='utf-8').splitlines(True),
    DRIVER.read_text(encoding='utf-8').splitlines(True), fromfile='before.py', tofile='after.py')), encoding='utf-8')
report = {'cases': results, 'passed': len(results), 'other_driver_ast_unchanged': True,
          'model_or_application_code_changed': False, 'model_simulation_or_release_pass': False}
(OUT / 'guard-validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'guard_cases_passed': len(results), 'other_driver_ast_unchanged': True}))
