"""Independent CAN-FD arbitration/data-phase evidence acceptance."""
def phase_key(key):
    return 'arbitration_bitrate' if key == 'bitrate' else None

def finalize_rate(resolved, rate_evidenced, phase_evidenced, declared, configured_scope, confirmed, matching_identity, matching_field, trusted_value):
    return phase_evidenced['arbitration_bitrate'] and (resolved.get('can_fd_brs') is False or phase_evidenced['data_bitrate'])


def rate_planning_values(requested, current, explicit):
    """Keep the actual controller clock; derive candidate register divisors exactly."""
    proposed = dict(requested)
    clock = explicit.get('can_clock_hz', current.get('can_clock_hz'))
    if not isinstance(clock, (int, float)) or isinstance(clock, bool) or clock <= 0:
        return proposed
    proposed['can_clock_hz'] = clock
    for rate, divider, tseg1, tseg2 in (
        ('arbitration_bitrate', 'can_prescaler', 'can_tseg1_tq', 'can_tseg2_tq'),
        ('data_bitrate', 'can_fd_data_prescaler', 'can_fd_data_tseg1_tq', 'can_fd_data_tseg2_tq')):
        settings = {**current, **proposed}
        terms = [settings.get(key) for key in (rate, tseg1, tseg2)]
        if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in terms) and terms[0] > 0:
            divisor = clock / (terms[0] * (1 + terms[1] + terms[2]))
            if divisor > 0 and divisor.is_integer():
                proposed[divider] = int(divisor)
    return proposed
