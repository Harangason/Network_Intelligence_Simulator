"use client";

import { type ReactNode, useCallback, useEffect, useState } from "react";
import type { SimulationJob } from "@/lib/types";
import { getSimulation } from "@/lib/api";

const terminalStates = new Set(["completed", "failed", "canceled"]);

export function SimulationResult({
  jobId,
  standalone = false,
  onJobChange,
  action,
}: {
  jobId: string;
  standalone?: boolean;
  onJobChange?: (job: SimulationJob) => void;
  action?: ReactNode;
}) {
  const [job, setJob] = useState<SimulationJob | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const nextJob = await getSimulation(jobId);
      setJob(nextJob);
      onJobChange?.(nextJob);
      setError("");
      return nextJob;
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Status nicht verfügbar",
      );
      return null;
    }
  }, [jobId, onJobChange]);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      const nextJob = await refresh();
      if (active && nextJob && !terminalStates.has(nextJob.status)) {
        timer = setTimeout(poll, 700);
      }
    };
    void poll();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [refresh]);

  if (error) {
    return <div className="notice error">{error}</div>;
  }
  if (!job) {
    return <div className="result-skeleton">Simulation wird vorbereitet …</div>;
  }

  const result = job.result;
  const running = !terminalStates.has(job.status);
  return (
    <section className={`result-panel ${standalone ? "standalone-result" : ""}`}>
      <div className="result-heading">
        <div>
          <p className="eyebrow">Simulation job</p>
          <h2>
            {running
              ? job.status === "queued"
                ? "Wartet auf Ausführung"
                : "Trace wird erzeugt"
              : job.status === "failed"
                ? "Simulation fehlgeschlagen"
                : job.status === "canceled"
                  ? "Simulation gestoppt"
                : job.validate_only
                  ? "Konfiguration validiert"
                  : "Simulation abgeschlossen"}
          </h2>
        </div>
        <div className="result-heading-actions">
          <span className={`status-badge ${job.status}`}>
            {running && <span className="spinner" />}
            {job.status}
          </span>
          {action}
        </div>
      </div>

      {job.error && <div className="notice error">{job.error}</div>}

      {result && (
        <>
          <div className="metric-grid">
            <div className="metric">
              <span>Trace events</span>
              <strong>{result.trace.events.toLocaleString("de-DE")}</strong>
            </div>
            <div className="metric">
              <span>Validierung</span>
              <strong>{result.hardware_validation.valid ? "Bestanden" : "Fehler"}</strong>
            </div>
            <div className="metric">
              <span>Artefakte</span>
              <strong>{job.artifact_downloads?.length ?? 0}</strong>
            </div>
          </div>

          {!!result.warnings?.length && (
            <div className="notice warning">{result.warnings.join(" · ")}</div>
          )}

          {!!job.artifact_downloads?.length && (
            <div className="artifact-section">
              <h3>Erzeugte Artefakte</h3>
              <div className="artifact-list">
                {job.artifact_downloads.map((artifact) => (
                  <a className="artifact" download={artifact.name} href={artifact.url} key={artifact.index}>
                    <span className="file-icon">↓</span>
                    <span>
                      <strong>{artifact.name}</strong>
                      <small>Herunterladen</small>
                    </span>
                  </a>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
