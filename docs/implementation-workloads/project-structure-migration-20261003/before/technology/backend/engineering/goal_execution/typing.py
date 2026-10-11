"""Identity-first typing over the existing canonical graph. No model mutation."""
from backend.agent_core.api.input_output import TypingResult


def type_reference(graph, reference, *, input_ref='', intent='INSPECT'):
    reference = str(reference).strip()
    exact = graph.objects.get(reference)
    # Exact IDs take precedence. Names and explicitly stored aliases are candidates,
    # not evidence that similarly named objects are the same device.
    candidates = [exact] if exact is not None else [row for row in graph.objects.values() if reference
        if reference.casefold() in {str(row.get('name', '')).casefold(),
            *[str(alias).casefold() for alias in (row.get('aliases') or []) if isinstance(alias, str)]}]
    normalized_hardware = False
    if not candidates:
        # Hardware persistence removes type suffixes (CentralGateway → Central).
        # Apply that same canonical rule, with matching device type, rather than
        # fuzzy matching names or losing the user's original hardware reference.
        from ..structure_rules import normalize_hardware_name, infer_device_type
        canonical = normalize_hardware_name(reference)
        if canonical != reference:
            candidates = [row for row in graph.hardware.values()
                if str(row.get('name', '')).casefold() == canonical.casefold()
                and row.get('device_type') == infer_device_type(reference)]
            normalized_hardware = bool(candidates)
    refs = sorted({str(row.get('id') or row.get('connection_id')) for row in candidates})
    result = TypingResult(input_ref=input_ref, intent=intent, candidate_refs=refs,
        clarification_required=len(refs) != 1)
    if len(refs) != 1:
        return result
    row = candidates[0]
    result.matched_object_ref = refs[0]
    result.source = 'CANONICAL_ID' if exact is not None else 'CANONICAL_HARDWARE_NAME' if normalized_hardware else 'CANONICAL_NAME_OR_ALIAS'
    result.confidence = 1
    result.evidence_refs = [graph.revision, refs[0]]
    for name, objects in [('HardwareNode', graph.hardware), ('Function', graph.functions),
        ('Interface', graph.interfaces), ('HardwareNetworkInterface', graph.hni),
        ('Message', graph.messages), ('Signal', graph.signals), ('Network', graph.networks)]:
        if refs[0] in objects:
            result.engineering_type = name
            break
    for field in ('device_type', 'device_class', 'data_complexity', 'unit'):
        if row.get(field) is not None:
            setattr(result, field, str(row[field]))
    semantic = row.get('semantic') or {}
    if isinstance(semantic, dict):
        result.semantic_type = semantic.get('semantic_type')
        result.behavior_type = semantic.get('behavior_type')
    return result
