"use client";

import { useEffect, useState } from "react";
import { readActiveProjectId } from "@/lib/user-settings";

/** Observe persisted revisions; never replace an open editor's draft. */
export function ProjectSyncNotice() {
  const [changed, setChanged] = useState(false);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let stopped = false;
    let pending = false;
    let project = "";
    let baseline = "";
    let localWrite = 0;
    const onWrite = () => { baseline = ""; localWrite++; };
    const poll = async () => {
      if (pending || document.visibilityState !== "visible") return;
      const projectId = readActiveProjectId();
      if (project !== projectId) {
        project = projectId;
        baseline = "";
        setChanged(false);
      }
      pending = true;
      const write = localWrite;
      try {
        const response = await fetch("/api/engineering/workflow/revision", {
          headers: { "X-Project-ID": projectId }, cache: "no-store", signal: AbortSignal.timeout(8000),
        });
        if (!response.ok) throw new Error("Projekt nicht erreichbar");
        const state = await response.json();
        if (stopped || projectId !== readActiveProjectId() || write !== localWrite) return;
        const revision = JSON.stringify([state.versions, state.edit_tokens]);
        if (baseline && baseline !== revision) setChanged(true);
        baseline = revision;
        setUnavailable(false);
      } catch {
        if (!stopped) setUnavailable(true);
      } finally {
        pending = false;
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 5000);
    window.addEventListener("engineering:write-completed", onWrite);
    window.addEventListener("focus", poll);
    document.addEventListener("visibilitychange", poll);
    return () => {
      stopped = true;
      window.clearInterval(timer);
      window.removeEventListener("engineering:write-completed", onWrite);
      window.removeEventListener("focus", poll);
      document.removeEventListener("visibilitychange", poll);
    };
  }, []);

  if (!changed && !unavailable) return null;
  return (
    <aside className="panel" role="status" style={{ position: "fixed", bottom: 16, left: 16, zIndex: 90, maxWidth: 520, padding: 16 }}>
      <strong>{unavailable ? "Projektverbindung unterbrochen" : "Neuer Projektstand verfügbar"}</strong>
      <p>{unavailable
        ? "Der gemeinsame Projektstand ist derzeit nicht erreichbar. Lokale Eingaben bleiben erhalten."
        : "Das Projekt wurde außerhalb dieser Ansicht geändert. Lokale Eingaben bleiben bis zum Neuladen erhalten."}</p>
      {changed && <button className="button secondary" onClick={() => window.location.reload()} type="button">Aktuellen Stand laden (verwirft ungespeicherte Eingaben)</button>}
    </aside>
  );
}
