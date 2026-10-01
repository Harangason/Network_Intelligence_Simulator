"use client";

import type { ReactNode } from "react";
import { useEffect, useId, useState } from "react";

import { WorkflowStatusOverview } from "@/components/workflow-status-overview";
import { readUserSettings, SETTINGS_EVENT, type UserSettings } from "@/lib/user-settings";

export function StudioWorkflowHero({
  eyebrow,
  title,
  children,
  className = "",
  initialProjectId = "",
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
  className?: string;
  initialProjectId?: string;
}) {
  const contentId = useId();
  const [collapsed, setCollapsed] = useState(true);

  useEffect(() => {
    setCollapsed(readUserSettings().collapseWorkflowHeroes);
    const handleSettings = (event: Event) => {
      setCollapsed((event as CustomEvent<UserSettings>).detail.collapseWorkflowHeroes);
    };
    window.addEventListener(SETTINGS_EVENT, handleSettings);
    return () => window.removeEventListener(SETTINGS_EVENT, handleSettings);
  }, []);

  return (
    <section className={`hero studio-workflow-hero ${collapsed ? "collapsed" : "expanded"} ${className}`.trim()}>
      <div className="studio-workflow-hero-heading">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {!collapsed && <p className="hero-copy" id={contentId}>{children}</p>}
      </div>
      <button
        aria-expanded={!collapsed}
        className="studio-workflow-hero-toggle"
        onClick={() => setCollapsed((current) => !current)}
        type="button"
      >
        <span>{collapsed ? "Übersicht aufklappen" : "Übersicht zuklappen"}</span>
        <b aria-hidden="true">{collapsed ? "⌄" : "⌃"}</b>
      </button>
      {!collapsed && <div className="studio-workflow-hero-status">
        <WorkflowStatusOverview compact initialProjectId={initialProjectId} />
      </div>}
    </section>
  );
}
