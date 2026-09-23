"""Reviewable load distribution with system clusters and explicit residual risks."""

from collections import defaultdict
from ..capacity.lin_schedule import lin_schedule_check
from ..capacity.dimensioning import bus_schedule, policy_for, stream_key, unique_streams
from copy import deepcopy
import json
from math import ceil, isfinite
import re
from typing import Any

from ..system_clusters import system_owners
from ..capacity.calculators import estimate_frame, utilization_percent
from ..capacity.service import parameters_for_protocol
from ..routing.validation import PROTOCOL_CAPACITY
from .services import _number


LOAD_KEYS = ("average_load_percent", "peak_load_percent", "burst_load_percent")
PROTOCOL_ALIASES = {
    "CANFD": "CAN_FD", "CAN_FD": "CAN_FD", "CAN-FD": "CAN_FD",
    "AUTOMOTIVE_ETHERNET": "ETHERNET", "SOMEIP": "SOME_IP", "SOME/IP": "SOME_IP",
}


def canonical_protocol(value: Any) -> str:
    normalized = str(value or "").strip().upper().replace(" ", "_")
    return PROTOCOL_ALIASES.get(normalized, normalized)


def physical_network_inventory(topology: dict[str, Any]) -> dict[str, set[str]]:
    """Count physical resources even when no current route uses them."""
    by_protocol: dict[str, set[str]] = defaultdict(set)
    for edge in topology.get('edges') or []:
        network = edge.get('physicalNetworkId')
        protocol = canonical_protocol(edge.get('bus') or edge.get('technology'))
        if network and protocol:
            by_protocol[protocol].add(str(network))
    return by_protocol


def communication_system_inventory(prompt: str) -> dict[str, int]:
    """Read the approved bus quantities embedded in a persisted wizard prompt."""
    match = re.search(r"^- Kommunikationssystem-Sollwerte:\s*(\[[^\r\n]*\])\s*$", prompt or "", re.M)
    if not match:
        return {}
    try:
        rows = json.loads(match.group(1))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    inventory: dict[str, int] = defaultdict(int)
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        identity = str(row.get("id") or row.get("label") or "").split(":")[-1]
        protocol = canonical_protocol(identity)
        if protocol not in PROTOCOL_CAPACITY:
            protocol = canonical_protocol(row.get("label"))
        if protocol in PROTOCOL_CAPACITY:
            inventory[protocol] += max(0, int(_number(row.get("count"), 0)))
    return dict(inventory)


def _technology_defaults(protocol: str, parameters: dict[str, Any]) -> dict[str, Any]:
    defaults = parameters.get("technology_defaults") or {}
    aliases = {
        "CAN_FD": ("can_fd", "canfd"), "ETHERNET": ("ethernet",),
        "SOME_IP": ("someip", "some_ip"), "LIN": ("lin",),
    }
    selected = next(
        (defaults[key] for key in aliases.get(protocol, (protocol.lower(),)) if isinstance(defaults.get(key), dict)),
        {},
    )
    return parameters_for_protocol(protocol, {**parameters, **selected})


def _candidate_route_load(row: dict[str, Any], protocol: str, parameters: dict[str, Any]) -> dict[str, float] | None:
    payload = max(0, int(_number(row.get("payload_bytes"), 8)))
    capacity = PROTOCOL_CAPACITY.get(protocol)
    if capacity is None or payload > capacity[1]:
        return None
    cycle = _number(row.get("cycle_ms"), 0)
    if cycle <= 0:
        return None
    frame = estimate_frame(protocol, payload, _technology_defaults(protocol, parameters))
    retry = max(0, min(1, _number(parameters.get("retransmission_rate"), 0)))
    average = utilization_percent(frame.transmission_time_s, cycle) * (1 + retry)
    source_average = max(_number(row.get("average_load_percent"), 0), 0.0001)
    return {
        "average_load_percent": average,
        "peak_load_percent": average * max(1, _number(row.get("peak_load_percent"), 0) / source_average),
        "burst_load_percent": average * max(1, _number(row.get("burst_load_percent"), 0) / source_average),
    }


