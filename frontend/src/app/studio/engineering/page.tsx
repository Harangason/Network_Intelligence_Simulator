import { StudioTabs } from "@/components/studio-tabs";
import { StudioWorkflowHero } from "@/components/studio-workflow-hero";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";

export default function EngineeringPage() {
  return (
    <main className="shell">
      <StudioTopbar />
      <WorkflowHeader />

      <StudioWorkflowHero eyebrow="Engineering-Modell" title="Hardware, Interfaces und Signale verwalten.">
        Kanonische Objekte mit Governance-Feldern (Lifecycle, Review,
        Approval) sowie Relations für den Knowledge Graph.
      </StudioWorkflowHero>

      <StudioTabs activeTab="engineering" initialMode="parameters" />
    </main>
  );
}
