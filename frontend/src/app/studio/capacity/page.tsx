import { CapacityWorkbench } from "@/features/workflow/stage_05_capacity_timing/index.ts";
import { StudioWorkflowHero } from "@/features/workflow/ui/studio-workflow-hero";
import { StudioTopbar } from "@/features/workflow/ui/studio-topbar";
import { WorkflowHeader } from "@/features/workflow/ui/workflow-header";
import { projectIdFromSearchParams, type ProjectQueryRecord } from "@/features/settings/lib/user-settings";

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
