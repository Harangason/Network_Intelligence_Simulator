import { StudioTabs } from "@/components/studio-tabs";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";

export default async function StudioPage({
  searchParams,
}: {
  searchParams: Promise<{ mode?: string }>;
}) {
  const { mode } = await searchParams;
  const initialMode = mode === "network" ? "network" : "parameters";

  return (
    <main className="shell">
      <StudioTopbar />
      <WorkflowHeader />

      <section className="hero">
        <div>
          <p className="eyebrow">Workflow {initialMode === "network" ? "03" : "04"}</p>
          <h1>{initialMode === "network" ? "Technische Kommunikationspfade verbinden." : "Technologien und Timing konfigurieren."}</h1>
          <p className="hero-copy">
            {initialMode === "network"
              ? "Ordne logische Routen realen Bussen, Interfaces und Gateways zu."
              : "Pflege technologieabhängige Netzwerk-, Message-, QoS- und Gateway-Parameter."}
          </p>
        </div>
        <div className="hero-stat">
          <span>{initialMode === "network" ? "Schritt" : "Technologien"}</span>
          <strong>{initialMode === "network" ? "03" : "54"}</strong>
          <small>{initialMode === "network" ? "Connect" : "dynamische Schemata"}</small>
        </div>
      </section>

      <StudioTabs activeTab="simulation" initialMode={initialMode} />
    </main>
  );
}
