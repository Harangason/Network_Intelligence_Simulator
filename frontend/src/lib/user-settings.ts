export type UserSettings = {
  activeProject: string;
  automaticModelSync: boolean;
  openAgentOnStart: boolean;
};

export const DEFAULT_USER_SETTINGS: UserSettings = {
  activeProject: "default",
  automaticModelSync: true,
  openAgentOnStart: false,
};

const STORAGE_KEY = "communication-simulator:settings:v1";
export const SETTINGS_EVENT = "communication-simulator:settings-changed";
const PROJECT_QUERY_KEYS = ["project_id", "projectId"];

export function normalizeProjectId(value: unknown): string {
  const normalized = String(value ?? "")
    .trim()
    .replace(/[^a-zA-Z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
  return normalized || DEFAULT_USER_SETTINGS.activeProject;
}

function readUrlProjectId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const searchParams = new URLSearchParams(window.location.search);
    const raw = PROJECT_QUERY_KEYS.map((key) => searchParams.get(key)).find((value) => value?.trim());
    return raw ? normalizeProjectId(raw) : null;
  } catch {
    return null;
  }
}

function readStoredUserSettings(): UserSettings {
  if (typeof window === "undefined") return DEFAULT_USER_SETTINGS;
  try {
    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "{}") as Partial<UserSettings>;
    return {
      ...DEFAULT_USER_SETTINGS,
      ...stored,
      activeProject: normalizeProjectId(stored.activeProject),
    };
  } catch {
    return DEFAULT_USER_SETTINGS;
  }
}

export function readUserSettings(): UserSettings {
  const stored = readStoredUserSettings();
  return {
    ...stored,
    activeProject: readUrlProjectId() ?? stored.activeProject,
  };
}

export function readActiveProjectId(): string {
  return readUserSettings().activeProject;
}

export function writeUserSettings(settings: UserSettings) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  window.dispatchEvent(new CustomEvent<UserSettings>(SETTINGS_EVENT, { detail: settings }));
}

export function adoptActiveProjectFromUrl(): string | null {
  const activeProject = readUrlProjectId();
  if (!activeProject || typeof window === "undefined") return activeProject;
  const stored = readStoredUserSettings();
  if (stored.activeProject !== activeProject) {
    writeUserSettings({ ...stored, activeProject });
  }
  return activeProject;
}
