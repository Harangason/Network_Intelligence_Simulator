const BACKEND_BASE = process.env.SIMULATOR_API_URL ?? "http://127.0.0.1:15050/api";

export async function proxyBackend(path: string, init?: RequestInit): Promise<Response | null> {
  try {
    const response = await fetch(`${BACKEND_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    return new Response(await response.arrayBuffer(), {
      status: response.status,
      headers: { "Content-Type": response.headers.get("Content-Type") ?? "application/json" },
    });
  } catch {
    return null;
  }
}
