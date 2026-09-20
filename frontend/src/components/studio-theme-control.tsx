"use client";

import { useEffect, useState } from "react";
import {
  applyStudioTheme,
  normalizeStudioTheme,
  persistStudioTheme,
  readStudioTheme,
  STUDIO_THEME_EVENT,
  STUDIO_THEME_STORAGE_KEY,
  type StudioTheme,
} from "@/lib/studio-theme";

const THEMES: Array<{ value: StudioTheme; label: string }> = [
  { value: "light", label: "Hell" },
  { value: "dark", label: "Dunkel" },
];

export function StudioThemeControl() {
  const [theme, setTheme] = useState<StudioTheme>("dark");

  useEffect(() => {
    const current = normalizeStudioTheme(document.documentElement.dataset.theme) ?? readStudioTheme(window.localStorage);
    setTheme(current);
    applyStudioTheme(current);

    const handleStorage = (event: StorageEvent) => {
      if (event.key !== STUDIO_THEME_STORAGE_KEY) return;
      const next = normalizeStudioTheme(event.newValue) ?? "dark";
      setTheme(next);
      applyStudioTheme(next);
    };
    const handleThemeChange = (event: Event) => {
      const next = normalizeStudioTheme((event as CustomEvent<StudioTheme>).detail);
      if (next) setTheme(next);
    };

    window.addEventListener("storage", handleStorage);
    window.addEventListener(STUDIO_THEME_EVENT, handleThemeChange);
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener(STUDIO_THEME_EVENT, handleThemeChange);
    };
  }, []);

  function selectTheme(next: StudioTheme) {
    setTheme(next);
    persistStudioTheme(next);
  }

  return (
    <div className="studio-theme-control" role="group" aria-label="Erscheinungsbild">
      {THEMES.map((option) => (
        <button
          aria-pressed={theme === option.value}
          className={theme === option.value ? "active" : undefined}
          key={option.value}
          onClick={() => selectTheme(option.value)}
          type="button"
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
