import assert from "node:assert/strict";
import test from "node:test";
import { inspectSignal, inspectMessageSignals, buildNetworkInspection } from "./capacity-network-inspection.ts";

const message = { id: "message", name: "Status", dlc: 8, interface_id: "sensor-port" };
const signal = { id: "signal", name: "Value", message_id: "message", start_bit: 0, length_bits: 8,
  data_type: "unsigned", min_value: 0, max_value: 255, factor: 1, offset_value: 0, byte_order: "little_endian", semantic: { semantic_type: "NUMERIC" }, data: { resolution: 1 } };
const codes = (value) => value.checks.map((check) => check.code);

test("64-bit value with an unsigned 0..255 range suggests 8 bits without changing the source", () => {
  const input = { ...signal, length_bits: 64 };
  const result = inspectSignal(input, message);
  assert.equal(result.requiredBits, 8);
  assert.equal(result.status, "WARNING");
  assert.ok(codes(result).includes("OVERSIZED"));
  assert.equal(input.length_bits, 64);
});

test("roll rate -300..300 at 0.01 requires all 16 signed bits", () => {
  const result = inspectSignal({ ...signal, length_bits: 16, data_type: "signed", min_value: -300, max_value: 300, factor: 0.01 }, message);
  assert.equal(result.requiredBits, 16);
  assert.equal(result.status, "PASS");
});

test("too-small signals and unsigned negative raw values are errors", () => {
  assert.ok(codes(inspectSignal({ ...signal, length_bits: 7 }, message)).includes("TOO_NARROW"));
  assert.ok(codes(inspectSignal({ ...signal, min_value: -1 }, message)).includes("UNSIGNED_NEGATIVE"));
});

test("signed boundaries and physical offsets use raw values", () => {
  for (const [min, max, bits] of [[-128, 127, 8], [-128, 128, 9], [-1, 0, 1]]) {
    assert.equal(inspectSignal({ ...signal, min_value: min, max_value: max, data_type: "signed" }, message).requiredBits, bits);
  }
  assert.equal(inspectSignal({ ...signal, min_value: -40, max_value: 215, offset_value: -40 }, message).requiredBits, 8);
  assert.equal(inspectSignal({ ...signal, min_value: -255, max_value: 0, factor: -1 }, message).requiredBits, 8);
});

test("incomplete value domains never assert a smaller encoding", () => {
  for (const values of [{ min_value: null }, { max_value: null }]) {
    const result = inspectSignal({ ...signal, length_bits: 64, ...values }, message);
    assert.equal(result.status, "OPEN");
    assert.equal(result.requiredBits, null);
    assert.ok(!codes(result).includes("OVERSIZED"));
  }
});

test("incomplete numeric encoding remains open while value-domain bit need stays visible", () => {
  for (const values of [{ factor: null }, { offset_value: null }, { min_value: 0, max_value: 0 }]) {
    const result = inspectSignal({ ...signal, length_bits: 64, ...values }, message);
    assert.equal(result.status, "OPEN");
    assert.ok(result.requiredBits !== null);
    assert.ok(!codes(result).includes("OVERSIZED"));
  }
});

test("incomplete parser inputs explain what AI must recover before bit optimization", () => {
  const result = inspectSignal({ ...signal, min_value: null, factor: null, data_type: "" }, message);
  const text = result.checks.map((check) => check.text).join(" ");

  assert.match(text, /Parser\/KI/);
  assert.match(text, /Min\/Max|Wertebereich/);
  assert.match(text, /Skalierung|Datentyp/);
});

test("inspection display names hide technical hardware role suffixes from existing data", () => {
  assert.equal(inspectSignal({ ...signal, name: "MainControllerStatus" }, message).name, "MainStatus");
  assert.equal(inspectSignal({ ...signal, name: "ProcessSensorStatus" }, message).name, "ProcessStatus");
  assert.equal(inspectSignal({ ...signal, name: "ValveActuatorStatus" }, message).name, "ValveStatus");
});

test("legacy uint8 min/max signals need semantic classification before optimization", () => {
  const { semantic, ...legacy } = signal;
  const result = inspectSignal(legacy, message);

  assert.equal(result.requiredBits, null);
  assert.equal(result.status, "OPEN");
  assert.ok(codes(result).includes("SEMANTIC_MISSING"));
});

