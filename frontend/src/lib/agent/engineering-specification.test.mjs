import assert from "node:assert/strict";
test('device connection selection applies only to the named device', () => {
  const task = '2 Aktoren für Ventile, 4 Sensoren für Temperaturen, und ein RaspberryPi';
  const spec = extractEngineeringSpecification(task + '\n- Geräteanschlüsse: {"RaspberryPi":"I2C","Temperatursensor1":"I2C","Ventilaktor1":"GPIO"}', { gateways: 0, ecus: 1, sensors: 4, actuators: 2 }, 'custom', true);
  assert.equal(spec.chains.find(c => c.hardware_name === 'Temperatursensor1').interface_type, 'I2C');
  assert.equal(spec.chains.find(c => c.hardware_name === 'Temperatursensor2').interface_type, 'Other');
  assert.equal(spec.chains.find(c => c.hardware_name === 'Ventilaktor1').interface_type, 'GPIO');
  assert.equal(spec.chains.find(c => c.hardware_name === 'Ventilaktor2').interface_type, 'Other');
});

test('structured device owners distribute endpoints only to confirmed controllers', () => {
  const result = extractEngineeringSpecification(`Controller: Control1
Controller: Control2
Sensor: Temperature1
Sensor: Pressure2
- Gerätezuordnungen: {"Temperature1":"Control1","Pressure2":"Control2"}`);
  const byName = Object.fromEntries(result.chains.map(chain => [chain.hardware_name, chain]));

  assert.equal(byName.Temperature1.configuration.functional_owner, 'Control1');
  assert.equal(byName.Pressure2.configuration.functional_owner, 'Control2');
  assert.equal(byName.Temperature1.configuration.functional_owner_source, 'explicit_user_statement');
  assert.equal(result.chains.some(chain => chain.hardware_name === 'Gerätezuordnungen'), false);
});
test('temperature purpose phrases create the actual sensor inventory', () => {
  for (const sensors of ['4 Sensoren für Temperaturen', '4 Sensoren für Temperatur', '4 Sensoren die Temperatur messen', '4 temperature sensors']) {
    const spec = extractEngineeringSpecification(`2 Aktoren für Ventile, ${sensors}, und ein RaspberryPi`, { gateways: 0, ecus: 1, sensors: 4, actuators: 2 }, 'custom', true);
    assert.equal(spec.chains.filter(c => c.device_type === 'SensorController').length, 4, sensors);
    assert.equal(spec.chains.filter(c => c.device_type === 'ActuatorController').length, 2, sensors);
    assert.ok(spec.chains.some(c => c.hardware_name === 'RaspberryPi'));
  }
});

test('a counted generic controller is inventory scope and never becomes a device named by its count', () => {
  const task = `Ein System besitzt:
- 2 Positionssensoren
- 2 Servoantriebe
- 1 Controller
- 1 Verbindung zu einem übergeordneten System

Die Positionen sollen zyklisch geregelt werden.`;
  const spec = extractEngineeringSpecification(task, {}, 'custom', true);

  assert.equal(spec.targetCounts.ecus, 1);
  assert.equal(spec.chains.filter(chain => isEngineeringControllerDevice(chain.device_type)).length, 1);
  assert.equal(spec.chains.filter(chain => chain.device_type === 'SensorController').length, 2);
  assert.equal(spec.chains.filter(chain => chain.device_type === 'ActuatorController').length, 2);
  assert.ok(!spec.chains.some(chain => chain.hardware_name === '1'));
});

test('S04-B materializes untyped fans and the shared controller without inventing a gateway', () => {
  const task = `Vier Temperatursensoren und drei Lüfter
sollen durch eine gemeinsame Steuerung geregelt werden.

Die Steuerung muss außerdem mit einem übergeordneten Netzwerk verbunden sein.`;
  const spec = extractEngineeringSpecification(task, {}, 'custom', true);

  assert.deepEqual(spec.targetCounts, { sensors: 4, actuators: 3, ecus: 1, gateways: 0, explicit: true });
  assert.deepEqual(
    spec.chains.filter(chain => chain.device_type === 'SensorController').map(chain => chain.hardware_name),
    ['Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3', 'Temperatursensor4'],
  );
  assert.deepEqual(
    spec.chains.filter(chain => chain.device_type === 'ActuatorController').map(chain => chain.hardware_name),
    ['Luefteraktor1', 'Luefteraktor2', 'Luefteraktor3'],
  );
  assert.deepEqual(
    spec.chains.filter(chain => isEngineeringControllerDevice(chain.device_type)).map(chain => chain.hardware_name),
    ['Steuerung'],
  );
  assert.deepEqual(spec.chains.filter(chain => chain.device_type === 'Gateway').map(chain => chain.hardware_name), []);
});

test('S06-A materializes counted PLC controllers and the central edge gateway', () => {
  const task = `3 PLC/Controller
12 Sensoren:
- 4 Temperatur
- 4 Position
- 4 Druck

8 Aktoren:
- 4 Ventile
- 2 Motor Drives
- 2 Linearantriebe

Netzwerke:
- 2 × PROFINET
- 1 × EtherCAT
- 1 × 1-Gbit-Ethernet Backbone

1 zentrales Gateway / Edge Controller

Zyklus:
Motion 2 ms
Position 5 ms
Pressure 20 ms
Temperature 100 ms

Erzeuge Segmentierung, Routing, Process Data, Capacity und Timing.`;
  const spec = extractEngineeringSpecification(task, {}, 'industrial_automation', true);

  assert.deepEqual(spec.targetCounts, { sensors: 12, actuators: 8, ecus: 3, gateways: 1, explicit: true });
  assert.equal(spec.chains.filter(chain => isEngineeringControllerDevice(chain.device_type)).length, 3);
  assert.equal(spec.chains.filter(chain => chain.device_type === 'Gateway').length, 1);
  assert.equal(spec.chains.filter(chain => chain.device_type === 'SensorController').length, 12);
  assert.equal(spec.chains.filter(chain => chain.device_type === 'ActuatorController').length, 8);
  assert.equal(spec.networkArchitecture, 'gateway_ecu_segments');
  assert.deepEqual(spec.communicationSystemCounts, { Ethernet: 1, ProfiNET: 2, EtherCAT: 1 });
});

test('S07-A counts grouped sensors once and keeps communication paths out of the device inventory', () => {
  const task = `1 Robot Controller
1 Edge Computer

8 Sensoren:
- 2 LiDAR
- 2 Kameras
- 2 Encoder
- 1 IMU
- 1 Abstandssensor

6 Aktoren:
- 4 Motor Drives
- 2 Steering Actuators

Kommunikation:
- LiDAR/Kamera: Ethernet / DDS
- Motor Drives: EtherCAT
- IMU/Encoder: CAN-FD
- Edge ↔ Robot Controller: 1-Gbit Ethernet`;
  const spec = extractEngineeringSpecification(task, {}, 'robotics_ros', true);
  assert.equal(spec.chains.filter(chain => chain.device_type === 'SensorController').length, 8);
  assert.equal(spec.chains.filter(chain => chain.device_type === 'ActuatorController').length, 6);
  assert.deepEqual(spec.chains.filter(chain => isEngineeringControllerDevice(chain.device_type)).map(chain => chain.hardware_name), ['Robot', 'Edge Computer']);
  assert.ok(!spec.chains.some(chain => chain.hardware_name.includes('↔')));
  const technologyByName = Object.fromEntries(spec.chains.map(chain => [chain.hardware_name, chain.interface_type]));
  assert.equal(technologyByName.Robot, 'Ethernet');
  assert.equal(technologyByName['Edge Computer'], 'Ethernet');
  assert.equal(technologyByName.LiDAR1, 'Ethernet');
  assert.equal(technologyByName.Kameras1, 'Ethernet');
  assert.equal(technologyByName.Encoder1, 'CAN_FD');
  assert.equal(technologyByName.IMU, 'CAN_FD');
  assert.equal(technologyByName['Motor Drives1'], 'EtherCAT');
  assert.equal(technologyByName['Steering Actuators1'], 'Other');
  const chainByName = Object.fromEntries(spec.chains.map(chain => [chain.hardware_name, chain]));
  assert.deepEqual(
    [chainByName.Kameras1.data_complexity, chainByName.Kameras1.payload_element_type, chainByName.Kameras1.semantic.semantic_type],
    ['IMAGE_STREAM', 'IMAGE', 'BYTE_ARRAY'],
  );
  assert.deepEqual(
    [chainByName.LiDAR1.data_complexity, chainByName.LiDAR1.payload_element_type, chainByName.LiDAR1.semantic.semantic_type],
    ['POINT_CLOUD', 'POINT_CLOUD', 'BYTE_ARRAY'],
  );
  assert.deepEqual(
    [chainByName.IMU.data_complexity, chainByName.IMU.payload_element_type, chainByName.IMU.semantic.semantic_type],
    ['MULTI_VALUE', 'ARRAY', 'BYTE_ARRAY'],
  );
});

