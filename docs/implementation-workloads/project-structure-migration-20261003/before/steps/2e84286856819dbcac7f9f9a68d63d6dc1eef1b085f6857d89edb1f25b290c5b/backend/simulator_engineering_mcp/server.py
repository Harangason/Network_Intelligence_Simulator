"""MCP registration only: authority and all domain operations live in Python core."""
from __future__ import annotations

import json
from mcp.server import MCPServer
from mcp.types import ToolAnnotations, CallToolResult, TextContent
from pydantic import ValidationError
from backend.agent_core.api.tool_contract import Permission, ToolResult
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.agent_tools.services import TOOLS
from backend.engineering.agent_tools import model as access
from backend.engineering.repository import ENTITY_SPECS
from backend.engineering.device_classification import DeviceClassificationRegistry


class EngineeringMCPServer(MCPServer):
    async def call_tool(self, name, arguments, context=None):
        definition = TOOLS.get(name)
        if definition:
            try:
                definition.input_model.model_validate(arguments.get('request'))
            except ValidationError as error:
                schema = definition.input_model.model_json_schema()
                result = ToolResult(success=False, status='INVALID_INPUT', findings=[{
                    'code': 'INVALID_INPUT', 'field': ['request', *item['loc']],
                    'reason': item['type'], 'message': item['msg'],
                    'expected_schema': schema,
                } for item in error.errors(include_input=False, include_context=False)])
                return CallToolResult(structured_content=result.model_dump(mode='json'),
                    content=[TextContent(type='text', text=result.model_dump_json())], is_error=True)
        return await super().call_tool(name, arguments, context)


def create_server(authority: ToolAuthority) -> MCPServer:
    server = EngineeringMCPServer("simulator-engineering-mcp", version="1.0.0", instructions=(
        "Projektgebundener Zugriff auf den Simulator. Tool-Erfolg bedeutet nicht Workload-Abschluss. "
        "Generierung erzeugt Vorschläge. Freigabe erfolgt ausschließlich durch die menschliche Review-Oberfläche. "
        "Der Agent meldet READY_FOR_REVIEW vor Apply und COMPLETED erst nach bestätigten kanonischen IDs. "
        "Ausnahme: Ein serverseitig vom Nutzer freigegebener Engineering-Gesamtplan wird durch continue_engineering_goal "
        "innerhalb seines gespeicherten Umfangs vollständig ausgeführt. Das Modell darf keine Freigabe erzeugen. "
        "Für Kommunikationsaufträge prepare_engineering_connection verwenden; Navigation ersetzt keine Umsetzung."))
    for definition in TOOLS.values():
        def make_tool(item):
            def call(request):
                # A draft edit is a patch: omitted fields must not become null
                # and clear earlier decisions, including nested device fields.
                arguments = request.model_dump(exclude_unset=item.name == 'update_project_draft')
                return execute(authority, item.name, item.permission, arguments, item.handler)
            call.__name__ = item.name
            call.__annotations__ = {"request": item.input_model, "return": ToolResult}
            return call
        read_only = definition.permission in {Permission.READ_MODEL, Permission.ANALYZE_TRACE}
        if definition.name in {"analyze_trace_root_cause", "find_trace_root_cause", "explain_simulation_failure", "investigate_deadline_miss", "analyze_fault_effects", "continue_reasoning"}:
            read_only = False  # Persists a derived analysis, never an architecture change.
        server.add_tool(make_tool(definition), name=definition.name, description=definition.description,
                        meta={'version': '1.0.0', 'permission': definition.permission.value},
                        annotations=ToolAnnotations(read_only_hint=read_only, destructive_hint=definition.name == "apply_approved_proposal",
                                                    idempotent_hint=read_only, open_world_hint=False), structured_output=True)

    def resource_result(project_id: str, section: str) -> str:
        def read(_):
            if project_id != authority.project_id:
                raise PermissionError("Die Ressource gehört nicht zum aktiven Projekt.")
            if section == "project":
                return TOOLS["inspect_project"].handler({})
            if section == "model":
                return access.model()
            if section == 'capabilities':
                return TOOLS['inspect_assistant_capabilities'].handler({})
            if section in access.SECTIONS:
                return {"items": access.objects(access.SECTIONS[section])}
            if section == "routing":
                return {"items": access.routes()}
            if section == "networks":
                return {"items": access.networks()}
            return TOOLS["inspect_findings"].handler({})
        result = execute(authority, f"resource:{section}", Permission.READ_MODEL, {}, read)
        return result.model_dump_json()

    for section in ["project", "model", *access.SECTIONS, "networks", "routing", "findings", "capabilities"]:
        uri = "simulator://project/{project_id}" + ("" if section == "project" else f"/{section}")
        def make_resource(key):
            def read(project_id: str) -> str:
                return resource_result(project_id, key)
            return read
        server.resource(uri, name=f"project-{section}", description=f"Kanonische Projektressource: {section}")(make_resource(section))

    @server.resource("simulator://schemas/{object_type}")
    def schema(object_type: str) -> str:
        kind = {"signal":"Signal", "message":"Message", "function":"Function", "hardware-interface":"HardwareNetworkInterface"}.get(object_type)
        if kind is None:
            raise ValueError("Unbekanntes Schema.")
        spec = ENTITY_SPECS[kind]
        return json.dumps({"object_type":kind,"required":["name",*spec.required],"properties":["name",*spec.own_columns],"enums":spec.enum_fields or {}},ensure_ascii=False)

    @server.resource("simulator://technologies/can-fd")
    def can_fd() -> str:
        from backend.engineering.message_packing import CAN_FD_PAYLOAD_CLASSES
        return json.dumps({"technology":"CAN_FD","max_payload_bytes":64,"payload_classes":CAN_FD_PAYLOAD_CLASSES,
                           "calculation_service":"backend.engineering.capacity.calculators.estimate_frame"})

    @server.resource("simulator://device-classes")
    def device_classes() -> str:
        return json.dumps(DeviceClassificationRegistry().class_options(),ensure_ascii=False)

    return server
