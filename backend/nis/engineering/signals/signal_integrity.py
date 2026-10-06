"""Semantic/encoding invariants and narrowly evidenced legacy generator repairs."""
from copy import deepcopy
from math import isfinite

VERSION = "signal-integrity-v1"
CODE_UNITS = {"", "code", "bool", "boolean", "enum", "state", "not_applicable", "1"}
LEGACY_ENUM = {"OK": 0, "WARNING": 1, "ERROR": 2, "NOT_AVAILABLE": 3}


def physical_unit(unit):
    return str(unit or "").strip().lower() not in CODE_UNITS


def raw_codes(data):
    return [*(data.get("enum_values") or {}).values(), *(data.get("reserved_values") or []),
            *(data.get("invalid_values") or ([] if data.get("invalid_value") is None else [data["invalid_value"]]))]


def integrity_checks(signal):
    checks = []
    def add(code, text, severity="ERROR"):
        checks.append({"code": code, "severity": severity, "text": text})
    data = signal.get("data") or {}
    semantic = str((signal.get("semantic") or {}).get("semantic_type") or "").upper()
    codes = raw_codes(data)
    if physical_unit(signal.get("unit")) and (semantic in {"STATE", "ENUM", "BOOLEAN", "FLAG"} or data.get("enum_values")):
        add("SIGNAL_SEMANTIC_ENCODING_CONFLICT", "Physikalische Messgröße und Zustandskodierung sind vermischt; Bedeutung und Kodierung getrennt festlegen.")
    if semantic == "NUMERIC" and data.get("resolution") is not None and signal.get("factor") is not None:
        try:
            resolution, factor = float(data["resolution"]), abs(float(signal["factor"]))
            if not isfinite(resolution) or not isfinite(factor) or resolution <= 0 or factor > resolution + 1e-9:
                add("SIGNAL_RESOLUTION_CONFLICT", "Skalierungsfaktor erfüllt die geforderte Auflösung nicht.")
        except (ValueError, TypeError):
            add("SIGNAL_RESOLUTION_CONFLICT", "Auflösung oder Skalierungsfaktor ist ungültig.")
    bits = signal.get("length_bits")
    if isinstance(bits, int) and 0 < bits <= 64:
        signed = str(signal.get("data_type") or "").lower() in {"signed", "int", "int8", "int16", "int32", "int64"}
        lo, hi = (-(2 ** (bits - 1)), 2 ** (bits - 1) - 1) if signed else (0, 2 ** bits - 1)
        if any(not isinstance(c, (int, float)) or not isfinite(c) or int(c) != c or not lo <= c <= hi for c in codes):
            add("SIGNAL_CODE_OUT_OF_RANGE", "Ein definierter Rohcode passt nicht in Datentyp und Bitbreite.")
    enums = set(str(v) for v in (data.get("enum_values") or {}).values())
    reserved = set(str(v) for v in data.get("reserved_values") or [])
    invalid = set(str(v) for v in data.get("invalid_values") or ([] if data.get("invalid_value") is None else [data["invalid_value"]]))
    if enums & reserved or enums & invalid or reserved & invalid:
        add("SIGNAL_CODE_DOMAIN_OVERLAP", "Gültige, reservierte und ungültige Rohcodes überschneiden sich.")
    return checks


def legacy_numeric_repair(signal):
    """Only the exact known generated template; preserve all physical encoding.

    User/imported domains and edited templates remain findings, never guessed fixes.
    Previous data are retained verbatim in provenance for audit/reversal.
    """
    semantic, data = signal.get("semantic") or {}, signal.get("data") or {}
    configuration = signal.get("configuration") or {}
    if signal.get("source") != "ai_generated" or VERSION in (signal.get("provenance") or {}):
        return None
    role = configuration.get("generation_role")
    companion = ((role == "QUALITY" and semantic.get("semantic_type") == "NUMERIC" and signal.get("unit") == "%"
                  and signal.get("min_value") == 0 and signal.get("max_value") == 100 and signal.get("factor") == .5)
                 or (role == "ALIVECOUNTER" and semantic.get("semantic_type") == "COUNTER" and signal.get("unit") == "count"
                     and signal.get("min_value") == 0 and signal.get("max_value") == 15 and signal.get("factor") == 1))
    parser = semantic.get("generated_by") == "engineering-specification-parser-v2"
    numeric = parser and semantic.get("semantic_type") == "NUMERIC" and not data.get("enum_values") and not data.get("reserved_values")
    state_error = (parser and semantic.get("semantic_type") == "STATE" and physical_unit(signal.get("unit"))
                   and data.get("enum_values") == LEGACY_ENUM and data.get("reserved_values") == [4, 5, 6, 7]
                   and data.get("invalid_values") == [15] and data.get("resolution") == 1)
    # Numeric v2 generated a physical maximum+resolution as an undeclared raw error code.
    if numeric:
        numeric = data.get("invalid_values") == [signal.get("max_value", 0) + signal.get("factor", 0)]
    if not (companion or state_error or numeric):
        return None
    factor, minimum, maximum = signal.get("factor"), signal.get("min_value"), signal.get("max_value")
    if factor is None or factor <= 0 or minimum is None or maximum is None or minimum >= maximum:
        return None
    provenance = deepcopy(signal.get("provenance") or {})
    provenance[VERSION] = {"reason": "Known parser-v2 domain generation or companion-domain inheritance",
        "previous_semantic": deepcopy(semantic), "previous_data": deepcopy(data), "previous_configuration": deepcopy(configuration)}
    configuration = deepcopy(signal.get("configuration") or {})
    configuration.update(encoding_type="linear", bit_length=signal["length_bits"], start_bit=signal["start_bit"],
        factor=signal["factor"], offset=signal["offset_value"], raw_datatype=signal["data_type"], signed=signal["data_type"] == "signed")
    corrected_semantic = {**semantic, "semantic_type": "COUNTER" if role == "ALIVECOUNTER" else "NUMERIC", "unit": signal["unit"],
        "generated_by": "engineering-specification-parser-v3", "assumptions": [], "correction": VERSION}
    return {"semantic": corrected_semantic, "configuration": configuration, "provenance": provenance,
        "data": {"minimum": minimum, "maximum": maximum, "resolution": factor,
                 "enum_values": {}, "allowed_values": [], "invalid_values": [], "reserved_values": []}}
