"""Stage focused regressions alongside the frozen source baseline."""
from prepare_parser_patch import stage, replace


def backend_tests(text):
    return text + r'''


@pytest.mark.parametrize('statement', [
    'Sensor- und Aktorfehler erkennen und behandeln.',
    'Das System verarbeitet kontinuierlich Sensordaten und steuert Aktuatoren.',
    'Der Gebäuderegler überwacht die Sensoren und steuert Aktoren.',
    'The robot processes sensor readings and controls actuators.',
])
def test_action_statements_do_not_declare_installed_device_categories(statement):
    from backend.nis.agent.orchestration.project_intake import document_component_policy
    assert document_component_policy(statement) == {'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None}


def test_numbered_architecture_headings_do_not_become_controller_inventory():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    units = document_component_sources(document_source_references('2. Domain-Controller-Design\nController (PDC)'))
    assert len(units) == 1
    assert units[0]['policy'] == {'kind': 'INSTANCE', 'role': 'CONTROLLER', 'quantity': 1}


def test_normative_list_scope_preserves_unnumbered_requirements_across_windows():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    prefix = '5. Anforderungen\nDas System muss\n'
    source = '\nEnergieversorgung für alle Subsysteme sicherstellen.\nSystemzustände überwachen und protokollieren.\n6. Hardware\nRaumcontroller'
    units = document_component_sources(document_source_references(source), scope_prefix=prefix)
    requirements = [unit for unit in units if unit['policy'] and unit['policy']['kind'] == 'REQUIREMENT']
    assert requirements and all(unit['required'] for unit in requirements)
    assert all(any(line in unit['text'] for unit in requirements) for line in source.splitlines()[1:3])
    assert units[-1]['policy']['kind'] == 'CATEGORY'
    assert units[-1]['policy']['role'] == 'CONTROLLER'


def test_functional_partner_aliases_and_direct_sensor_links_are_not_false_protocols():
    from backend.nis.agent.orchestration.project_intake import document_declared_unknown_transports, document_source_references
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    source = 'Chassis Controller (CDC)\nSchnittstellen:\nCDC (Lenk-/Bremsanforderungen)\nDirekte Sensorlinks (GMSL, FPD-Link, GigE)\nEthernet möglich'
    unknown = document_declared_unknown_transports(document_source_references(source), DEFAULT_TECHNOLOGY_REGISTRY.profiles())
    assert set(unknown) == {'GMSL', 'FPD-Link', 'GigE'}


def test_unicode_transport_spelling_has_one_registry_identity_and_merged_fact():
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    from backend.nis.agent.orchestration.project_intake import compose_document_proposal
    assert {DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(name) for name in ['CAN-FD', 'CAN‑FD', 'can_fd']} == {'can_fd'}
    parts = [{'components': [], 'technologies': [{'name': name, 'kind': 'TRANSPORT', 'source_quote': name}]} for name in ['CAN‑FD', 'can_fd']]
    assert len(compose_document_proposal(parts)['technologies']) == 1
'''


