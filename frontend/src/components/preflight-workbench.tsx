"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import {
  engineeringObjectTypeClass,
  engineeringObjectTypeLabel,
} from "@/lib/engineering-object-style";
import { listRoutes, updateRoute } from "@/lib/routing-api";
import type { RoutingEntry } from "@/lib/types";
import { getPreflight, getWorkflow, runPreflight, type AnalysisFinding, type PreflightCategory, type PreflightResults, type WorkflowState, type WorkflowStatus } from "@/lib/workflow-api";
import { notifyWorkflowChanged } from "./workflow-header";
import { useWorkflowRefresh } from "@/lib/use-workflow-refresh";
import { withProjectParam } from "@/lib/user-settings";

export function PreflightWorkbench({ initialProjectId = "" }: { initialProjectId?: string }) {
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null);
  const [findings, setFindings] = useState<AnalysisFinding[]>([]);
  const [routes, setRoutes] = useState<RoutingEntry[]>([]);
  const [selectedFinding, setSelectedFinding] = useState<AnalysisFinding | null>(null);
  const [payloadDraft, setPayloadDraft] = useState("");
  const [status, setStatus] = useState<WorkflowStatus | null>(null);
  const [categoryStatuses, setCategoryStatuses] = useState<Partial<PreflightResults["category_statuses"]>>({});
  const [categoryChecks, setCategoryChecks] = useState<Partial<PreflightResults["category_checks"]>>({});
  const [outdated, setOutdated] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [nextWorkflow, nextRoutes, snapshot] = await Promise.all([
        getWorkflow(),
        listRoutes(),
        getPreflight(),
      ]);
      setWorkflow(nextWorkflow);
      setRoutes(nextRoutes);
      setFindings(snapshot.findings);
      setStatus(snapshot.status);
      setOutdated(snapshot.is_outdated);
      const results = snapshot.results as Partial<PreflightResults>;
      setCategoryStatuses(results.category_statuses ?? {});
      setCategoryChecks(results.category_checks ?? {});
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Preflight-Daten nicht verfügbar.");
    }
  }, []);
  useWorkflowRefresh(load);

  async function validate() {
    setBusy(true);
    setError("");
    try {
      const response = await runPreflight();
      setFindings(response.findings);
      setStatus(response.status);
      setCategoryStatuses(response.category_statuses);
      setCategoryChecks(response.category_checks);
      setOutdated(false);
      setWorkflow(await getWorkflow());
      setRoutes(await listRoutes());
      notifyWorkflowChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Preflight fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  function openFinding(finding: AnalysisFinding) {
    setSelectedFinding(finding);
    setPayloadDraft("");
  }

  async function savePayloadFinding() {
    if (!selectedFinding?.object_id || !payloadDraft.trim()) return;
    setBusy(true);
    setError("");
    try {
      const route = routes.find((item) => item.id === selectedFinding.object_id);
      if (!route) throw new Error("Die betroffene Route wurde nicht gefunden.");
      await updateRoute(route.id, {
        payload: {
          ...route.payload,
          data_object: payloadDraft.trim(),
          topic: route.payload.topic ?? null,
        },
        actor: "preflight-dialog",
      });
      const response = await runPreflight();
      setFindings(response.findings);
      setStatus(response.status);
      setCategoryStatuses(response.category_statuses);
      setCategoryChecks(response.category_checks);
      setWorkflow(await getWorkflow());
      setRoutes(await listRoutes());
      setSelectedFinding(null);
      setPayloadDraft("");
      notifyWorkflowChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Befund konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  }

  const canSimulate = status === "APPROVED" || status === "WARNING";
  const projectIdForLinks = workflow?.project_id ?? initialProjectId;
  const warningCount = findings.filter((finding) => finding.severity === "WARNING").length;
  const errorCount = findings.filter((finding) => finding.severity === "ERROR").length;
  const verdictText = outdated
    ? "Der Preflight ist veraltet. Änderungen an vorgelagerten Schritten müssen erneut geprüft werden."
    : status === "WARNING"
      ? `Kein blockierender Fehler. ${warningCount} Warnung${warningCount === 1 ? "" : "en"} verwendet noch unvollständige Zuordnungen oder Engineering-Schätzwerte. Die Simulation ist möglich, ihre Aussagekraft kann aber eingeschränkt sein.`
      : status === "APPROVED"
        ? "Alle technischen Prüfungen sind bestanden. Der validierte Stand kann als unveränderlicher SimulationSnapshot ausgeführt werden."
        : errorCount > 0
          ? `${errorCount} blockierende Fehler müssen vor der Simulation behoben werden.`
          : "Simulation bleibt blockiert, bis alle ERROR-Befunde behoben und aktuelle Berechnungen vorhanden sind.";
  const categories: Array<{ id: PreflightCategory; label: string }> = [
    { id: "engineering_model", label: "Engineering-Modell" },
    { id: "routing", label: "Routing" },
    { id: "network", label: "Netzwerk" },
    { id: "parameters", label: "Parameter" },
    { id: "capacity", label: "Capacity" },
    { id: "timing", label: "Timing" },
    { id: "reliability", label: "Reliability" },
    { id: "synchronization", label: "Synchronisation" },
  ];
  return (
    <section className="analysis-workbench preflight-workbench">
      <div className="analysis-toolbar">
        <div><p className="eyebrow">Technical gate</p><h2>Validation / Preflight</h2><p>Prüft Modell, Routing, Netzwerk, Parameter und Capacity gegen denselben Versionsstand.</p></div>
        <button className="button primary" disabled={busy} onClick={() => void validate()} type="button">{busy ? "Prüft …" : "Preflight ausführen"}</button>
      </div>
      {error && <div className="notice error">{error}</div>}
      {outdated && <div className="workflow-blocker warning"><strong>Preflight ist OUTDATED</strong><span>Ein vorgelagerter Schritt wurde geändert.</span></div>}
      <div className="preflight-status-grid">
        {categories.map((category, index) => {
          const categoryStatus = categoryStatuses[category.id] ?? "EMPTY";
          const checkCount = categoryChecks[category.id]?.length ?? 0;
          const firstFinding = categoryChecks[category.id]?.[0];
          return (
          <button className="preflight-step" disabled={!firstFinding} key={category.id} onClick={() => firstFinding && openFinding(firstFinding)} type="button"><span>{String(index + 1).padStart(2, "0")}</span><strong>{category.label}</strong><small className={`workflow-status status-${categoryStatus.toLowerCase()}`}><i /> {categoryStatus}</small><em>{checkCount ? `${checkCount} Befunde` : "ohne Befund"}</em></button>
          );
        })}
      </div>
      <div className={`preflight-verdict verdict-${(status ?? "empty").toLowerCase()}`}>
        <div><span>Preflight verdict</span><strong>{status ?? "Noch nicht ausgeführt"}</strong></div>
        <p>{verdictText}</p>
      </div>
      <div className="analysis-list findings-list">
        {findings.length ? findings.map((finding, index) => (
          <button className={`finding finding-${finding.severity.toLowerCase()}`} key={`${finding.code}-${index}`} onClick={() => openFinding(finding)} type="button"><span>{finding.category?.replaceAll("_", " ") ?? finding.severity}</span><strong>{finding.message}</strong><small>{finding.code}{finding.recommendation ? ` · ${finding.recommendation}` : ""}</small></button>
        )) : <div className="analysis-empty"><strong>Noch keine Befunde</strong><p>Führe den Preflight aus, sobald Capacity & Timing aktuell ist.</p></div>}
      </div>
      <div className="analysis-footer-actions"><Link className="button secondary" href={withProjectParam("/studio/capacity", projectIdForLinks)}>Capacity öffnen</Link><Link aria-disabled={!canSimulate || outdated} className={`button primary ${!canSimulate || outdated ? "disabled" : ""}`} href={withProjectParam(canSimulate && !outdated ? "/studio/simulation" : "/studio/validation", projectIdForLinks)}>Simulation vorbereiten →</Link></div>
      {selectedFinding && (
        <FindingDialog
          busy={busy}
          finding={selectedFinding}
          onClose={() => setSelectedFinding(null)}
          onPayloadDraft={setPayloadDraft}
          onSavePayload={() => void savePayloadFinding()}
          payloadDraft={payloadDraft}
          projectId={projectIdForLinks}
          route={routes.find((item) => item.id === selectedFinding.object_id) ?? null}
        />
      )}
    </section>
  );
}

function FindingDialog({ finding, route, payloadDraft, busy, onClose, onPayloadDraft, onSavePayload, projectId }: {
  finding: AnalysisFinding;
  route: RoutingEntry | null;
  payloadDraft: string;
  busy: boolean;
  onClose: () => void;
  onPayloadDraft: (value: string) => void;
  onSavePayload: () => void;
  projectId?: string;
}) {
  const editablePayload = finding.object_type === "RoutingEntry" && finding.code === "PAYLOAD_UNSPECIFIED" && Boolean(route);
  const problemHref = finding.object_type === "RoutingEntry" && finding.object_id
    ? `/studio/routing?route=${encodeURIComponent(finding.object_id)}&view=validation&edit=1`
    : finding.step === "capacity_timing" || finding.category === "capacity"
      ? "/studio/capacity"
      : finding.category === "network"
        ? "/studio?mode=network"
        : finding.category === "parameters"
          ? "/studio?mode=parameters"
          : "/studio/engineering";
  return (
    <div className="finding-dialog-backdrop" role="presentation">
      <section aria-labelledby="finding-dialog-title" aria-modal="true" className="finding-dialog" role="dialog">
        <header>
          <div>
            <p className="eyebrow">{finding.severity} · {finding.category?.replaceAll("_", " ") ?? "Preflight"}</p>
            <h2 id="finding-dialog-title">Inkonsistenz prüfen</h2>
          </div>
          <button aria-label="Dialog schließen" onClick={onClose} type="button">×</button>
        </header>
        <div className="finding-dialog-body">
          <dl>
            <dt>Befund</dt><dd>{finding.message}</dd>
            <dt>Code</dt><dd><code>{finding.code}</code></dd>
            <dt>Objekt</dt><dd>{finding.object_type ? <><span className={`eng-object-badge ${engineeringObjectTypeClass(finding.object_type)}`}>{engineeringObjectTypeLabel(finding.object_type)}</span> · {route?.route_code ?? finding.object_id ?? "unbekannt"}</> : "Workflow / Modell"}</dd>
            <dt>Empfehlung</dt><dd>{finding.recommendation ?? recommendationForFinding(finding)}</dd>
          </dl>
          {editablePayload ? (
            <label className="finding-edit-field">
              <span>Payload / Data Object</span>
              <input onChange={(event) => onPayloadDraft(event.target.value)} placeholder="z. B. VehicleSpeedFrame" value={payloadDraft} />
            </label>
          ) : (
            <p className="finding-dialog-note">Dieser Befund braucht Kontext aus dem betroffenen Editor. Öffne das Problem, prüfe Interface, Pfad oder Modellobjekt und speichere dort die Änderung.</p>
          )}
        </div>
        <footer>
          <button className="button secondary" onClick={onClose} type="button">Abbrechen</button>
          {editablePayload ? (
            <button className="button primary" disabled={busy || !payloadDraft.trim()} onClick={onSavePayload} type="button">{busy ? "Speichert ..." : "Übernehmen"}</button>
          ) : (
            <Link className="button primary" href={withProjectParam(problemHref, projectId)}>Zum Problem</Link>
          )}
        </footer>
      </section>
    </div>
  );
}

function recommendationForFinding(finding: AnalysisFinding) {
  if (finding.code === "SOURCE_INTERFACE_MISSING") return "Source Interface in der betroffenen Route auswählen.";
  if (finding.code === "DESTINATION_INTERFACE_MISSING") return "Ziel-Interface in der betroffenen Route setzen.";
  if (finding.code === "PAYLOAD_UNSPECIFIED") return "Message, Signale oder ein Data Object fuer die Route festlegen.";
  if (finding.code === "DUPLICATE_ROUTE") return "Route vergleichen und Dublette entfernen oder bewusst zusammenfuehren.";
  return "Betroffenen Workflow-Schritt öffnen und die Ursache korrigieren.";
}
