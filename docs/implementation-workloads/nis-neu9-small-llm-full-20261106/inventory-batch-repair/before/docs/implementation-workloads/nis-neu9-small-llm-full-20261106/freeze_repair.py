"""Record the tested minimal source scope and exact next normal image identity."""
import ast
import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path

out=Path(__file__).resolve().parent
root=out.parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--phase',choices=['source-reference','source-semantics','function-coverage'],required=True)
args=parser.parse_args()
semantic_phase=args.phase in {'source-semantics','function-coverage'}
coverage_phase=args.phase=='function-coverage'
directory=out/({'source-reference':'intake-source-reference-repair','source-semantics':'source-semantics-repair','function-coverage':'function-coverage-repair'}[args.phase])
baseline=out/'intake-cardinality-repair'/'before'
def baseline_file(name):
    if (baseline/name).exists():return baseline/name
    if (directory/'before'/name).exists():return directory/'before'/name
    return out/'source-semantics-repair/before'/name
assert not (directory/'source-scope-proof.json').exists(), 'Never overwrite a frozen proof'
work=json.loads((out/'workload.json').read_text(encoding='utf-8'))
def ref(path):
    return {'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
def module_at(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
def parse(path):
    return ast.parse(path.read_text(encoding='utf-8'))
name='backend/nis/agent/orchestration/local_reasoner.py'
before,after=parse(baseline/name),parse(root/name)
def without_intake(tree):
    for item in tree.body:
        if isinstance(item,ast.ClassDef) and item.name=='LocalEngineeringReasoner':
            item.body=[method for method in item.body if getattr(method,'name',None)!='interpret_document']
    return ast.dump(tree,include_attributes=False)
assert without_intake(before)==without_intake(after)
before_test=parse(baseline/'backend/tests/test_qwen_document_intake.py')
after_test=parse(root/'backend/tests/test_qwen_document_intake.py')
assert ast.dump(ast.Module(body=after_test.body[:len(before_test.body)],type_ignores=[]),include_attributes=False)==ast.dump(before_test,include_attributes=False)
if semantic_phase:
    previous_tests=parse(directory/'before/backend/tests/test_qwen_document_intake.py')
    assert ast.dump(ast.Module(body=after_test.body[:len(previous_tests.body)],type_ignores=[]),include_attributes=False)==ast.dump(previous_tests,include_attributes=False)
def without_component_sources(tree):
    changed={'document_component_sources','document_component_policy','_document_context_heading'} if semantic_phase else {'document_component_sources'}
    tree.body=[node for node in tree.body if getattr(node,'name',None) not in changed]
    return ast.dump(tree,include_attributes=False)
intake='backend/nis/agent/orchestration/project_intake.py'
assert without_component_sources(parse(baseline/intake))==without_component_sources(parse(root/intake))
if coverage_phase:
    def without_coverage(tree):
        tree.body=[node for node in tree.body if getattr(node,'name',None)!='document_component_sources']
        return ast.dump(tree,include_attributes=False)
    assert without_coverage(parse(directory/'before'/intake))==without_coverage(parse(root/intake))
    for filename,digest in work['frozen_files'].items():
        if filename not in {intake,'backend/tests/test_qwen_document_intake.py'}:
            assert ref(root/filename)['sha256']==digest
import xml.etree.ElementTree as ET
def suite(path):
    return next(ET.parse(path).getroot().iter('testsuite')).attrib
checks=(['green.xml','green-final.xml','regression-final.xml'] if coverage_phase else ['green.xml','boundary-green-regression.xml','function-shape-green-regression.xml','profile-scope-green-regression.xml','literal-header-green-regression.xml','source-scope-regression.xml'] if semantic_phase else ['green.xml','regression.xml'])
for filename in checks:
    result=suite(directory/filename)
    assert result['failures']==result['errors']=='0', (filename,result)
diff=[]
after_refs=[]
for name in work['files_changed']:
    old=baseline_file(name)
    new=root/name
    target=directory/'after'/name
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(new.read_bytes())
    after_refs.append(ref(target))
    diff.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),new.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+name,tofile='after/'+name))
(directory/'change.diff').write_text(''.join(diff),encoding='utf-8')
source=module_at('neu9_freeze_manifest',root/'scripts/write-build-info.py').build_manifest()
verification=module_at('neu9_freeze_gate',root/'scripts/run-release-gate.py').verification_manifest()
proof={'at':datetime.now(timezone.utc).isoformat(),'status':'FROZEN_AFTER_LOCAL_GREEN',
       'only_reasoner_method_changed':'interpret_document','all_other_reasoner_ast_identical':True,'all_original_test_module_ast_preserved':True,
       'intake_functions_changed':['document_component_sources','document_component_policy','_document_context_heading'] if semantic_phase else ['document_component_sources'],'all_other_intake_ast_identical':True,
       'source':source,'verification_sha256':verification,'files':{name:ref(root/name)['sha256'] for name in work['files_changed']},
       'scope':'No family-specific path, public validator, source text, model/context/output/timeout configuration or canonical model changed.'}