test("legacy status signals use a conservative state domain instead of open numeric optimization", () => {
  const { semantic, ...legacy } = signal;
  const result = inspectSignal({ ...legacy, name: "ProcessStatus" }, message);
  const text = result.checks.map((check) => check.text).join(" ");

  assert.equal(result.semanticType, "STATE");
  assert.equal(result.requiredBits, 3);
  assert.equal(result.status, "PASS");
  assert.ok(!codes(result).includes("SEMANTIC_MISSING"));
  assert.doesNotMatch(text, /Wertebereich|Skalierung|Datentyp/);
  assert.match(text, /Reservehinweis/);
});

test("zero scale, reversed bounds and unrepresentable endpoints are errors", () => {
  for (const [values, code] of [[{ factor: 0 }, "SCALE_ZERO"], [{ min_value: 10, max_value: 0 }, "RANGE_REVERSED"], [{ min_value: 0, max_value: 1, factor: 0.3 }, "QUANTIZATION"]]) {
    const result = inspectSignal({ ...signal, ...values }, message);
    assert.equal(result.status, "ERROR");
    assert.ok(codes(result).includes(code));
  }
  assert.equal(inspectSignal({ ...signal, max_value: 0.3, factor: 0.1 }, message).requiredBits, 2);
});

test("sentinels participate in bit width and reserved codes block premature optimization", () => {
  const invalid = inspectSignal({ ...signal, length_bits: 8, data: { invalid_value: 256 } }, message);
  assert.equal(invalid.requiredBits, 9);
  assert.equal(invalid.status, "ERROR");
  const reserved = inspectSignal({ ...signal, length_bits: 64, configuration: { reserved_values: [65535] } }, message);
  assert.equal(reserved.status, "OPEN");
  assert.ok(!codes(reserved).includes("OVERSIZED"));
});

test("float precision, wrong numeric datatypes and unsafe integer ranges remain explicitly open", () => {
  for (const values of [{ data_type: "float64", length_bits: 64 }, { data_type: "enum" }, { max_value: 2 ** 64, length_bits: 64 }]) {
    const result = inspectSignal({ ...signal, ...values }, message);
    assert.equal(result.status, "OPEN");
    assert.ok(result.requiredBits === null || result.requiredBits > 0);
  }
  assert.ok(codes(inspectSignal({ ...signal, data_type: "float32", length_bits: 16 }, message)).includes("FLOAT_WIDTH"));
});

test("Intel and Motorola positions detect payload overflow across byte boundaries", () => {
  const motorola = inspectSignal({ ...signal, start_bit: 7, length_bits: 16, byte_order: "big_endian" }, message);
  assert.deepEqual(motorola.occupiedBits, [7, 6, 5, 4, 3, 2, 1, 0, 15, 14, 13, 12, 11, 10, 9, 8]);
  assert.ok(codes(inspectSignal({ ...signal, start_bit: 63, length_bits: 2 }, message)).includes("PAYLOAD_OVERFLOW"));
  assert.ok(codes(inspectSignal({ ...signal, start_bit: 56, length_bits: 2, byte_order: "big_endian" }, message)).includes("PAYLOAD_OVERFLOW"));
});

test("missing placement and missing message are not presented as valid", () => {
  for (const values of [{ start_bit: null }, { length_bits: null }, { byte_order: null }]) assert.equal(inspectSignal({ ...signal, ...values }, message).status, "OPEN");
  assert.equal(inspectSignal(signal).status, "OPEN");
  assert.equal(inspectSignal(signal, { ...message, dlc: null }).status, "OPEN");
});

test("overlapping signals fail on both sides; multiplexed overlap remains unverified", () => {
  const results = inspectMessageSignals([signal, { ...signal, id: "other", start_bit: 4 }], message);
  assert.ok(results.every((item) => item.status === "ERROR" && codes(item).includes("OVERLAP")));
  const mux = inspectMessageSignals([signal, { ...signal, id: "other", configuration: { multiplexer_id: 2 } }], message);
  assert.ok(mux.every((item) => item.status === "OPEN"));
});

