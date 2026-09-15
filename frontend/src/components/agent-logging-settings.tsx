"use client";

import { useEffect, useState } from "react";
import { readActiveProjectId } from "@/lib/user-settings";

export function AgentLoggingSettings() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/agent/diagnostics?agentLog=status", { cache: "no-store", signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error("Der Protokollstatus konnte nicht geladen werden.");
        const payload = await response.json() as { enabled?: boolean };
        if (typeof payload.enabled !== "boolean") throw new Error("Der Protokollstatus ist nicht verfügbar.");
        if (!controller.signal.aborted) setEnabled(payload.enabled);
      })
      .catch(caught => { if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : "Protokollstatus nicht verfügbar."); });
    return () => controller.abort();
  }, []);

  async function toggle() {
    if (busy || enabled === null) return;
    setBusy(true); setError("");
    try {
      const response = await fetch("/api/agent/diagnostics", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "agent-log", enabled: !enabled,
          projectId: readActiveProjectId(), runId: "settings" }),
      });
      if (!response.ok) throw new Error("Die Protokollierung konnte nicht umgeschaltet werden.");
      const payload = await response.json() as { enabled?: boolean };
      if (typeof payload.enabled !== "boolean") throw new Error("Der neue Protokollstatus wurde nicht bestätigt.");
      setEnabled(payload.enabled);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Die Protokollierung konnte nicht umgeschaltet werden.");
    } finally { setBusy(false); }
  }

  return <section className="panel settings-panel" aria-labelledby="agent-logging-title">
    <div className="panel-heading"><div><p className="eyebrow">Diagnose</p>
      <h2 id="agent-logging-title">Agent-Protokollierung</h2></div></div>
    <label className="settings-toggle">
      <span><strong>Agent-Ereignisse protokollieren</strong>
        <small>Aufträge, Rückfragen, Laufzeiten und Fehler zur Fehlersuche aufzeichnen.</small></span>
      <input type="checkbox" role="switch" checked={enabled === true} disabled={busy || enabled === null}
        onChange={() => void toggle()} />
    </label>
    <p role="status">{busy ? "Wird gespeichert …" : enabled === null ? "Status wird geladen …" : enabled ? "Protokollierung ist eingeschaltet." : "Protokollierung ist ausgeschaltet."}</p>
    {error && <p role="alert">{error}</p>}
  </section>;
}
