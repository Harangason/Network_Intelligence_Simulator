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
parser.add_argument('--phase',choices=['source-reference','source-semantics','function-coverage','inventory-batch','inventory-codec','inventory-context','inventory-cohort','inventory-bindings','inventory-closure'],required=True)
args=parser.parse_args()
semantic_phase=args.phase in {'source-semantics','function-coverage'}
coverage_phase=args.phase=='function-coverage'
directory=out/({'source-reference':'intake-source-reference-repair','source-semantics':'source-semantics-repair','function-coverage':'function-coverage-repair','inventory-batch':'inventory-batch-repair','inventory-codec':'inventory-output-codec-repair','inventory-context':'inventory-context-capacity-repair','inventory-cohort':'inventory-context-capacity-repair/cohort-table-repair','inventory-bindings':'binding-schema-capacity-repair','inventory-closure':'inventory-closure-repair'}[args.phase])
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

if args.phase == 'inventory-closure':
    import xml.etree.ElementTree as ET
    check = next(ET.parse(directory/'green-regression.xml').getroot().iter('testsuite')).attrib
    assert check['failures'] == check['errors'] == check['skipped'] == '0'
    assert work['active_local_regression']['status'] == 'PASS' and work['active_local_regression']['exit_code'] == 0
    native_path = directory/'native-counter-02/result.json'
    native = json.loads(native_path.read_text(encoding='utf8'))
    assert native['status'] == 'PASS' and native['actual_inference_requests'] == 2
    assert native['model'] == 'qwen3.5:9b' and native['schema_public_validation_scoped_merge_preserved']
    assert [(row['mode'], row['new_devices'], row['preserved_existing_devices'], row['final_devices'])
            for row in native['counters']] == [('closed', 0, 3, 3), ('missing-last-instance', 1, 2, 3)]
    reasoner = 'backend/nis/agent/orchestration/local_reasoner.py'
    assert ref(root/reasoner)['sha256'] == native['source_sha256']
    # Compare all application declarations. Only the closure predicate, native
    # schema and the infer instruction/predicate assignment may differ.
    def normalize(tree):
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'LocalEngineeringReasoner')
        plan = next(node for node in cls.body if getattr(node, 'name', None) == 'plan_reference_design')
        infer = next(node for node in ast.walk(plan) if isinstance(node, ast.AsyncFunctionDef) and node.name == 'infer')
        infer.body = [node for node in infer.body if not (isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == 'inventory_closed' for target in node.targets))]
        count = 0
        for node in ast.walk(infer):
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'prompt' for target in node.targets):
                for index, key in enumerate(node.value.keys):
                    if isinstance(key, ast.Constant) and key.value == 'instruction':
                        node.value.values[index] = ast.Constant(value='REVIEWED_SOURCE_STAGE_INSTRUCTION')
                        count += 1
        assert count == 1
        tree.body = [node for node in tree.body if getattr(node, 'name', None) not in {
            '_reference_inventory_closed', '_reference_schema_for_stage'}]
        return ast.dump(tree, include_attributes=False)
    assert normalize(parse(directory/'before'/reasoner)) == normalize(parse(root/reasoner))
    names = [reasoner, 'backend/tests/test_reference_inventory_closure.py',
             str((directory/'probe_native_closure.py').relative_to(root)).replace(chr(92), '/'),
             str((out/'freeze_repair.py').relative_to(root)).replace(chr(92), '/')]
    for name, digest in work['frozen_files'].items():
        if name not in names:
            assert ref(root/name)['sha256'] == digest, name
    assert ref(Path(work['source']['path']))['sha256'] == work['source']['sha256']
    assert len(work['required_outcomes']) == len(work['validation_requirements']) == 7
    before_refs, after_refs, diffs = [], [], []
    for name in names:
        old, new = directory/'before'/name, root/name
        saved = directory/'after'/name
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(new.read_bytes())
        if old.exists(): before_refs.append(ref(old))
        after_refs.append(ref(saved))
        diffs.extend(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True) if old.exists() else [],
            new.read_text(encoding='utf8').splitlines(True), fromfile='before/'+name, tofile='after/'+name))
    (directory/'change.diff').write_text(''.join(diffs), encoding='utf8')
    source = module_at('neu9_closure_manifest', root/'scripts/write-build-info.py').build_manifest()
    verification = module_at('neu9_closure_gate', root/'scripts/run-release-gate.py').verification_manifest()
    for name in names:
        if name not in work['files_changed']: work['files_changed'].append(name)
    proof = {'status': 'FROZEN_LOCAL_AND_NATIVE_COUNTER_PASS_ORIGINAL_PENDING',
        'at': datetime.now(timezone.utc).isoformat(), 'source': source, 'verification_sha256': verification,
        'checks': {'green-regression.xml': check}, 'native_counter': ref(native_path),
        'application_change_scope': ['finite source-inventory closure predicate', 'native schema closure subset', 'matching stage instruction'],
        'all_other_application_ast_identical': True,
        'public_validation_merge_scheduler_context_output_timeout_original_unchanged': True,
        'original_acceptance': False, 'simulation_acceptance': False,
        'files': {name: ref(root/name)['sha256'] for name in work['files_changed']}}
    (directory/'source-scope-proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    for key, values in (('before', before_refs), ('after', after_refs), ('diff', [ref(directory/'change.diff')])):
        work.setdefault(key, []).extend(values)
    work.update(frozen_source=source, frozen_files=proof['files'], frozen_verification_sha256=verification)
    work['tests'].append({'scope': 'Current finite-instance closure plus adjacent inventory and reasoner regression',
        'result': check, 'evidence': [ref(directory/'green-regression.xml')]})
    work['repair']['evidence'].extend([ref(directory/'source-scope-proof.json'), ref(native_path)])
    (out/'workload.json').write_text(json.dumps(work, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    state_path = out/'attempt-11/state.json'
    state = json.loads(state_path.read_text(encoding='utf8'))
    terminal_path = out/'attempt-11/terminal-7711-verified/manifest.json'
    terminal = json.loads(terminal_path.read_text(encoding='utf8'))
    assert state['status'] == terminal['state_status'] == 'NATIVE_PLAN_REFERENCE_FAILED'
    assert terminal['session'] == 7711 and terminal['exit_code'] == 1 and terminal['normal_terminal_result']['success'] is False
    plan = {'receipt': state['receipt'], 'image_id': state['image_id'], 'resources': state['containers'],
        'state': str(state_path), 'terminal_evidence': ref(terminal_path),
        'expected_production_image': work['current_image'], 'output': str(out/'retire-4c4'),
        'archive': 'F:/CodexOrdner/visualizations/2026/10/09/01a11f88-d6c9-7b63-bec3-26450a86e52c/nis-neu9-small-llm-20261106/retire-4c4'}
    plan_path = out/'retire-4c4-plan.json'
    assert not plan_path.exists()
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'source_sha256': source['source_sha256'], 'verification_sha256': verification, 'checks': check}))
    raise SystemExit(0)

