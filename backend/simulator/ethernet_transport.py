"""Project-bound IPv4/IPv6 data-plane emulation; never sends real network traffic.

RFC 791 / 8200 / 768 headers. ARP and NDP remain out of scope. Optional
rest-bus sessions add deterministic TCP or application-level control frames.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import struct
from pathlib import Path


ETHERNET_TECHNOLOGIES = {
    "ethernet", "automotive_ethernet", "ipv4", "ipv6", "ip", "udp", "tcp",
    "someip", "dds", "dds_rtps", "ros2", "modbus_tcp", "doip",
}
ADDRESS_FIELDS = ("ipv4", "ipv6", "mac", "mac_address", "ip_version", "transport_protocol",
                  "source_port", "destination_port", "udp_port", "tcp_port", "mtu", "vlan_id")


def is_ethernet(technology):
    return str(technology).lower() in ETHERNET_TECHNOLOGIES


def checksum(data: bytes) -> int:
    data += b"\0" * (len(data) % 2)
    total = sum(struct.unpack(f"!{len(data) // 2}H", data))
    while total >> 16:
        total = (total & 0xffff) + (total >> 16)
    return (~total) & 0xffff


def _integer(value, minimum, maximum, label):
    if isinstance(value, bool) or str(value).strip() != str(int(value)) or not minimum <= int(value) <= maximum:
        raise ValueError(f"{label}: expected integer {minimum}..{maximum}, got {value!r}")
    return int(value)


def _mac(value):
    try:
        raw = bytes.fromhex(str(value).replace(":", "").replace("-", ""))
    except ValueError as exc:
        raise ValueError(f"Invalid Ethernet MAC address: {value!r}") from exc
    if len(raw) != 6 or raw[0] & 1 or raw == bytes(6):
        raise ValueError(f"Ethernet endpoint requires a unicast MAC address: {value!r}")
    return raw.hex(":")


def _settings(endpoint):
    interface = endpoint.get("interface") or {}
    return {**(interface.get("configuration") or {}), **interface}


def resolve_flow(route):
    """Freeze the exact addresses used by universal events and packet exports.

    Missing addresses receive deterministic simulation-only addresses, recorded
    with provenance, without editing the engineering model. Explicit conflicting
    families and malformed addresses are errors, never silently replaced.
    """
    if not is_ethernet(route["technology"]):
        return None
    source, receivers = route["sender"], route["receivers"]
    if not receivers:
        raise ValueError(f"Ethernet route {route['id']} has no receiver")
    endpoints = [source, *receivers]
    network = route.get("network_metadata") or {}
    meta = {**network, **(route.get("metadata") or {})}
    settings = [_settings(e) for e in endpoints]
    versions = {str(s["ip_version"]).lower().removeprefix("ipv") for s in [meta, *settings] if s.get("ip_version") is not None}
    technology = str(route["technology"]).lower()
    if technology in {"ipv4", "ipv6"}:
        versions.add(technology[-1])
    if len(versions) > 1 or (versions and versions - {"4", "6"}):
        raise ValueError(f"Conflicting IP versions on route {route['id']}: {sorted(versions)}")
    version = int(next(iter(versions))) if versions else (6 if any(s.get("ipv6") and not s.get("ipv4") for s in settings) else 4)
    protocol = str(meta.get("transport_protocol") or settings[0].get("transport_protocol") or ("tcp" if technology in {"tcp", "modbus_tcp", "doip"} else "udp")).lower()
    if protocol not in {"udp", "tcp"}:
        raise ValueError(f"Unsupported IP transport {protocol!r}; select UDP or TCP")
    resolved = []
    for endpoint, data in zip(endpoints, settings):
        token = f"{route['network']}:{endpoint['interface_id']}"
        digest = hashlib.sha256(token.encode()).digest()
        raw_ip = data.get(f"ipv{version}")
        if not raw_ip and data.get(f"ipv{10-version}"):
            raise ValueError(f"Interface {endpoint['interface_id']} lacks IPv{version}; no implicit family conversion")
        if raw_ip:
            try:
                address = ipaddress.ip_interface(str(raw_ip)).ip
            except ValueError as exc:
                raise ValueError(f"Invalid IPv{version} address on {endpoint['interface_id']}: {raw_ip!r}") from exc
            if address.version != version or address.is_multicast or address.is_unspecified:
                raise ValueError(f"Invalid IPv{version} endpoint address: {raw_ip!r}")
        else:
            # Reserved private / ULA space; used only in the simulated snapshot.
            address = ipaddress.ip_address(bytes([10, digest[0], digest[1], 1 + digest[2] % 254]) if version == 4 else b"\xfd" + digest[:15])
        raw_mac = data.get("mac") or data.get("mac_address")
        resolved.append({"hardware_id": endpoint["hardware_id"], "interface_id": endpoint["interface_id"],
            "port_id": endpoint["port_id"], "ip": str(address),
            "mac": _mac(raw_mac) if raw_mac else (b"\x02" + digest[:5]).hex(":"),
            "ip_provenance": "configured" if raw_ip else "simulation_derived",
            "mac_provenance": "configured" if raw_mac else "simulation_derived"})
    for key in ("ip", "mac"):
        owners = {}
        for endpoint in resolved:
            owner = owners.setdefault(endpoint[key], endpoint["interface_id"])
            if owner != endpoint["interface_id"]:
                raise ValueError(f"Duplicate {key} on route {route['id']}: {endpoint[key]}")
    src = settings[0]
    source_port = _integer(meta.get("source_port", src.get("source_port", src.get(f"{protocol}_port", 49152))), 1, 65535, "source_port")
    destination_ports = [_integer(meta.get("destination_port", data.get("destination_port", data.get(f"{protocol}_port", 5000))), 1, 65535, "destination_port") for data in settings[1:]]
    mtu = min(_integer(data.get("mtu", meta.get("mtu", 1500)), 68 if version == 4 else 1280, 65535, "mtu") for data in settings)
    vlan = meta.get("vlan_id", settings[0].get("vlan_id"))
    if vlan is not None:
        vlan = _integer(vlan, 0, 4094, "vlan_id")
    if any(s.get("vlan_id") is not None and s["vlan_id"] != vlan for s in settings):
        raise ValueError(f"Conflicting VLAN assignments on route {route['id']}")
    return {"ip_version": version, "transport_protocol": protocol, "source": resolved[0], "destinations": resolved[1:],
        "source_port": source_port, "destination_ports": destination_ports, "mtu": mtu, "vlan_id": vlan,
        "application_encoding": "canonical_payload_bytes", "generator": "project-ip-data-plane-v1"}


def packet_bytes(event, receiver_index=0):
    flow = event["ethernet"]
    source, target = flow["source"], flow["destinations"][receiver_index]
    payload = bytes.fromhex(event["payload_hex"])
    src, dst = ipaddress.ip_address(source["ip"]).packed, ipaddress.ip_address(target["ip"]).packed
    version = flow["ip_version"]
    protocol = 17 if flow["transport_protocol"] == "udp" else 6
    sport, dport = flow["source_port"], flow["destination_ports"][receiver_index]
    if protocol == 17:
        transport = struct.pack("!HHHH", sport, dport, 8 + len(payload), 0)
        checksum_offset = 6
    else:
        sequence = int(event.get("transport_sequence_bytes", int(event["sequence"]) * len(payload))) & 0xffffffff
        acknowledgement = int(event.get("transport_ack_number") or 0) & 0xffffffff
        flags = int(event.get("tcp_flags", 0x18 if payload else 0x10)) & 0xff
        transport = struct.pack("!HHIIBBHHH", sport, dport, sequence, acknowledgement, 5 << 4, flags, 65535, 0, 0)
        checksum_offset = 16
    length = len(transport) + len(payload)
    total_length = (20 if version == 4 else 40) + length
    if total_length > flow["mtu"] or length > 65535:
        raise ValueError(f"Route {event['route_id']}: IP packet {total_length} B exceeds MTU {flow['mtu']}; fragmentation is not enabled")
    pseudo = src + dst + (struct.pack("!BBH", 0, protocol, length) if version == 4 else struct.pack("!I3xB", length, protocol))
    check = checksum(pseudo + transport + payload)
    if protocol == 17 and check == 0:
        check = 0xffff
    transport = transport[:checksum_offset] + struct.pack("!H", check) + transport[checksum_offset + 2:]
    if version == 4:
        header = struct.pack("!BBHHHBBH4s4s", 0x45, 0, total_length, int(event["sequence"]) & 0xffff, 0x4000, 64, protocol, 0, src, dst)
        header = header[:10] + struct.pack("!H", checksum(header)) + header[12:]
    else:
        header = struct.pack("!IHBB16s16s", 6 << 28, length, protocol, 64, src, dst)
    ethertype = 0x0800 if version == 4 else 0x86dd
    link = bytes.fromhex(target["mac"].replace(":", "")) + bytes.fromhex(source["mac"].replace(":", ""))
    if flow.get("vlan_id") is not None:
        link += struct.pack("!HH", 0x8100, flow["vlan_id"])
    raw = link + struct.pack("!H", ethertype) + header + transport + payload
    return raw + bytes(max(0, 60 - len(raw)))  # Capture excludes FCS.


def wire_bytes(flow, payload_bytes):
    ip = 20 if flow["ip_version"] == 4 else 40
    transport = 8 if flow["transport_protocol"] == "udp" else 20
    return max(60, 14 + (4 if flow["vlan_id"] is not None else 0) + ip + transport + payload_bytes) + 24  # FCS, preamble, IFG


def write_project_captures(out_dir: Path, events, formats):
    """One RX capture record per delivered receiver, with exact event provenance.

    A streaming sidecar includes TX/RX times and also records dropped events.
    PCAPNG interface IDs identify physical RX ports; packet comments carry refs.
    """
    selected = [fmt for fmt in ("pcap", "pcapng") if fmt in formats]
    if not selected:
        return [], {}
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [out_dir / f"ethernet.{fmt}" for fmt in selected]
    sidecar = out_dir / "ethernet_packet_map.jsonl"
    ports = sorted({(d["hardware_id"], d["port_id"]) for e in events if e.get("ethernet") for d in e["ethernet"]["destinations"]})
    port_ids = {port: index for index, port in enumerate(ports)}
    def block(kind, data):
        data += bytes((-len(data)) % 4)
        return struct.pack("<II", kind, len(data) + 12) + data + struct.pack("<I", len(data) + 12)
    def option(kind, data):
        return struct.pack("<HH", kind, len(data)) + data + bytes((-len(data)) % 4)
    summary = {"generator": "project-ip-data-plane-v1", "capture_point": "receiver", "packets": 0, "dropped_events": 0,
        "ipv4_packets": 0, "ipv6_packets": 0, "unsupported_events": 0, "packet_map": str(sidecar)}
    from contextlib import ExitStack
    with ExitStack() as stack:
        handles = {fmt: stack.enter_context(path.open("wb")) for fmt, path in zip(selected, paths)}
        mapping = stack.enter_context(sidecar.open("w", encoding="utf-8", newline="\n"))
        if "pcap" in handles:
            handles["pcap"].write(struct.pack("<IHHIIII", 0xa1b2c3d4, 2, 4, 0, 0, 262144, 1))
        if "pcapng" in handles:
            handles["pcapng"].write(block(0x0a0d0d0a, struct.pack("<IHHq", 0x1a2b3c4d, 1, 0, -1)))
            for hardware, port in ports:
                handles["pcapng"].write(block(1, struct.pack("<HHI", 1, 0, 262144) + option(2, f"{hardware}/{port}/RX".encode()) + bytes(4)))
        for event in events:
            flow = event.get("ethernet")
            if not flow:
                summary["unsupported_events"] += 1
                continue
            reference = {"route_id": event["route_id"], "route_ref": event.get("route_ref"), "sequence": event["sequence"],
                "message_ids": event.get("message_ids", []), "status": event["status"], "tx_port": flow["source"]["port_id"],
                "tx_start_s": event.get("tx_start_s"), "tx_end_s": event.get("tx_end_s"), "faults": event.get("faults", [])}
            if event["status"] == "dropped":
                summary["dropped_events"] += 1
                mapping.write(json.dumps({**reference, "packet_index": None, "drop_reason": event.get("drop_reason")}) + "\n")
                continue
            for index, receiver in enumerate(flow["destinations"]):
                packet = packet_bytes(event, index)
                rx = (event.get("rx_ports") or [{} for _ in flow["destinations"]])[index]
                if rx.get("status") == "dropped":
                    mapping.write(json.dumps({**reference, "packet_index": None, "rx_port": receiver["port_id"], "status": "dropped", "drop_reason": "rx_queue_overflow"}) + "\n")
                    continue
                relative = float(rx.get("end_s", event["time_s"]))
                timestamp = float(event["timestamp_unix"]) - float(event["time_s"]) + relative
                micros = round(timestamp * 1_000_000)
                refs = {**reference, "packet_index": summary["packets"], "rx_port": receiver["port_id"], "rx_interface": receiver["interface_id"],
                    "rx_time_s": relative, "ip_version": flow["ip_version"], "src_ip": flow["source"]["ip"], "dst_ip": receiver["ip"],
                    "payload_sha256": hashlib.sha256(bytes.fromhex(event["payload_hex"])).hexdigest()}
                comment = json.dumps(refs, ensure_ascii=False).encode()
                if "pcap" in handles:
                    handles["pcap"].write(struct.pack("<IIII", micros // 1_000_000, micros % 1_000_000, len(packet), len(packet)) + packet)
                if "pcapng" in handles:
                    body = struct.pack("<IIIII", port_ids[(receiver["hardware_id"], receiver["port_id"])], micros >> 32, micros & 0xffffffff, len(packet), len(packet)) + packet + bytes((-len(packet)) % 4)
                    handles["pcapng"].write(block(6, body + option(1, comment) + bytes(4)))
                mapping.write(comment.decode() + "\n")
                summary["packets"] += 1
                summary[f"ipv{flow['ip_version']}_packets"] += 1
    return [*paths, sidecar], summary
