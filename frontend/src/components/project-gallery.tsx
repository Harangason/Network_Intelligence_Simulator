"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Arrow } from "./marketing-shell";
import { requestEngineeringAgentWizard } from "@/lib/agent-task-events";
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
      const stamp = new Date().toISOString().replace(/[-:T.Z]/g, "").slice(0, 17);
      const project = pendingProject.current ??= `network-project-${stamp}-${crypto.randomUUID().slice(0, 8)}`;
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
    {createError && <p role="alert" className={styles.error}>{createError} Die Plus-Kachel wiederholt dieselbe Projektanlage.</p>}
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
        <button className={styles.deleteButton} type="button" aria-label={`Projekt ${project.name || project.project_id} löschen`} disabled={deleting !== null} onClick={() => void remove(project)}>
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 10v7M14 10v7" /></svg>
          {deleting === project.project_id ? 'Wird gelöscht …' : 'Löschen'}
        </button>
      </article>)}
    </div>
    {loading && <p role="status">Projekte werden geladen …</p>}
    {!loading && !error && filtered.length === 0 && <p>{term ? "Keine passenden Projekte in der geladenen Auswahl." : "Hier erscheint jedes angelegte Projekt als eigene Kachel."}</p>}
    {next !== null && <button className="button secondary" disabled={loading} onClick={() => void load(next)}>Weitere Projekte laden</button>}
  </section>;
}