if args.phase in {'inventory-context', 'inventory-cohort', 'inventory-bindings'}:
    cohort_phase = args.phase == 'inventory-cohort'
    binding_phase = args.phase == 'inventory-bindings'
    import xml.etree.ElementTree as ET
    checks = {}
    regression_file = 'field-sharing-repair/green-regression.xml' if binding_phase else 'regression-final.xml'
    check_names = (regression_file,) if binding_phase else ('green.xml' if cohort_phase else 'green-confirmed.xml', regression_file)
    for name in check_names:
        result = next(ET.parse(directory/name).getroot().iter('testsuite')).attrib
        assert result['failures'] == result['errors'] == result['skipped'] == '0', (name, result)
        checks[name] = result
    assert work['active_local_regression']['status'] == 'PASS'
    assert work['active_local_regression']['exit_code'] == 0
    native_path = directory/('native-251-qwen-product/result.json' if binding_phase else 'native-nis-cohort-purpose/result.json' if cohort_phase else 'native-nis-inventory/result.json')
    native = json.loads(native_path.read_text(encoding='utf8'))
    assert native['status'] == 'PASS' and native['actual_inference_requests'] == 1
    if binding_phase:
        assert native['existing_devices'] == 251 and native['native_bindings'] == 8 and native['available_facts'] == 16
        assert native['public_validation_scoped_merge_preserved']
        assert native['model'] == 'qwen3.5:9b'
        assert not native['independent_shared_fields_counter'] and not native['plain_selection_counter']
        expansion = json.loads((directory/'field-sharing-repair/independent-expansion-proof.json').read_text(encoding='utf8'))
        assert expansion['status'] == 'PASS' and expansion['expanded_schema_exactly_equal']
        assert expansion['source_sha256'] == native['source_sha256']
    else:
        assert native['native_devices'] == 8 and native['preserved_existing_devices'] == 12
        assert native['packed_context'] and native['schema_and_public_validation_and_scoped_merge']
    if cohort_phase:
        assert native['segmented_tables'] > 0 and native['native_owner_selection']
        assert native['native_owner_selection_basis'] == 'purpose_only_in_complete_context'
    reasoner = 'backend/nis/agent/orchestration/local_reasoner.py'
    new_test = 'backend/tests/test_reference_binding_schema_capacity.py' if binding_phase else 'backend/tests/test_reference_inventory_context_capacity.py'
    extra_files = (['backend/tests/test_reference_planning_throughput.py',
                    'backend/tests/test_reference_context_delta_capacity.py',
                    str((out/'inventory-output-codec-repair/probe_native_codec.py').relative_to(root)).replace('\\', '/')]
                   if cohort_phase else [])
    if binding_phase:
        extra_files = ['backend/tests/test_reference_reasoner.py',
            *[str(path.relative_to(root)).replace('\\', '/') for path in (
                directory/'probe_native_bindings.py', out/'read_provider.py', out/'initialize.py',
                out/'verify_isolation.py', out/'human-small-model-decision-20261107.json')]]
    changed_nodes = ({'_reference_schema_for_stage'} if binding_phase else
                     {'_reference_context_messages', *({'_reference_context_snapshot'} if cohort_phase else set())})
    assert ref(root/reasoner)['sha256'] == native['source_sha256' if binding_phase else 'source_code_sha256']
    def protected(tree):
        return ast.dump(ast.Module(body=[node for node in tree.body
            if getattr(node, 'name', None) not in changed_nodes], type_ignores=[]), include_attributes=False)
    assert protected(parse(directory/'before'/reasoner)) == protected(parse(root/reasoner))
    for name, digest in work['frozen_files'].items():
        if name not in {reasoner, new_test, *extra_files}:
            assert ref(root/name)['sha256'] == digest, name
    assert ref(Path(work['source']['path']))['sha256'] == work['source']['sha256']
    assert len(work['required_outcomes']) == len(work['validation_requirements']) == 7
    before_refs, after_refs, diff = [], [], []
    operator = str((out/'freeze_repair.py').relative_to(root)).replace('\\', '/')
    for name in (reasoner, new_test, *extra_files, operator):
        old, new = directory/'before'/name, root/name
        target = directory/'after'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(new.read_bytes())
        if old.exists(): before_refs.append(ref(old))
        after_refs.append(ref(target))
        diff.extend(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True) if old.exists() else [],
                    new.read_text(encoding='utf8').splitlines(True), fromfile='before/'+name, tofile='after/'+name))
    (directory/'change.diff').write_text(''.join(diff), encoding='utf8')
    source = module_at('neu9_context_manifest', root/'scripts/write-build-info.py').build_manifest()
    verification = module_at('neu9_context_gate', root/'scripts/run-release-gate.py').verification_manifest()
    for name in (new_test, *extra_files):
        if name not in work['files_changed']: work['files_changed'].append(name)
    proof = {'at': datetime.now(timezone.utc).isoformat(),
        'status': 'FROZEN_LOCAL_AND_NATIVE_NIS_INVENTORY_CHECKED_ORIGINAL_PENDING',
        'source': source, 'verification_sha256': verification, 'checks': checks,
        'native_counter': ref(native_path), 'changed_application_nodes': sorted(changed_nodes),
        'all_other_functions_and_classes_identical': True,
        'context_output_timeout_public_validation_merge_and_original_source_unchanged': True,
        'native_semantic_selection_diagnostics': ref(out/'inventory-context-capacity-repair/native-selection-diagnostic-summary.json'),
        'remaining_findings': work.get('remaining_findings', []),
        'qualification': ('Native qwen3.5:9b counter on251 existing authored devices/16facts/eight bindings PASS. Current field-sharing regression is separate from earlier648PASS range-only baseline. Earlier llama8B semantic selection FAIL and externally interrupted control remain preserved, not accepted. ' if binding_phase else 'Normal NIS inventory counter and unforced existing-owner selection from segmented context PASS. ' if cohort_phase else 'Normal constrained NIS inventory counter PASS. ') + 'Earlier unconstrained semantic selection FAIL also on raw baseline; not represented as comprehensively repaired or accepted. Full ordinary Original and simulation gates remain mandatory.',
        'original_acceptance': False, 'simulation_acceptance': False,
        'files': {name: ref(root/name)['sha256'] for name in work['files_changed']}}
    (directory/'source-scope-proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    for key, values in (('before', before_refs), ('after', after_refs), ('diff', [ref(directory/'change.diff')])):
        work.setdefault(key, []).extend(values)
    work.update(frozen_source=source, frozen_files=proof['files'], frozen_verification_sha256=verification)
    work['tests'].append({'scope': 'Current-source binding-schema/source-binding/throughput/field-scope/reasoner regression' if binding_phase else 'Current-source combined reference/inventory/context/source/intake/cancellation regression',
        'result': checks[regression_file], 'evidence': [ref(directory/regression_file)]})
    work['repair']['evidence'].extend([ref(directory/'source-scope-proof.json'), ref(native_path)])
    (out/'workload.json').write_text(json.dumps(work, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    state_path = out/('attempt-10/state.json' if binding_phase else 'attempt-08/state.json' if cohort_phase else 'attempt-07/state.json')
    state = json.loads(state_path.read_text(encoding='utf8'))
    assert state['status'] == 'NATIVE_PLAN_REFERENCE_FAILED'
    terminal_path = out/('attempt-10/terminal-22291-verified/manifest.json' if binding_phase else 'attempt-08/terminal-49354-verified/manifest.json' if cohort_phase else 'attempt-07/terminal-86039-verified/manifest.json')
    terminal = json.loads(terminal_path.read_text(encoding='utf8'))
    assert terminal['exit_code'] == 1 and terminal['session'] == (22291 if binding_phase else 49354 if cohort_phase else 86039)
    if cohort_phase or binding_phase:
        assert terminal['normal_terminal_result']['success'] is False
        assert terminal['state_status'] == state['status']
    else:
        assert terminal['classification'] == 'NATIVE_TERMINAL_CONTEXT_BOUND_FAILURE_NOT_CANCELLATION'
    retire_name = 'retire-cbb' if binding_phase else 'retire-c069' if cohort_phase else 'retire-74c6'
    plan = {'receipt': state['receipt'], 'image_id': state['image_id'], 'resources': state['containers'],
        'state': str(state_path), 'terminal_evidence': ref(terminal_path),
        'expected_production_image': work['current_image'], 'output': str(out/retire_name),
        'archive': 'F:/CodexOrdner/visualizations/2026/10/09/01a11f88-d6c9-7b63-bec3-26450a86e52c/nis-neu9-small-llm-20261106/' + retire_name}
    plan_path = out/(retire_name+'-plan.json')
    assert not plan_path.exists()
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'source_sha256': source['source_sha256'], 'verification_sha256': verification, 'checks': checks}))
    raise SystemExit(0)

