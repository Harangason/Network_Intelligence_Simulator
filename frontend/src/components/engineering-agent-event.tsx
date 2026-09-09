"use client";

import { useEffect, useState } from "react";
import type { EngineeringAgentEvent, EngineeringProposal } from "@/lib/agent/engineering-agent";
import { publishEngineeringModelChanged } from "@/lib/engineering-events";
import { WorkloadProgress } from "./workload-progress";
import type { AgentInput, InteractiveQuestion } from "@/lib/agent/agent-response";
import { engineeringContextHref, readAssistantContext } from "@/lib/agent/assistant-context";
import { readConversation } from '@/lib/agent/conversation-client';
import { applyReviewedProposal, approveAndApplyWizardProposal, refreshProposal } from '@/lib/agent/proposal-client';

function LazyDetails({ title, children }: { title: string; children: () => React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return <details onToggle={event => setOpen(event.currentTarget.open)}><summary>{title}</summary>{open && children()}</details>;
}

function ContextLinks({ refs, projectId }: { refs: Record<string, string>[]; projectId: string }) {
  const links = (items: Record<string, string>[]) => items.map((ref, i) => {
    const href = engineeringContextHref(ref, projectId);
    return href ? <a key={i} href={href}>{ref.name ?? ref.label ?? ref.object_type}{ref.id && !ref.name ? ` · ${ref.id.slice(0, 8)}` : ""}</a> : <span key={i}>{ref.name ?? ref.object_type}</span>;
  });
  return <nav className="engineering-context-links" aria-label="Betroffene Modellobjekte">{links(refs.slice(0, 3))}{refs.length > 3 && <LazyDetails title={`${refs.length - 3} weitere Objekte`}>{() => links(refs.slice(3))}</LazyDetails>}</nav>;
}

const statusLabels: Record<string, string> = {
  PROPOSED: "Vorschlag", VALIDATED: "Geprüft · Freigabe offen", APPROVED: "Freigegeben · Übernahme offen",
  APPLIED: "Übernommen", REJECTED: "Abgelehnt", OUTDATED: "Modellstand geändert · erneut prüfen",
};

function Value({ value, references = {} }: { value: unknown; references?: Record<string, string> }) {
  if (Array.isArray(value)) return <ul>{value.map((item, index) => <li key={index}><Value value={item} references={references} /></li>)}</ul>;
  if (value && typeof value === "object") return <dl>{Object.entries(value).map(([key, item]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd><Value value={item} references={references} /></dd></div>)}</dl>;
  return <span>{value == null ? "—" : (references[String(value)] ?? String(value))}</span>;
}

function ProposalReview({ initial, projectId, wizardReview = false }: { initial: EngineeringProposal; projectId: string; wizardReview?: boolean }) {
  const [proposal, setProposal] = useState(initial);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [names, setNames] = useState<Record<string, string>>({});
  const [rationale, setRationale] = useState(initial.rationale);
  const base = `/api/engineering/agent/proposals/${encodeURIComponent(proposal.proposal_id)}`;
  useEffect(() => {
    if (busy) return;
    const controller = new AbortController();
    const refresh = () => refreshProposal(proposal, projectId, controller.signal)
      .then(result => { if (!controller.signal.aborted) { setProposal(result); setLoaded(true); if (result.status === "APPLIED") setError(""); } })
      .catch(() => {});
    void refresh();
    const timer = window.setInterval(() => { if (document.visibilityState === "visible") void refresh(); }, 5000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [base, projectId, busy, proposal.revision]);
  async function action(kind: "approve" | "approveApply" | "reject" | "apply" | "validate" | "revise") {
    setBusy(true); setError("");
    try {
      const session = await fetch("/api/engineering/agent/review-session", { cache: "no-store" });
      if (!session.ok) throw new Error("Review-Sitzung konnte nicht geöffnet werden.");
      const { csrf_token } = await session.json();
      if (kind === "apply" || kind === "approveApply") {
        const persisted = kind === "approveApply"
          ? await approveAndApplyWizardProposal(proposal, projectId, csrf_token)
          : await applyReviewedProposal(proposal, projectId, csrf_token);
        setProposal(persisted);
        setEditing(false);
        if (persisted.status === "APPLIED") {
          window.dispatchEvent(new Event("engineering:write-completed"));
          publishEngineeringModelChanged({ resource: "hardware-nodes", id: persisted.proposal_id, name: "Engineering-Vorschlag" });
        }
        return;
      }
      const actionPath = kind === "validate" || kind === "revise" ? kind : "review";
      const response = await fetch(`${base}/${actionPath}`, {
        method: "POST", headers: { "Content-Type": "application/json", "X-Project-ID": projectId,
          "X-Review-CSRF": csrf_token, "X-Human-Review": "confirmed" },
        body: JSON.stringify({ decision: kind, revision: proposal.revision, ...(kind === 'revise' ? { names, rationale } : {}) }),
      });
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.error ?? result.findings?.[0]?.message ?? "Aktion fehlgeschlagen.");
      setProposal(current => ({ ...current, ...result.data }));
      setEditing(false);
      if (result.data.status === "APPLIED") {
        window.dispatchEvent(new Event("engineering:write-completed"));
        publishEngineeringModelChanged({ resource: "hardware-nodes", id: proposal.proposal_id, name: "Engineering-Vorschlag" });
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Aktion fehlgeschlagen."); }
    finally { setBusy(false); }
  }
  const references = Object.fromEntries(proposal.changes.map(change => [`$${change.local_ref}`, String(change.data?.name ?? change.object_name ?? change.object_type)]));
  return <section className="engineering-proposal-review" aria-label="Engineering-Vorschlag">
    <strong>{statusLabels[proposal.status]}</strong>
    <p>{proposal.rationale}</p>
    <p>{proposal.changes.length} Änderungen</p>
    <LazyDetails title="Änderungen prüfen">{() => <>
      {proposal.changes.map((change, index) => <article key={index}>
        <h4>{change.action === "CREATE" ? "Anlegen" : change.action === "DELETE" ? "Löschen" : "Ändern"}: {String(change.data?.name ?? change.object_name ?? change.object_type)}</h4>
        <Value value={change.data ?? change.impact_analysis ?? change.object_id} references={references} />
      </article>)}
    </>}</LazyDetails>
    {!!proposal.assumptions.length && <details><summary>Annahmen ({proposal.assumptions.length})</summary><ul>{proposal.assumptions.map((item, index) => <li key={index}>{item}</li>)}</ul></details>}
    {proposal.validation_result.findings?.map((finding, index) => <p role="alert" key={index}>{finding.message}</p>)}
    <div className="engineering-proposal-actions">
      {['PROPOSED', 'VALIDATED', 'APPROVED', 'OUTDATED'].includes(proposal.status) && <button disabled={busy || !loaded} onClick={() => setEditing(value => !value)}>Bearbeiten</button>}
      {proposal.status === "VALIDATED" && (wizardReview
        ? <button disabled={busy || !loaded} onClick={() => void action("approveApply")}>Freigeben, übernehmen &amp; fortfahren</button>
        : <button disabled={busy || !loaded} onClick={() => void action("approve")}>Vorschlag freigeben</button>)}
      {proposal.status === "APPROVED" && (wizardReview
        ? <button disabled={busy || !loaded} onClick={() => void action("approveApply")}>Übernehmen &amp; fortfahren</button>
        : <button disabled={busy || !loaded} onClick={() => void action("apply")}>Ins Modell übernehmen</button>)}
      {["PROPOSED", "OUTDATED"].includes(proposal.status) && <button disabled={busy || !loaded} onClick={() => void action("validate")}>Erneut prüfen</button>}
      {["PROPOSED", "VALIDATED", "APPROVED", "OUTDATED"].includes(proposal.status) && <button disabled={busy || !loaded} onClick={() => void action("reject")}>Ablehnen</button>}
    </div>
    {editing && <form className="engineering-proposal-editor" onSubmit={e => { e.preventDefault(); void action('revise'); }}>
      <p>Eine bearbeitete Fassung wird neu validiert und benötigt eine neue Freigabe.</p>
      <label>Beschreibung<textarea required value={rationale} onChange={e => setRationale(e.target.value)} /></label>
      {proposal.changes.filter(change => change.data?.name).map((change, index) => <label key={change.local_ref ?? index}>{change.object_type}<input required maxLength={200} value={names[change.local_ref ?? ''] ?? String(change.data?.name)} onChange={e => setNames(current => ({ ...current, [change.local_ref ?? '']: e.target.value }))} /></label>)}
      <button type="submit" disabled={busy}>Bearbeitete Fassung prüfen</button><button type="button" onClick={() => setEditing(false)}>Abbrechen</button>
    </form>}
    <ContextLinks refs={proposal.canonical_ids.map((ref, index) => ({ ...ref, name: String(proposal.changes[index]?.data?.name ?? proposal.changes[index]?.object_name ?? ref.object_type) }))} projectId={projectId} />
    {proposal.status === "APPLIED" && <p>{proposal.canonical_ids.length} Modellobjekte bestätigt.</p>}
    {error && <p role="alert">{error}</p>}
  </section>;
}

function EngineeringQuestion({ question, projectId, onAnswer }: { question: InteractiveQuestion; projectId: string; onAnswer?: (answer: AgentInput) => void }) {
  const multiple = question.selection_mode === "MULTI";
  const [selected, setSelected] = useState<string[]>(() => question.recommended_options.length ? question.recommended_options : question.options.filter(o => o.recommended && !o.disabled).map(o => o.id));
  const [currentStatus, setCurrentStatus] = useState<string>(question.status);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    const refresh = async () => {
      try {
        const result = await readConversation(projectId, controller.signal, question.id);
        const current = result.data?.questions?.[question.id];
        if (current) {
          const context = readAssistantContext();
          const expected = result.data.selected_context;
          const refs = (items: Record<string, string>[]) => items.map(item => [item.id, item.object_type]).sort();
          const outdated = current.status === 'OPEN' && expected && (expected.active_view !== context.active_view || JSON.stringify(refs(expected.selected_object_refs)) !== JSON.stringify(refs(context.selected_object_refs)));
          setCurrentStatus(outdated ? 'OUTDATED' : current.status);
          if (current.selected_options) setSelected(current.selected_options); setLoaded(true);
        }
        else { setCurrentStatus('OUTDATED'); setLoaded(true); }
      } catch { if (!controller.signal.aborted) setLoaded(false); }
    };
    void refresh();
    const timer = window.setInterval(() => { if (document.visibilityState === 'visible') void refresh(); }, 5000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [projectId, question.id]);
  const labels: Record<string, string> = { OPEN: 'Entscheidung offen', ANSWERED: 'Beantwortet', SKIPPED: 'Übersprungen', EXPIRED: 'Abgelaufen', OUTDATED: 'Kontext geändert · neu klären' };
  return <section className="engineering-question-card">
    <p className="muted" role="status">{loaded ? labels[currentStatus] : 'Gesprächsstand wird geprüft …'} · {question.engineering_impact === 'CRITICAL' ? 'Architekturrelevant' : question.required ? 'Erforderlich' : 'Optional'}</p>
    <fieldset className="engineering-agent-question" disabled={!loaded || currentStatus !== 'OPEN' || !onAnswer}>
      <legend>{question.question}</legend>
      {question.description && <p>{question.description}</p>}
      {question.options.map(option => <div className="engineering-option" key={option.id}>
        <label>
          <input type={multiple ? "checkbox" : "radio"} name={question.id} disabled={option.disabled} checked={selected.includes(option.id)}
            aria-describedby={`${question.id}-${option.id}-description`}
            onChange={() => setSelected(current => multiple ? current.includes(option.id) ? current.filter(value => value !== option.id) : [...current, option.id] : [option.id])} />
          <span>{option.label}{option.recommended && <small className="engineering-recommended">Empfohlen</small>}</span>
        </label>
        {option.description && <p id={`${question.id}-${option.id}-description`}>{option.description}</p>}
        {option.reason && <LazyDetails title="Warum?">{() => <p>{option.reason}</p>}</LazyDetails>}
      </div>)}
      <button type="button" disabled={!selected.length} onClick={() => onAnswer?.({ type: 'QUESTION_ANSWER', question_id: question.id, selected_options: selected })}>Auswahl übernehmen</button>
      {!question.required && <button type="button" onClick={() => onAnswer?.({ type: 'SKIP_QUESTION', question_id: question.id, selected_options: [] })}>Überspringen</button>}
    </fieldset>
    <ContextLinks refs={question.context_refs} projectId={projectId} />
  </section>;
}

function FindingDecision({ event, projectId, onAnswer }: { event: EngineeringAgentEvent; projectId: string; onAnswer?: (answer: AgentInput) => void }) {
  const [choice, setChoice] = useState('MITIGATE');
  const [rationale, setRationale] = useState('');
  const [review, setReview] = useState(true);
  const [status, setStatus] = useState('Offen');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    const refresh = () => readConversation(projectId, controller.signal)
      .then(r => { const decision = r.data?.decisions?.[event.id ?? '']; if (decision) setStatus(decision.status); }).catch(() => {});
    void refresh(); const timer = window.setInterval(refresh, 10000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [event.id, projectId]);
  async function save() {
    setBusy(true); setError('');
    try {
      const session = await fetch('/api/engineering/agent/review-session', { cache: 'no-store' }).then(r => r.json());
      const response = await fetch(`/api/engineering/agent/findings/${encodeURIComponent(event.id ?? '')}/decision`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Project-ID': projectId, 'X-Human-Review': 'confirmed', 'X-Review-CSRF': session.csrf_token },
        body: JSON.stringify({ decision: choice, rationale, review_on_change: review }),
      });
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.findings?.[0]?.message ?? 'Entscheidung konnte nicht gespeichert werden.');
      setStatus(result.data.status);
      if (choice === 'MITIGATE' && event.id) onAnswer?.({type:'FINDING_ACTION', finding_id:event.id});
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Speichern fehlgeschlagen.'); }
    finally { setBusy(false); }
  }
  const states: Record<string, string> = { MITIGATE: 'Abhilfe angefordert', ACCEPTED_RISK: 'Risiko akzeptiert', DEFERRED: 'Zurückgestellt', NEEDS_REVIEW: 'Modell geändert · erneute Prüfung erforderlich' };
  return <LazyDetails title={`Entscheidung: ${states[status] ?? status}`}>{() => <div>
    <label>Umgang mit dem Finding<select value={choice} onChange={e => setChoice(e.target.value)}><option value="MITIGATE">Maßnahme vorschlagen</option><option value="ACCEPTED_RISK">Risiko akzeptieren</option><option value="DEFERRED">Später prüfen</option></select></label>
    <label>Begründung<textarea value={rationale} onChange={e => setRationale(e.target.value)} maxLength={4000} /></label>
    <label><input type="checkbox" checked={review} onChange={e => setReview(e.target.checked)} />Bei Architekturänderung erneut prüfen</label>
    <button disabled={busy || (choice === 'MITIGATE' && !onAnswer) || (choice === 'ACCEPTED_RISK' && rationale.trim().length < 10)} onClick={() => void save()}>Entscheidung speichern</button>
    {error && <p role="alert">{error}</p>}
  </div>}</LazyDetails>;
}

export function EngineeringAgentEventCard({ event, projectId, onAnswer, onRetry, wizardReview = false }: { event: EngineeringAgentEvent; projectId: string; onAnswer?: (answer: AgentInput) => void; onRetry?: () => void; wizardReview?: boolean }) {
  if (event.type === 'CONTEXT' || event.type === 'HEARTBEAT') return null;
  if (event.type === "APPROVAL" && event.proposal) return <ProposalReview initial={event.proposal} projectId={projectId} wizardReview={wizardReview} />;
  if (event.question) return <section data-response-type={event.type}>{event.title && <h4>{event.title}</h4>}{event.recommendation && <LazyDetails title="Empfehlung im Detail">{() => <Value value={event.recommendation} />}</LazyDetails>}<EngineeringQuestion question={event.question} projectId={projectId} onAnswer={onAnswer} /></section>;
  const text = event.text ?? '';
  const summary = text.length > 700 ? `${text.slice(0, 700)}…` : text;
  return <section className={`engineering-response is-${event.type.toLowerCase()}`} data-response-type={event.type}>
    {event.title && <h4>{event.title}</h4>}
    <p role={event.type === 'ERROR' ? 'alert' : event.type === 'PROGRESS' ? 'status' : undefined}>{summary}</p>
    {text.length > 700 && <LazyDetails title="Vollständige Antwort">{() => <p>{text}</p>}</LazyDetails>}
    {event.type === 'FINDING' && <><small>{event.severity || 'Hinweis'}</small><FindingDecision event={event} projectId={projectId} onAnswer={onAnswer} /></>}
    {!!event.progress?.length && <ol className="engineering-progress">{event.progress.map((step, i) => <li key={i} data-status={step.status}>{step.status === 'done' ? '✓' : step.status === 'active' ? '◉' : '○'} {step.label}</li>)}</ol>}
    {event.type === 'PROGRESS' && Boolean(event.workload?.workload_id) && <LazyDetails title="Arbeitsauftrag im Detail">{() => <WorkloadProgress reviewViaAgent projectId={projectId} workloadId={String(event.workload!.workload_id)} initial={event.workload} />}</LazyDetails>}
    {event.recommendation && <LazyDetails title="Empfehlung im Detail">{() => <Value value={event.recommendation} />}</LazyDetails>}
    <ContextLinks refs={event.context_refs ?? []} projectId={projectId} />
    {event.type === 'ERROR' && <button type="button" disabled={!onRetry} onClick={onRetry}>Erneut versuchen</button>}
    {(event.type === 'RESULT' || text.length > 700 || Boolean(event.metadata?.detail_id)) && <ContextLinks refs={[{ object_type: 'Workspace', name: 'Im Workspace öffnen', ...(event.metadata?.detail_id ? {id:String(event.metadata.detail_id)} : {}) }]} projectId={projectId} />}
    <ContextLinks refs={(event.actions ?? []).filter(action => action.type === 'NAVIGATE' && typeof action.object_type === 'string').map(action => ({object_type:String(action.object_type),id:String(action.object_id ?? ''),name:String(action.label ?? 'Objekt öffnen')}))} projectId={projectId} />
    {event.metadata?.details != null && <LazyDetails title="Technische Details">{() => <Value value={event.metadata?.details} />}</LazyDetails>}
  </section>;
}
