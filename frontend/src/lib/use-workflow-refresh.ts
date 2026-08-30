"use client";

import { useEffect } from "react";
import { SETTINGS_EVENT } from "./user-settings";

const WORKFLOW_CHANGED_EVENT = "workflow:changed";

export function useWorkflowRefresh(refresh: () => void | Promise<void>, intervalMs = 10_000) {
  useEffect(() => {
    const run = () => { void refresh(); };
    run();
    const interval = window.setInterval(run, intervalMs);
    window.addEventListener(WORKFLOW_CHANGED_EVENT, run);
    window.addEventListener(SETTINGS_EVENT, run);
    window.addEventListener("focus", run);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener(WORKFLOW_CHANGED_EVENT, run);
      window.removeEventListener(SETTINGS_EVENT, run);
      window.removeEventListener("focus", run);
    };
  }, [intervalMs, refresh]);
}
