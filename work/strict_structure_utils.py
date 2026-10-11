"""Guard and retain evidence for the user's stricter consolidation request."""
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/implementation-workloads/structure-consolidation-20261004'
GUARD = Path('F:/CodexOrdner/skills/lokaler-implementierungs-agent/scripts/implementation_guard.py')
WRITES = {}
REMOVALS = []

def read(relative):
    return (ROOT / relative).read_text(encoding='utf-8-sig')

def write(relative, text):
    WRITES[relative] = text

def segment(source, node):
    start = min([node.lineno] + [d.lineno for d in getattr(node, 'decorator_list', [])])
    return '\n'.join(source.splitlines()[start-1:node.end_lineno])

def parts(source, names):
    nodes = {getattr(node, 'name', None):node for node in ast.parse(source).body}
    return '\n\n\n'.join(segment(source, nodes[name]) for name in names) + '\n'

def without(source, names, insertion):
    lines = source.splitlines(keepends=True)
    nodes = [node for node in ast.parse(source).body if getattr(node, 'name', None) in names]
    for node in sorted(nodes, key=lambda n:n.lineno, reverse=True):
        start = min([node.lineno] + [d.lineno for d in getattr(node, 'decorator_list', [])])
        lines[start-1:node.end_lineno] = [insertion + '\n'] if node is nodes[0] else []
    return ''.join(lines)

def apply(label):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / 'workload.json'
    work = json.loads(path.read_text()) if path.exists() else dict(
        goal_id='structure-consolidation-20261004',goal_type='STRUCTURE_CONSOLIDATION',
        repository=str(ROOT),project_scope='Canonical NIS; complete technology ownership and remove empty source scaffolding',
        requested_change='Revisit the complete migration plan after user grade 3; consolidate remaining actual technical rules and empty packages',
        kind='implementation',modify_code=True,allow_repair=True,
        constraints=['Preserve public contracts and stored identities','Use isolated SQL and the exact-image release gate','Preserve preexisting work and historical evidence'],
        forbidden_changes=['Foreign technology fallback','Product DB tests','Unverified capability claims','Historical image pruning'],
        required_outcomes=['native_format_ownership','simulation_technology_ownership','assessment_technology_ownership','empty_scaffolding_removed','complete_dependency_evidence','production_delivery'],
        validation_requirements=['behavior_equivalence','targeted_regressions','architecture','full_release_gate','production_verification'],
        unresolved_decisions=[],remaining_findings=['native_format_rules','legacy_generator_rules','assessment_rules','empty_scaffolding'],
        completion_status='IMPLEMENTING',files_changed=[])
    changed = list(WRITES) + REMOVALS
    revisions = {}
    for relative in changed:
        actual = ROOT / relative
        revisions[relative] = hashlib.sha256(actual.read_bytes()).hexdigest() if actual.is_file() else None
        if actual.is_file():
            backup = OUT / 'before' / label / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(actual.read_bytes())
    work['revision_before'] = revisions
    work['files_changed'] = sorted(set(work['files_changed']) | set(changed))
    path.write_text(json.dumps(work,indent=2),encoding='utf-8')
    result = subprocess.run([sys.executable,str(GUARD),'before-apply','--workload',str(path)],capture_output=True,text=True)
    (OUT / (label+'-guard.json')).write_text(result.stdout,encoding='utf-8')
    if result.returncode:
        raise RuntimeError(result.stdout)
    for relative, text in WRITES.items():
        if relative.endswith('.py'): ast.parse(text,filename=relative)
        actual = ROOT / relative
        actual.parent.mkdir(parents=True,exist_ok=True)
        actual.write_text(text,encoding='utf-8',newline='\n')
    for relative in REMOVALS:
        actual = (ROOT / relative).resolve()
        assert actual.is_relative_to(ROOT.resolve())
        actual.unlink()
    (OUT / (label+'-files.json')).write_text(json.dumps(changed),encoding='utf-8')
    print(f'{label}: {len(WRITES)} writes, {len(REMOVALS)} removals guarded')
