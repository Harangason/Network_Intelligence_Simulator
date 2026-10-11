/** An unavailable registry is an explicit error, never a different catalog. */
export async function registeredCatalogResponse(readBackend: () => Promise<Response | null>): Promise<Response> {
  const response = await readBackend();
  return response ?? Response.json({
    error: 'Der vollständige Technologiekatalog ist derzeit nicht erreichbar. Bitte erneut versuchen.',
  }, { status: 503 });
}