test('the engineering wizard applies the architecture inferred from the complete task', () => {
  const source = readFileSync(new URL('../../components/agent-chat-core.tsx', import.meta.url), 'utf8');
  assert.match(source, /setNetworkArchitecture\(extractNetworkArchitectureMode\(taskSource\)\)/);
  assert.doesNotMatch(source, /setNetworkArchitecture\(defaultNetworkArchitectureMode\(equipmentCounts\.gateways\)\)/);
});

test('every scalar wizard measurement has a complete conservative value domain', () => {
  const measurements = ['Temperatur', 'Drehzahl', 'Drehmoment', 'Druck', 'Durchfluss', 'Strom', 'Spannung',
    'Position', 'Winkel', 'Kraft', 'Luftfeuchtigkeit', 'Abstand', 'Beschleunigung'];
  const task = `${measurements.length} Sensoren:\n${measurements.map(name => `- 1 ${name}sensor`).join('\n')}`;
  const spec = extractEngineeringSpecification(task, {}, undefined, true);
  const sensors = spec.chains.filter(chain => chain.device_type === 'SensorController');
  assert.equal(sensors.length, measurements.length);
  assert.ok(sensors.every(chain => Number.isFinite(chain.min_value) && Number.isFinite(chain.max_value)));
  assert.ok(sensors.every(chain => chain.min_value < chain.max_value));
});

test('S20-B recognizes central coupling as the single gateway target', () => {
  const task = `Umfang:
- 100 Sensoren
- 100 Aktoren
- 50 Steuerungs-/Rechenknoten
- 1 zentrale Kopplung
- mehrere leistungsfähige Rechenknoten`;
  const spec = extractEngineeringSpecification(task, {}, undefined, true);
  assert.deepEqual(spec.targetCounts, { sensors: 100, actuators: 100, ecus: 50, gateways: 1, explicit: true });
  assert.equal(spec.chains.filter(chain => chain.device_type === 'Gateway').length, 1);
});
import { readFileSync } from 'node:fs';

test('standard status replaces a generated legacy duplicate and class two has status', () => {
  const base = extractEngineeringSpecification('Motorsteuergerät mit CAN-FD und Signal Motordrehzahl').chains[0];
  const chain = { ...base, hardware_name: 'Smart', signal_name: 'SmartStatus', device_class: 2, device_type: 'SensorController', data: { enum_values: { OK: 0, ERROR: 1 } } };
  const status = expandEngineeringSignalModel([chain]).filter(signal => signal.signal_name === 'SmartStatus');
  assert.equal(status.length, 1);
  assert.deepEqual(status[0].data.enum_values, { OFF: 0, INIT: 1, READY: 2, ACTIVE: 3, DEGRADED: 4, ERROR: 5 });
});
import test from "node:test";
import { reconcileConfirmedGraphDevices } from "./engineering-specification.ts";

test("confirmed graph identities survive unrelated prose templates and preserve role counts", () => {
  const prompt = `- Industrie: Automotive
- Netzwerktechnologien: CAN-FD (can_fd)
- Hardware-Sollwerte: {"gateways":1,"ecus":1,"sensors":1,"actuators":1}
- Systemcluster-Graph: [{"network_id":"can_fd","controllers":[{"ecu":"Motorsteuerung","sensors":["MotorTemperature"],"actuators":["MotorValve"]}]}]
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
Erzeuge ein Netzwerk mit einem Gateway, einer Motorsteuerung, einem Temperatursensor und einem Stellglied.`;
  const spec = extractEngineeringSpecification(prompt);
  const chains = reconcileConfirmedGraphDevices(spec, prompt);
  assert.deepEqual(chains.filter(c => c.device_type !== "Gateway").map(c => c.hardware_name).sort(),
    ["MotorTemperature", "MotorValve", "Motorsteuerung"].sort());
  assert.equal(chains.filter(c => c.device_type === "Gateway").length, 1);
  assert.equal(chains.find(c => c.hardware_name === "MotorValve").configuration.parameter_quality, "GENERIC_ESTIMATE");
  const mapped = applyConfirmedClusterGraph(chains, prompt);
  assert.match(mapped.find(c => c.hardware_name === "MotorTemperature").transport_network_ref, /IO-motorsteuerung/);
});

test("confirmed graph rejects conflicting identities and excess hardware before proposal review", () => {
  const spec = extractEngineeringSpecification("Fahrzeug mit 1 ECU, 1 Sensor und 1 Gateway");
  assert.throws(() => reconcileConfirmedGraphDevices(spec,
    '- Systemcluster-Graph: [{"controllers":[{"ecu":"Drive","sensors":["Drive"]}]}]'), /Mehrdeutige/);
  assert.throws(() => reconcileConfirmedGraphDevices(spec,
    '- Hardware-Sollwerte: {"ecus":1,"sensors":0,"actuators":0,"gateways":1}\n- Systemcluster-Graph: [{"controllers":[{"ecu":"Drive","sensors":["Temp"]}]}]'), /Hardware-Sollwert sensors/);
});

test("confirmed graph may exceed targets declared as minimum scope for system completeness", () => {
  const prompt = `- Hardware-Sollwerte: {"ecus":1,"sensors":1,"actuators":0,"gateways":0}
- Vollstaendigkeitsprinzip: System- und Funktionsvollstaendigkeit hat Vorrang vor den Hardware-Sollwerten; diese sind Mindestumfang, keine Obergrenze.
- Systemcluster-Graph: [{"controllers":[{"ecu":"Fahrerassistenz","sensors":["FrontCamera","RearCamera"]}]}]`;
  const spec = extractEngineeringSpecification(prompt);
  const chains = reconcileConfirmedGraphDevices(spec, prompt);
  assert.deepEqual(
    chains.filter(c => c.device_type === "SensorController").map(c => c.hardware_name).sort(),
    ["FrontCamera", "RearCamera"],
  );
});

import { applyConfirmedClusterGraph, canonicalCommunicationSystem, defaultNetworkArchitectureMode, normalizeHardwareName, engineeringDomainEvidence, expandEngineeringSignalModel, extractCommunicationSystemCounts, extractEngineeringSpecification, extractEngineeringTargetCounts, extractNetworkArchitectureMode, isEngineeringAnalysisWorkRequest, isEngineeringControllerDevice, isEngineeringReviewRequest, isStructuredEngineeringSpecification, packEngineeringChains } from "./engineering-specification.ts";

test("catalog technology identifiers resolve to device connection types", () => {
  assert.equal(canonicalCommunicationSystem("ethercat industrial_automation"), "EtherCAT");
  assert.equal(canonicalCommunicationSystem("generic_can custom"), "CAN");
  assert.equal(canonicalCommunicationSystem("io_link industrial_automation"), "IO_LINK");
});

test('role-first user declarations retain named participants instead of filling their slots from the catalogue', () => {
  const task = 'Erzeuge ein Automotive CAN-FD Netzwerk mit einem Gateway System, den ECUs Motorsteuerung und Anzeige, einem Sensor MotorTemperature und einem Aktor MotorValve. MotorTemperature wird von Motorsteuerung ausgewertet. Motorsteuerung steuert MotorValve. Statuswerte werden an Anzeige und System übermittelt. Prüfe und arbeite bis Data Science & Intelligence.';
  const spec = extractEngineeringSpecification(task, { gateways: 1, ecus: 2, sensors: 1, actuators: 1 }, 'automotive', true);
  assert.deepEqual(spec.chains.map(chain => [chain.hardware_name, chain.device_type]).sort(), [
    ['System', 'Gateway'], ['Motorsteuerung', 'ECU'], ['Anzeige', 'ECU'],
    ['MotorTemperature', 'SensorController'], ['MotorValve', 'ActuatorController'],
  ].sort());
  for (const name of ['MotorTemperature', 'MotorValve']) {
    const endpoint = spec.chains.find(chain => chain.hardware_name === name);
    assert.equal(endpoint.configuration.functional_owner, 'Motorsteuerung');
    assert.equal(endpoint.configuration.functional_owner_source, 'explicit_user_statement');
    assert.equal(endpoint.configuration.bit_length, endpoint.length_bits);
  }
});

test('typed lists support quoted identifiers across industries without consuming following prose as devices', () => {
  const spec = extractEngineeringSpecification('Erzeuge ein Profinet Netzwerk mit der PLC "Room Control", den Sensoren "Room Temp" und humidity, dem Aktor valve. Sensoren werden ausgewertet. Aktoren mit Rückmeldung.', {}, 'building_automation');
  assert.deepEqual(spec.chains.map(chain => [chain.hardware_name, chain.device_type]).sort(), [
    ['Room Control', 'PLC'], ['Room Temp', 'SensorController'], ['humidity', 'SensorController'], ['valve', 'ActuatorController'],
  ].sort());
});

