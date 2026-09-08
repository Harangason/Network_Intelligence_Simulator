export type TraceStorageSettings = {
  project_id: string;
  path: string;
  resolved_path: string;
  default_path: string;
  is_default: boolean;
  container: boolean;
  roots: string[];
  host_folder_connected: boolean;
};

export type StorageDirectories = {
  path: string;
  parent: string | null;
  directories: { name: string; path: string }[];
  truncated: boolean;
};

export async function storageRequest<T>(project: string, endpoint: string, method = "GET", body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/storage/${endpoint}`, {
    method,
    headers: { "Content-Type": "application/json", "X-Project-ID": project, "X-NetworkIS-Storage": "confirmed" },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000),
  });
  const result = await response.json().catch(() => null);
  if (!response.ok || !result) throw new Error(result?.error || `Speicher-Einstellungen sind nicht erreichbar (HTTP ${response.status}).`);
  return result as T;
}
