import { backendEndpoints } from '@/lib/backend-endpoints';
import { projectHeaders, projectIdFromRequest } from '../_backend';
import { MAX_IMPORT_BYTES } from '@/lib/trace-records';

export async function POST(request: Request) {
  if (!request.body) return Response.json({ error: 'Die Trace-Datei ist leer.' }, { status: 400 });
  let size = 0;
  let oversized = Number(request.headers.get('content-length')) > MAX_IMPORT_BYTES;
  if (oversized) return Response.json({ error: 'Trace-Import: maximal 500 MiB.' }, { status: 413 });
  const body = request.body.pipeThrough(new TransformStream<Uint8Array, Uint8Array>({
    transform(chunk, controller) {
      size += chunk.byteLength;
      if (size > MAX_IMPORT_BYTES) { oversized = true; throw new Error('Upload zu groß'); }
      controller.enqueue(chunk);
    },
  }));
  try {
    const parameters = new URLSearchParams({ filename: new URL(request.url).searchParams.get('filename') ?? '' });
    const { simulator } = backendEndpoints(process.env);
    const options: RequestInit & { duplex: 'half' } = {
      method: 'POST', body, duplex: 'half', cache: 'no-store',
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(600000)]),
      headers: { ...projectHeaders(projectIdFromRequest(request)), 'Content-Type': 'application/octet-stream' },
    };
    const response = await fetch(`${simulator}/trace-import?${parameters}`, options);
    return new Response(response.body, { status: response.status, headers: { 'Content-Type': 'application/json' } });
  } catch {
    return Response.json({ error: oversized ? 'Trace-Import: maximal 500 MiB.' : 'Trace-Importdienst nicht erreichbar oder Zeitlimit überschritten.' }, { status: oversized ? 413 : 503 });
  }
}
