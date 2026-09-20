export const STUDIO_THEME_STORAGE_KEY = "network-simulator:studio-theme";
export const STUDIO_THEME_EVENT = "network-simulator:studio-theme-changed";

export type StudioTheme = "dark" | "light";

export function normalizeStudioTheme(value: unknown): StudioTheme | null {
  return value === "dark" || value === "light" ? value : null;
}

export function readStudioTheme(storage?: Pick<Storage, "getItem">): StudioTheme {
  if (!storage) return "dark";
  return normalizeStudioTheme(storage.getItem(STUDIO_THEME_STORAGE_KEY)) ?? "dark";
}

export function applyStudioTheme(theme: StudioTheme, root: HTMLElement = document.documentElement) {
  root.dataset.theme = theme;
  root.style.colorScheme = theme;

  const themeColor = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
  if (themeColor) themeColor.content = theme === "light" ? "#f4f7f9" : "#080b0f";
}

export function persistStudioTheme(theme: StudioTheme) {
  applyStudioTheme(theme);
  window.localStorage.setItem(STUDIO_THEME_STORAGE_KEY, theme);
  window.dispatchEvent(new CustomEvent<StudioTheme>(STUDIO_THEME_EVENT, { detail: theme }));
}
