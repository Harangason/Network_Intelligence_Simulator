import { StudioTabs } from "@/components/studio-tabs";
import { StudioWorkflowHero } from "@/components/studio-workflow-hero";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";
import { projectIdFromSearchParams, type ProjectQueryRecord } from "@/lib/user-settings";

export default async function EngineeringPage({
  searchParams,
}: {
  searchParams: Promise<ProjectQueryRecord>;
}) {
  const initialProjectId = projectIdFromSearchParams(await searchParams);
  return (
    <main className="shell studio-shell">
      <StudioTopbar initialProjectId={initialProjectId} />
      <WorkflowHeader initialProjectId={initialProjectId} />

      <StudioWorkflowHero eyebrow="Engineering-Modell" initialProjectId={initialProjectId} title="Hardware, Interfaces und Signale verwalten.">
        Kanonische Objekte mit Governance-Feldern (Lifecycle, Review,
        Approval) sowie Relations für den Knowledge Graph.
      </StudioWorkflowHero>

      <StudioTabs activeTab="engineering" initialMode="parameters" initialProjectId={initialProjectId} />
    </main>
  );
}
