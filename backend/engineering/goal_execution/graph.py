"""Canonical graph queries, independent of a selected UI row or a naming convention."""
from copy import deepcopy
from hashlib import sha256
import json
from .models import ModelSituation
from ..physical_ports import technology_id

REFERENCE_FIELDS = ('hardware_node_id', 'function_id', 'interface_id', 'hardware_interface_id', 'message_id',
    'hardware_node_ref', 'hardware_interface_ref', 'controller_ref', 'port_ref', 'network_ref', 'technology_binding_ref')


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


class ModelGraphService:
    def __init__(self, model, resources=None, *, state=None, relations=()):
        self.model, self.resources = model, resources or {}
        self.state = state or {'parameters': model.get('parameters', {}), 'topology': model.get('topology', {})}
        self.relations = list(relations)
        self.hardware = {str(x['id']): x for x in model.get('hardware', [])}
        self.functions = {str(x['id']): x for x in model.get('functions', [])}
        self.interfaces = {str(x['id']): x for x in model.get('interfaces', [])}
        self.hni = {str(x['id']): x for x in model.get('hardware-interfaces', [])}
        self.messages = {str(x['id']): x for x in model.get('messages', [])}
        self.signals = {str(x['id']): x for x in model.get('signals', [])}
        self.networks = {str(x['id']): x for x in model.get('parameters', {}).get('networks', [])}
        self.objects = {**self.hardware, **self.functions, **self.interfaces, **self.hni, **self.messages, **self.signals, **self.networks,
            **{str(x.get('id') or x.get('connection_id')): x for values in self.resources.values() for x in values}}
        # A simulation attaches SIMULATED_IN observations to the unchanged route.
        # Those are output evidence, not a new architecture that revokes its own
        # authorization. Keep them queryable, but outside the source fingerprint.
        source_relations = [r for r in self.relations if not (r.get('relation_type') == 'SIMULATED_IN'
            and r.get('source') == 'simulation_derived' and r.get('target_type') == 'SimulationRun')]
        self.revision = digest({'model': model, 'resources': self.resources, 'relations': source_relations})

    @classmethod
    def load(cls):
        from ..agent_tools import model as access
        from ..workflow.service import WorkflowStatusService
        from ..project_context import current_project_id
        from ..relations import list_relations
        from ..pagination import all_pages
        from .store import resources
        return cls(access.model(), resources(), state=access.json_safe(WorkflowStatusService(current_project_id()).get()),
                   relations=access.json_safe(all_pages(list_relations)))

    def find_object(self, ref):
        if ref in self.objects:
            return self.objects[ref]
        matches = [row for row in self.objects.values() if row.get('name', '').casefold() == str(ref).casefold()]
        if len(matches) != 1:
            raise ValueError(f'Objekt {ref!r} ist nicht eindeutig: {len(matches)} Treffer. Kanonische ID wählen.')
        return matches[0]

    def find_related_objects(self, ref):
        ids = set()
        for relation in self.relations:
            source, target = str(relation.get('source_id')), str(relation.get('target_id'))
            if ref in (source, target): ids.update((source, target))
        ids.update(key for key, row in self.objects.items() if ref in map(str, [row.get(field) for field in REFERENCE_FIELDS]))
        return [self.objects[key] for key in sorted(ids - {ref}) if key in self.objects]

    def find_host_hardware(self, function_ref):
        function = self.functions.get(function_ref)
        hosts = {str(function['hardware_node_id'])} if function and function.get('hardware_node_id') else set()
        hosts.update(str(r['target_id']) for r in self.relations if str(r.get('source_id')) == function_ref
                     and r.get('relation_type') in {'RUNS_ON', 'MAPPED_TO'} and str(r.get('target_id')) in self.hardware)
        if len(hosts) != 1 or not hosts <= self.hardware.keys():
            raise ValueError(f'Funktionszuordnung {function_ref} fehlt oder ist mehrdeutig.')
        return self.hardware[next(iter(hosts))]

    def host(self, ref):
        if ref in self.hardware: return self.hardware[ref]
        if ref in self.functions: return self.find_host_hardware(ref)
        item = self.find_object(ref)
        for key in ('function_id', 'hardware_node_id', 'interface_id', 'message_id', 'hardware_node_ref', 'hardware_interface_ref', 'port_ref'):
            if item.get(key): return self.host(str(item[key]))
        raise ValueError(f'Keine Hardwarezuordnung für {ref}.')

    def find_functions_on_hardware(self, ref):
        return [x for x in self.functions.values() if str(x.get('hardware_node_id')) == ref]

    def find_function_interfaces(self, ref):
        return [x for x in self.interfaces.values() if str(x.get('function_id')) == ref]

    def find_hardware_interfaces(self, ref):
        return [x for x in self.hni.values() if str(x.get('hardware_node_id')) == ref]

    def find_network_membership(self, ref):
        return sorted({str(x['network_ref']) for x in self.find_hardware_interfaces(ref) if x.get('network_ref')})

    def find_networks_for_interface(self, ref):
        interface = self.hni.get(ref, {})
        return [self.networks[interface['network_ref']]] if interface.get('network_ref') in self.networks else []

    def find_routes_between(self, source, target):
        src, dst = str(self.host(source)['id']), str(self.host(target)['id'])
        return [route for route in self.model.get('routing', []) if route.get('status') not in {'SUPERSEDED','DEPRECATED','REJECTED'}
                and str(route.get('source', {}).get('node_id')) == src
                and any(str(endpoint.get('node_id')) == dst for endpoint in route.get('destinations', []))]

    def find_transport_units_between(self, source, target):
        ids = {str(mid) for route in self.find_routes_between(source, target)
               for mid in [*(route.get('payload', {}).get('message_ids') or []), route.get('payload', {}).get('message_id')] if mid}
        return [self.messages[mid] for mid in sorted(ids) if mid in self.messages]

    def find_gateways_between(self, source, target):
        from ..communication_repair import RepairPlanner
        objects = {kind: list(rows.values()) for kind, rows in [('HardwareNode', self.hardware), ('Function', self.functions),
                   ('Interface', self.interfaces), ('HardwareNetworkInterface', self.hni), ('Message', self.messages), ('Signal', self.signals)]}
        planner = RepairPlanner(self.state, objects, self.model.get('routing', []))
        paths = []
        for src in self.find_hardware_interfaces(str(self.host(source)['id'])):
            for dst in self.find_hardware_interfaces(str(self.host(target)['id'])):
                paths.extend(planner.paths(str(src['id']), str(dst['id'])))
        return paths

    def find_upstream_dependencies(self, ref):
        result, pending = set(), [ref]
        while pending:
            item = self.objects.get(pending.pop(), {})
            for key in REFERENCE_FIELDS:
                target = str(item.get(key) or '')
                if target in self.objects and target not in result:
                    result.add(target); pending.append(target)
        return sorted(result)

    def find_downstream_dependencies(self, ref):
        return sorted(key for key in self.objects if ref in self.find_upstream_dependencies(key))

    def find_technology_bindings(self, ref=None):
        bindings = []
        for message in self.messages.values():
            if ref and str(message['id']) != ref and ref not in self.find_upstream_dependencies(str(message['id'])): continue
            configuration = message.get('configuration') or {}
            bindings.extend(configuration.get('physical_transmit_bindings') or [])
            if configuration.get('transport_unit'): bindings.append(configuration['transport_unit'])
        for signal in self.signals.values():
            if not ref or ref == str(signal['id']) or ref in self.find_upstream_dependencies(str(signal['id'])):
                values = signal.get('protocol_bindings') or []
                bindings.extend([values] if isinstance(values, dict) else values)
        return bindings

    def find_communication_capabilities(self, hardware_ref):
        explicit = self.resources.get('CommunicationCapability', [])
        embedded = (self.hardware.get(hardware_ref, {}).get('hardware_information') or {}).get('communication_capabilities', [])
        return [{**x, 'hardware_node_ref': hardware_ref} for x in [*explicit, *embedded] if str(x.get('hardware_node_ref', hardware_ref)) == hardware_ref]

    find_available_hardware_capabilities = find_communication_capabilities

    def find_communication_controllers(self, hardware_ref):
        explicit = self.resources.get('CommunicationController', [])
        embedded = (self.hardware.get(hardware_ref, {}).get('hardware_information') or {}).get('communication_controllers', [])
        return [{**x, 'hardware_node_ref': hardware_ref} for x in [*explicit, *embedded] if str(x.get('hardware_node_ref', hardware_ref)) == hardware_ref]

    def find_ports(self, hardware_ref):
        ports = [deepcopy(p) for p in self.resources.get('PhysicalPort', []) if p['hardware_node_ref'] == hardware_ref]
        represented = {p['hardware_interface_ref'] for p in ports}
        # Existing canonical connectors are readable legacy facts, never new capacity.
        for interface in self.find_hardware_interfaces(hardware_ref):
            if str(interface['id']) not in represented and interface.get('physical_port_ref'):
                ports.append({'id': interface['physical_port_ref'], 'hardware_node_ref': hardware_ref,
                    'controller_ref': interface.get('controller_ref'), 'hardware_interface_ref': str(interface['id']),
                    'technology': interface['technology'], 'channel_index': interface.get('channel_index'),
                    'direction': 'BIDIRECTIONAL', 'network_ref': interface.get('network_ref'),
                    'connection_status': 'CONNECTED' if interface.get('network_ref') else 'FREE',
                    'provenance': {'source': 'canonical-hardware-interface', 'legacy': True}})
        return ports

    def find_ports_by_technology(self, hardware_ref, technology):
        return [p for p in self.find_ports(hardware_ref) if technology_id(p['technology']) == technology_id(technology)]

    def find_free_ports(self, hardware_ref, technology):
        return [p for p in self.find_ports_by_technology(hardware_ref, technology) if not p.get('network_ref') and p['connection_status'] == 'FREE']

    def find_network_for_port(self, port_ref):
        port = next((p for hw in self.hardware for p in self.find_ports(hw) if p['id'] == port_ref), {})
        return self.networks.get(port.get('network_ref'))

    def find_port_capacity(self, controller_ref):
        controller = next((c for hw in self.hardware for c in self.find_communication_controllers(hw) if c['id'] == controller_ref), None)
        if not controller: return {'controller_ref': controller_ref, 'known': False, 'available_channels': []}
        owner = controller['hardware_node_ref']
        used = set(controller.get('active_channels') or [])
        used.update(p.get('channel_index') for p in self.find_ports(owner) if p.get('controller_ref') == controller_ref)
        used.update(p.get('channel_index') for p in self.find_hardware_interfaces(owner) if p.get('controller_ref') == controller_ref)
        maximum = controller.get('max_channels')
        free = [i for i in range(1, maximum + 1) if i not in used] if isinstance(maximum, int) and maximum >= 0 else []
        return {'controller_ref': controller_ref, 'known': isinstance(maximum, int), 'max_channels': maximum,
                'used_channels': sorted(i for i in used if isinstance(i, int)), 'available_channels': free}

    def find_free_channels(self, controller_ref):
        return self.find_port_capacity(controller_ref)['available_channels']

    def can_create_port(self, hardware_ref, technology):
        from .ports import inspect_port_decision
        return inspect_port_decision(self, hardware_ref, technology, None)

    def can_connect_port(self, port_ref, network_ref):
        from .ports import connection_findings
        port = next((p for hw in self.hardware for p in self.find_ports(hw) if p['id'] == port_ref), None)
        return connection_findings(self, port, self.networks.get(network_ref))

    def situation(self, targets):
        target_objects = [self.find_object(ref) for ref in targets]
        capacities = self.state.get('latest_analyses', {}).get('capacity_timing', {})
        analyses = list((self.state.get('latest_analyses') or {}).values())
        findings = [f for analysis in analyses for f in analysis.get('findings', [])]
        gaps = [{'hardware_ref': hw, 'field': 'communication_capabilities', 'reason': 'Keine expliziten Hardwarefähigkeiten erfasst.'}
                for hw in self.hardware if not self.find_communication_capabilities(hw)]
        return ModelSituation(project_ref=self.model['project_id'], project_revision=self.revision,
            target_objects=target_objects, related_objects=[o for ref in targets for o in self.find_related_objects(ref)],
            functions=list(self.functions.values()), function_mappings=[{'function_ref': x['id'], 'hardware_node_ref': x.get('hardware_node_id')} for x in self.functions.values()],
            hardware_nodes=list(self.hardware.values()), logical_node_addresses=[{'hardware_node_ref': x['id'], 'address': x.get('logical_node_address'), 'status': x.get('address_status')} for x in self.hardware.values()],
            hardware_interfaces=list(self.hni.values()), functional_interfaces=list(self.interfaces.values()), payload_elements=list(self.signals.values()),
            transport_units=list(self.messages.values()), networks=list(self.networks.values()), technology_bindings=self.find_technology_bindings(), routes=self.model.get('routing', []),
            gateways=[h for h in self.hardware.values() if h.get('device_type') == 'Gateway'],
            capacity_results=[capacities] if capacities else [], timing_results=[capacities] if capacities else [],
            open_findings=findings, data_gaps=gaps,
            assumptions=[{'source': 'capacity_timing', **(capacities.get('provenance', {}).get('assumptions') or {})}] if capacities else [],
            stale_results=[x for x in [*self.state.get('simulation_snapshots', []), *analyses] if x.get('status') in {'STALE', 'OUTDATED'}],
            communication_capabilities=[c for hw in self.hardware for c in self.find_communication_capabilities(hw)],
            communication_controllers=[c for hw in self.hardware for c in self.find_communication_controllers(hw)],
            physical_ports=[p for hw in self.hardware for p in self.find_ports(hw)], network_connections=self.resources.get('NetworkConnection', []))
