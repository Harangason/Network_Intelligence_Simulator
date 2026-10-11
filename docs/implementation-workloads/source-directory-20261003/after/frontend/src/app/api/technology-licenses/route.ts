import { proxyBackend, projectHeaders, projectIdFromRequest } from '../_backend';
export async function GET(request: Request) {
  return await proxyBackend('/technology-licenses', {headers: projectHeaders(projectIdFromRequest(request))})
    ?? Response.json({error: 'Die Lizenzprüfung ist momentan nicht erreichbar.'}, {status: 503});
}
export async function POST(request: Request) {
  let payload: unknown;
  try { payload = await request.json(); }
  catch { return Response.json({error: 'Ein gültiges JSON-Objekt ist erforderlich.'}, {status: 400}); }
  return await proxyBackend('/technology-licenses', {method: 'POST', body: JSON.stringify(payload),
    headers: projectHeaders(projectIdFromRequest(request))})
    ?? Response.json({error: 'Der Nachweis konnte nicht eingereicht werden.'}, {status: 503});
}
