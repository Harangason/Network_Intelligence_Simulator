import { fuzzyTechnologySearch } from '../../communication/lib/technology-catalog-selection.ts';
import type { Technology } from '../../../shared/api/types';

export type LicenseState = {
  revision: string; clearance_required: boolean; blocked: boolean; status: string;
  issuer?: string; reason?: string; evidence_url?: string;
  records: Array<{id: string; issuer: string; reference: string; scope_description: string; expires_on?: string | null; status: string}>;
};
export type SourceRow = {
  id: string; name: string; publisher: string; url: string; accessed_at: string | null;
  technologies: Array<{id: string; abbreviation: string; name: string}>;
  revisions: string[];
  rights: {publication: string; label: string; explanation: string; evidence_url: string | null; review_status: string};
};
export type SourceDirectory = {
  sources: SourceRow[]; source_count: number; technology_count: number;
  project_id: string; rights_reviewed_at: string; licenses: Record<string, LicenseState>;
};
export type SourceSort = 'abbreviation' | 'technology' | 'name' | 'url' | 'accessed_at' | 'rights' | 'license';
const collator = new Intl.Collator('de', {sensitivity: 'base', numeric: true});
const compact = (value: string) => value.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]/g, '');

function matches(row: SourceRow, input: string): boolean {
  const terms = [row.name, row.publisher, row.url, row.rights.label, displaySourceDate(row.accessed_at),
    ...row.technologies.flatMap(item => [item.id, item.abbreviation, item.name])];
  const words = terms.flatMap(term => [term, ...term.split(/[\s/_.:–-]+/)]).filter(Boolean);
  return input.trim().split(/\s+/).every(query => {
    const normalized = compact(query);
    // Subsequence matching an entire provenance paragraph would match almost
    // every short query. Fuzzy edits operate on short bibliographic words only.
    const candidates = words.filter(word => compact(word).length <= normalized.length + 4)
      .map(word => ({id: word, label: word, family: word}) as Technology);
    return !normalized || terms.some(term => compact(term).includes(normalized))
      || fuzzyTechnologySearch(candidates, query).length > 0;
  });
}

export function sourceRows(rows: SourceRow[], query: string, sort: SourceSort = 'abbreviation', descending = false, licenses: Record<string, LicenseState> = {}): SourceRow[] {
  const key = (row: SourceRow): string => {
    if (sort === 'abbreviation') return row.technologies.map(item => item.abbreviation).join(', ');
    if (sort === 'technology') return row.technologies.map(item => item.name).join(', ');
    if (sort === 'rights') return row.rights.label;
    if (sort === 'license') return row.technologies.map(item => licenses[item.id]?.clearance_required
      ? licenses[item.id].blocked ? 'Gesperrt' : 'Freigegeben' : 'Keine NIS-Lizenzsperre').join(', ');
    return row[sort] ?? '';
  };
  return rows.filter(row => !query.trim() || matches(row, query)).sort((a, b) => {
    // Unknown access dates always remain last, in both directions.
    if (sort === 'accessed_at' && (!a.accessed_at || !b.accessed_at) && a.accessed_at !== b.accessed_at) return a.accessed_at ? -1 : 1;
    const difference = collator.compare(key(a), key(b));
    return (descending ? -difference : difference) || collator.compare(a.name, b.name) || collator.compare(a.id, b.id);
  });
}

export function displaySourceDate(value: string | null): string {
  if (!value) return 'Nicht dokumentiert';
  const parsed = new Date(value.length === 10 ? value + 'T12:00:00Z' : value);
  return Number.isNaN(parsed.getTime()) ? 'Nicht dokumentiert' : parsed.toLocaleDateString('de-DE', {timeZone: 'UTC'});
}
