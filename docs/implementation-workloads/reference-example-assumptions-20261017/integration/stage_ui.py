"""Stage reference source roles and native review in the existing wizard."""
from pathlib import Path

STAGED = Path(__file__).parent / 'staged'


def change(relative, transform):
    path = STAGED / relative
    text = path.read_text(encoding='utf-8')
    result = transform(text)
    assert result != text, relative
    path.write_text(result, encoding='utf-8', newline='\n')


def transport(text):
    text = text.replace("type DocumentToolResult = { success: boolean; data?: DocumentIntakeProposal;", "type DocumentToolResult<T> = { success: boolean; data?: T;", 1)
    text = text.replace("export async function readDocumentIntakeResponse(response: Response, onProgress: (text: string) => void): Promise<DocumentIntakeProposal> {\n  let result: DocumentToolResult | undefined;",
        "export async function readDocumentIntakeResponse<T = DocumentIntakeProposal>(response: Response, onProgress: (text: string) => void, maxBytes = 2_000_000): Promise<T> {\n  let result: DocumentToolResult<T> | undefined;", 1)
    text = text.replace('if (bytes > 2_000_000)', 'if (bytes > maxBytes)', 1)
    return text + '''

export type ReferenceSource = {
  id: string; name: string; role: 'REFERENCE_SUPPLEMENT' | 'USER_CLARIFICATION';
  text: string; source_sha256: string;
  allowed_fields: ('quantity' | 'device_type' | 'function_hosts' | 'ports' | 'measurements' | 'commands' | 'communication')[];
};
export type ReferenceDesignRecord = {
  schema_version: 1; design_id: string; revision: number;
  project_id: string; source_sha256: string; request_sha256: string;
  status: 'REVIEW_REQUIRED' | 'ACCEPTED'; canonical_writes: false;
  request: { mode: 'EXAMPLE_PROJECT'; prompt: string; reference_sources: ReferenceSource[]; source_request_id?: string };
  fact_id_map: Record<string, string>;
  proposal: {
    devices: { id: string; name: string; kind: string; quantity: number; rationale: string; owner_device_id?: string | null }[];
    functions: { source_fact_id: string; realization: 'ATOMIC' | 'COMPOSITE'; executor_device_ids: string[]; realized_by_fact_ids: string[]; rationale: string }[];
    ports: { id: string; device_id: string; technology: string; role: string; network_scope: string; parameters: Record<string, unknown>; rationale: string }[];
    measurements: { device_id: string; measurement_id: string; rationale: string }[];
    commands: { device_id: string; definition: Record<string, unknown>; rationale: string }[];
    communication: { id: string; producer_device_id: string; consumer_device_ids: string[]; signal_name: string; rationale: string; encoding: Record<string, unknown> }[];
    functional_dependencies: { id: string; producer_fact_id: string; consumer_fact_ids: string[]; executor_device_id: string; signal_name: string; rationale: string; encoding: Record<string, unknown> }[];
    unresolved: { code: string; target_ref: string; message: string }[];
  };
  decision_evidence: Record<string, unknown>[];
  protected_fields: Record<string, unknown>;
};

export function referenceDesignMarker(record: ReferenceDesignRecord) {
  if (record.status !== 'ACCEPTED' || record.canonical_writes !== false) throw new Error('Referenzannahmen zuerst prüfen und übernehmen.');
  return '- Dokument-Referenzentwurf: ' + JSON.stringify(Object.fromEntries([
    'schema_version', 'design_id', 'revision', 'request_sha256', 'source_sha256', 'status',
    'proposal', 'fact_id_map', 'decision_evidence', 'protected_fields',
  ].map(key => [key, record[key as keyof ReferenceDesignRecord]])));
}
'''


change('frontend/src/features/agent/lib/engineering-agent.ts', transport)


