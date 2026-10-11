"use client"
import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import type { AssuranceDraft } from "@/lib/eip/types"
import { VerificationCommand, workflowFailure } from "@/lib/eip/verification-command"

type Source = { ref: string; label: string; revision: number }
const categories = ["spoofing", "tampering", "repudiation", "information-disclosure", "denial-of-service", "elevation-of-privilege"]

/** EDS assurance-drafts v1: explicit analyst input, immutable attempt, separate review. */
export function AssuranceDrafts({ projectId, method, rows, total, canEdit }: {
  projectId: string; method: string; rows: AssuranceDraft[]; total: number; canEdit: boolean
}) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState("")
  const [reviewing, setReviewing] = useState<string | null>(null)
  const reviewAttempts = useRef(new Map<string, VerificationCommand>())
  if (!["fmea", "fta", "stride", "attack-tree", "nis-evidence", "nis-security-evidence"].includes(method)) return null
  async function review(row: AssuranceDraft) {
    if (reviewing) return
    setReviewing(row.ref); setMessage("")
    let attempt = reviewAttempts.current.get(row.ref)
    if (!attempt) { attempt = new VerificationCommand(); reviewAttempts.current.set(row.ref, attempt) }
    try {
      const result = await attempt.send(projectId, "reviews", { subjectRef: row.ref, subjectRevision: row.revision,
        reason: `Separate fachliche Prüfung der ${row.method.toUpperCase()}-Analyse ${row.ref}` }, 0)
      setMessage(`Prüfung ${result.record.ref} angefordert. Eine andere berechtigte Person entscheidet im Review Center.`)
      router.refresh()
    } catch (error) { setMessage(workflowFailure(error)) } finally { setReviewing(null) }
  }
  return <section className="space-y-3 rounded-lg border bg-card p-3 text-xs" aria-label="Gespeicherte Draft-Analysen">
    <div className="flex items-center justify-between gap-2"><h3 className="font-semibold">{method.toUpperCase()} · Draft-Analysen</h3><button className="rounded border px-3 py-2 disabled:opacity-50" disabled={!canEdit} onClick={() => setOpen(true)}>Analyse erstellen</button></div>
    <p>Explizite fachliche Eingaben, gebunden an Core-Quellrevisionen. Eine Prüfung ist keine Releasefreigabe.</p>
    {total > rows.length ? <p role="status">{rows.length} von {total} Analysen geladen; die Liste ist begrenzt.</p> : null}
    {rows.filter(row => row.method === method).map(row => <details key={row.ref} className="rounded border p-2"><summary>{row.title} · {row.ref} · r{row.revision} · {row.freshness}</summary>
      <p>Quellen: {Object.entries(row.sourceRevisions).map(([ref, revision]) => `${ref} r${revision}`).join(", ")}</p>
      <AssuranceResult method={row.method} result={row.assessment.result} />
      {row.assessment.gaps.map(gap => <p key={gap}>{gap}</p>)}
      {row.staleSources.length ? <p role="alert">Veraltete Quellen: {row.staleSources.join(", ")}</p> : null}
      <button className="mt-2 rounded border px-3 py-2 disabled:opacity-50" disabled={!canEdit || reviewing !== null || row.freshness !== "CURRENT"} onClick={() => void review(row)}>Separate Prüfung anfordern</button>
    </details>)}
    {message ? <p role="status">{message}</p> : null}
    {open ? <DraftEditor key={`${projectId}:${method}`} projectId={projectId} method={method} onClose={() => setOpen(false)} /> : null}
  </section>
}