test('the original large wizard specification retains one gateway instead of promoting its tasks to hardware', () => {
  const original = readFileSync(new URL('../../../e2e/fixtures/wizard-large-50-250-250.txt', import.meta.url), 'utf8');
  const spec = extractEngineeringSpecification(original, {}, 'automotive', true);
  assert.deepEqual(spec.chains.filter(chain => chain.device_type === 'Gateway').map(chain => chain.hardware_name), ['System']);
  assert.ok(!spec.chains.some(chain => ['Queueing', 'Timing', 'Load', 'muss', 'Delay', 'Drop'].includes(chain.hardware_name)));
});

test('the confirmed original graph restores coverage signal identities and command encodings after catalogue redistribution', () => {
  const prompt = readFileSync(new URL('../../../e2e/fixtures/wizard-large-50-250-250.txt', import.meta.url), 'utf8');
  const spec = extractEngineeringSpecification(prompt);
  const owners = ['Allradsteuerung', 'Hinterachslenkung', 'Soundsystem'];
  const roles = [
    ['PrimaryFeedback', 'Rueckmeldung', 10, 0.1, 100, '%'],
    ['OperatingState', 'Betriebszustand', 4, 1, 15, 'code'],
    ['PrimaryCommand', 'Stellbefehl', 10, 0.1, 100, '%'],
    ['EnableCommand', 'Freigabebefehl', 1, 1, 1, 'code'],
    ['SafetyCommand', 'Sicherheitsbefehl', 3, 1, 3, 'code'],
  ];
  const missing = new Set(owners.flatMap(owner => roles.map(([role]) => `${owner}${role}`)));
  for (const owner of ['Parkassistenz', 'Reifendruckkontrolle', 'Ultraschallverarbeitung']) missing.add(`${owner}HealthFeedback`);
  // Simulate a changed catalogue/count allocation without changing the reviewed graph.
  spec.chains = spec.chains.filter(chain => !missing.has(chain.hardware_name));
  const restored = reconcileConfirmedGraphDevices(spec, prompt);
  for (const owner of owners) for (const [role, signal, bits, factor, maximum, unit] of roles) {
    const chain = restored.find(item => item.hardware_name === `${owner}${role}`);
    assert.ok(chain, `${owner}${role}`);
    assert.equal(chain.signal_name, `${owner}${signal}`);
    assert.equal(chain.configuration.functional_owner, owner);
    assert.equal(chain.configuration.coverage_role, role);
    assert.equal(chain.configuration.parameter_quality, 'DOMAIN_TEMPLATE');
    assert.deepEqual([chain.length_bits, chain.factor, chain.min_value, chain.max_value, chain.unit, chain.byte_order],
      [bits, factor, 0, maximum, unit, 'little_endian']);
    assert.equal(chain.interface_type, owner === 'Soundsystem' ? 'LIN' : 'CAN_FD');
    if (role.endsWith('Command')) {
      assert.deepEqual(chain.configuration.actuator_command_template.data, { minimum: 0, maximum, resolution: factor });
      assert.equal(chain.configuration.actuator_command_template.length_bits, bits);
      assert.equal(chain.configuration.actuator_command_template.source, 'wizard-generic-actuator-v1');
    }
    if (role === 'EnableCommand') assert.deepEqual(chain.data.enum_values, { FALSE: 0, TRUE: 1 });
    if (role === 'OperatingState') assert.deepEqual(chain.data.enum_values, { OK: 0, WARNING: 1, ERROR: 2, NOT_AVAILABLE: 3 });
  }
  for (const owner of ['Parkassistenz', 'Reifendruckkontrolle', 'Ultraschallverarbeitung']) {
    const chain = restored.find(item => item.hardware_name === `${owner}HealthFeedback`);
    assert.equal(chain.signal_name, `${owner}Zustandsdiagnose`);
    assert.equal(chain.configuration.functional_owner, owner);
  }
});

test('bare gateway capabilities do not declare hardware while explicit names remain supported', () => {
  const capabilities = '- Gateway Queueing\n- Gateway Timing\n- Gateway Load Monitoring\nGateway muss Fehler melden.\n- Gateway Delay\n- Gateway Drop';
  assert.equal(extractEngineeringSpecification(capabilities).chains.length, 0);
  const named = extractEngineeringSpecification('Erzeuge ein Netzwerk.\nGateway namens System\nGateway namens Timing\nGateway: Queueing\nGateway "Load"');
  assert.deepEqual(named.chains.filter(chain => chain.device_type === 'Gateway').map(chain => chain.hardware_name).sort(), ['Load', 'Queueing', 'System', 'Timing']);
});

test("domain evidence detects rail content independently from a conflicting wizard header", () => {
  const evidence = engineeringDomainEvidence(`Industrie: Automotive\nAxleTemperatureSensor\nBogiesensorik\nPantographControl\nWaysideCommunication`);
  assert.equal(evidence.domain, "rail");
  assert.ok(evidence.confidence >= 0.7);
  assert.ok(evidence.markers.length >= 3);
});

test("domain evidence classifies the mobile robot before industrial and automotive transport hints", () => {
  const input = `1 Robot Controller
1 Edge Computer
2 LiDAR und 2 Kameras
LiDAR/Kamera: Ethernet / DDS
Motor Drives: EtherCAT
IMU/Encoder: CAN-FD`;

  const evidence = engineeringDomainEvidence(input);
  const specification = extractEngineeringSpecification(input);

  assert.equal(evidence.domain, "robotics_ros");
  assert.equal(specification.domain, "robotics_ros");
  assert.equal(specification.modelType, "robotics_ros");
});

test("confirmed cluster graph preserves endpoint technology on local controller I/O", () => {
  const base = extractEngineeringSpecification("Rail project with 1 AxleTemperature sensor").chains[0];
  const chains = [{ ...base, hardware_name: "AxleTemperature", interface_type: "LIN", interface_name: "AxleTemperature_LIN" }];
  const prompt = '- Systemcluster-Graph: [{"network_id":"rail-mvb","network_label":"Rail MVB","controllers":[{"ecu":"BogieControl","sensors":["AxleTemperature"],"actuators":[]}]}]';
  const [mapped] = applyConfirmedClusterGraph(chains, prompt);
  assert.equal(mapped.interface_type, "LIN");
  assert.equal(mapped.interface_name, "AxleTemperature_LIN");
  assert.match(mapped.transport_network_ref, /IO-bogiecontrol-lin$/);

  const industrialPrompt = '- Systemcluster-Graph: [{"network_id":"profinet","network_label":"industrial_automation · profinet","controllers":[{"ecu":"SPSLeitsystem","sensors":["AxleTemperature"],"actuators":[]}]}]';
  const [industrial] = applyConfirmedClusterGraph(chains, industrialPrompt);
  assert.equal(industrial.interface_type, "LIN");
  assert.match(industrial.transport_network_ref, /IO-spsleitsystem-lin$/);
});

test("confirmed cluster graph binds only the controller to the selected backbone", () => {
  const base = extractEngineeringSpecification("Motorsteuergerät mit CAN-FD und Signal Motordrehzahl").chains[0];
  const chains = [{ ...base, hardware_name: "Motorsteuerung", device_type: "ECU", interface_type: "LIN" }];
  const prompt = '- Systemcluster-Graph: [{"network_id":"automotive-can_fd","network_label":"CAN FD","bus_name":"Antriebsstrang_01","controllers":[{"ecu":"Motorsteuerung","sensors":[],"actuators":[]}]}]';
  const [mapped] = applyConfirmedClusterGraph(chains, prompt);
  assert.equal(mapped.interface_type, "CAN_FD");
  assert.equal(mapped.transport_network_ref, "Antriebsstrang_01");
});

test("confirmed V4 cluster splits controllers with explicit mixed technologies", () => {
  const prompt = `- Geräteanschlüsse: {"PLC1":"PROFINET","PLC2":"PROFINET","PLC3":"EtherCAT"}
- Systemcluster-Graph: [{"network_id":"ethernet","network_label":"Ethernet","bus_name":"Maschine_Motion-S01","controllers":[{"ecu":"PLC1"},{"ecu":"PLC2"},{"ecu":"PLC3"}]}]`;
  const base = extractEngineeringSpecification(`3 PLC/Controller
Netzwerke:
- 2 × PROFINET
- 1 × EtherCAT
- 1 × 1-Gbit-Ethernet Backbone`, { gateways: 0, ecus: 3, sensors: 0, actuators: 0 }, 'industrial_automation', true);
  const mapped = applyConfirmedClusterGraph(reconcileConfirmedGraphDevices(base, prompt), prompt);
  const controllers = Object.fromEntries(mapped.map((chain) => [chain.hardware_name, chain]));

  assert.equal(controllers.PLC1.interface_type, "ProfiNET");
  assert.equal(controllers.PLC2.interface_type, "ProfiNET");
  assert.equal(controllers.PLC3.interface_type, "EtherCAT");
  assert.equal(controllers.PLC1.transport_network_ref, "Maschine_Motion-S01-profinet");
  assert.equal(controllers.PLC2.transport_network_ref, "Maschine_Motion-S01-profinet");
  assert.equal(controllers.PLC3.transport_network_ref, "Maschine_Motion-S01-ethercat");
});

