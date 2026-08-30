"use client";

import Link from "next/link";
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import {
  assessIntelligence,
  createOptimizationProposal,
  getIntelligence,
  intelligenceExportUrl,
  listOptimizationProposals,
  reviewOptimizationProposal,
  type IntelligenceIssue,
  type IntelligenceRecommendation,
  type IntelligenceSnapshot,
  type OptimizationProposal,
} from "@/lib/workflow-api";
import {
  ENGINEERING_AGENT_OPEN_EVENT,
  queueEngineeringAgentTask,
} from "@/lib/agent-task-events";
import {
  engineeringObjectTypeClass,
  engineeringObjectTypeLabel,
} from "@/lib/engineering-object-style";
import { notifyWorkflowChanged } from "./workflow-header";
import { useWorkflowRefresh } from "@/lib/use-workflow-refresh";

type View = "overview" | "analytics" | "insights" | "knowledge";

const COUNT_LABELS: Record<string, string> = {
  nodes: "Nodes", networks: "Networks", routes: "Routes", messages: "Messages", signals: "Signals",
  routing_errors: "Routing Errors", timing_violations: "Timing Violations", capacity_warnings: "Capacity Warnings",
  unmapped_signals: "Unmapped Signals", simulation_failures: "Simulation Failures",
};

const METRIC_LABELS: Record<string, string> = {
  routing_coverage: "Routing Coverage", signal_coverage: "Signal Coverage",
  interface_completeness: "Interface Completeness", network_reachability: "Network Reachability",
  validation_pass_rate: "Validation Pass Rate", timing_compliance: "Timing Compliance",
  capacity_reserve: "Capacity Reserve", simulation_pass_rate: "Simulation Pass Rate",
  data_quality: "Data Quality", requirement_coverage: "Requirement Coverage",
};