function AssuranceResult({ method, result }: { method: string; result: Record<string, unknown> }) {
  const records = (value: unknown): Record<string, unknown>[] => Array.isArray(value) ? value.filter(item => item && typeof item === "object" && !Array.isArray(item)) : []
  const labels: Record<string, string> = { failureMode: "Fehlermodus", cause: "Ursache", localEffect: "Lokale Auswirkung", systemEffect: "Systemauswirkung", detection: "Erkennung", controls: "Maßnahmen", severity: "Schwere S", occurrence: "Auftreten O", detectability: "Entdeckbarkeit D", rpn: "RPN (S × O × D)", sourceRef: "Core-Quelle", category: "STRIDE-Kategorie", scenario: "Szenario", mitigation: "Gegenmaßnahme" }
  if (method === "fmea" || method === "stride") return <div className="my-2 space-y-2">
    {records(method === "fmea" ? result.rows : result.entries).map((record, index) => <dl key={index} className="grid grid-cols-[minmax(0,1fr)_minmax(0,2fr)] gap-x-3 gap-y-1 rounded border p-2">{Object.entries(record).map(([key, value]) => <div key={key} className="contents"><dt className="text-muted-foreground">{labels[key] ?? key}</dt><dd className="break-words">{value == null || value === "" ? "Nicht bewertet" : String(value)}</dd></div>)}</dl>)}
    <p>{method === "fmea" ? "Lokale S/O/D-Skala 1–10; keine normative Akzeptanzschwelle." : `Nicht untersuchte Kategorien: ${Array.isArray(result.unassessedCategories) ? result.unassessedCategories.join(", ") : "unbekannt"}`}</p>
  </div>
  if (["nis-evidence", "nis-security-evidence"].includes(method)) return <div className="space-y-2">
    <p>NIS-Projekt: {String(result.nisProjectId)} · Snapshot: {String(result.snapshotId)}</p>
    <p>Herkunft: ungeprüfter Operator-Import · aktueller NIS-Modellstand: ungeprüft · normative Bewertung: offen</p>
    <table className="w-full"><thead><tr><th>Anforderung</th><th>Norm / Ausgabe</th><th>Lieferantenergebnis</th></tr></thead><tbody>{records(result.requirements).map((row, index) => {
      const profile = row.profile as Record<string, unknown> | undefined;
      return <tr key={index}><td>{String(row.name)} · {String(row.sourceRef)}</td><td>{String(profile?.standard ?? "Offen")} · {String(profile?.edition ?? "Offen")}</td><td>{String(row.providerTechnicalStatus)}</td></tr>
    })}</tbody></table><p>Hash: {String(result.contentHash)}</p><p>Der Originalbericht bleibt im Core-Draft gespeichert. Review und Evidence-Qualifikation sind getrennte Schritte.</p>
  </div>
  const nodes = records(result.nodes)
  const names = new Map(nodes.map(node => [String(node.id), String(node.label)]))
  const sets = method === "fta" ? result.minimalCutSets : result.minimalAttackSets
  return <div className="my-2 space-y-2"><p className="font-semibold">Ziel: {names.get(String(result.rootId)) ?? "Unbekannt"}</p>
    <ul className="list-inside list-disc space-y-1">{nodes.map(node => <li key={String(node.id)}>{String(node.label)} · {node.kind === "event" ? `Basisereignis · ${node.sourceRef}` : `${node.kind === "and" ? "UND" : "ODER"}: ${Array.isArray(node.children) ? node.children.map(id => names.get(String(id)) ?? String(id)).join("; ") : "unbekannt"}`}</li>)}</ul>
    <p className="font-semibold">{method === "fta" ? "Minimale Ausfallkombinationen" : "Minimale Angriffskombinationen"}</p>
    <ol className="list-inside list-decimal">{Array.isArray(sets) ? sets.map((set, index) => <li key={index}>{Array.isArray(set) ? set.map(id => names.get(String(id)) ?? String(id)).join(" UND ") : "Unbekannt"}</li>) : null}</ol>
    <p>Qualitative Logik. Wahrscheinlichkeit nicht bewertet.</p>
  </div>
}

