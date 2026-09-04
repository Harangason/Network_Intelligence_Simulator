import { Arrow, MarketingShell, PageHero, ProjectAwareLink } from "@/components/marketing-shell";

const principles = [
  ["Observable", "Ein System ist erst verständlich, wenn seine Kommunikation sichtbar und untersuchbar wird."],
  ["Reproducible", "Deterministische Seeds und explizite Konfigurationen machen Ergebnisse nachvollziehbar."],
  ["Technology-open", "Gemeinsame Modelle verbinden Domänen, ohne spezifische Protokolle zu verwässern."],
];

export default function AboutPage() {
  return (
    <MarketingShell>
      <PageHero eyebrow="About the project" title="Complex systems." accent="Clear evidence." description="Communication Simulator ist ein offenes Engineering-Werkzeug für Menschen, die vernetzte Systeme entwerfen, prüfen und erklären." />
      <section className="about-statement"><p>Kommunikation verbindet jede moderne Maschine — und bleibt dennoch oft unsichtbar. Dieses Projekt macht aus abstrakten Protokollen konkrete Traces, überprüfbare Grenzen und portable Daten.</p></section>
      <section className="principle-grid">
        {principles.map(([title, text], index) => <article key={title}><span>0{index + 1}</span><h2>{title}</h2><p>{text}</p></article>)}
      </section>
      <section className="split-feature about-tech"><div><p className="section-label">How it is built</p><h2>Transparent from interface to engine.</h2></div><div className="about-facts"><div><span>Frontend</span><strong>Next.js / TypeScript</strong></div><div><span>Engine</span><strong>Python / Browser fallback</strong></div><div><span>Output</span><strong>JSONL / CSV / Native</strong></div><div><span>License model</span><strong>Open project</strong></div></div></section>
      <section className="page-cta"><p className="section-label">See it in operation</p><h2>Build signals. Understand systems.</h2><ProjectAwareLink className="primary-link" href="/studio">Launch simulator <Arrow /></ProjectAwareLink></section>
    </MarketingShell>
  );
}
