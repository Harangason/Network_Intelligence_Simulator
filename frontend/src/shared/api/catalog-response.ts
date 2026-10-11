import type { Catalog } from './types';

function completeCatalog(value: unknown): value is Catalog {
  if (!value || typeof value !== 'object') return false;
  const catalog = value as Partial<Catalog>;
  return Number.isInteger(catalog.technology_count) && Number(catalog.technology_count) > 0
    && Array.isArray(catalog.formats) && catalog.formats.every(format => typeof format === 'string')
    && Array.isArray(catalog.domains)
    && catalog.domains.length > 0 && catalog.domains.every(domain =>
      domain && typeof domain.id === 'string' && typeof domain.label === 'string'
      && Array.isArray(domain.technologies) && domain.technologies.every(technology =>
        technology && typeof technology.id === 'string'
        && (technology.label === undefined || typeof technology.label === 'string')
        && (technology.parameter_schema === undefined || Array.isArray(technology.parameter_schema))));
}

/** Retry this read once; only the registered backend catalog can succeed. */
export async function readRegisteredCatalog(load: () => Promise<unknown>): Promise<Catalog> {
  for (let attempt = 0; ; attempt += 1) {
    try {
      const catalog = await load();
      if (!completeCatalog(catalog)) throw new Error('Technologieprofile wurden unvollständig geladen. Bitte erneut laden.');
      return catalog;
    } catch (error) {
      if (attempt === 1) throw error;
    }
  }
}
