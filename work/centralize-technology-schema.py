"""Mechanical relocation of the existing form descriptors to their profile owner."""
from pathlib import Path
import textwrap

root = Path(__file__).resolve().parents[1]
base = root / 'docs/implementation-workloads/technology-full-parameter-audit-20261001/before'
paths = ['backend/app/simulation_service.py', 'backend/communication/technologies/catalog.py',
         'backend/communication/technologies/core/registry.py']
for path in paths:
    dest = base / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes((root / path).read_bytes())
service = root / paths[0]
source = service.read_text(encoding='utf-8')
start = source.index('    @staticmethod\n    def _parameter_schema(')
end = source.index('    def prepare_config(', start)
method = textwrap.dedent(source[start:end]).replace('@staticmethod\n', '', 1)
method = method.replace('def _parameter_schema(technology_id: str, technology: dict[str, Any])',
                        'def _parameter_form_schema(technology_id: str, technology: dict[str, Any], rate_source: dict[str, Any], review: dict[str, Any])', 1)
method = method.replace('    from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry\n    rate_source = registry.rate_profile(technology_id)\n', '')
method = method.replace('registry.normalize_id(technology_id)', 'technology_id')
method = method.replace("    review = registry.parameter_defaults_review(technology_id)\n", '')
# Shared scenario/requirement fields are not universal technology requirements.
# Rate fields remain mandatory. Capacity proofs retain their own strict requirements.
method = method.replace('    return fields\n', '''    rate_keys = {item["key"] for item in rate_fields}
    for item in fields:
        item["required"] = item["key"] in rate_keys
        item["parameter_origin"] = "TRANSPORT_PROFILE" if item["key"] in rate_keys else "NIS_SCENARIO"
        item["default_status"] = "PROPOSED" if "default" in item else "UNKNOWN"
        item["source"] = review["source"] if item["key"] in rate_keys else "docs/COMMUNICATION_DESIGN_CONTRACT.md"
        item["source_revision"] = review.get("source_revision") if item["key"] in rate_keys else "NIS_SCENARIO_POLICY_V1"
    return fields
''')
service.write_text(source[:start] + '''    @staticmethod
    def _parameter_schema(technology_id: str, technology: dict[str, Any]) -> list[dict[str, Any]]:
        """Render the registered profile; HTTP does not own parameter definitions."""
        return COMMUNICATION_TECHNOLOGY_REGISTRY.parameter_fields(technology_id)

''' + source[end:], encoding='utf-8')
catalog = root / paths[1]
source = catalog.read_text(encoding='utf-8')
source += '\n\n' + method
catalog.write_text(source, encoding='utf-8')

registry_path = root / paths[2]
source = registry_path.read_text(encoding='utf-8')
start = source.index('    def parameter_defaults_review(')
end = source.index('    def list_all(', start)
old = source[start:end]
# Reuse precisely the current default algorithm, while moving policy to catalog.
body = textwrap.dedent(old).replace('def parameter_defaults_review(self, technology_id: str)',
                                   'def _parameter_defaults_review(technology_id: str, profile: dict[str, Any])', 1)
body = body.replace('    profile = self.rate_profile(technology_id)\n', '')
body = body.replace('self.normalize_id(technology_id)', 'technology_id')
source = source[:start] + '''    def parameter_defaults_review(self, technology_id: str) -> dict[str, Any]:
        from ..catalog import _parameter_defaults_review
        return _parameter_defaults_review(self.normalize_id(technology_id), self.rate_profile(technology_id))

    def parameter_fields(self, technology_id: str) -> list[dict[str, Any]]:
        """One profile-owned schema for UI, wizard and API consumers."""
        from ..catalog import PARAMETER_UI_ALIASES
        profile = self.profile(technology_id)
        result = []
        for name, spec in profile.get('parameter_schema', {}).items():
            if not spec.get('label'):
                continue
            result.append({**deepcopy(spec), 'key': PARAMETER_UI_ALIASES.get(name, name)})
        return result

''' + source[end:]
registry_path.write_text(source, encoding='utf-8')
source = catalog.read_text(encoding='utf-8') + '\n\n' + body
old = '''def technology_definitions() -> list[dict[str, Any]]:
    return [_spec(*row) for row in ROWS]
'''
new = '''PARAMETER_UI_ALIASES = {'bitrate_bps': 'bitrate', 'nominal_bitrate_bps': 'arbitration_bitrate',
                        'data_bitrate_bps': 'data_bitrate'}
PARAMETER_CORE_ALIASES = {alias: key for key, alias in PARAMETER_UI_ALIASES.items()}


def technology_definitions() -> list[dict[str, Any]]:
    definitions = [_spec(*row) for row in ROWS]
    by_id = {profile['id']: profile for profile in definitions}
    for profile in definitions:
        rate_profile = profile
        if not (profile.get('rate_model') or {}).get('fields'):
            rate_profile = next((by_id[layer] for layer in profile['default_stack']
                                 if by_id[layer]['rate_model'].get('fields')), profile)
        review = _parameter_defaults_review(profile['id'], rate_profile)
        fields = _parameter_form_schema(profile['id'], profile, rate_profile, review)
        profile['parameter_schema'] = {
            PARAMETER_CORE_ALIASES.get(item['key'], item['key']): {
                key: value for key, value in item.items() if key != 'key'
            } for item in fields
        }
    return definitions
'''
assert old in source
catalog.write_text(source.replace(old, new), encoding='utf-8')
print('Relocated schema definitions; all values unchanged; scenario origin made explicit.')