function DraftEditor({ projectId, method, onClose }: { projectId: string; method: string; onClose: () => void }) {
  const router = useRouter()
  const [id] = useState(() => `ASM-${crypto.randomUUID()}`)
  const [search, setSearch] = useState("")
  const [sources, setSources] = useState<Source[]>([])
  const [source, setSource] = useState<Source | null>(null)
  const [title, setTitle] = useState("")
  const [reason, setReason] = useState("")
  const [fields, setFields] = useState<Record<string, string>>({})
  const [category, setCategory] = useState(categories[0])
  const [bundleText, setBundleText] = useState("")
  const [nisProjectId, setNisProjectId] = useState("")
  const [gate, setGate] = useState("or")
  const [events, setEvents] = useState(["", ""])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("")
  const attempt = useRef(new VerificationCommand())
  const dialog = useRef<HTMLElement>(null)
  const busyRef = useRef(busy)
  busyRef.current = busy
  const closeRef = useRef(onClose)
  closeRef.current = onClose
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    dialog.current?.querySelector<HTMLInputElement>("input")?.focus()
    function keydown(event: KeyboardEvent) {
      if (event.key === "Escape" && !busyRef.current) { event.preventDefault(); closeRef.current(); return }
      if (event.key !== "Tab") return
      const nodes = Array.from(dialog.current?.querySelectorAll<HTMLElement>("button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled)") ?? []).filter(node => !node.matches(":disabled"))
      const first = nodes[0], last = nodes[nodes.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    document.addEventListener("keydown", keydown)
    return () => { document.removeEventListener("keydown", keydown); previous?.focus() }
  }, [])
  async function find() {
    setBusy(true); setMessage("")
    try {
      const response = await fetch(`/api/eip-verification/${encodeURIComponent(projectId)}/test/verification?recordCursor=0&targetSearch=${encodeURIComponent(search)}`, { cache: "no-store" })
      const data = await response.json()
      if (!response.ok || data.projectId !== projectId || !Array.isArray(data.targetOptions)) throw new Error("Quellen konnten nicht geladen werden.")
      setSources(data.targetOptions)
      if (data.targetNextCursor != null) setMessage("Erste 200 Treffer. Suche eingrenzen, um weitere Quellen zu finden.")
    } catch (error) { setMessage(workflowFailure(error)) } finally { setBusy(false) }
  }
  async function save() {
    if ((!source && !["nis-evidence", "nis-security-evidence"].includes(method)) || busy || !title.trim() || !reason.trim()) return
    setBusy(true); setMessage("")
    try {
      let analysis: Record<string, unknown>
      let sourceRevisions: Record<string, number> = source ? { [source.ref]: source.revision } : {}
      if (["nis-evidence", "nis-security-evidence"].includes(method)) {
        const bundle = JSON.parse(bundleText)
        analysis = { bundle, nisProjectId, eipProjectId: projectId }
        sourceRevisions = {}
        for (const row of bundle.payload.assessment.requirements) {
          const revisions = row.configuration.eip.source_revisions as Record<string, number>
          for (const [ref, revision] of Object.entries(revisions)) {
            if (ref in sourceRevisions && sourceRevisions[ref] !== revision) throw new Error("Widersprüchliche Quellenrevisionen.")
            sourceRevisions[ref] = revision
          }
        }
      } else if (method === "fmea") {
        const row: Record<string, unknown> = { ...fields, sourceRef: source!.ref }
        for (const key of ["severity", "occurrence", "detectability"]) row[key] = fields[key]?.trim() ? Number(fields[key]) : null
        analysis = { rows: [row] }
      } else if (method === "stride") analysis = { entries: [{ sourceRef: source!.ref, category, scenario: fields.scenario ?? "", mitigation: fields.mitigation ?? "" }] }
      else analysis = { rootId: "top", nodes: [{ id: "top", label: title, kind: gate, children: events.map((_, index) => `e${index + 1}`) },
        ...events.map((label, index) => ({ id: `e${index + 1}`, label, kind: "event", sourceRef: source!.ref }))] }
      await attempt.current.send(projectId, "assurance/drafts", { id, title, reason, method, sourceRevisions, analysis }, 0, id)
      router.refresh(); onClose()
    } catch (error) { setMessage(workflowFailure(error)) } finally { setBusy(false) }
  }
  const labels = method === "fmea" ? { failureMode: "Fehlermodus", cause: "Ursache", localEffect: "Lokale Auswirkung", systemEffect: "Systemauswirkung", detection: "Erkennung", controls: "Maßnahmen", severity: "Schwere S (1–10, optional)", occurrence: "Auftreten O (1–10, optional)", detectability: "Entdeckbarkeit D (1–10, optional)" } : { scenario: "Bedrohungsszenario", mitigation: "Gegenmaßnahme (optional)" }
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4"><section ref={dialog} role="dialog" aria-modal="true" aria-labelledby="assurance-title" className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-xl border bg-card p-4 text-xs">
    <h3 id="assurance-title" className="mb-3 font-semibold">{method.toUpperCase()}-Draft erstellen</h3>
    <fieldset disabled={busy || attempt.current.uncertain || attempt.current.blocked} className="grid gap-3 disabled:opacity-60">
      <label>Titel<input className="block w-full rounded border bg-background p-2" value={title} onChange={e => setTitle(e.target.value)} maxLength={300} /></label>
      {!["nis-evidence", "nis-security-evidence"].includes(method) && <><div><label>Core-Quelle suchen<input className="block w-full rounded border bg-background p-2" value={search} onChange={e => setSearch(e.target.value)} /></label><button className="mt-1 rounded border p-2" onClick={() => void find()}>Quellen suchen</button></div>
      <label>Quelle<select className="block w-full rounded border bg-background p-2" value={source?.ref ?? ""} onChange={e => setSource(sources.find(row => row.ref === e.target.value) ?? null)}><option value="">Quelle auswählen</option>{sources.map(row => <option key={row.ref} value={row.ref}>{row.label} · {row.ref} · r{row.revision}</option>)}</select></label></>}
      {["nis-evidence", "nis-security-evidence"].includes(method) && <><label>Originales NIS-Projekt<input className="block w-full rounded border bg-background p-2" value={nisProjectId} onChange={e => setNisProjectId(e.target.value)} required /></label><label>Exportierten NIS-Prüfbericht einfügen<textarea className="block w-full rounded border bg-background p-2 font-mono" rows={10} value={bundleText} onChange={e => setBundleText(e.target.value)} maxLength={2097152} /></label><p>Core-Safety-/SecurityRequirement-Referenzen und originale Revisionen werden aus den expliziten EIP-Zuordnungen geprüft. Keine automatische Risikofreigabe.</p></>}
      {method === "stride" ? <label>STRIDE-Kategorie<select className="block rounded border bg-background p-2" value={category} onChange={e => setCategory(e.target.value)}>{categories.map(value => <option key={value}>{value}</option>)}</select></label> : null}
      {["nis-evidence", "nis-security-evidence"].includes(method) ? null : ["fmea", "stride"].includes(method) ? Object.entries(labels).map(([key, label]) => <label key={key}>{label}<input className="block w-full rounded border bg-background p-2" value={fields[key] ?? ""} onChange={e => setFields({ ...fields, [key]: e.target.value })} /></label>) : <>
        <p>Ein AND/OR-Gatter mit expliziten Basisereignissen derselben Quelle. Keine Wahrscheinlichkeitsbewertung.</p>
        <label>Verknüpfung<select className="block rounded border bg-background p-2" value={gate} onChange={e => setGate(e.target.value)}><option value="or">ODER: mindestens ein Ereignis</option><option value="and">UND: alle Ereignisse</option></select></label>
        {events.map((value, index) => <label key={index}>Basisereignis {index + 1}<input className="block w-full rounded border bg-background p-2" value={value} onChange={e => setEvents(events.map((old, i) => i === index ? e.target.value : old))} /></label>)}
        <button className="rounded border p-2" disabled={events.length >= 16} onClick={() => setEvents([...events, ""])}>Basisereignis ergänzen</button>
      </>}
      <label>Begründung<textarea className="block w-full rounded border bg-background p-2" value={reason} onChange={e => setReason(e.target.value)} /></label>
    </fieldset>
    <p className="my-3">Fehlende Bewertungen bleiben offen. Speichern erzeugt einen Draft; die unabhängige Prüfung wird danach separat angefordert.</p>
    {message ? <p role="alert" className="my-2">{message}</p> : null}
    <footer className="flex justify-end gap-2"><button className="rounded border p-2" disabled={busy} onClick={onClose}>Schließen</button><button className="rounded border p-2 disabled:opacity-50" disabled={busy || (["nis-evidence", "nis-security-evidence"].includes(method) ? !bundleText.trim() || !nisProjectId.trim() : !source) || !title.trim() || !reason.trim() || attempt.current.blocked} onClick={() => void save()}>{attempt.current.uncertain ? "Unverändert wiederholen" : "Draft speichern"}</button></footer>
  </section></div>
}
