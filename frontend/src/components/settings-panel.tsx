"use client";

import { useEffect, useState } from "react";
import {
  DEFAULT_USER_SETTINGS,
  normalizeProjectId,
  readUserSettings,
  writeUserSettings,
  type UserSettings,
} from "@/lib/user-settings";

export function SettingsPanel() {
  const [settings, setSettings] = useState<UserSettings>(DEFAULT_USER_SETTINGS);
  const [projectDraft, setProjectDraft] = useState(DEFAULT_USER_SETTINGS.activeProject);

  useEffect(() => {
    const stored = readUserSettings();
    setSettings(stored);
    setProjectDraft(stored.activeProject);
  }, []);

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

  return (
    <div className="settings-layout">
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

      <aside className="panel settings-panel settings-system" aria-labelledby="system-settings">
        <p className="eyebrow">System</p>
        <h2 id="system-settings">Daten & Laufzeit</h2>
        <dl>
          <div><dt>Datenbank</dt><dd>PostgreSQL</dd></div>
          <div><dt>Modell</dt><dd>Kanonisch · Schema v2</dd></div>
          <div><dt>Engineering-API</dt><dd className="mono">:5050</dd></div>
          <div><dt>Studio</dt><dd className="mono">:3500</dd></div>
        </dl>
      </aside>
    </div>
  );
}
