"""Decode generated packet bytes independently of the serializer under test."""
from copy import deepcopy
import ipaddress
import json
import struct

import pytest
from ethernet_transport import packet_bytes, checksum
from communication_simulator import run_simulation
from hardware_profile import normalize_hardware_config
from universal_trace import generate_universal_events


def ip_config(tmp_path, version=4):
    ips = ["192.0.2.10", "192.0.2.20", "192.0.2.30"] if version == 4 else ["2001:db8::10", "2001:db8::20", "2001:db8::30"]
    return {"output_dir": str(tmp_path), "seed": 0, "duration_s": .02, "formats": ["universal-jsonl", "universal-csv", "pcap", "pcapng"],
        "networks": [{"id": "project-lan", "technology": "ethernet", "bitrate": 1_000_000}],
        "hardware": {"devices": [{"id": name, "ports": [{"id": name + "-port", "network_interfaces": [{"id": name + "-eth", "technology": "ethernet", "network": "project-lan", f"ipv{version}": address, "mac": f"02:00:00:00:00:0{i+1}"}]}]} for i, (name, address) in enumerate(zip(("a", "b", "c"), ips))]},
        "communications": [{"id": "project-message", "routing_entry_id": "approved-route", "sender_interface": "a-eth", "receiver_interfaces": ["b-eth"], "technology": "ethernet", "cycle_ms": 10, "payload_bytes": 16, "jitter_ratio": 0, "source_port": 12345, "destination_port": 23456}],
        "scenario": {"mode": "NORMAL", "faults": []}}


def events(config):
    return generate_universal_events(config, normalize_hardware_config(config), start_utc=1700000000)[1]


@pytest.mark.parametrize("version", [4, 6])
@pytest.mark.parametrize("protocol", ["udp", "tcp"])
def test_exact_project_addresses_payload_headers_checksums(tmp_path, version, protocol):
    config = ip_config(tmp_path, version)
    config["communications"][0]["transport_protocol"] = protocol
    e = events(config)[0]
    packet = packet_bytes(e)
    assert packet[:6].hex(":") == "02:00:00:00:00:02"
    assert packet[6:12].hex(":") == "02:00:00:00:00:01"
    assert packet[12:14] == bytes.fromhex("0800" if version == 4 else "86dd")
    ip = packet[14:]
    assert ip[0] >> 4 == version
    if version == 4:
        assert checksum(ip[:20]) == 0
        src, dst, body = ip[12:16], ip[16:20], ip[20:struct.unpack("!H", ip[2:4])[0]]
        proto = ip[9]
        pseudo = src + dst + struct.pack("!BBH", 0, proto, len(body))
    else:
        src, dst, body = ip[8:24], ip[24:40], ip[40:40+struct.unpack("!H", ip[4:6])[0]]
        proto = ip[6]
        pseudo = src + dst + struct.pack("!I3xB", len(body), proto)
    assert str(ipaddress.ip_address(src)) == e["src_ip"]
    assert str(ipaddress.ip_address(dst)) == e["dst_ips"][0]
    assert struct.unpack("!HH", body[:4]) == (12345, 23456)
    assert checksum(pseudo + body) == 0
    assert body[8 if protocol == "udp" else 20:] == bytes.fromhex(e["payload_hex"])
    assert e["ethernet"]["source"]["ip_provenance"] == "configured"


