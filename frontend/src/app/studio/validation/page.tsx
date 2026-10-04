import { PreflightWorkbench } from "@/features/workflow/stage_06_validation/index.ts";
import { StudioWorkflowHero } from "@/features/workflow/ui/studio-workflow-hero";
import { StudioTopbar } from "@/features/workflow/ui/studio-topbar";
import { WorkflowHeader } from "@/features/workflow/ui/workflow-header";
import { projectIdFromSearchParams, type ProjectQueryRecord } from "@/features/settings/lib/user-settings";

export default async function ValidationPage({
  searchParams,
}: {
  searchParams: Promise<ProjectQueryRecord>;
}) {
  const initialProjectId = projectIdFromSearchParams(await searchParams);
  return (
    <main className="shell studio-shell workflow-shell">
      <StudioTopbar initialProjectId={initialProjectId} />
      <WorkflowHeader initialProjectId={initialProjectId} />
      <StudioWorkflowHero eyebrow="Workflow 06" initialProjectId={initialProjectId} title="Technische Konsistenz vor der Simulation prüfen.">
        ERROR blockiert. WARNING bleibt sichtbar und ist zulässig. Der Preflight bindet alle Quellversionen.
      </StudioWorkflowHero>
      <PreflightWorkbench initialProjectId={initialProjectId} />
    </main>
  );
}
