import type { UIMessage } from 'ai';
import { readProgramCache } from '@/lib/server/program-cache';
import { backendEndpoints } from '@/lib/backend-endpoints';
export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
const { engineering: backend } = backendEndpoints(process.env);
async function forward(request: Request) {
  let payload: { projectId?: string; messages?: UIMessage[] } = {};
  if (request.method === 'PUT') {
    if (Number(request.headers.get('content-length') ?? 0) > 5_000_000) return Response.json({ error: 'Verlauf zu groß.' }, { status: 413 });
    try { payload = await request.json(); } catch { return Response.json({ error: 'Ungültiges JSON.' }, { status: 400 }); }
  }
  const projectId = payload.projectId ?? new URL(request.url).searchParams.get('projectId');
  if (!projectId) return Response.json({ error: 'projectId fehlt.' }, { status: 400 });
  const headers = { 'Content-Type': 'application/json', 'X-Project-ID': projectId };
  try {
    const response = await fetch(`${backend}/agent/history`, { method: request.method, headers, cache: 'no-store',
      body: request.method === 'PUT' ? JSON.stringify({ messages: payload.messages }) : undefined, signal: AbortSignal.timeout(8000) });
    let data = await response.json();
    if (request.method === 'GET' && response.ok && data.updatedAt == null) {
      const legacy = await readProgramCache<{ messages: UIMessage[] }>('agent-chat', projectId);
      if (legacy?.value.messages.length) {
        const migrated = await fetch(`${backend}/agent/history`, { method: 'PUT', headers, body: JSON.stringify({ messages: legacy.value.messages.filter(m => m.role !== 'system').slice(-60) }), signal: AbortSignal.timeout(8000) });
        if (migrated.ok) data = await migrated.json();
      }
    }
    return Response.json(data, { status: response.status, headers: { 'Cache-Control': 'no-store' } });
  } catch { return Response.json({ error: 'Gesprächsspeicher vorübergehend nicht verfügbar.' }, { status: 503 }); }
}
export const GET = forward;
export const PUT = forward;
export const DELETE = forward;
