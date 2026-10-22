from pathlib import Path
import ast

root = Path(__file__).parent / 'staged'
path = root / 'backend/nis/agent/tools/wizard_generation.py'
text = path.read_text(encoding='utf-8')
start = text.index('def _materialize_reference_bindings(')
end = text.index('\ndef generate(arguments:', start)
block = text[start:end]
point = block.index('    # Preserve the exact proposed physical endpoint')
block = block[:point] + '''    # Device acquisition/execution remains a marked design function. It is
    # distinct from source responsibilities and is never a measured algorithm.
    for device_id, ref in device_refs.items():
        node = row_for(ref, 'HardwareNode')
        profile = DeviceClassificationRegistry().resolve_profile(name=node['name'], device_type=node['device_type'], device_class=node.get('device_class'))
        if profile.requires_function_model and not any(item['object_type'] == 'Function' and item['data'].get('hardware_node_id') == ref for item in changes):
            ensure('Function', concise_name('Function', node['name'] + ' Gerätefunktion'), {
                'hardware_node_id': ref, 'domain': spec['domain'],
                'description': by_device[device_id].get('purpose') or by_device[device_id]['rationale'],
                'configuration': {'reference_design': stamp, 'processing_evidence': 'NONE', 'dependency_review': 'REFERENCE_DESIGN'}}, 'hardware_node_id')

    def assumptions(port):
        technology = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(port['technology'])
        roles = DEFAULT_TECHNOLOGY_REGISTRY.parameter_roles(technology)
        aliases = DEFAULT_TECHNOLOGY_REGISTRY.profile(technology, fields=('parameter_aliases',)).get('parameter_aliases') or {}
        values = {aliases.get(key, key): value for key, value in port['parameters'].items() if roles.get(aliases.get(key, key)) == 'CONFIGURATION'}
        return {technology: {'values': values, 'provenance': {key: {
            'source': 'NIS_SIMULATION_ASSUMPTION', 'status': 'ASSUMED', 'technology': technology,
            'hardware_evidence': False, 'value': deepcopy(value), 'reference_origin': stamp,
            'rationale': port['rationale']} for key, value in values.items()}}}

''' + block[point:]
block = block.replace("            **{key: value for key, value in port['parameters'].items() if key in {'bitrate', 'data_bitrate'}},\n", '')
block = block.replace("'technology_stack': contract['stack'], 'reference_design':", "'technology_stack': contract['stack'], 'simulation_parameter_assumptions': assumptions(port), 'reference_design':", 1)
block = block.replace("            current.update({key: value for key, value in port['parameters'].items() if key in {'bitrate', 'data_bitrate'}})\n", "            current.setdefault('capabilities', {})['simulation_parameter_assumptions'] = assumptions(port)\n")
begin = block.index('                for key, value in port[\'parameters\'].items():')
finish = block.index('    # ensure() can append', begin)
block = block[:begin] + '''                group = net.setdefault('simulation_parameter_assumptions', {})
                for technology, incoming in assumptions(port).items():
                    saved = group.setdefault(technology, {'values': {}, 'provenance': {}})
                    for key, value in incoming['values'].items():
                        if key in saved['values'] and saved['values'][key] != value:
                            raise ValueError(f'Unvereinbare Referenzannahmen im selben physischen Netz: {network}/{key}.')
                        saved['values'][key] = deepcopy(value)
                        saved['provenance'][key] = deepcopy(incoming['provenance'][key])
                net.setdefault('reference_parameter_decisions', []).append({**stamp, 'port_id': port['id'], 'parameters': deepcopy(port['parameters'])})
''' + block[finish:]
begin = block.index("        message = next((item['data']")
block = block[:begin] + '''        technology = _technology_contract(chain['interface_type'])['technology_id']
        from backend.nis.communication.catalog import DIRECT_IO_TECHNOLOGIES
        signal = next((item['data'] for item in changes if item['object_type'] == 'Signal' and item['data']['name'] == concise_name('Signal', chain['signal_name'])), None)
        if signal is None:
            raise ValueError('Eine geplante Nutzdatenkodierung fehlt im kanonischen Vorschlag.')
        role = ('COMMAND' if any(by_device[key]['kind'] == 'ACTUATOR' for key in communication['consumer_device_ids'])
                else 'MEASUREMENT' if by_device[communication['producer_device_id']]['kind'] == 'SENSOR'
                else 'FEEDBACK' if by_device[communication['producer_device_id']]['kind'] == 'ACTUATOR' else 'FUNCTION_OUTPUT')
        signal.setdefault('configuration', {}).update(reference_design={**stamp, 'communication_id': key}, generation_role=role)
        if technology in DIRECT_IO_TECHNOLOGIES:
            if len(consumers) != 1:
                raise ValueError('Direktes I/O benötigt eine explizite einzelne Zielbindung je Leitung.')
            signal['configuration']['direct_signal_binding'] = {
                'source_hardware_node_ref': source, 'destination_hardware_node_ref': consumers[0],
                'physical_port_ref': port_refs[communication['source_port_id']],
                'signal_type': technology.upper(), 'electrical_profile': {},
                'update_rate_hz': 1000 / communication['cycle_ms'] if communication.get('cycle_ms') else None,
                'timing_profile': {}, 'validation_status': 'REFERENCE_DESIGN', 'provenance': stamp}
            continue
''' + block[begin:]
block = block.replace("        if communication.get('trigger'):\n            transmission['trigger'] = communication['trigger']", "        for field in ('trigger', 'trigger_description', 'release_times_ms', 'request_source', 'response_processing_ms', 'request_times_ms'):\n            if communication.get(field) is not None:\n                transmission[field] = deepcopy(communication[field])")
# Request IDs are resolved after every canonical message exists. Neither an
# external request nor a bus request is invented by the serializer.
point = block.index("    for dependency in plan.get('functional_dependencies', []):")
block = block[:point] + '''    for communication in plan['communication']:
        request_id = communication.get('request_communication_id')
        if not request_id:
            continue
        message_refs = {item['data'].get('configuration', {}).get('reference_design', {}).get('communication_id'): '$' + item['local_ref']
                        for item in changes if item['object_type'] == 'Message'}
        response_ref = message_refs.get(communication['id'])
        request_ref = message_refs.get(request_id)
        if not response_ref or not request_ref:
            raise ValueError('Die geplante Bus-Anfrage/Antwort ist nicht vollständig auf kanonische Nachrichten gebunden.')
        row_for(response_ref, 'Message')['configuration']['communication_contract']['transmission']['request_message_ref'] = request_ref

''' + block[point:]
text = text[:start] + block + text[end:]
ast.parse(text)
path.write_text(text, encoding='utf-8', newline='\n')

path = root / 'backend/nis/agent/orchestration/local_reasoner.py'
text = path.read_text(encoding='utf-8').replace("if item['kind'] in {'CONTROLLER', 'GATEWAY', 'SENSOR'}", "if item['kind'] in {'CONTROLLER', 'GATEWAY', 'SENSOR', 'ACTUATOR'}", 1)
text = text.replace("            'Stellbefehle brauchen passende physikalische Bedeutung", "            'Intelligente Teilnehmer benötigen bewusst geplante Statusausgänge und deren Empfänger; Aktoren eine getrennte Istwert-/Ausführungsrückmeldung. Keine stillen Begleitsignale ergänzen. '\n            'Stellbefehle brauchen passende physikalische Bedeutung", 1)
ast.parse(text)
path.write_text(text, encoding='utf-8', newline='\n')