if args.phase in {'inventory-batch', 'inventory-codec'}:
    codec_phase = args.phase == 'inventory-codec'
    import xml.etree.ElementTree as ET
    checks = {}
    for name in (('green.xml', 'regression-final.xml') if codec_phase else ('green.xml', 'progress-types-green.xml', 'regression-final.xml')):
        result = next(ET.parse(directory/name).getroot().iter('testsuite')).attrib
        assert result['failures'] == result['errors'] == result['skipped'] == '0', (name,result)
        checks[name] = result
    native = json.loads((directory/'native-grammar/result.json').read_text(encoding='utf8'))
    assert native['status'] == 'PASS' and native['actual_inference_requests'] == 1 and native['native_devices'] == 8
    reasoner = 'backend/nis/agent/orchestration/local_reasoner.py'
    assert ref(root/reasoner)['sha256'] == native['source_code_sha256']
    changed = [reasoner, 'backend/nis/agent/orchestration/project_intake.py',
               'backend/tests/test_reference_reasoner.py', 'backend/tests/test_reference_inventory_batch.py']
    # Compare every existing declaration outside the deliberately affected layer.
    exclusions = {
        reasoner: {'_REFERENCE_SOURCE_INVENTORY_BATCH', '_reference_inventory_batch_names',
                   '_reference_schema_for_stage', '_reference_expand_inventory_bindings',
                   '_reference_expand_inventory_choices', '_reference_scoped_inventory_delta'},
        changed[1]: {'_DOCUMENT_TYPE_GROUP_LABEL', 'document_component_policy',
                     'validate_document_interpretation', 'reference_inventory_members'},
        changed[2]: {'reasoner_with_transport'},
    }
    if codec_phase:
        changed = [reasoner, 'backend/tests/test_reference_reasoner.py', 'backend/tests/test_reference_inventory_codec.py']
        exclusions = {reasoner: {'_reference_compact_inventory_schema', '_reference_expand_inventory_choices'},
                      changed[1]: {'reasoner_with_transport'}}
    def protected_ast(path, excluded, strip_plan=False):
        tree = parse(path)
        selected = []
        for node in tree.body:
            names = {getattr(node,'name',None)}
            if isinstance(node,ast.Assign): names |= {t.id for t in node.targets if isinstance(t,ast.Name)}
            if names & excluded: continue
            if strip_plan and isinstance(node,ast.ClassDef) and node.name == 'LocalEngineeringReasoner':
                node.body = [m for m in node.body if getattr(m,'name',None) != 'plan_reference_design']
            selected.append(node)
        return ast.dump(ast.Module(body=selected,type_ignores=[]),include_attributes=False)
    for name, excluded in exclusions.items():
        assert protected_ast(directory/'before'/name,excluded,name==reasoner) == protected_ast(root/name,excluded,name==reasoner), name
    assertion_file = 'backend/tests/test_reference_reasoner.py'
    assert [ast.dump(node,include_attributes=False) for node in ast.walk(parse(directory/'before'/assertion_file)) if isinstance(node,ast.Assert)] == [
        ast.dump(node,include_attributes=False) for node in ast.walk(parse(root/assertion_file)) if isinstance(node,ast.Assert)]
    for name,digest in work['frozen_files'].items():
        if name not in changed: assert ref(root/name)['sha256'] == digest, name
    assert ref(Path(work['source']['path']))['sha256'] == work['source']['sha256']
    before_refs,after_refs,diff=[],[],[]
    operator_names = [str((out/name).relative_to(root)).replace('\\','/') for name in ('retire_dd9.py','freeze_repair.py')]
    for name in [*changed,*operator_names]:
        old,new=directory/'before'/name,root/name
        target=directory/'after'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(new.read_bytes())
        if old.exists(): before_refs.append(ref(old))
        after_refs.append(ref(target))
        diff.extend(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True) if old.exists() else [],
                    new.read_text(encoding='utf8').splitlines(True),fromfile='before/'+name,tofile='after/'+name))
    (directory/'change.diff').write_text(''.join(diff),encoding='utf8')
    source=module_at('neu9_batch_manifest',root/'scripts/write-build-info.py').build_manifest()
    verification=module_at('neu9_batch_gate',root/'scripts/run-release-gate.py').verification_manifest()
    proof={'at':datetime.now(timezone.utc).isoformat(),'status':'FROZEN_AFTER_LOCAL_AND_NATIVE_COUNTER_GREEN',
           'source':source,'verification_sha256':verification,'checks':checks,'native_counter':ref(directory/'native-grammar/result.json'),
           'unchanged_reasoner_context_output_timeout_intake_and_next_ast':True,'all_existing_reference_test_assertions_ast_unchanged':True,
           'intake_change':None if codec_phase else 'Explicit type-list role policy; identical shared label grammar in member extraction and required-group validation.',
           'private_codec_change':'Exact named NEW-slot schema constants omitted and restored before unchanged public validation; native ownership/purpose preserved.' if codec_phase else None,
           'original_source_unchanged':True,'original_acceptance':False,'simulation_acceptance':False,
           'files':{name:ref(root/name)['sha256'] for name in work['files_changed']}}
    (directory/'source-scope-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for key,values in (('before',before_refs),('after',after_refs),('diff',[ref(directory/'change.diff')])):
        work.setdefault(key,[]).extend(values)
    work.update(frozen_source=source,frozen_files=proof['files'],frozen_verification_sha256=verification)
    work['active_local_regression'].update(status='PASS',exit_code=0)
    work['tests'].append({'scope':'Final combined document, reference, inventory, context and cancellation regression',
                          'result':checks['regression-final.xml'],'evidence':[ref(directory/'regression-final.xml')]})
    work['repair']['evidence'].extend([ref(directory/'source-scope-proof.json'),ref(directory/'native-grammar/result.json')])
    (out/'workload.json').write_text(json.dumps(work,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    attempt = 'attempt-06' if codec_phase else 'attempt-05'
    retirement = 'retire-8e4b' if codec_phase else 'retire-3459'
    state_path=out/attempt/'state.json'; state=json.loads(state_path.read_text(encoding='utf8'))
    canceled=out/attempt/('cancellation-72009.json' if codec_phase else 'cancellation-6618.json')
    assert json.loads(canceled.read_text(encoding='utf8'))['server_generation']['status']=='CANCELED'
    state.update(status='OPERATOR_VERIFIED_REFERENCE_CANCELED',operator_terminal_evidence=ref(canceled))
    operator_state=out/attempt/'canceled-state.json'
    assert not operator_state.exists();operator_state.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    receipt_path=Path(state['receipt']);receipt=json.loads(receipt_path.read_text(encoding='utf8'))
    plan={'receipt':str(receipt_path),'image_id':state['image_id'],'resources':state['containers'],
          'state':str(operator_state),'cancellation_evidence':ref(canceled),'expected_production_image':work['current_image'],
          'output':str(out/retirement),
          'archive':'F:/CodexOrdner/visualizations/2026/10/09/01a11f88-d6c9-7b63-bec3-26450a86e52c/nis-neu9-small-llm-20261106/'+retirement}
    plan_path=out/(retirement+'-plan.json');assert not plan_path.exists()
    plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'source_sha256':source['source_sha256'],'verification_sha256':verification,'checks':checks}))
    raise SystemExit(0)

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
