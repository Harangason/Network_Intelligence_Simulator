import type { Technology, TechnologyParameterField } from './types';

type Parameters = Record<string, unknown>;
export type DeclaredNetwork = Parameters & { id: string; name?: string; technology?: string };
const record = (value: unknown): Parameters => value && typeof value === 'object' && !Array.isArray(value) ? value as Parameters : {};
export const technologyKey = (value: unknown) => String(value ?? '').toLowerCase().replace(/[ -]/g, '_');
const matchingProof = (proof: Parameters, technologyId: string) => ['technology', 'technology_id', 'protocol']
  .every(key => !proof[key] || technologyKey(proof[key]) === technologyKey(technologyId));

/** The profile owns device requirements; a controller port is not a transaction. */
export function localEvidenceFieldRequired(
  field: NonNullable<Technology['local_timing_schema']>[number], values: Parameters,
): boolean {
  if (field.required_scopes) return field.required_scopes.includes(String(values.evidence_scope || 'TRANSACTION'));
  if (field.required_when) return Object.entries(field.required_when).every(([key, value]) => values[key] === value);
  if (field.key === 'arbitration_bound_us') return values.multi_master === true;
  return !field.optional;
}

/** A device state with no default must remain unknown until explicitly selected. */
export function booleanParameterValue(field: {default?: unknown}, raw: FormDataEntryValue | null): boolean | null {
  if (field.default !== undefined) return raw !== null; // Existing proposed checkbox.
  if (raw === null || raw === '') return null;
  if (raw === 'true') return true;
  if (raw === 'false') return false;
  throw new Error('Bitte einen gültigen Ja-/Nein-Wert auswählen.');
}

/** Resolve a literature proposal only when every declared condition is known. */
export function conditionalParameterDefault(field: Pick<TechnologyParameterField, 'conditional_defaults'>, values: Parameters): unknown {
  const matches = (field.conditional_defaults ?? []).filter(proposal =>
    Object.entries(proposal.when).every(([key, expected]) => values[key] === expected));
  return matches.length && matches.every(item => item.value === matches[0].value) ? matches[0].value : undefined;
}

/** Parse a profile field without rounding protocol counters or durations. */
export function numericParameterValue(field: TechnologyParameterField, entered: string): number | string | null {
  const text = entered.trim();
  if (!text) {
    if (field.required) throw new Error(`${field.label}: Bitte einen bestätigten Wert eingeben.`);
    return null;
  }
  if (field.numeric_encoding === 'DECIMAL_STRING') {
    if (!/^-?[0-9]+$/.test(text) || text.length > 40) throw new Error(`${field.label}: Bitte eine ganze Dezimalzahl eingeben.`);
    const integer = BigInt(text);
    if (field.decimal_min !== undefined && integer < BigInt(field.decimal_min)
      || field.decimal_max !== undefined && integer > BigInt(field.decimal_max)) throw new Error(`${field.label}: Der Wert liegt außerhalb des gültigen Bereichs.`);
    return integer.toString();
  }
  const numeric = Number(text);
  if (!Number.isFinite(numeric) || field.integer && !Number.isSafeInteger(numeric)
    || field.min !== undefined && numeric < field.min || field.max !== undefined && numeric > field.max) {
    throw new Error(`${field.label}: Der Wert liegt außerhalb des gültigen Bereichs.`);
  }
  return numeric;
}

/** Catalog defaults remain proposals; only matching saved values may override them. */
export function technologyParameterValues(parameters: Parameters, technology: Technology): Parameters {
  const scoped = record(record(parameters.technology_parameters)[technology.id]);
  const proposed = record(record(parameters.technology_defaults)[technology.id]);
  const global = technologyKey(parameters.technology) === technology.id ? parameters : {};
  const saved = record(scoped.values);
  const values = Object.fromEntries((technology.parameter_schema ?? []).map(field => {
    const value = saved[field.key] ?? global[field.key];
    const proof = record(record(scoped.provenance)[field.key] ?? record(parameters.parameter_provenance)[field.key]);
    const rate = field.unit === 'bit/s' && ['bitrate', 'arbitration_bitrate', 'data_bitrate'].includes(field.key);
    const matching = matchingProof(proof, technology.id);
    const confirmed = matching && (proof.status === 'CONFIRMED' && proof.source === 'USER_CONFIRMED' && proof.value === value || proof.source === 'EXPLICIT_USER_SPECIFICATION' && proof.value === value);
    const invalidRate = rate && (typeof value !== 'number' || !Number.isFinite(value) || value <= 0 || field.min !== undefined && value < field.min || field.max !== undefined && value > field.max || field.allowed_bps?.length && !field.allowed_bps.includes(value));
    const oldProposal = rate && (proof.status === 'REVIEW_REQUIRED' || proof.source === 'TECHNOLOGY_DEFAULT');
    return [field.key, !matching ? field.default : confirmed ? value : invalidRate || oldProposal ? field.default : value ?? field.default ?? proposed[field.key]];
  }));
  // Dependencies may appear later in the schema. Iterate only proposed fields;
  // confirmed/explicit values always retain their original actual setting.
  const schema = technology.parameter_schema ?? [];
  for (let pass = 0; pass < schema.length; pass++) {
    let changed = false;
    for (const field of schema) {
      if (!field.conditional_defaults?.length) continue;
      const proof = record(record(scoped.provenance)[field.key] ?? record(parameters.parameter_provenance)[field.key]);
      const explicit = matchingProof(proof, technology.id) && proof.value === values[field.key]
        && (proof.source === 'EXPLICIT_USER_SPECIFICATION' || proof.source === 'USER_CONFIRMED' && proof.status === 'CONFIRMED');
      const oldSuggestion = proof.status === 'REVIEW_REQUIRED' && /DEFAULT|PROPOSAL/.test(String(proof.source || ''));
      if (!explicit && (oldSuggestion || values[field.key] === undefined || values[field.key] === null || values[field.key] === '')) {
        const suggestion = conditionalParameterDefault(field, values);
        if (values[field.key] !== suggestion) { values[field.key] = suggestion; changed = true; }
      }
    }
    if (!changed) break;
  }
  return values;
}

