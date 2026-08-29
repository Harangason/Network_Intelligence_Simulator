import "server-only";

import { createHash, randomUUID } from "node:crypto";
import { mkdir, readFile, readdir, rename, stat, unlink, writeFile } from "node:fs/promises";
import path from "node:path";

export type ProgramCacheEntry<T> = {
  key: string;
  updatedAt: number;
  value: T;
};

function projectRoot() {
  return path.basename(process.cwd()).toLowerCase() === "frontend"
    ? path.dirname(process.cwd())
    : process.cwd();
}

function safeNamespace(namespace: string) {
  if (!/^[a-z0-9-]{1,48}$/i.test(namespace)) {
    throw new Error("Ungueltiger Cache-Bereich.");
  }
  return namespace.toLowerCase();
}

function cacheDirectory(namespace: string) {
  return path.join(projectRoot(), "backend", "runtime", "program-cache", safeNamespace(namespace));
}

function cacheFileName(key: string) {
  const normalized = key.trim() || "default";
  const label = normalized.replace(/[^a-zA-Z0-9._-]+/g, "-").slice(0, 72) || "default";
  const digest = createHash("sha256").update(normalized).digest("hex").slice(0, 16);
  return `${label}-${digest}.json`;
}

function cachePath(namespace: string, key: string) {
  return path.join(cacheDirectory(namespace), cacheFileName(key));
}

function isMissingFile(error: unknown) {
  return error instanceof Error && "code" in error && error.code === "ENOENT";
}

export async function readProgramCache<T>(namespace: string, key: string): Promise<ProgramCacheEntry<T> | null> {
  try {
    const serialized = await readFile(cachePath(namespace, key), "utf8");
    const entry = JSON.parse(serialized) as Partial<ProgramCacheEntry<T>>;
    if (entry.key !== key || typeof entry.updatedAt !== "number" || !("value" in entry)) return null;
    return entry as ProgramCacheEntry<T>;
  } catch (error) {
    if (isMissingFile(error) || error instanceof SyntaxError) return null;
    throw error;
  }
}

export async function writeProgramCache<T>(
  namespace: string,
  key: string,
  value: T,
  maximumBytes: number,
): Promise<ProgramCacheEntry<T>> {
  const directory = cacheDirectory(namespace);
  const target = cachePath(namespace, key);
  const entry: ProgramCacheEntry<T> = { key, updatedAt: Date.now(), value };
  const serialized = JSON.stringify(entry);
  const bytes = Buffer.byteLength(serialized, "utf8");
  if (bytes > maximumBytes) {
    throw new Error(`Cache-Eintrag ist mit ${bytes} Bytes zu gross (Limit ${maximumBytes}).`);
  }

  await mkdir(directory, { recursive: true });
  const temporary = path.join(directory, `.${cacheFileName(key)}.${randomUUID()}.tmp`);
  await writeFile(temporary, serialized, "utf8");
  try {
    await rename(temporary, target);
  } catch (error) {
    const code = error instanceof Error && "code" in error ? error.code : "";
    if (code !== "EEXIST" && code !== "EPERM") throw error;
    await unlink(target).catch((unlinkError) => {
      if (!isMissingFile(unlinkError)) throw unlinkError;
    });
    await rename(temporary, target);
  } finally {
    await unlink(temporary).catch((error) => {
      if (!isMissingFile(error)) throw error;
    });
  }
  return entry;
}

export async function deleteProgramCache(namespace: string, key: string): Promise<void> {
  await unlink(cachePath(namespace, key)).catch((error) => {
    if (!isMissingFile(error)) throw error;
  });
}

export async function pruneProgramCache(namespace: string, maximumEntries: number): Promise<void> {
  const directory = cacheDirectory(namespace);
  let files: string[];
  try {
    files = (await readdir(directory)).filter((file) => file.endsWith(".json"));
  } catch (error) {
    if (isMissingFile(error)) return;
    throw error;
  }
  if (files.length <= maximumEntries) return;

  const candidates = await Promise.all(files.map(async (file) => ({
    file,
    modifiedAt: (await stat(path.join(directory, file))).mtimeMs,
  })));
  candidates.sort((left, right) => right.modifiedAt - left.modifiedAt);
  await Promise.all(candidates.slice(maximumEntries).map(({ file }) => unlink(path.join(directory, file))));
}
