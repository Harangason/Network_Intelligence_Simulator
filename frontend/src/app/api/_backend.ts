const BACKEND_BASE = process.env.SIMULATOR_API_URL ?? "http://127.0.0.1:15050/api";

export function projectIdFromRequest(
  request: Request,
  payload?: Record<string, unknown> | null,
): string | undefined {
  const url = new URL(request.url);
  const raw = request.headers.get("X-Project-ID")
    ?? url.searchParams.get("project")
    ?? url.searchParams.get("project_id")
    ?? url.searchParams.get("projectId")
    ?? (typeof payload?.project === "string" ? payload.project : null)
    ?? (typeof payload?.project_id === "string" ? payload.project_id : null)
    ?? (typeof payload?.projectId === "string" ? payload.projectId : null);
  const projectId = String(raw ?? "").trim();
  return projectId || undefined;
}

export function projectHeaders(projectId: string | undefined): HeadersInit {
  return projectId ? { "X-Project-ID": projectId } : {};
}

export async function proxyBackend(path: string, init?: RequestInit): Promise<Response | null> {
  try {
    const response = await fetch(`${BACKEND_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    const headers = new Headers({
      "Content-Type": response.headers.get("Content-Type") ?? "application/json",
    });
    const disposition = response.headers.get("Content-Disposition");
    if (disposition) headers.set("Content-Disposition", disposition);
    return new Response(await response.arrayBuffer(), {
      status: response.status,
      headers,
    });
  } catch {
    return null;
  }
}
