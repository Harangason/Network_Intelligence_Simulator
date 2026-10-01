"""Compose existing Python generators into reviewable engineering changes."""
from __future__ import annotations

from uuid import uuid4
import re
from ..requirement_expansion_modules.engine import expand_requirement
from ..message_packing import SignalCandidate, pack_signals
from ..signal_audit import required_signal_bits
from ..device_classification import DeviceClassificationRegistry
from ..device_communication import complete_new_controller_status
from ..repository import get_object, list_objects
from . import proposal_service as proposals


def expand(arguments: dict) -> dict:
    return expand_requirement(arguments["prompt"], domain=arguments.get("domain"))


def _reviewable_new_ecu_defaults(prompt: str) -> tuple[dict, str, float, list[str]] | None:
    """Use project evidence for an explicitly requested, unnamed acquisition ECU."""
    if not re.search(r"\b(?:neue?|eine)\s+ECU\b", prompt, re.I) or not re.search(
        r"Stellglied|Aktor|actuator", prompt, re.I
    ):
        return None
    nodes = {str(node['id']): node for node in list_objects('HardwareNode', limit=1000)}
    interfaces = list_objects('Interface', limit=1000)
    actuator_ids = {node_id for node_id, node in nodes.items()
                    if node.get('device_type') == 'ActuatorController'}
    technologies = {str(port.get('interface_type')) for port in interfaces
                    if str(port.get('hardware_node_id')) in actuator_ids and port.get('interface_type')}
    if len(technologies) != 1:
        return None
    technology = technologies.pop()
    controller_ids = {node_id for node_id, node in nodes.items()
                      if node.get('device_type') in {'ECU', 'EmbeddedController'}}
    controller_interfaces = {str(port['id']) for port in interfaces
                             if str(port.get('hardware_node_id')) in controller_ids
                             and port.get('interface_type') == technology}
    cycles = {float(message['cycle_ms']) for message in list_objects('Message', limit=1000)
              if str(message.get('interface_id')) in controller_interfaces
              and message.get('cycle_ms') and not (message.get('configuration') or {}).get('generation_role') == 'COMMAND'}
    if len(cycles) != 1:
        return None
    cycle = cycles.pop()
    return ({'name': 'StellgliedAbfrageECU', 'device_type': 'ECU'}, technology, cycle, [
        'Entwurfsname StellgliedAbfrageECU aus dem Auftrag abgeleitet; vor Übernahme prüfen.',
        f'Anschluss {technology} aus den vorhandenen Stellgliedanschlüssen abgeleitet; vor Übernahme prüfen.',
        f'Statuszyklus {cycle:g} ms aus dem vorhandenen Controller auf {technology} abgeleitet; vor Übernahme prüfen. '
        'Der angeforderte 30-Sekunden-Abfragezyklus ist davon unabhängig.'
    ])


def _position_poll_draft(prompt: str, technology: str) -> tuple[list[str], dict | None]:
    """Describe the approved candidate pairs without inventing CANopen object entries."""
    if technology.casefold() != 'canopen' or not re.search(r'\b30\s*(?:Sekunden|s)\b', prompt, re.I):
        return [], None
    nodes = list_objects('HardwareNode', limit=1000)
    sensors = {match.group(1): node['name'] for node in nodes
               if node.get('device_type') == 'SensorController'
               if (match := re.fullmatch(r'Positionssensor\s*(\d+)', str(node.get('name') or ''), re.I))}
    actuators = {match.group(1): node['name'] for node in nodes
                 if node.get('device_type') == 'ActuatorController'
                 if (match := re.fullmatch(r'Servoantrieb\s*(\d+)', str(node.get('name') or ''), re.I))}
    keys = sorted(sensors.keys() & actuators.keys(), key=int)
    if not keys:
        return [], None
    pairs = [{'sensor': sensors[key], 'actuator': actuators[key]} for key in keys]
    notes = [f'Prüfbare Zuordnung: {pair["sensor"]} ↔ {pair["actuator"]}; fachlich bestätigen.' for pair in pairs]
    notes += [
        'Prüfbarer Kommunikationsentwurf: alle 30000 ms CANopen-Anfrage durch die neue ECU; '
        'je zugeordnetem Stellglied eine korrelierte Antwort mit der aktuellen Position. '
        'Anfrage und Antwort sind gemeinsam auf dem CAN-Bus zu dimensionieren.',
        'CANopen-Objektverzeichnis, Nutzdatenkodierung, Antwortzeit und Fehlerverhalten sind nicht bestätigt. '
        'Vor einer ausführbaren Kommunikation und Timing-Freigabe fachlich ergänzen.',
    ]
    return notes, {'source': 'project_position_poll_draft', 'technology': 'CANopen',
                   'interval_ms': 30000, 'mode': 'REQUEST_RESPONSE', 'pairs': pairs,
                   'review_state': 'CANDIDATE', 'object_dictionary': None, 'encoding': None}


