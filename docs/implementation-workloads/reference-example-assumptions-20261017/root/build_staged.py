"""Materialize the owned patch under the workload without changing app source."""
from pathlib import Path


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
RELATIVE = Path('backend/nis/agent/orchestration/project_intake.py')
before_bytes = (ROOT / RELATIVE).read_bytes()
before = before_bytes.decode('utf-8')
newline = '\r\n' if '\r\n' in before else '\n'
signature = 'def reviewed_document_evidence(prompt: str):'
assert before.count(signature) == 1
after = before.replace(signature, 'def reviewed_document_evidence(prompt: str, *, include_source: bool = False):')
generic_chapter = (r'(?:(?:Systemverhalten|Systemanforderungen|Kommunikationsarchitektur|Zusammenfassung|Schnittstellen und Daten|Interfaces and Data|System behavior|System requirements|Communication architecture|Summary)'
    r'|(?:(?:Erweiterte|Extended)\s+)?(?:Safety|Cybersecurity|ADAS|Sensorfusion)(?:[- /]*(?:und|and|&)?[- /]*(?:Safety|Cybersecurity|ADAS|Sensorfusion))*[- ]+(?:Anforderungen|Requirements)'
    r'|Safety,\s*Security,\s*(?:Qualität|Quality)\s*(?:und|and)\s*(?:Betrieb|Operations?)'
    r'|Diagnose\s*(?:&|und|and)\s*OTA)(?:\s*\([^()\r\n]*\))?')
