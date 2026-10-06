"use client";

import { useCallback, useState } from "react";
import { getPreflight, type AnalysisSnapshot } from "@/features/workflow/lib/workflow-api";
import { findingsAtSource } from "@/features/sources/lib/source-findings";
import { readActiveProjectId } from "@/features/settings/lib/user-settings";
import { useWorkflowRefresh } from "@/features/workflow/lib/use-workflow-refresh";

export function SourceFindings({ projectId = "", stage, objectType, objectId }: {
  projectId?: string; stage?: string; objectType?: string; objectId?: string;
}) {
  const [snapshot, setSnapshot] = useState<AnalysisSnapshot | null>(null);
  const [error, setError] = useState("");
  const currentProject = readActiveProjectId();
  const refresh = useCallback(async () => {
    const requestedProject = readActiveProjectId();
    if (projectId && projectId !== requestedProject) { setSnapshot(null); return; }
    try {
      const next = await getPreflight();
      if (requestedProject !== readActiveProjectId()) return;
      if (next.project_id !== requestedProject) throw new Error("Prüfbefunde gehören nicht zum aktuellen Projekt.");
      setSnapshot(next); setError("");
    } catch (caught) {
      setSnapshot(null);
      if (caught && typeof caught === "object" && "status" in caught && caught.status === 404) setError("");
      else setError(caught instanceof Error ? caught.message : "Prüfbefunde sind nicht verfügbar.");
    }
  }, [projectId]);
  useWorkflowRefresh(refresh);
  const findings = findingsAtSource(snapshot?.findings ?? [], {
    projectId: currentProject, snapshotProjectId: snapshot?.project_id, stage, objectType, objectId,
  });
  if (error) return <p className="notice warning">Quellbefunde nicht verfügbar: {error}</p>;
  if (!findings.length) return null;
  return <section className="notice warning source-findings" aria-label="Prüfbefunde an der Quelle"
    data-source-object={objectId} data-source-stage={stage}>
    <strong>{snapshot?.is_outdated ? "Veraltete Prüfbefunde – Preflight erneut ausführen" : "Blockierende Prüfbefunde"}</strong>
    <ul>{findings.map((finding, index) => <li key={`${finding.code}:${finding.object_id ?? stage}:${index}`}>
      <strong>{finding.code}</strong> · {finding.message}
    </li>)}</ul>
  </section>;
}