def frontend_tests(text):
    text = replace(text, '''  assert.equal(result.unresolvedInventoryGroups.length, 2);
  assert.match(result.unresolvedInventoryGroups[0], /Radar.*Kamera.*Stückzahlen/);
  assert.match(result.unresolvedInventoryGroups[1], /Bremsaktuator.*Lenkaktuator.*Stückzahlen/);''', '''  assert.equal(result.unresolvedInventoryGroups.length, 9);
  for (const member of ['Radar', 'Kamera', 'Lidar', 'Ultraschall', 'IMU', 'Raddrehzahl', 'Bremsaktuator', 'Lenkaktuator', 'Antriebsaktuator']) {
    assert.ok(result.unresolvedInventoryGroups.some(finding => finding.includes(`(${member})`) && finding.includes('Stückzahl')));
  }''')
    return "import { documentDeviceQuestions, reviewDocumentEquipment, documentReviewSource, readReviewedDocumentEquipment } from './document-clarification.ts';\n" + text + r'''

test('document questions transfer each reviewed member, retaining partial gaps and minimum provenance', () => {
  const source = 'Controller: PerceptionUnit\nSensorik (Kamera, IMU, Lidar)\nAktorik (Greifer, Antrieb)';
  const questions = documentDeviceQuestions(source);
  assert.equal(questions.length, 5);
  const camera = questions.find(question => question.label === 'Kamera');
  const equipment = reviewDocumentEquipment(source, null, { [camera.id]: '2' }, true);
  const prompt = `${source}\n- Dokument-Geräte: ${JSON.stringify(equipment)}`;
  const spec = extractEngineeringSpecification(prompt);
  assert.deepEqual(spec.chains.filter(chain => chain.device_type === 'SensorController').map(chain => chain.hardware_name), ['Kamera1', 'Kamera2']);
  assert.equal(spec.unresolvedInventoryGroups.length, 4);
  assert.ok(spec.unresolvedInventoryGroups.some(finding => finding.includes('IMU')));
  assert.ok(spec.unresolvedInventoryGroups.some(finding => finding.includes('Lidar')));
  assert.equal(readReviewedDocumentEquipment(prompt).answers[0].minimum, true);
  assert.ok(spec.chains.filter(chain => chain.device_type === 'SensorController').every(chain => chain.configuration.document_equipment_evidence.minimum === true));
  assert.ok(spec.chains.filter(chain => chain.device_type === 'SensorController').every(chain => chain.interface_type === 'Other'));
  assert.equal(documentReviewSource(prompt), source);
});

test('native reviewed device facts enter the normal inventory without copying proposal prose', () => {
  const source = 'Control Computer (CC)\nSensor types (Camera, IMU)\nFunction: Processing sensor data.';
  const proposal = { source_sha256: 'a'.repeat(64), interpretation: { components: [
    { name: 'Control Computer (CC)', kind: 'INSTANCE', role: 'CONTROLLER', quantity: 1, source_quote: 'Control Computer (CC)' },
    { name: 'Processing sensor data', kind: 'FUNCTION', role: 'OTHER', quantity: null, source_quote: 'Function: Processing sensor data.' },
  ] } };
  const questions = documentDeviceQuestions(source, proposal);
  const equipment = reviewDocumentEquipment(source, proposal, Object.fromEntries(questions.map(question => [question.id, '1'])), true);
  const spec = extractEngineeringSpecification(`${source}\n- Dokument-Geräte: ${JSON.stringify(equipment)}`);
  assert.equal(new Set(spec.chains.filter(chain => isEngineeringControllerDevice(chain.device_type)).map(chain => chain.hardware_name)).size, 1);
  assert.equal(spec.targetCounts.sensors, 2);
  assert.equal(spec.unresolvedInventoryGroups.length, 0);
  assert.ok(!spec.chains.some(chain => chain.hardware_name.includes('Processing')));
});

test('a different sensor never resolves a missing category and forged document citations fail', () => {
  const source = 'Sensor: Temperature1\nSensorik (Kamera, IMU)';
  assert.equal(extractEngineeringSpecification(source).unresolvedInventoryGroups.length, 2);
  const equipment = reviewDocumentEquipment(source, null, {}, false);
  equipment.answers.push({ ...equipment.questions[0], quantity: 1, minimum: false, source_quote: 'Erfundene Quelle' });
  assert.throws(() => extractEngineeringSpecification(`${source}\n- Dokument-Geräte: ${JSON.stringify(equipment)}`), /Unbelegte/);
});
'''


stage('backend/tests/test_qwen_document_intake.py', backend_tests)
stage('frontend/src/features/agent/lib/engineering-specification.test.mjs', frontend_tests)


def browser_test(text):
    text = replace(text, "  await expect(dialog.getByText(/Sensorik \\(Radar, Kamera, Lidar, Ultraschall, IMU, Raddrehzahl\\)/)).toBeVisible();", "  await expect(dialog.getByRole('spinbutton', { name: 'Anzahl Kamera', exact: true })).toHaveValue('');\n  await expect(dialog.getByRole('spinbutton', { name: 'Anzahl IMU', exact: true })).toHaveValue('');")
    text = replace(text, "  await expect(dialog.getByText(/Aktorik \\(Bremsaktuator, Lenkaktuator, Antriebsaktuator\\)/)).toBeVisible();", "  await expect(dialog.getByRole('spinbutton', { name: 'Anzahl Bremsaktuator', exact: true })).toHaveValue('');")
    return text + '''
test('document scope answers enter inventory without hiding unanswered sensor types @parser', async ({ page }) => {
  await page.goto(`/studio/engineering?assistant=project&project=nis-e2e-clarification-${randomUUID()}`);
  const dialog = page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' });
  await dialog.locator('#engineering-project-name').fill('Dokument-Rückfragen');
  await dialog.locator('fieldset.agent-project-name-step input[type=file]').setInputFiles(
    fileURLToPath(new URL('./fixtures/document-intake-vehicle.txt', import.meta.url)));
  await dialog.getByRole('button', { name: '4', exact: true }).click();
  await dialog.getByRole('spinbutton', { name: 'Anzahl Kamera', exact: true }).fill('2');
  await dialog.getByRole('checkbox', { name: /Angaben sind ein Mindestumfang/ }).check();
  await dialog.getByRole('button', { name: 'Geprüfte Dokumentangaben übernehmen', exact: true }).click();
  await expect(dialog.getByRole('spinbutton', { name: 'Sensoren: verbindliche Anzahl', exact: true })).toHaveValue('2');
  await expect(dialog.getByRole('alert', { name: 'Offene Gerätegruppen' })).toContainText('IMU');
  await expect(dialog.getByRole('alert', { name: 'Offene Gerätegruppen' })).toContainText('Radar');
  await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeDisabled();
  await expect(dialog.getByRole('spinbutton', { name: 'Anzahl Kamera', exact: true })).toHaveValue('2');
});
'''


stage('frontend/e2e/document-intake.spec.ts', browser_test)
