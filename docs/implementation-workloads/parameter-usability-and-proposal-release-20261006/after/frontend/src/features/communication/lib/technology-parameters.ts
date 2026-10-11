import type { Technology, TechnologyParameterField } from '../../../shared/api/types';

type Parameters = Record<string, unknown>;
export type DeclaredNetwork = Parameters & { id: string; name?: string; technology?: string };
const record = (value: unknown): Parameters => value && typeof value === 'object' && !Array.isArray(value) ? value as Parameters : {};
const present = (value: unknown) => value === '' || value === null ? undefined : value;
const placeholderReference = (field: TechnologyParameterField, value: unknown) =>
  field.value_role && field.value_role !== 'CONFIGURATION' && typeof value === 'string' && /^simulation:[^:]+:[^:]+$/.test(value);

/** The native profile owns rates; everyday scenario controls precede details. */
export function commonTechnologyParameters(technology: Technology): TechnologyParameterField[] {
  const schema = technology.parameter_schema ?? [];
  const keys = [...technologyRateParameters(technology).map(field => field.key),
    'can_fd_brs', 'payload_bytes', 'cycle_ms', 'deadline_ms', 'duration_s', 'seed'];
  return [...new Set(keys)].map(key => schema.find(field => field.key === key))
    .filter((field): field is TechnologyParameterField => !!field && (!field.value_role || field.value_role === 'CONFIGURATION'));
}
export const technologyKey = (value: unknown) => {
  const key = String(value ?? '').toLowerCase().replace(/[ -]/g, '_');
  return ({automotive_ethernet:'ethernet',canfd:'can_fd',some_ip:'someip'} as Record<string,string>)[key] ?? key;
};
const matchingProof = (proof: Parameters, technologyId: string) => ['technology', 'technology_id', 'protocol']
  .every(key => !proof[key] || technologyKey(proof[key]) === technologyKey(technologyId));
const commonNetworkParameter = (parameters: Parameters, technologyId: string, key: string) => {
  const networks = (Array.isArray(parameters.networks) ? parameters.networks : []).map(record)
    .filter(item => technologyKey(item.technology) === technologyKey(technologyId));
  return networks.length && networks.every(item => {
    const proof = record(record(item.parameter_provenance)[key]);
    return present(item[key]) !== undefined && item[key] === networks[0][key]
      && proof.source === 'USER_CONFIRMED' && proof.status === 'CONFIRMED'
      && proof.value === item[key] && matchingProof(proof, technologyId);
  }) ? networks[0] : undefined;
};

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

export function technologyParameterApplicable(field: TechnologyParameterField, values: Parameters): boolean {
  return !(field.not_applicable_when ?? []).some(when => Object.entries(when).every(([key, value]) => values[key] === value));
}

/** Bind native phase names to their exact exported fields, without a protocol fallback. */
export function technologyRateParameters(technology: Technology): TechnologyParameterField[] {
  const schema = technology.parameter_schema ?? [];
  const model = technology.rate_model?.fields ?? [];
  const names = model.length ? model : technology.simulation_defaults?.rate_fields ?? [];
  return names.length ? names.map(name => schema.find(field => (field.native_key ?? field.key) === name))
    .filter((field): field is TechnologyParameterField => !!field)
    : schema.filter(field => field.scope === 'network' && field.unit === 'bit/s');
}

function resolvedProfileProposal(field: TechnologyParameterField): boolean {
  return field.simulation_default !== undefined && !!field.simulation_default_provenance
    && !['SCHEMA_SIMULATION_EXAMPLE', 'REGISTERED_PARAMETER_DEFAULT'].includes(field.simulation_default_provenance.basis);
}