test("gateway-free main controller preserves an explicit I2C connection", () => {
  const prompt = `- Netzarchitektur-ID: sensor_ecu_actuator
- Hardware-Sollwerte: {"gateways":0,"ecus":1,"sensors":1,"actuators":0}
- Geräteanschlüsse: {"RaspberryPi":"I2C","Druck":"I2C"}
- Systemcluster-Graph: [{"network_id":"can_fd","network_label":"CAN FD","bus_name":"Systemgruppe","controllers":[{"ecu":"RaspberryPi","sensors":["Druck"],"actuators":[]}]}]
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
1 Raspberry Pi und 1 Drucksensor über I2C.`;
  const specification = extractEngineeringSpecification(prompt);
  const mapped = applyConfirmedClusterGraph(reconcileConfirmedGraphDevices(specification, prompt), prompt);
  const controller = mapped.find((chain) => chain.hardware_name === "RaspberryPi");

  assert.equal(specification.networkArchitecture, "sensor_ecu_actuator");
  assert.equal(controller.interface_type, "I2C");
  assert.equal(controller.interface_name, "RaspberryPi_I2C");
  assert.equal(controller.configuration.connection_source, "explicit_device_connection");
  assert.ok(!mapped.some((chain) => chain.hardware_name === "RaspberryPi" && chain.interface_type === "CAN_FD"));
});

test("a review with hardware evidence must never trigger model creation", () => {
  const review = `Bewerte diese Intelligence-Empfehlung als Engineering-Agent.
Empfehlung: 2 LIN-Segmente innerhalb der Systemcluster vorsehen.
Evidence: FondtuerRechts-ECU, MotorCurrentSensor, AirbagActuator, System-Gateway
Messbereich: 0 bis 100; Sollwert: 60%`;
  assert.equal(isEngineeringReviewRequest(review), true);
  assert.equal(isStructuredEngineeringSpecification(review), false);
  assert.equal(isStructuredEngineeringSpecification(`Konkrete Aufgabe des Nutzers:\n${review}`), false);
  assert.equal(isEngineeringReviewRequest("Erstelle ein Fahrzeugnetzwerk aus dem folgenden Muster."), false);
});

test("analysis wording stays actionable instead of read-only review", () => {
  const request = "Analysiere diesen Befund und arbeite an der Lösung.";
  assert.equal(isEngineeringReviewRequest(request), false);
  assert.equal(isEngineeringAnalysisWorkRequest(request), true);
});

const SAMPLE = `
# Musterprojekt - Fahrzeugnetzwerk

## 1. Systemumfang

- **100 Sensoren**
- **50 Funktions-ECUs**
- **1 zentrales Gateway**
- LIN
- CAN-FD
- Automotive Ethernet

## 3. Beispiel Temperatursensor

- Bereich: −20 °C bis +120 °C
- Auflösung: 0,1 °C
- Signal: Temperature
- Verwendung durch eine Thermal-/Klima-ECU

## 11. Zentrales Gateway

Es existiert genau ein zentrales Gateway.

## 12. Routing-Tabelle

- Gateway
- Destination Network
`;

function summarize(result) {
  const counts = result.chains.reduce(
    (current, chain) => {
      current[chain.device_type] = (current[chain.device_type] ?? 0) + 1;
      return current;
    },
    {},
  );
  const temperature = result.chains.find((chain) => chain.hardware_name === "Temperatur");
  return {
    targetCounts: result.targetCounts,
    counts,
    communicationSystems: result.communicationSystems,
    hardwareNames: result.chains.map((chain) => chain.hardware_name),
    temperature: temperature && {
      functionName: temperature.function_name,
      minValue: temperature.min_value,
      maxValue: temperature.max_value,
      dataType: temperature.data_type,
    },
  };
}

test("numbered headings and prose do not create extra hardware", () => {
  const summary = summarize(extractEngineeringSpecification(SAMPLE));
  assert.deepEqual(summary.targetCounts, { sensors: 100, actuators: 0, ecus: 50, gateways: 1, explicit: true });
  assert.deepEqual(summary.counts, { SensorController: 100, ECU: 50, Gateway: 1 });
  assert.deepEqual(summary.communicationSystems, ["LIN", "CAN_FD", "Ethernet"]);
  assert.equal(summary.hardwareNames.includes("Gateway"), false);
  assert.equal(summary.hardwareNames.includes("Verwendung durch eine Thermal-/Klima-ECU"), false);
  assert.equal(summary.hardwareNames.filter((name) => name === "System").length, 1);
  assert.deepEqual(summary.temperature, {
    functionName: "Temperatur_Erfassung",
    minValue: -20,
    maxValue: 120,
    dataType: "signed",
  });
});

test("specification extraction is stable over 25 project-creation passes", () => {
  const expected = summarize(extractEngineeringSpecification(SAMPLE));
  for (let pass = 1; pass <= 25; pass += 1) {
    assert.deepEqual(summarize(extractEngineeringSpecification(SAMPLE)), expected, `pass ${pass}`);
  }
});

test("completeness-first expansion retains every controller referenced by generated endpoints", () => {
  const result = extractEngineeringSpecification(
    "- Generierungsmodus: EXAMPLE_PROJECT\nIndustrie: Automotive\n- Lichtsteuergerät",
    { sensors: 100, actuators: 100, ecus: 50, gateways: 1 },
    "automotive",
    true,
  );
  const controllerNames = new Set(result.chains
    .filter((chain) => !["SensorController", "ActuatorController", "Gateway"].includes(chain.device_type))
    .map((chain) => chain.hardware_name));
  const ownedEndpoints = result.chains.filter((chain) =>
    (chain.device_type === "SensorController" || chain.device_type === "ActuatorController")
    && chain.configuration?.functional_owner);

  assert.equal(controllerNames.has("Licht"), true);
  assert.equal(controllerNames.has("HeadUpDisplay"), true);
  assert.equal(controllerNames.size, 51);
  assert.equal(ownedEndpoints.every((chain) => controllerNames.has(chain.configuration.functional_owner)), true);
});

test("wizard architecture ids are extracted without ambiguity", () => {
  assert.equal(extractNetworkArchitectureMode("- Netzarchitektur-ID: sensor_ecu_actuator"), "sensor_ecu_actuator");
  assert.equal(extractNetworkArchitectureMode("- Netzarchitektur-ID: eva"), "eva");
  assert.equal(extractNetworkArchitectureMode("- Netzarchitektur-ID: ecu_gateway"), "ecu_gateway");
  assert.equal(extractNetworkArchitectureMode("- Netzarchitektur-ID: gateway_ecu_segments"), "gateway_ecu_segments");
  assert.equal(extractNetworkArchitectureMode("- Netzarchitektur-ID: gateway_direct"), "gateway_direct");
  assert.equal(extractNetworkArchitectureMode("- Netzarchitektur-ID: hybrid_ai"), "hybrid_ai");
  assert.equal(extractNetworkArchitectureMode("Variante 0 Sensor ECU Aktor"), "sensor_ecu_actuator");
  assert.equal(extractNetworkArchitectureMode("am Gateway haengen ueber eine Leitung bis zu 6 ECU"), "gateway_ecu_segments");
  assert.equal(extractNetworkArchitectureMode("Kombination aus Variante 2 und 3"), "hybrid_ai");
  assert.equal(extractNetworkArchitectureMode("3 Sensoren, 4 Aktoren und ein Raspberry Pi"), "sensor_ecu_actuator");
  assert.equal(extractNetworkArchitectureMode("3 Sensoren, 4 Aktoren, ein Raspberry Pi und ein Gateway"), "gateway_direct");
  assert.equal(defaultNetworkArchitectureMode(0), "sensor_ecu_actuator");
  assert.equal(defaultNetworkArchitectureMode(1), "gateway_direct");
});

test("wizard variant numbers never become hardware quantities", () => {
  for (const [id, label] of [
    ["sensor_ecu_actuator", "Variante 0 · Sensor-ECU-Aktor"],
    ["eva", "Variante 1 · Einfaches EVA"],
    ["ecu_gateway", "Variante 2 · ECU-vermittelt"],
    ["gateway_ecu_segments", "Variante 4 · Gateway-Segmente"],
    ["gateway_direct", "Variante 3 · Gateway-direkt"],
    ["hybrid_ai", "KI-Kombination · Variante 2 + 3"],
  ]) {
    const wrapped = `Strukturierte Vorgaben fuer den Engineering-Agenten:
- Netzarchitektur-ID: ${id}
- Netzarchitektur: ${label}
- Workflowumfang: Workflow 1 Engineering-Modell; Workflow 2 Routing-Tabelle; Workflow 9 Data Science

Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
${SAMPLE}

Verbindliche Kanonisierung bei der Projektanlage: ADAS und Fahrerassistenz sind Synonyme.

Starte jetzt die Analyse.`;
    const result = extractEngineeringSpecification(wrapped);
    assert.deepEqual(result.targetCounts, { sensors: 100, actuators: 0, ecus: 50, gateways: 1, explicit: true }, label);
    assert.deepEqual(summarize(result), summarize(extractEngineeringSpecification(SAMPLE)), label);
    assert.equal(result.networkArchitecture, id);
    assert.deepEqual(extractEngineeringTargetCounts(wrapped), result.targetCounts);
  }
});

