"""Read-only pure native ingress diagnostic; no SQL calls or writes."""
import json
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.engineering.capacity.service import simulation_parameters_for_protocol
from backend.nis.communication.technologies.can_fd.timing import planning_frame_parameters

values = {'can_fd_dlc': 15, 'can_fd_wire_data_bytes': 64, 'can_fd_crc_bits': 21}
parameters = registry.simulation_defaults_for_project({
    'technology': 'lin',
    'explicit_technology_bitrates': {'can_fd': 2_000_000},
    'technology_parameters': {'can_fd': {'values': values, 'provenance': {
        key: {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED',
              'technology': 'can_fd', 'value': value} for key, value in values.items()}}},
}, ['lin', 'can_fd', 'ethernet'])
resolved = simulation_parameters_for_protocol('CAN_FD', parameters, confirmed_parameters=parameters)
prepared = planning_frame_parameters(2, resolved)
print(json.dumps({'saved_group': parameters['technology_parameters']['can_fd'],
    'resolved': {key: resolved.get(key) for key in [*values, '_simulation_assumption_fields',
        '_simulation_parameter_findings', '_simulation_parameters_usable']},
    'prepared': {key: prepared.get(key) for key in values}}, default=str, indent=2))
