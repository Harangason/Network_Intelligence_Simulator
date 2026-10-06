"""Preserved technology-specific scheduling bound; functional acceptance remains separate."""
from math import ceil, floor, lcm
from backend.nis.communication.core.scheduling import number, _constraints

from collections import defaultdict

def schedule(rows, result):
    """Bound Ethernet serialization independently for each confirmed TX port."""
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    try:
        technology = DEFAULT_TECHNOLOGY_REGISTRY.profile("ethernet")
    except KeyError:
        return {**result, "status": "PROFILE_INCOMPLETE", "reasons": ["Ethernet TechnologyProfile fehlt."]}
    if technology.get("medium_access_model") not in {"FULL_DUPLEX_SWITCHED","VARIANT_DEPENDENT"}:
        return {**result, "status": "PROFILE_INCOMPLETE", "reasons": ["Das Ethernet TechnologyProfile weist kein geschaltetes Vollduplex-Zugriffsmodell aus."]}

    allowed_rates = {number(value) for value in (technology.get("rate_model") or {}).get("allowed_bps", [])}
    maximum_payload = number(technology.get("max_payload_bytes"))
    ports = defaultdict(list)
    for row in rows:
        if row.get('duplex')!='FULL' or row.get('eth_link_up') is not True:
            return {**result,'status':'PROFILE_INCOMPLETE','reasons':['Ethernet benötigt bestätigten Vollduplex-Link; unbekannter Zustand oder CSMA/CD liefert keinen FIFO-Nachweis.']}
        if any(row.get(key) is not False for key in ('eth_pause_rx','eth_pause_tx','eth_eee_enabled')):
            return {**result,'status':'PROFILE_INCOMPLETE','reasons':['PAUSE/PFC oder EEE sind aktiv oder unbekannt; ihre Blockierzeiten sind im FIFO-Modell nicht nachgewiesen.']}
        source = row.get("physical_source") or {}
        node_id = str(source.get("node_id") or "").strip()
        port_id = str(source.get("hardware_interface_id") or source.get("physical_port_ref") or source.get("port_id") or "").strip()
        if not node_id or not port_id or row.get("physical_path_resolved") is not True:
            return {**result, "status": "PROFILE_INCOMPLETE", "reasons": ["Für Ethernet fehlen bestätigter physischer Pfad oder eindeutiger TX-Port."]}
        if str(row.get("queue_policy") or "").upper() != "FIFO":
            return {**result, "status": "PROFILE_INCOMPLETE", "reasons": ["Das Ethernet-Antwortzeitmodell unterstützt derzeit nur eine FIFO-Sendequeue."]}
        bitrate = number(row.get("bitrate"))
        if not bitrate or (allowed_rates and bitrate not in allowed_rates):
            return {**result, "status": "PROFILE_INCOMPLETE", "reasons": ["Ethernet-Linkrate fehlt oder ist im TechnologyProfile nicht freigegeben."]}
        if maximum_payload and number(row.get("payload_bytes")) > maximum_payload:
            return {**result, "status": "PROFILE_INCOMPLETE", "reasons": ["Ethernet-Nutzlast überschreitet die Profilgrenze; Fragmentierung ist nicht modelliert."]}
        if row.get("calculation_model") != "ETHERNET_WIRE_ESTIMATE":
            return {**result, "status": "PROFILE_INCOMPLETE", "reasons": ["Ethernet-spezifische Wire-Serialisierung fehlt."]}
        if number(row.get("segment_transmission_latency_ms")) <= 0:
            return {**result, "status": "PROFILE_INCOMPLETE", "reasons": ["Ethernet-Rahmen-Serialisierungsgrenze fehlt."]}
        ports[(node_id, port_id)].append(row)

    port_schedules = []
    responses = {}
    port_loads = []
    reasons = []
    for (node_id, port_id), members in sorted(ports.items()):
        if len({number(row.get("bitrate")) for row in members}) > 1:
            return {**result, "status": "MODEL_INCONSISTENT", "reasons": ["Ein physischer Ethernet-TX-Port besitzt widersprüchliche Linkraten."]}
        utilization = sum(number(row.get("segment_transmission_latency_ms")) / number(row.get("cycle_ms")) * 100
                          for row in members)
        port_loads.append(utilization)
        port_responses = {}
        port_reasons = []
        port_status = "FEASIBLE_UNDER_ASSUMPTIONS"
        if utilization >= 100:
            port_status = "OVERLOAD"
            port_reasons.append("Nominaler Ethernet-Sendeportbedarf erreicht oder überschreitet 100 %.")
        else:
            for row in members:
                stream_id = row["stream_id"]
                own = number(row.get("segment_transmission_latency_ms"))
                period = number(row.get("cycle_ms"))
                response = own
                for _ in range(1000):
                    workload = 0.0
                    for other in members:
                        other_period = number(other.get("cycle_ms"))
                        jitter = number(other.get("release_jitter_ms"))
                        jobs = ceil((response + jitter + 1e-9) / other_period)
                        if other["stream_id"] == stream_id:
                            jobs = max(0, jobs - 1)
                        workload += jobs * number(other.get("segment_transmission_latency_ms"))
                    updated = own + workload
                    if abs(updated - response) < 1e-9:
                        response = updated
                        break
                    response = updated
                else:
                    port_status = "SEARCH_LIMIT"
                    port_reasons.append("Ethernet-FIFO-Antwortzeitanalyse hat die Iterationsgrenze erreicht.")
                port_responses[stream_id] = response
                port_reasons.extend(_constraints(row, period,
                    response + number(row.get("fixed_path_delay_ms")),
                    response - number(row.get("segment_transmission_latency_ms"))))
            if port_reasons and port_status == "FEASIBLE_UNDER_ASSUMPTIONS":
                port_status = "CONSTRAINT_VIOLATION"
        port_schedules.append({"source_node_id": node_id, "source_port_id": port_id,
            "nominal_load_percent": round(utilization, 6), "status": port_status,
            "responses": port_responses, "reasons": port_reasons})
        responses.update(port_responses)
        reasons.extend(port_reasons)

    statuses = {item["status"] for item in port_schedules}
    status = ("OVERLOAD" if "OVERLOAD" in statuses else
              "SEARCH_LIMIT" if "SEARCH_LIMIT" in statuses else
              "CONSTRAINT_VIOLATION" if "CONSTRAINT_VIOLATION" in statuses else
              "FEASIBLE_UNDER_ASSUMPTIONS")
    if status == "OVERLOAD":
        reasons = ["Mindestens ein Ethernet-Sendeport ist nominal überlastet."]
    return {**result, "model": "ETHERNET_FULL_DUPLEX_FIFO_RESPONSE_BOUND_V1",
        "status": status, "nominal_load_percent": round(max(port_loads, default=0.0), 6),
        "responses": responses, "port_schedules": port_schedules, "reasons": reasons,
        "assumptions": [*result.get("assumptions", []),
            "Voll-duplex geschaltete Ethernet-Links werden je physischem TX-Port getrennt bewertet",
            "Nicht präemptive FIFO-Übertragung; maximale Ankunft entsprechend Zyklus/Mindestabstand",
            "Ethernet-Wire-Estimate als Serialisierungsgrenze; keine Fehler- oder Retransmissions-Bursts",
            "Kein TAS/CBS/TSN-Zeitplan und keine funktionale Fristfreigabe"]}

# Physical ports have independent rates and queues; nominal total is no bus limit.
INDEPENDENT_PORTS = True

def schedule_context(rows, policy, periods, result):
    return schedule(rows, result)

def policy_only_eligible(entry, check):
    # Preserve the published raw-ID behavior of the historical sizing service.
    return entry['protocol'] == 'ETHERNET' and check['status'] in {'UNVERIFIED', 'PROFILE_INCOMPLETE'}


def independent_segment_key(network_id, segment_edges):
    return network_id, segment_edges

def serialized_path_factor(frame):
    return 2 if frame.calculation_model == 'ETHERNET_WIRE_ESTIMATE' else 1
