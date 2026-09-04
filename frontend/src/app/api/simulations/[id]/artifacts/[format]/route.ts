import { getDevArtifact } from "../../../../_dev-opt/store";
import { projectHeaders, projectIdFromRequest, proxyBackend } from "../../../../_backend";

// DEV-OPT: downloadable preview artifact; production files are served by Flask.
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string; format: string }> },
) {
  const { id, format } = await params;
  const backend = await proxyBackend(
    `/simulations/${encodeURIComponent(id)}/artifacts/${encodeURIComponent(format)}`,
    { headers: projectHeaders(projectIdFromRequest(request)) },
  );
  if (backend && backend.status !== 404) return backend;
  const artifact = getDevArtifact(id, format);
  if (!artifact) {
    return Response.json({ error: "Artefakt nicht gefunden." }, { status: 404 });
  }
  return new Response(artifact.body, {
    headers: {
      "Content-Type": artifact.type,
      "Content-Disposition": `attachment; filename="${artifact.name}"`,
    },
  });
}