test("quantity matches cannot cross line or variant-label boundaries", () => {
  const text = "Variante 3: Gateway-direkt\nVariante 2: ECU-vermittelt\n3\nGateway / BCM\n- 100 Sensoren\n- 50 Funktions-ECUs\n- 1 zentrales Gateway";
  assert.deepEqual(extractEngineeringTargetCounts(text), { sensors: 100, actuators: 0, ecus: 50, gateways: 1, explicit: true });
});

test("quantity matches support noun-first wizard and file wording", () => {
  const text = [
    "Geräteumfang:",
    "Gateways: 2",
    "ECUs = 47",
    "Sensoren - 95",
    "Aktoren Anzahl 88",
  ].join("\n");

  assert.deepEqual(extractEngineeringTargetCounts(text), { sensors: 95, actuators: 88, ecus: 47, gateways: 2, explicit: true });
});

test("comma-separated count-first hardware quantities stay attached to their nouns", () => {
  const text = "Erzeuge 1 Gateway, 50 Controller, 100 Sensoren und 100 Aktoren mit CAN-FD.";
  assert.deepEqual(extractEngineeringTargetCounts(text), { sensors: 100, actuators: 100, ecus: 50, gateways: 1, explicit: true });
});

test("communication system quantities are extracted from the specification text", () => {
  const text = [
    "Kommunikationssysteme:",
    "CAN FD: 20 Busse",
    "LIN 10",
    "Automotive Ethernet = 5",
    "SOME/IP: 1",
    "500 kbit/s CAN FD als Bitrate",
  ].join("\n");

  assert.deepEqual(extractCommunicationSystemCounts(text), { CAN_FD: 20, LIN: 10, Ethernet: 5, SOME_IP: 1 });
  assert.deepEqual(extractEngineeringSpecification(text).communicationSystemCounts, { CAN_FD: 20, LIN: 10, Ethernet: 5, SOME_IP: 1 });
  assert.equal(extractEngineeringSpecification("SOME/IP 1\n- 1 ECU").interfaceType, "Ethernet");
});

test("neu 9 system scope generates all 100 actuators alongside sensors, ECUs and one gateway", () => {
  const text = SAMPLE.replace("- **100 Sensoren**", "- **100 Sensoren**\n- **100 Aktuatoren**");
  const expected = summarize(extractEngineeringSpecification(text));
  for (let pass = 0; pass < 25; pass += 1) {
    const result = extractEngineeringSpecification(text);
    assert.deepEqual(summarize(result), expected);
    assert.deepEqual(summarize(result).counts, { SensorController: 100, ActuatorController: 100, ECU: 50, Gateway: 1 });
    assert.equal(new Set(result.chains.map((chain) => chain.hardware_name)).size, 251);
    assert.equal(result.chains.some((chain) => /100 Aktuatoren/.test(chain.hardware_name)), false);
    assert.equal(result.networkArchitecture, "gateway_direct");
  }
});

test("sensor templates preserve their domain bus while simple actuators remain on LIN", () => {
  const result = extractEngineeringSpecification(SAMPLE, { sensors: 100, actuators: 100 });
  const basicSensors = result.chains.filter((chain) =>
    chain.device_type === "SensorController"
      && !/camera|kamera|vision|radar|lidar|scanner|ultrasonic/i.test(chain.hardware_name),
  );
  const actuators = result.chains.filter((chain) => chain.device_type === "ActuatorController");

  assert.ok(basicSensors.length > 0);
  assert.ok(actuators.length > 0);
  assert.ok(basicSensors.some((chain) => chain.interface_type === "CAN_FD"));
  assert.ok(basicSensors.some((chain) => chain.interface_type === "LIN"));
  assert.ok(actuators.every((chain) => chain.interface_type === "LIN"));
});

test("gateway-direct generation does not add a central computer beside the system gateway", () => {
  const result = extractEngineeringSpecification(SAMPLE, { actuators: 100 });
  const centralComputerNames = result.chains
    .map((chain) => chain.hardware_name)
    .filter((name) => /zentralrechner/i.test(name));

  assert.deepEqual(centralComputerNames, []);
  assert.equal(result.chains.filter((chain) => chain.device_type === "Gateway").length, 1);
});

test("German and English actuator quantities and named actuators are recognized", () => {
  for (const noun of ["Aktoren", "Aktuatoren", "Actuators"]) {
    assert.equal(extractEngineeringTargetCounts(`- 100 ${noun}`).actuators, 100);
  }
  const result = extractEngineeringSpecification("- Bremsaktuator\n- Fensteraktor\n- DoorActuator");
  assert.equal(result.chains.filter((chain) => chain.device_type === "ActuatorController").length, 3);
});

test("separate industrial and backbone Ethernet segments are both counted", () => {
  const text = [
    "Netzwerke:",
    "- 15 lokale Low-Speed-Segmente: LIN / RS-485 / IO-Link nach Geräteeignung",
    "- 10 CAN-FD-Segmente",
    "- 5 Industrial-Ethernet-Segmente",
    "- 5 Ethernet-Backbone-Segmente",
  ].join("\n");
  const counts = extractCommunicationSystemCounts(text);
  assert.equal(counts.CAN_FD, 10);
  assert.equal(counts.Ethernet, 10);
  assert.equal(counts.IO_LINK, 1);
  assert.equal(counts.RS485, 1);
  assert.equal(counts.LIN, 1);
});

test("counted hardware sections preserve the named S01-A devices", () => {
  const requirement = `1 Raspberry Pi 5
3 Sensoren:
- PT100 über SPI-ADC, -20…150 °C, 0,1 °C, 100 ms
- Drucksensor über I2C, 0…10 bar, 0,01 bar, 20 ms
- Drehzahlsensor über GPIO Counter, 0…6000 rpm, 10 ms

4 Aktoren:
- 2 PWM-Ventile
- 1 DC-Motorcontroller über CAN-FD
- 1 Relaisausgang

CAN-FD:
500 kbit/s nominal
2 Mbit/s data

Funktionen:
TemperatureMonitoring
PressureControl
SpeedControl
SafetyShutdown`;
  const result = extractEngineeringSpecification(requirement);
  const confirmed = extractEngineeringSpecification(`Strukturierte Vorgaben fuer den Engineering-Agenten:
- Hardware-Sollwerte: {"gateways":0,"ecus":1,"sensors":3,"actuators":4}

Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
${requirement}`);

  for (const extracted of [result, confirmed]) {
    assert.deepEqual(
      extracted.chains.filter((chain) => chain.device_type === "SensorController").map((chain) => chain.hardware_name),
      ["PT100", "Druck", "Drehzahl"],
    );
    assert.deepEqual(
      extracted.chains.filter((chain) => chain.device_type === "ActuatorController").map((chain) => chain.hardware_name),
      ["Ventilaktor1", "Ventilaktor2", "DC-Motor", "Relaisausgang"],
    );
    assert.deepEqual(
      Object.fromEntries(extracted.chains.map((chain) => [chain.hardware_name, chain.interface_type])),
      {
        RaspberryPi: "CAN_FD",
        PT100: "SPI",
        Druck: "I2C",
        Drehzahl: "GPIO",
        Ventilaktor1: "PWM",
        Ventilaktor2: "PWM",
        "DC-Motor": "CAN_FD",
        Relaisausgang: "Other",
      },
    );
  }
});

test("counted CANopen position sensors and servo drives expand into typed devices", () => {
  const requirement = `1 Embedded Controller
2 Positionssensoren über CANopen
2 Servoantriebe über CANopen
1 Ethernet-Gateway

CANopen:
500 kbit/s
Sensorzyklus 10 ms
Drive Command 5 ms

Gateway:
CANopen ↔ Ethernet
Ethernet 1 Gbit/s`;
  const result = extractEngineeringSpecification(requirement);
  assert.deepEqual(
    result.chains.filter((chain) => chain.device_type === "SensorController").map((chain) => chain.hardware_name),
    ["Positionssensor1", "Positionssensor2"],
  );
  assert.deepEqual(
    result.chains.filter((chain) => chain.device_type === "ActuatorController").map((chain) => chain.hardware_name),
    ["Servoantrieb1", "Servoantrieb2"],
  );
  assert.ok(result.chains.filter((chain) => /Positionssensor|Servoantrieb/.test(chain.hardware_name)).every((chain) => chain.interface_type === "CAN"));
  assert.equal(result.chains.filter((chain) => chain.device_type === "EmbeddedController").length, 1);
  assert.equal(result.chains.filter((chain) => chain.device_type === "Gateway").length, 1);
});