if semantic_phase:
    assert json.loads((root/'backend/nis/domain/inventory-vocabulary.json').read_text(encoding='utf-8'))==json.loads((root/'frontend/src/features/agent/lib/inventory-vocabulary.json').read_text(encoding='utf-8'))
    controlled_path=directory/('minimum-required-review-final/result.json' if coverage_phase else 'controlled-review-frozen-final/result.json')
    controlled=json.loads(controlled_path.read_text(encoding='utf-8'))
    assert controlled['quantity_sum']==251 and controlled['actual_inference_requests']==0 and controlled['no_dangling_function_fragments']
    assert controlled['source_system_profiles']==[[]]
    assert controlled['explicit_monitoring_function_preserved'] and controlled['no_structure_only_claims']
    proof['previous_intake_module_ast_preserved']=True
    proof['vocabulary_frontend_is_exact_domain_projection']=True
    proof['controlled_review']=ref(controlled_path)
    if coverage_phase:
        assert controlled['component_key_selection']=='required'
        proof['delta_only_intake_method_changed']='document_component_sources'
        proof['local_validation_scope']={'current_regression':suite(directory/'regression-final.xml'),'current_targeted':suite(directory/'green-final.xml'),'qualification':'Full earlier537 reference/adjacent tests preserved separately; current full document/adjacent regression and required-only product projection. Native Original and full final release still required.'}
    else:proof['local_validation_scope']={'extended_full_regression_before_final_metadata_guard':suite(directory/'source-scope-regression.xml'),
                                     'current_metadata_scope_regression':suite(directory/'literal-header-green-regression.xml'),
                                     'qualification':'537 full adjacent/reference cases passed before the final two metadata guards;52 focused cases and full controlled private/public/frontend projection passed after them. Full release gate and actual native Original remain required.'}
(directory/'source-scope-proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
work.update(after=after_refs,diff=[ref(directory/'change.diff')],frozen_files=proof['files'],
            frozen_source=source,frozen_verification_sha256=verification)
evidence_names=(['red.xml','green.xml','green-final.xml','regression.xml','regression-final.xml','technology-declaration-red.xml','technology-declaration-before.json','minimum-required-review-final/result.json','source-scope-proof.json'] if coverage_phase else ['red.xml','green-01.xml','iteration-01.json','frontend-tests.json','green.xml','regression.xml','boundary-red.xml','boundary-green-regression.xml','final-regression.xml','function-shape-red.xml','function-shape-red-02.xml','function-shape-green-regression.xml','controlled-review-final/result.json','final-bundled-regression.xml','profile-scope-red.xml','profile-scope-green-regression.xml','frontend-final-tests.log','controlled-review-source-scope/result.json','source-scope-regression.xml','literal-header-red.xml','literal-header-green-regression.xml','controlled-review-frozen-final/result.json','source-scope-proof.json'] if semantic_phase else ['red.xml','fixture-correction.json','red-full-source-corrected-fixture.xml','green.xml','regression.xml','source-scope-proof.json'])
work['repair']['evidence'] += [ref(directory/name) for name in evidence_names]
regression_name='regression-final.xml' if coverage_phase else 'source-scope-regression.xml' if semantic_phase else 'regression.xml'
work['tests'].extend([{'scope':'Required source function coverage and pure technology separation' if coverage_phase else 'Shared source semantics' if semantic_phase else 'Empty delimiter clauses and full preserved original private/public projection', 'red':suite(directory/'red.xml'), 'green':suite(directory/'green.xml'), 'evidence':[ref(directory/name) for name in evidence_names if name.endswith('.xml')]},
               {'scope':'Current full document and adjacent isolated regression', 'result':suite(directory/regression_name), 'evidence':[ref(directory/regression_name)]}])
(out/'workload.json').write_text(json.dumps(work,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
token='d2b584c6ed3b' if coverage_phase else 'fb093547b9ea' if semantic_phase else 'de5bdb227444'
retirement='retire-d2' if coverage_phase else 'retire-fb' if semantic_phase else 'retire-de5'
receipt=root/('backend/test-output/release-gates/neu9-small-native-20261106/'+token+'/receipt.json')
record=json.loads(receipt.read_text(encoding='utf-8'))
plan={'receipt':str(receipt),'image_id':record['image_id'],'resources':record['containers'],
      'state':str(out/('attempt-04/review-rejected-state.json' if coverage_phase else 'attempt-03/review-rejected-state.json' if semantic_phase else 'attempt-02/state.json')),'expected_production_image':work['current_image'],
      'output':str(out/retirement),
      'archive':'F:/CodexOrdner/visualizations/2026/10/09/01a11f88-d6c9-7b63-bec3-26450a86e52c/nis-neu9-small-llm-20261106/'+retirement}
plan_path=out/(retirement+'-plan.json')
if plan_path.exists():
    assert json.loads(plan_path.read_text(encoding='utf-8'))==plan, 'Never replace a bound retirement plan'
else:
    plan_path.write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'source_sha256':source['source_sha256'],'verification_sha256':verification,'files':proof['files']}))
