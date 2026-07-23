import Link from "next/link";
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
        <Link className="back-link" href="/">
          ← Neue Simulation
        </Link>
        <span className="mono muted">{id}</span>
      </header>
      <SimulationResult jobId={id} standalone />
    </main>
  );
}
