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
  withProjectParam,
  type UserSettings,
} from "@/lib/user-settings";
import {
  DEFAULT_ENGINEERING_WIZARD_SETTINGS,
  normalizeEngineeringWizardSettings,
  REQUIRED_WIZARD_PROCESS_ID,
  WIZARD_PROCESS_GROUP,
  WIZARD_SCOPE_GROUP,
  type EngineeringWizardSettings,
} from "@/lib/engineering-wizard-settings";
import { getWorkflow, saveWorkflowParameters, setWorkflowContext } from "@/lib/workflow-api";
import { notifyWorkflowChanged } from "./workflow-header";
import { BUS_SETTING_LABELS } from "@/lib/bus-settings";
import { AgentLoggingSettings } from "./agent-logging-settings";
import { TraceStorageSettingsPanel } from "./trace-storage-settings";

export function SettingsPanel() {
  const [settings, setSettings] = useState<UserSettings>(DEFAULT_USER_SETTINGS);
  const [projectDraft, setProjectDraft] = useState(DEFAULT_USER_SETTINGS.activeProject);
  const [workflowParameters, setWorkflowParameters] = useState<Record<string, unknown>>({});
  const [parameterToken, setParameterToken] = useState<string>();
  const [catalog, setCatalog] = useState(localCatalog);
  const [formatsSaving, setFormatsSaving] = useState(false);
  const [formatsMessage, setFormatsMessage] = useState("");
  const [wizardSettings, setWizardSettings] = useState<EngineeringWizardSettings>(DEFAULT_ENGINEERING_WIZARD_SETTINGS);
  const [wizardProjectNameDraft, setWizardProjectNameDraft] = useState("");
  const [busLimitsDraft, setBusLimitsDraft] = useState(DEFAULT_ENGINEERING_WIZARD_SETTINGS.bus_participant_limits);
  const [wizardSettingsSaving, setWizardSettingsSaving] = useState(false);
  const [wizardSettingsLoaded, setWizardSettingsLoaded] = useState(false);
  const [wizardSettingsMessage, setWizardSettingsMessage] = useState("");

  useEffect(() => {
    const stored = readUserSettings();
    setSettings(stored);
    setProjectDraft(stored.activeProject);
    void Promise.all([
      getCatalog().catch(() => localCatalog),
      getWorkflow(),
    ]).then(([nextCatalog, workflow]) => {
      setCatalog(nextCatalog);
      setWorkflowParameters(workflow.parameters ?? {});
      setParameterToken(workflow.edit_tokens?.parameters);
      const fallbackModelType = typeof workflow.parameters?.industry === "string"
        ? workflow.parameters.industry
        : DEFAULT_ENGINEERING_WIZARD_SETTINGS.model_type;
      const nextWizardSettings = normalizeEngineeringWizardSettings(
        workflow.context?.engineering_wizard_settings,
        fallbackModelType,
      );
      setWizardSettings(nextWizardSettings);
      setWizardProjectNameDraft(nextWizardSettings.project_name);
      setBusLimitsDraft(nextWizardSettings.bus_participant_limits);
      setWizardSettingsLoaded(true);
    }).catch((error) => setFormatsMessage(error instanceof Error ? error.message : "Projekt konnte nicht geladen werden."));
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

  function update(key: "automaticModelSync" | "openAgentOnStart" | "collapseWorkflowHeroes", value: boolean) {
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
    window.location.assign(withProjectParam("/studio/settings", activeProject));
  }

  function reset() {
    setSettings(DEFAULT_USER_SETTINGS);
    setProjectDraft(DEFAULT_USER_SETTINGS.activeProject);
    writeUserSettings(DEFAULT_USER_SETTINGS);
    window.location.assign(withProjectParam("/studio/settings", DEFAULT_USER_SETTINGS.activeProject));
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
    setFormatsSaving(true);
    setFormatsMessage("");
    try {
      const saved = await saveWorkflowParameters(nextParameters, parameterToken);
      setWorkflowParameters(saved.parameters);
      setParameterToken(saved.edit_tokens?.parameters);
      notifyWorkflowChanged();
      setFormatsMessage(`${nextFormats.length} Ausgabeformat${nextFormats.length === 1 ? "" : "e"} gespeichert.`);
    } catch (error) {
      setFormatsMessage(error instanceof Error ? error.message : "Ausgabeformate konnten nicht gespeichert werden.");
    } finally {
      setFormatsSaving(false);
    }
  }

  async function saveWizardSettings(next: EngineeringWizardSettings, successMessage: string) {
    if (!wizardSettingsLoaded || wizardSettingsSaving) return;
    const previous = wizardSettings;
    setWizardSettings(next);
    setWizardSettingsSaving(true);
    setWizardSettingsMessage("");
    try {
      const workflow = await setWorkflowContext({ engineering_wizard_settings: next });
      const saved = normalizeEngineeringWizardSettings(workflow.context?.engineering_wizard_settings, next.model_type);
      setWizardSettings(saved);
      setWizardProjectNameDraft(saved.project_name);
      notifyWorkflowChanged();
      setWizardSettingsMessage(successMessage);
    } catch (error) {
      setWizardSettings(previous);
      setWizardProjectNameDraft(previous.project_name);
      setWizardSettingsMessage(error instanceof Error ? error.message : "Wizard-Vorgaben konnten nicht gespeichert werden.");
    } finally {
      setWizardSettingsSaving(false);
    }
  }

  function toggleWizardSetting(key: "scope_ids" | "process_ids", id: string) {
    if (key === "process_ids" && id === REQUIRED_WIZARD_PROCESS_ID) {
      setWizardSettingsMessage("Freigabe und Übernahme sind bewusst in einer einzigen Bestätigung verbunden.");
      return;
    }
    const current = wizardSettings[key];
    const values = current.includes(id) ? current.filter((item) => item !== id) : [...current, id];
    if (!values.length) {
      setWizardSettingsMessage("Mindestens eine Option muss aktiv bleiben.");
      return;
    }
    void saveWizardSettings({ ...wizardSettings, [key]: values }, "Wizard-Vorgabe gespeichert.");
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
          <label className="settings-toggle">
            <span>
              <strong>Workflow-Kopfbereiche standardmäßig einklappen</strong>
              <small>Die große Beschreibung und Statusübersicht in allen Workflow-Ansichten zunächst kompakt anzeigen.</small>
            </span>
            <input
              checked={settings.collapseWorkflowHeroes}
              onChange={(event) => update("collapseWorkflowHeroes", event.target.checked)}
              type="checkbox"
            />
          </label>
          <button className="button secondary settings-reset" onClick={reset} type="button">
            Standard wiederherstellen
          </button>
        </section>

        <AgentLoggingSettings />

        <section className="panel settings-panel settings-wizard" aria-labelledby="wizard-settings">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Projektanlage</p>
              <h2 id="wizard-settings">Wizard-Vorgaben</h2>
            </div>
            <span className="settings-wizard-state">{wizardSettingsSaving ? "Speichert …" : "Projektbezogen"}</span>
          </div>
          <p className="settings-wizard-intro">
            Diese Vorgaben gelten für neue Engineering-Läufe in diesem Projekt. Ein bereits gestarteter Lauf behält seinen bestätigten Stand.
          </p>
          <div className="settings-wizard-project-name">
            <label htmlFor="wizard-project-name">
              <strong>Projektname</strong>
              <small>Die lesbare Bezeichnung; die technische Projekt-ID bleibt unverändert.</small>
            </label>
            <div className="settings-project-control">
              <input
                id="wizard-project-name"
                maxLength={120}
                onChange={(event) => setWizardProjectNameDraft(event.target.value)}
                placeholder="z. B. NIS Restbussimulation"
                value={wizardProjectNameDraft}
              />
              <button
                className="button secondary"
                disabled={!wizardSettingsLoaded || wizardSettingsSaving || wizardProjectNameDraft.trim() === wizardSettings.project_name}
                onClick={() => void saveWizardSettings(
                  { ...wizardSettings, project_name: wizardProjectNameDraft.trim() },
                  "Projektname gespeichert.",
                )}
                type="button"
              >
                Speichern
              </button>
            </div>
          </div>
          <fieldset className="settings-wizard-group">
            <legend>Projekt-Modelltyp</legend>
            <p>Steuert Domänenkatalog, Gerätebegriffe und verfügbare Netztechnologien.</p>
            <div className="settings-wizard-grid model-types">
              {catalog.domains.map((domain) => (
                <label className={wizardSettings.model_type === domain.id ? "selected" : ""} key={domain.id}>
                  <input
                    checked={wizardSettings.model_type === domain.id}
                    disabled={!wizardSettingsLoaded || wizardSettingsSaving}
                    name="wizard-model-type"
                    onChange={() => void saveWizardSettings(
                      { ...wizardSettings, model_type: domain.id },
                      `Modelltyp ${domain.label} gespeichert.`,
                    )}
                    type="radio"
                  />
                  <span><strong>{domain.label}</strong><small>{domain.technologies.length} Technologien verfügbar</small></span>
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset className="settings-wizard-group">
            <legend>{WIZARD_SCOPE_GROUP.label}</legend>
            <p>Legt fest, bis zu welchen Studio-Artefakten der Agent arbeiten soll.</p>
            <div className="settings-wizard-grid workflow-scope">
              {WIZARD_SCOPE_GROUP.options.map((option) => (
                <label className={wizardSettings.scope_ids.includes(option.id) ? "selected" : ""} key={option.id}>
                  <input
                    checked={wizardSettings.scope_ids.includes(option.id)}
                    disabled={!wizardSettingsLoaded || wizardSettingsSaving}
                    onChange={() => toggleWizardSetting("scope_ids", option.id)}
                    type="checkbox"
                  />
                  <span><strong>{option.label}</strong><small>{option.detail}</small></span>
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset className="settings-wizard-group">
            <legend>{WIZARD_PROCESS_GROUP.label}</legend>
            <p>Definiert Standardisierung, Review-Gate und Übernahmeverhalten.</p>
            <div className="settings-wizard-grid">
              {WIZARD_PROCESS_GROUP.options.map((option) => (
                <label className={wizardSettings.process_ids.includes(option.id) ? "selected" : ""} key={option.id}>
                  <input
                    checked={wizardSettings.process_ids.includes(option.id)}
                    disabled={!wizardSettingsLoaded || wizardSettingsSaving || option.id === REQUIRED_WIZARD_PROCESS_ID}
                    onChange={() => toggleWizardSetting("process_ids", option.id)}
                    type="checkbox"
                  />
                  <span><strong>{option.label}</strong><small>{option.detail}</small></span>
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset className="settings-wizard-group">
            <legend>Teilnehmergrenzen je Bustyp</legend>
            <p>Maximale Teilnehmer je physischem Bussegment, einschließlich Gateway oder Controller. 0 bedeutet unbegrenzt. Die Vorgaben gelten für neue Planungen; bestehende Verbindungen werden beim Speichern nicht automatisch umgebaut.</p>
            <div className="settings-bus-limits">
              {Object.entries(BUS_SETTING_LABELS).map(([key, label]) => (
                <label key={key}>{label}<input aria-label={`${label} Teilnehmergrenze`} type="number" min="0" max="100000" step="1"
                  value={wizardSettingsLoaded ? busLimitsDraft[key] ?? 0 : ""} disabled={!wizardSettingsLoaded || wizardSettingsSaving}
                  onChange={event => setBusLimitsDraft(current => ({...current, [key]: Number(event.target.value)}))} /></label>
              ))}
            </div>
            <button className="button secondary" type="button" disabled={!wizardSettingsLoaded || wizardSettingsSaving || Object.values(busLimitsDraft).some(n => !Number.isInteger(n) || n < 0 || n === 1 || n > 100000)}
              onClick={() => void saveWizardSettings({...wizardSettings, bus_participant_limits: busLimitsDraft}, "Bus-Teilnehmergrenzen gespeichert.")}>Busgrenzen speichern</button>
          </fieldset>
          {wizardSettingsMessage && <p className="settings-format-message" role="status">{wizardSettingsMessage}</p>}
        </section>

        <TraceStorageSettingsPanel key={settings.activeProject} project={settings.activeProject} />

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
