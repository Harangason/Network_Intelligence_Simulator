"use client";

import { useEffect, useState } from "react";

export function RuntimeStatus() {
  const [mode, setMode] = useState<"checking" | "backend" | "browser">("checking");
  useEffect(() => {
    const update = (event: Event) => setMode((event as CustomEvent<"backend" | "browser">).detail);
    window.addEventListener("simulator-mode", update);
    const controller = new AbortController();
    fetch("/api/health", {
      cache: "no-store",
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(3000)]),
    })
      .then((response) => setMode(response.ok ? "backend" : "browser"))
      .catch(() => {
        if (!controller.signal.aborted) setMode("browser");
      });
    return () => {
      controller.abort();
      window.removeEventListener("simulator-mode", update);
    };
  }, []);
  return <div className="system-state" aria-live="polite"><span className={`state-dot ${mode}`} />{mode === "checking" ? "Engine wird geprüft" : mode === "backend" ? "Python engine" : "Browser engine"}</div>;
}
