"""Prepare the ordinary Wizard UI for complete reviewed typed evidence."""
from pathlib import Path

OUT = Path(__file__).parent
REL = 'frontend/src/features/agent/ui/agent-chat-core.tsx'
text = (OUT / 'before' / REL).read_text(encoding='utf-8')


def replace(old, new):
    global text
    assert text.count(old) == 1, (old[:100], text.count(old))
    text = text.replace(old, new)


replace('DOCUMENT_EQUIPMENT_MARKER, documentDeviceQuestions,', 'DOCUMENT_EQUIPMENT_MARKER, documentEvidenceCounts, documentDeviceQuestions,')
replace("  const [documentMinimum, setDocumentMinimum] = useState(false);", "  const [documentMinimum, setDocumentMinimum] = useState(false);\n  const [documentRoles, setDocumentRoles] = useState<{ source: string; project: string; values: Record<string, string> }>({ source: '', project: '', values: {} });")
replace("  function adoptDocumentEquipment() {", "  const activeDocumentRoles = documentRoles.source === documentSourceIdentity && documentRoles.project === projectId ? documentRoles.values : {};\n  function adoptDocumentEquipment() {")
replace('reviewDocumentEquipment(originalTaskSource, currentDocumentProposal, activeDocumentAnswers, documentMinimum)', 'reviewDocumentEquipment(documentSourceIdentity, currentDocumentProposal, activeDocumentAnswers, documentMinimum, activeDocumentRoles)')
replace("  const detectedDomain = useMemo", '''  function reviewedDocumentEvidence() {
    if (!activeDocumentEquipment?.facts) return null;
    const counts = documentEvidenceCounts(activeDocumentEquipment);
    return <section className="agent-cluster-review" aria-label="Übernommene Dokumentbefunde">
      <h3>Quellenbefunde im Wizard</h3>
      <p role="status">{counts.total} Befunde übernommen: {counts.devices} Gerätebefunde, {counts.functions} Funktionsbefunde, {counts.requirements} Anforderungsblöcke mit {counts.requirementIds} Anforderungs-IDs.</p>
      <p>Geräteart, Stückzahl und Funktionszuordnung bleiben offen, soweit die Quelle sie nicht festlegt. Anforderungen und Funktionen bleiben mit ihren vollständigen Quellenbelegen im Auftrag erhalten.</p>
      <details><summary>Übernommene Aussagen und Quellen</summary><ul>{activeDocumentEquipment.facts.map((item, index) => <li key={index} data-document-kind={item.kind} data-document-role={item.role}>
        <strong>{item.name}</strong> · {({ INSTANCE: 'Geräteinstanz', CATEGORY: 'Geräteart', FUNCTION: 'Funktion', REQUIREMENT: 'Anforderung' })[item.kind]}
        {item.quantity !== null && ` · Anzahl ${item.quantity}`}
        {item.source_context?.length ? <p>Kontext: {item.source_context.join(' / ')}</p> : null}
        <blockquote>{item.source_quote}</blockquote>
      </li>)}</ul></details>
    </section>;
  }
  const detectedDomain = useMemo''')
replace('<li key={index}>\n                <strong>{item.name}</strong>', '<li key={index} data-document-kind={item.kind} data-document-role={item.role}>\n                <strong>{item.name}</strong>')
replace("{item.quantity !== null && ' · Anzahl ' + item.quantity}<blockquote>", "{item.quantity !== null && ' · Anzahl ' + item.quantity}{item.source_context?.length ? <p>Kontext: {item.source_context.join(' / ')}</p> : null}<blockquote>")
replace('Geprüfte Gerätebefunde werden mit ihrer Quelle in den Wizard übernommen. Fehlende Stückzahlen beantwortest du im Geräteumfang. Funktionen und Anforderungen bleiben in der vollständigen Originalquelle erhalten; Modelländerungen benötigen weiterhin die normale Prüfung und Freigabe.', 'Geräte, Funktionen und Anforderungen werden als getrennte Quellenbefunde in den Wizard übernommen. Fehlende Gerätearten und Stückzahlen klärst du im Geräteumfang. Modelländerungen benötigen weiterhin die normale Prüfung und Freigabe.')
replace('          {taskFiles.some((file) => file.source === "task") && (', '          {reviewedDocumentEvidence()}\n          {taskFiles.some((file) => file.source === "task") && (')
replace('          {documentQuestions.length > 0 && <section', '          {reviewedDocumentEvidence()}\n          {documentQuestions.length > 0 && <section')
replace('Welche Anzahl ist für jede genannte Geräteart vorgesehen? Eine leere Angabe bleibt offen. NIS erzeugt daraus die Teilnehmer für den normalen Geräte- und Funktionsreview.', 'Wie viele Teilnehmer sollen aus jeder genannten Geräteart in das Kommunikationsmodell aufgenommen werden? Eine leere Angabe bleibt offen. Bei 0 wird kein Teilnehmer daraus erzeugt; der Quellenbefund bleibt erhalten. Geräteart, Anschlüsse und Funktionen werden im normalen Review geprüft.')
replace('<span>{question.label}</span>\n              <input type="number"', '''<span>{question.label}</span>
              {question.source_context?.length ? <small>Kontext: {question.source_context.join(' / ')}</small> : null}
              {question.role === 'OTHER' ? <select aria-label={`Geräteart ${question.label}`} disabled={effectiveBusy} value={activeDocumentRoles[question.id] ?? ''}
                onChange={event => setDocumentRoles({ source: documentSourceIdentity, project: projectId, values: { ...activeDocumentRoles, [question.id]: event.target.value } })}>
                <option value="">Geräteart offen</option><option value="CONTROLLER">Controller</option><option value="GATEWAY">Gateway</option><option value="SENSOR">Sensor</option><option value="ACTUATOR">Aktor</option>
              </select> : null}
              <input type="number"''')
replace('          <h4>{projectName || \'Projektname fehlt\'}</h4>', '          <h4>{projectName || \'Projektname fehlt\'}</h4>\n          {reviewedDocumentEvidence()}')
(OUT / 'staged' / REL).write_text(text, encoding='utf-8')
print('Staged Wizard complete-evidence review prepared; application freeze preserved.')