function sources() {
  return {
    versions: { engineering_model: 1, routing: 1, network_editor: 1 },
    hardware: [{ id: "sensor", name: "RollRate", device_type: "SensorController" }, { id: "ecu", name: "Stabilitaetsregelung", device_type: "ECU" }, { id: "gateway", name: "Zentrale", device_type: "Gateway" }, { id: "idle", name: "Reserve", device_type: "ECU" }, { id: "other", name: "OtherBus", device_type: "ECU" }],
    interfaces: [{ id: "sensor-port", hardware_node_id: "sensor", name: "Sensor LIN" }, { id: "gateway-port", hardware_node_id: "gateway", name: "Stabilitaets-LIN" }], functions: [], messages: [message], signals: [signal],
    routes: [{ id: "route", source: { node_id: "sensor", interface_id: "sensor-port", network_id: "lin" }, destinations: [{ node_id: "gateway", interface_id: "gateway-port", network_id: "lin" }], payload: { message_id: "message", message_ids: ["message"], signal_ids: ["signal"] } }],
    topology: { nodes: [
      { id: "n1", engineeringId: "sensor", systemOwnerId: "ecu", systemOwnerSource: "inferred", ports: [{ id: "p1", engineeringId: "sensor-port" }] },
      { id: "n2", engineeringId: "gateway", ports: [{ id: "p2", engineeringId: "gateway-port" }, { id: "separate" }] },
      { id: "n3", engineeringId: "idle", ports: [{ id: "p3" }] }, { id: "n4", engineeringId: "other", ports: [{ id: "p4" }] },
    ], edges: [{ id: "e1", source: "n1", sourcePort: "p1", target: "n2", targetPort: "p2" }, { id: "e2", source: "n3", sourcePort: "p3", target: "n2", targetPort: "p2" }, { id: "e3", source: "n4", sourcePort: "p4", target: "n2", targetPort: "separate" }] },
  };
}

test("network participants follow shared ports, but do not merge separate gateway ports", () => {
  const result = buildNetworkInspection("lin", sources());
  assert.deepEqual(result.participants.map((item) => item.id).sort(), ["gateway", "idle", "sensor"]);
  assert.equal(result.participants.find((item) => item.id === "sensor").system.name, "Stabilitaetsregelung");
  assert.equal(result.participants.find((item) => item.id === "sensor").system.basis, "inferred");
  assert.equal(result.counts.senders, 1);
  assert.equal(result.counts.signals, 1);
  assert.equal(result.counts.messages, 1);
  assert.equal(result.messages[0].origin, "RollRate");
});

test("message payload and signal width stay distinct, with duplicate route references counted once", () => {
  const data = sources();
  data.routes.push({ ...data.routes[0], id: "second" });
  data.signals[0] = { ...signal, length_bits: 16, data_type: "signed", min_value: -300, max_value: 300, factor: 0.01 };
  const result = buildNetworkInspection("lin", data);
  assert.equal(result.counts.signals, 1);
  assert.equal(result.messages[0].bytes, 8);
  assert.equal(result.messages[0].occupiedBits, 16);
  assert.equal(result.messages[0].minimumBytes, 2);
  assert.equal(result.signals[0].requiredBits, 16);
});

test("all message signals count toward packing, including those absent from a route's selection", () => {
  const data = sources();
  data.signals.push({ ...signal, id: "additional", start_bit: 48 });
  const result = buildNetworkInspection("lin", data);
  assert.equal(result.counts.signals, 2);
  assert.equal(result.messages[0].minimumBytes, 7);
  assert.equal(result.messages[0].occupiedBits, 16);
});

test("unresolved references and missing ownership remain visible", () => {
  const data = sources();
  data.signals = [];
  delete data.topology.nodes[0].systemOwnerId;
  const result = buildNetworkInspection("lin", data);
  assert.equal(result.counts.signals, 1);
  assert.equal(result.counts.missingSignals, 1);
  assert.ok(result.notices.some((item) => item.includes("signal")));
  assert.equal(result.participants.find((item) => item.id === "sensor").system, null);
  assert.equal(result.messages[0].minimumBytes, null);
});
