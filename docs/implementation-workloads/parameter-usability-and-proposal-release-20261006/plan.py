import json, hashlib, shutil
from pathlib import Path
OUT = Path(__file__).parent
ROOT = OUT.parents[2]
files = [
 'backend/nis/communication/catalog.py', 'backend/nis/communication/registry.py',
 'backend/nis/agent/tools/proposal_service.py', 'backend/nis/agent/tools/validation.py',
 'backend/nis/interfaces/http/engineering.py',
 'frontend/src/shared/api/types.ts', 'frontend/src/features/communication/lib/technology-parameters.ts',
 'frontend/src/features/communication/lib/technology-parameters.test.mjs',
 'frontend/src/features/simulation/ui/simulation-wizard.tsx',
 'frontend/src/features/workflow/lib/workflow-api.ts',
 'frontend/src/features/agent/lib/proposal-client.ts', 'frontend/src/features/agent/lib/proposal-client.test.mjs',
 'frontend/src/features/agent/ui/engineering-agent-event.tsx',
 'backend/tests/test_simulation_parameter_defaults.py', 'backend/tests/test_technology_parameter_review.py',
 'backend/tests/test_proposal_capacity.py', 'frontend/e2e/technology-parameter-review.spec.ts',
 'backend/tests/test_engineering_mcp.py', 'frontend/src/features/communication/lib/technology-projection.json',
 'frontend/e2e/wizard.spec.ts',
 'backend/nis/engineering/capacity/dimensioning.py',
 'backend/nis/communication/technologies/lin/timing.py',
 'backend/tests/test_bus_rate_planning.py',
 'backend/tests/test_technology_full_parameter_audit.py',
]
work = json.loads((OUT/'workload.json').read_text())
work['files_inspected'] = files
work['revision_before'] = {}
for file in files:
 p = ROOT/file
 work['revision_before'][file] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
 if p.exists():
  target = OUT/'before'/file
  target.parent.mkdir(parents=True, exist_ok=True)
  if not target.exists(): shutil.copyfile(p, target)
evidence = OUT/'diagnosis.md'
evidence.write_text('''# Root causes and coverage

1. User project parameter revision is 4 while canonical model is empty. Proposal has 2114 valid changes and remains VALIDATED. `model_revision()` hashes parameters; `review()` turns it OUTDATED after parameter saves. Actual normal UI review reproduced OUTDATED with no canonical IDs. `get()` does not expose that mismatch before the click; combined client treats non-APPLIED response as success. Owner PROJECT_PRODUCT.
2. Catalog generic string fallback invents `simulation:lin:lin_registered_source` and source/device IDs. These are identity/evidence metadata, not numeric scenario configuration. Keep actual source requirements and unknown identity, never fake evidence. Existing typed-default regression must separately assert metadata has no fabricated value; all operational inputs remain covered.
3. Form groups use schema insertion order, without priority or collapsed details. Conditional help renders compact raw profile prose. Existing parameter editor browser case covers current model only, not an unapplied proposal, stale review, and return after saving. Extend it and existing backend/native default/client tests; no duplicate checker runner/campaign.
4. Parameter review ignores proposal query, reads empty canonical graph instead of pending proposal and therefore cannot highlight those findings. Reuse effective-model validator for pending proposal previews and current canonical validator after apply, retaining revision checks.
5. Full release regression found LIN rate planning relied on invented references making its actual-device estimator appear complete. Keep the actual estimator strict; share its native nominal frame formula with a specialization-owned scenario estimator that accepts only missing identity/source metadata, never missing operational inputs or invalid PHY. Rate-plan results retain hardware_evidence=false and functional_timing_accepted=false. Per-profile schema audit explicitly checks the new value-role projection and UNKNOWN metadata.
6. Final code review found validate() returned a stale APPROVED contract unchanged. Permit renewed validation only when its complete model hash changed, discard obsolete approval authority, and require a new human review. The existing persistence regression now exercises both VALIDATED and APPROVED stale states and rejects both old revisions.

Tool Checker existing registry and persistence cases inspected. Existing campaign REPAIR_1_ACTIVE is unchanged. S10 model_resolves_parameters and existing technology persistence cases only partially cover new UI sequence; focused regression evidence belongs to existing executable test paths, not a new independent registry.
''', encoding='utf-8')
work['repair'].update(root_cause='Parameter saves stale proposal revision but UI hides it and accepts non-applied success; synthetic metadata defaults and unprioritized schema rendering; pending proposal ignored by parameter review.', first_failing_layer='PROJECT_PRODUCT catalog, proposal lifecycle API and UI', evidence=[{'path':str(evidence.resolve()),'sha256':hashlib.sha256(evidence.read_bytes()).hexdigest()}])
work['repair'].update(affected_files=files, acceptance_criteria=work['required_outcomes'], targeted_tests=['test_simulation_parameter_defaults.py', 'test_technology_parameter_review.py', 'test_proposal_capacity.py', 'technology-parameters.test.mjs', 'proposal-client.test.mjs', 'technology-parameter-review.spec.ts'])
work['implementation_plan'] = ['Keep revision gates; expose stale state before approval and require new validation/review, report non-APPLIED outcomes.', 'Separate evidence/identity from operational defaults in existing profile projection; retain explicit user values.', 'Prioritize native rates and common simulation fields, collapse editable details, expand linked findings.', 'Review pending proposal using existing validator; save and return to actual review.', 'Targeted regressions then full release gate, deploy exact image and verify actual project.']
work['completion_status'] = 'IMPLEMENTING'
(OUT/'workload.json').write_text(json.dumps(work, indent=2), encoding='utf-8')
print('planned', len(files), 'files')
