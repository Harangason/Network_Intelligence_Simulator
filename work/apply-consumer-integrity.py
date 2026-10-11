from pathlib import Path
root=Path('.')
p=root/'backend/communication/technologies/core/components.py'
s=p.read_text(encoding='utf-8')
pos=s.index('\ndef _safe_finite')
s=s[:pos]+'''
def _normalize_wide_integers(parameters: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Decimal wire text is allowed only for declared wide integer fields.

    Python calculations retain exact integers; canonical JSON/UI can keep the
    decimal text and its identical provenance without an IEEE754 round trip.
    """
    result = dict(parameters)
    for name, spec in schema.items():
        wide = (spec.get('integer') or spec.get('type') == 'integer') and any(
            isinstance(spec.get(key), int) and abs(spec[key]) > 2**53 - 1
            for key in ('min', 'max', 'minimum', 'maximum'))
        value = result.get(name)
        if wide and isinstance(value, str) and len(value) <= 40 and re.fullmatch(r'-?(?:0|[1-9][0-9]*)', value):
            result[name] = int(value)
    return result

''' +s[pos:]
s=s.replace('parameters = dict(context.get("parameters") or {})','parameters = _normalize_wide_integers(dict(context.get("parameters") or {}), self.profile.get("parameter_schema", {}))',1)
s=s.replace("if not valid_type or (spec.get('integer') or kind == 'integer') and isinstance(value, (int, float)) and value != int(value):", "if not valid_type or (spec.get('integer') or kind == 'integer') and isinstance(value, (int, float)) and (value != int(value) or isinstance(value, float) and abs(value) > 2**53 - 1):",1)
s=s.replace("exact_equality=kind=='equal_expression' and constraint.get('exact_decimal_equality',False)", "integer_output = bool(self.profile.get('parameter_schema', {}).get(name, {}).get('integer') or self.profile.get('parameter_schema', {}).get(name, {}).get('type') == 'integer')\n                    exact_equality=kind=='equal_expression' and (integer_output or constraint.get('exact_decimal_equality',False))")
s=s.replace("exact_decimal=exact_equality or kind in", "exact_decimal=integer_output or exact_equality or kind in")
s=s.replace("outside |= not math.isclose(value, expected, rel_tol=0, abs_tol=1e-6)", "outside |= (value != expected if self.profile.get('parameter_schema', {}).get(name, {}).get('integer') else not math.isclose(value, expected, rel_tol=0, abs_tol=1e-6))")
s=s.replace("bound = total / denominator\n                                if ratio_kind=='equal_ratio':", "integer_output = bool(self.profile.get('parameter_schema', {}).get(name, {}).get('integer'))\n                                bound = Fraction(str(total)) / Fraction(str(denominator)) if integer_output else total / denominator\n                                if ratio_kind=='equal_ratio':")
s=s.replace("outside |= not _safe_finite(bound) or not math.isclose(value, bound, rel_tol=1e-9, abs_tol=1e-6)", "outside |= not _safe_finite(bound) or (value != bound if integer_output else not math.isclose(value, bound, rel_tol=1e-9, abs_tol=1e-6))")
p.write_text(s,encoding='utf-8')
p=root/'backend/communication/technologies/core/registry.py';s=p.read_text(encoding='utf-8')
s=s.replace('    required_rate_fields,','    required_rate_fields,\n    _normalize_wide_integers,')
s=s.replace("result.append({**deepcopy(spec), 'key': PARAMETER_UI_ALIASES.get(name, name)})", """field = {**deepcopy(spec), 'key': PARAMETER_UI_ALIASES.get(name, name)}
            if (spec.get('integer') or spec.get('type') == 'integer') and any(
                isinstance(spec.get(bound), int) and abs(spec[bound]) > 2**53 - 1 for bound in ('min', 'max', 'minimum', 'maximum')):
                field['numeric_encoding'] = 'DECIMAL_STRING'
                for bound, aliases in (('min', ('min', 'minimum')), ('max', ('max', 'maximum'))):
                    actual = next((spec[key] for key in aliases if spec.get(key) is not None), None)
                    if actual is not None:
                        field['decimal_' + bound] = str(actual)
                        field.pop(bound, None)
            result.append(field)""")
