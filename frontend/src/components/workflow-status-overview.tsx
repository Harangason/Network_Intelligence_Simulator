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
import { SETTINGS_EVENT, withProjectParam } from "@/lib/user-settings";
import { WORKFLOW_CHANGED_EVENT } from "./workflow-header";
import { WORKFLOW_LINKS, WORKFLOW_STEP_DEFINITIONS } from "@/features/workflow/definition";

type StatusBucket = {
  key: "current" | "warning" | "outdated" | "error" | "active" | "open";
  label: string;
  count: number;
  color: string;
};

const STEP_LINKS: Record<WorkflowStepId, string> = WORKFLOW_LINKS;

const STATUS_LABELS: Record<WorkflowStatus, string> = {
  EMPTY: "Offen",
  IN_PROGRESS: "In Arbeit",
  COMPLETE: "Vollständig",
  WARNING: "Warnung",
  ERROR: "Fehler",
  APPROVED: "Freigegeben",
  OUTDATED: "Veraltet",
};

const FALLBACK_STEPS: WorkflowStep[] = WORKFLOW_STEP_DEFINITIONS.map((stage) => ({
  id: stage.id,
  label: stage.label,
  position: stage.position,
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

export function WorkflowStatusOverview({
  compact = false,
  initialProjectId = "",
}: {
  compact?: boolean;
  initialProjectId?: string;
}) {
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
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") refresh();
    };
    refreshWhenVisible();
    const timer = window.setInterval(refreshWhenVisible, 30000);
    window.addEventListener(WORKFLOW_CHANGED_EVENT, refresh);
    window.addEventListener(SETTINGS_EVENT, refresh);
    window.addEventListener("focus", refreshWhenVisible);
    document.addEventListener("visibilitychange", refreshWhenVisible);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener(WORKFLOW_CHANGED_EVENT, refresh);
      window.removeEventListener(SETTINGS_EVENT, refresh);
      window.removeEventListener("focus", refreshWhenVisible);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
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
  const projectIdForLinks = workflow?.project_id ?? initialProjectId;
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
                href={withProjectParam(STEP_LINKS[step.id], projectIdForLinks)}
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
