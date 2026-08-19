import { getDevArtifact } from "../../../../_dev-opt/store";

// DEV-OPT: downloadable preview artifact; production files are served by Flask.
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string; format: string }> },
) {
  const { id, format } = await params;
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
