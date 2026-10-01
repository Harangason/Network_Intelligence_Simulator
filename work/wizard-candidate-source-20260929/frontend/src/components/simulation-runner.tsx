"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { cancelSimulation, createSimulation } from "@/lib/api";
import { topologyToConfig, type NetworkTopology } from "@/lib/topology";
import { createSimulationSnapshot, getWorkflow, setWorkflowContext, type SimulationSnapshot, type WorkflowState } from "@/lib/workflow-api";
import type { SimulationJob } from "@/lib/types";
import { SimulationResult } from "./simulation-result";
import { notifyWorkflowChanged } from "./workflow-header";
import { withProjectParam } from "@/lib/user-settings";

export function SimulationRunner({ initialProjectId = "" }: { initialProjectId?: string }) {
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null);
  const [snapshot, setSnapshot] = useState<SimulationSnapshot | null>(null);
  const [job, setJob] = useState<SimulationJob | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { void getWorkflow().then(setWorkflow).catch((caught) => setError(caught instanceof Error ? caught.message : "Workflow nicht verfügbar.")); }, []);

  useEffect(() => {
    void setWorkflowContext({
      selected_simulation: snapshot ? { snapshot_id: snapshot.id, job_id: job?.id ?? null } : null,
    }).catch(() => undefined);
  }, [job?.id, snapshot]);

  const valid = workflow?.statuses.validation === "APPROVED" || workflow?.statuses.validation === "WARNING";
  const simulationOutdated = workflow?.statuses.simulation === "OUTDATED";

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workflow || !valid) return;
    setBusy(true);
    setError("");
    try {
      const form = new FormData(event.currentTarget);
      const topology = workflow.topology as NetworkTopology;
      const hasTopology = Array.isArray(topology.nodes) && topology.nodes.length >= 2 && Array.isArray(topology.edges) && topology.edges.length > 0;
      let config: Record<string, unknown>;
      if (hasTopology) {
        config = topologyToConfig(topology, (workflow.parameters.formats as string[] | undefined) ?? ["universal-jsonl", "universal-csv"]).config;
      } else {
        config = {
          name: "validated_workflow_simulation",
          industry: workflow.parameters.industry ?? "automotive",
          technology: workflow.parameters.technology ?? "can_fd",
          node_count: 2,
          formats: workflow.parameters.formats ?? ["universal-jsonl"],
        };
      }
      config = {
        ...config,
        ...workflow.parameters,
        duration_s: Number(form.get("duration_s")),
        seed: Number(form.get("seed")),
        max_events: Number(form.get("max_events")),
        dropout_probability: Number(form.get("dropout_probability")),
        corruption_probability: Number(form.get("corruption_probability")),
      };
      const nextSnapshot = await createSimulationSnapshot(config);
      setSnapshot(nextSnapshot);
      const nextJob = await createSimulation(
        {
          workflow_managed: true,
          workflow_snapshot_id: nextSnapshot.id,
          project_id: workflow.project_id,
          ...(hasTopology ? { config } : config),
        },
        false,
      );
      setJob(nextJob);
      notifyWorkflowChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Simulation konnte nicht gestartet werden.");
    } finally {
      setBusy(false);
    }
  }

  async function stop() {
    if (!job) return;
    setBusy(true);
    setError("");
    try {
      setJob(await cancelSimulation(job.id));
      notifyWorkflowChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Simulation konnte nicht gestoppt werden.");
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setJob(null);
    setSnapshot(null);
    setError("");
  }

  const sourceSummary = useMemo(
    () => Object.entries(snapshot?.source_versions ?? workflow?.versions ?? {}),
    [snapshot, workflow],
  );
  return (
    <section className="simulation-runner">
      {!valid && <div className="workflow-blocker error"><strong>Simulation blockiert</strong><span>Ein aktueller Preflight mit Status APPROVED oder WARNING ist erforderlich.</span><Link href={withProjectParam("/studio/validation", initialProjectId)}>Preflight öffnen →</Link></div>}
      {simulationOutdated && <div className="workflow-blocker warning"><strong>Frühere Simulation ist OUTDATED</strong><span>{workflow?.stale_reasons.simulation}</span></div>}
      <div className="simulation-layout">
        <form className="panel simulation-control-panel" onSubmit={start}>
          <div className="panel-heading"><div><p className="eyebrow">Validated run</p><h2>Simulationsszenario</h2></div><span className={`snapshot-state ${valid ? "ready" : "blocked"}`}>{valid ? "SNAPSHOT READY" : "BLOCKED"}</span></div>
          <div className="form-grid three">
            <NumberControl label="Dauer" name="duration_s" unit="s" value="1" min="0.001" step="0.001" />
            <NumberControl label="Seed" name="seed" value="42" min="0" />
            <NumberControl label="Max. Events" name="max_events" value="100000" min="1" />
          </div>
          <div className="section-title"><span>FI</span> Failure Injection</div>
          <div className="form-grid">
            <NumberControl label="Dropout" name="dropout_probability" value="0" min="0" max="1" step="0.001" />
            <NumberControl label="Korruption" name="corruption_probability" value="0" min="0" max="1" step="0.001" />
          </div>
          {error && <div className="notice error">{error}</div>}
          <div className="form-actions"><Link className="button secondary" href={withProjectParam("/studio/validation", initialProjectId)}>Preflight prüfen</Link>{job && !["completed", "failed", "canceled"].includes(job.status) && <button className="button secondary" disabled={busy} onClick={() => void stop()} type="button">Stop</button>}{job && ["completed", "failed", "canceled"].includes(job.status) && <button className="button secondary" disabled={busy} onClick={reset} type="button">Reset</button>}<button className="button primary" disabled={!valid || busy || Boolean(job)} type="submit">{busy ? "Snapshot wird erstellt ..." : job ? "Lauf gestartet" : "Snapshot erstellen & starten ->"}</button><Link className="button secondary" href={withProjectParam("/trace-analysis", initialProjectId)}>Trace-Analyse</Link></div>
        </form>
        <aside className="side-column">
          <div className="panel snapshot-summary"><p className="eyebrow">Source versions</p><h2>Validierter Stand</h2><dl className="overview-list">{sourceSummary.map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>v{value}</dd></div>)}</dl>{snapshot && <p className="snapshot-id">Snapshot {snapshot.id}</p>}</div>
          {job ? <SimulationResult jobId={job.id} onJobChange={setJob} /> : <div className="empty-result"><strong>Noch kein Lauf gestartet</strong><p>Der Snapshot friert Modell, Routing, Netzwerk, Parameter und Berechnungen ein.</p></div>}
        </aside>
      </div>
    </section>
  );
}

function NumberControl({ label, name, value, unit, ...props }: { label: string; name: string; value: string; unit?: string; min?: string; max?: string; step?: string }) {
  return <label className="field"><span>{label}{unit ? ` (${unit})` : ""}</span><input defaultValue={value} id={name} name={name} type="number" {...props} /></label>;
}
