"""Prepare source-bound clarification changes without disturbing a live gate."""
from prepare_parser_patch import stage, replace


def specification(text):
    text = "import { documentDeviceQuestions, readReviewedDocumentEquipment } from './document-clarification.ts';\n" + text
    text = replace(text, "  const measurements = sensorMeasurementSelections(text);", "  const measurements = sensorMeasurementSelections(text);\n  const documentEquipment = readReviewedDocumentEquipment(text);")
    text = replace(text, 'Gerätezuordnungen|Geräte-Spezifikationen):', 'Gerätezuordnungen|Geräte-Spezifikationen|Dokument-Geräte):')
    text = replace(text, 'const contexts = new Map<string, { name: string; lines: string[]; declaredType?: string; declaredInterface?: string }>();', 'const contexts = new Map<string, { name: string; lines: string[]; declaredType?: string; declaredInterface?: string; documentEvidence?: Record<string, unknown> }>();')
    anchor = '  // Explicit choices can resolve count-only Sensor1… slots without inventing a function.\n'
    text = replace(text, anchor, '''  // One shared inventory path: native source facts and reviewed quantity
  // answers feed the same contexts, ownership and connection gates as text.
  for (const item of [...(documentEquipment?.devices ?? []), ...(documentEquipment?.answers ?? [])]) {
    const baseName = ('name' in item ? item.name : item.label).replace(/\\s*\\([A-Z][A-Z0-9_-]{1,15}\\)\\s*$/, '');
    for (let index = 0; index < item.quantity; index += 1) {
      const name = item.quantity === 1 ? baseName : `${baseName}${index + 1}`;
      const key = normalized(normalizeHardwareName(name));
      const existing = contexts.get(key);
      contexts.set(key, { name, lines: existing?.lines ?? [item.source_quote],
        documentEvidence: { source_sha256: documentEquipment?.source_sha256 ?? null, source_quote: item.source_quote,
          evidence: 'name' in item ? 'reviewed_native_document_fact' : 'explicit_user_clarification', minimum: item.minimum,
          quantity: item.quantity, device_role: item.role },
        declaredType: ({ CONTROLLER: 'ECU', GATEWAY: 'Gateway', SENSOR: 'SensorController', ACTUATOR: 'ActuatorController' })[item.role] });
    }
  }

''' + anchor)
    text = replace(text, "        ...(explicitConnection ? { connection_source: 'explicit_device_connection' } : {}),\n        ...(functionalOwner", "        ...(entry.documentEvidence ? { document_equipment_evidence: entry.documentEvidence } : {}),\n        ...(explicitConnection ? { connection_source: 'explicit_device_connection' } : {}),\n        ...(functionalOwner")
    start = text.index('    unresolvedInventoryGroups: lines.flatMap(line => {')
    end = text.index('\n    }),', start) + len('\n    }),')
    text = text[:start] + '''    unresolvedInventoryGroups: [...new Map([
      ...documentDeviceQuestions(lines.join('\\n')),
      ...(documentEquipment?.questions ?? []),
    ].map(question => [question.id, question])).values()].flatMap(question => {
      const answer = documentEquipment?.answers.find(item => item.id === question.id);
      if (answer && (!answer.coverage_confirmed || answer.covered_by?.every(reference =>
        documentEquipment?.devices.some(item => item.name === reference)
        || documentEquipment?.answers.some(item => item.id === reference && item.quantity > 0)))) return [];
      const type = question.role === 'SENSOR' ? 'SensorController' : question.role === 'ACTUATOR' ? 'ActuatorController' : question.role === 'GATEWAY' ? 'Gateway' : 'ECU';
      const label = normalized(question.label);
      if (expanded.chains.some(chain => chain.device_type === type && normalized(chain.hardware_name).includes(label))) return [];
      return [`${question.role === 'SENSOR' ? 'Sensorik' : question.role === 'ACTUATOR' ? 'Aktorik' : 'Gerätegruppe'} (${question.label}): Stückzahl und konkrete Teilnehmer fehlen. Bitte die gezielte Dokument-Rückfrage beantworten; Anschlüsse und Funktionszuordnungen bleiben getrennt zu prüfen.`];
    }),''' + text[end:]
    return text


