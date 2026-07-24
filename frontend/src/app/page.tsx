import { SimulationWizard } from "@/components/simulation-wizard";

export default function Home() {
  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            CS
          </span>
          <div>
            <strong>Communication Simulator</strong>
            <span>Network trace studio</span>
          </div>
        </div>
        <div className="system-state">
          <span className="state-dot" />
          Local workspace
        </div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">Simulation workspace</p>
          <h1>Kommunikation modellieren. Trace-Pakete erzeugen.</h1>
          <p className="hero-copy">
            Konfiguriere technologieoffene Netzwerke, validiere Hardware und
            exportiere universelle oder native Kommunikationsformate.
          </p>
        </div>
        <div className="hero-stat">
          <span>Technologien</span>
          <strong>54</strong>
          <small>10 Anwendungsbereiche</small>
        </div>
      </section>

      <SimulationWizard />
    </main>
  );
}
