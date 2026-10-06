"""Native serial-device rate acceptance for this timing owner."""
from backend.nis.communication.core.serial_parameter_evidence import finalize_local_rate as _finalize

def finalize_local_rate(target, resolved, rate_evidenced, evidence, number):
    return _finalize(target, resolved, rate_evidenced, evidence, number)