def wizard(text):
    text = replace(text, '"use client";\n', '"use client";\n\nimport { DOCUMENT_EQUIPMENT_MARKER, documentDeviceQuestions, documentReviewSource, reviewDocumentEquipment, type ReviewedDocumentEquipment } from \'@/features/agent/lib/document-clarification\';\n')
    anchor = '  const [acceptedDomainMismatch, setAcceptedDomainMismatch] = useState("");\n'
    text = replace(text, '  const [projectId] = useState(() => readActiveProjectId());\n', '')
    text = replace(text, anchor, '  const [projectId] = useState(() => readActiveProjectId());\n' + anchor)
    text = replace(text, anchor, anchor + '''  const [reviewedDocument, setReviewedDocument] = useState<{ source: string; project: string; equipment: ReviewedDocumentEquipment } | null>(null);
  const [documentAnswers, setDocumentAnswers] = useState<{ source: string; project: string; values: Record<string, string> }>({ source: '', project: '', values: {} });
  const [documentMinimum, setDocumentMinimum] = useState(false);
''')
    text = replace(text, '  const taskSource = `${taskText}\\n${taskFiles.map(formatTaskAttachment).join("\\n")}`;', '''  const originalTaskSource = `${taskText}\\n${taskFiles.map(formatTaskAttachment).join("\\n")}`;
  const documentSourceIdentity = documentReviewSource(originalTaskSource);
  const currentDocumentProposal = documentIntake && documentReviewSource(documentIntake.source) === documentSourceIdentity && documentIntake.project === projectId ? documentIntake.proposal : null;
  const activeDocumentEquipment = reviewedDocument?.source === documentSourceIdentity && reviewedDocument.project === projectId ? reviewedDocument.equipment : null;
  const taskSource = originalTaskSource + (activeDocumentEquipment ? `\\n${DOCUMENT_EQUIPMENT_MARKER}${JSON.stringify(activeDocumentEquipment)}` : '');
  const documentQuestions = documentDeviceQuestions(originalTaskSource, currentDocumentProposal);
  const activeDocumentAnswers = documentAnswers.source === documentSourceIdentity && documentAnswers.project === projectId ? documentAnswers.values : {};
  function adoptDocumentEquipment() {
    try {
      const equipment = reviewDocumentEquipment(originalTaskSource, currentDocumentProposal, activeDocumentAnswers, documentMinimum);
      setReviewedDocument({ source: documentSourceIdentity, project: projectId, equipment });
      setDocumentIntakeError('');
    } catch (error) { setDocumentIntakeError(error instanceof Error ? error.message : 'Dokumentangaben konnten nicht übernommen werden.'); }
  }''')
    text = replace(text, '  const currentDocumentProposal = documentIntake?.source === taskSource && documentIntake.project === projectId ? documentIntake.proposal : null;\n', '')
    text = replace(text, '    const source = taskSource;\n', '    const source = originalTaskSource;\n')
    start = text.index('            <p>Du kannst die Entwurfsidee in der Projektbeschreibung ausarbeiten.')
    end = text.index('          </section>}', start)
    text = text[:start] + '''            <p>Geprüfte Gerätebefunde werden mit ihrer Quelle in den Wizard übernommen. Fehlende Stückzahlen beantwortest du im Geräteumfang. Funktionen und Anforderungen bleiben in der vollständigen Originalquelle erhalten; Modelländerungen benötigen weiterhin die normale Prüfung und Freigabe.</p>
            <button className="button secondary" type="button" disabled={effectiveBusy} onClick={adoptDocumentEquipment}>Geprüfte Dokumentangaben übernehmen</button>
            {activeDocumentEquipment && <p role="status">Dokumentangaben im Wizard übernommen. Offene Rückfragen und Anschlüsse bleiben zu prüfen.</p>}
''' + text[end:]
    anchor = '          {plannedEquipment.unresolvedInventoryGroups.length > 0 && <section'
    pos = text.index(anchor)
    text = text[:pos] + '''          {documentQuestions.length > 0 && <section className="agent-cluster-review" aria-label="Gezielte Dokument-Rückfragen">
            <h3>Geräteangaben gezielt klären</h3>
            <p>Welche Anzahl ist für jede genannte Geräteart vorgesehen? Eine leere Angabe bleibt offen. NIS erzeugt daraus die Teilnehmer für den normalen Geräte- und Funktionsreview.</p>
            <label><input type="checkbox" checked={documentMinimum} disabled={effectiveBusy} onChange={event => setDocumentMinimum(event.target.checked)} /> Angaben sind ein Mindestumfang; zusätzlicher fachlicher Bedarf muss getrennt vorgeschlagen und bestätigt werden.</label>
            {documentQuestions.map(question => <label key={question.id} className="agent-device-choice"><span>{question.label}</span>
              <input type="number" min="0" max="1000" step="1" aria-label={`Anzahl ${question.label}`} disabled={effectiveBusy}
                value={activeDocumentAnswers[question.id] ?? ''} onChange={event => setDocumentAnswers({ source: documentSourceIdentity, project: projectId, values: { ...activeDocumentAnswers, [question.id]: event.target.value } })} />
              <small>Quelle: {question.source_quote}</small></label>)}
            <button className="button secondary" type="button" disabled={effectiveBusy} onClick={adoptDocumentEquipment}>Geprüfte Dokumentangaben übernehmen</button>
            {documentIntakeError && <p role="alert">{documentIntakeError}</p>}
          </section>}
''' + text[pos:]
    # The identical reviewed input travels with the normal confirmed wizard graph.
    text = replace(text, '    const concreteTask = `${confirmedTaskText.trim() || "Aufgabe wurde als Datei uebergeben."}${attachments}`;', '    const concreteTask = `${confirmedTaskText.trim() || "Aufgabe wurde als Datei uebergeben."}${attachments}${activeDocumentEquipment ? `\\n${DOCUMENT_EQUIPMENT_MARKER}${JSON.stringify(activeDocumentEquipment)}` : ""}`;')
    text = replace(text, "{taskText || 'Projektbeschreibung fehlt'}", "{taskText || (taskFiles.length ? `Vollständige Aufgabenquelle: ${taskFiles.map(file => file.name).join(', ')}` : 'Projektbeschreibung fehlt')}")
    text = replace(text, "value={activeDocumentAnswers[question.id] ?? ''} onChange=", "value={activeDocumentAnswers[question.id] === 'covered' ? '' : activeDocumentAnswers[question.id] ?? ''} onChange=")
    text = replace(text, '              <small>Quelle: {question.source_quote}</small></label>)}', '''              {question.covered_by?.length ? <span><input type="checkbox" checked={activeDocumentAnswers[question.id] === 'covered'} disabled={effectiveBusy}
                onChange={event => setDocumentAnswers({ source: documentSourceIdentity, project: projectId, values: { ...activeDocumentAnswers, [question.id]: event.target.checked ? 'covered' : '' } })} />
                Vorhandene Teilnehmer und getrennt beantwortete Gerätegruppen decken diese Übersicht ab: {question.covered_by.map(reference => documentQuestions.find(item => item.id === reference)?.label ?? reference).join(', ')}</span> : null}
              <small>Quelle: {question.source_quote}</small></label>)}''')
    return text


stage('frontend/src/features/agent/lib/engineering-specification.ts', specification)
stage('frontend/src/features/agent/ui/agent-chat-core.tsx', wizard)
