import type { ReactNode } from "react";

import { WorkflowStatusOverview } from "@/components/workflow-status-overview";

export function StudioWorkflowHero({
  eyebrow,
  title,
  children,
  className = "",
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`hero studio-workflow-hero ${className}`.trim()}>
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="hero-copy">{children}</p>
      </div>
      <div className="studio-workflow-hero-status">
        <WorkflowStatusOverview compact />
      </div>
    </section>
  );
}
