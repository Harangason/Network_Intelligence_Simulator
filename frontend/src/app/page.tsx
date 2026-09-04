import { Arrow, LogoMark, MarketingFooter, MarketingNav, ProjectAwareLink } from "@/components/marketing-shell";

const features = [
  {
    index: "01",
    title: "Model",
    text: "Konfiguriere Protokolle, Topologien und physikalische Parameter in einem klaren Workspace.",
    visual: "nodes",
  },
  {
    index: "02",
    title: "Simulate",
    text: "Erzeuge deterministische Kommunikationsereignisse mit reproduzierbaren Seeds und Fehlermodellen.",
    visual: "signal",
  },
  {
    index: "03",
    title: "Inspect",
    text: "Validiere Hardwaregrenzen und exportiere jeden Lauf in universelle oder native Formate.",
    visual: "metrics",
  },
];

export default function Home() {
  return (
    <main className="landing">
      <MarketingNav />

      <section className="landing-hero" aria-labelledby="hero-title">
        <div className="hero-noise" aria-hidden="true" />
        <div className="hero-orbit" aria-hidden="true">
          <div className="orbit-ring orbit-ring-one" />
          <div className="orbit-ring orbit-ring-two" />
          <span className="orbit-node node-one" />
          <span className="orbit-node node-two" />
          <span className="orbit-node node-three" />
          <div className="orbit-core"><LogoMark /></div>
        </div>
        <div className="landing-hero-content">
          <p className="landing-kicker"><span /> Network systems, made observable</p>
          <h1 id="hero-title">Build signals.<br /><em>Understand systems.</em></h1>
          <p className="landing-intro">
            Eine offene Simulationsumgebung für moderne Kommunikation — vom ersten Knoten bis zum vollständigen Trace.
          </p>
          <div className="hero-actions">
            <ProjectAwareLink className="primary-link" href="/studio">Start simulating <Arrow /></ProjectAwareLink>
            <ProjectAwareLink className="primary-link trace-link" href="/trace-analysis">Start Trace Analyse <Arrow /></ProjectAwareLink>
            <ProjectAwareLink className="text-link" href="/platform">Explore the platform <Arrow /></ProjectAwareLink>
          </div>
        </div>
        <div className="hero-coordinates" aria-hidden="true">
          <span>SYS / 00.01</span><span>48° 08&apos; 19.4&quot; N</span>
        </div>
      </section>

      <section className="manifesto" id="about">
        <p className="section-label">What we believe</p>
        <p className="manifesto-copy">
          Complex systems should not feel like a black box. We turn communication into something you can <em>see, test and trust.</em>
        </p>
      </section>

      <section className="feature-section" id="platform" aria-labelledby="platform-title">
        <div className="section-header">
          <div>
            <p className="section-label">The platform</p>
            <h2 id="platform-title">From protocol to proof.</h2>
          </div>
          <p>One precise environment to design, run and inspect communication across industries.</p>
        </div>
        <div className="feature-grid">
          {features.map((feature) => (
            <article className="feature-card" key={feature.index}>
              <div className={`feature-visual ${feature.visual}`} aria-hidden="true">
                <FeatureVisual type={feature.visual} />
              </div>
              <div className="feature-copy">
                <span>{feature.index}</span>
                <div><h3>{feature.title}</h3><p>{feature.text}</p></div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="workflow" id="workflow" aria-labelledby="workflow-title">
        <div className="workflow-copy">
          <p className="section-label">Built for iteration</p>
          <h2 id="workflow-title">Go from an idea to a verified trace in minutes.</h2>
          <p>Choose a domain, tune the system, and let the simulation engine produce evidence you can work with.</p>
          <ProjectAwareLink className="text-link light" href="/studio">Enter the workspace <Arrow /></ProjectAwareLink>
        </div>
        <div className="console-card" aria-label="Beispiel eines Simulationslaufs">
          <div className="console-top"><span>trace_run_021</span><span>● LIVE</span></div>
          <div className="console-body">
            <p><span>01</span> domain&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; automotive</p>
            <p><span>02</span> protocol&nbsp;&nbsp;&nbsp; CAN_FD</p>
            <p><span>03</span> nodes&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 12</p>
            <p><span>04</span> duration&nbsp;&nbsp;&nbsp;&nbsp; 8.0s</p>
            <div className="console-rule" />
            <p className="console-success"><span>✓</span> 8,402 events generated</p>
            <p className="console-success"><span>✓</span> hardware validation passed</p>
          </div>
          <div className="console-chart" aria-hidden="true">
            {[32, 54, 38, 72, 61, 88, 48, 76, 56, 92, 68, 84, 44, 63, 79, 58, 96, 70].map((height, index) => (
              <i key={index} style={{ height: `${height}%` }} />
            ))}
          </div>
        </div>
      </section>

      <section className="landing-cta">
        <p className="section-label">Your system. In focus.</p>
        <h2>Ready to see what<br />your network is saying?</h2>
        <ProjectAwareLink className="primary-link dark" href="/studio">Launch simulator <Arrow /></ProjectAwareLink>
      </section>

      <MarketingFooter />
    </main>
  );
}

function FeatureVisual({ type }: { type: string }) {
  if (type === "nodes") return <><span className="fv-node n1">A</span><span className="fv-node n2">B</span><span className="fv-node n3">C</span><span className="fv-line l1" /><span className="fv-line l2" /><span className="fv-line l3" /></>;
  if (type === "signal") return <><div className="signal-track"><i /><i /><i /><i /><i /><i /><i /><i /></div><span className="signal-label">TX / 24.8 KBPS</span></>;
  return <><div className="metric-large">99.98<span>%</span></div><div className="metric-line"><i /><i /><i /><i /><i /><i /><i /><i /><i /></div><span className="signal-label">VALID EVENTS</span></>;
}
