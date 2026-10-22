def _materialize_reference_bindings(reference, spec, changes, existing, ensure, hardware_refs, document_evidence):
    """Bind an accepted NIS plan to the ordinary proposed canonical objects.

    This adapter does not write, approve, infer extra recipients, or claim
    executable processing. All writes remain proposal validate/review/apply.
    """
    from backend.nis.agent.orchestration.project_intake import document_fact_identity
    plan = reference['proposal']
    by_device = {row['id']: row for row in plan['devices']}
    by_fact = {value: key for key, value in reference['fact_id_map'].items()}
    facts = {by_fact[document_fact_identity(row)]: row for row in document_evidence['components']}
    device_names, port_names, port_networks = {}, {}, {}
    for chain in spec['chains']:
        config = chain.get('configuration') or {}
        device_id, port_id = config.get('reference_device_id'), config.get('reference_port_id')
        if not device_id or not port_id:
            raise ValueError('Der Referenzadapter verliert eine Teilnehmer-/Portidentität.')
        if device_id in device_names and device_names[device_id] != chain['hardware_name']:
            raise ValueError('Referenzgruppen mit mehreren Kommunikationsinstanzen müssen als konkrete Einzelgeräte geplant werden.')
        device_names[device_id] = chain['hardware_name']
        port_names[port_id] = chain['interface_name']
        port_networks[port_id] = chain.get('transport_network_ref')
    device_refs = {key: hardware_refs[name.casefold()] for key, name in device_names.items()}
    stamp = {'source': 'REFERENCE_ASSUMPTION', 'design_id': reference['design_id'],
             'revision': reference['revision'], 'request_sha256': reference['request_sha256'],
             'source_sha256': reference['source_sha256'], 'review_source': reference['review_source'],
             'processing_evidence': 'NONE', 'timing_evidence': 'NONE'}
    created = {('$' + item['local_ref']): item for item in changes}

    def row_for(ref, kind):
        item = created.get(ref)
        if item:
            if item['object_type'] != kind:
                raise ValueError('Referenzbindung verwendet einen falschen kanonischen Objekttyp.')
            return item['data']
        return next((row for row in existing.get(kind, []) if str(row['id']) == ref), None)

    def source_metadata(ids):
        return [{'fact_id': reference['fact_id_map'][key], 'source_sha256': reference['source_sha256'],
                 'source_context': facts[key].get('source_context', []), 'source_quote': facts[key]['source_quote'],
                 'kind': facts[key]['kind'], 'role': facts[key]['role']} for key in ids]

    # Concrete inventory and non-communicating context retain their own roles.
    # A passive chassis or software service is not a fabricated ECU or packet.
    context_bindings = []
    for device in plan['devices']:
        if device['kind'] == 'PHYSICAL_CONTEXT':
            context_bindings.append({**deepcopy(device), 'source_bindings': source_metadata(device['source_fact_ids']),
                'contained_hardware_node_refs': [device_refs[key] for key in device.get('contained_device_ids', []) if key in device_refs],
                'owner_hardware_node_ref': device_refs.get(device.get('owner_device_id')), 'provenance': stamp})
            continue
        ref = device_refs.get(device['id'])
        node = row_for(ref, 'HardwareNode')
        if node is None:
            raise ValueError(f"Referenzteilnehmer {device['name']} fehlt im kanonischen Vorschlag.")
        if ref in created:
            identity = node.setdefault('identity', {})
            identity.update(reference_design=stamp, source_bindings=source_metadata(device['source_fact_ids']))
            if device.get('owner_device_id'):
                owner = device_refs[device['owner_device_id']]
                previous = identity.get('system_owner_id')
                if previous and previous != owner:
                    raise ValueError('Die Referenzzuordnung darf eine bestehende Eigentümerschaft nicht ersetzen.')
                identity['system_owner_id'] = owner
    document_evidence['context_bindings'] = context_bindings

    # Canonical Function requires real hardware. COMPOSITE is coverage of its
    # atomic children, never one executable function copied onto all hosts.
    function_refs = {}
    function_rows = {row['source_fact_id']: row for row in plan['functions']}
    for function in plan['functions']:
        if function['realization'] != 'ATOMIC':
            continue
        fact_id = function['source_fact_id']
        fact = facts[fact_id]
        refs = []
        for executor in function['executor_device_ids']:
            name = concise_name('Function', f"{fact['name']} [{fact_id[1:11]} {executor[1:7]}]")
            ref = ensure('Function', name, {'hardware_node_id': device_refs[executor], 'domain': spec['domain'],
                'description': fact['source_quote'], 'configuration': {
                    'reviewed_document_function': {**fact, 'fact_id': reference['fact_id_map'][fact_id],
                        'source_sha256': reference['source_sha256'], 'assignment_source': 'REFERENCE_ASSUMPTION'},
                    'reference_design': {**stamp, 'rationale': function['rationale'], 'realization': 'ATOMIC'},
                    'processing_evidence': 'NONE', 'dependency_review': 'REFERENCE_DESIGN'}}, 'hardware_node_id')
            refs.append(ref)
        function_refs[fact_id] = refs

    def realized(fact_id):
        if fact_id not in function_refs:
            function_refs[fact_id] = list(dict.fromkeys(ref for child in function_rows[fact_id]['realized_by_fact_ids'] for ref in realized(child)))
        return function_refs[fact_id]

    for function in plan['functions']:
        key = function['source_fact_id']
        refs = realized(key)
        document_evidence.setdefault('function_bindings', []).append({
            'fact_id': reference['fact_id_map'][key], 'function_refs': refs,
            'realization': function['realization'], 'provenance': stamp})

    # Preserve the exact proposed physical endpoint, bitrate and network. A
    # receive-only port has no fabricated message or default status transmission.
    port_refs = {}
    for port in plan['ports']:
        name = port_names.get(port['id'])
        network = port_networks.get(port['id'])
        if not name:
            raise ValueError('Ein geplanter physischer Empfangs-/Sendeport fehlt im Referenzadapter.')
        contract = _technology_contract(port['technology'])
        ref = ensure('HardwareNetworkInterface', name, {
            'hardware_node_id': device_refs[port['device_id']], 'technology': port['technology'],
            'network_ref': network, 'channel_index': 1,
            **{key: value for key, value in port['parameters'].items() if key in {'bitrate', 'data_bitrate'}},
            'capabilities': {**contract['capabilities'], 'hardware_interface': contract['hardware_interface'],
                'technology_stack': contract['stack'], 'reference_design': {**stamp, 'parameters': deepcopy(port['parameters'])}}}, 'hardware_node_id')
        port_refs[port['id']] = ref
        if ref in created:
            current = created[ref]['data']
            current.update({key: value for key, value in port['parameters'].items() if key in {'bitrate', 'data_bitrate'}})
            current.setdefault('capabilities', {})['reference_design'] = {**stamp, 'parameters': deepcopy(port['parameters'])}
        # Network is the existing workflow parameter scope used by capacity,
        # physical realization and simulation, not a parallel parameter store.
        if network:
            net = next((item['data'] for item in changes if item['object_type'] == 'Network' and item['data']['id'] == network), None)
            if net is not None:
                for key, value in port['parameters'].items():
                    if key in net and net[key] != value:
                        raise ValueError(f'Unvereinbare Referenzparameter im selben physischen Netz: {network}/{key}.')
                    net[key] = deepcopy(value)
                    net.setdefault('parameter_provenance', {})[key] = {**stamp, 'value': deepcopy(value), 'status': 'REVIEWED_ASSUMPTION'}
    # ensure() can append after the initial created map was built.
    created.update({('$' + item['local_ref']): item for item in changes})

    comm_by_id = {row['id']: row for row in plan['communication']}
    for chain in spec['chains']:
        config = chain.get('configuration') or {}
        key = config.get('reference_communication_id')
        if not key:
            continue
        communication = comm_by_id[key]
        source = device_refs[communication['producer_device_id']]
        consumers = [device_refs[key] for key in communication['consumer_device_ids']]
        message = next((item['data'] for item in changes if item['object_type'] == 'Message' and item['data']['name'] == concise_name('Message', chain['message_name'])), None)
        if message is None:
            raise ValueError('Eine geplante Übertragung fehlt im kanonischen Vorschlag.')
        message['hardware_interface_id'] = port_refs[communication['source_port_id']]
        producer = communication.get('producer_fact_id')
        if producer:
            fn = next((ref for ref in realized(producer) if row_for(ref, 'Function')['hardware_node_id'] == source), None)
            if not fn:
                raise ValueError('Die sendende Funktion ist nicht auf dem geplanten Teilnehmer gebunden.')
            logical = ensure('Interface', concise_name('Interface', f"{chain['interface_name']} {producer[1:9]}"), {
                'function_id': fn, 'interface_type': chain['interface_type'],
                'configuration': {'physical_interface_ids': [message['hardware_interface_id']], 'reference_design': stamp}}, 'function_id')
            message['interface_id'] = logical
        role = ('COMMAND' if any(by_device[key]['kind'] == 'ACTUATOR' for key in communication['consumer_device_ids'])
                else 'MEASUREMENT' if by_device[communication['producer_device_id']]['kind'] == 'SENSOR'
                else 'FEEDBACK' if by_device[communication['producer_device_id']]['kind'] == 'ACTUATOR' else 'EXPLICIT')
        transmission = {'mode': communication['transmission_mode']}
        if communication.get('cycle_ms') is not None:
            transmission['period_ms'] = communication['cycle_ms']
        if communication.get('min_interval_ms') is not None:
            transmission['minimum_interval_ms'] = communication['min_interval_ms']
        if communication.get('trigger'):
            transmission['trigger'] = communication['trigger']
        message_config = message.setdefault('configuration', {})
        message_config['reference_design'] = {**stamp, 'communication_id': key}
        message_config['communication_contract'] = {'version': 2, 'scope': communication['scope'], 'role': role,
            'basis': 'Geprüfter NIS-Referenzentwurf; keine Quellenbehauptung', 'producer_ref': source,
            'consumer_refs': consumers, 'transmission': transmission}
        message_config.setdefault('transport_unit', {}).update(producer_ref=source, consumer_refs=consumers,
            timing={'cycle_ms': communication.get('cycle_ms')}, provenance=stamp)
        message_config['receiver_port_refs'] = [port_refs[key] for key in communication['consumer_port_ids']]

    for dependency in plan.get('functional_dependencies', []):
        host = device_refs[dependency['executor_device_id']]
        producer = next(ref for ref in realized(dependency['producer_fact_id']) if row_for(ref, 'Function')['hardware_node_id'] == host)
        consumers = [ref for key in dependency['consumer_fact_ids'] for ref in realized(key) if row_for(ref, 'Function')['hardware_node_id'] == host]
        changes.append({'object_type': 'DataObject', 'local_ref': f'reference-dependency-{len(changes)}', 'data': {
            'name': concise_name('DataObject', dependency['signal_name']), 'producer_function_ref': producer,
            'consumer_function_refs': consumers, 'fields': [{'name': dependency['signal_name'], **deepcopy(dependency['encoding'])}],
            'description': dependency['rationale'], 'provenance': stamp, 'binding': 'LOGICAL_SAME_EXECUTOR',
            'processing_evidence': 'NONE', 'timing_evidence': 'NONE'}})
    document_evidence['reference_design'] = {**stamp, 'coverage': deepcopy(reference['coverage']),
        'decision_evidence': deepcopy(reference['decision_evidence']), 'context_bindings': context_bindings}


