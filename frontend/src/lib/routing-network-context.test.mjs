import assert from "node:assert/strict";
import test from "node:test";
import { withPhysicalBindings, interfaceNetworkId, physicalNetworkAliases, physicalNetworkName, assessInterfaceBinding, selectPhysicalBinding, routeEndpointNetworkLabel, routeNetworkLabel } from "./routing-network-context.ts";

const iface = (id, node) => ({ id, hardware_node_id: node, name: node, interface_type: "LIN", configuration: {} });
const port = (id, node, network, name) => ({ id, hardware_node_id: node, technology: "LIN", network_ref: network, name });

test("route network labels resolve saved names even without a bound port and follow renames", () => {
  const id = "network-automotive_ethernet-7537dce901cb";
  const endpoint = Object.freeze({ network_id: id, interface_id: "ecu" });
  const interfaceLabels = new Map([["ecu", "Old channel label"]]);
  const names = new Map([[id, "ETH_Fahrerassistenz_02"]]);
  assert.equal(routeEndpointNetworkLabel(endpoint, interfaceLabels, names), "ETH_Fahrerassistenz_02");
  assert.equal(routeEndpointNetworkLabel(endpoint, new Map(), names), "ETH_Fahrerassistenz_02");
  names.set(id, "ETH_Kamera_03");
  assert.equal(routeEndpointNetworkLabel(endpoint, interfaceLabels, names), "ETH_Kamera_03");
  assert.equal(endpoint.network_id, id);
});

test("route summaries retain exact saved names across networks and deduplicate a shared bus", () => {
  const names = new Map([["N1", "ETH_Fahrerassistenz_02"], ["N2", "ETH_Kameraverarbeitung_01"]]);
  const route = { source: { network_id: "N1" }, destinations: [{ network_id: "N1" }, { network_id: "N2" }] };
  assert.equal(routeNetworkLabel(route, new Map(), names), "ETH_Fahrerassistenz_02 → ETH_Kameraverarbeitung_01");
});

test("unknown explicit identities are not replaced by another bus or a protocol label", () => {
  const labels = new Map([["ecu", "ETH_Kamera_01, ETH_Radar_01"]]);
  assert.equal(routeEndpointNetworkLabel({ interface_id: "ecu" }, labels, new Map()), "ETH_Kamera_01, ETH_Radar_01");
  assert.equal(routeEndpointNetworkLabel({ network_id: "unknown", interface_id: "ecu" }, labels, new Map()), "Unbekanntes Netz (unknown)");
  assert.equal(routeNetworkLabel({ source: { protocol: "ETHERNET" }, destinations: [] }, new Map(), new Map()), "—");
});

test("LIN devices retain their separate canonical networks instead of the first alphabetical device", () => {
  const items = withPhysicalBindings([iface("exhaust", "Abgasnachbehandlung"), iface("suspension", "FrontLeftSuspensionTravel"), iface("oil", "OilTemperature")],
    [{ interface_id: "suspension", hardware_interface_id: "p1", configuration: {} }, { interface_id: "oil", hardware_interface_id: "p2", configuration: {} }],
    [port("p1", "FrontLeftSuspensionTravel", "Chassis-01", "Daempferregelung LIN 01"), port("p2", "OilTemperature", "Powertrain-02", "Motorsteuerung LIN 05")], []);
  const aliases = physicalNetworkAliases(items);
  assert.equal(interfaceNetworkId(items[0]), null);
  assert.equal(interfaceNetworkId(items[1]), "Chassis-01");
  assert.equal(physicalNetworkName(interfaceNetworkId(items[1]), aliases), "Daempferregelung LIN 01");
  assert.equal(physicalNetworkName(interfaceNetworkId(items[2]), aliases), "Motorsteuerung LIN 05");
  assert.equal(aliases.has("network-lin"), false);
  assert.match(physicalNetworkName("unknown", aliases), /Unbekannt/);
});

test("multiple physical channels require an explicit choice and preserve a selected port", () => {
  const [item] = withPhysicalBindings([iface("ecu", "ECU")], [{ interface_id: "ecu", hardware_interface_id: "p1", configuration: { physical_transmit_bindings: [{ hardware_interface_id: "p2" }] } }],
    [port("p1", "ECU", "N1", "LIN 01"), port("p2", "ECU", "N2", "LIN 02")], []);
  assert.equal(interfaceNetworkId(item), null);
  assert.equal(selectPhysicalBinding(item), undefined);
  assert.equal(selectPhysicalBinding(item, "N2", "p2")?.portId, "p2");
  assert.equal(assessInterfaceBinding(item, "ECU", "LIN").compatible, false);
  assert.equal(assessInterfaceBinding(item, "ECU", "LIN", "N2").compatible, true);
  assert.equal(assessInterfaceBinding({ ...item, interface_type: "CAN_FD" }, "ECU", "LIN", "N2").compatible, false);
});

test("a port belonging to another device is not evidence for an interface", () => {
  const [item] = withPhysicalBindings([iface("ecu", "ECU")], [{ interface_id: "ecu", hardware_interface_id: "foreign", configuration: {} }], [port("foreign", "Other", "N1", "Other LIN")], []);
  assert.equal(interfaceNetworkId(item), null);
  assert.equal(assessInterfaceBinding(item, "ECU", "LIN").compatible, false);
});

test("transport capability checks allow CAN frames on CAN-FD but reject LIN", () => {
  const item = { ...iface("i", "ECU"), interface_type: "CAN_FD", physicalBindings: [{ id: "N", portId: "p", name: "CAN 01", protocol: "CAN_FD" }] };
  assert.equal(assessInterfaceBinding(item, "ECU", "CAN", "N").compatible, true);
  assert.equal(assessInterfaceBinding(item, "ECU", "LIN", "N").compatible, false);
});


test("network choices use stored network names even with custom port names and sort alphabetically", () => {
  const [item] = withPhysicalBindings([iface("ecu", "ECU")], [{ interface_id: "ecu", hardware_interface_id: "p1", configuration: { physical_transmit_bindings: [{ hardware_interface_id: "p2" }] } }],
    [port("p1", "ECU", "N1", "Custom uplink"), port("p2", "ECU", "N2", "Different connector")], [],
    [{ id: "N1", name: "ETH_Radar_01" }, { id: "N2", name: "ETH_Kamera_01" }]);
  assert.deepEqual(item.physicalBindings.map(binding => binding.name), ["ETH_Kamera_01", "ETH_Radar_01"]);
  assert.equal(physicalNetworkName("N1", physicalNetworkAliases([item])), "ETH_Radar_01");
});
