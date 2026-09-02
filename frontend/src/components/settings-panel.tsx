"use client";

import { useEffect, useMemo, useState } from "react";
import { getCatalog } from "@/lib/api";
import { localCatalog } from "@/lib/local-simulator";
import {
  defaultSimulationFormats,
  groupSimulationFormats,
  mergeSimulationFormats,
} from "@/lib/simulation-formats";
import {
  DEFAULT_USER_SETTINGS,
  normalizeProjectId,
  readUserSettings,
  writeUserSettings,
  type UserSettings,
} from "@/lib/user-settings";
import { getWorkflow, saveWorkflowParameters } from "@/lib/workflow-api";
import { notifyWorkflowChanged } from "./workflow-header";

export function SettingsPanel() {
  const [settings, setSettings] = useState<UserSettings>(DEFAULT_USER_SETTINGS);
  const [projectDraft, setProjectDraft] = useState(DEFAULT_USER_SETTINGS.activeProject);
  const [workflowParameters, setWorkflowParameters] = useState<Record<string, unknown>>({});
  const [catalog, setCatalog] = useState(localCatalog);
  const [formatsSaving, setFormatsSaving] = useState(false);
  const [formatsMessage, setFormatsMessage] = useState("");

  useEffect(() => {
    const stored = readUserSettings();
    setSettings(stored);
    setProjectDraft(stored.activeProject);
    void Promise.all([
      getCatalog().catch(() => localCatalog),
      getWorkflow().catch(() => ({ parameters: {} })),
    ]).then(([nextCatalog, workflow]) => {
      setCatalog(nextCatalog);
      setWorkflowParameters(workflow.parameters ?? {});
    });
  }, []);

  const selectedTechnology = useMemo(() => {
    const industry = typeof workflowParameters.industry === "string" ? workflowParameters.industry : "automotive";
    const technology = typeof workflowParameters.technology === "string" ? workflowParameters.technology : "can_fd";
    return catalog.domains
      .find((domain) => domain.id === industry)
      ?.technologies.find((item) => item.id === technology);
  }, [catalog.domains, workflowParameters.industry, workflowParameters.technology]);

  const selectedFormats = useMemo(
    () => Array.isArray(workflowParameters.formats)
      ? workflowParameters.formats.map(String)
      : defaultSimulationFormats,
    [workflowParameters.formats],
  );
  const availableFormats = useMemo(
    () => mergeSimulationFormats(catalog.formats, selectedTechnology?.native_formats, defaultSimulationFormats),
    [catalog.formats, selectedTechnology],
  );
  const formatGroups = useMemo(() => groupSimulationFormats(availableFormats), [availableFormats]);

  function update(key: "automaticModelSync" | "openAgentOnStart", value: boolean) {
    const next = { ...settings, [key]: value };
    setSettings(next);
    writeUserSettings(next);
  }

  function activateProject() {
    const activeProject = normalizeProjectId(projectDraft);
    const next = { ...settings, activeProject };
    setProjectDraft(activeProject);
    setSettings(next);
    writeUserSettings(next);
  }

  function reset() {
    setSettings(DEFAULT_USER_SETTINGS);
    setProjectDraft(DEFAULT_USER_SETTINGS.activeProject);
    writeUserSettings(DEFAULT_USER_SETTINGS);
  }

  async function toggleFormat(format: string) {
    const nextFormats = selectedFormats.includes(format)
      ? selectedFormats.filter((item) => item !== format)
      : [...selectedFormats, format];
    if (nextFormats.length === 0) {
      setFormatsMessage("Mindestens ein Ausgabeformat muss aktiv bleiben.");
      return;
    }
    const nextParameters = { ...workflowParameters, formats: nextFormats };
    setWorkflowParameters(nextParameters);
    setFormatsSaving(true);
    setFormatsMessage("");
    try {
      await saveWorkflowParameters(nextParameters);
      notifyWorkflowChanged();
      setFormatsMessage(`${nextFormats.length} Ausgabeformat${nextFormats.length === 1 ? "" : "e"} gespeichert.`);
    } catch (error) {
      setFormatsMessage(error instanceof Error ? error.message : "Ausgabeformate konnten nicht gespeichert werden.");
    } finally {
      setFormatsSaving(false);
    }
  }

  return (
    <div className="settings-layout">
      <div className="settings-main-column">
        <section className="panel settings-panel" aria-labelledby="behavior-settings">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Verhalten</p>
              <h2 id="behavior-settings">Arbeitsbereich</h2>
            </div>
          </div>
          <div className="settings-project">
            <label htmlFor="active-project">
              <strong>Aktives Projekt</strong>
              <small>Workflow, Snapshots, Simulationen und KI-Kontext verwenden diese Projekt-ID.</small>
            </label>
            <div className="settings-project-control">
              <input
                id="active-project"
                maxLength={80}
                onChange={(event) => setProjectDraft(event.target.value)}
                spellCheck={false}
                value={projectDraft}
              />
              <button
                className="button secondary"
                disabled={normalizeProjectId(projectDraft) === settings.activeProject}
                onClick={activateProject}
                type="button"
              >
                Aktivieren
              </button>
            </div>
            <span className="settings-project-active mono">Aktiv: {settings.activeProject}</span>
          </div>
          <label className="settings-toggle">
            <span>
              <strong>Automatischer Modellabgleich</strong>
              <small>Änderungen im Netzwerk-Editor direkt mit dem Engineering-Modell abgleichen.</small>
            </span>
            <input
              checked={settings.automaticModelSync}
              onChange={(event) => update("automaticModelSync", event.target.checked)}
              type="checkbox"
            />
          </label>
          <label className="settings-toggle">
            <span>
              <strong>KI-Agent beim Start öffnen</strong>
              <small>Den Engineering-Assistenten beim Laden einer Seite aufgeklappt anzeigen.</small>
            </span>
            <input
              checked={settings.openAgentOnStart}
              onChange={(event) => update("openAgentOnStart", event.target.checked)}
              type="checkbox"
            />
          </label>
          <button className="button secondary settings-reset" onClick={reset} type="button">
            Standard wiederherstellen
          </button>
        </section>

        <section className="panel settings-panel settings-formats" aria-labelledby="format-settings">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Simulation</p>
              <h2 id="format-settings">Ausgabeformate</h2>
            </div>
            <span className="settings-format-count">{selectedFormats.length} aktiv</span>
          </div>
          <div className={`format-groups ${formatsSaving ? "saving" : ""}`}>
            {formatGroups.map((group) => (
              <section className="format-group" key={group.id}>
                <h3>{group.label}</h3>
                <div className="format-grid">
                  {group.formats.map((format) => (
                    <label
                      className={`format-option ${selectedFormats.includes(format.id) ? "selected" : ""}`}
                      key={format.id}
                    >
                      <input
                        checked={selectedFormats.includes(format.id)}
                        disabled={formatsSaving}
                        onChange={() => void toggleFormat(format.id)}
                        type="checkbox"
                      />
                      <span>{format.id}</span>
                      <small>{format.description}</small>
                    </label>
                  ))}
                </div>
              </section>
            ))}
          </div>
          {formatsMessage && <p className="settings-format-message">{formatsMessage}</p>}
        </section>
      </div>

      <aside className="panel settings-panel settings-system" aria-labelledby="system-settings">
        <p className="eyebrow">System</p>
        <h2 id="system-settings">Daten & Laufzeit</h2>
        <dl>
          <div><dt>Datenbank</dt><dd>PostgreSQL</dd></div>
          <div><dt>Modell</dt><dd>Kanonisch · Schema v2</dd></div>
          <div><dt>Engineering-API</dt><dd className="mono">:5050</dd></div>
          <div><dt>Studio</dt><dd className="mono">:13500</dd></div>
        </dl>
      </aside>
    </div>
  );
}
