import { CapacityWorkbench } from "@/components/capacity-workbench";
import { StudioWorkflowHero } from "@/components/studio-workflow-hero";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";
import { projectIdFromSearchParams, type ProjectQueryRecord } from "@/lib/user-settings";

export default async function CapacityPage({
  searchParams,
}: {
  searchParams: Promise<ProjectQueryRecord>;
}) {
  const initialProjectId = projectIdFromSearchParams(await searchParams);
  return (
    <main className="shell studio-shell workflow-shell">
      <StudioTopbar initialProjectId={initialProjectId} />
      <WorkflowHeader initialProjectId={initialProjectId} />
      <StudioWorkflowHero eyebrow="Workflow 05" initialProjectId={initialProjectId} title="Kapazität und Timing vor dem Lauf verstehen.">
        Buslast, Peak/Burst Load, Reserve, Queueing, Gateway-Last und End-to-End-Latenz werden versioniert berechnet.
      </StudioWorkflowHero>
      <CapacityWorkbench initialProjectId={initialProjectId} />
    </main>
  );
}