def _technology_candidates(
    rows: list[dict[str, Any]], current_protocol: str, target: float,
    parameters: dict[str, Any], inventory: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    candidates = []
    for protocol, stock in inventory.items():
        if protocol == current_protocol or stock["free"] <= 0:
            continue
        recalculated = [_candidate_route_load(row, protocol, parameters) for row in rows]
        if not recalculated or any(item is None for item in recalculated):
            continue
        route_loads = [item for item in recalculated if item is not None]
        maximum_route = max((_load([item]) for item in route_loads), default=0)
        combined = _load(route_loads)
        bins: list[list[dict[str, float]]] = []
        for route_load in sorted(route_loads, key=lambda item: _load([item]), reverse=True):
            destination = next(
                (bucket for bucket in bins if _load([*bucket, route_load]) <= target),
                None,
            )
            if destination is None:
                bins.append([route_load])
            else:
                destination.append(route_load)
        required = max(1, len(bins))
        projected_max = max((_load(bucket) for bucket in bins), default=0)
        candidates.append({
            "protocol": protocol,
            "available_segments": stock["free"],
            "required_segments": required,
            "projected_combined_load_percent": round(combined, 4),
            "projected_max_segment_load_percent": round(projected_max, 4),
            "projected_max_route_load_percent": round(maximum_route, 4),
            "payload_compatible": True,
            "fits_target": maximum_route <= target and required <= stock["free"],
            "requires_interface_migration": True,
        })
    return sorted(
        candidates,
        key=lambda item: (
            not item["fits_target"], item["required_segments"],
            PROTOCOL_CAPACITY.get(item["protocol"], (float("inf"), 0))[0], item["protocol"],
        ),
    )


def _load(rows: list[dict[str, Any]]) -> float:
    return max((sum(_number(row.get(key)) for row in rows) for key in LOAD_KEYS), default=0.0)


def _route_ids(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({str(identifier) for row in rows for identifier in (row.get('route_ids') or [row['route_id']])})


def _schedule_check(rows: list[dict[str, Any]], parameters: dict[str, Any]) -> dict:
    protocols = {canonical_protocol(row.get('protocol')) for row in rows}
    if len(protocols) > 1:
        return {'status': 'FAIL', 'communication_schedule': {
            'status': 'MODEL_INCONSISTENT', 'responses': {},
            'reasons': ['Ein physischer Bus enthält widersprüchliche Protokolle; keine Teilmenge gilt als Gesamtnachweis.']}}
    lin = [row for row in rows if canonical_protocol(row.get('protocol')) == 'LIN']
    if lin and all('bitrate' in row for row in lin):
        # Use exactly the capacity service's complete physical master schedule.
        checked = bus_schedule(unique_streams(lin), policy_for(parameters))
        if ((parameters.get('communication_sizing') or {}).get('reserve_requirement') == 'HARD'
                and checked.get('slot_load_percent', 0) > policy_for(parameters)['maximum_slot_load_percent']):
            checked = {**checked, 'status': 'CONSTRAINT_VIOLATION', 'reasons': [
                *(checked.get('reasons') or []), 'Die ausdrücklich harte LIN-Slotreserve wird unterschritten.']}
        return {'status': 'PASS' if checked['status'] == 'FEASIBLE_UNDER_ASSUMPTIONS' else 'FAIL',
                'communication_schedule': checked}
    if protocols and protocols <= {'CAN', 'CAN_CLASSIC', 'CAN_FD'}:
        if all(_number(row.get('bitrate')) > 0 and _number(row.get('frame_time_bound_ms')) > 0
               and _number(row.get('segment_transmission_latency_ms')) > 0 for row in rows):
            checked = bus_schedule(unique_streams(rows), policy_for(parameters))
        else:
            checked = {'status': 'PROFILE_INCOMPLETE', 'reasons': [
                'Physische CAN-Bitrate oder konservative Rahmendauer fehlt.'], 'responses': {}}
        status = ('PASS' if checked['status'] == 'FEASIBLE_UNDER_ASSUMPTIONS' else
                  'FAIL' if checked['status'] in {'OVERLOAD', 'MODEL_INCONSISTENT', 'CONSTRAINT_VIOLATION'}
                  else 'UNVERIFIED')
        return {'status': status, 'communication_schedule': checked}
    legacy = lin_schedule_check(rows)
    # A batch estimate or a protocol without a schedule model is not a complete
    # timing proof. Keep a failed LIN estimate binding, expose missing evidence.
    return {**legacy, 'communication_schedule': {'status': 'UNVERIFIED', 'responses': {},
        'reasons': ['Vollständiger physischer LIN-Plan fehlt.' if lin else
                    'Für dieses Protokoll ist eine gesonderte Port-/Technologieanalyse erforderlich.']}}


def _timing_status(check: dict) -> str:
    if (check.get('communication_schedule') or {}).get('status') == 'FEASIBLE_UNDER_ASSUMPTIONS':
        return 'VERIFIED_UNDER_ASSUMPTIONS'
    return 'FAILED' if check.get('status') == 'FAIL' else 'UNVERIFIED'


def _reserve_warnings(rows: list[dict[str, Any]], target: float, parameters: dict[str, Any], error_load: float) -> list[dict]:
    """An unchanged indivisible transmission may miss a soft planning reserve.

    This does not waive payload, physical capacity, schedule or timing checks.
    The existing error threshold and explicitly hard reserve policies remain binding.
    """
    if not rows or any(canonical_protocol(row.get('protocol')) != 'LIN' for row in rows):
        return []
    row = rows[0]
    checked = _schedule_check(rows, parameters)
    if checked.get('status') != 'PASS' or not checked.get('communication_schedule'):
        return []
    schedule = checked['communication_schedule']
    if schedule.get('nominal_load_percent', 100) >= 100:
        return []
    sizing = parameters.get('communication_sizing') or {}
    if sizing.get('reserve_requirement') == 'HARD':
        return []
    warnings = []
    if len(rows) == 1 and target < _load(rows) < error_load:
        warnings.append({'severity': 'WARNING', 'code': 'CAPACITY_TARGET_RESERVE_UNMET',
        'message': f"{row.get('message_name') or row.get('name')}: vollständige Nachricht auf eigenem LIN-Netz; "
                   f"{_load(rows):.4f} % Stressbedarf überschreitet das unveränderte Reservenziel {target:g} %. "
                   'Die Reserve bleibt unterschritten; weitere gleichartige Netze verkleinern diese Nachricht nicht.',
        'message_id': row.get('message_id'), 'route_ids': _route_ids(rows),
        'target_load_percent': target, 'projected_load_percent': _load(rows),
        'nominal_load_percent': schedule['nominal_load_percent']})
    slot_limit = policy_for(parameters)['maximum_slot_load_percent']
    if schedule.get('slot_load_percent', 0) > slot_limit:
        warnings.append({'severity': 'WARNING', 'code': 'LIN_SCHEDULE_RESERVE_UNMET',
            'message': f"{row.get('message_name') or row.get('name')}: {schedule['slot_load_percent']:g} % der LIN-Slots reserviert "
                       f"bei unverändertem Reserveziel {slot_limit:g} %. Bei 100 % bleibt kein freier Slot; "
                       'der Plan gilt nur unter den ausgewiesenen Annahmen und bestätigt keine Fahrzeugfunktion.',
            'slot_load_percent': schedule['slot_load_percent'], 'maximum_slot_load_percent': slot_limit,
            'message_id': row.get('message_id'), 'route_ids': _route_ids(rows)})
    return warnings


def _within_hardware_load_limits(rows: list[dict[str, Any]], physical_interfaces: list[dict]) -> bool:
    by_id = {str(row['id']): row for row in physical_interfaces}
    # Every participant is on this shared bus, so its channel limit applies to
    # the complete segment demand rather than only its own published message.
    limits = [float(port['hard_load_limit']) for row in rows for channel_id in row.get('_physical_channel_ids', [])
              if (port := by_id.get(channel_id))
              and port.get('hard_load_limit') is not None]
    return not limits or _load(rows) < min(limits)


def plan_network_distribution(
    capacity: dict[str, Any], hardware: list[dict[str, Any]], topology: dict[str, Any], *,
    parameters: dict[str, Any] | None = None, allowed_protocols: list[str] | None = None,
    available_protocol_counts: dict[str, int] | None = None,
    resource_policy: dict[str, Any] | None = None,
    physical_interfaces: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    policy = resource_policy or {'mode': 'FIXED_INVENTORY', 'hard_limits': {}}
    auto_size = policy.get('mode') == 'AUTO_SIZE'
    hard_limits = policy.get('hard_limits') or {}
    results = capacity.get("results") or {}
    target = _number((results.get("overview") or {}).get("target_bus_load_percent"), 60.0)
    plan: dict[str, Any] = {
        "status": "NO_CAPACITY_DATA", "target_load_percent": target,
        "source_snapshot_id": str(capacity.get("id") or ""),
        "networks": [], "clusters": [], "inventory_constraints": [], "unresolved": [], "schedule_assessments": [],
        "automatic_changes": False, "requires_human_approval": True,
        "resource_policy": policy,
        "calculation": "Cluster-preserving first-fit decreasing; max(sum average, sum peak, sum burst)",
        "validation_scope": "Buslast rechnerisch geprueft; Timing, Gateway-Portkapazitaet und Safety vor Uebernahme neu pruefen.",
    }
    if capacity.get("is_outdated"):
        plan["status"] = "STALE_CAPACITY_DATA"
        return plan
    if not results.get("routes"):
        return plan
    if not isfinite(target) or not 0 < target <= 100:
        plan["status"] = "INVALID_TARGET"
        plan["unresolved"] = ["Die Ziel-Buslast muss groesser als 0 und hoechstens 100 Prozent sein."]
        return plan
    parameters = parameters or {}
    physical_interfaces = physical_interfaces or []
    owners = system_owners(hardware, topology)
    plan["clusters"] = [{"device_id": key, **owner} for key, owner in sorted(owners.items())]
    metrics_by_network: dict[str, list[dict[str, Any]]] = defaultdict(list)
    channel_ids = defaultdict(set)
    for row in results['routes']:
        for side in ('physical_source', 'physical_target'):
            if identifier := (row.get(side) or {}).get('hardware_interface_id'):
                channel_ids[stream_key(row)].add(str(identifier))
    for row in unique_streams(results["routes"]):
        row['_physical_channel_ids'] = sorted(channel_ids[stream_key(row)])
        metrics_by_network[str(row.get("network_id") or "unknown")].append(row)
    physical_networks = physical_network_inventory(topology)
    for network_id, rows in metrics_by_network.items():
        if rows:
            physical_networks[canonical_protocol(rows[0].get("protocol"))].add(network_id)
    used_protocols = {protocol: len(networks) for protocol, networks in physical_networks.items()}
    binding_inventory = bool(available_protocol_counts)
    requested_inventory = {
        canonical_protocol(key): max(0, int(value))
        for key, value in (available_protocol_counts or {}).items()
        if canonical_protocol(key) in PROTOCOL_CAPACITY
    }
    if not requested_inventory and allowed_protocols and not auto_size:
        requested_inventory = {canonical_protocol(item): 1_000_000 for item in allowed_protocols}
    if not requested_inventory and not auto_size:
        requested_inventory = {
            canonical_protocol(key): 1_000_000
            for key in (parameters.get("technology_defaults") or {})
            if canonical_protocol(key) in PROTOCOL_CAPACITY
        }
    inventory_protocols = set(requested_inventory)
    if binding_inventory or auto_size:
        inventory_protocols.update(used_protocols)
    inventory = {
        protocol: {
            "provisioned": requested_inventory.get(protocol, 0),
            "used": used_protocols.get(protocol, 0),
            "free": max(0, requested_inventory.get(protocol, 0) - used_protocols.get(protocol, 0)),
        }
        for protocol in sorted(inventory_protocols)
    }
    plan["protocol_inventory"] = inventory
    if binding_inventory and not auto_size:
        for protocol, stock in inventory.items():
            excess = max(0, stock["used"] - stock["provisioned"])
            if not excess:
                continue
            constraint = {"protocol": protocol, **stock, "excess": excess}
            plan["inventory_constraints"].append(constraint)
            plan["unresolved"].append(
                f"{protocol}: {stock['used']} physische Segmente belegt, aber nur "
                f"{stock['provisioned']} bestätigt; Sollbestand um {excess} überschritten."
            )
    remaining = {protocol: min(stock['free'], max(0, hard_limits.get(protocol, stock['provisioned']) - stock['used']))
                 for protocol, stock in inventory.items()}
    allocated = defaultdict(int)
    for protocol, maximum in hard_limits.items():
        if used_protocols.get(protocol, 0) > maximum:
            plan['unresolved'].append(f'{protocol}: bestehende Topologie überschreitet die ausdrücklich feste Grenze von {maximum} Segmenten.')
    ordered_networks = sorted(metrics_by_network.items(), key=lambda item: (-_load(item[1]), item[0]))
    for network_id, rows in ordered_networks:
        before = _load(rows)
        current_check = _schedule_check(rows, parameters)
        mixed_protocols = len({canonical_protocol(row.get('protocol')) for row in rows}) > 1
        plan['schedule_assessments'].append({'network_id': network_id, 'protocol': rows[0].get('protocol'),
            'timing_status': _timing_status(current_check),
            'communication_schedule': current_check['communication_schedule']})
        if mixed_protocols:
            reason = f'{network_id}: widersprüchliche physische Protokolle vor einer Netzaufteilung auflösen.'
            plan['unresolved'].append(reason)
            plan['networks'].append({'network_id': network_id, 'protocol': 'MIXED',
                'current_load_percent': round(before, 4), 'current_segments': 1,
                'lin_schedule': current_check, 'timing_status': 'FAILED',
                'target_status': 'EXCEEDED' if before > target else 'PASS',
                'warnings': [{'severity': 'ERROR', 'code': 'PHYSICAL_PROTOCOL_CONFLICT', 'message': reason}],
                'proposed_segments': 0, 'additional_segments': 0, 'projected_max_load_percent': round(before, 4),
                'available_additional_segments': 0, 'resource_action': 'REVIEW_PHYSICAL_MODEL',
                'new_resources_required': 0, 'decision': 'UNRESOLVED_CAPACITY_CONSTRAINT',
                'selected_protocol': 'MIXED', 'technology_candidates': [], 'segments': []})
            continue
        if canonical_protocol(rows[0].get('protocol')) in {'GPIO', 'PWM'}:
            plan['unresolved'].append(
                f'{network_id}: direkte Signalleitung; eine Aufteilung nach Buslast ist nicht anwendbar. '
                'Abtast-, Erfassungs- und Aktuierungsgrenzen am physischen Anschluss prüfen.'
            )
            continue
        if (before <= target and current_check["status"] != "FAIL"
                and _within_hardware_load_limits(rows, physical_interfaces)):
            continue
        protocol = canonical_protocol(rows[0].get("protocol") or "UNKNOWN")
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            producer = str(row.get("producer") or row["route_id"])
            owner = owners.get(producer, {"id": producer, "name": producer, "basis": "unassigned"})
            grouped[owner["id"]].append(row)
        segments = []
        for cluster_id, members in sorted(grouped.items()):
            owner = next((item for item in owners.values() if item["id"] == cluster_id), {"name": cluster_id, "basis": "unassigned"})
            bins: list[list[dict[str, Any]]] = []
            for row in sorted(members, key=lambda item: (-_load([item]), str(item["route_id"]))):
                destination = next((bucket for bucket in bins if _load([*bucket, row]) <= target
                    and _within_hardware_load_limits([*bucket, row], physical_interfaces)
                    and _schedule_check([*bucket, row], parameters)["status"] != "FAIL"), None)
                if destination is None:
                    destination = []
                    bins.append(destination)
                destination.append(row)
            for index, bucket in enumerate(bins):
                load = _load(bucket)
                segment = {
                    "name": f"{owner['name']}-{protocol.replace('_', '-')}-{index + 1}",
                    "cluster_id": cluster_id, "cluster_name": owner["name"], "ownership_basis": owner["basis"],
                    "protocol": protocol, "route_ids": _route_ids(bucket),
                    "cluster_ids": [cluster_id],
                    "cluster_names": [owner["name"]],
                    "device_ids": sorted({str(row.get("producer") or "") for row in bucket}),
                    "load_components": {key: sum(_number(row.get(key)) for row in bucket) for key in LOAD_KEYS},
                    "projected_load_percent": round(load, 4),
                    "load_check": "PASS" if load <= target else "EXCEEDED",
                    "lin_schedule": _schedule_check(bucket, parameters),
                    "alternatives": [],
                }
                if load > target:
                    for row in bucket:
                        minimum_cycle = ceil(_number(row.get("cycle_ms")) * load / target * 10) / 10
                        explanation = (
                            f"{row.get('name') or row['route_id']}: Einzelroute erreicht {load:.2f}%. "
                            f"Weitere {protocol}-Busse allein loesen das nicht. "
                            f"Zyklus >= {minimum_cycle:.1f} ms nur bei passender Anforderung; "
                            "alternativ schnelleres Protokoll und passende Interfaces pruefen."
                        )
                        segment["alternatives"].append(explanation)
                if owner["basis"] == "unassigned":
                    plan["unresolved"].append(f"Systemzuordnung von {owner['name']} noch nicht bestaetigt.")
                segments.append(segment)
        # Entire cluster portions share a bus when they fit; system ownership is
        # independent of bus membership. Only an oversized cluster spans buses.
        packed: list[dict[str, Any]] = []
        for segment in sorted(segments, key=lambda item: (-item["projected_load_percent"], item["cluster_id"])):
            destination = next((item for item in packed if max(
                item["load_components"][key] + segment["load_components"][key] for key in LOAD_KEYS
            ) <= target and _within_hardware_load_limits([row for row in rows if str(row['route_id']) in {*item['route_ids'], *segment['route_ids']}], physical_interfaces)
                and _schedule_check([row for row in rows if str(row["route_id"]) in {*item["route_ids"], *segment["route_ids"]}], parameters)["status"] != "FAIL"), None)
            if destination is None:
                packed.append(segment)
                continue
            for key in ("route_ids", "device_ids", "cluster_ids", "cluster_names", "alternatives"):
                destination[key] = list(dict.fromkeys([*destination[key], *segment[key]]))
            destination["load_components"] = {key: destination["load_components"][key] + segment["load_components"][key] for key in LOAD_KEYS}
            destination["projected_load_percent"] = round(max(destination["load_components"].values()), 4)
            destination["cluster_name"] = ", ".join(destination["cluster_names"])
            destination["lin_schedule"] = _schedule_check([row for row in rows if str(row["route_id"]) in destination["route_ids"]], parameters)
            if segment["ownership_basis"] != "explicit":
                destination["ownership_basis"] = segment["ownership_basis"]
        segments = packed
        for index, segment in enumerate(segments):
            segment["name"] = f"{network_id}-CAP-S{index + 1:02d}"
        additional = max(0, len(segments) - 1)
        same_protocol_free = remaining.get(protocol, 0 if auto_size else 1_000_000)
        available_inventory = {
            candidate_protocol: {**stock, "free": remaining.get(candidate_protocol, stock["free"])}
            for candidate_protocol, stock in inventory.items()
        }
        technology_candidates = _technology_candidates(rows, protocol, target, parameters, available_inventory)
        selected_technology = next((item for item in technology_candidates if item["fits_target"]), None)
        hardware_limits_met = all(_within_hardware_load_limits(
            [row for row in rows if str(row['route_id']) in item['route_ids']], physical_interfaces) for item in segments)
        fits_same_protocol = hardware_limits_met and max(item['projected_load_percent'] for item in segments) <= target and all(item["lin_schedule"]["status"] != "FAIL" for item in segments)
        error_load = _number((results.get('thresholds') or {}).get('overload'),
                             _number(parameters.get('overload_threshold'), 90))
        reserve_warnings = []
        timing_warnings = []
        for segment in segments:
            members = [row for row in rows if str(row['route_id']) in segment['route_ids']]
            segment['warnings'] = _reserve_warnings(members, target, parameters, error_load)
            reserve_warnings.extend(segment['warnings'])
            segment['timing_status'] = _timing_status(segment['lin_schedule'])
            if segment['timing_status'] == 'UNVERIFIED':
                warning = {'severity': 'WARNING', 'code': 'COMMUNICATION_TIMING_UNVERIFIED',
                    'message': f"{segment['name']}: Lastaufteilung ohne bestätigten Zeitnachweis. "
                        + ' '.join(segment['lin_schedule']['communication_schedule'].get('reasons') or []),
                    'route_ids': segment['route_ids']}
                segment['warnings'].append(warning)
                timing_warnings.append(warning)
        fits_with_reserve_warning = hardware_limits_met and bool(reserve_warnings) and all(
            item['lin_schedule']['status'] != 'FAIL'
            and (item['projected_load_percent'] <= target or any(w['code'] == 'CAPACITY_TARGET_RESERVE_UNMET' for w in item['warnings']))
            for item in segments)
        can_expand = auto_size and (protocol not in hard_limits or
            used_protocols.get(protocol, 0) + allocated[protocol] + additional <= hard_limits[protocol])
        resource_action = 'USE_EXISTING_SEGMENTS'
        if fits_with_reserve_warning and additional == 0:
            decision = 'KEEP_CURRENT_WITH_RESERVE_WARNING'
            resource_action = 'KEEP_CURRENT_TOPOLOGY'
        elif (fits_same_protocol or fits_with_reserve_warning) and (additional <= same_protocol_free or can_expand):
            decision = "SPLIT_CURRENT_TECHNOLOGY"
            resource_action = 'PLAN_ADDITIONAL_SEGMENTS' if additional > same_protocol_free else 'USE_EXISTING_SEGMENTS'
            allocated[protocol] += additional
            if protocol in remaining:
                remaining[protocol] = max(0, remaining[protocol] - additional)
        elif selected_technology:
            decision = "MIGRATE_TECHNOLOGY"
            selected_protocol = selected_technology["protocol"]
            remaining[selected_protocol] -= selected_technology["required_segments"]
            # A migration is only a recommendation. The split-only proposal
            # cannot spend its source segment until that migration is applied.
        else:
            decision = "UNRESOLVED_CAPACITY_CONSTRAINT"
            for segment in segments:
                plan["unresolved"].extend(segment["alternatives"])
            plan["unresolved"].append(
                f"{network_id}: {additional} zusätzliche {protocol}-Segmente benötigt, "
                f"aber nur {same_protocol_free} frei; keine verfügbare Technologie erfüllt Last und Payload."
            )
        plan["networks"].append({
            "network_id": network_id, "protocol": protocol,
            "current_load_percent": round(before, 4), "current_segments": 1,
            "lin_schedule": current_check,
            "timing_status": ('VERIFIED_UNDER_ASSUMPTIONS' if all(item['timing_status'] == 'VERIFIED_UNDER_ASSUMPTIONS' for item in segments)
                              else 'FAILED' if any(item['timing_status'] == 'FAILED' for item in segments) else 'UNVERIFIED'),
            "target_status": 'EXCEEDED' if any(item['projected_load_percent'] > target for item in segments) else 'PASS',
            "warnings": [*reserve_warnings, *timing_warnings],
            "proposed_segments": len(segments), "additional_segments": additional,
            "projected_max_load_percent": max(item["projected_load_percent"] for item in segments),
            "available_additional_segments": same_protocol_free,
            "resource_action": resource_action,
            "new_resources_required": max(0, additional - same_protocol_free) if decision == 'SPLIT_CURRENT_TECHNOLOGY' else 0,
            "decision": decision,
            "selected_protocol": (
                selected_technology["protocol"]
                if decision == "MIGRATE_TECHNOLOGY" and selected_technology
                else protocol
            ),
            "technology_candidates": technology_candidates,
            "segments": segments,
        })
    plan["remaining_protocol_inventory"] = remaining
    plan['resource_allocation'] = [{
        'protocol': protocol, 'baseline_count': stock['provisioned'], 'current_modeled_count': stock['used'],
        'recommended_count': stock['used'] + allocated[protocol],
        'increase_over_baseline': max(0, stock['used'] + allocated[protocol] - stock['provisioned']),
        'additional_for_load': allocated[protocol], 'hard_limit': hard_limits.get(protocol),
        'decision': 'EXPAND_SAME_TECHNOLOGY' if allocated[protocol] else 'KEEP_CURRENT_TOPOLOGY',
    } for protocol, stock in inventory.items()]
    plan['decision_rationale'] = ('Vorhandene freie Segmente zuerst nutzen; danach gleichartige Segmente nach berechneter '
        'Ziel-Buslast ergänzen. Protokolle, Zyklen und unbetroffene Zweige bleiben erhalten. '
        'Keine globale Minimalitätsbehauptung und kein Nachweis real vorhandener zusätzlicher Hardware.'
        if auto_size else 'Explizit feste Ressourcenobergrenzen einhalten; Engpässe als Grenzen ausweisen.')
    plan["status"] = "RESIDUAL_CONSTRAINTS" if plan["unresolved"] else "PROPOSED" if plan["networks"] else "WITHIN_TARGET"
    return plan


def split_topology_by_distribution(topology: dict[str, Any], plan: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Materialize only validated same-technology split decisions into a topology copy."""
    assignments: dict[tuple[str, str], tuple[str, str]] = {}
    for network in plan.get("networks") or []:
        if network.get("decision") != "SPLIT_CURRENT_TECHNOLOGY":
            continue
        for segment in network.get("segments") or []:
            for route_id in segment.get("route_ids") or []:
                assignments[(str(network.get("network_id")), str(route_id))] = (
                    str(segment.get("name")), str(segment.get("name")),
                )
    if not assignments:
        return deepcopy(topology), 0

    updated = deepcopy(topology)
    nodes = {str(node.get("id")): node for node in updated.get("nodes") or []}
    port_by_id = {
        str(port.get("id")): (node, port)
        for node in nodes.values()
        for port in node.get("ports") or []
        if port.get("id")
    }
    new_edges = []
    changed = 0
    for edge in updated.get("edges") or []:
        network_id = str(edge.get("physicalNetworkId") or "")
        route_ids = [str(item) for item in (edge.get("routingEntryIds") or []) if item]
        if not route_ids and edge.get("routingEntryId"):
            route_ids = [str(edge["routingEntryId"])]
        groups: dict[tuple[str, str], list[str]] = defaultdict(list)
        unchanged = []
        for route_id in route_ids:
            target = assignments.get((network_id, route_id))
            (groups[target] if target else unchanged).append(route_id)
        if not groups:
            new_edges.append(edge)
            continue
        if unchanged:
            retained = deepcopy(edge)
            retained["routingEntryIds"] = unchanged
            retained["routingEntryId"] = unchanged[0]
            retained["routingMetadata"] = {
                key: value for key, value in (retained.get("routingMetadata") or {}).items() if key in unchanged
            }
            new_edges.append(retained)
        for group_index, ((target_id, target_name), members) in enumerate(sorted(groups.items()), start=1):
            clone = deepcopy(edge)
            clone["id"] = f"{edge.get('id')}-capacity-{group_index}"
            clone["physicalNetworkId"] = target_id
            clone["physicalNetworkName"] = target_name
            clone["routingEntryIds"] = members
            clone["routingEntryId"] = members[0]
            clone["routingMetadata"] = {
                key: value for key, value in (clone.get("routingMetadata") or {}).items() if key in members
            }
            for side in ("source", "target"):
                port_key = f"{side}Port"
                original_id = str(clone.get(port_key) or "")
                original = port_by_id.get(original_id)
                node = nodes.get(str(clone.get(side) or ""))
                if original is None or node is None:
                    continue
                new_port = deepcopy(original[1])
                new_port["id"] = f"{original_id}-capacity-{target_id}"
                new_port["physicalNetworkId"] = target_id
                new_port["physicalNetworkName"] = target_name
                if not any(str(item.get("id")) == new_port["id"] for item in node.get("ports") or []):
                    node.setdefault("ports", []).append(new_port)
                clone[port_key] = new_port["id"]
            new_edges.append(clone)
            changed += 1
    updated["edges"] = new_edges
    return updated, changed


def distribution_recommendations(plan: dict[str, Any]) -> list[dict[str, Any]]:
    branch_recommendations = [{
        "candidate_id": f"SEGMENT-{network['network_id']}", "category": "Network Segmentation",
        "problem": f"{network['network_id']}: {network['current_load_percent']:.2f}% Buslast",
        "affected_objects": sorted({node for segment in network["segments"] for node in segment["device_ids"]}),
        "recommendation": (
            ' '.join(item['message'] for item in network['warnings'])
            if network.get('resource_action') == 'REVIEW_PHYSICAL_MODEL' else
            'Bestehendes physisch zulässiges Netz behalten. Die unveränderte Reserveunterschreitung ausdrücklich prüfen; '
            'weitere Segmente verändern die einzelne Nachricht nicht. '
            + ' '.join(warning['message'] for warning in network.get('warnings') or [])
            if network.get('decision') == 'KEEP_CURRENT_WITH_RESERVE_WARNING' else
            f"Auf {network['selected_protocol']} wechseln; {next((item['required_segments'] for item in network['technology_candidates'] if item['protocol'] == network['selected_protocol']), 1)} "
            "verfügbare Segmente tragen Payload und Last. Teilnehmer- und Gateway-Interfaces vor Übernahme migrieren und Timing/Safety neu prüfen."
            if network.get("decision") == "MIGRATE_TECHNOLOGY" else
            f"Busaufteilung allein reicht nicht: Einzelrouten ueberschreiten {plan['target_load_percent']:.2f}%. "
            "Die berechneten Zyklus- und Protokollalternativen pruefen; keine Lastentlastung durch unveraenderte Segmente behaupten."
            if network.get("decision") == "UNRESOLVED_CAPACITY_CONSTRAINT" else
            f"{network['proposed_segments']} {network['protocol']}-Segmente unter Erhalt der Systemcluster vorsehen. "
            f"Prognose maximal {network['projected_max_load_percent']:.2f}% bei Ziel {plan['target_load_percent']:.2f}%. "
            "Gateway-Interfaces und Timing vor Freigabe validieren."
        ),
        "expected_impact": {**network, "requires_revalidation": True},
        "evidence": [{"capacity_snapshot_id": plan["source_snapshot_id"], "target_load_percent": plan["target_load_percent"], **network}],
        "graph_context": network["segments"], "rag_context": [], "confidence": 0.9, "priority": 95,
        "priority_factors": {"capacity": 95}, "implementation_effort": "MEDIUM",
        "status": "CANDIDATE", "governance": "Validate -> Human Review -> Approval",
    } for network in plan["networks"]]
    inventory_recommendations = [{
        "candidate_id": f"INVENTORY-{item['protocol']}",
        "category": "Communication System Inventory",
        "problem": (
            f"{item['protocol']}: {item['used']} Segmente belegt, "
            f"aber nur {item['provisioned']} bestätigt"
        ),
        "affected_objects": [],
        "recommendation": (
            f"Die {item['excess']} überzähligen {item['protocol']}-Segmente konsolidieren oder "
            "den Sollbestand im Engineering-Auftrag ausdrücklich freigeben."
        ),
        "expected_impact": {**item, "requires_revalidation": True},
        "evidence": [{"capacity_snapshot_id": plan["source_snapshot_id"], **item}],
        "graph_context": [], "rag_context": [], "confidence": 1.0, "priority": 98,
        "priority_factors": {"capacity": 98}, "implementation_effort": "MEDIUM",
        "status": "CANDIDATE", "governance": "Human Review -> Approval -> Recalculate",
    } for item in plan.get("inventory_constraints") or []]
    return [*inventory_recommendations, *branch_recommendations]
