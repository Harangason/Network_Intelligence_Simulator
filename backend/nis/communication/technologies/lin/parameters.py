"""Reviewed LIN clock evidence and generic-estimator alias adaptation."""
VALIDATE_WITHOUT_RATE = True
EXCLUDED_VALIDATION_FIELDS = {'bitrate', 'bitrate_bps'}

def _number(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def scoped_rate(resolved, key, value):
    if key == 'lin_bitrate_bps' and _number(value) > 0:
        resolved['_lin_native_rate_evidenced'] = True

def finalize_rate(resolved, rate_evidenced, phase_evidenced, declared, configured_scope, confirmed, matching_identity, matching_field, trusted_value):
    # Keep the reviewed native LDF clock distinct from an old generic rate.
    key = 'lin_bitrate_bps'
    native_source = next((scope for scope in (declared, configured_scope, confirmed)
                          if key in scope and matching_identity(scope, required=scope is confirmed)
                          and matching_field(scope,key) and trusted_value(scope,key)), {})
    if native_source:
        resolved[key] = native_source[key]
    scoped_rate_evidenced = resolved.pop('_lin_native_rate_evidenced',False)
    rate_evidenced = bool(native_source or scoped_rate_evidenced) and _number(resolved.get(key),0)>0
    if rate_evidenced:
        resolved['bitrate'] = resolved[key]  # Internal nominal estimator input only.
    return rate_evidenced