test("confirmed count corrections take precedence over the original sample, including zero", () => {
  const counts = { sensors: 2, actuators: 3, ecus: 1, gateways: 0 };
  const text = `Strukturierte Vorgaben fuer den Engineering-Agenten:\n- Hardware-Sollwerte: ${JSON.stringify(counts)}\n\nKonkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:\n${SAMPLE}`;
  const result = extractEngineeringSpecification(text);
  assert.deepEqual(result.targetCounts, { ...counts, explicit: true });
  assert.deepEqual(summarize(result).counts, { SensorController: 2, ActuatorController: 3, ECU: 1 });
});

test("corrected quantities can exceed the initial template catalog", () => {
  const result = extractEngineeringSpecification(SAMPLE, { sensors: 110, actuators: 105, ecus: 55, gateways: 2 });
  assert.deepEqual(summarize(result).counts, { SensorController: 110, ActuatorController: 105, ECU: 55, Gateway: 2 });
  assert.equal(new Set(result.chains.map((chain) => chain.hardware_name)).size, 272);
});

test("250 endpoints expand into unique semantic roles instead of numbered clones", () => {
  const result = extractEngineeringSpecification(
    "- Generierungsmodus: EXAMPLE_PROJECT\nIndustrie: Automotive\n- 50 ECUs\n- 250 Sensoren\n- 250 Aktoren\n- 1 Gateway",
    { sensors: 250, actuators: 250, ecus: 50, gateways: 1 },
    "automotive",
    true,
  );
  const endpoints = result.chains.filter((chain) => chain.device_type === "SensorController" || chain.device_type === "ActuatorController");

  assert.equal(endpoints.length, 500);
  assert.equal(new Set(endpoints.map((chain) => chain.hardware_name)).size, 500);
  assert.equal(new Set(endpoints.map((chain) => chain.signal_name)).size, 500);
  assert.equal(endpoints.some((chain) => /[-_]\d+$/.test(chain.hardware_name)), false);
  assert.equal(endpoints.filter((chain) => chain.configuration?.functional_owner).length, 500);
  assert.equal(endpoints.filter((chain) => chain.semantic?.semantic_type === "STATE").every((chain) => chain.length_bits >= 3), true);
  assert.equal(endpoints.filter((chain) => chain.configuration?.coverage_role === "EnableCommand").every((chain) => chain.length_bits === 1), true);
});

test("system completeness supplements an underspecified ADAS low-level scope", () => {
  const result = extractEngineeringSpecification(`
- Generierungsmodus: EXAMPLE_PROJECT
Industrie: Automotive
- Fahrerassistenzsteuergeraet
- Hardware-Sollwerte: {"gateways":0,"ecus":1,"sensors":1,"actuators":0}
- Vollstaendigkeitsprinzip: System- und Funktionsvollstaendigkeit hat Vorrang vor den Hardware-Sollwerten; diese sind Mindestumfang, keine Obergrenze.
  `);
  const hardwareNames = new Set(result.chains.map((chain) => chain.hardware_name));
  const sensorNames = result.chains
    .filter((chain) => chain.device_type === "SensorController")
    .map((chain) => chain.hardware_name);

  assert.deepEqual(result.targetCounts, { sensors: 1, actuators: 0, ecus: 1, gateways: 0, explicit: true });
  for (const required of ["Fahrerassistenz", "Kameraverarbeitung", "Radarverarbeitung", "Ultraschallverarbeitung"]) {
    assert.equal(hardwareNames.has(required), true, required);
  }
  assert.ok(sensorNames.length > result.targetCounts.sensors);
  assert.ok(sensorNames.some((name) => /FrontCamera/i.test(name)));
  assert.ok(sensorNames.some((name) => /RearRadarDistance/i.test(name)));
  assert.equal(sensorNames.filter((name) => /UltrasonicDistance/i.test(name)).length, 4);
});

test("generated system variants follow the selected industry without ECU suffixes", () => {
  const examples = [
    ["Automotive", "automotive", "Kuehlkreislaufsteuerung", "ECU"],
    ["Industrial Automation", "industrial_automation", "SPSLeitsystem", "PLC"],
    ["Embedded Systems", "embedded_systems", "MainControl", "EmbeddedController"],
    ["Aerospace / Defense", "aerospace", "FlightManagement", "FlightComputer"],
    ["Rail", "rail", "TrainControl", "ECU"],
    ["Marine", "marine", "PropulsionControl", "ECU"],
    ["Building Automation", "building_automation", "Gebaeudeleittechnik", "BuildingController"],
    ["Energy", "energy", "Umrichtersteuerung", "EnergyController"],
    ["Robotics / ROS", "robotics_ros", "MotionPlanner", "RobotController"],
    ["Generic Networking", "generic_networking", "CoreSwitch", "IndustrialPC"],
  ];

  for (const [label, domain, expectedName, expectedType] of examples) {
    const result = extractEngineeringSpecification(`- Generierungsmodus: EXAMPLE_PROJECT\nIndustrie: ${label}\n- 3 ECUs\n- 1 Gateway`);
    const controllerNames = result.chains.filter((chain) => chain.device_type === expectedType).map((chain) => chain.hardware_name);

    assert.equal(result.domain, domain, label);
    assert.equal(controllerNames[0], expectedName, label);
    assert.equal(controllerNames.some((name) => /-ECU$/i.test(name)), false, label);
  }
});

test("automotive prose headings do not create generic or synonymous duplicate ECUs", () => {
  const result = extractEngineeringSpecification(`- Generierungsmodus: EXAMPLE_PROJECT
Industrie: Automotive
- 50 Funktions-ECUs
- 1 zentrales Gateway

## 1. Anforderungen
- je Funktion-ECU min 5 und max 20 Signale anlegen

## 9. Beispiel Motion-/Antriebs-ECU
- Motorsteuergeraet
- Getriebesteuergeraet
- Lenkungssteuergeraet
- Fahrwerksteuergeraet
- Klimasteuergeraet
`);
  const ecuNames = result.chains
    .filter((chain) => chain.device_type === "ECU")
    .map((chain) => chain.hardware_name);

  assert.equal(ecuNames.length, 50);
  assert.equal(new Set(ecuNames.map((name) => name.toLowerCase())).size, 50);
  assert.equal(ecuNames.filter((name) => name === "Motorsteuerung").length, 1);
  assert.equal(ecuNames.filter((name) => name === "Getriebesteuerung").length, 1);
  assert.equal(ecuNames.filter((name) => name === "Lenkung").length, 1);
  assert.equal(ecuNames.filter((name) => name === "Fahrwerk").length, 1);
  assert.equal(ecuNames.filter((name) => name === "Klimatisierung").length, 1);
  for (const invalid of ["Funktion", "Motion", "Antriebs", "Motor", "Getriebe", "Lenkungs", "Klima", "Thermal", "Fahrdynamik"]) {
    assert.equal(ecuNames.includes(invalid), false, invalid);
  }
});

test("generated sensor names and buses stay industry specific", () => {
  const industrial = extractEngineeringSpecification("- Generierungsmodus: EXAMPLE_PROJECT\nIndustrie: Industrial Automation\n- 2 Sensoren\n- 1 ECU");
  const embedded = extractEngineeringSpecification("- Generierungsmodus: EXAMPLE_PROJECT\nIndustrie: Embedded Systems\n- 2 Sensoren\n- 1 ECU");

  assert.deepEqual(
    industrial.chains.filter((chain) => chain.device_type === "SensorController").map((chain) => chain.hardware_name),
    ["MotorCurrent", "AxisPosition"],
  );
  assert.deepEqual(
    embedded.chains.filter((chain) => chain.device_type === "SensorController").map((chain) => chain.interface_type),
    ["I2C", "I2C"],
  );
  assert.equal(industrial.chains.some((chain) => /^FrontLeftWheel/.test(chain.hardware_name)), false);
});

test("hardware roles are properties, not name suffixes; instance numbers stay stable", () => {
  for (const [raw, clean] of [["Airbag-ECU", "Airbag"], ["Airbagsteuergerät", "Airbag"], ["Airbag-Steuergeraet-2", "Airbag-2"], ["AcceleratorPositionSensor", "AcceleratorPosition"], ["BrakeActuator", "Brake"], ["BremsAktuator", "Brems"], ["Airbag-ECU-2", "Airbag-2"], ["Sensor", "Sensor"]]) {
    assert.equal(normalizeHardwareName(raw), clean);
  }
  const result = extractEngineeringSpecification(SAMPLE, { actuators: 100 });
  assert.equal(result.chains.some((chain) => /(?:-ECU|Sensor|Actuator|Aktuator)$/.test(chain.hardware_name)), false);
  assert.equal(new Set(result.chains.map((chain) => chain.hardware_name)).size, result.chains.length);
  assert.equal(result.chains.filter((chain) => chain.device_type === "ActuatorController").length, 100);
  assert.equal(result.chains.filter((chain) => chain.device_type === "ECU").length, 50);
  assert.equal(new Set(result.chains.filter((chain) => chain.device_type === "ECU").map((chain) => chain.hardware_name)).size, 50);
});