s=s.replace('        return result\n\n    def parameter_keys', "        schema = {field: spec for layer in self.profile(technology_id).get('default_stack') or (technology_id,)\n                  for field, spec in self.profile(layer).get('parameter_schema', {}).items()}\n        return _normalize_wide_integers(result, schema)\n\n    def parameter_keys",1)
s=s.replace('required_rates = {field for stack_id in stack for field in','required_rates = {field for stack_id in validation_stack for field in',1)
p.write_text(s,encoding='utf-8')
p=root/'backend/engineering/agent_tools/project_draft.py';s=p.read_text(encoding='utf-8')
s=s.replace(r'zum\s+(?:steuern\s+von\s+ventilen|ventil\s+steuern)', r'zum\s+(?:steuern\s+von\s+ventilen|ventil\s+steuern|(?:proportional\s+)?schlie(?:ß|ss)en\s+(?:eines?\s+)?ventils?)')
p.write_text(s,encoding='utf-8')
for file in ['api.ts','workflow-api.ts','engineering-api.ts']:
 p=root/'frontend/src/lib'/file;s=p.read_text(encoding='utf-8');s="import { readLosslessJson } from './lossless-json.ts';\n"+s
 s=s.replace('await response.json().catch(() => ({}))', 'await readLosslessJson(response).catch(() => ({}))');p.write_text(s,encoding='utf-8')
p=root/'frontend/src/lib/types.ts';s=p.read_text(encoding='utf-8');s=s.replace('  min?: number;\n  max?: number;', "  min?: number;\n  max?: number;\n  numeric_encoding?: 'DECIMAL_STRING';\n  decimal_min?: string;\n  decimal_max?: string;")
s=s.replace("default_status?: 'PROPOSED' | 'UNKNOWN';", "default_status?: 'PROPOSED' | 'PROPOSED_CONDITIONAL' | 'UNKNOWN';")
s=s.replace('category: "physical"', 'category: "technology" | "physical"');p.write_text(s,encoding='utf-8')
p=root/'frontend/src/lib/technology-parameters.ts';s=p.read_text(encoding='utf-8')
s=s.replace('return matches.length === 1 ? matches[0].value : undefined;', 'return matches.length && matches.every(item => item.value === matches[0].value) ? matches[0].value : undefined;')
pos=s.index('/** Catalog defaults')
s=s[:pos]+'''/** Parse a profile field without rounding protocol counters or durations. */
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

''' +s[pos:]
start=s.index('  for (const field of technology.parameter_schema ?? []) {');end=s.index('  return values;',start)
s=s[:start]+'''  // Dependencies may appear later in the schema. Iterate only proposed fields;
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
''' +s[end:];p.write_text(s,encoding='utf-8')
p=root/'frontend/src/components/simulation-wizard.tsx';s=p.read_text(encoding='utf-8')
s="import { parseLosslessJson } from '../lib/lossless-json.ts';\n"+s if not s.startswith('"use client"') else s.replace('"use client";', '"use client";\n\nimport { parseLosslessJson } from "../lib/lossless-json.ts";',1)
# Keep the use client directive first even if it uses single quotes.
if s.startswith("import { parseLosslessJson }") and "'use client'" in s:
 s=s.replace("import { parseLosslessJson } from '../lib/lossless-json.ts';\n",'').replace("'use client';", "'use client';\nimport { parseLosslessJson } from '../lib/lossless-json.ts';",1)
s=s.replace('booleanParameterValue,', 'booleanParameterValue, numericParameterValue,',1)
s=s.replace('JSON.parse(advancedConfig)', 'parseLosslessJson(advancedConfig)')
start=s.index('              if (!entered && field.required)');end=s.index('\n            }',start)
s=s[:start]+'''              return [field.key, numericParameterValue(field, entered)];''' +s[end:]
needle='  return (\n    <div title={field.description}>'
pos=s.index(needle,s.index('function ParameterControl'))
s=s[:pos]+'''  if (field.numeric_encoding === 'DECIMAL_STRING') {
    return <div className="field" title={field.description}>
      <label htmlFor={field.key}>{label}</label>{gap}
      <input defaultValue={String(value ?? '')} id={field.key} name={field.key} type="text" inputMode="numeric" required={field.required} />
      {conditionalProposal}
    </div>;
  }
''' +s[pos:]
s=s.replace('        step="any"\n        required={field.required}', '        step={field.integer ? "1" : "any"}\n        required={field.required}',1)
p.write_text(s,encoding='utf-8')
