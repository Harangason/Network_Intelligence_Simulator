import type { Catalog, Technology } from './types';

const record = (value: unknown): Record<string, unknown> =>
  value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};

export function registeredTechnologies(catalog: Catalog): Technology[] {
  const unique = new Map<string, Technology>();
  for (const domain of catalog.domains) {
    for (const technology of domain.technologies) {
      if (!unique.has(technology.id)) unique.set(technology.id, technology);
    }
  }
  return [...unique.values()];
}

export function parameterTechnologySelection(
  parameters: Record<string, unknown>,
  context: Record<string, unknown>,
): { domainId: string; technologyId: string } {
  const wizard = record(context.agent_wizard_status);
  const confirmed = Boolean(wizard.confirmed_at);
  const domainId = typeof parameters.industry === 'string' && parameters.industry.trim()
    ? parameters.industry
    : confirmed && typeof wizard.model_type === 'string' ? wizard.model_type : '';
  if (typeof parameters.technology === 'string' && parameters.technology.trim()) {
    return { domainId, technologyId: parameters.technology };
  }
  const counts = confirmed && Array.isArray(wizard.communication_system_counts)
    ? wizard.communication_system_counts : [];
  const ids = [...new Set(counts
    .map(item => record(item))
    .filter(item => typeof item.id === 'string' && Number(item.count) > 0)
    .map(item => String(item.id)))];
  return { domainId, technologyId: ids.length === 1 ? ids[0] : '' };
}
