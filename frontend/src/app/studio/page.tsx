import Link from "next/link";
import { SimulationWizard } from "@/components/simulation-wizard";
import { RuntimeStatus } from "@/components/runtime-status";

export default async function StudioPage({
  searchParams,
}: {
  searchParams: Promise<{ mode?: string }>;
}) {
  const { mode } = await searchParams;
  const initialMode = mode === "network" ? "network" : "parameters";

  return (
    <main className="shell">
      <header className="topbar">
        <Link className="brand" href="/">
          <span className="brand-mark" aria-hidden="true">
            CS
          </span>
          <div>
            <strong>Communication Simulator</strong>
            <span>Network trace studio</span>
          </div>
        </Link>
        <RuntimeStatus />
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

      <SimulationWizard initialMode={initialMode} />
    </main>
  );
}
