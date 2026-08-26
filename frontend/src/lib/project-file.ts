import type { ProjectBundle } from "./workflow-api";

type WritableFile = {
  write(data: Blob | string): Promise<void>;
  close(): Promise<void>;
};

type ProjectFileHandle = {
  name: string;
  createWritable(): Promise<WritableFile>;
  getFile(): Promise<File>;
  queryPermission?(descriptor: { mode: "read" | "readwrite" }): Promise<"granted" | "denied" | "prompt">;
  requestPermission?(descriptor: { mode: "read" | "readwrite" }): Promise<"granted" | "denied" | "prompt">;
};

type ProjectFileWindow = Window & {
  showSaveFilePicker?: (options: Record<string, unknown>) => Promise<ProjectFileHandle>;
  showOpenFilePicker?: (options: Record<string, unknown>) => Promise<ProjectFileHandle[]>;
};

const DB_NAME = "communication-simulator-project-files";
const STORE_NAME = "handles";

function openHandleDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE_NAME);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
  });
}

async function readHandle(projectId: string): Promise<ProjectFileHandle | null> {
  try {
    const db = await openHandleDatabase();
    return await new Promise((resolve, reject) => {
      const request = db.transaction(STORE_NAME, "readonly").objectStore(STORE_NAME).get(projectId);
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve((request.result as ProjectFileHandle | undefined) ?? null);
    });
  } catch {
    return null;
  }
}

async function storeHandle(projectId: string, handle: ProjectFileHandle) {
  try {
    const db = await openHandleDatabase();
    await new Promise<void>((resolve, reject) => {
      const request = db.transaction(STORE_NAME, "readwrite").objectStore(STORE_NAME).put(handle, projectId);
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve();
    });
  } catch {
    // Some browsers cannot structured-clone file handles. Saving still works for this session.
  }
}

async function ensureWritePermission(handle: ProjectFileHandle): Promise<boolean> {
  if (!handle.queryPermission) return true;
  if (await handle.queryPermission({ mode: "readwrite" }) === "granted") return true;
  return (await handle.requestPermission?.({ mode: "readwrite" })) === "granted";
}

function projectPickerOptions(suggestedName: string) {
  return {
    suggestedName,
    types: [{ description: "Network Intelligence Project", accept: { "application/json": [".json"] } }],
    excludeAcceptAllOption: false,
  };
}

function isUnsupportedPickerError(caught: unknown) {
  const name = (caught as { name?: string }).name;
  return caught instanceof TypeError || name === "NotSupportedError" || name === "SecurityError";
}

export async function hasProjectFileHandle(projectId: string) {
  return Boolean(await readHandle(projectId));
}

export async function saveProjectBundleToFile(
  bundle: ProjectBundle,
  { forceChoose = false }: { forceChoose?: boolean } = {},
): Promise<{ fileName: string; persistent: boolean }> {
  const browser = window as ProjectFileWindow;
  let handle = forceChoose ? null : await readHandle(bundle.project_id);
  if (handle && !(await ensureWritePermission(handle))) handle = null;
  if (!handle && browser.showSaveFilePicker) {
    try {
      handle = await browser.showSaveFilePicker(projectPickerOptions(`${bundle.project_id}.nis-project.json`));
    } catch (caught) {
      if (!isUnsupportedPickerError(caught)) throw caught;
    }
  }
  const content = JSON.stringify(bundle, null, 2);
  if (handle) {
    const writable = await handle.createWritable();
    await writable.write(content);
    await writable.close();
    await storeHandle(bundle.project_id, handle);
    return { fileName: handle.name, persistent: true };
  }

  const url = URL.createObjectURL(new Blob([content], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${bundle.project_id}.nis-project.json`;
  anchor.click();
  URL.revokeObjectURL(url);
  return { fileName: anchor.download, persistent: false };
}

type ProjectOpenStatus = {
  fileName?: string;
  message: string;
};

async function inputFileFallback(): Promise<File> {
  return new Promise((resolve, reject) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json,application/json";
    input.onchange = () => input.files?.[0] ? resolve(input.files[0]) : reject(new Error("Keine Projektdatei ausgewählt."));
    input.click();
  });
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export async function openProjectBundleFromFile(
  onStatus?: (status: ProjectOpenStatus) => void,
): Promise<{ bundle: ProjectBundle; fileName: string; handle: ProjectFileHandle | null }> {
  const browser = window as ProjectFileWindow;
  let handle: ProjectFileHandle | null = null;
  if (browser.showOpenFilePicker) {
    try {
      handle = (await browser.showOpenFilePicker(projectPickerOptions("project.nis-project.json")))[0] ?? null;
    } catch (caught) {
      if (!isUnsupportedPickerError(caught)) throw caught;
    }
  }
  const file = handle ? await handle.getFile() : await inputFileFallback();
  onStatus?.({ fileName: file.name, message: `Lese ${file.name} (${formatFileSize(file.size)}) ...` });
  const content = await file.text();
  onStatus?.({ fileName: file.name, message: `Pruefe Projektdatei ${file.name} ...` });
  const bundle = JSON.parse(content) as ProjectBundle;
  if (bundle.format !== "network-intelligence-project") {
    throw new Error("Die ausgewählte Datei ist kein Network-Intelligence-Projekt.");
  }
  if (handle) await storeHandle(bundle.project_id, handle);
  return { bundle, fileName: file.name, handle };
}
