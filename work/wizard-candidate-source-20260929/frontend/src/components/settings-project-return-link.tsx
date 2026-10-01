"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { readActiveProjectId, SETTINGS_EVENT, withProjectParam } from "@/lib/user-settings";

export function SettingsProjectReturnLink({ initialProjectId }: { initialProjectId?: string }) {
  const [projectId, setProjectId] = useState(initialProjectId);

  useEffect(() => {
    const syncProject = () => setProjectId(readActiveProjectId());
    syncProject();
    window.addEventListener(SETTINGS_EVENT, syncProject);
    return () => window.removeEventListener(SETTINGS_EVENT, syncProject);
  }, []);

  return <Link className="button secondary" href={withProjectParam("/studio?mode=network", projectId)}>← Zum Projekt</Link>;
}
