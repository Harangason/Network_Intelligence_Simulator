import type { Technology } from './types';

type Parameters = Record<string, unknown>;
export type DeclaredNetwork = Parameters & { id: string; name?: string; technology?: string };
const record = (value: unknown): Parameters => value && typeof value === 'object' && !Array.isArray(value) ? value as Parameters : {};
export const technologyKey = (value: unknown) => String(value ?? '').toLowerCase().replace(/[ -]/g, '_');

/** Catalog defaults remain proposals; only matching saved values may override them. */
export function technologyParameterValues(parameters: Parameters, technology: Technology): Parameters {
  const scoped = record(record(parameters.technology_parameters)[technology.id]);
  const proposed = record(record(parameters.technology_defaults)[technology.id]);
  const global = technologyKey(parameters.technology) === technology.id ? parameters : {};
  const saved = record(scoped.values);
  return Object.fromEntries((technology.parameter_schema ?? []).map(field => {
    const value = saved[field.key] ?? global[field.key];
    const proof = record(record(scoped.provenance)[field.key] ?? record(parameters.parameter_provenance)[field.key]);
    const rate = field.unit === 'bit/s' && ['bitrate', 'arbitration_bitrate', 'data_bitrate'].includes(field.key);
    const confirmed = proof.status === 'CONFIRMED' && proof.value === value || proof.source === 'EXPLICIT_USER_SPECIFICATION' && proof.value === value;
    const invalidRate = rate && (typeof value !== 'number' || !Number.isFinite(value) || value <= 0 || field.min !== undefined && value < field.min || field.max !== undefined && value > field.max || field.allowed_bps?.length && !field.allowed_bps.includes(value));
    const oldProposal = rate && (proof.status === 'REVIEW_REQUIRED' || proof.source === 'TECHNOLOGY_DEFAULT');
    return [field.key, confirmed ? value : invalidRate || oldProposal ? field.default : value ?? field.default ?? proposed[field.key]];
  }));
}

export function technologyParameterUnverified(parameters: Parameters, key: string, technologyId: string): boolean {
  const scoped = record(record(parameters.technology_parameters)[technologyId]);
  const value = record(scoped.values)[key];
  const proof = record(record(scoped.provenance)[key]);
  if (value !== undefined && value !== null && proof.source === 'USER_CONFIRMED' && proof.status === 'CONFIRMED' && proof.value === value) return false;
  if (technologyKey(parameters.technology) !== technologyId) return true;
  const global = parameters[key];
  const provenance = record(record(parameters.parameter_provenance)[key]);
  return global === undefined || global === null || global === '' || provenance.status === 'REVIEW_REQUIRED';
}

export function confirmTechnologyParameters(parameters: Parameters, technology: Technology, values: Parameters): Parameters {
  const selected = Object.fromEntries((technology.parameter_schema ?? []).map(field => [field.key, values[field.key]]));
  if (selected.bitrate === undefined && selected.data_bitrate !== undefined) selected.bitrate = selected.data_bitrate;
  const provenance = Object.fromEntries(Object.entries(selected).map(([key, value]) => [key, { source: 'USER_CONFIRMED', status: 'CONFIRMED', value }]));
  const scoped = { ...record(parameters.technology_parameters), [technology.id]: { values: selected, provenance } };
  // Mixed projects retain their primary technology and every declared network.
  if (parameters.technology && technologyKey(parameters.technology) !== technology.id && Array.isArray(parameters.networks) && parameters.networks.length) {
    return { ...parameters, technology_parameters: scoped };
  }
  const result: Parameters = { ...parameters, ...selected, technology: technology.id, technology_parameters: scoped,
    parameter_provenance: { ...record(parameters.parameter_provenance), ...provenance } };
  // A different rate model cannot retain a previous technology's rate phases.
  for (const key of ['bitrate_bps', 'nominal_bitrate_bps', 'data_bitrate_bps', 'arbitration_bitrate', 'data_bitrate']) {
    if (!(key in selected)) delete result[key];
  }
  return result;
}

export function confirmNetworkParameters(parameters: Parameters, technology: Technology, ids: string[], values: Parameters): Parameters {
  const networks = (Array.isArray(parameters.networks) ? parameters.networks : []) as DeclaredNetwork[];
  const selected = new Set(ids);
  if (!selected.size || networks.filter(item => selected.has(item.id)).length !== selected.size) throw new Error('Die ausgewählten Netze sind nicht mehr vorhanden. Bitte neu laden.');
  if (networks.some(item => selected.has(item.id) && technologyKey(item.technology) !== technology.id)) throw new Error('Die Auswahl enthält eine andere Technologie. Bitte neu laden.');
  const fields = (technology.parameter_schema ?? []).filter(field => field.scope === 'network' && Object.hasOwn(values, field.key));
  const confirmed = Object.fromEntries(fields.map(field => [field.key, values[field.key]]));
  return { ...parameters, networks: networks.map(item => selected.has(item.id) ? { ...item, ...confirmed,
    parameter_provenance: { ...record(item.parameter_provenance), ...Object.fromEntries(Object.entries(confirmed).map(([key, value]) => [key, { source: 'USER_CONFIRMED', status: 'CONFIRMED', value }])) } } : item) };
}

export type ReviewFinding = { code?: string; message?: string; object_type?: string; object_id?: string; recommendation?: string };
export function groupPreflightFindings(findings: ReviewFinding[]): Array<{ id: string; objectType: string; objectId?: string; findings: ReviewFinding[]; rateMissing: boolean }> {
  const groups = new Map<string, { id: string; objectType: string; objectId?: string; findings: ReviewFinding[]; rateMissing: boolean }>();
  for (const finding of findings) {
    const id = `${finding.object_type ?? 'Workflow'}:${finding.object_id ?? finding.code ?? 'unknown'}`;
    const group = groups.get(id) ?? { id, objectType: finding.object_type ?? 'Workflow', objectId: finding.object_id, findings: [], rateMissing: false };
    if (!group.findings.some(item => item.code === finding.code && item.message === finding.message)) group.findings.push(finding);
    group.rateMissing ||= finding.code === 'CAPACITY_RATE_UNVERIFIED';
    groups.set(id, group);
  }
  return [...groups.values()];
}
