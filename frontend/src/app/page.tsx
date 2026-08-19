import Link from "next/link";
import { SimulationWizard } from "@/components/simulation-wizard";

const highlights = [
  {
    title: "Offenheit",
    text: "Mehr als 50 Technologien direkt nutzbar, von CAN und Ethernet bis zu I2C, LIN, Modbus und TCP/IP.",
  },
  {
    title: "Schnellstart",
    text: "Parameter setzen, simulieren, validieren. Ein geschlossener Flow fuer schnelle erste Ergebnisse.",
  },
  {
    title: "Export ready",
    text: "Universelle Traces plus native Formate, damit du direkt mit Analyse-Tools weiterarbeiten kannst.",
  },
];

export default function Home() {
  return (
    <main className="shell landing-shell">
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
        <div className="landing-hero-content">
          <p className="eyebrow">Simulation workspace</p>
          <h1>
            Kommunikation modellieren.
            <br />
            Traces gezielt auswerten.
          </h1>
          <p className="hero-copy">
            Starte mit einem schlanken Frontend, definiere reale
            Kommunikationssysteme und erzeuge reproduzierbare Simulationsdaten
            fuer Tests, Validierung und Demos.
          </p>
          <div className="landing-actions">
            <a className="button primary" href="#simulation-start">
              Simulation starten
            </a>
            <Link className="button secondary" href="/simulations">
              Ergebnisse ansehen
            </Link>
          </div>
        </div>
        <div className="hero-mini">
          <span>Technologien</span>
          <strong>54</strong>
          <small>10 Domaenen · 50+ Protokolle</small>
        </div>
      </section>

      <section className="landing-highlights">
        {highlights.map((item) => (
          <article className="landing-card" key={item.title}>
            <h2>{item.title}</h2>
            <p>{item.text}</p>
          </article>
        ))}
      </section>

      <section className="landing-wizard" id="simulation-start">
        <SimulationWizard />
      </section>
    </main>
  );
}
