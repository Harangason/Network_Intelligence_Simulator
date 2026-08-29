"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type WorkloadPackage = {
  category: string;
  duplicate_count: number;
  findings?: Array<{ code?: string; message?: string }>;
  generated_count: number;
  invalid_count: number;
  missing_count: number;
  package_code: string;
  requested_count: number;
  status: string;
  valid_count: number;
  work_package_id: string;
};

type WorkloadDependency = {
  dependency_workload_id?: string;
  required_status: string;
  satisfied: boolean;
  status: string;
  title: string;
  workload_id?: string;
  workload_type: string;
};

type WorkloadProgressData = {
  attempts: number;
  dependencies: WorkloadDependency[];
  duplicates: number;
  generated: number;
  invalid: number;
  max_generation_attempts: number;
  metrics?: { coverage_percent?: number; validation_pass_rate?: number };
  missing: number;
  requested: number;
  status: string;
  title: string;
  valid: number;
  work_packages: WorkloadPackage[];
  workload_id: string;
  workload_type: string;
};

type WorkloadObject = {
  approval_state?: string;
  canonical_id?: string | null;
  category: string;
  definition: Record<string, unknown>;
  duplicate_of?: string | null;
  is_duplicate: boolean;
  is_valid: boolean;
  proposal_id?: string | null;
  proposal_index?: number | null;
  review_state: string;
  validation_results?: Array<{ code?: string; field?: string; message?: string; severity?: string }>;
  workload_object_id: string;
};

type WorkloadEvent = {
  actor?: string | null;
  event_id: number;
  event_type: string;
  occurred_at: string;
};

type InitialWorkloadResult = Partial<{
  attempts: number;
  duplicates: number;
  generated: number;
  invalid: number;
  max_generation_attempts: number;
  missing: number;
  requested: number;
  status: string;
  valid: number;
}>;

const ACTIVE_STATUSES = new Set(["RECEIVED", "PLANNING", "IN_PROGRESS", "VALIDATING"]);

const STATUS_LABELS: Record<string, string> = {
  BLOCKED: "Blockiert",
  CANCELED: "Abgebrochen",
  COMPLETED: "Abgeschlossen",
  FAILED: "Fehlgeschlagen",
  INCOMPLETE: "Unvollständig",
  IN_PROGRESS: "In Arbeit",
  PAUSED: "Pausiert",
  PLANNING: "Planung",
  READY_FOR_REVIEW: "Bereit zur Prüfung",
  RECEIVED: "Angenommen",
  VALIDATING: "Validierung",
};

function statusLabel(status: string) {
  return STATUS_LABELS[status] ?? status.replaceAll("_", " ");
}

function numberValue(value: unknown, fallback = 0) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function initialProgress(workloadId: string, initial?: InitialWorkloadResult): WorkloadProgressData {
  return {
    attempts: numberValue(initial?.attempts),
    dependencies: [],
    duplicates: numberValue(initial?.duplicates),
    generated: numberValue(initial?.generated),
    invalid: numberValue(initial?.invalid),
    max_generation_attempts: numberValue(initial?.max_generation_attempts, 3),
    metrics: {},
    missing: numberValue(initial?.missing),
    requested: numberValue(initial?.requested),
    status: String(initial?.status ?? "RECEIVED"),
    title: "Engineering-Workload",
    valid: numberValue(initial?.valid),
    work_packages: [],
    workload_id: workloadId,
    workload_type: "SIGNAL_GENERATION",
  };
}