def ui(text):
    text = text.replace("readDocumentIntakeResponse, type DocumentIntakeProposal", "readDocumentIntakeResponse, referenceDesignMarker, type ReferenceDesignRecord, type ReferenceSource, type DocumentIntakeProposal", 1)
    text = text.replace('source: "task" | "architecture";', 'source: "task" | "architecture" | "reference";', 1)
    point = "  const originalTaskSource = "
    start = text.index(point)
    end = text.index('  const documentQuestions', start)
    text = text[:start] + '''  const [referenceExample, setReferenceExample] = useState(false);
  const [referenceClarification, setReferenceClarification] = useState('');
  const [referenceBusy, setReferenceBusy] = useState(false);
  const [referenceProgress, setReferenceProgress] = useState('');
  const [referenceError, setReferenceError] = useState('');
  const [referenceDesign, setReferenceDesign] = useState<{ signature: string; project: string; record: ReferenceDesignRecord } | null>(null);
  const primaryFiles = taskFiles.filter(file => file.source !== 'reference');
  const referenceFiles = taskFiles.filter(file => file.source === 'reference');
  const originalTaskSource = `${taskText}\\n${primaryFiles.map(formatTaskAttachment).join("\\n")}`;
  const documentSourceIdentity = documentRequestSource(taskText, primaryFiles.map(formatTaskAttachment));
  const currentDocumentProposal = documentIntake?.source === documentSourceIdentity && documentIntake.project === projectId ? documentIntake.proposal : null;
  const activeDocumentEquipment = reviewedDocument?.source === documentSourceIdentity && reviewedDocument.project === projectId ? reviewedDocument.equipment : null;
  const sourceTask = originalTaskSource + (activeDocumentEquipment ? `\\n${DOCUMENT_EQUIPMENT_MARKER}${JSON.stringify(activeDocumentEquipment)}` : '');
  const referenceSignature = JSON.stringify([sourceTask, notes, referenceFiles, referenceClarification, referenceExample]);
  const currentReference = referenceExample && referenceDesign?.project === projectId && referenceDesign.signature === referenceSignature ? referenceDesign.record : null;
  const acceptedReference = currentReference?.status === 'ACCEPTED' ? currentReference : null;
  const referenceMarker = acceptedReference ? referenceDesignMarker(acceptedReference) : '';
  const taskSource = sourceTask + (referenceMarker ? '\\n' + referenceMarker : '');
''' + text[end:]
    text = text.replace('busy || submitting || documentIntakeBusy ||', 'busy || submitting || documentIntakeBusy || referenceBusy ||', 1)
    # All inventory/source callers exclude role-scoped reference files.
    text = text.replace('taskFiles.map(formatTaskAttachment)', 'primaryFiles.map(formatTaskAttachment)')
    text = text.replace('taskFiles.map((file) => formatTaskAttachment(file))', 'primaryFiles.map((file) => formatTaskAttachment(file))')
    text = text.replace('taskFiles.map(file => file.name)', 'primaryFiles.map(file => file.name)')
    text = text.replace('const attachments = taskFiles.length', 'const attachments = primaryFiles.length', 1)
    text = text.replace('""}`;\n    const nextRunId', '""}${referenceMarker ? `\\n${referenceMarker}` : ""}`;\n    const nextRunId', 1)
    text = text.replace('${engineeringGenerationMode(confirmedTaskSource)}', "${acceptedReference ? 'EXAMPLE_PROJECT' : engineeringGenerationMode(confirmedTaskSource)}", 1)
    text = text.replace("  const unresolvedDocumentFunctions = documentFunctionFacts.filter", "  const unresolvedDocumentFunctions = acceptedReference ? [] : documentFunctionFacts.filter", 1)
    # Successful typed plan validation replaces literal-source gaps, not
    # technical or workflow validation. Ordinary model proposal gates still run.
    text = text.replace('...(!equipmentOwnershipReady ?', '...(!acceptedReference && !equipmentOwnershipReady ?', 1)
    text = text.replace('...(!equipmentClusterValidationReady ?', '...(!acceptedReference && !equipmentClusterValidationReady ?', 1)
    for key in ['unresolvedConnections', 'unresolvedSensorMeasurements', 'unresolvedCommands']:
        text = text.replace(f'...({key}.length ?', f'...(!acceptedReference && {key}.length ?', 1)
    text = text.replace('  const startBlockers = [', "  const startBlockers = [\n    ...(referenceExample && !acceptedReference ? [{ step: 'project', text: 'Die aktuellen Referenzannahmen vollständig prüfen und übernehmen.' }] : []),", 1)
    point = text.index('  async function handleTaskFiles(')
    text = text[:point] + '''  async function referenceAction(accept = false) {
    if (effectiveBusy || !activeDocumentEquipment || !referenceExample) return;
    const signature = referenceSignature;
    setReferenceBusy(true); setReferenceError('');
    setReferenceProgress(accept ? 'Referenzprüfung wird gespeichert …' : 'Lokaler Qwen plant die vollständigen fachlichen Ketten …');
    try {
      const sha = async (value: string) => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value))), byte => byte.toString(16).padStart(2, '0')).join('');
      const sources: ReferenceSource[] = await Promise.all(referenceFiles.map(async (file, index) => {
        if (!file.content) throw new Error(`${file.name}: Die Referenz muss vollständig als Text gelesen werden.`);
        return { id: 'reference-' + index, name: file.name, role: 'REFERENCE_SUPPLEMENT', text: file.content,
          source_sha256: await sha(file.content), allowed_fields: ['function_hosts', 'ports', 'measurements', 'commands', 'communication'] };
      }));
      if (referenceClarification.trim()) sources.push({ id: 'user-clarification', name: 'Ergänzende Nutzeranforderung', role: 'USER_CLARIFICATION',
        text: referenceClarification, source_sha256: await sha(referenceClarification),
        allowed_fields: ['quantity', 'device_type', 'function_hosts', 'ports', 'measurements', 'commands', 'communication'] });
      if (readActiveProjectId() !== projectId) throw new Error('Das aktive Projekt wurde gewechselt.');
      const sessionResponse = await fetch('/api/engineering/agent/review-session', { cache: 'no-store' });
      if (!sessionResponse.ok) throw new Error('Die Referenzprüfung konnte nicht vorbereitet werden.');
      const session = await sessionResponse.json();
      if (accept && !currentReference) throw new Error('Der aktuelle Referenzentwurf fehlt.');
      const response = await fetch('/api/engineering/agent/document-reference-design' + (accept ? '/accept' : ''), {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'application/x-ndjson', 'X-Project-ID': projectId,
          'X-Human-Review': 'confirmed', 'X-Review-CSRF': session.csrf_token },
        body: JSON.stringify(accept ? { design_id: currentReference!.design_id, revision: currentReference!.revision,
          request_sha256: currentReference!.request_sha256 } : { mode: 'EXAMPLE_PROJECT', prompt: sourceTask + (notes ? '\\n' + notes : ''),
          source_request_id: crypto.randomUUID(), reference_sources: sources }),
      });
      const record = await readDocumentIntakeResponse<ReferenceDesignRecord>(response, setReferenceProgress, 24_000_000);
      if (readActiveProjectId() !== projectId || record.canonical_writes !== false || record.schema_version !== 1
          || record.source_sha256 !== activeDocumentEquipment.source_sha256 || !record.design_id
          || !['REVIEW_REQUIRED', 'ACCEPTED'].includes(record.status)) throw new Error('Die Referenzantwort passt nicht zur aktuellen vollständigen Quelle.');
      setReferenceDesign({ signature, project: projectId, record });
      // No canonical writes here. Starting the ordinary wizard is a separate
      // action and retains validate/review/apply, preflight and simulation.
    } catch (error) { setReferenceError(error instanceof Error ? error.message : 'Die Referenzplanung ist fehlgeschlagen.'); }
    finally { setReferenceBusy(false); }
  }

  function referenceReview() {
    return <section className="agent-cluster-review" aria-label="Beispiel und Referenzannahmen">
      <h3>Beispielprojekt mit Referenzentwurf</h3>
      <label><input type="checkbox" disabled={effectiveBusy} checked={referenceExample} onChange={event => setReferenceExample(event.target.checked)} />
        Fehlende Beispieldaten von NIS als prüfbare Referenzannahmen planen lassen</label>
      {referenceExample && <>
        <p>Die Originalquelle bleibt erhalten. Ergänzende Referenzen bestimmen keine neuen Stückzahlen. Neue Auslegungsdaten bleiben Referenzannahmen, auch nach ihrer Übernahme.</p>
        <label>Ergänzende Nutzeranforderung<textarea aria-label="Ergänzende Nutzeranforderung" rows={3} disabled={effectiveBusy} value={referenceClarification} onChange={event => setReferenceClarification(event.target.value)} /></label>
        <label>Ergänzende Referenzdatei<input aria-label="Ergänzende Referenzdatei" type="file" accept=".txt,.md,.json,.csv" multiple disabled={effectiveBusy}
          onChange={event => { void handleTaskFiles(event.target.files, 'reference'); event.currentTarget.value = ''; }} /></label>
        <ul>{referenceFiles.map(file => <li key={file.name}>{file.name} · {file.content?.length.toLocaleString('de-DE')} Zeichen · nur Funktionszuordnung, Anschlüsse, Messdaten, Befehle und Kommunikation
          <button type="button" disabled={effectiveBusy} onClick={() => setTaskFiles(taskFiles.filter(item => item !== file))}>Referenz entfernen</button></li>)}</ul>
        <button type="button" className="button secondary" disabled={effectiveBusy || !activeDocumentEquipment} onClick={() => void referenceAction()}>NIS-Referenzentwurf mit lokalem Qwen erstellen</button>
        {!activeDocumentEquipment && <p>Die vollständigen Dokumentbefunde zuerst prüfen und übernehmen.</p>}
        {referenceBusy && <p role="status">{referenceProgress}</p>}
        {referenceError && <p role="alert">{referenceError}</p>}
        {currentReference && <>
          <p role="status">{currentReference.status === 'ACCEPTED' ? 'Referenzannahmen übernommen' : 'Referenzannahmen zur Prüfung'} · {currentReference.proposal.devices.length} Teilnehmerentwürfe · {currentReference.proposal.functions.length} Funktionen · {currentReference.proposal.communication.length} Kommunikationsbeziehungen</p>
          <details><summary>Alle Referenzannahmen mit Begründung prüfen</summary>
            <p>Belegart: REFERENCE_ASSUMPTION. Keine bestätigte Hardwareeignung, Verarbeitungsausführung oder funktionale Zeitbewertung.</p>
            <h4>Teilnehmer und Umfang</h4><ul>{currentReference.proposal.devices.map(row => <li key={row.id}>{row.quantity} × {row.name} · {row.kind}: {row.rationale}</li>)}</ul>
            <h4>Funktionszuordnung</h4><ul>{currentReference.proposal.functions.map(row => <li key={row.source_fact_id}>{row.source_fact_id} · {row.realization} · {row.executor_device_ids.join(', ') || row.realized_by_fact_ids.join(', ')}: {row.rationale}</li>)}</ul>
            <h4>Anschlüsse und technische Parameter</h4><ul>{currentReference.proposal.ports.map(row => <li key={row.id}>{row.device_id} · {row.technology} · {row.network_scope}: {JSON.stringify(row.parameters)} · {row.rationale}</li>)}</ul>
            <h4>Messgrößen und Stellbefehle</h4><ul>{currentReference.proposal.measurements.map((row, index) => <li key={'m' + index}>{row.device_id}: {row.measurement_id} · {row.rationale}</li>)}
              {currentReference.proposal.commands.map((row, index) => <li key={'c' + index}>{row.device_id}: {JSON.stringify(row.definition)} · {row.rationale}</li>)}</ul>
            <h4>Daten und Empfänger</h4><ul>{currentReference.proposal.communication.map(row => <li key={row.id}>{row.producer_device_id} → {row.consumer_device_ids.join(', ')} · {row.signal_name}: {JSON.stringify(row.encoding)} · {row.rationale}</li>)}</ul>
            <h4>Logische Daten innerhalb eines Controllers</h4><ul>{currentReference.proposal.functional_dependencies.map(row => <li key={row.id}>{row.producer_fact_id} → {row.consumer_fact_ids.join(', ')} · {row.signal_name} · {row.rationale}</li>)}</ul>
            <details><summary>Vollständiger Entwurf und Herkunft aller Felder</summary><pre>{JSON.stringify(currentReference, null, 2)}</pre></details>
          </details>
          {currentReference.proposal.unresolved.length > 0 && <ul role="alert">{currentReference.proposal.unresolved.map((row, index) => <li key={index}>{row.message}</li>)}</ul>}
          {currentReference.status === 'REVIEW_REQUIRED' && <button type="button" className="button secondary" disabled={effectiveBusy || currentReference.proposal.unresolved.length > 0}
            onClick={() => void referenceAction(true)}>Geprüfte Referenzannahmen übernehmen</button>}
        </>}
      </>}
    </section>;
  }

''' + text[point:]
    text = text.replace('          {documentIntakeBusy && <p role="status">', '          {referenceReview()}\n          {documentIntakeBusy && <p role="status">', 1)
    # A same-name reference cannot silently replace an original attachment.
    text = text.replace('item.name === attachment.name && item.size === attachment.size', 'item.name === attachment.name && item.size === attachment.size && item.source === attachment.source', 1)
    return text


change('frontend/src/features/agent/ui/agent-chat-core.tsx', ui)
