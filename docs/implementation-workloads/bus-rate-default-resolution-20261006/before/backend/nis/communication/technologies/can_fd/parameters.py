"""Independent CAN-FD arbitration/data-phase evidence acceptance."""
def phase_key(key):
    return 'arbitration_bitrate' if key == 'bitrate' else None

def finalize_rate(resolved, rate_evidenced, phase_evidenced, declared, configured_scope, confirmed, matching_identity, matching_field, trusted_value):
    return phase_evidenced['arbitration_bitrate'] and (resolved.get('can_fd_brs') is False or phase_evidenced['data_bitrate'])
