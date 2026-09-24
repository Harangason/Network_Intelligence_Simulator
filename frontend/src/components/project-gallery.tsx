"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Arrow } from "./marketing-shell";
import { requestEngineeringAgentWizard } from "@/lib/agent-task-events";
import { createNetworkProjectId } from "@/lib/project-ids";
import { readUserSettings, withProjectParam, writeUserSettings } from "@/lib/user-settings";
import { setWorkflowContext } from "@/lib/workflow-api";
import styles from "./project-gallery.module.css";

type Project = { project_id: string; name: string; description: string; active_step: string;
  statuses: Record<string, string>; updated_at: string };
type ProjectPage = { items: Project[]; total: number; next_offset: number | null };
const steps: Record<string, string> = { engineering_model: "Engineering-Modell", routing: "Routing",
  network_editor: "Netzwerk", parameters: "Parameter", capacity_timing: "Kapazität & Timing",
  validation: "Validierung", simulation: "Simulation", results_analysis: "Ergebnisse",
  data_science_intelligence: "Bewertung" };
const statusNames: Record<string, string> = { EMPTY: "Noch nicht begonnen", IN_PROGRESS: "In Arbeit",
  COMPLETE: "Abgeschlossen", APPROVED: "Freigegeben", WARNING: "Mit Hinweisen", ERROR: "Prüfung erforderlich", OUTDATED: "Aktualisierung erforderlich" };

