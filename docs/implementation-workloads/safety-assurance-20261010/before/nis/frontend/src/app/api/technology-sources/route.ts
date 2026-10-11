import { proxyBackend, projectHeaders, projectIdFromRequest } from '../_backend';
export async function GET(request: Request) {
  return await proxyBackend('/technology-sources', {headers: projectHeaders(projectIdFromRequest(request))})
    ?? Response.json({error: 'Das Quellenverzeichnis ist momentan nicht erreichbar.'}, {status: 503});
}
