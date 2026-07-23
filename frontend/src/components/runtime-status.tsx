"use client";

import { useEffect, useState } from "react";

export function RuntimeStatus() {
  const [mode, setMode] = useState<"checking" | "backend" | "browser">("checking");
  useEffect(() => {
    const update = (event: Event) => setMode((event as CustomEvent<"backend" | "browser">).detail);
    window.addEventListener("simulator-mode", update);
    return () => window.removeEventListener("simulator-mode", update);
  }, []);
  return <div className="system-state" aria-live="polite"><span className={`state-dot ${mode}`} />{mode === "checking" ? "Engine wird geprüft" : mode === "backend" ? "Python engine" : "Browser engine"}</div>;
}