export function technologyParameterUnverified(parameters: Parameters, key: string, technologyId: string): boolean {
  const scoped = record(record(parameters.technology_parameters)[technologyId]);
  const value = record(scoped.values)[key];
  const proof = record(record(scoped.provenance)[key]);
  if (value !== undefined && value !== null && matchingProof(proof, technologyId) && proof.source === 'USER_CONFIRMED' && proof.status === 'CONFIRMED' && proof.value === value) return false;
  if (technologyKey(parameters.technology) !== technologyId) return true;
  const global = parameters[key];
  const provenance = record(record(parameters.parameter_provenance)[key]);
  return global === undefined || global === null || global === '' || !matchingProof(provenance, technologyId) || provenance.value !== global
    || !(provenance.status === 'CONFIRMED' && provenance.source === 'USER_CONFIRMED'
      || provenance.source === 'EXPLICIT_USER_SPECIFICATION');
}

export function confirmTechnologyParameters(parameters: Parameters, technology: Technology, values: Parameters): Parameters {
  const oldGroup = record(record(parameters.technology_parameters)[technology.id]);
  const allowed = new Set((technology.parameter_schema ?? []).map(field => field.key));
  const matchingGlobal = technologyKey(parameters.technology) === technology.id;
  const globalProof = matchingGlobal ? record(parameters.parameter_provenance) : {};
  const previousKeys = new Set([...Object.keys(globalProof),
    ...Object.keys(matchingGlobal ? record(record(parameters.technology_defaults)[technology.id]) : {})]);
  const oldValues = { ...Object.fromEntries([...previousKeys].filter(key => key in parameters).map(key => [key, parameters[key]])),
    ...record(oldGroup.values) };
  const oldProof = { ...globalProof, ...record(oldGroup.provenance) };
  const oldRetired = record(oldGroup.retired_parameters);
  const retiredKeys = Object.keys(oldValues).filter(key => !allowed.has(key));
  const retired = retiredKeys.length ? {
    values: { ...record(oldRetired.values), ...Object.fromEntries(retiredKeys.map(key => [key, oldValues[key]])) },
    provenance: { ...record(oldRetired.provenance), ...Object.fromEntries(retiredKeys.map(key => [key, oldProof[key]])) },
    reason: 'NOT_IN_CURRENT_TECHNOLOGY_SCHEMA',
  } : oldRetired;
  const selected = Object.fromEntries((technology.parameter_schema ?? []).map(field => [field.key, values[field.key]])
    .filter(([, value]) => value !== undefined && value !== null && value !== ''));
  if (selected.bitrate === undefined && selected.data_bitrate !== undefined) selected.bitrate = selected.data_bitrate;
  const provenance = Object.fromEntries(Object.entries(selected).map(([key, value]) => [key, { source: 'USER_CONFIRMED', status: 'CONFIRMED', value }]));
  const scoped = { ...record(parameters.technology_parameters), [technology.id]: { values: selected, provenance,
    ...(Object.keys(retired).length ? { retired_parameters: retired } : {}) } };
  // Mixed projects retain their primary technology and every declared network.
  if (parameters.technology && technologyKey(parameters.technology) !== technology.id && Array.isArray(parameters.networks) && parameters.networks.length) {
    return { ...parameters, technology_parameters: scoped };
  }
  const result: Parameters = { ...parameters, ...selected, technology: technology.id, technology_parameters: scoped,
    parameter_provenance: { ...record(parameters.parameter_provenance), ...provenance } };
  if (parameters.technology) {
    const previous = record(record(record(parameters.technology_parameters)[technologyKey(parameters.technology)]).values);
    const knownPrevious = new Set([...Object.keys(previous), ...Object.keys(record(parameters.parameter_provenance)),
      ...Object.keys(record(record(parameters.technology_defaults)[technologyKey(parameters.technology)]))]);
    for (const key of knownPrevious) {
      if (!allowed.has(key) && !(key in selected)) {
        delete result[key];
        delete record(result.parameter_provenance)[key];
      }
    }
  }
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
  const fields = (technology.parameter_schema ?? []).filter(field => field.scope === 'network' && Object.hasOwn(values, field.key)
    && values[field.key] !== undefined && values[field.key] !== null && values[field.key] !== '');
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
