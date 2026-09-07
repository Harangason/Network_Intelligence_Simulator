"""Register thin capability adapters; engineering calculations stay in Python."""
from __future__ import annotations

from collections import defaultdict
from typing import Any
from backend.agent_core.api.tool_contract import Permission as P, ToolResult, ToolStatus
from ..repository import get_object, ENTITY_SPECS, NotFoundError
from ..project_context import current_project_id
from ..device_classification import DeviceClassificationRegistry
from ..semantic_intelligence import SemanticClassificationService
from ..signal_audit import required_signal_bits, inspect_signal, inspect_message_signals
from ..capacity.calculators import estimate_frame, utilization_percent
from ..capacity.service import CapacityTimingService, PreflightService
from ..message_packing import valid_payload_bytes
from ..routing.generation import RoutingGenerationService
from ..routing.validation import RoutingValidator
from ..routing.repository import get_route
from ..workflow.service import WorkflowStatusService
from ..workloads import EngineeringWorkloadOrchestrator
from ..intelligence import IntelligenceService
from ..addressing import AddressResolutionService, LogicalNodeAddressAllocator
from backend.intelligence.ml import MLInferenceService
from . import model as access, generation, proposal_service as proposals, analysis, audit, wizard_generation
from .catalog import TOOLS, register, ID, TEXT, OBJECT, OPTIONAL_OBJECT, ITEMS, COUNT, LIMIT, TECHNOLOGY


def _validation(data: dict) -> ToolResult:
    findings = data.get("findings") or data.get("errors") or data.get("checks") or []
    valid = data.get("valid")
    if valid is None:
        valid = data.get("status") not in {"ERROR", "OPEN", "FAILED", "BLOCKED"}
    return ToolResult(success=bool(valid), status=ToolStatus.SUCCESS if valid else ToolStatus.VALIDATION_FAILED,
                      data=access.json_safe(data), findings=access.json_safe(findings))


def _device(a):
    data = a.get("device") or get_object("HardwareNode", a["hardware_id"])
    return DeviceClassificationRegistry().resolve_profile(**{k:v for k,v in data.items() if k in
        {"name", "device_type", "device_class", "device_typing", "data_complexity"}}).to_dict()


def _signal(a):
    return a.get("signal") or get_object("Signal", a["signal_id"])


def _ask_question(a):
    from backend.agent_core.api.agent_response import AgentResponse, InteractiveQuestion
    from uuid import uuid4
    options = [{**{key:value for key,value in option.items() if key != 'value'},
        'id':option.get('id') or option.get('value')} for option in a['options']]
    question = InteractiveQuestion(id=str(uuid4()), question=a['question'], description=a.get('question_description', ''),
        selection_mode='MULTI' if a.get('multiple') else 'SINGLE', options=options,
        recommended_options=a.get('recommended_options') or [], required=a.get('required', True),
        engineering_impact=a.get('engineering_impact', 'REQUIRED'))
    response = AgentResponse(type='MULTI_SELECT' if a.get('multiple') else 'SINGLE_SELECT', text=a['question'], question=question,
        metadata={'decision_key':a['question_id']})
    return {'agent_response':response.model_dump(mode='json', exclude_none=True)}


def _message_validation(a):
    reports = inspect_message_signals(a["signals"],a["message"])
    findings = [check for report in reports for check in report["checks"]]
    return _validation({"valid":not any(f["severity"] in {"ERROR","OPEN"} for f in findings),"findings":findings,"signals":reports})


def _capacity(a):
    return CapacityTimingService(current_project_id()).calculate(a.get("overrides"), persist=False)


def _network(a):
    networks = access.networks()
    item = next((n for n in networks if str(n.get("id")) == a["network_id"]), None)
    if item is None:
        raise NotFoundError("Netzwerk im aktiven Projekt nicht gefunden.")
    return item


def _frame(a):
    technology, size = a["technology"], a["payload_bytes"]
    payload = valid_payload_bytes(technology, size)
    if payload is None:
        raise ValueError(f"Nutzlast von {size} Byte überschreitet die Grenze für {technology}.")
    return estimate_frame(technology, payload, a.get("parameters") or {}).to_dict()