def functions(arguments: dict) -> dict:
    expansion = expand(arguments)
    changes = []
    hardware_id = arguments.get("hardware_id")
    new_hardware = arguments.get('new_hardware')
    status_technology = arguments.get('status_technology')
    status_cycle_ms = arguments.get('status_cycle_ms')
    draft_assumptions = []
    draft_evidence = []
    if hardware_id and new_hardware:
        raise ValueError('Vorhandene Hardware oder neue Hardware wählen, nicht beides.')
    if hardware_id:
        get_object("HardwareNode", hardware_id)
    else:
        if not new_hardware or not status_technology or status_cycle_ms is None:
            draft = _reviewable_new_ecu_defaults(arguments['prompt'])
            if draft:
                suggested_hardware, suggested_technology, suggested_cycle, draft_assumptions = draft
                new_hardware = new_hardware or suggested_hardware
                status_technology = status_technology or suggested_technology
                status_cycle_ms = status_cycle_ms if status_cycle_ms is not None else suggested_cycle
                poll_notes, poll_evidence = _position_poll_draft(arguments['prompt'], status_technology)
                draft_assumptions.extend(poll_notes)
                if poll_evidence:
                    draft_evidence.append(poll_evidence)
        if not isinstance(new_hardware, dict) or not new_hardware.get('name') or not new_hardware.get('device_type'):
            raise ValueError('Welcher Controller führt die Funktionen aus? Vorhandene hardware_id wählen oder Name und Gerätetyp für neue Hardware bestätigen.')
        if not status_technology or status_cycle_ms is None:
            raise ValueError('Anschlusstechnologie und Statuszyklus der neuen Hardware ausdrücklich festlegen.')
        hardware = new_hardware
        profile = DeviceClassificationRegistry().resolve_profile(name=hardware["name"], device_type=hardware['device_type']).to_dict()
        changes.append({"object_type": "HardwareNode", "local_ref": "hardware", "data": {
            "name": hardware["name"], "device_type": hardware['device_type'], "device_class": profile["device_class"],
            "description": "Ausdrücklich angeforderte Hardwarezuordnung; vor Übernahme prüfen."}})
        hardware_id = "$hardware"
    requested = arguments.get("count")
    count_match = re.search(r"(\d+)\s*(?!(?:Grad|degrees?)\b)(?:[A-Za-zÄÖÜäöüß_-]+\s+){0,2}(?:Funktion(?:en)?|functions?)\b",arguments["prompt"],re.I)
    if requested is None and count_match:
        requested = int(count_match.group(1))
    if requested is not None and not 1 <= requested <= 100:
        raise ValueError("Funktionsanzahl muss zwischen 1 und 100 liegen.")
    candidates = [dict(item) for item in expansion["functions"]]
    if arguments.get("decompose"):
        candidates = [{"name": sub} for item in candidates for sub in item.get("subfunctions", [])] or candidates
    if requested and requested > len(candidates):
        candidates += [{"name":sub} for item in expansion["functions"] for sub in item.get("subfunctions",[]) if sub not in {c["name"] for c in candidates}]
    if requested and requested > len(candidates):
        raise ValueError(f"Fachlich begründete Funktionen: {len(candidates)}, angefordert: {requested}. Anforderung präzisieren.")
    position_poll = bool(new_hardware and re.search(r'Stellgliedposition|Aktorposition', arguments['prompt'], re.I)
                         and re.search(r'\b30\s*(?:Sekunden|s)\b', arguments['prompt'], re.I))
    if position_poll:
        # The general requirement expander can return GenericFunctionalization
        # for this precise intent. Preserve the typed acquisition goal and its
        # period in the reviewable canonical function instead.
        candidates = [{'name': 'StellgliedPositionAbfrage',
                       'subfunctions': ['Positionsanfrage und korrelierte Antwort über die bestätigte Technologie',
                                        'Abfrageintervall 30000 ms']}]
    for index, function in enumerate(candidates[:requested] if requested else candidates):
        changes.append({"object_type": "Function", "local_ref": f"function-{index}", "data": {
            "name": function["name"], "hardware_node_id": hardware_id, "domain": arguments.get("domain") or "custom",
            "description": ", ".join(function.get("subfunctions") or []),
            **({'configuration': {'acquisition_mode': 'REQUEST_RESPONSE',
                                  'cycle_time_ms': 30000, 'review_state': 'CANDIDATE'}}
               if position_poll else {})}})
    complete_new_controller_status(changes, status_technology=status_technology, status_cycle_ms=status_cycle_ms)
    return proposals.create("FUNCTION_STRUCTURE", changes, arguments["prompt"],
                            assumptions=[*[str(item) for item in expansion["assumptions"]], *draft_assumptions, *([f"Statuszyklus im Entwurf: {status_cycle_ms} ms über {status_technology}; Buszuordnung und Timing vor Routing prüfen."] if new_hardware else [])],
                            evidence=[{"source": "requirement_expansion", "interpretation": expansion["interpretation"]}, *draft_evidence])