@pytest.mark.parametrize("version", [4, 6])
def test_captures_come_from_same_events_with_loss_and_provenance(tmp_path, version):
    config = ip_config(tmp_path, version)
    config["scenario"] = {"mode": "USER_DEFINED_FAULT", "faults": [{"scope": "MESSAGE", "type": "MESSAGE_LOSS", "target": {"id": "project-message"}, "start_s": .01, "end_s": .011}]}
    result = run_simulation(config)
    universal = [json.loads(line) for line in (tmp_path / "traces/universal_trace.jsonl").read_text().splitlines()]
    assert len([e for e in universal if e["status"] == "dropped"]) == 1
    rows = [json.loads(line) for line in (tmp_path / "native/ethernet_packet_map.jsonl").read_text().splitlines()]
    assert len(rows) == len(universal)
    assert result["native_ethernet"]["packets"] == 2
    assert result["native_ethernet"][f"ipv{version}_packets"] == 2
    data = (tmp_path / "native/ethernet.pcap").read_bytes()
    position = 24
    delivered = [e for e in universal if e["status"] != "dropped"]
    for event in delivered:
        sec, us, size, original = struct.unpack("<IIII", data[position:position+16])
        position += 16
        assert data[position:position+size] == packet_bytes(event)
        assert abs(sec+us/1e6-event["timestamp_unix"]) < 1e-6
        position += size
    assert position == len(data)
    assert all(row["route_ref"] == "approved-route" for row in rows)
    assert b"b/b-port/RX" in (tmp_path / "native/ethernet.pcapng").read_bytes()


def test_full_duplex_and_independent_ports_but_shared_tx_and_rx_contend(tmp_path):
    config = ip_config(tmp_path)
    route = config["communications"][0]
    config["communications"].append({**route, "id": "reverse", "sender_interface": "b-eth", "receiver_interfaces": ["a-eth"]})
    first = [e for e in events(config) if e["sequence"] == 0]
    assert all(e["queue_delay_ms"] == 0 for e in first)
    config["communications"].append({**route, "id": "same-tx", "receiver_interfaces": ["c-eth"]})
    first = [e for e in events(config) if e["sequence"] == 0]
    assert next(e for e in first if e["route_id"] == "same-tx")["queue_delay_ms"] > 0
    config["communications"][-1].update(sender_interface="c-eth", receiver_interfaces=["b-eth"])
    first = [e for e in events(config) if e["sequence"] == 0]
    assert max(e["rx_ports"][0]["queue_delay_ms"] for e in first) > 0


def test_missing_addresses_are_stable_and_never_modify_input(tmp_path):
    config = ip_config(tmp_path)
    for node in config["hardware"]["devices"]:
        interface = node["ports"][0]["network_interfaces"][0]
        del interface["ipv4"], interface["mac"]
    original = deepcopy(config)
    a, b = events(config), events(config)
    assert a == b and config == original
    assert a[0]["ethernet"]["source"]["ip_provenance"] == "simulation_derived"


def test_runtime_load_is_busiest_physical_direction_not_sum_of_ports(tmp_path):
    from backend.app.runtime_analysis import analyze_runtime_trace
    config = ip_config(tmp_path)
    route = config['communications'][0]
    config['communications'].append({**route, 'id': 'reverse', 'sender_interface': 'b-eth', 'receiver_interfaces': ['a-eth']})
    result = analyze_runtime_trace({'model_simulation': {'frames': events(config)}}, config)
    network = result['networks'][0]
    assert network['load_basis'] == 'BUSIEST_FULL_DUPLEX_PORT'
    assert len(network['port_metrics']) == 4
    assert network['peak_load_percent'] == pytest.approx(6.72)


@pytest.mark.parametrize("change,match", [("family", "family conversion"), ("bad_ip", "address"), ("duplicate", "Duplicate"), ("mtu", "MTU"), ("port", "destination_port")])
def test_invalid_configuration_fails_explicitly(tmp_path, change, match):
    config = ip_config(tmp_path)
    interface = config["hardware"]["devices"][1]["ports"][0]["network_interfaces"][0]
    if change == "family":
        del interface["ipv4"]
        interface["ipv6"] = "2001:db8::20"
    elif change == "bad_ip":
        interface["ipv4"] = "999.1.2.3"
    elif change == "duplicate":
        interface["ipv4"] = "192.0.2.10"
    elif change == "mtu":
        config["communications"][0]["payload_bytes"] = 1500
    else:
        config["communications"][0]["destination_port"] = 70000
    with pytest.raises(ValueError, match=match):
        events(config)
