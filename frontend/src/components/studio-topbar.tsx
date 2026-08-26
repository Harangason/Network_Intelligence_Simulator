"use client";

import Link from "next/link";
import { ProjectActions } from "@/components/project-actions";
import { RuntimeStatus } from "@/components/runtime-status";

export function StudioTopbar() {
  return (
    <header className="topbar">
      <Link className="brand" href="/">
        <span className="brand-mark" aria-hidden="true">CS</span>
        <div>
          <strong>Communication Simulator</strong>
          <span>Network trace studio</span>
        </div>
      </Link>
      <div className="topbar-actions">
        <ProjectActions />
        <Link className="topbar-link" href="/studio/settings">Einstellungen</Link>
        <RuntimeStatus />
      </div>
    </header>
  );
}
