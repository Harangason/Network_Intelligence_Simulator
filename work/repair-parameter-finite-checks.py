from pathlib import Path
p=Path('backend/communication/technologies/core/components.py');text=p.read_text(encoding='utf-8')
assert 'def _safe_finite('not in text
count=text.count('math.isfinite(');text=text.replace('math.isfinite(','_safe_finite(')
marker='def _parameter_expression('
helper='''def _safe_finite(value: Any) -> bool:
    """Untrusted integers and exact intermediate fractions may exceed float range."""
    try:
        return math.isfinite(value)
    except (OverflowError,TypeError,ValueError):
        return False


def _condition_equal(actual: Any, expected: Any) -> bool:
    """Numeric JSON int/float values match; boolean1 and numeric1 do not."""
    if isinstance(expected,(int,float)) and not isinstance(expected,bool):
        return isinstance(actual,(int,float)) and not isinstance(actual,bool) and _safe_finite(actual) and actual==expected
    return type(actual)is type(expected) and actual==expected


'''
assert text.count(marker)==1;text=text.replace(marker,helper+marker)
old="if not all(parameters.get(name) == value for name, value in constraint.get('when', {}).items()):"
assert old in text;text=text.replace(old,"if not all(_condition_equal(parameters.get(name),value) for name,value in constraint.get('when',{}).items()):")
p.write_text(text,encoding='utf-8');print({'finite_checks':count,'typed_conditions':True})
