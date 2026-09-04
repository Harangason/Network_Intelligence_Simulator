import { ProjectAwareLink } from "@/components/marketing-shell";
import { SimulationResult } from "@/components/simulation-result";

export default async function SimulationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <main className="shell detail-shell">
      <header className="topbar">
        <ProjectAwareLink className="back-link" href="/studio">
          ← Neue Simulation
        </ProjectAwareLink>
        <span className="mono muted">{id}</span>
      </header>
      <SimulationResult jobId={id} standalone />
    </main>
  );
}