def _network_capacity(a):
    network = _network(a)
    result = _capacity(a)
    metric = next((item for item in result["results"]["networks"] if item["network_id"]==a["network_id"]),None)
    if metric is None:
        metric = {"network_id":a["network_id"],"protocol":network["technology"],"average_load_percent":0,
                  "capacity_margin_percent":100,"target_margin_percent":60,"route_count":0,"status":"PASS"}
    return {**metric,"findings":[item for item in result["findings"] if a["network_id"] in str(item)],"network":network}


def _available(a):
    result = _capacity(a)
    metrics = {item["network_id"]:item for item in result["results"]["networks"]}
    candidates = []
    for network in access.networks():
        if network["id"]==a.get("exclude_network_id"):
            continue
        if a.get("technology") and network.get("technology") != a["technology"]:
            continue
        metric = metrics.get(network["id"],{"target_margin_percent":60,"average_load_percent":0})
        if metric["target_margin_percent"] >= a.get("required_load_percent",0):
            candidates.append({"network":network,"metrics":metric})
    return {"candidates":sorted(candidates,key=lambda item:item["metrics"]["average_load_percent"]),"required_load_percent":a.get("required_load_percent",0)}


def _interface_load(a):
    interface = get_object("HardwareNetworkInterface",a["interface_id"])
    messages = [item for item in access.objects("Message") if str(item.get("hardware_interface_id"))==a["interface_id"]]
    load = sum(_load({"technology":interface["technology"],"payload_bytes":message.get("dlc") or 0,
                "cycle_ms":message.get("cycle_ms") or 10,"parameters":{"bitrate":interface.get("bitrate"),"data_bitrate":interface.get("data_bitrate")}})["load_percent"] for message in messages)
    limit = float(interface.get("target_load_limit") or 60)
    return {"interface_id":a["interface_id"],"load_percent":load,"message_count":len(messages),"limit_percent":limit,"valid":load<=limit}


def _load(a):
    frame = _frame(a)
    load = utilization_percent(frame["transmission_time_s"], a["cycle_ms"], a.get("multiplicity", 1))
    return {**frame, "load_percent": load, "valid": load <= 100}


def _identifier(a):
    interface = get_object("Interface", a["interface_id"])
    used = set()
    for message in access.objects("Message"):
        if str(message.get("interface_id")) == str(interface["id"]) and message.get("message_id_hex"):
            used.add(int(str(message["message_id_hex"]), 16))
    maximum = 0x1FFFFFFF if a.get("extended") else 0x7FF
    candidate = next((value for value in range(a.get("start", 0x100), maximum+1) if value not in used), None)
    if candidate is None:
        return ToolResult(success=False, status=ToolStatus.CAPACITY_EXCEEDED, findings=[{"message": "Kein freier Identifier."}])
    return {"message_id_hex": hex(candidate), "reserved": False, "requires_validation_at_apply": True}


def _route_proposal(a):
    data = a.get("route")
    if data:
        routes = [data]
    else:
        routes = [RoutingGenerationService().generate_route(source_node_id=a["source_node_id"],
                    destination_node_id=target, message_id=a.get("message_id")) for target in a["destination_node_ids"]]
    return proposals.create("ROUTING", [{"object_type": "RoutingEntry", "data": route} for route in routes],
                            a.get("prompt") or "Technisch geeignete Routen vorschlagen.")


def _rank(a):
    validated = []
    for route in a["routes"]:
        result = RoutingValidator().validate(route, exclude_route_id=route.get("id"))
        if result["valid"]:
            validated.append({**route, "validation": result, "validation_status": "VALID"})
    result = MLInferenceService().rank_routes(validated)
    return {**result, "rejected_count": len(a["routes"])-len(validated),
            "explanation_context": MLInferenceService().explain_for_qwen(result)}


def _update(a):
    return proposals.create("OBJECT_UPDATE", [{"object_type": a["object_type"], "object_id": a["object_id"],
        "action": "UPDATE", "data": a["changes"]}], a["rationale"])


def _delete(a):
    impact = proposals.impact(a["object_type"], a["object_id"])
    return proposals.create("OBJECT_DELETE", [{"object_type": a["object_type"], "object_id": a["object_id"],
        "action": "DELETE", "impact_analysis": impact}], a["rationale"], evidence=[impact])


def _workloads():
    return EngineeringWorkloadOrchestrator(current_project_id())


