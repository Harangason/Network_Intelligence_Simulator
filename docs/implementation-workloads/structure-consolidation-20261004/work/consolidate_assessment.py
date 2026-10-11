"""Route scheduling contracts through existing registered timing owners."""
import ast
import textwrap
from edit_utils import read, write, extract, apply

path = 'backend/nis/traces/trace_support.py'
write(path, read(path) + '\ndef exact_iso_utc(timestamp: float) -> str:\n    """Preserve runtime timestamp precision independently of demo exports."""\n    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")\n')
path = 'backend/nis/communication/technologies/ethernet/runtime.py'
write(path, read(path).replace('iso_utc as _utc', 'exact_iso_utc as _utc'))

path = 'backend/nis/communication/registry.py'
source = read(path)
marker = '    def get_capabilities('
methods = '''    def scheduling_implementation(self, technology_id):
        """Use the registered timing owner; no parallel technology registry."""
        implementation = self.timing_implementation(technology_id)
        if implementation is None:
            return None
        from importlib import import_module
        return import_module(implementation.__package__ + '.scheduling')

    def forwarded_release_wait(self, row, period):
        owner = self.scheduling_implementation(row.get('protocol'))
        hook = getattr(owner, 'forwarded_release_wait', None)
        return hook(row, period) if hook else 0

'''
write(path, source.replace(marker, methods + marker, 1))
path = 'backend/nis/communication/technologies/ethernet/scheduling.py'
write(path, read(path) + '''

# Physical ports have independent rates and queues; nominal total is no bus limit.
INDEPENDENT_PORTS = True

def schedule_context(rows, policy, periods, result):
    return schedule(rows, result)

def policy_only_eligible(entry, check):
    # Preserve the published raw-ID behavior of the historical sizing service.
    return entry['protocol'] == 'ETHERNET' and check['status'] in {'UNVERIFIED', 'PROFILE_INCOMPLETE'}
''')
path = 'backend/nis/communication/technologies/lin/scheduling.py'
write(path, read(path) + '''

def forwarded_release_wait(row, period):
    return period if row.get('protocol') == 'LIN' and row.get('route_segment_index', 1) > 1 else 0

def validate_policy(policy):
    if number(policy.get('lin_timebase_ms')) <= 0:
        raise ValueError('communication_sizing.lin_timebase_ms muss positiv sein.')
    if number(policy.get('lin_master_jitter_ms'), -1) < 0:
        raise ValueError('LIN Master-Jitter darf nicht negativ sein.')

def reserve_reason():
    return 'Reservierte LIN-Slots lassen zu wenig Reserve.'
''')
path = 'backend/nis/engineering/capacity/dimensioning.py'
source = read(path).replace('"maximum_generated_period_ms", "lin_timebase_ms"', '"maximum_generated_period_ms"')
source = source.replace('    if number(policy.get("lin_master_jitter_ms"), -1) < 0:\n        raise ValueError("LIN Master-Jitter darf nicht negativ sein.")', "    from backend.nis.communication.technologies.lin.scheduling import validate_policy\n    validate_policy(policy)")
source = source.replace('    is_ethernet = protocol in {"ETHERNET", "AUTOMOTIVE_ETHERNET"}', "    scheduling = DEFAULT_TECHNOLOGY_REGISTRY.scheduling_implementation(protocol)\n    independent_ports = getattr(scheduling, 'INDEPENDENT_PORTS', False)")
source = source.replace('not is_ethernet', 'not independent_ports')
start = source.index("        handler = import_module(implementation.__package__ + '.scheduling').schedule")
end = source.index('\n    else:\n        reason =', start)
source = source[:start] + '''        handler = getattr(scheduling, 'schedule_context', scheduling.schedule)
        result = handler(rows, policy, periods, result)
        accepted = {'FEASIBLE_UNDER_ASSUMPTIONS'} if independent_ports else {'UNVERIFIED', 'FEASIBLE_UNDER_ASSUMPTIONS'}
        if result['status'] not in accepted or (not independent_ports and not result['responses']):
            return result''' + source[end:]
source = source.replace('                reasons.append("Reservierte LIN-Slots lassen zu wenig Reserve.")', "                scheduling = DEFAULT_TECHNOLOGY_REGISTRY.scheduling_implementation(candidate[0]['protocol'])\n                reasons.append(scheduling.reserve_reason())")
source = source.replace('        if entry["protocol"] != "ETHERNET" or check["status"] not in {"UNVERIFIED", "PROFILE_INCOMPLETE"}:', "        scheduling = DEFAULT_TECHNOLOGY_REGISTRY.scheduling_implementation(entry['protocol'])\n        eligible = getattr(scheduling, 'policy_only_eligible', lambda entry, check: False)\n        if not eligible(entry, check):")
source = source.replace('(proposals.get(row.get("message_id"), row["cycle_ms"]) if row.get("protocol") == "LIN" and row.get("route_segment_index", 1) > 1 else 0)', 'DEFAULT_TECHNOLOGY_REGISTRY.forwarded_release_wait(row, proposals.get(row.get("message_id"), row["cycle_ms"]))')
write(path, source)
path = 'backend/nis/engineering/capacity/service.py'
write(path, read(path).replace('(item["cycle_ms"] if item["protocol"] == "LIN" and item.get("route_segment_index", 1) > 1 else 0)', 'DEFAULT_TECHNOLOGY_REGISTRY.forwarded_release_wait(item, item["cycle_ms"])'))

# Only CAN-FD has an implemented single-bus request/response transport contract.
path = 'backend/nis/engineering/capacity/transmission.py'
chunk, source = extract(read(path), {'bus_request_pairs'})
write('backend/nis/communication/technologies/can_fd/request_response.py', '"""Existing bounded CAN-FD unicast request/response proof."""\nfrom backend.nis.engineering.capacity.transmission import profile, positive\n\n' + chunk)
write(path, source + '\n\ndef bus_request_pairs(rows):\n    """Compatibility export of the implemented CAN-FD exchange contract."""\n    from backend.nis.communication.technologies.can_fd.request_response import bus_request_pairs as validate\n    return validate(rows)\n')
apply('assessment-owners')
