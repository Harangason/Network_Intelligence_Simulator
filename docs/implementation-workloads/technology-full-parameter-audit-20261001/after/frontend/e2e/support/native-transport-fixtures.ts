import type { Page } from 'playwright/test';
import { readFile } from 'node:fs/promises';

// Explicit test operator input through the normal parameter API. Generated
// objects and captured requirements are untouched; physical qualification is
// deliberately absent from this virtual serializer acceptance fixture.
export async function reviewVirtualTransports(page: Page, project: string): Promise<void> {
  const headers = { 'X-Project-ID': project };
  const initial = await (await page.request.get('/api/engineering/workflow/parameters', { headers })).json();
  const groups: Record<string, unknown> = { ...initial.parameters.technology_parameters };
  for (const technology of ['lin', 'ethernet']) {
    const fixture = JSON.parse(await readFile(new URL(`../fixtures/virtual-${technology}-profile.json`, import.meta.url), 'utf8'));
    const values = fixture.values;
    const provenance = Object.fromEntries(Object.entries(values).map(([key, value]) =>
      [key, { source: 'USER_CONFIRMED', status: 'CONFIRMED', value }]));
    groups[technology] = { values, provenance };
  }
  const response = await page.request.patch('/api/engineering/workflow/parameters', { headers,
    data: { expected_token: initial.edit_token, parameters: { ...initial.parameters,
      technology_parameters: groups } } });
  if (!response.ok()) throw new Error(`Virtual transport review HTTP ${response.status()}: ${await response.text()}`);
}
