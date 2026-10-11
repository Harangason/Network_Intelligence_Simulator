from pathlib import Path
import json
keys=json.loads(Path('work/global-constraint-audit.json').read_text(encoding='utf-8'))['recognized_constraint_keys']
keys += ['source_revision','encoded_bytes_parameter','text_codepoints_parameter','bounded_product_parameters','text_utf16_units_parameter','ip_address_max','minimum_product_parameters','ip_address_min']
p=Path('backend/communication/technologies/core/components.py');s=p.read_text(encoding='utf-8');pos=s.index('\ndef _normalize_wide_integers')
addition='\n# Supported rule vocabulary is explicit; unknown rules must never silently pass.\n_PARAMETER_RULE_KEYS = frozenset('+repr(sorted(set(keys)))+')\n'
addition+='''
def validate_parameter_rule_syntax(profile: dict[str, Any]) -> None:
    """Reject unsupported rule DSL before a profile can be registered."""
    arities = {'sum': None, 'product': None, 'subtract': 2, 'integer_remainder': 2,
               'power': 2, 'maximum': None, 'minimum': None, 'ceiling': 1, 'floor': 1}
    def expression(value, depth=0):
        if depth > 64:
            raise ValueError('Technology parameter expression is too deep')
        if isinstance(value, str) or isinstance(value, (int, float)) and not isinstance(value, bool) and _safe_finite(value):
            return
        if not isinstance(value, dict) or len(value) != 1:
            raise ValueError('Invalid technology parameter expression')
        operation, terms = next(iter(value.items()))
        if operation not in arities or not isinstance(terms, list) or not terms or arities[operation] is not None and len(terms) != arities[operation]:
            raise ValueError(f'Unsupported technology parameter expression: {operation}')
        for term in terms:
            expression(term, depth + 1)
    for rule in profile.get('parameter_constraints') or ():
        if not isinstance(rule, dict) or not isinstance(rule.get('parameter'), str):
            raise ValueError('Technology parameter rule requires a parameter')
        unknown = set(rule) - _PARAMETER_RULE_KEYS
        if unknown:
            raise ValueError(f'Unsupported technology parameter rule keys: {sorted(unknown)}')
        for condition in ('when', 'when_not'):
            if not isinstance(rule.get(condition, {}), dict) or any(not isinstance(value, (str, int, float, bool)) for value in rule.get(condition, {}).values()):
                raise ValueError(f'Technology parameter {condition} requires explicit scalar conditions')
        for key in ('equal_expression', 'minimum_expression', 'maximum_expression', 'exclusive_minimum_expression', 'exclusive_maximum_expression'):
            if key in rule:
                expression(rule[key])

'''
s=s[:pos]+addition+s[pos:];p.write_text(s,encoding='utf-8')
p=Path('backend/communication/technologies/core/registry.py');s=p.read_text(encoding='utf-8').replace('    _normalize_wide_integers,', '    _normalize_wide_integers,\n    validate_parameter_rule_syntax,')
s=s.replace('        key = self.normalize_id(technology_id)\n        if key in self._profiles:', '        validate_parameter_rule_syntax(profile)\n        key = self.normalize_id(technology_id)\n        if key in self._profiles:',1);p.write_text(s,encoding='utf-8')
p=Path('backend/tests/test_parameter_consumer_integrity.py');s=p.read_text(encoding='utf-8')
s+='''

@pytest.mark.parametrize('rule', [
    {'parameter':'payload_bytes','minimum_ratio':1},
    {'parameter':'payload_bytes','when':{'mode':['STANDARD']},'allowed':[1]},
    {'parameter':'payload_bytes','equal_expression':{'divide':[1,2]}},
    {'parameter':'payload_bytes','equal_expression':{'subtract':[1]}},
])
def test_unimplemented_rule_cannot_be_registered_and_silently_ignored(rule):
    from backend.communication.technologies.core.registry import TechnologyRegistry
    isolated = TechnologyRegistry()
    profile = deepcopy(registry.profile('can'))
    profile['parameter_constraints'] = [rule]
    with pytest.raises(ValueError):
        isolated.register_profile('can',profile)
    assert not isolated.profiles()
'''
p.write_text(s,encoding='utf-8')