test("derived user-facing names use the normalized hardware name", () => {
  const result = extractEngineeringSpecification(`
    Airbagsteuergerät
    - Kommunikationsprotokoll: LIN
    - Wertebereich: 0..1
  `);
  const chain = result.chains.find((item) => item.hardware_name === "Airbag");

  assert.ok(chain);
  assert.equal(chain.device_type, "ECU");
  assert.equal(chain.function_name, "Airbag");
  assert.equal(chain.interface_name, "Airbag");
  assert.equal(chain.message_name, "Airbag");
  assert.equal(chain.signal_name, "AirbagStatus");
  assert.equal(chain.signal_display_name, "AirbagStatus");
  assert.equal([chain.hardware_name, chain.function_name, chain.interface_name, chain.message_name, chain.signal_name].some((value) => /steuerger(?:ä|ae|a|�)t/i.test(value)), false);
});

test("new-project generator sizes signal bits and message DLC from physical range", () => {
  const result = extractEngineeringSpecification(SAMPLE, { actuators: 2 });
  const temperature = result.chains.find((chain) => chain.hardware_name === "Temperatur");
  const gateway = result.chains.find((chain) => chain.device_type === "Gateway");
  const binaryActuator = result.chains.find((chain) => chain.signal_name.endsWith("SchaltausgangStatus"));

  assert.equal(temperature?.length_bits, 12);
  assert.equal(temperature?.dlc, 2);
  assert.equal(gateway?.length_bits, 8);
  assert.equal(gateway?.dlc, 1);
  assert.equal(binaryActuator?.length_bits, 1);
  assert.equal(binaryActuator?.dlc, 1);
});

test("recognized physical sensors receive complete conservative defaults when the prompt omits them", () => {
  const result = extractEngineeringSpecification("TemperaturSensor\nDruckSensor\n- Kommunikationsprotokoll: LIN");
  const temperature = result.chains.find((chain) => chain.signal_name === "Temperatur");
  const pressure = result.chains.find((chain) => chain.signal_name === "Druck");

  assert.ok(temperature);
  assert.equal(temperature.min_value, -40);
  assert.equal(temperature.max_value, 215);
  assert.equal(temperature.factor, 0.1);
  assert.equal(temperature.unit, "degC");
  assert.equal(temperature.quality.value_domain_complete, true);
  assert.ok(pressure);
  assert.equal(pressure.min_value, 0);
  assert.equal(pressure.max_value, 250);
  assert.equal(pressure.unit, "bar");
  assert.equal(pressure.semantic.semantic_type, "NUMERIC");
});

test("confirmed single-bus and explicit example projects inherit their project technology", () => {
  const confirmed = extractEngineeringSpecification(`- Industrie: Embedded Systems
- Netzwerktechnologien: ADC (adc)
- Hardware-Sollwerte: {"gateways":0,"ecus":1,"sensors":1,"actuators":1}
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
ein Raspberry Pi, ein Temperatursensor und ein Ventilaktor`);
  assert.ok(confirmed.chains.length >= 3);
  assert.ok(confirmed.chains.every((chain) => chain.interface_type === "ADC"));

  const example = extractEngineeringSpecification(`Beispielprojekt mit CAN-FD und Ethernet
- Temperatursensor
- Ventilaktor`);
  assert.ok(example.chains.length >= 2);
  assert.ok(example.chains.every((chain) => chain.interface_type !== "Other"));
});

test("decimal commas in the original large request never become integer resolutions", () => {
  const prompt = readFileSync(new URL('../../../e2e/fixtures/wizard-large-50-250-250.txt', import.meta.url), 'utf8');
  const current = extractEngineeringSpecification(prompt).chains.find(chain => chain.hardware_name === 'Strom');
  assert.ok(current);
  assert.equal(current.factor, 0.1);
  assert.equal(current.length_bits, 8);
});

test("direct prose creation request extracts front camera engineering chain", () => {
  const result = extractEngineeringSpecification(
    "lege ein Hardware konten an. Frontkamera mit der Funktion umfelderfassung mit Schnittstellen die notwendigen Signale sollen Objekte wie Bälle erkennen lönnen",
  );

  assert.equal(result.chains.length, 1);
  assert.equal(result.chains[0].hardware_name, "Frontkamera");
  assert.equal(result.chains[0].device_type, "SensorController");
  assert.equal(result.chains[0].domain, "automotive");
  assert.equal(result.chains[0].function_name, "Frontkamera_Umfelderfassung");
  assert.equal(result.chains[0].interface_type, "Other");
  assert.equal(result.chains[0].interface_name, "Frontkamera");
  assert.equal(result.chains[0].message_name, "Frontkamera Umfelderfassung");
  assert.equal(result.chains[0].signal_name, "ObjektErkannt");
  assert.equal(result.chains[0].length_bits, 1);
  assert.equal(result.chains[0].dlc, 1);
  assert.equal(result.chains[0].semantic?.semantic_type, "BOOLEAN");
});

test("packing reuses one interface and one message for compatible producer signals", () => {
  const base = extractEngineeringSpecification("Motorsteuergerät mit Signal Motordrehzahl");
  const template = base.chains[0];
  const packed = packEngineeringChains([
    { ...template, signal_name: "MotorRpm", signal_display_name: "MotorRpm", length_bits: 16 },
    { ...template, signal_name: "MotorTorque", signal_display_name: "MotorTorque", length_bits: 16 },
    { ...template, signal_name: "MotorCurrent", signal_display_name: "MotorCurrent", length_bits: 16 },
  ]);

  assert.equal(new Set(packed.map((chain) => chain.interface_name)).size, 1);
  assert.equal(new Set(packed.map((chain) => chain.message_name)).size, 1);
  assert.deepEqual(packed.map((chain) => chain.start_bit).sort((a, b) => a - b), [0, 16, 32]);
  assert.equal(packed[0].dlc, 6);
  assert.equal(packed[0].configuration?.payload_used_bits, 48);
  assert.equal(packed[0].configuration?.payload_capacity_bits, 48);
});

test("intelligent devices receive a complete five-signal minimum model before packing", () => {
  const base = extractEngineeringSpecification("Motorsteuergerät mit CAN-FD und Signal Motordrehzahl").chains[0];
  const expanded = expandEngineeringSignalModel([base]);
  const packed = packEngineeringChains(expanded);

  assert.equal(expanded.length, 5);
  assert.equal(new Set(expanded.map((chain) => chain.signal_name)).size, 5);
  assert.equal(new Set(packed.map((chain) => chain.message_name)).size, 1);
  assert.deepEqual(packed.map((chain) => chain.start_bit).sort((a, b) => a - b), [0, 4, 7, 11, 19]);
});

test("CAN-FD packing uses valid payload classes and splits atomically beyond one frame", () => {
  const base = extractEngineeringSpecification("Fahrwerksteuergerät mit CAN-FD und Signal Federweg");
  const template = { ...base.chains[0], interface_type: "CAN_FD", cycle_ms: 10 };
  const packed = packEngineeringChains([
    { ...template, signal_name: "BlobA", signal_display_name: "BlobA", length_bits: 392 },
    { ...template, signal_name: "BlobB", signal_display_name: "BlobB", length_bits: 120 },
    { ...template, signal_name: "BlobC", signal_display_name: "BlobC", length_bits: 8 },
  ]);
  const messageNames = new Set(packed.map((chain) => chain.message_name));

  assert.equal(messageNames.size, 2);
  assert.ok(packed.every((chain) => [1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64].includes(chain.dlc)));
  assert.equal(packed.find((chain) => chain.signal_name === "BlobA")?.dlc, 64);
  assert.equal(packed.find((chain) => chain.signal_name === "BlobB")?.start_bit, 392);
  assert.equal(packed.find((chain) => chain.signal_name === "BlobC")?.start_bit, 0);
});

test("direct lowercase camera creation request is still actionable", () => {
  const result = extractEngineeringSpecification("frontkamera anlegen mit funktion umfelderfassung und signal objekt erkannt");

  assert.equal(result.chains.length, 1);
  assert.equal(result.chains[0].hardware_name, "frontkamera");
  assert.equal(result.chains[0].function_name, "Frontkamera_Umfelderfassung");
});

test("wizard preserves the explicit project model type independently from the display label", () => {
  const result = extractEngineeringSpecification(`Strukturierte Vorgaben fuer den Engineering-Agenten:
- Industrie: Industrial Automation / SPS
- Projekt-Modelltyp: industrial_automation
- Hardware-Sollwerte: {"gateways":0,"ecus":1,"sensors":1,"actuators":0}
Konkrete Aufgabe des Nutzers:
PLC TemperatureControl mit PROFINET und Temperatursensor.`);

  assert.equal(result.modelType, "industrial_automation");
  assert.equal(result.domain, "industrial_automation");
  assert.equal(result.chains.filter((chain) => chain.device_type === "PLC").length, 1);
  assert.equal(result.chains.some((chain) => chain.device_type === "ECU"), false);
  assert.equal(result.chains.find((chain) => chain.device_type === "PLC")?.interface_type, "ProfiNET");
});