export function IntelligenceWorkbench() {
  const [snapshot, setSnapshot] = useState<IntelligenceSnapshot | null>(null);
  const [proposals, setProposals] = useState<OptimizationProposal[]>([]);
  const [view, setView] = useState<View>("overview");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      let next: IntelligenceSnapshot;
      try {
        next = await getIntelligence();
      } catch {
        next = await assessIntelligence();
        notifyWorkflowChanged();
      }
      const governed = await listOptimizationProposals();
      setSnapshot(next);
      setProposals(governed.items);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Intelligence-Bewertung nicht verfügbar.");
    } finally {
      setLoading(false);
    }
  }, []);

  useWorkflowRefresh(load);

  async function recalculate() {
    setBusy(true);
    try {
      setSnapshot(await assessIntelligence());
      notifyWorkflowChanged();
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Bewertung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  async function persistRecommendation(item: IntelligenceRecommendation) {
    setBusy(true);
    try {
      const created = await createOptimizationProposal(item);
      setProposals((current) => [created, ...current]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Vorschlag konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  }

  async function reviewProposal(id: string, status: OptimizationProposal["status"]) {
    try {
      const next = await reviewOptimizationProposal(id, status);
      setProposals((current) => current.map((item) => item.proposal_id === id ? next : item));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Review konnte nicht gespeichert werden.");
    }
  }

  if (loading) return <section className="intelligence-workbench"><div className="analysis-empty"><span className="spinner" /><strong>Systemdaten werden korreliert</strong><p>Engineering-, Routing-, Graph- und Simulationsquellen werden versioniert ausgewertet.</p></div></section>;
  if (!snapshot) return <section className="intelligence-workbench"><div className="notice error">{error || "Keine Intelligence-Daten verfügbar."}</div><button className="button primary" onClick={() => void load()} type="button">Erneut laden</button></section>;

  const results = snapshot.results;
  return (
    <section className="intelligence-workbench">
      <header className="intelligence-toolbar">
        <div>
          <p className="eyebrow">09 Intelligence</p>
          <h2>Gesamtsystem-Bewertung</h2>
          <p>Snapshot {snapshot.id.slice(0, 8)} · {new Date(snapshot.created_at).toLocaleString("de-DE")}</p>
        </div>
        <div className="analysis-actions">
          <a className="button secondary" download href={intelligenceExportUrl("csv")}>CSV</a>
          <a className="button secondary" download href={intelligenceExportUrl("json")}>JSON</a>
          <button className="button primary" disabled={busy} onClick={() => void recalculate()} type="button">Neu bewerten</button>
        </div>
      </header>

      {snapshot.is_outdated && <div className="workflow-blocker warning"><strong>OUTDATED</strong><span>{snapshot.outdated_reason}</span><button className="button secondary tiny" onClick={() => void recalculate()} type="button">Aktualisieren</button></div>}
      {error && <div className="notice error">{error}</div>}

      <nav aria-label="Intelligence-Bereiche" className="intelligence-tabs" role="tablist">
        {(["overview", "analytics", "insights", "knowledge"] as View[]).map((item) => (
          <button aria-selected={view === item} className={view === item ? "active" : ""} key={item} onClick={() => setView(item)} role="tab" type="button">{item === "overview" ? "Overview" : item === "analytics" ? "Analytics" : item === "insights" ? "Insights" : "Knowledge"}</button>
        ))}
      </nav>

      {view === "overview" && <Overview onCreate={persistRecommendation} proposals={proposals} snapshot={snapshot} />}
      {view === "analytics" && <Analytics snapshot={snapshot} />}
      {view === "insights" && <Insights onCreate={persistRecommendation} proposals={proposals} onReview={reviewProposal} snapshot={snapshot} />}
      {view === "knowledge" && <Knowledge snapshot={snapshot} />}
    </section>
  );
}

function Overview({ snapshot, proposals, onCreate }: { snapshot: IntelligenceSnapshot; proposals: OptimizationProposal[]; onCreate(item: IntelligenceRecommendation): Promise<void> }) {
  const { system_health: health, maturity, critical_issues: issues } = snapshot.results;
  return (
    <div className="intelligence-view">
      <div className="intelligence-kpi-band">
        <div className="intelligence-health-score"><span>System Health</span><strong>{health.score.toFixed(0)}</strong><small>von 100</small></div>
        <dl className="intelligence-counts">{Object.entries(health.counts).map(([key, value]) => <div className={key.includes("error") || key.includes("violation") || key.includes("failure") ? "attention" : ""} key={key}><dt>{COUNT_LABELS[key] ?? label(key)}</dt><dd>{value.toLocaleString("de-DE")}</dd></div>)}</dl>
      </div>

      <div className="intelligence-overview-grid">
        <section className="intelligence-section">
          <div className="section-heading"><div><p className="eyebrow">System health</p><h3>Coverage & Compliance</h3></div></div>
          <div className="score-list">{Object.entries(health.metrics).map(([name, value]) => <ScoreBar key={name} label={METRIC_LABELS[name] ?? label(name)} value={value} />)}</div>
        </section>
        <section className="intelligence-section">
          <div className="section-heading"><div><p className="eyebrow">Maturity</p><h3>{maturity.level} {maturity.level_name}</h3></div><strong>{maturity.overall_score.toFixed(0)} %</strong></div>
          <div className="score-list compact">{Object.entries(maturity.dimensions).map(([name, value]) => <ScoreBar key={name} label={name} value={value} />)}</div>
          <div className="maturity-target"><span>Nächstes Ziel</span><strong>{maturity.target_level} {maturity.target_level_name}</strong><small>{maturity.gaps[0] ? `${maturity.gaps[0].dimension}: ${maturity.gaps[0].gap.toFixed(1)} Punkte fehlen` : "Kriterien erfüllt"}</small></div>
        </section>
      </div>

      <IssueTable issues={issues} onCreate={onCreate} proposals={proposals} />
    </div>
  );
}

function Analytics({ snapshot }: { snapshot: IntelligenceSnapshot }) {
  const data = snapshot.results;
  const requirements = arrayOfRecords(data.capacity_timing_analytics.requirements);
  const correlations = data.correlations;
  return (
    <div className="intelligence-view">
      <div className="intelligence-analytics-grid">
        <AnalyticsSummary eyebrow="Routing" title="Logical paths" data={data.routing_analytics} link="/studio/routing" />
        <AnalyticsSummary eyebrow="Network" title="Graph topology" data={data.network_analytics} link="/studio?mode=network" />
        <AnalyticsSummary eyebrow="Data Quality" title="Engineering data" data={data.data_quality} link="/studio/engineering" />
      </div>
      <section className="intelligence-section full">
        <div className="section-heading"><div><p className="eyebrow">Capacity & Timing</p><h3>Requirement deviations</h3></div><Link className="button secondary tiny" href="/studio/capacity">Capacity öffnen</Link></div>
        <div className="analysis-table-wrap"><table className="analysis-table"><thead><tr><th>Bereich</th><th>Objekt</th><th>Messgröße</th><th>Ist</th><th>Anforderung</th><th>Abweichung</th><th>Severity</th></tr></thead><tbody>{requirements.map((row, index) => <tr key={`${row.object_id}-${index}`}><td>{String(row.category)}</td><td>{String(row.object_id)}</td><td>{String(row.metric)}</td><td>{formatValue(row.current_value)}</td><td>{formatValue(row.requirement)}</td><td>{formatValue(row.deviation)}</td><td><Status value={String(row.severity)} /></td></tr>)}</tbody></table></div>
      </section>
      <section className="intelligence-section full">
        <div className="section-heading"><div><p className="eyebrow">Cross-domain correlation</p><h3>Zusammenhänge, nicht Kausalität</h3></div></div>
        <div className="correlation-grid">{correlations.map((item, index) => <div key={`${item.metric_pair}-${index}`}><span>{String(item.metric_pair)}</span><strong>{item.coefficient == null ? "n/a" : Number(item.coefficient).toFixed(2)}</strong><small>n={String(item.sample_size)} · {String(item.status)}</small></div>)}</div>
      </section>
    </div>
  );
}

function Insights({ snapshot, proposals, onCreate, onReview }: { snapshot: IntelligenceSnapshot; proposals: OptimizationProposal[]; onCreate(item: IntelligenceRecommendation): Promise<void>; onReview(id: string, status: OptimizationProposal["status"]): Promise<void> }) {
  const { anomalies, root_causes: rootCauses, trends, recommendations } = snapshot.results;
  return (
    <div className="intelligence-view">
      <section className="intelligence-section full">
        <div className="section-heading"><div><p className="eyebrow">Recommendations</p><h3>Priorisierte Verbesserungen</h3></div><span className="governance-note">Proposal → Review → Approval</span></div>
        <div className="recommendation-list">{recommendations.map((item, index) => <article key={item.candidate_id}><div className="recommendation-priority"><span>Priority {index + 1}</span><strong>{item.priority}</strong></div><div><h4>{item.problem}</h4><p>{item.recommendation}</p><small>{item.category} · Confidence {(item.confidence * 100).toFixed(0)} % · Effort {item.implementation_effort}</small></div><div className="recommendation-actions"><button className="button secondary tiny" onClick={() => askAgent(buildRecommendationAgentPrompt(item))} type="button">Ask AI</button><button className="button primary tiny" disabled={proposals.some((proposal) => proposal.problem === item.problem)} onClick={() => void onCreate(item)} type="button">Create Proposal</button></div></article>)}</div>
      </section>

      {!!proposals.length && <section className="intelligence-section full"><div className="section-heading"><div><p className="eyebrow">Proposal governance</p><h3>Human Review</h3></div></div><div className="proposal-list">{proposals.map((item) => <article key={item.proposal_id}><div><Status value={item.status} /><h4>{item.problem}</h4><p>{item.recommendation}</p></div><div className="recommendation-actions"><button className="button secondary tiny" disabled={item.status !== "PROPOSED"} onClick={() => void onReview(item.proposal_id, "UNDER_REVIEW")} type="button">Review</button><button className="button primary tiny" disabled={!(["PROPOSED", "UNDER_REVIEW"] as string[]).includes(item.status)} onClick={() => void onReview(item.proposal_id, "ACCEPTED")} type="button">Accept</button><button className="button danger tiny" disabled={!(["PROPOSED", "UNDER_REVIEW"] as string[]).includes(item.status)} onClick={() => void onReview(item.proposal_id, "REJECTED")} type="button">Reject</button></div></article>)}</div></section>}

      <div className="intelligence-overview-grid">
        <section className="intelligence-section"><div className="section-heading"><div><p className="eyebrow">Anomaly Detection</p><h3>{anomalies.length} Auffälligkeiten</h3></div></div><div className="compact-record-list">{anomalies.slice(0, 12).map((item, index) => <div key={`${item.object_id}-${index}`}><Status value="ANOMALY" /><strong>{String(item.name ?? item.object_id)}</strong><span>{String(item.category)} · {formatValue(item.current_value)} vs {formatValue(item.reference_value)}</span><small>{String(item.impact)}</small></div>)}</div></section>
        <section className="intelligence-section"><div className="section-heading"><div><p className="eyebrow">Root Cause</p><h3>Dependency chains</h3></div></div><div className="compact-record-list">{rootCauses.slice(0, 12).map((item, index) => <div key={`${item.issue_code}-${index}`}><strong>{String(item.issue_code)}</strong><span>{String(item.most_likely_cause)}</span><small>{arrayOfStrings(item.dependency_chain).join(" → ")}</small></div>)}</div></section>
      </div>

      <section className="intelligence-section full"><div className="section-heading"><div><p className="eyebrow">Trends & Comparison</p><h3>{label(trends.direction)}</h3></div></div><div className="analysis-table-wrap"><table className="analysis-table"><thead><tr><th>Zeit</th><th>Typ</th><th>Status</th><th>Routen</th><th>Fehler</th><th>Peak Load</th><th>Maturity</th></tr></thead><tbody>{trends.points.slice(-15).reverse().map((item, index) => <tr key={`${item.id}-${index}`}><td>{item.created_at ? new Date(String(item.created_at)).toLocaleString("de-DE") : "—"}</td><td>{String(item.kind ?? "—")}</td><td><Status value={String(item.status ?? "—")} /></td><td>{formatValue(item.routes)}</td><td>{formatValue(item.errors)}</td><td>{formatValue(item.peak_load)}</td><td>{formatValue(item.maturity)}</td></tr>)}</tbody></table></div></section>
    </div>
  );
}

function Knowledge({ snapshot }: { snapshot: IntelligenceSnapshot }) {
  const { rag_knowledge_insights: rag, graph_insights: graph, maturity } = snapshot.results;
  return (
    <div className="intelligence-view">
      <div className="intelligence-overview-grid">
        <section className="intelligence-section"><div className="section-heading"><div><p className="eyebrow">Hybrid RAG</p><h3>Retrieved Evidence</h3></div></div><div className="knowledge-list">{rag.map((item, index) => <article className={`eng-object-surface ${engineeringObjectTypeClass(item.object_type)}`} key={`${item.object_id}-${index}`}><span className={`eng-object-badge ${engineeringObjectTypeClass(item.object_type)}`}>{engineeringObjectTypeLabel(item.object_type ?? "Knowledge")}</span><strong>{String(item.text ?? item.object_id)}</strong><small>{String(item.source_id ?? "canonical-model")} · Score {formatValue(item.score)}</small></article>)}{!rag.length && <p className="muted">Für die aktuellen Befunde wurde keine zusätzliche Knowledge-Evidence gefunden.</p>}</div></section>
        <section className="intelligence-section"><div className="section-heading"><div><p className="eyebrow">Knowledge Graph</p><h3>Structural insights</h3></div><Link className="button secondary tiny" href="/studio/engineering">Modell öffnen</Link></div><RecordList data={graph} /></section>
      </div>
      <section className="intelligence-section full"><div className="section-heading"><div><p className="eyebrow">Maturity criteria</p><h3>Konfigurierbare, deterministische Regeln</h3></div></div><div className="criteria-list">{Object.entries(maturity.criteria).map(([levelName, criterion]) => <div className={levelName === maturity.level ? "active" : ""} key={levelName}><strong>{levelName}</strong><span>{criterion}</span></div>)}</div></section>
    </div>
  );
}

function IssueTable({ issues, proposals, onCreate }: { issues: IntelligenceIssue[]; proposals: OptimizationProposal[]; onCreate(item: IntelligenceRecommendation): Promise<void> }) {
  const pageSize = 30;
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("ALL");
  const [category, setCategory] = useState("ALL");
  const [sort, setSort] = useState("severity");
  const [group, setGroup] = useState("none");
  const [page, setPage] = useState(0);
  const [expanded, setExpanded] = useState("");
  const categories = useMemo(() => [...new Set(issues.map((item) => item.category))].sort(), [issues]);
  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    const rank = { ERROR: 0, WARNING: 1, INFO: 2 };
    return issues.filter((item) => (severity === "ALL" || item.severity === severity) && (category === "ALL" || item.category === category) && (!query || JSON.stringify(item).toLowerCase().includes(query))).sort((left, right) => {
      if (group === "category" && left.category !== right.category) return left.category.localeCompare(right.category);
      if (group === "severity" && left.severity !== right.severity) return rank[left.severity] - rank[right.severity];
      if (sort === "object") return left.object_id.localeCompare(right.object_id);
      if (sort === "category") return left.category.localeCompare(right.category);
      return rank[left.severity] - rank[right.severity];
    });
  }, [category, group, issues, search, severity, sort]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const visible = filtered.slice(page * pageSize, (page + 1) * pageSize);
  useEffect(() => { setPage(0); }, [category, group, search, severity, sort]);
  useEffect(() => { if (page >= pageCount) setPage(pageCount - 1); }, [page, pageCount]);
  return (
    <section className="intelligence-section full issue-table-section">
      <div className="section-heading"><div><p className="eyebrow">Critical issues</p><h3>Technische Problemübersicht</h3></div><span>{filtered.length} von {issues.length}</span></div>
      <div className="table-controls"><label><span>Suche</span><input onChange={(event) => setSearch(event.target.value)} placeholder="Objekt, Ursache, Code ..." value={search} /></label><label><span>Severity</span><select onChange={(event) => setSeverity(event.target.value)} value={severity}><option>ALL</option><option>ERROR</option><option>WARNING</option><option>INFO</option></select></label><label><span>Kategorie</span><select onChange={(event) => setCategory(event.target.value)} value={category}><option>ALL</option>{categories.map((item) => <option key={item}>{item}</option>)}</select></label><label><span>Sortieren</span><select onChange={(event) => setSort(event.target.value)} value={sort}><option value="severity">Severity</option><option value="category">Kategorie</option><option value="object">Objekt</option></select></label><label><span>Gruppieren</span><select onChange={(event) => setGroup(event.target.value)} value={group}><option value="none">Keine</option><option value="severity">Severity</option><option value="category">Kategorie</option></select></label></div>
      <div className="analysis-table-wrap"><table className="analysis-table issue-table"><thead><tr><th>Severity</th><th>Category</th><th>Object</th><th>Problem</th><th>Detected Cause</th><th>Affected</th><th>Recommendation</th><th>Aktionen</th></tr></thead><tbody>{visible.map((item, index) => { const rowKey = `${item.code}-${item.object_id}-${index}`; return <Fragment key={rowKey}><tr><td><Status value={item.severity} /></td><td>{item.category}</td><td><strong>{item.object_id}</strong><small className={`eng-object-badge ${engineeringObjectTypeClass(item.object_type)}`}>{engineeringObjectTypeLabel(item.object_type)}</small></td><td>{item.problem}<small>{item.code}</small></td><td>{item.detected_cause}</td><td>{item.affected_objects.length}</td><td>{item.recommendation}</td><td><div className="table-actions"><Link className="button secondary tiny" href={objectLink(item)}>{item.object_type === "RoutingEntry" ? "Open Route" : "Open Object"}</Link><Link className="button secondary tiny" href="/studio?mode=network">Open Network</Link><button className="button secondary tiny" onClick={() => setExpanded((current) => current === rowKey ? "" : rowKey)} type="button">Evidence</button><Link className="button secondary tiny" href={`/studio/engineering?graph=${encodeURIComponent(item.object_id)}`}>Graph</Link><button className="button secondary tiny" onClick={() => askAgent(buildIssueAgentPrompt(item))} type="button">Ask AI</button><button className="button primary tiny" disabled={proposals.some((proposal) => proposal.problem === item.problem)} onClick={() => void onCreate(recommendationFromIssue(item))} type="button">Create Proposal</button></div></td></tr>{expanded === rowKey && <tr className="issue-evidence-row"><td colSpan={8}><strong>Evidence & Provenance</strong><pre>{JSON.stringify({ evidence: item.evidence, affected_objects: item.affected_objects, cause: item.detected_cause }, null, 2)}</pre></td></tr>}</Fragment>; })}</tbody></table></div>
      <footer className="table-pagination"><span>{filtered.length ? `${page * pageSize + 1}-${Math.min((page + 1) * pageSize, filtered.length)} von ${filtered.length}` : "Keine Treffer"}</span><div><button className="button secondary tiny" disabled={page === 0} onClick={() => setPage((current) => Math.max(0, current - 1))} type="button">Zurück</button><span>Seite {page + 1} / {pageCount}</span><button className="button secondary tiny" disabled={page + 1 >= pageCount} onClick={() => setPage((current) => Math.min(pageCount - 1, current + 1))} type="button">Weiter</button></div></footer>
    </section>
  );
}

function AnalyticsSummary({ eyebrow, title, data, link }: { eyebrow: string; title: string; data: Record<string, unknown>; link: string }) {
  return <section className="intelligence-section"><div className="section-heading"><div><p className="eyebrow">{eyebrow}</p><h3>{title}</h3></div><Link className="button secondary tiny" href={link}>Öffnen</Link></div><RecordList data={data} /></section>;
}

function RecordList({ data }: { data: Record<string, unknown> }) {
  const rows = Object.entries(data).filter(([, value]) => !Array.isArray(value) || value.length < 20).slice(0, 12);
  return <dl className="overview-list">{rows.map(([key, value]) => <div key={key}><dt>{label(key)}</dt><dd>{Array.isArray(value) ? value.length : typeof value === "object" ? Object.keys(value as object).length : formatValue(value)}</dd></div>)}</dl>;
}

function ScoreBar({ label: barLabel, value }: { label: string; value: number }) {
  return <div className="score-row"><div><span>{barLabel}</span><strong>{value.toFixed(1)} %</strong></div><div className="score-track"><i style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></div></div>;
}

function Status({ value }: { value: string }) {
  const normalized = value.toLowerCase().replaceAll("_", "-");
  return <span className={`intelligence-status status-${normalized}`}>{value}</span>;
}

function objectLink(issue: IntelligenceIssue) {
  if (issue.object_type === "RoutingEntry" || issue.category === "Routing") return `/studio/routing?route=${encodeURIComponent(issue.object_id)}`;
  if (issue.object_type === "Network" || issue.category === "Network" || issue.category === "Graph") return "/studio?mode=network";
  if (issue.category.includes("Capacity") || issue.category === "Timing") return "/studio/capacity";
  return `/studio/engineering?object=${encodeURIComponent(issue.object_id)}`;
}

function recommendationFromIssue(issue: IntelligenceIssue): IntelligenceRecommendation {
  const priority = issue.severity === "ERROR" ? 85 : issue.severity === "WARNING" ? 60 : 35;
  return {
    candidate_id: `REC-${issue.code}-${issue.object_id.slice(0, 8)}`,
    category: issue.category,
    problem: issue.problem,
    affected_objects: issue.affected_objects.length ? issue.affected_objects : [issue.object_id],
    recommendation: issue.recommendation,
    expected_impact: { risk_reduction: issue.severity === "ERROR" ? "HIGH" : "MEDIUM", requires_revalidation: true },
    evidence: issue.evidence,
    graph_context: [{ object_type: issue.object_type, object_id: issue.object_id }],
    rag_context: [],
    confidence: issue.evidence.length ? 0.9 : 0.7,
    priority,
    priority_factors: { severity: priority, affected_objects: issue.affected_objects.length },
    implementation_effort: "MEDIUM",
    status: "CANDIDATE",
    governance: "Validate -> Human Review -> Approval",
  };
}

function buildIssueAgentPrompt(issue: IntelligenceIssue) {
  return [
    "Analysiere diesen Intelligence-Befund als Engineering-Agent.",
    "Nutze die verfügbaren Simulator-Tools, prüfe Status, Graph-/Netzwerk-Kontext und Evidence, und erkläre präzise, wie der Befund entstehen konnte.",
    "Bewerte danach konkrete Verbesserungen. Wenn das Modell wirklich lückenhaft ist, lege einen OptimizationProposal-Kandidaten mit klarer Begründung zur Human-Review an; ändere keine Engineering-Daten ohne Review.",
    "",
    `Befund-Code: ${issue.code}`,
    `Severity: ${issue.severity}`,
    `Kategorie: ${issue.category}`,
    `Objekt: ${issue.object_type} ${issue.object_id}`,
    `Problem: ${issue.problem}`,
    `Erkannte Ursache: ${issue.detected_cause}`,
    `Empfehlung der deterministischen Analyse: ${issue.recommendation}`,
    `Betroffene Objekte: ${issue.affected_objects.length ? issue.affected_objects.join(", ") : issue.object_id}`,
    `Evidence: ${JSON.stringify(issue.evidence).slice(0, 1800)}`,
  ].join("\n");
}

function buildRecommendationAgentPrompt(item: IntelligenceRecommendation) {
  return [
    "Bewerte diese Intelligence-Empfehlung als Engineering-Agent.",
    "Prüfe Evidence, Graph-Kontext und Umsetzungsrisiko. Erkläre, ob der Vorschlag technisch sinnvoll ist, und lege bei belastbarer Evidence einen OptimizationProposal-Kandidaten zur Human-Review an.",
    "",
    `Kategorie: ${item.category}`,
    `Problem: ${item.problem}`,
    `Empfehlung: ${item.recommendation}`,
    `Priorität: ${item.priority}`,
    `Confidence: ${(item.confidence * 100).toFixed(0)} %`,
    `Effort: ${item.implementation_effort}`,
    `Betroffene Objekte: ${item.affected_objects.join(", ")}`,
    `Evidence: ${JSON.stringify(item.evidence).slice(0, 1800)}`,
    `Graph-Kontext: ${JSON.stringify(item.graph_context).slice(0, 1200)}`,
  ].join("\n");
}

function askAgent(question: string) {
  window.dispatchEvent(new CustomEvent(ENGINEERING_AGENT_OPEN_EVENT));
  queueEngineeringAgentTask(question);
}

function arrayOfRecords(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object") : [];
}

function arrayOfStrings(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return Number.isInteger(value) ? value.toLocaleString("de-DE") : value.toFixed(2);
  return String(value);
}