export function ProjectGallery({ mode = "simulation" }: { mode?: "simulation" | "trace" }) {
  const trace = mode === "trace";
  const destination = trace ? "/trace-analysis" : "/studio/engineering";
  const [projects, setProjects] = useState<Project[]>([]);
  const [next, setNext] = useState<number | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [query, setQuery] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ projectId: string; name: string } | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [renameError, setRenameError] = useState("");
  const deleteBusy = useRef(false);
  const pendingProject = useRef<string | null>(null);
  const createBusy = useRef(false);
  const loadAbort = useRef<AbortController | null>(null);

  async function load(offset = 0) {
    loadAbort.current?.abort();
    const controller = new AbortController(); loadAbort.current = controller;
    setLoading(true); setError("");
    try {
      const response = await fetch(`/api/engineering/projects?offset=${offset}`, { signal: controller.signal, cache: "no-store" });
      if (!response.ok) throw new Error("Die Projekte konnten nicht geladen werden.");
      const result: ProjectPage = await response.json();
      if (controller.signal.aborted) return;
      setProjects(previous => offset === 0 ? result.items : [...new Map([...previous, ...result.items].map(item => [item.project_id, item])).values()]);
      setNext(result.next_offset); setTotal(result.total);
    } catch (caught) {
      if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : "Projekte konnten nicht geladen werden.");
    } finally { if (!controller.signal.aborted) setLoading(false); }
  }
  useEffect(() => { void load(); return () => loadAbort.current?.abort(); }, []);

  async function create() {
    if (createBusy.current) return;
    createBusy.current = true; setCreating(true); setCreateError("");
    try {
      // Keep this identity on retry, including when the accepted save response was lost.
      const project = pendingProject.current ??= createNetworkProjectId();
      await setWorkflowContext({ engineering_wizard_settings: { project_name: trace ? "Neues Trace-Projekt" : "Neues Projekt", model_type: "custom" } }, project);
      writeUserSettings({ ...readUserSettings(), activeProject: project });
      if (!trace) requestEngineeringAgentWizard(project, { dispatch: false });
      window.location.assign(withProjectParam(destination, project));
    } catch (caught) {
      setCreateError(caught instanceof Error ? caught.message : "Das Projekt konnte nicht angelegt werden.");
      setCreating(false); createBusy.current = false;
    }
  }
  const term = query.trim().toLocaleLowerCase("de");
  async function remove(project: Project) {
    if (deleteBusy.current || !window.confirm(`Projekt „${project.name || project.project_id}“ endgültig löschen? Modell, Aufträge und gespeicherte Projektdaten werden entfernt.`)) return;
    deleteBusy.current = true; setDeleting(project.project_id); setError('');
    try {
      const response = await fetch('/api/engineering/projects/delete', { method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Project-ID': project.project_id },
        body: JSON.stringify({ confirm_project_id: project.project_id }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Projekt konnte nicht gelöscht werden.');
      const settings = readUserSettings();
      if (settings.activeProject === project.project_id) writeUserSettings({ ...settings, activeProject: 'default' });
      await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Projekt konnte nicht gelöscht werden.'); }
    finally { deleteBusy.current = false; setDeleting(null); }
  }
  async function rename(project: Project) {
    if (!editing || editing.projectId !== project.project_id || renaming) return;
    const name = editing.name.trim();
    if (!name) { setRenameError("Bitte einen Projektnamen eingeben."); return; }
    if (name === project.name) { setEditing(null); setRenameError(""); return; }
    setRenaming(true); setRenameError("");
    try {
      const response = await fetch("/api/engineering/projects/rename", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Project-ID": project.project_id },
        body: JSON.stringify({ name }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Projektname konnte nicht gespeichert werden.");
      setProjects(current => current.map(item => item.project_id === project.project_id ? { ...item, name: result.name } : item));
      setEditing(null);
      void load();
    } catch (caught) {
      setRenameError(caught instanceof Error ? caught.message : "Projektname konnte nicht gespeichert werden.");
    } finally { setRenaming(false); }
  }
  const filtered = projects.filter(project => `${project.name} ${project.description} ${project.project_id}`.toLocaleLowerCase("de").includes(term));
  return <section className={styles.gallery} aria-labelledby="projects-title">
    <header className={styles.header}>
      <p className="section-label">Dein Workspace</p>
      <h1 id="projects-title">{trace ? "Deine Trace-Projekte" : "Deine Projekte"}<span>.</span></h1>
      <p>{trace ? "Ein Projekt für die Trace-Analyse öffnen oder ein neues Projekt zum Laden eigener Trace-Dateien anlegen." : "Eine Idee beginnen oder dort weitermachen, wo du aufgehört hast."}</p>
    </header>
    <div className={styles.toolbar}>
      <label>Projekte durchsuchen<input type="search" placeholder="Name, Beschreibung oder Projekt-ID" value={query} onChange={event => setQuery(event.target.value)} /></label>
      <span>{projects.length} von {total} Projekten</span>
      <button className="button secondary" disabled={loading} onClick={() => void load()}>Aktualisieren</button>
    </div>
    {error && <p role="alert" className={styles.error}>{error} <button className="button secondary" onClick={() => void load()}>Erneut versuchen</button></p>}
    {createError && <p role="alert" className={styles.error}>{createError} Bitte erneut versuchen.</p>}
    <div className={styles.grid} aria-busy={loading}>
      <button className={`${styles.card} ${styles.newCard}`} onClick={() => void create()} disabled={creating}>
        <span className={styles.plus} aria-hidden="true">+</span>
        <strong>{creating ? "Projekt wird angelegt …" : trace ? "Neues Trace-Projekt" : "Neues Projekt"}</strong>
        <span>{trace ? "Trace-Dateien laden und analysieren" : "Mit dem Engineering-Wizard starten"}</span>
      </button>
      {filtered.map(project => <article key={project.project_id} className={styles.card}>
        <Link href={withProjectParam(destination, project.project_id)} className={styles.cardLink}>
        <div className={styles.cardTop}><span>{trace ? "Trace-Analyse" : steps[project.active_step] ?? "Engineering"}</span><Arrow /></div>
        <h2>{project.name || project.project_id}</h2>
        <p>{project.description || (trace ? "Eigene Trace-Dateien oder vorhandene Simulationsläufe untersuchen." : "Modell, Kommunikation und Simulation in einem Projekt.")}</p>
        <span className={styles.status} data-status={project.statuses[project.active_step]}>{trace ? "Trace-Analyse öffnen" : statusNames[project.statuses[project.active_step]] ?? "Projekt öffnen"}</span>
        <div className={styles.cardBottom}><time dateTime={project.updated_at}>Geändert {new Date(project.updated_at).toLocaleDateString("de-DE")}</time><span title={project.project_id}>{project.project_id.replace(/^network-project-/, "")}</span></div>
        </Link>
        {editing?.projectId === project.project_id && <form className={styles.renameForm} onSubmit={event => { event.preventDefault(); void rename(project); }}>
          <label htmlFor={`project-name-${project.project_id}`}>Projektname ändern</label>
          <input id={`project-name-${project.project_id}`} maxLength={120} value={editing.name}
            onChange={event => { setEditing({ projectId: project.project_id, name: event.target.value }); setRenameError(""); }} disabled={renaming} required />
          {renameError && <span role="alert" className={styles.error}>{renameError}</span>}
          <div className={styles.renameActions}>
            <button className="button secondary" type="button" disabled={renaming} onClick={() => { setEditing(null); setRenameError(""); }}>Abbrechen</button>
            <button className="button primary" type="submit" disabled={renaming || !editing.name.trim()}>{renaming ? "Speichert …" : "Speichern"}</button>
          </div>
        </form>}
        <div className={styles.cardActions}>
          {editing?.projectId !== project.project_id && <button className={styles.renameButton} type="button" aria-label={`Projekt ${project.name || project.project_id} umbenennen`}
            disabled={deleting !== null || renaming} onClick={() => { setEditing({ projectId: project.project_id, name: project.name }); setRenameError(""); }}>
            Umbenennen
          </button>}
          <button className={styles.deleteButton} type="button" aria-label={`Projekt ${project.name || project.project_id} löschen`} disabled={deleting !== null || renaming} onClick={() => void remove(project)}>
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 10v7M14 10v7" /></svg>
            {deleting === project.project_id ? 'Wird gelöscht …' : 'Löschen'}
          </button>
        </div>
      </article>)}
    </div>
    {loading && <p role="status">Projekte werden geladen …</p>}
    {!loading && !error && filtered.length === 0 && <p>{term ? "Keine passenden Projekte in der geladenen Auswahl." : "Hier erscheint jedes angelegte Projekt als eigene Kachel."}</p>}
    {next !== null && <button className="button secondary" disabled={loading} onClick={() => void load(next)}>Weitere Projekte laden</button>}
  </section>;
}
