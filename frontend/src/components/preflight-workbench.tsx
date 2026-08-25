"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getPreflight, getWorkflow, runPreflight, type AnalysisFinding, type PreflightCategory, type PreflightResults, type WorkflowState, type WorkflowStatus } from "@/lib/workflow-api";
import { notifyWorkflowChanged } from "./workflow-header";

export function PreflightWorkbench() {
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null);
  const [findings, setFindings] = useState<AnalysisFinding[]>([]);
  const [status, setStatus] = useState<WorkflowStatus | null>(null);
  const [categoryStatuses, setCategoryStatuses] = useState<Partial<PreflightResults["category_statuses"]>>({});
  const [categoryChecks, setCategoryChecks] = useState<Partial<PreflightResults["category_checks"]>>({});
  const [outdated, setOutdated] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void getWorkflow().then(setWorkflow).catch(() => undefined);
    void getPreflight().then((snapshot) => {
      setFindings(snapshot.findings);
      setStatus(snapshot.status);
      setOutdated(snapshot.is_outdated);
      const results = snapshot.results as Partial<PreflightResults>;
      setCategoryStatuses(results.category_statuses ?? {});
      setCategoryChecks(results.category_checks ?? {});
    }).catch(() => undefined);
  }, []);

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
      notifyWorkflowChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Preflight fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  const canSimulate = status === "APPROVED" || status === "WARNING";
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
          return (
          <div className="preflight-step" key={category.id}><span>{String(index + 1).padStart(2, "0")}</span><strong>{category.label}</strong><small className={`workflow-status status-${categoryStatus.toLowerCase()}`}><i /> {categoryStatus}</small><em>{checkCount ? `${checkCount} Befunde` : "ohne Befund"}</em></div>
          );
        })}
      </div>
      <div className={`preflight-verdict verdict-${(status ?? "empty").toLowerCase()}`}>
        <div><span>Preflight verdict</span><strong>{status ?? "Noch nicht ausgeführt"}</strong></div>
        <p>{verdictText}</p>
      </div>
      <div className="analysis-list findings-list">
        {findings.length ? findings.map((finding, index) => (
          <div className={`finding finding-${finding.severity.toLowerCase()}`} key={`${finding.code}-${index}`}><span>{finding.category?.replaceAll("_", " ") ?? finding.severity}</span><strong>{finding.message}</strong><small>{finding.code}{finding.recommendation ? ` · ${finding.recommendation}` : ""}</small></div>
        )) : <div className="analysis-empty"><strong>Noch keine Befunde</strong><p>Führe den Preflight aus, sobald Capacity & Timing aktuell ist.</p></div>}
      </div>
      <div className="analysis-footer-actions"><Link className="button secondary" href="/studio/capacity">Capacity öffnen</Link><Link aria-disabled={!canSimulate || outdated} className={`button primary ${!canSimulate || outdated ? "disabled" : ""}`} href={canSimulate && !outdated ? "/studio/simulation" : "/studio/validation"}>Simulation vorbereiten →</Link></div>
    </section>
  );
}
