import { getDevArtifact } from "../../../../_dev-opt/store";
import { proxyBackend } from "../../../../_backend";

// DEV-OPT: downloadable preview artifact; production files are served by Flask.
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string; format: string }> },
) {
  const { id, format } = await params;
  const url = new URL(request.url);
  const projectId = request.headers.get("X-Project-ID") ?? url.searchParams.get("project_id") ?? "default";
  const backend = await proxyBackend(
    `/simulations/${encodeURIComponent(id)}/artifacts/${encodeURIComponent(format)}`,
    { headers: { "X-Project-ID": projectId } },
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
