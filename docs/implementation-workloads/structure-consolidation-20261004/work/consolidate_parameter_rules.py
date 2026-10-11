import ast
import textwrap
from edit_utils import read, write, apply

path = 'backend/nis/communication/registry.py'
source = read(path)
marker = '    def scheduling_implementation('
write(path, source.replace(marker, '''    def capacity_parameter_implementation(self, technology_id):
        """Optional evidence adaptation attached to the registered timing owner."""
        implementation = self.timing_implementation(technology_id)
        if implementation is None:
            return None
        from importlib import import_module, util
        name = implementation.__package__ + '.parameters'
        return import_module(name) if util.find_spec(name) else None

''' + marker, 1))
path = 'backend/nis/engineering/capacity/service.py'
source = read(path)
source = source.replace('    target = canonical(protocol)', "    target = canonical(protocol)\n    owner = DEFAULT_TECHNOLOGY_REGISTRY.capacity_parameter_implementation(protocol)", 1)
source = source.replace("            if target == 'LIN' and key == 'lin_bitrate_bps' and _number(value, 0) > 0:\n                resolved['_lin_native_rate_evidenced'] = True", "            scoped_hook = getattr(owner, 'scoped_rate', None)\n            if scoped_hook:\n                scoped_hook(resolved, key, value)")
source = source.replace('        if target == "CAN_FD":\n            phase_evidenced["arbitration_bitrate"] = True', "        phase_key = getattr(owner, 'phase_key', lambda key: None)('bitrate')\n        if phase_key:\n            phase_evidenced[phase_key] = True")
source = source.replace('            if key == "bitrate" and target == "CAN_FD":\n                phase_evidenced["arbitration_bitrate"] = True', "            phase_key = getattr(owner, 'phase_key', lambda key: None)(key)\n            if phase_key:\n                phase_evidenced[phase_key] = True")
start = source.index('    if target == "CAN_FD":\n        rate_evidenced =')
end = source.index('    if confirmed_parameters is not None:', start)
block = source[start:end]
lin_start = block.index("    if target == 'LIN':")
lin_body = textwrap.dedent(block[lin_start:].split('\n', 1)[1])
lin = '''"""Reviewed LIN clock evidence and generic-estimator alias adaptation."""
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
''' + textwrap.indent(lin_body, '    ') + '    return rate_evidenced\n'
write('backend/nis/communication/technologies/lin/parameters.py', lin)
write('backend/nis/communication/technologies/can_fd/parameters.py', '''"""Independent CAN-FD arbitration/data-phase evidence acceptance."""
def phase_key(key):
    return 'arbitration_bitrate' if key == 'bitrate' else None

def finalize_rate(resolved, rate_evidenced, phase_evidenced, declared, configured_scope, confirmed, matching_identity, matching_field, trusted_value):
    return phase_evidenced['arbitration_bitrate'] and (resolved.get('can_fd_brs') is False or phase_evidenced['data_bitrate'])
''')
source = source[:start] + '''    rate_hook = getattr(owner, 'finalize_rate', None)
    if rate_hook:
        rate_evidenced = rate_hook(resolved, rate_evidenced, phase_evidenced, declared, configured_scope,
                                  confirmed, matching_identity, matching_field, trusted_value)
''' + source[end:]
start = source.index('    if target in {"I2C", "SPI"}:')
end = source.index('    if rate_evidenced or target', start)
serial_body = textwrap.dedent(source[start:end].split('\n', 1)[1])
# Existing serial evidence owners retain independent protocols. Shared adaptation
# uses the published callback, without duplicating either native timing model.
serial = '''"""Shared evidence acceptance for registered serial timing implementations."""
def finalize_local_rate(target, resolved, rate_evidenced, confirmed_serial_evidence, _number):
''' + textwrap.indent(serial_body, '    ')
write('backend/nis/communication/core/serial_parameter_evidence.py', serial)
for key in ('i2c', 'spi'):
    write(f'backend/nis/communication/technologies/{key}/parameters.py', '''"""Native serial-device rate acceptance for this timing owner."""
from backend.nis.communication.core.serial_parameter_evidence import finalize_local_rate as _finalize

def finalize_local_rate(target, resolved, rate_evidenced, evidence, number):
    return _finalize(target, resolved, rate_evidenced, evidence, number)
''')
# Return the final status explicitly from the neutral serial adaptation.
serial += "    return resolved['_rate_evidenced']\n"
write('backend/nis/communication/core/serial_parameter_evidence.py', serial)
source = source[:start] + '''    local_hook = getattr(owner, 'finalize_local_rate', None)
    if local_hook:
        rate_evidenced = local_hook(target, resolved, rate_evidenced, confirmed_serial_evidence, _number)
''' + source[end:]
source = source.replace("rate_evidenced or target=='LIN'", "rate_evidenced or getattr(owner, 'VALIDATE_WITHOUT_RATE', False)")
source = source.replace("not (target=='LIN' and key in {'bitrate','bitrate_bps'})", "key not in getattr(owner, 'EXCLUDED_VALIDATION_FIELDS', ())")
write(path, source)
apply('parameter-evidence-owners')
