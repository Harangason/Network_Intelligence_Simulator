"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import {
  getWorkflow,
  setWorkflowContext,
  type WorkflowState,
  type WorkflowStatus,
  type WorkflowStep,
  type WorkflowStepId,
} from "@/lib/workflow-api";
import { SETTINGS_EVENT } from "@/lib/user-settings";

const LINKS: Record<WorkflowStepId, string> = {
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
  EMPTY: "Leer",
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

export const WORKFLOW_CHANGED_EVENT = "workflow:changed";
type WorkflowHeaderVariant = "engineering" | "trace-analysis";

const TRACE_ANALYSIS_STEPS = [
  { id: "session", label: "Session / Daten laden", status: "LOADED" },
  { id: "messages", label: "Botschaften", status: "INSPECT" },
  { id: "sequence", label: "Sequenz", status: "ORDER" },
  { id: "signals", label: "Signale", status: "VALUES" },
  { id: "trace", label: "Trace", status: "SYNC" },
  { id: "findings", label: "Findings / Gaps", status: "CONTEXT" },
  { id: "root-cause", label: "Root Cause", status: "EXPLAIN" },
] as const;

export function notifyWorkflowChanged() {
  window.dispatchEvent(new CustomEvent(WORKFLOW_CHANGED_EVENT));
}

export function WorkflowHeader({ variant = "engineering" }: { variant?: WorkflowHeaderVariant }) {
  if (variant === "trace-analysis") return <TraceAnalysisHeader />;
  return <Suspense fallback={<WorkflowHeaderSkeleton />}><WorkflowHeaderContent /></Suspense>;
}

function TraceAnalysisHeader() {
  const search = useSearchParams();
  const activeView = search.get("view") || "session";
  const jobId = search.get("job");
  return (
    <section className="workflow-header trace-workflow-header" aria-label="Verbindlicher Trace-Analyse-Workflow">
      <div className="workflow-heading">
        <div>
          <span className="eyebrow">Trace workflow</span>
          <strong>Load → Filter → Inspect Messages → Follow Sequence → Inspect Signals → Synchronize Trace → Detect Findings</strong>
        </div>
        <div className="workflow-heading-status">
          <span className="workflow-project mono">Analysis projection only</span>
        </div>
      </div>
      <nav className="workflow-steps trace-workflow-steps">
        {TRACE_ANALYSIS_STEPS.map((step, index) => (
          <Link
            aria-current={step.id === activeView ? "step" : undefined}
            className={`workflow-step ${step.id === activeView ? "active" : ""}`}
            href={`/trace-analysis?view=${step.id}${jobId ? `&job=${encodeURIComponent(jobId)}` : ""}`}
            key={step.id}
            title={step.label}
          >
            <span className="workflow-step-number">{index + 1}</span>
            <span className="workflow-step-copy">
              <strong>{step.label}</strong>
              <small className="workflow-status status-in_progress"><i aria-hidden="true" /> {step.status}</small>
            </span>
          </Link>
        ))}
      </nav>
    </section>
  );
}

function WorkflowHeaderSkeleton() {
  return <section className="workflow-header"><nav className="workflow-steps">{FALLBACK_STEPS.map((step) => <span className="workflow-step" key={step.id}><span className="workflow-step-number">{step.position}</span><span className="workflow-step-copy"><strong>{step.label}</strong><small className="workflow-status"><i /> Status lädt</small></span></span>)}</nav></section>;
}

function WorkflowHeaderContent() {
  const pathname = usePathname();
  const search = useSearchParams();
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null);
  const [error, setError] = useState("");

  const activeStep = useMemo<WorkflowStepId>(() => {
    if (pathname.endsWith("/engineering")) return "engineering_model";
    if (pathname.endsWith("/routing")) return "routing";
    if (pathname.endsWith("/capacity")) return "capacity_timing";
    if (pathname.endsWith("/validation")) return "validation";
    if (pathname.endsWith("/simulation")) return "simulation";
    if (pathname.endsWith("/results")) return "results_analysis";
    if (pathname.endsWith("/intelligence")) return "data_science_intelligence";
    return search.get("mode") === "network" ? "network_editor" : "parameters";
  }, [pathname, search]);

  const refresh = useCallback(() => {
    getWorkflow()
      .then((state) => {
        setWorkflow(state);
        setError("");
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Workflow unbekannt."));
  }, []);

  useEffect(() => {
    const handleSettingsChanged = () => {
      void setWorkflowContext({ active_workflow_step: activeStep })
        .then((state) => {
          setWorkflow(state);
          setError("");
        })
        .catch((caught) => setError(caught instanceof Error ? caught.message : "Workflow unbekannt."));
    };
    refresh();
    const timer = window.setInterval(refresh, 10000);
    window.addEventListener(WORKFLOW_CHANGED_EVENT, refresh);
    window.addEventListener(SETTINGS_EVENT, handleSettingsChanged);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener(WORKFLOW_CHANGED_EVENT, refresh);
      window.removeEventListener(SETTINGS_EVENT, handleSettingsChanged);
    };
  }, [activeStep, refresh]);

  useEffect(() => {
    void setWorkflowContext({ active_workflow_step: activeStep }).catch(() => undefined);
  }, [activeStep]);

  const activeStepStatus = workflow?.steps.find((step) => step.id === activeStep)?.status;
  const activeStaleReason = activeStepStatus === "OUTDATED"
    ? workflow?.stale_reasons?.[activeStep]
    : undefined;

  return (
    <section className="workflow-header" aria-label="Verbindlicher Engineering-Workflow">
      <div className="workflow-heading">
        <div>
          <span className="eyebrow">Project workflow</span>
          <strong>Define → Route → Connect → Configure → Calculate → Validate → Simulate → Analyze → Assess</strong>
        </div>
        <div className="workflow-heading-status">
          {workflow?.project_id && <span className="workflow-project mono">Projekt: {workflow.project_id}</span>}
          {error && <span className="workflow-api-error">Status nicht verfügbar</span>}
        </div>
      </div>
      <nav className="workflow-steps">
        {(workflow?.steps ?? FALLBACK_STEPS).map((step) => (
          <Link
            aria-current={step.id === activeStep ? "step" : undefined}
            className={`workflow-step ${step.id === activeStep ? "active" : ""}`}
            href={LINKS[step.id]}
            key={step.id}
            title={step.reason || `${step.label}: ${STATUS_LABELS[step.status]}`}
          >
            <span className="workflow-step-number">{step.position}</span>
            <span className="workflow-step-copy">
              <strong>{step.label}</strong>
              <small className={`workflow-status status-${step.status.toLowerCase()}`}>
                <i aria-hidden="true" /> {STATUS_LABELS[step.status]}
              </small>
            </span>
          </Link>
        ))}
      </nav>
      {activeStaleReason && (
        <p className="workflow-stale-reason">
          <strong>Neuberechnung erforderlich:</strong> {activeStaleReason}
        </p>
      )}
    </section>
  );
}
