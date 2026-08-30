"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getWorkflowSummary,
  type WorkflowState,
  type WorkflowStatus,
  type WorkflowStep,
  type WorkflowStepId,
} from "@/lib/workflow-api";
import { SETTINGS_EVENT } from "@/lib/user-settings";
import { WORKFLOW_CHANGED_EVENT } from "./workflow-header";

type StatusBucket = {
  key: "current" | "warning" | "outdated" | "error" | "active" | "open";
  label: string;
  count: number;
  color: string;
};

const STEP_LINKS: Record<WorkflowStepId, string> = {
  engineering_model: "/studio/engineering",
  routing: "/studio/routing",
  network_editor: "/studio?mode=network",
  parameters: "/studio?mode=parameters",
  capacity_timing: "/studio/capacity",
  validation: "/studio/validation",
  simulation: "/studio/simulation",
  results_analysis: "/studio/results",
  data_science_intelligence: "/studio/intelligence",
};

const STATUS_LABELS: Record<WorkflowStatus, string> = {
  EMPTY: "Offen",
  IN_PROGRESS: "In Arbeit",
  COMPLETE: "Vollständig",
  WARNING: "Warnung",
  ERROR: "Fehler",
  APPROVED: "Freigegeben",
  OUTDATED: "Veraltet",
};

const FALLBACK_STEPS: WorkflowStep[] = [
  ["engineering_model", "Engineering-Modell"],
  ["routing", "Routing-Tabelle"],
  ["network_editor", "Netzwerk-Editor"],
  ["parameters", "Parameter"],
  ["capacity_timing", "Capacity & Timing"],
  ["validation", "Validation / Preflight"],
  ["simulation", "Simulation"],
  ["results_analysis", "Results / Analysis"],
  ["data_science_intelligence", "Data Science & Intelligence"],
].map(([id, label], index) => ({
  id: id as WorkflowStepId,
  label,
  position: index + 1,
  status: "EMPTY" as WorkflowStatus,
  version: 0,
}));

const STATUS_COLORS = {
  current: "#9fea4e",
  warning: "#f7c65b",
  outdated: "#f19a54",
  error: "#ff6b6b",
  active: "#69a7ff",
  open: "#536173",
} as const;

function statusBucket(status: WorkflowStatus): StatusBucket["key"] {
  if (status === "COMPLETE" || status === "APPROVED") return "current";
  if (status === "WARNING") return "warning";
  if (status === "OUTDATED") return "outdated";
  if (status === "ERROR") return "error";
  if (status === "IN_PROGRESS") return "active";
  return "open";
}

function buildDonutGradient(buckets: StatusBucket[], total: number) {
  if (total === 0) return "conic-gradient(#283341 0 100%)";

  let cursor = 0;
  const stops = buckets
    .filter((bucket) => bucket.count > 0)
    .map((bucket) => {
      const start = (cursor / total) * 100;
      cursor += bucket.count;
      const end = (cursor / total) * 100;
      return `${bucket.color} ${start}% ${end}%`;
    });

  return `conic-gradient(${stops.join(", ")})`;
}

export function WorkflowStatusOverview({ compact = false }: { compact?: boolean }) {
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(() => {
    getWorkflowSummary()
      .then((state) => {
        setWorkflow(state);
        setError("");
      })
      .catch(() => setError("Workflow-Status nicht verfügbar"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 10000);
    window.addEventListener(WORKFLOW_CHANGED_EVENT, refresh);
    window.addEventListener(SETTINGS_EVENT, refresh);
    window.addEventListener("focus", refresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener(WORKFLOW_CHANGED_EVENT, refresh);
      window.removeEventListener(SETTINGS_EVENT, refresh);
      window.removeEventListener("focus", refresh);
    };
  }, [refresh]);

  const steps = workflow?.steps ?? FALLBACK_STEPS;
  const buckets = useMemo(() => {
    const counts = { current: 0, warning: 0, outdated: 0, error: 0, active: 0, open: 0 };
    steps.forEach((step) => { counts[statusBucket(step.status)] += 1; });
    return [
      { key: "current", label: "Aktuell", count: counts.current, color: STATUS_COLORS.current },
      { key: "warning", label: "Warnung", count: counts.warning, color: STATUS_COLORS.warning },
      { key: "outdated", label: "Veraltet", count: counts.outdated, color: STATUS_COLORS.outdated },
      { key: "error", label: "Fehler", count: counts.error, color: STATUS_COLORS.error },
      { key: "active", label: "In Arbeit", count: counts.active, color: STATUS_COLORS.active },
      { key: "open", label: "Offen", count: counts.open, color: STATUS_COLORS.open },
    ] satisfies StatusBucket[];
  }, [steps]);

  const total = steps.length;
  const currentCount = buckets.find((bucket) => bucket.key === "current")?.count ?? 0;
  const gradient = buildDonutGradient(buckets, total);
  const summary = buckets.map((bucket) => `${bucket.label}: ${bucket.count}`).join(", ");

  return (
    <section
      className={`workflow-status-overview ${compact ? "compact" : ""}`}
      aria-busy={loading}
      aria-label="Workflow-Gesamtstatus"
    >
      <header className="workflow-status-overview-header">
        <div>
          <p className="agent-widget-eyebrow">Project workflow</p>
          <h2>Gesamtübersicht</h2>
        </div>
        <span className="workflow-status-live"><i aria-hidden="true" />Live</span>
      </header>

      <div className="workflow-status-summary">
        <div
          aria-label={`${currentCount} von ${total} Schritten aktuell. ${summary}`}
          className="workflow-status-donut"
          role="img"
          style={{ background: gradient }}
        >
          <div className="workflow-status-donut-center">
            <strong>{loading ? "…" : `${currentCount}/${total}`}</strong>
            <span>aktuell</span>
          </div>
        </div>

        <dl className="workflow-status-legend">
          {buckets.map((bucket) => (
            <div key={bucket.key}>
              <dt><i aria-hidden="true" style={{ backgroundColor: bucket.color }} />{bucket.label}</dt>
              <dd>{bucket.count}</dd>
            </div>
          ))}
        </dl>
      </div>

      {!compact && (
        <>
          <nav className="workflow-status-step-list" aria-label="Status aller Workflow-Schritte">
            {steps.map((step) => (
              <Link
                className={`workflow-status-step status-${step.status.toLowerCase()} ${step.id === workflow?.active_step ? "active" : ""}`}
                href={STEP_LINKS[step.id]}
                key={step.id}
                title={step.reason || `${step.label}: ${STATUS_LABELS[step.status]}`}
              >
                <span>{step.position}</span>
                <span>
                  <strong>{step.label}</strong>
                  <small><i aria-hidden="true" />{STATUS_LABELS[step.status]} · v{step.version}</small>
                </span>
              </Link>
            ))}
          </nav>

          <footer className="workflow-status-overview-footer">
            <span className={error ? "workflow-status-error" : ""}>{error || `${currentCount}/${total} Schritte aktuell`}</span>
            <span>{workflow?.project_id ?? "Projekt wird geladen"}</span>
          </footer>
        </>
      )}
    </section>
  );
}
