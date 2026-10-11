import { backendEndpoints } from '@/lib/backend-endpoints';
import { projectHeaders, projectIdFromRequest } from '../../_backend';

export async function GET(request: Request, context: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = await context.params;
  const { simulator } = backendEndpoints(process.env);
  const response = await fetch(`${simulator}/trace-import/${encodeURIComponent(sessionId)}${new URL(request.url).search}`, {
    headers: projectHeaders(projectIdFromRequest(request)), cache: 'no-store', signal: AbortSignal.timeout(15000),
  });
  return new Response(response.body, { status: response.status, headers: { 'Content-Type': 'application/json' } });
}
