"""Reviewable load distribution with system clusters and explicit residual risks."""

from collections import defaultdict
from math import ceil, isfinite
from typing import Any

from ..system_clusters import system_owners
from ..capacity.calculators import estimate_frame, utilization_percent
from ..capacity.service import parameters_for_protocol
from .services import _number


LOAD_KEYS = ("average_load_percent", "peak_load_percent", "burst_load_percent")


def _load(rows: list[dict[str, Any]]) -> float:
    return max((sum(_number(row.get(key)) for row in rows) for key in LOAD_KEYS), default=0.0)


def plan_network_distribution(capacity: dict[str, Any], hardware: list[dict[str, Any]], topology: dict[str, Any], *, parameters: dict[str, Any] | None = None, allowed_protocols: list[str] | None = None) -> dict[str, Any]:
    results = capacity.get("results") or {}
    target = _number((results.get("overview") or {}).get("target_bus_load_percent"), 60.0)
    plan: dict[str, Any] = {
        "status": "NO_CAPACITY_DATA", "target_load_percent": target,
        "source_snapshot_id": str(capacity.get("id") or ""),
        "networks": [], "clusters": [], "unresolved": [],
        "automatic_changes": False, "requires_human_approval": True,
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
    owners = system_owners(hardware, topology)
    plan["clusters"] = [{"device_id": key, **owner} for key, owner in sorted(owners.items())]
    metrics_by_network: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results["routes"]:
        metrics_by_network[str(row.get("network_id") or "unknown")].append(row)
    for network_id, rows in sorted(metrics_by_network.items()):
        before = _load(rows)
        if before <= target:
            continue
        protocol = str(rows[0].get("protocol") or "UNKNOWN")
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
                destination = next((bucket for bucket in bins if _load([*bucket, row]) <= target), None)
                if destination is None:
                    destination = []
                    bins.append(destination)
                destination.append(row)
            for index, bucket in enumerate(bins):
                load = _load(bucket)
                segment = {
                    "name": f"{owner['name']}-{protocol.replace('_', '-')}-{index + 1}",
                    "cluster_id": cluster_id, "cluster_name": owner["name"], "ownership_basis": owner["basis"],
                    "protocol": protocol, "route_ids": [str(row["route_id"]) for row in bucket],
                    "cluster_ids": [cluster_id],
                    "cluster_names": [owner["name"]],
                    "device_ids": sorted({str(row.get("producer") or "") for row in bucket}),
                    "load_components": {key: sum(_number(row.get(key)) for row in bucket) for key in LOAD_KEYS},
                    "projected_load_percent": round(load, 4),
                    "load_check": "PASS" if load <= target else "EXCEEDED",
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
                        plan["unresolved"].append(explanation)
                        if protocol.upper() == "LIN" and allowed_protocols and "CAN_FD" in allowed_protocols:
                            candidate_parameters = parameters_for_protocol("CAN_FD", parameters or {})
                            estimate = estimate_frame("CAN_FD", int(_number(row.get("payload_bytes"), 8)), candidate_parameters)
                            cycle = _number(row.get("cycle_ms"))
                            retry = max(0, min(1, _number((parameters or {}).get("retransmission_rate"))))
                            factor = max(1, _load([row]) / max(_number(row.get("average_load_percent")), 0.0001))
                            candidate_load = utilization_percent(estimate.transmission_time_s, cycle) * (1 + retry) * factor
                            segment["alternatives"].append(
                                f"Berechnete CAN-FD-Alternative: {candidate_load:.2f}% bei unveraendert {cycle:.1f} ms und "
                                f"{candidate_parameters['bitrate']:.0f} bit/s. CAN-FD-Interfaces an Teilnehmer und Gateway sowie Timing/Safety sind freigabepflichtig."
                            )
                if owner["basis"] == "unassigned":
                    plan["unresolved"].append(f"Systemzuordnung von {owner['name']} noch nicht bestaetigt.")
                segments.append(segment)
        # Entire cluster portions share a bus when they fit; system ownership is
        # independent of bus membership. Only an oversized cluster spans buses.
        packed: list[dict[str, Any]] = []
        for segment in sorted(segments, key=lambda item: (-item["projected_load_percent"], item["cluster_id"])):
            destination = next((item for item in packed if max(
                item["load_components"][key] + segment["load_components"][key] for key in LOAD_KEYS
            ) <= target), None)
            if destination is None:
                packed.append(segment)
                continue
            for key in ("route_ids", "device_ids", "cluster_ids", "cluster_names", "alternatives"):
                destination[key] = list(dict.fromkeys([*destination[key], *segment[key]]))
            destination["load_components"] = {key: destination["load_components"][key] + segment["load_components"][key] for key in LOAD_KEYS}
            destination["projected_load_percent"] = round(max(destination["load_components"].values()), 4)
            destination["cluster_name"] = ", ".join(destination["cluster_names"])
            if segment["ownership_basis"] != "explicit":
                destination["ownership_basis"] = segment["ownership_basis"]
        segments = packed
        for index, segment in enumerate(segments):
            segment["name"] = f"{protocol.replace('_', '-')}-{index + 1}"
        plan["networks"].append({
            "network_id": network_id, "protocol": protocol,
            "current_load_percent": round(before, 4), "current_segments": 1,
            "proposed_segments": len(segments), "additional_segments": max(0, len(segments) - 1),
            "projected_max_load_percent": max(item["projected_load_percent"] for item in segments),
            "segments": segments,
        })
    plan["status"] = "RESIDUAL_CONSTRAINTS" if plan["unresolved"] else "PROPOSED" if plan["networks"] else "WITHIN_TARGET"
    return plan


def distribution_recommendations(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "candidate_id": f"SEGMENT-{network['network_id']}", "category": "Network Segmentation",
        "problem": f"{network['network_id']}: {network['current_load_percent']:.2f}% Buslast",
        "affected_objects": sorted({node for segment in network["segments"] for node in segment["device_ids"]}),
        "recommendation": (
            f"Busaufteilung allein reicht nicht: Einzelrouten ueberschreiten {plan['target_load_percent']:.2f}%. "
            "Die berechneten Zyklus- und Protokollalternativen pruefen; keine Lastentlastung durch unveraenderte Segmente behaupten."
            if network["projected_max_load_percent"] > plan["target_load_percent"] else
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