def _workload_review(a):
    service = _workloads()
    workload = service.get_workload(a["workload_id"])
    if workload["status"] != "READY_FOR_REVIEW":
        return ToolResult(success=False, status=ToolStatus.BLOCKED, data=service.progress(a["workload_id"]),
                          findings=[{"message": "Workload ist noch nicht vollständig validiert."}])
    pending = [item for item in service.list_workload_objects(a["workload_id"]) if not item.get("canonical_id")]
    from .. import proposals as store
    ids = sorted({str(item["proposal_id"]) for item in pending if item.get("proposal_id")})
    for identifier in ids:
        existing = store.get_proposal(identifier)
        if existing.get("engineering_contract"):
            return {"workload": service.progress(a["workload_id"]), "proposals": [proposals.get(identifier)]}
    if not pending:
        return {"workload": service.progress(a["workload_id"]), "proposals": []}
    proposal = proposals.create("WORKLOAD_RESULT", [{"object_type":item["definition"].get("object_type") or workload["target_object"],
        "data":{key:value for key,value in item["definition"].items() if key not in
            {"object_type","resource","canonical_id","approval_state","review_state","source","created_by"}}} for item in pending],
        workload["prompt"],workload_id=a["workload_id"],evidence=[{"workload_id":a["workload_id"],"requested":workload["requested_total"],"valid":workload["valid_count"]}])
    for index,item in enumerate(pending):
        service.attach_object_to_proposal(item,proposal,index)
    for identifier in ids:
        store._update_proposal_row(identifier,status="SUPERSEDED",actor="engineering-review-consolidation")
    return {"workload":service.progress(a["workload_id"]),"proposals":[proposals.validate(proposal["proposal_id"])]}


def _simulation(a, action):
    from . import simulation_gateway
    workflow = WorkflowStatusService(current_project_id())
    if action == "snapshot":
        from ..simulation import prepare_workflow_simulation_config
        return workflow.create_simulation_snapshot(prepare_workflow_simulation_config(a.get("configuration") or {}, current_project_id()))
    if action == "start":
        from .runtime import PostCommitAction
        return PostCommitAction(lambda:simulation_gateway.start(a["snapshot_id"]),lambda:None)
    item = simulation_gateway.stop(a["job_id"]) if action == "stop" else simulation_gateway.job(a["job_id"])
    if item is None:
        raise NotFoundError("Simulation im aktiven Projekt nicht gefunden.")
    return item.get("result") or {"status": item["status"]} if action == "results" else item


