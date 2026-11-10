"""Freeze terminal evidence and the exact-finding accumulation repair plan."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

ROOT = Path.cwd()
GOAL = ROOT / 'docs/implementation-workloads/nis-neu9-small-llm-full-20261106'
OUT = GOAL / 'finding-accumulation-repair'
TERMINAL = Path(__file__).resolve().parent
OUT.mkdir(exist_ok=True)
(OUT / 'before').mkdir(exist_ok=True)

def evidence(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

context = json.loads((TERMINAL / 'complete-context.json').read_text(encoding='utf8'))
findings = context['current_candidate']['unresolved']
keys = Counter(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in findings)
finding = {'at_utc': datetime.now(timezone.utc).isoformat(), 'terminal': evidence(TERMINAL / 'terminal-process-proof.json'),
    'context': evidence(TERMINAL / 'complete-context.json'), 'restored_admission': evidence(TERMINAL / 'restored-token-admission.json'),
    'total_findings': len(findings), 'distinct_exact_findings': len(keys), 'duplicate_occurrences': len(findings)-len(keys),
    'root_cause': 'Every native stage appends unresolved rows without idempotency. Identical code/message/target_ref triples recur in the same original candidate. This duplicates questions and inflates subsequent complete contexts.',
    'separate_environment_failure': 'Diagnostic tokenizer host13503 was absent at terminal inspection. Exact saved complete context fits53972 tokens including unchanged reserves after restarting unchanged host. Original process disappearance cause unknown.',
    'forbidden': 'Do not resolve/drop distinct findings, alter targets/messages, import this intermediate model, resume its inventory or loosen any validation.'}
(OUT / 'finding.json').write_text(json.dumps(finding, ensure_ascii=False, indent=2), encoding='utf8')
app = 'backend/nis/agent/orchestration/local_reasoner.py'
test = 'backend/tests/test_reference_finding_accumulation.py'
before = OUT / 'before/local_reasoner.py'
assert not before.exists(), 'Do not overwrite immutable baseline'
before.write_bytes((ROOT / app).read_bytes())
work = {'goal_id':'neu9-exact-finding-accumulation-repair', 'kind':'repair', 'repository':str(ROOT),
    'modify_code':True, 'allow_repair':True, 'status':'PLANNED',
    'required_outcomes':['distinct_findings_preserved','repeated_findings_idempotent','native_counter_verified'],
    'validation_requirements':['red_green','adjacent_regression','native_counter','source_scope'],
    'revision_before':{app:evidence(ROOT/app)['sha256'],test:None}, 'before':[evidence(before)],
    'repair':{'owner':'PROJECT_PRODUCT','root_cause':finding['root_cause'],
              'first_failing_layer':'Native reference stage result accumulation',
              'reproduction':'Terminal original82889 contains96 unresolved entries but only33 exact triples, preserved in immutable full context.',
              'evidence':[evidence(OUT/'finding.json'),evidence(TERMINAL/'complete-context.json')],
              'weaken_assertions_to_pass':False},
    'implementation_plan':['Deduplicate only exact validated finding triples against current unresolved and within the accepted stage delta. Keep original raw response/hash/cache history and every different code/message/target unchanged.',
                           'Explicitly request new findings only; current findings remain authoritative. Test repeated native stage outputs, target/message distinctions and invalid outputs. Native small-model counter then fresh full original.'],
    'constraints':['No source/model/token/output/timeout/public schema changes','No accepted original/simulation/release claim from a counter','Production delivery remains required'],
    'remaining_findings':['Full neu9, simulation, complete release and exact production delivery remain open']}
(OUT/'workload.json').write_text(json.dumps(work,ensure_ascii=False,indent=2),encoding='utf8')
root = json.loads((GOAL/'workload.json').read_text(encoding='utf8'))
root['status']='REPAIRING'
root['active_native']={'session':82889,'status':'TERMINAL_INVALID_INPUT','evidence':evidence(TERMINAL/'terminal-process-proof.json'),'exit_code':'unavailable after tool handle loss; normal RESULT and process end verified'}
root['current_repair']=evidence(OUT/'workload.json')
(GOAL/'workload.json').write_text(json.dumps(root,ensure_ascii=False,indent=2),encoding='utf8')
note='## '+datetime.now(timezone.utc).isoformat()+' — 82889 naturally terminal; exact findings repair\n\n59 validated calls,144 internal ports; normal INVALID_INPUT context guard, Python processes ended, workeridle. Lost toolhandle means exitcode unobserved. Host13503 absent; restarted exact unchanged service detached, full saved context fits53972tokens with reserves.96 findings include63 exact repeated occurrences. Repair accumulation, retain all distinct findings/raw provenance/source/gates; no internal resume or fullmodel acceptance. EIP startup window ended19:21:02UTC Exit1/ownerproofmissing; no competing inference. Production unchanged. All7/7original requirements remain.\n\n'
for name in ('NEXT.md','REPORT.md'):
    p=GOAL/name
    p.write_text(note+p.read_text(encoding='utf8'),encoding='utf8')
print(OUT/'workload.json')
