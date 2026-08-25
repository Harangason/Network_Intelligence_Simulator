// Server-seitiger Client für die Engineering-API, genutzt vom Agent (Route
// Handler laufen außerhalb des Next.js-Rewrite-Kontexts und sprechen daher
// direkt mit dem Flask-Backend statt über einen relativen "/api"-Pfad).

const ENGINEERING_BASE =
  process.env.ENGINEERING_API_URL ?? "http://127.0.0.1:5050/api/engineering";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${ENGINEERING_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
    signal: AbortSignal.timeout(8000),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error((payload as { error?: string }).error ?? `Engineering-API-Fehler ${response.status}`);
  }
  return payload as T;
}

export function listObjects(resource: string, params: Record<string, string | undefined> = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, value);
  }
  const suffix = query.toString();
  return request<{ items: Record<string, unknown>[]; count: number }>(
    `/${resource}${suffix ? `?${suffix}` : ""}`,
  );
}

export function getObject(resource: string, id: string) {
  return request<Record<string, unknown>>(`/${resource}/${id}`);
}

export function createObject(resource: string, payload: Record<string, unknown>) {
  return request<Record<string, unknown>>(`/${resource}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateObject(resource: string, id: string, payload: Record<string, unknown>) {
  return request<Record<string, unknown>>(`/${resource}/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function listRelations(params: Record<string, string | undefined> = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, value);
  }
  const suffix = query.toString();
  return request<{ items: Record<string, unknown>[]; count: number }>(
    `/relations${suffix ? `?${suffix}` : ""}`,
  );
}

export function createRelation(payload: Record<string, unknown>) {
  return request<Record<string, unknown>>("/relations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
