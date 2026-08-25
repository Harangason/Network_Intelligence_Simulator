import Link from "next/link";
import { StudioTabs } from "@/components/studio-tabs";
import { RuntimeStatus } from "@/components/runtime-status";

export default function EngineeringPage() {
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
          <p className="eyebrow">Engineering-Modell</p>
          <h1>Hardware, Interfaces und Signale verwalten.</h1>
          <p className="hero-copy">
            Kanonische Objekte mit Governance-Feldern (Lifecycle, Review,
            Approval) sowie Relations für den Knowledge Graph.
          </p>
        </div>
        <div className="hero-stat">
          <span>Objekttypen</span>
          <strong>5</strong>
          <small>+ Relations</small>
        </div>
      </section>

      <StudioTabs activeTab="engineering" initialMode="parameters" />
    </main>
  );
}
