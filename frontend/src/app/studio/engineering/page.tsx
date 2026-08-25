import { StudioTabs } from "@/components/studio-tabs";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";

export default function EngineeringPage() {
  return (
    <main className="shell">
      <StudioTopbar />
      <WorkflowHeader />

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