def interfaces(arguments: dict, *, physical: bool = False) -> dict:
    count = int(arguments.get("count", 1))
    technology = arguments["technology"]
    parent = arguments["hardware_id" if physical else "function_id"]
    get_object("HardwareNode" if physical else "Function", parent)
    changes = [{"object_type": "HardwareNetworkInterface" if physical else "Interface", "data": {
        "name": f"{arguments.get('name', technology)}_{index+1}",
        **({"hardware_node_id": parent, "technology": technology, "channel_index": index+1}
           if physical else {"function_id": parent, "interface_type": technology})}} for index in range(count)]
    return proposals.create("HARDWARE_INTERFACES" if physical else "FUNCTION_INTERFACES", changes,
                            arguments.get("prompt") or "Schnittstellen für das gewählte Objekt vorschlagen.")


def data_models(arguments: dict, kind: str) -> dict:
    result = expand(arguments)
    key = "status_models" if kind == "StatusModel" else "data_objects"
    return proposals.create(kind.upper(), [{"object_type": kind, "data": item} for item in result[key]], arguments["prompt"],
                            assumptions=[str(item) for item in result["assumptions"]])


def packed(arguments: dict) -> list[dict]:
    candidates = []
    for signal in arguments["signals"]:
        bits = required_signal_bits(signal) or signal.get("length_bits")
        if not bits:
            raise ValueError(f"Bitbedarf für {signal.get('name')} ist nicht bestimmt.")
        candidates.append(SignalCandidate(name=signal["name"], required_bits=int(bits),
            producer_function_ref=str(signal.get("producer_function_ref") or arguments.get("function_id") or "unassigned"),
            sender_hardware_ref=str(signal.get("sender_hardware_ref") or arguments.get("hardware_id") or "unassigned"),
            technology=arguments["technology"], cycle_ms=float(signal.get("cycle_ms", arguments.get("cycle_ms", 10))),
            receiver_set=tuple(sorted(signal.get("receiver_set") or [])), priority=str(signal.get("priority", "NORMAL")), data=signal))
    return [message.to_dict() for message in pack_signals(candidates)]


def messages(arguments: dict) -> dict:
    interface = get_object("Interface", arguments["interface_id"])
    function_name = get_object("Function",str(interface["function_id"]))["name"] if interface.get("function_id") else interface["name"]
    packed_messages = packed({**arguments, "technology": interface["interface_type"], "function_id": function_name})
    changes = []
    for index, message in enumerate(packed_messages):
        ref = f"message-{index}"
        changes.append({"object_type": "Message", "local_ref": ref, "data": {
            "name": message["name"], "interface_id": str(interface["id"]), "cycle_ms": message["cycle_ms"], "dlc": message["dlc"]}})
        for signal in message["signals"]:
            data = signal["data"]
            changes.append({"object_type": "Signal", "data": {
                **{key: value for key, value in data.items() if key in
                   {"name", "display_name", "description", "domain", "data_type", "factor", "offset_value", "unit", "min_value", "max_value", "semantic", "data", "communication", "quality", "configuration"}},
                "name": signal["name"], "message_id": f"${ref}", "start_bit": signal["start_bit"], "length_bits": signal["length_bits"],
                "byte_order": data.get("byte_order", "little_endian")}})
    return proposals.create("MESSAGE_PACKING", changes, arguments.get("prompt") or "Signale nach Funktion, Technologie, Zyklus und Empfängern packen.",
                            evidence=[{"source": "message_packing", "messages": packed_messages}])


def mapping(arguments: dict) -> dict:
    function = get_object("Function", arguments["function_id"])
    get_object("HardwareNode", arguments["hardware_id"])
    return proposals.create("FUNCTION_MAPPING", [{"object_type": "Function", "object_id": str(function["id"]),
        "action": "UPDATE", "data": {"hardware_node_id": arguments["hardware_id"]}}], "Funktion der gewählten Hardware zuordnen.")


def network(arguments: dict) -> dict:
    data = {**(arguments.get("configuration") or {}), "id": arguments.get("network_id") or str(uuid4()), "name": arguments["name"],
            "technology": arguments["technology"]}
    from ..naming import is_ethernet, new_bus_name
    from . import model
    if is_ethernet(data['technology']) and data.get('name_source') != 'user':
        context = data.get('name_context') or arguments['name']
        data.update(name=new_bus_name(data['id'], model.networks(), technology=data['technology'], context=context),
                    name_source='generated', name_context=context)
    return proposals.create("NETWORK", [{"object_type": "Network", "data": data}], arguments.get("prompt") or "Netzwerk vorschlagen.")