test("explicit model types select their native controller classes", () => {
  const examples = [
    ["process_industry", "PLC"],
    ["robotics_ros", "RobotController"],
    ["aerospace", "FlightComputer"],
    ["building_automation", "BuildingController"],
    ["energy", "EnergyController"],
    ["embedded_systems", "EmbeddedController"],
    ["iot_wireless", "EmbeddedController"],
    ["generic_networking", "IndustrialPC"],
    ["custom", "IndustrialPC"],
  ];
  for (const [modelType, expectedType] of examples) {
    const result = extractEngineeringSpecification(`- Generierungsmodus: EXAMPLE_PROJECT\n- Projekt-Modelltyp: ${modelType}\n- Hardware-Sollwerte: {"gateways":0,"ecus":1,"sensors":0,"actuators":0}`);
    assert.equal(result.domain, modelType);
    assert.equal(result.chains.length, 1);
    assert.equal(result.chains[0].device_type, expectedType, modelType);
  }
});


test("planning limit keys never select a different communication technology", () => {
  const prompt = "SPS mit Temperaturmessung über PROFINET.";
  const metadata = '\n- Bus-Teilnehmergrenzen: {"lin":128,"can_fd":64,"automotive_ethernet":256}\n';
  const before = extractEngineeringSpecification(prompt);
  const after = extractEngineeringSpecification(prompt + metadata);
  assert.deepEqual(after, before);
  assert.deepEqual(after.communicationSystems ?? after.communication_systems, before.communicationSystems ?? before.communication_systems);
});


test("companion domains do not inherit percentage, boolean or state metadata", () => {
  const base = extractEngineeringSpecification("Motorsteuergeraet mit CAN-FD und Signal Motordrehzahl").chains[0];
  const signals = expandEngineeringSignalModel([{ ...base, device_class: 3, hardware_name: "Motor",
    data: { enum_values: { OK: 0, ERROR: 1 }, resolution: 1, invalid_values: [15] } }]);
  const quality = signals.find(s => s.signal_name === "MotorQuality");
  const counter = signals.find(s => s.signal_name === "MotorAliveCounter");
  assert.deepEqual(quality.data.enum_values, {});
  assert.equal(quality.data.resolution, .5);
  assert.deepEqual(quality.data.invalid_values, []);
  assert.deepEqual(counter.data.enum_values, {});
  assert.equal(counter.data.maximum, 15);
  assert.equal(counter.configuration.bit_length, 4);
});


test("hosted output templates preserve hosts, explicit signals and separate editable messages", async () => {
  const { addAutomotiveFunctionOutputs } = await import("./engineering-specification.ts");
  const spec = extractEngineeringSpecification("Beispielprojekt: Automotive Fahrzeug mit 50 ECUs und 1 Gateway");
  const enriched = addAutomotiveFunctionOutputs(spec.chains, spec.domain);
  assert.equal(new Set(enriched.map(c => c.hardware_name)).size, new Set(spec.chains.map(c => c.hardware_name)).size);
  assert.deepEqual(enriched.slice(0, spec.chains.length), spec.chains);
  const outputs = enriched.filter(c => c.configuration?.functional_output_template);
  assert.ok(outputs.length >= 15);
  assert.equal(new Set(outputs.map(c => c.message_name)).size, outputs.length);
  assert.equal(new Set(enriched.map(c => c.message_id_hex)).size, new Set(spec.chains.map(c => c.message_id_hex)).size + outputs.length);
  assert.deepEqual(addAutomotiveFunctionOutputs(enriched, spec.domain), enriched);
  assert.deepEqual(addAutomotiveFunctionOutputs(spec.chains, "rail"), spec.chains);
});

test("standalone PLC and IO-Link sensor groups remain concrete wizard hardware", () => {
  const result = extractEngineeringSpecification(`1 PLC
2 IO-Link-Sensoren:
- Durchfluss 0–100 l/min, 20 ms
- Druck 0–16 bar, 20 ms

2 Aktoren:
- Frequenzumrichter über PROFINET
- Magnetventil über digitales Remote-I/O

PROFINET:
100 Mbit/s

Funktionen:
FlowControl
PressureLimit
PumpCommand`);

  assert.equal(result.chains.filter((chain) => chain.device_type === "PLC").length, 1);
  assert.equal(result.chains.filter((chain) => chain.device_type === "SensorController").length, 2);
  assert.equal(result.chains.filter((chain) => chain.device_type === "ActuatorController").length, 2);
});

test("S05-A materializes explicit safety devices with FSoE semantics and the safety cycle", () => {
  const result = extractEngineeringSpecification(`1 Safety Controller
3 digitale Sicherheitssensoren
2 Safety-Aktoren
1 Gateway

Kommunikation:
EtherCAT / FSoE

Safety Cycle:
4 ms

Funktionen:
SafetyInputMonitor
SafetyDecision
SafeStop`);

  assert.deepEqual(result.targetCounts, { ecus: 1, sensors: 3, actuators: 2, gateways: 1, explicit: true });
  assert.equal(result.chains.filter(chain => chain.device_type === "ECU").length, 1);
  assert.equal(result.chains.filter(chain => chain.device_type === "SensorController").length, 3);
  assert.equal(result.chains.filter(chain => chain.device_type === "ActuatorController").length, 2);
  assert.equal(result.chains.filter(chain => chain.device_type === "Gateway").length, 1);
  assert.ok(result.chains.every(chain => chain.interface_type === "EtherCAT"));
  assert.ok(result.chains.every(chain => chain.cycle_ms === 4));
  assert.ok(result.chains.every(chain => chain.configuration?.safety_profile === "FSoE"));
  assert.ok(result.chains.filter(chain => chain.device_type === "SensorController")
    .every(chain => chain.configuration?.sensor_measurement === "safety_state"));
  assert.ok(result.chains.filter(chain => chain.device_type === "ActuatorController")
    .every(chain => chain.configuration?.actuator_command_template?.source === "wizard-safety-actuator-v1"));
  assert.ok(result.chains.filter(chain => chain.device_type === "ActuatorController")
    .every(chain => chain.min_value === 0 && chain.max_value === 1 && chain.unit === "code"));
  assert.ok(result.chains.filter(chain => chain.device_type === "ActuatorController")
    .every(chain => chain.configuration?.actuator_command_template?.data?.default_value === "RUN"));
});

test("S05-B materializes semantic safety inventory without inventing a transport", () => {
  const task = `Ein Sicherheitssystem besitzt:
- 3 Sicherheitssensoren
- 2 sicherheitsrelevante Aktoren
- 1 Sicherheitssteuerung
- 1 übergeordnete Kommunikationsanbindung

Die Reaktionszeit muss kurz und deterministisch sein.`;
  const result = extractEngineeringSpecification(task);

  assert.deepEqual(result.targetCounts, { ecus: 1, sensors: 3, actuators: 2, gateways: 1, explicit: true });
  assert.equal(result.domain, "industrial_automation");
  assert.equal(result.networkArchitecture, "gateway_direct");
  assert.deepEqual(
    result.chains.map(chain => [chain.hardware_name, chain.device_type]).sort(),
    [
      ["Sicherheitssensor1", "SensorController"],
      ["Sicherheitssensor2", "SensorController"],
      ["Sicherheitssensor3", "SensorController"],
      ["SafetyAktor1", "ActuatorController"],
      ["SafetyAktor2", "ActuatorController"],
      ["Sicherheitssteuerung", "ECU"],
      ["System", "Gateway"],
    ].sort(),
  );
  assert.ok(result.chains.every(chain => chain.interface_type === "Other"));
  assert.ok(result.chains.filter(chain => chain.device_type === "SensorController")
    .every(chain => chain.configuration?.sensor_measurement === "safety_state"));
  assert.ok(result.chains.filter(chain => chain.device_type === "ActuatorController")
    .every(chain => chain.configuration?.actuator_command_template?.data?.default_value === "RUN"));
});

test("industry generation dispatcher isolates optional automotive enrichment", async () => {
  const { applyIndustryGenerationPath } = await import("./engineering-specification.ts");
  const automotive = extractEngineeringSpecification("Beispielprojekt: Automotive Fahrzeug mit 12 ECUs und 1 Gateway");
  const automotiveResult = applyIndustryGenerationPath(automotive.chains, automotive.domain);
  assert.ok(automotiveResult.some(chain => chain.configuration?.functional_output_template));

  for (const domain of ["industrial_automation", "robotics_ros", "aerospace", "rail", "marine", "building_automation", "energy", "embedded_systems", "generic_networking"]) {
    const specification = extractEngineeringSpecification(`- Generierungsmodus: EXAMPLE_PROJECT\n- Projekt-Modelltyp: ${domain}\n- Hardware-Sollwerte: {"gateways":1,"ecus":2,"sensors":1,"actuators":1}`);
    const result = applyIndustryGenerationPath(specification.chains, domain);
    assert.deepEqual(result, specification.chains, domain);
    assert.equal(result.some(chain => chain.configuration?.functional_output_template), false, domain);
  }
});