/** Catalog defaults remain proposals; only matching saved values may override them. */
export function technologyParameterValues(parameters: Parameters, technology: Technology): Parameters {
  const scoped = record(record(parameters.technology_parameters)[technology.id]);
  const proposed = record(record(parameters.technology_defaults)[technology.id]);
  const global = technologyKey(parameters.technology) === technology.id ? parameters : {};
  const saved = record(scoped.values);
  const assumptions = record(record(record(parameters.simulation_parameter_assumptions)[technology.id]).values);
  const values = Object.fromEntries((technology.parameter_schema ?? []).map(field => {
    const stored = saved[field.key] ?? global[field.key];
    const storedProof = record(record(scoped.provenance)[field.key] ?? record(parameters.parameter_provenance)[field.key]);
    const supplied = placeholderReference(field, stored) && storedProof.status !== 'CONFIRMED'
      && storedProof.source !== 'EXPLICIT_USER_SPECIFICATION' ? undefined : stored;
    const common = field.scope === 'network' ? commonNetworkParameter(parameters, technology.id, field.key) : undefined;
    const value = present(common ? common[field.key] : supplied);
    const proof = common ? record(record(common.parameter_provenance)[field.key]) : record(record(scoped.provenance)[field.key] ?? record(parameters.parameter_provenance)[field.key]);
    const rate = field.unit === 'bit/s' && ['bitrate', 'arbitration_bitrate', 'data_bitrate'].includes(field.key);
    const matching = matchingProof(proof, technology.id);
    const confirmed = matching && (proof.status === 'CONFIRMED' && proof.source === 'USER_CONFIRMED' && proof.value === value || proof.source === 'EXPLICIT_USER_SPECIFICATION' && proof.value === value);
    const invalidRate = rate && (typeof value !== 'number' || !Number.isFinite(value) || value <= 0 || field.min !== undefined && value < field.min || field.max !== undefined && value > field.max || field.allowed_bps?.length && !field.allowed_bps.includes(value));
    const oldProposal = rate && (proof.status === 'REVIEW_REQUIRED' || proof.source === 'TECHNOLOGY_DEFAULT');
    const assumption = placeholderReference(field, assumptions[field.key]) ? undefined : present(assumptions[field.key]);
    const preset = resolvedProfileProposal(field);
    const fallback = assumption ?? (preset ? field.simulation_default : present(field.default) ?? present(proposed[field.key]) ?? field.simulation_default);
    return [field.key, !matching ? fallback : confirmed ? value : assumption ?? (invalidRate || oldProposal ? fallback : value ?? fallback)];
  }));
  // Dependencies may appear later in the schema. Iterate only proposed fields;
  // confirmed/explicit values always retain their original actual setting.
  const schema = technology.parameter_schema ?? [];
  for (let pass = 0; pass < schema.length; pass++) {
    let changed = false;
    for (const field of schema) {
      if (!field.conditional_defaults?.length) continue;
      if (field.scope === 'network' && commonNetworkParameter(parameters, technology.id, field.key)) continue;
      const proof = record(record(scoped.provenance)[field.key] ?? record(parameters.parameter_provenance)[field.key]);
      const explicit = matchingProof(proof, technology.id) && proof.value === values[field.key]
        && (proof.source === 'EXPLICIT_USER_SPECIFICATION' || proof.source === 'USER_CONFIRMED' && proof.status === 'CONFIRMED');
      const oldSuggestion = proof.status === 'REVIEW_REQUIRED' && /DEFAULT|PROPOSAL/.test(String(proof.source || ''));
      const savedAssumption = present(assumptions[field.key]) !== undefined;
      const savedActual = saved[field.key] ?? global[field.key];
      if (!explicit && !savedAssumption && !resolvedProfileProposal(field)
          && (oldSuggestion || savedActual === undefined || savedActual === null || savedActual === '')) {
        const suggestion = conditionalParameterDefault(field, values) ?? assumptions[field.key] ?? field.simulation_default;
        if (values[field.key] !== suggestion) { values[field.key] = suggestion; changed = true; }
      }
    }
    if (!changed) break;
  }
  return values;
}

