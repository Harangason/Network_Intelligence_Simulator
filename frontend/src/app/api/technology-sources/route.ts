import { proxyBackend, projectHeaders, projectIdFromRequest } from '../_backend';
export async function GET(request: Request) {
  // Cold registry/bibliography construction can exceed the ordinary 8s proxy
  // budget; this read-only catalogue retains a bounded 30s request deadline.
  return await proxyBackend('/technology-sources', {headers: projectHeaders(projectIdFromRequest(request)), signal: AbortSignal.timeout(30000)})
    ?? Response.json({error: 'Das Quellenverzeichnis ist momentan nicht erreichbar.'}, {status: 503});
}