scope_signature = 'def document_system_scope(context: list[str]) -> list[str]:'
assert after.count(scope_signature) == 1
after = after.replace(scope_signature, '_DOCUMENT_GENERIC_SYSTEM_CHAPTER = ' + repr(generic_chapter) + newline + newline + newline + scope_signature)
scope_needle = "        if re.fullmatch(r'(?:Systemstruktur"
assert after.count(scope_needle) == 1
after = after.replace(scope_needle, ("        if re.fullmatch(_DOCUMENT_GENERIC_SYSTEM_CHAPTER, title, re.I):\n            return context[:index]\n").replace('\n', newline) + scope_needle)
(OUT / 'generic-system-chapter-pattern.json').write_text(__import__('json').dumps({'pattern':generic_chapter},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
needle = ("'source_sha256': digest, 'source_chars': len(source),\n            'components': interpretation['components']").replace('\n', newline)
assert after.count(needle) == 1
after = after.replace(needle, ("'source_sha256': digest, 'source_chars': len(source),\n            **({'source_text': source} if include_source else {}),\n            'components': interpretation['components']").replace('\n', newline))
after += (OUT / 'reference-contract.fragment.py').read_text(encoding='utf-8').replace('\n', newline)
for directory, text in [('before', before), ('staged', after)]:
    target = OUT / directory / RELATIVE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(text.encode('utf-8'))
compile(after, str(OUT / 'staged' / RELATIVE), 'exec')
frontend_file = Path('frontend/src/features/agent/lib/actuator-commands.ts')
raw = (ROOT / frontend_file).read_bytes()
original = raw.decode('utf-8')
start = original.index('export function proposedActuatorCommand(')
end = original.index('\nexport function unresolvedActuatorCommands(', start)
replacement = (OUT / 'actuator-semantics.fragment.ts').read_text(encoding='utf-8').rstrip() + '\n'
candidate = original[:start] + replacement + original[end:]
for directory, content in [('before', raw), ('staged', candidate.encode('utf-8'))]:
    target = OUT / directory / frontend_file
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
tests_file = Path('frontend/src/features/agent/lib/device-proposals.test.mjs')
raw = (ROOT / tests_file).read_bytes()
original = raw.decode('utf-8')
needle = "assert.equal(proposedActuatorCommand('Linearantriebe1')?.choice, 'POSITION');"
assert original.count(needle) == 1
candidate = original.replace(needle, "assert.equal(proposedActuatorCommand('Linearantriebe1', 'Stellposition 0–100 %')?.choice, 'POSITION');")
candidate += '''
test('drive names do not substitute a position preset for unspecified or different command quantities', () => {
  for (const name of ['Antriebs ', 'Antriebsmotor', 'Motor', 'Servo', 'Linearantriebe1', 'MotionActuator', 'Luefter', 'Fan', 'Steering'])
    assert.equal(proposedActuatorCommand(name), null, name);
  for (const purpose of ['Drehmomentanforderung', 'Requested torque in Nm', 'Drehzahlsollwert', 'Rotational speed in rpm'])
    assert.equal(proposedActuatorCommand('Positionsantrieb', purpose), null, purpose);
  assert.equal(proposedActuatorCommand('Servomotor', 'Position in Grad von -90 bis 90'), null);
});

test('relative position evidence and explicit generic presets remain reviewable candidates', () => {
  assert.equal(proposedActuatorCommand('Servo', 'Stellposition 0–100 %')?.choice, 'POSITION');
  assert.equal(proposedActuatorCommand('Servo', 'Relative position in percent')?.choice, 'POSITION');
  assert.equal(proposedActuatorCommand('Antrieb', 'Position 0..100 %')?.choice, 'POSITION');
  assert.equal(proposedActuatorCommand('SystemStellglied')?.choice, 'POSITION');
  assert.equal(proposedActuatorCommand('SystemSchaltausgang')?.choice, 'OPEN_CLOSE');
});
'''
for directory, content in [('before', raw), ('staged', candidate.encode('utf-8'))]:
    target = OUT / directory / tests_file
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
# Execution-only import projection. The deliverable tests retain their normal
# relative imports; this view tests the staged helper against the real existing
# transport helper without overlaying or changing application source.
run_dir = OUT / 'staged-run'
run_dir.mkdir(exist_ok=True)
helper_url = (OUT / 'staged' / frontend_file).as_uri()
connection_url = (ROOT / 'frontend/src/features/agent/lib/device-connections.ts').as_uri()
(run_dir / tests_file.name).write_text(candidate.replace("'./device-connections.ts'", repr(connection_url))
    .replace("'./actuator-commands.ts'", repr(helper_url)), encoding='utf-8')
legacy = (ROOT / 'frontend/src/features/agent/lib/actuator-commands.test.mjs').read_text(encoding='utf-8')
(run_dir / 'actuator-existing.test.mjs').write_text(legacy.replace("'./actuator-commands.ts'", repr(helper_url)), encoding='utf-8')
print('Owned source and semantic patch staged; canonical files untouched.')

# These two integration files were explicitly handed over by the peer. Capture
# their staging baseline once; do not overwrite subsequent owned adapter work.
integration = OUT.parent / 'integration/staged'
handed = OUT / 'handoff'
for rel in [Path('frontend/src/features/agent/lib/engineering-specification.ts'),
            Path('frontend/scripts/extract-wizard-specification.mjs')]:
    source = handed / rel
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes((integration / rel).read_bytes())
    canonical_before = OUT / 'before' / rel
    canonical_before.parent.mkdir(parents=True, exist_ok=True)
    canonical_before.write_bytes((ROOT / rel).read_bytes())
spec_file = Path('frontend/src/features/agent/lib/engineering-specification.ts')
candidate = (handed / spec_file).read_text(encoding='utf-8')
candidate = candidate.replace('documentParticipantName, readReviewedDocumentEquipment', 'documentParticipantName, documentFactIdentity, readReviewedDocumentEquipment')
candidate = "import technologyProjection from '../../communication/lib/technology-projection.json' with { type: 'json' };\n" + candidate
candidate = candidate.replace('  byte_order: "little_endian";', '  byte_order: "little_endian" | "big_endian";')
candidate = candidate.replace('  data_type: "signed" | "unsigned";', '  data_type: "signed" | "unsigned" | "float" | "double" | "float32" | "float64";')
candidate = candidate.replace('dataType?: "signed" | "unsigned";', 'dataType?: ExtractedEngineeringChain["data_type"];')
candidate = candidate.replace('dataType: "signed" | "unsigned";', 'dataType: ExtractedEngineeringChain["data_type"];')
candidate = candidate.replace('byteOrder: "little_endian";', 'byteOrder: ExtractedEngineeringChain["byte_order"];')
candidate = candidate.replace('  unresolvedInventoryGroups: string[];\n', '  unresolvedInventoryGroups: string[];\n  reference_design?: Record<string, unknown>;\n')
needle = '  const documentEquipment = readReviewedDocumentEquipment(text);'
assert candidate.count(needle) == 1
candidate = candidate.replace(needle, '  const reference = readDocumentReferenceDesign(text);\n  if (reference) return extractReferenceDesignSpecification(text, reference, overrides, domainOverride);\n' + needle)
for needle in [
    "  if (domain !== \"automotive\") return chains;",
    '  return chains.flatMap((chain) => {',
    "  if (domain === 'automotive') return addAutomotiveFunctionOutputs",
    '  const packed = chains.map((chain) => ({ ...chain, function_name:',
]:
    assert needle in candidate
    candidate = candidate.replace(needle, '  if (chains.some(isReferenceDesignChain)) return chains;\n' + needle, 1)
for signature in ['export function reconcileConfirmedGraphDevices(spec: ExtractedEngineeringSpecification, prompt: string) {',
                  'export function applyConfirmedClusterGraph(chains: ExtractedEngineeringChain[], prompt: string) {']:
    assert signature in candidate
    guard = '  if (spec.reference_design) return spec.chains;' if 'reconcile' in signature else '  if (chains.some(isReferenceDesignChain)) return chains;'
    candidate = candidate.replace(signature, signature + '\n' + guard)
candidate += (OUT / 'reference-adapter.fragment.ts').read_text(encoding='utf-8')
target = OUT / 'staged' / spec_file
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(candidate, encoding='utf-8')
bridge_file = Path('frontend/scripts/extract-wizard-specification.mjs')
bridge = (handed / bridge_file).read_text(encoding='utf-8')
bridge = bridge.replace('completeFunctionalDeviceDesign, usesFunctionalDeviceDesign }', 'completeFunctionalDeviceDesign, usesFunctionalDeviceDesign, OBJECT_LIST_SCHEMA }')
bridge = bridge.replace('    actuator_commands: ACTUATOR_COMMANDS,', '    actuator_commands: ACTUATOR_COMMANDS, object_list_schema: OBJECT_LIST_SCHEMA,')
bridge = bridge.replace("} else {\nif (operation !== undefined)", "} else if (specification.reference_design) {\n  process.stdout.write(JSON.stringify(specification));\n} else {\nif (operation !== undefined)")
target = OUT / 'staged' / bridge_file
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(bridge, encoding='utf-8')
print('Handed-over canonical-plan adapter staged; application source still unchanged.')