def scenario(arguments: dict) -> dict:
    data = {**arguments["scenario"], 'source': 'ai_generated',
            'faults': [{**fault, 'source': 'ai_generated', 'approved': False}
                       for fault in arguments['scenario'].get('faults') or []]}
    return proposals.create("SIMULATION_SCENARIO", [{"object_type": "SimulationScenario", "data": data}],
                            arguments.get("prompt") or "Simulations- oder Fehlerszenario zur Prüfung vorschlagen.")


def camera_architecture(arguments: dict) -> dict:
    coverage, profile, outputs = arguments['coverage'], arguments['profile'], arguments['outputs']
    if coverage not in {'front', 'front_rear', 'surround'} or profile not in {'four_wide', 'directional', 'two_fisheye'}:
        raise ValueError('Abdeckung und Sensorprofil müssen ausdrücklich festgelegt sein.')
    if not outputs or not set(outputs) <= {'objects', 'free_space', 'status', 'raw_image'}:
        raise ValueError('Ungültige Kamera-Ausgaben.')
    if (coverage == 'surround') != (profile in {'four_wide', 'two_fisheye'}):
        raise ValueError('Sensorprofil passt nicht zur Abdeckung.')
    directions = ['Front', 'Heck', 'Links', 'Rechts'] if profile == 'four_wide' else ['Front', 'Heck'] if coverage != 'front' else ['Front']
    changes = []
    for index, direction in enumerate([*directions, 'Vision Controller']):
        ref = f'camera-{index}' if index < len(directions) else 'vision-controller'
        changes.extend([
            {'object_type':'HardwareNode', 'local_ref':ref, 'data':{'name':f'Kamera {direction}' if index < len(directions) else direction,
                'device_type':'ECU', 'device_class':3, 'description':'Explizit gewählte Kamera-Planungsarchitektur.'}},
            {'object_type':'Function', 'local_ref':f'{ref}-function', 'data':{'name':f'Bilderfassung {direction}' if index < len(directions) else 'Visuelle Umfeldinterpretation', 'hardware_node_id':f'${ref}', 'domain':'automotive'}},
            {'object_type':'Interface', 'local_ref':f'{ref}-logical', 'data':{'name':f'{direction} Daten', 'function_id':f'${ref}-function', 'interface_type':'Ethernet'}},
            {'object_type':'HardwareNetworkInterface', 'local_ref':f'{ref}-port', 'data':{'name':f'{direction} Ethernet', 'hardware_node_id':f'${ref}', 'technology':'Ethernet', 'channel_index':1}},
        ])
    labels = {'objects':'Objektliste', 'free_space':'Freiraum', 'status':'Status und Diagnose', 'raw_image':'Rohbilder'}
    for output in outputs:
        changes.append({'object_type':'StatusModel' if output == 'status' else 'DataObject', 'data':{
            'name':labels[output], 'producer_function_ref':'$vision-controller-function',
            'description':'Strukturvorschlag; Dimensionierung und konkrete Datentypen vor Kommunikationsgenerierung prüfen.',
            'states':['AVAILABLE','DEGRADED','UNAVAILABLE'] if output == 'status' else [],
            'fields': [{'name':'timestamp', 'data_type':'uint64', 'unit':'us'},
                {'name': {'objects':'objects','free_space':'regions','raw_image':'pixels','status':'state'}[output],
                 'data_type':'uint8' if output == 'status' else 'array', 'dimension_status':'UNSPECIFIED'}]}})
    complete_new_controller_status(changes, status_cycle_ms=100)
    return proposals.create('CAMERA_ARCHITECTURE', changes, arguments.get('prompt') or 'Kameraarchitektur',
        assumptions=['Neue Controller senden den einheitlichen Betriebsstatus vorläufig alle 100 ms über Ethernet; Timing vor Routing prüfen.', f'Explizite Auswahl: {coverage}, Sensorprofil {profile}, Ausgaben {", ".join(outputs)}.',
            '100° horizontale Sicht bei vier Weitwinkelkameras bzw. 190° bei zwei Fisheye-Kameras sind Planungsannahmen; Montage und Überlappung validieren.',
            'Ethernet-Datenpfade sind strukturell vorbereitet. Auflösung, Bildrate, Kodierung, Netzwerktopologie und Timing müssen vor Routing und Simulation dimensioniert werden.'],
        evidence=[{'source':'structured_camera_decisions','coverage':coverage,'profile':profile,'outputs':outputs}])
