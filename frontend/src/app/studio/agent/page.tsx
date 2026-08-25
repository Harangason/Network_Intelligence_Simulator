import Link from "next/link";
import { StudioTabs } from "@/components/studio-tabs";
import { RuntimeStatus } from "@/components/runtime-status";

export default function AgentPage() {
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
          <p className="eyebrow">Engineering-Agent</p>
          <h1>Mit dem Netzwerkmodell im Dialog arbeiten.</h1>
          <p className="hero-copy">
            Frage nach Hardware-Knoten, Interfaces oder Signalen und lass den
            Agenten Vorschläge für neue Engineering-Objekte erarbeiten.
          </p>
        </div>
        <div className="hero-stat">
          <span>Modell</span>
          <strong>KI</strong>
          <small>Vercel AI Gateway</small>
        </div>
      </section>

      <StudioTabs activeTab="agent" initialMode="parameters" />
    </main>
  );
}
