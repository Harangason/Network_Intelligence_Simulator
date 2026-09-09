"use client";

import { useEffect, useState } from "react";

export function RuntimeStatus() {
  const [mode, setMode] = useState<"checking" | "backend" | "browser">("checking");
  const [release, setRelease] = useState<{ id: string; mismatch: boolean } | null>(null);
  useEffect(() => {
    const update = (event: Event) => setMode((event as CustomEvent<"backend" | "browser">).detail);
    window.addEventListener("simulator-mode", update);
    const controller = new AbortController();
    const readBuild = async (url: string) => {
      const response = await fetch(url, { cache: "no-store", signal: controller.signal });
      if (!response.ok) throw new Error("Build-Kennung nicht verfügbar");
      return response.json() as Promise<{ build_id: string }>;
    };
    void readBuild("/api/build-info").then(async (backend) => {
      if (backend.build_id === "development") return;
      const frontendBuildId = process.env.NEXT_PUBLIC_NETWORKIS_BUILD_ID ?? "development";
      setRelease({ id: backend.build_id, mismatch: backend.build_id !== frontendBuildId });
    })
      .catch(() => { /* Development runs can omit the production manifest. */ });
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
  return <div className="system-state" aria-live="polite" title={release ? `Backend-Build ${release.id}${release.mismatch ? "; Frontend verwendet einen anderen Stand. Seite neu laden." : "; Frontend und Backend stimmen überein."}` : undefined}><span className={`state-dot ${mode}`} />{mode === "checking" ? "Engine wird geprüft" : mode === "backend" ? "Python engine" : "Browser engine"}{release && <small> · {release.mismatch ? "Build-Abweichung" : release.id}</small>}</div>;
}
