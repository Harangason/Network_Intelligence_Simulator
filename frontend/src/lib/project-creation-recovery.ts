/** Check the project registry after a create response is lost. GET never creates a project. */
export async function committedProjectExists(
  projectId: string,
  expectedName: string,
  fetcher: typeof fetch = fetch,
): Promise<boolean> {
  const response = await fetcher('/api/engineering/projects?offset=0', { cache: 'no-store' });
  if (!response.ok) return false;
  const result: unknown = await response.json();
  if (!result || typeof result !== 'object' || !('items' in result) || !Array.isArray(result.items)) return false;
  return result.items.some((item: unknown) => Boolean(item && typeof item === 'object'
    && 'project_id' in item && item.project_id === projectId
    && 'name' in item && item.name === expectedName));
}
