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

const compact = (value: string): string => value.normalize('NFKD')
  .replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]/g, '');

function editDistance(left: string, right: string): number {
  let previous = Array.from({ length: right.length + 1 }, (_, index) => index);
  for (let row = 1; row <= left.length; row += 1) {
    const current = [row];
    for (let column = 1; column <= right.length; column += 1) {
      current[column] = Math.min(
        previous[column] + 1,
        current[column - 1] + 1,
        previous[column - 1] + (left[row - 1] === right[column - 1] ? 0 : 1),
      );
    }
    previous = current;
  }
  return previous[right.length];
}

function searchScore(technology: Technology, query: string): number {
  const terms = [technology.id, technology.label, technology.family]
    .filter((value): value is string => typeof value === 'string')
    .map(compact);
  let best = Number.POSITIVE_INFINITY;
  for (const term of terms) {
    if (term === query) return 0;
    if (term.startsWith(query)) best = Math.min(best, 10 + term.length - query.length);
    else if (term.includes(query)) best = Math.min(best, 20 + term.length - query.length);
    else if (query.length >= 4 && Math.abs(term.length - query.length) <= 2) {
      const distance = editDistance(query, term);
      if (distance <= (query.length >= 7 ? 2 : 1)) best = Math.min(best, 30 + distance);
    }
    if (query.length >= 3) {
      let position = 0;
      for (const letter of term) if (letter === query[position]) position += 1;
      if (position === query.length) best = Math.min(best, 50 + term.length - query.length);
    }
  }
  return best;
}

export function fuzzyTechnologySearch(technologies: Technology[], input: string): Technology[] {
  const query = compact(input.trim());
  if (!query) return technologies;
  return technologies.map((technology, index) => ({ technology, index, score: searchScore(technology, query) }))
    .filter(item => Number.isFinite(item.score))
    .sort((left, right) => left.score - right.score || left.index - right.index)
    .map(item => item.technology);
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