export function technologyParameterUnverified(parameters: Parameters, key: string, technologyId: string): boolean {
  const scoped = record(record(parameters.technology_parameters)[technologyId]);
  if (key === 'technology') return technologyKey(parameters.technology) !== technologyKey(technologyId)
    && !Object.keys(record(scoped.values)).length
    && !Object.keys(record(record(record(parameters.simulation_parameter_assumptions)[technologyId]).values)).length;
  if (commonNetworkParameter(parameters, technologyId, key)) return false;
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

export function confirmTechnologyParameters(parameters: Parameters, technology: Technology, values: Parameters,
  options: {preserveSimulationAssumptions?: boolean} = {}): Parameters {
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
  const assumptionFields = new Set((technology.parameter_schema ?? []).filter(field =>
    options.preserveSimulationAssumptions && field.simulation_default != null
    && technologyParameterApplicable(field, values)
    && (field.default === undefined || resolvedProfileProposal(field))
    && technologyParameterUnverified(parameters, field.key, technology.id)).map(field => field.key));
  const assumptions = Object.fromEntries((technology.parameter_schema ?? []).filter(field => assumptionFields.has(field.key))
    .map(field => [field.key, values[field.key]]).filter(([, value]) => value !== undefined && value !== null && value !== ''));
  const assumptionState = { ...record(parameters.simulation_parameter_assumptions), [technology.id]: {
    values: assumptions, provenance: Object.fromEntries(Object.entries(assumptions).map(([key, value]) =>
      [key, {source:'NIS_SIMULATION_ASSUMPTION', status:'ASSUMED', technology:technology.id, hardware_evidence:false, value}])) }};
  const selected = Object.fromEntries((technology.parameter_schema ?? []).filter(field => !assumptionFields.has(field.key) && technologyParameterApplicable(field, values)).map(field => [field.key, values[field.key]])
    .filter(([, value]) => value !== undefined && value !== null && value !== ''));
  if (selected.bitrate === undefined && selected.data_bitrate !== undefined) selected.bitrate = selected.data_bitrate;
  const provenance = Object.fromEntries(Object.entries(selected).map(([key, value]) => [key, { source: 'USER_CONFIRMED', status: 'CONFIRMED', value }]));
  const scoped = { ...record(parameters.technology_parameters), [technology.id]: { values: selected, provenance,
    ...(Object.keys(retired).length ? { retired_parameters: retired } : {}) } };
  // Mixed projects retain their primary technology and every declared network.
  if (parameters.technology && technologyKey(parameters.technology) !== technology.id && Array.isArray(parameters.networks) && parameters.networks.length) {
    return { ...parameters, technology_parameters: scoped,
      ...(options.preserveSimulationAssumptions ? {simulation_parameter_assumptions: assumptionState} : {}) };
  }
  const result: Parameters = { ...parameters, ...selected, technology: technology.id, technology_parameters: scoped,
    parameter_provenance: { ...record(parameters.parameter_provenance), ...provenance },
    ...(options.preserveSimulationAssumptions ? {simulation_parameter_assumptions: assumptionState} : {}) };
  for (const key of assumptionFields) {
    delete result[key];
    delete record(result.parameter_provenance)[key];
  }
  for (const field of technology.parameter_schema ?? []) {
    if (placeholderReference(field, result[field.key]) && technologyParameterUnverified(parameters, field.key, technology.id)
        && present(values[field.key]) === undefined) {
      delete result[field.key];
      delete record(result.parameter_provenance)[field.key];
    }
  }
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


export type ParameterFinding = ReviewFinding & { severity?: string; technology?: string; network_id?: string;
  network_name?: string; node_name?: string; object_name?: string; missing_fields?: string[]; parameter_fields?: string[];
  parameter_findings?: Array<{parameter?: string; code?: string; message?: string}> };

/** A saved scenario is still not hardware evidence, but it is no longer an unsaved draft. */
export function parameterValueStatus(parameters: Parameters, key: string, technologyId: string) {
  if (!technologyParameterUnverified(parameters, key, technologyId)) return 'CONFIRMED';
  const assumed = record(record(record(parameters.simulation_parameter_assumptions)[technologyId]).values);
  return present(assumed[key]) !== undefined ? 'SAVED_ASSUMPTION' : 'PROPOSAL';
}

export function parameterReviewHref(projectId: string, technology: string, proposalId?: string) {
  const query = new URLSearchParams({mode:'parameters', project:projectId, technology:technologyKey(technology)});
  if (proposalId) query.set('proposal', proposalId);
  return `/studio?${query}#parameter-findings`;
}

export function findingsForParameter(findings: ParameterFinding[], technologyId: string, key: string) {
  return findings.filter(finding => technologyKey(finding.technology) === technologyKey(technologyId)
    && (finding.parameter_fields ?? finding.missing_fields ?? []).includes(key));
}