export function WorkloadProgress({
  initial,
  projectId,
  workloadId,
}: {
  initial?: InitialWorkloadResult;
  projectId: string;
  workloadId: string;
}) {
  const [progress, setProgress] = useState<WorkloadProgressData>(() => initialProgress(workloadId, initial));
  const [objects, setObjects] = useState<WorkloadObject[]>([]);
  const [events, setEvents] = useState<WorkloadEvent[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [categoryFilter, setCategoryFilter] = useState("ALL");
  const [reviewFilter, setReviewFilter] = useState("ALL");
  const [busyAction, setBusyAction] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const request = useCallback(async <T,>(path: string, init?: RequestInit): Promise<T> => {
    const response = await fetch(`/api/engineering${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        "X-Project-ID": projectId,
        ...init?.headers,
      },
      signal: AbortSignal.timeout(15_000),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error((payload as { error?: string }).error ?? `Workload-API ${response.status}`);
    }
    return payload as T;
  }, [projectId]);

  const refresh = useCallback(async () => {
    const [nextProgress, objectResult, eventResult] = await Promise.all([
      request<WorkloadProgressData>(`/workloads/${workloadId}/progress`),
      request<{ items: WorkloadObject[] }>(`/workloads/${workloadId}/objects`),
      request<{ items: WorkloadEvent[] }>(`/workloads/${workloadId}/events`),
    ]);
    setProgress(nextProgress);
    setObjects(objectResult.items);
    setEvents(eventResult.items);
  }, [request, workloadId]);

  useEffect(() => {
    let active = true;
    void refresh().catch((refreshError) => {
      if (active) setError(refreshError instanceof Error ? refreshError.message : "Workload konnte nicht geladen werden.");
    });
    return () => {
      active = false;
    };
  }, [refresh]);

  useEffect(() => {
    if (!ACTIVE_STATUSES.has(progress.status)) return;
    const timer = window.setInterval(() => {
      void refresh().catch(() => undefined);
    }, 1500);
    return () => window.clearInterval(timer);
  }, [progress.status, refresh]);

  const categories = useMemo(
    () => [...new Set(objects.map((item) => item.category))].sort(),
    [objects],
  );
  const filteredObjects = useMemo(() => objects.filter((item) => {
    if (categoryFilter !== "ALL" && item.category !== categoryFilter) return false;
    if (reviewFilter === "VALID" && (!item.is_valid || item.is_duplicate)) return false;
    if (reviewFilter === "INVALID" && item.is_valid && !item.is_duplicate) return false;
    if (reviewFilter === "WARNING" && !(item.validation_results ?? []).some((finding) => finding.severity === "WARNING")) return false;
    if (reviewFilter === "ERROR" && !(item.validation_results ?? []).some((finding) => (finding.severity ?? "ERROR") === "ERROR")) return false;
    if (reviewFilter === "AI_GENERATED" && item.definition.source !== "ai_generated") return false;
    if (reviewFilter === "PENDING" && (item.canonical_id || !item.is_valid || item.is_duplicate)) return false;
    if (reviewFilter === "APPROVED" && !item.canonical_id) return false;
    return true;
  }), [categoryFilter, objects, reviewFilter]);
  const reviewable = objects.filter((item) => item.is_valid && !item.is_duplicate && !item.canonical_id && item.proposal_id);
  const completionPercent = progress.requested > 0
    ? Math.min(100, Math.round(progress.valid * 100 / progress.requested))
    : 0;
  const warningCount = objects.reduce(
    (count, item) => count + (item.validation_results ?? []).filter((finding) => finding.severity === "WARNING").length,
    0,
  );

  async function mutate(action: string, targetWorkloadId = workloadId) {
    setBusyAction(`${targetWorkloadId}:${action}`);
    setError("");
    setNotice("");
    try {
      await request(`/workloads/${targetWorkloadId}/${action}`, {
        method: "POST",
        body: JSON.stringify({ actor: "engineering-workload-review-ui" }),
      });
      await refresh();
    } catch (mutationError) {
      setError(mutationError instanceof Error ? mutationError.message : "Aktion fehlgeschlagen.");
    } finally {
      setBusyAction("");
    }
  }

  async function approveSelected() {
    const selections: Record<string, number[]> = {};
    for (const item of objects) {
      if (!selected.has(item.workload_object_id) || !item.proposal_id || typeof item.proposal_index !== "number") continue;
      (selections[item.proposal_id] ??= []).push(item.proposal_index);
    }
    if (!Object.keys(selections).length) return;
    setBusyAction("approve-selected");
    setError("");
    try {
      await request(`/workloads/${workloadId}/approve-selected`, {
        method: "POST",
        body: JSON.stringify({ actor: "engineering-workload-review-ui", selections }),
      });
      setSelected(new Set());
      setNotice("Die ausgewählten, validen Objekte wurden ins kanonische Modell übernommen.");
      await refresh();
    } catch (approvalError) {
      setError(approvalError instanceof Error ? approvalError.message : "Freigabe fehlgeschlagen.");
    } finally {
      setBusyAction("");
    }
  }

  async function approveAll() {
    setBusyAction("approve-all-valid");
    setError("");
    try {
      await request(`/workloads/${workloadId}/approve-all-valid`, {
        method: "POST",
        body: JSON.stringify({ actor: "engineering-workload-review-ui" }),
      });
      setSelected(new Set());
      setNotice("Alle validen Objekte wurden freigegeben.");
      await refresh();
    } catch (approvalError) {
      setError(approvalError instanceof Error ? approvalError.message : "Freigabe fehlgeschlagen.");
    } finally {
      setBusyAction("");
    }
  }

  async function approveDependency(dependency: WorkloadDependency) {
    const dependencyId = dependency.dependency_workload_id ?? dependency.workload_id;
    if (!dependencyId) return;
    setBusyAction(`${dependencyId}:approve`);
    setError("");
    try {
      await request(`/workloads/${dependencyId}/approve-all-valid`, {
        method: "POST",
        body: JSON.stringify({ actor: "engineering-workload-review-ui" }),
      });
      await request(`/workloads/${workloadId}/resume`, {
        method: "POST",
        body: JSON.stringify({ actor: "engineering-workload-review-ui" }),
      });
      setNotice("Abhängigkeit freigegeben; der Hauptauftrag wurde fortgesetzt.");
      await refresh();
    } catch (dependencyError) {
      setError(dependencyError instanceof Error ? dependencyError.message : "Abhängigkeit konnte nicht freigegeben werden.");
    } finally {
      setBusyAction("");
    }
  }

  function toggleSelection(item: WorkloadObject) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(item.workload_object_id)) next.delete(item.workload_object_id);
      else next.add(item.workload_object_id);
      return next;
    });
  }

  return (
    <section className={`workload-progress status-${progress.status.toLowerCase().replaceAll("_", "-")}`}>
      <header className="workload-progress-head">
        <div>
          <span className="eyebrow">Engineering-Workload</span>
          <strong>{progress.title}</strong>
          <small>{statusLabel(progress.status)} · Versuch {progress.attempts}/{progress.max_generation_attempts}</small>
        </div>
        <div className="workload-progress-total">
          <b>{completionPercent} %</b>
          <span>{progress.valid} von {progress.requested} valide</span>
        </div>
      </header>

      <div aria-label={`${completionPercent} Prozent abgeschlossen`} className="workload-progress-track" role="progressbar" aria-valuemax={100} aria-valuemin={0} aria-valuenow={completionPercent}>
        <i style={{ width: `${completionPercent}%` }} />
      </div>

      <div className="workload-metrics">
        <span><small>Angefordert</small><b>{progress.requested}</b></span>
        <span><small>Erzeugt</small><b>{progress.generated}</b></span>
        <span><small>Valide</small><b>{progress.valid}</b></span>
        <span><small>Warnungen</small><b>{warningCount}</b></span>
        <span><small>Fehler</small><b>{progress.invalid}</b></span>
        <span><small>Duplikate</small><b>{progress.duplicates}</b></span>
        <span><small>Fehlend</small><b>{progress.missing}</b></span>
      </div>

      <div className="workload-packages">
        {progress.work_packages.map((item) => {
          const percent = item.requested_count > 0 ? Math.min(100, Math.round(item.valid_count * 100 / item.requested_count)) : 0;
          return (
            <article key={item.work_package_id}>
              <header><strong>{item.package_code} · {item.category}</strong><b>{percent} %</b></header>
              <div className="workload-progress-track"><i style={{ width: `${percent}%` }} /></div>
              <small>{statusLabel(item.status)} · {item.valid_count}/{item.requested_count} valide · {item.missing_count} fehlend</small>
              {item.findings?.map((finding, index) => (
                <em key={`${finding.code}-${index}`}>{finding.message ?? finding.code}</em>
              ))}
            </article>
          );
        })}
      </div>

      {progress.dependencies.length > 0 && (
        <div className="workload-dependencies">
          <strong>Abhängigkeiten</strong>
          {progress.dependencies.map((dependency) => {
            const dependencyId = dependency.dependency_workload_id ?? dependency.workload_id ?? dependency.title;
            return (
              <div key={dependencyId}>
                <span>{dependency.title}<small>{statusLabel(dependency.status)} · benötigt {statusLabel(dependency.required_status)}</small></span>
                {dependency.satisfied ? <b>Erfüllt</b> : (
                  <button className="button primary tiny" disabled={Boolean(busyAction)} onClick={() => void approveDependency(dependency)} type="button">
                    ✓ Prüfen, freigeben & fortsetzen
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="workload-controls">
        {!['PAUSED', 'CANCELED', 'COMPLETED'].includes(progress.status) && (
          <button className="button secondary tiny" disabled={Boolean(busyAction)} onClick={() => void mutate("pause")} type="button">Ⅱ Pausieren</button>
        )}
        {progress.status === "PAUSED" && (
          <button className="button primary tiny" disabled={Boolean(busyAction)} onClick={() => void mutate("resume")} type="button">▶ Fortsetzen</button>
        )}
        {!['CANCELED', 'COMPLETED'].includes(progress.status) && (
          <button className="button danger tiny" disabled={Boolean(busyAction)} onClick={() => void mutate("cancel")} type="button">× Abbrechen</button>
        )}
        {!['CANCELED', 'COMPLETED'].includes(progress.status) && (
          <button className="button secondary tiny" disabled={Boolean(busyAction)} onClick={() => void mutate("validate")} type="button">✓ Neu validieren</button>
        )}
        {progress.missing > 0 && (
          <button className="button secondary tiny" disabled={Boolean(busyAction)} onClick={() => void mutate("generate-missing")} type="button">＋ Fehlende erzeugen</button>
        )}
        {progress.invalid > 0 && (
          <button className="button secondary tiny" disabled={Boolean(busyAction)} onClick={() => void mutate("retry-invalid")} type="button">↻ Ungültige reparieren</button>
        )}
        {objects.length > 0 && (
          <button
            className="button secondary tiny"
            onClick={() => document.getElementById(`workload-review-${workloadId}`)?.scrollIntoView({ behavior: "smooth", block: "start" })}
            type="button"
          >Ergebnisse prüfen</button>
        )}
      </div>

      {objects.length > 0 && (
        <section className="workload-review" id={`workload-review-${workloadId}`}>
          <header>
            <strong>Objektprüfung</strong>
            <span>{reviewable.length} valide Objekte warten auf Freigabe</span>
          </header>
          <div className="workload-review-filters">
            <label>Kategorie
              <select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
                <option value="ALL">Alle</option>
                {categories.map((category) => <option key={category} value={category}>{category}</option>)}
              </select>
            </label>
            <label>Status
              <select value={reviewFilter} onChange={(event) => setReviewFilter(event.target.value)}>
                <option value="ALL">Alle</option>
                <option value="PENDING">Freigabe offen</option>
                <option value="VALID">Valide</option>
                <option value="INVALID">Mit Befund</option>
                <option value="WARNING">Warnung</option>
                <option value="ERROR">Fehler</option>
                <option value="AI_GENERATED">KI erzeugt</option>
                <option value="APPROVED">Freigegeben</option>
              </select>
            </label>
            <button className="button secondary tiny" disabled={!selected.size || Boolean(busyAction)} onClick={() => void approveSelected()} type="button">✓ Auswahl freigeben ({selected.size})</button>
            <button className="button primary tiny" disabled={!reviewable.length || Boolean(busyAction)} onClick={() => void approveAll()} type="button">✓ Alle validen freigeben</button>
          </div>
          <div className="workload-review-table-wrap">
            <table className="workload-review-table">
              <thead><tr><th>Auswahl</th><th>#</th><th>Kategorie</th><th>Signal</th><th>Einheit</th><th>Bereich</th><th>Zyklus</th><th>Producer</th><th>Validierung</th><th>Freigabe</th></tr></thead>
              <tbody>
                {filteredObjects.map((item, index) => {
                  const definition = item.definition;
                  const canSelect = item.is_valid && !item.is_duplicate && !item.canonical_id && Boolean(item.proposal_id);
                  const findings = item.validation_results ?? [];
                  return (
                    <tr key={item.workload_object_id}>
                      <td><input aria-label={`${String(definition.name ?? "Objekt")} auswählen`} checked={selected.has(item.workload_object_id)} disabled={!canSelect} onChange={() => toggleSelection(item)} type="checkbox" /></td>
                      <td>{index + 1}</td>
                      <td>{item.category}</td>
                      <td><strong>{String(definition.display_name ?? definition.name ?? item.workload_object_id)}</strong><small>{String(definition.datatype ?? "")}</small></td>
                      <td>{String(definition.unit ?? "–")}</td>
                      <td>{String(definition.minimum ?? "–")} … {String(definition.maximum ?? "–")}</td>
                      <td>{String(definition.cycle_time ?? "–")} ms</td>
                      <td>{String(definition.producer ?? "–")}</td>
                      <td className={item.is_valid && !item.is_duplicate ? "valid" : "invalid"}>{item.is_duplicate ? "Duplikat" : item.is_valid ? "Valide" : findings.map((finding) => finding.field ?? finding.code).filter(Boolean).join(", ") || "Befund"}</td>
                      <td>{item.canonical_id ? "Freigegeben" : item.review_state === "READY_FOR_REVIEW" ? "Offen" : statusLabel(item.review_state)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <details className="workload-audit">
        <summary>Auditspur · {events.length} Ereignisse</summary>
        <ol>
          {events.slice(0, 20).map((event) => (
            <li key={event.event_id}><time>{new Date(event.occurred_at).toLocaleString("de-DE")}</time><span>{event.event_type.replaceAll("_", " ")}</span><small>{event.actor ?? "System"}</small></li>
          ))}
        </ol>
      </details>

      {busyAction && <small className="workload-action-state" role="status"><span className="spinner" /> Aktion wird verarbeitet …</small>}
      {notice && <small className="notice success" role="status">{notice}</small>}
      {error && <small className="notice error" role="alert">{error}</small>}
    </section>
  );
}