def register_tools():
    if TOOLS:
        return
    register("inspect_project", "Aktiven Workflow und Projektstand lesen.", P.READ_MODEL, lambda a: WorkflowStatusService(current_project_id()).get())
    register("inspect_object", "Kanonisches Objekt im aktiven Projekt lesen.", P.READ_MODEL, lambda a: get_object(a["object_type"], a["object_id"]), object_type=TEXT, object_id=ID)
    for name, kind in {"inspect_function":"Function", "inspect_hardware":"HardwareNode", "inspect_function_interface":"Interface", "inspect_hardware_interface":"HardwareNetworkInterface", "inspect_signal":"Signal", "inspect_message":"Message"}.items():
        register(name, f"{kind} im aktiven Projekt lesen.", P.READ_MODEL, lambda a, k=kind: get_object(k,a["object_id"]), object_id=ID)
    register("inspect_network", "Kanonisches Netzwerk lesen.", P.READ_MODEL, _network, network_id=ID)
    register("inspect_route", "Kanonische Route lesen.", P.READ_MODEL, lambda a: get_route(a["route_id"]), route_id=ID)
    register("inspect_findings", "Projektfindings aus vorhandenen Analysediensten lesen.", P.READ_MODEL, lambda a: IntelligenceService(current_project_id()).assess(persist=False))
    register("get_logical_node_address", "Logische Diagnoseadresse eines HardwareNode lesen.", P.READ_MODEL,
             lambda a: AddressResolutionService(namespace=a["namespace"]).resolve_address(a["hardware_id"]),
             hardware_id=ID, namespace=(str, "PROJECT"))
    register("resolve_logical_node_address", "Diagnoseadresse in HardwareNode, Interfaces und Netze auflösen.", P.READ_MODEL,
             lambda a: AddressResolutionService(namespace=a["namespace"]).resolve(a["address"]),
             address=(str | int, ...), namespace=(str, "PROJECT"))
    register("find_free_logical_node_address", "Nächste freie Diagnoseadresse ausschließlich im Python-Allocator ermitteln.", P.READ_MODEL,
             lambda a: LogicalNodeAddressAllocator(namespace=a["namespace"]).find_next_free_address().to_dict(),
             namespace=(str, "PROJECT"))
    register("validate_logical_node_address", "Diagnoseadresse gegen Projektpolicy, Reservierungen und Eindeutigkeit prüfen.", P.VALIDATE,
             lambda a: _validation(LogicalNodeAddressAllocator(namespace=a["namespace"]).validate_address(a["address"], node_id=a.get("hardware_id"))),
             address=(str | int, ...), hardware_id=(str | None, None), namespace=(str, "PROJECT"))
    register("allocate_logical_node_address", "Freie oder explizite Diagnoseadresse serverseitig atomar zuweisen.", P.APPLY_APPROVED_PROPOSAL,
             lambda a: LogicalNodeAddressAllocator(namespace=a["namespace"]).assign_address(
                 a["hardware_id"], a.get("address"), assignment_mode=a["assignment_mode"], actor=a.get("_actor")
             ), hardware_id=ID, address=(str | int | None, None), assignment_mode=(str, "AUTO"), namespace=(str, "PROJECT"))
    register("resolve_route_by_address", "Kanonische Routen zwischen zwei logischen Diagnoseadressen auflösen.", P.READ_MODEL,
             lambda a: {"items": AddressResolutionService(namespace=a["namespace"]).resolve_routes(a["source_address"], a["destination_address"])},
             source_address=(str | int, ...), destination_address=(str | int, ...), namespace=(str, "PROJECT"))
    register("search_model", "Objekte über Typen hinweg nach Namen suchen.", P.READ_MODEL, lambda a: {"items": [
        {**item,"object_type":kind} for kind in ([a["object_type"]] if a.get("object_type") else ENTITY_SPECS)
        for item in access.objects(kind) if a["query"].casefold() in str(item.get("name", "")).casefold()][:a["limit"]]}, query=(str,Field(default="",max_length=2000)), object_type=(str|None,None), limit=LIMIT)
    register("expand_requirement", "Anforderung fachlich expandieren; Annahmen und offene Entscheidungen sichtbar halten.", P.READ_MODEL, generation.expand, prompt=TEXT, domain=(str,"automotive"))
    for name in ["generate_functions", "generate_function_structure", "decompose_function"]:
        register(name, "Funktionen aus der Anforderung als gemeinsamen Proposal erzeugen.", P.GENERATE_PROPOSAL,
                 lambda a,n=name: generation.functions({**a,"decompose":n=="decompose_function"}), prompt=TEXT, hardware_id=(str|None,None), count=(int|None,Field(default=None,ge=1,le=100)), domain=(str,"automotive"))
    register("generate_function_interfaces", "Logische Interfaces einer Funktion vorschlagen.", P.GENERATE_PROPOSAL, generation.interfaces, function_id=ID, count=COUNT, technology=TECHNOLOGY, name=(str,"Interface"))
    for name in ["generate_hardware_interfaces", "create_hardware_interface_proposal"]:
        register(name, "Physische Hardware-Schnittstellen vorschlagen.", P.GENERATE_PROPOSAL, lambda a:generation.interfaces(a,physical=True), hardware_id=ID, count=COUNT, technology=TECHNOLOGY, name=(str,"Port"))
    for name,kind in [("generate_status_models","StatusModel"),("generate_data_objects","DataObject")]:
        register(name, "Fachliches Modell aus der Anforderung vorschlagen.", P.GENERATE_PROPOSAL, lambda a,k=kind:generation.data_models(a,k), prompt=TEXT, domain=(str,"automotive"))
    for name in ["classify_device", "get_device_class_profile", "get_device_capabilities", "inspect_hardware_capabilities"]:
        register(name, "Geräteklasse und Fähigkeiten mit dem Python-Register bestimmen.", P.READ_MODEL, _device, device=(dict[str,Any]|None,None), hardware_id=(str|None,None))
    register("generate_device_capabilities", "Bestimmte Gerätefähigkeiten zur Freigabe vorschlagen.", P.GENERATE_PROPOSAL,
             lambda a:_update({"object_type":"HardwareNode","object_id":a["hardware_id"],"changes":{"hardware_information":{**(get_object("HardwareNode",a["hardware_id"]).get("hardware_information") or {}),"capability_profile":_device(a)}},"rationale":"Gerätefähigkeiten aus dem Klassenregister übernehmen."}), hardware_id=ID)
    register("validate_device_classification", "Klasse, Typisierung und Datenkomplexität prüfen.", P.VALIDATE, lambda a:_validation(dict(zip(("valid","message"),DeviceClassificationRegistry().validate_combination(**a["classification"])))), classification=OBJECT)
    for name in ["classify_signal_semantics", "classify_semantics"]:
        register(name, "Semantik anhand der Ontologie und Evidenz klassifizieren.", P.READ_MODEL, lambda a:SemanticClassificationService().classify(a["object"]), object=OBJECT)
    register("calculate_signal_bit_length", "Bitbedarf aus der Signaldefinition berechnen.", P.READ_MODEL, lambda a:{"required_bits":required_signal_bits(a["signal"])}, signal=OBJECT)
    register("resolve_signal_encoding", "Encoding und darstellbaren Wertebereich prüfen.", P.READ_MODEL, lambda a:inspect_signal(a["signal"],a.get("message")), signal=OBJECT, message=OPTIONAL_OBJECT)
    register("resolve_signal_emulator", "Physikalisches oder Statusmodell über den bestehenden ML-Dienst auswählen.", P.READ_MODEL, lambda a:MLInferenceService().select_physical_model(a["signal"]), signal=OBJECT)
    register("validate_signal", "Signal einschließlich Nutzlastgrenze prüfen.", P.VALIDATE, lambda a:_validation(inspect_signal(a["signal"],a.get("message"))), signal=OBJECT, message=OPTIONAL_OBJECT)
    register("find_similar_signals", "Signale mit gleicher Einheit oder ähnlichem Namen finden.", P.READ_MODEL, lambda a:{"items":[s for s in access.objects("Signal") if a["query"].casefold() in s["name"].casefold() or (a.get("unit") and s.get("unit")==a["unit"])][:a["limit"]]}, query=TEXT, unit=(str|None,None), limit=LIMIT)
    register("map_function_to_hardware", "Hardwarezuordnung einer Funktion vorschlagen.", P.GENERATE_PROPOSAL, generation.mapping, function_id=ID, hardware_id=ID)
    register("validate_function_mapping", "Existenz und Zuordnung der Funktion prüfen.", P.VALIDATE, lambda a:_validation({"valid":str(get_object("Function",a["function_id"])["hardware_node_id"])==a["hardware_id"],"hardware":get_object("HardwareNode",a["hardware_id"])}), function_id=ID, hardware_id=ID)
    register("get_function_interfaces", "Alle logischen Interfaces der Funktion lesen.", P.READ_MODEL, lambda a:{"items":[i for i in access.objects("Interface") if str(i.get("function_id"))==a["function_id"]]}, function_id=ID)
    packing_fields=dict(signals=ITEMS,technology=TECHNOLOGY,function_id=(str|None,None),hardware_id=(str|None,None),cycle_ms=(float,10.0))
    for name in ["group_signals_for_messages","pack_message","pack_function_messages"]:
        register(name, "Signale nach Funktion, Zyklus und Empfängern gruppieren und Nutzlastgrenzen einhalten.", P.READ_MODEL, generation.packed, **packing_fields)
    register("generate_messages", "Gepackte Nachrichten und Signale als Proposal erzeugen.", P.GENERATE_PROPOSAL, generation.messages, interface_id=ID,signals=ITEMS,prompt=(str,"Signale packen."))
    register("calculate_message_payload", "Nutzlastgröße aus Signalbelegung berechnen.", P.READ_MODEL, lambda a:{"packed_messages":generation.packed(a)}, **packing_fields)
    register("allocate_message_identifier", "Freien Identifier ermitteln; Reservierung erst bei Apply.", P.READ_MODEL, _identifier, interface_id=ID,extended=(bool,False),start=(int,256))
    register("validate_message", "Signalüberlappung und Payload prüfen.", P.VALIDATE, _message_validation,message=OBJECT,signals=ITEMS)
    frame_fields=dict(technology=TECHNOLOGY,payload_bytes=(int,Field(ge=0,le=65535)),parameters=OPTIONAL_OBJECT)
    register("calculate_message_size", "Technologiespezifische Framegröße und Sendezeit berechnen.", P.READ_MODEL,_frame,**frame_fields)
    register("calculate_bus_load", "Technologiespezifische Buslast berechnen.", P.READ_MODEL,_load,**frame_fields,cycle_ms=(float,Field(gt=0)),multiplicity=(int,Field(default=1,ge=1,le=100000)))
    register("calculate_capacity","Kapazität und Timing berechnen; kanonische Eingaben als aktuellen Prüfsnapshot speichern.",P.VALIDATE,lambda a:CapacityTimingService(current_project_id()).calculate(a.get("overrides"),persist=not bool(a.get("overrides"))),overrides=OPTIONAL_OBJECT)
    register("calculate_network_load","Last des gewählten Netzwerks berechnen.",P.READ_MODEL,_network_capacity,network_id=ID,overrides=OPTIONAL_OBJECT)
    register("validate_network","Kapazität des gewählten Netzwerks validieren.",P.VALIDATE,lambda a:_validation((lambda metric:{**metric,"valid":metric["status"] not in {"FAIL","OVERLOAD","CRITICAL"}})(_network_capacity(a))),network_id=ID,overrides=OPTIONAL_OBJECT)
    register("calculate_interface_load","Last aus den tatsächlich zugeordneten Nachrichten berechnen.",P.READ_MODEL,_interface_load,interface_id=ID)
    register("validate_interface_capacity","Last der physischen Schnittstelle gegen ihr Ziel prüfen.",P.VALIDATE,lambda a:_validation(_interface_load(a)),interface_id=ID)
    for name in ["find_available_capacity","find_alternative_network"]:
        register(name,"Technologisch passende Netze mit ausreichender Reserve suchen.",P.READ_MODEL,_available,technology=(str|None,None),exclude_network_id=(str|None,None),required_load_percent=(float,Field(default=0,ge=0,le=100)))
    register("create_network_proposal", "Neues Netzwerk im Topologiemodell vorschlagen.", P.GENERATE_PROPOSAL,generation.network,name=TEXT,network_id=(str|None,None),technology=TECHNOLOGY,configuration=OPTIONAL_OBJECT)
    register("assign_network_to_interface", "Physische Schnittstelle einem vorhandenen Netzwerk zuordnen.", P.GENERATE_PROPOSAL,
             lambda a:_update({"object_type":"HardwareNetworkInterface","object_id":a["interface_id"],"changes":{"network_ref":_network(a)["id"]},"rationale":"Netzwerkzuordnung vorschlagen."}),interface_id=ID,network_id=ID)
    register("allocate_message_to_hardware_interface", "Nachricht einem physischen Interface zuordnen.", P.GENERATE_PROPOSAL,
             lambda a:_update({"object_type":"Message","object_id":a["message_id"],"changes":{"hardware_interface_id":str(get_object("HardwareNetworkInterface",a["interface_id"])["id"])},"rationale":"Physisches Interface für Nachricht vorschlagen."}),message_id=ID,interface_id=ID)
    register("find_route_candidates", "Graphbasierte Routen zwischen zwei Hardwareknoten suchen.", P.READ_MODEL, lambda a:RoutingGenerationService().find_candidate_paths(a["source_node_id"],a["destination_node_id"],limit=a["limit"]),source_node_id=ID,destination_node_id=ID,limit=LIMIT)
    register("validate_route", "Route durch Python-Regeln validieren.", P.VALIDATE,lambda a:_validation(RoutingValidator().validate(a["route"],exclude_route_id=a["route"].get("id"))),route=OBJECT)
    register("calculate_route_metrics", "Routing-Metriken mit dem bestehenden Validator berechnen.", P.READ_MODEL,lambda a:RoutingValidator().validate(a["route"])["metrics"],route=OBJECT)
    for name in ["rank_routes","rank_candidates"]:
        register(name,"Nur Python-validierte Routen bewerten; Evidenz für Erklärung bereitstellen.",P.READ_MODEL,_rank,routes=ITEMS)
    register("create_route_proposal","Eine Route zur Prüfung vorschlagen.",P.GENERATE_PROPOSAL,_route_proposal,route=OBJECT,prompt=(str,"Route vorschlagen."))
    register("generate_routing","Routen für Sender und Empfänger vorschlagen.",P.GENERATE_PROPOSAL,_route_proposal,source_node_id=ID,destination_node_ids=(list[str],Field(min_length=1,max_length=100)),message_id=(str|None,None),prompt=(str,"Routing erzeugen."))
    for name in ["generate_simulation_scenario","generate_fault_scenario_proposal"]:
        register(name,"Szenario als freizugebenden Vorschlag erzeugen.",P.GENERATE_PROPOSAL,generation.scenario,scenario=OBJECT,prompt=(str,"Szenario vorschlagen."))
    register("generate_signal_behavior_proposal","Signalverhalten zur Prüfung vorschlagen.",P.GENERATE_PROPOSAL,lambda a:proposals.create("SIGNAL_BEHAVIOR",[{"object_type":"SignalBehavior","data":a["behavior"]}],a["rationale"]),behavior=OBJECT,rationale=TEXT)
    register("validate_simulation_preflight","Verbindliche Vorprüfung vor einem Simulationslauf durchführen.",P.VALIDATE,lambda a:_validation(PreflightService(current_project_id()).run()))
    register("create_simulation_snapshot","Validierten unveränderlichen Simulationsstand erzeugen.",P.RUN_SIMULATION,lambda a:_simulation(a,"snapshot"),configuration=OPTIONAL_OBJECT)
    register("start_simulation","Einen validierten Snapshot einmalig starten.",P.RUN_SIMULATION,lambda a:_simulation(a,"start"),snapshot_id=ID)
    for name,action in [("get_simulation_status","status"),("stop_simulation","stop"),("get_simulation_results","results")]:
        register(name,"Projektgebundenen Simulationslauf lesen oder stoppen.",P.RUN_SIMULATION,lambda a,x=action:_simulation(a,x),job_id=ID)
    trace_fields=dict(job_id=(str|None,None),events=(list[dict[str,Any]]|None,None))
    for name,handler in [("load_trace",analysis.window),("get_trace_window",analysis.window),("analyze_trace",analysis.analyze),("find_trace_root_cause",analysis.root_cause),("find_anomalies",analysis.analyze)]:
        register(name,"Projektgebundene Trace-Ereignisse auswerten.",P.ANALYZE_TRACE,handler,**trace_fields,start_s=(float,0.0),end_s=(float,1e12),limit=LIMIT,offset=(int,Field(default=0,ge=0)),configuration=OPTIONAL_OBJECT)
    register("correlate_signals","Signalreihen auf gemeinsamen Zeitpunkten korrelieren.",P.ANALYZE_TRACE,analysis.correlate,**trace_fields,signal_names=(list[str]|None,None))
    register("compare_golden_trace","Trace mit einem Golden Trace vergleichen.",P.ANALYZE_TRACE,analysis.compare,**trace_fields,golden_job_id=(str|None,None),golden_events=(list[dict[str,Any]],Field(default_factory=list)))
    for name in ["classify_trace_fault","classify_fault"]:
        register(name,"Trace-Fehler über den ML-Fachdienst klassifizieren.",P.ANALYZE_TRACE,lambda a:MLInferenceService().classify_fault(a["trace"]),trace=OBJECT)
    register("evaluate_architecture","Kanonische Architektur bewerten.",P.VALIDATE,lambda a:IntelligenceService(current_project_id()).assess(persist=False))
    register("assess_intelligence","Data Science & Intelligence als aktuellen Workflow-Nachweis speichern.",P.VALIDATE,
             lambda a:IntelligenceService(current_project_id()).assess(persist=True))
    for name in ["find_graph_gaps","find_single_points_of_failure"]:
        register(name,"Graphlücken und Ausfallpunkte aus kanonischen Routen ermitteln.",P.READ_MODEL,lambda a:analysis.graph_analysis())
    register("update_object_via_proposal","Versionierte Änderung als Proposal erzeugen.",P.GENERATE_PROPOSAL,_update,object_type=TEXT,object_id=ID,changes=OBJECT,rationale=TEXT)
    register("delete_object_via_impact_analysis","Löschung mit Auswirkungsanalyse ausschließlich vorschlagen.",P.DELETE_WITH_IMPACT_ANALYSIS,_delete,object_type=TEXT,object_id=ID,rationale=TEXT)
    register("inspect_proposal","Gemeinsamen Proposal-Vertrag lesen.",P.READ_MODEL,lambda a:proposals.get(a["proposal_id"]),proposal_id=ID)
    register("validate_proposal","Proposal und referenzierten Modellstand validieren.",P.VALIDATE,lambda a:proposals.validate(a["proposal_id"]),proposal_id=ID)
    register("apply_approved_proposal","Ausschließlich menschlich freigegebenen, aktuellen Proposal atomar anwenden.",P.APPLY_APPROVED_PROPOSAL,lambda a:proposals.apply(a["proposal_id"],actor=a["_actor"],trace_id=a["_trace_id"]),proposal_id=ID)
    register("generate_wizard_model", "Bestätigte Wizard-Spezifikation mit den Branchenvorlagen in einen prüfbaren Modellvorschlag umsetzen.", P.GENERATE_PROPOSAL, wizard_generation.generate, prompt=TEXT)
    register("generate_wizard_routing", "Bestätigten Systemcluster-Graph deterministisch in einen prüfbaren Routing-Vorschlag umsetzen.", P.GENERATE_PROPOSAL, wizard_generation.generate_routing, prompt=TEXT)
    register("generate_wizard_network", "Freigegebene Wizard-Routen deterministisch in eine prüfbare physische Netzwerktopologie umsetzen.", P.GENERATE_PROPOSAL, wizard_generation.generate_network_topology, prompt=TEXT)
    register("create_workload","Messbaren Auftrag mit Sollzahlen planen und speichern.",P.GENERATE_PROPOSAL,lambda a:_workloads().create_workload(a["request"]),request=OBJECT)
    register("generate_signals","Signalauftrag durch vorhandenen Workload-Generator planen.",P.GENERATE_PROPOSAL,lambda a:_workloads().create_workload({**a["request"],"workload_type":"SIGNAL_GENERATION"}),request=OBJECT)
    for name,method in [("start_workload","start_workload"),("validate_workload","validate_workload"),("repair_workload","retry_invalid"),("generate_missing","generate_missing"),("inspect_workload","get_workload"),("get_workload_progress","progress")]:
        register(name,"Bestehenden Workload-Kern für Ausführung, Reparatur oder Fortschritt verwenden.",P.READ_MODEL if name.startswith(("inspect","get_")) else P.GENERATE_PROPOSAL,lambda a,m=method:getattr(_workloads(),m)(a["workload_id"]),workload_id=ID)
    register("prepare_workload_review","Vollständig validierten Workload in den gemeinsamen Review-Vertrag übernehmen.",P.GENERATE_PROPOSAL,_workload_review,workload_id=ID)
    register("inspect_agent_audit","Projektgebundene Audit-Ereignisse lesen.",P.READ_MODEL,lambda a:audit.events(a["limit"]),limit=LIMIT)
    register("discover_engineering_tools","Weitere verfügbare Werkzeuge nach Begriff suchen.",P.READ_MODEL,
             lambda a:{"tools":[{"name":item.name,"description":item.description} for item in TOOLS.values() if a["query"].casefold() in (item.name+" "+item.description).casefold()][:12]},query=TEXT)
    register('generate_camera_architecture', 'Explizit ausgewählte Kameraarchitektur als prüfbaren Vorschlag erzeugen.', P.GENERATE_PROPOSAL,
             generation.camera_architecture, coverage=TEXT, profile=TEXT, outputs=(list[str],Field(min_length=1,max_length=4)), prompt=TEXT)
    register("ask_engineering_question","Eine gezielte Auswahlfrage stellen und auf die Nutzerentscheidung warten.",P.READ_MODEL,
             _ask_question, question_id=ID,question=TEXT,multiple=(bool,False),options=(list[dict[str,Any]],Field(min_length=2,max_length=4)),
             question_description=(str,Field(default='',max_length=2000)), required=(bool,True),
             engineering_impact=(str,Field(default='REQUIRED',pattern='^(OPTIONAL|REQUIRED|CRITICAL)$')),
             recommended_options=(list[str],Field(default_factory=list,max_length=4)))


from pydantic import Field
register_tools()
