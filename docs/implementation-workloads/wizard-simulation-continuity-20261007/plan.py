import hashlib, json, shutil
from pathlib import Path

out = Path(__file__).parent
root = out.parents[2]
files = [
    'frontend/src/features/agent/ui/agent-chat-core.tsx',
    'frontend/src/features/agent/lib/proposal-client.ts',
    'frontend/src/features/agent/ui/engineering-agent-event.tsx',
    'frontend/src/features/simulation/ui/simulation-wizard.tsx',
    'backend/nis/agent/tools/validation.py',
    'backend/nis/agent/tools/wizard_generation.py',
    'backend/nis/workflow/services/service.py',
    'backend/nis/engineering/capacity/service.py',
    'backend/nis/engineering/routing/config_builder.py',
    'backend/nis/engineering/simulation.py',
    'frontend/src/features/agent/lib/proposal-client.test.mjs',
    'frontend/e2e/wizard.spec.ts',
    'frontend/e2e/technology-parameter-review.spec.ts',
    'backend/tests/test_technology_parameter_review.py',
    'backend/tests/test_simulation_parameter_defaults.py',
    'backend/tests/test_workflow.py',
]
work = dict(goal_id=out.name, goal_type='SIMULATION_WIZARD_CONTINUITY', kind='implementation',
    repository=str(root), project_scope='20261007041943709-40764014; all persisted simulation configurations',
    requested_change='Restore the running wizard without a first-step flash or restarting; refresh stale proposal review from saved values. Missing device qualification alone is informational for simulation.',
    modify_code=True, allow_repair=True, unresolved_decisions=[],
    required_outcomes=['wizard_continuity', 'saved_value_precedence', 'simulation_readiness_without_device_qualification', 'production_delivery'],
    validation_requirements=['targeted_regression', 'full_release_gate', 'production_verification'],
    constraints=['Persisted provenance and native TechnologyProfile validation remain authoritative', 'Model/schedule/invalid parameter blockers remain enforced', 'Preserve dirty changes and pending user model review'],
    forbidden_changes=['Product database test fixtures', 'Automatic human approval or model application', 'Invented hardware evidence', 'Foreign technology fallbacks'],
    files_inspected=files, revision_before={}, completion_status='IMPLEMENTING',
    context={'independent_campaign_id':'nis-ea-independent-20260924-run1', 'campaign_passed':False},
    implementation_plan=['Gate wizard display on successful restoration and refresh OUTDATED review without starting or approving.', 'Retain saved user configuration over original prompt rates on continuation.', 'Use the existing provenance-aware scenario resolver for workflow/preflight/runtime; report device qualification separately from native scenario validity.', 'Extend existing regression cases, run the full release gate, deploy the exact tested image and verify the affected live project.'],
    delivery={'decision':'YES', 'authorization':'Standing user AGENTS.md rule', 'target':'NetworkIS localhost:13500'})
for file in files:
    source = root/file
    work['revision_before'][file] = hashlib.sha256(source.read_bytes()).hexdigest()
    target = out/'before'/file
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
(out/'workload.json').write_text(json.dumps(work,indent=2),encoding='utf-8')
(out/'diagnosis.md').write_text('''User requirement: saved simulation configuration must survive returning to the running wizard; missing actual device evidence must not block simulation.\n\nObserved live state: existing run 1dfcae6a-a187-498f-b85b-c9cfb5245f92, step 5 status overview; proposal aa7c0504-1cf4-4d09-b2e8-6ce28f8a2b49 OUTDATED after parameter save. No canonical hardware objects applied.\n\nProduct causes: questionnaire rendered before asynchronous restoration, restoration failures silently ignored; review reload does not refresh OUTDATED findings; parameter artifact and preflight use actual-only proof validation; device-only capacity finding classified REVIEW and therefore blocks simulation; simulation snapshot transport uses actual-only ingress. Saved prompt rate precedence can overwrite later user edits.\n\nScope: operational simulation under stored assumptions; actual hardware capacity, measured timing and safety qualification remain unverified. Missing/invalid configuration, scope, provenance, native schedule and physical/model inconsistencies remain blocking. Existing tests extended, independent campaign state not altered.\n''',encoding='utf-8')
print('Continuity workload planned; existing revisions preserved.')
