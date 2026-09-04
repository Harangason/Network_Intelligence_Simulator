export type UserSettings = {
  activeProject: string;
  automaticModelSync: boolean;
  openAgentOnStart: boolean;
};

export const NETWORK_PROJECT_PREFIX = "network-project-";
export const DEFAULT_PROJECT_ID = "default";

export const DEFAULT_USER_SETTINGS: UserSettings = {
  activeProject: DEFAULT_PROJECT_ID,
  automaticModelSync: true,
  openAgentOnStart: false,
};

const STORAGE_KEY = "communication-simulator:settings:v1";
export const SETTINGS_EVENT = "communication-simulator:settings-changed";
const PROJECT_QUERY_KEYS = ["project", "project_id", "projectId"];
const COMPACT_NETWORK_PROJECT_PATTERN = /^\d{14,17}-[A-Za-z0-9._-]+$/;
type ProjectQueryValue = string | string[] | undefined;
export type ProjectQueryRecord = Record<string, ProjectQueryValue>;

function sanitizeProjectId(value: unknown): string {
  return String(value ?? "")
    .trim()
    .replace(/[^a-zA-Z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

export function normalizeProjectId(value: unknown): string {
  const normalized = sanitizeProjectId(value);
  return normalized || DEFAULT_USER_SETTINGS.activeProject;
}

export function expandBrowserProjectId(value: unknown): string {
  const normalized = normalizeProjectId(value);
  if (normalized === DEFAULT_USER_SETTINGS.activeProject || normalized.startsWith(NETWORK_PROJECT_PREFIX)) {
    return normalized;
  }
  return COMPACT_NETWORK_PROJECT_PATTERN.test(normalized)
    ? `${NETWORK_PROJECT_PREFIX}${normalized}`
    : normalized;
}

export function compactProjectId(value: unknown): string {
  const normalized = normalizeProjectId(value);
  return normalized.startsWith(NETWORK_PROJECT_PREFIX)
    ? normalized.slice(NETWORK_PROJECT_PREFIX.length)
    : normalized;
}

export function withProjectParam(href: string, projectId?: string): string {
  if (!href || href.startsWith("#") || /^(?:[a-z][a-z0-9+.-]*:)?\/\//i.test(href)) return href;
  const activeProject = projectId === undefined
    ? (typeof window === "undefined" ? "" : readActiveProjectId())
    : sanitizeProjectId(projectId);
  if (!activeProject) return href;
  const hashIndex = href.indexOf("#");
  const pathAndSearch = hashIndex >= 0 ? href.slice(0, hashIndex) : href;
  const hash = hashIndex >= 0 ? href.slice(hashIndex) : "";
  const queryIndex = pathAndSearch.indexOf("?");
  const path = queryIndex >= 0 ? pathAndSearch.slice(0, queryIndex) : pathAndSearch;
  const params = new URLSearchParams(queryIndex >= 0 ? pathAndSearch.slice(queryIndex + 1) : "");
  params.delete("project_id");
  params.delete("projectId");
  params.set("project", compactProjectId(activeProject));
  const query = params.toString();
  return `${path}${query ? `?${query}` : ""}${hash}`;
}

function firstQueryValue(value: ProjectQueryValue): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

export function compactProjectQueryFromSearchParams(searchParams: ProjectQueryRecord): string {
  const projectId = projectIdFromSearchParams(searchParams);
  return projectId ? `project=${encodeURIComponent(compactProjectId(projectId))}` : "";
}

export function projectIdFromSearchParams(searchParams: ProjectQueryRecord): string | undefined {
  for (const key of PROJECT_QUERY_KEYS) {
    const raw = firstQueryValue(searchParams[key]);
    if (!raw.trim()) continue;
    return expandBrowserProjectId(raw);
  }
  return undefined;
}

export function projectQuerySuffixFromSearchParams(searchParams: ProjectQueryRecord): string {
  const query = compactProjectQueryFromSearchParams(searchParams);
  return query ? `?${query}` : "";
}

export function ensureCurrentUrlProjectParam(projectId: string = readActiveProjectId()): void {
  if (typeof window === "undefined") return;
  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  const next = withProjectParam(current, projectId);
  if (next !== current) window.history.replaceState(window.history.state, "", next);
}

function readUrlProjectId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const searchParams = new URLSearchParams(window.location.search);
    for (const key of PROJECT_QUERY_KEYS) {
      const raw = searchParams.get(key);
      if (!raw?.trim()) continue;
      return expandBrowserProjectId(raw);
    }
    return null;
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
