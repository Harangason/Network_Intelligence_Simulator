import fs from "node:fs/promises";
import path from "node:path";
import { extractEngineeringSpecification } from "../frontend/src/lib/agent/engineering-specification.ts";

const BASE_URL = (process.env.ENGINEERING_QA_API_URL ?? "http://127.0.0.1:15050/api/engineering").replace(/\/$/, "");
const RUNS = Number(process.env.NEUANLAGE_RUNS ?? "50");
const CHAIN_CONCURRENCY = Number(process.env.NEUANLAGE_CHAIN_CONCURRENCY ?? "8");
const SAMPLE_PATH = process.argv[2] ?? "I:/PycharmProjects/neu 9.txt";
const BATCH_ID = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
const REPORT_DIR = path.resolve(process.cwd(), "reports");
const REPORT_PATH = path.join(REPORT_DIR, `neuanlage-quality-50x-${BATCH_ID}.json`);

const EXPECTED = {
  gateways: 1,
  ecus: 50,
  sensors: 100,
  actuators: 100,
};

function expectedTotal(expected = EXPECTED) {
  return expected.gateways + expected.ecus + expected.sensors + expected.actuators;
}

function normalizeRole(deviceType) {
  if (deviceType === "Gateway") return "gateways";
  if (deviceType === "ECU") return "ecus";
  if (deviceType === "SensorController") return "sensors";
  if (deviceType === "ActuatorController") return "actuators";
  return "unknown";
}

function createVariant(sample, index) {
  const sensorPhrases = [
    "100 Sensoren",
    "100 fahrzeugrelevante Sensoren",
    "100 technische Sensoren",
    "100 logische Sensors",
  ];
  const actuatorPhrases = [
    "100 Aktuatoren",
    "100 Aktoren",
    "100 einfache Aktuatoren",
    "100 technische Actuators",
  ];
  const ecuPhrases = [
    "50 Funktions-ECUs",
    "50 Funktions ECUs",
    "50 typische ECUs",
    "50 weitere ECUs",
  ];
  const gatewayPhrases = [
    "1 zentrales Gateway",
    "ein zentrales Gateway",
    "1 zentraler Gateway",
    "1 einziges Gateway",
  ];
  const architectureNotes = [
    "Netzarchitektur: Variante 3 Gateway-direkt. Sensoren, ECUs und Aktoren erhalten direkte Gateway-/BCM-Anbindungen.",
    "Netzarchitektur: Variante 2 ECU-vermittelt. Sensoren und Aktoren haengen an ECUs, ECUs sprechen mit Gateway / BCM.",
    "Netzarchitektur: KI-Kombination Variante 2 + 3. Kritische Systeme direkt, lokale Systeme ECU-vermittelt.",
    "Netzarchitektur: Einfaches EVA-Modell als Kontrollvariante mit klaren Eingabe-, Verarbeitung- und Ausgabegruppen.",
  ];

  return sample
    .replace(/\*\*100 Sensoren\*\*/g, `**${sensorPhrases[index % sensorPhrases.length]}**`)
    .replace(/\*\*100 Aktuatoren\*\*/g, `**${actuatorPhrases[index % actuatorPhrases.length]}**`)
    .replace(/\*\*50 Funktions-ECUs\*\*/g, `**${ecuPhrases[index % ecuPhrases.length]}**`)
    .replace(/\*\*1 zentrales Gateway\*\*/g, `**${gatewayPhrases[index % gatewayPhrases.length]}**`)
    .concat(`\n\nQA-Variation ${index + 1}: ${architectureNotes[index % architectureNotes.length]}\n`);
}

function percentDeviation(actual, expected) {
  const totalDelta =
    Math.abs(actual.gateways - expected.gateways) +
    Math.abs(actual.ecus - expected.ecus) +
    Math.abs(actual.sensors - expected.sensors) +
    Math.abs(actual.actuators - expected.actuators);
  return Number(((totalDelta / expectedTotal(expected)) * 100).toFixed(4));
}

function ensureNoRoleSuffix(name) {
  return !/(?:[-_\s]?(?:ECU|Gateway|Sensor|Actuator|Aktuator|Aktor|Controller|Steuerger(?:ä|ae|a|�)t))$/i.test(name);
}

function wizardChecks(spec, variant, index) {
  const extractedCounts = { gateways: 0, ecus: 0, sensors: 0, actuators: 0 };
  for (const chain of spec.chains) {
    const role = normalizeRole(chain.device_type);
    if (role in extractedCounts) extractedCounts[role] += 1;
  }
  const hardwareNames = spec.chains.map((chain) => chain.hardware_name);
  const duplicateNames = hardwareNames.filter((name, position) => hardwareNames.indexOf(name) !== position);
  const suffixViolations = hardwareNames.filter((name) => !ensureNoRoleSuffix(name));
  const countDeviation = percentDeviation(extractedCounts, EXPECTED);
  const requiredSystems = ["LIN", "CAN_FD", "Ethernet"];
  const missingCommunicationSystems = requiredSystems.filter((system) => !spec.communicationSystems.includes(system));
  const incompleteChains = spec.chains.filter((chain) => !(
    chain.hardware_name
    && chain.function_name
    && chain.interface_name
    && chain.message_name
    && chain.signal_name
    && Number.isFinite(chain.length_bits)
    && chain.length_bits >= 1
    && chain.length_bits <= 64
    && Number.isFinite(chain.dlc)
    && chain.dlc >= Math.ceil(chain.length_bits / 8)
  ));
  const pass =
    countDeviation <= 2.5
    && duplicateNames.length === 0
    && suffixViolations.length === 0
    && missingCommunicationSystems.length === 0
    && incompleteChains.length === 0
    && Boolean(spec.networkArchitecture);
  return {
    pass,
    run: index + 1,
    target_counts: spec.targetCounts,
    extracted_counts: extractedCounts,
    count_deviation_percent: countDeviation,
    communication_systems: spec.communicationSystems,
    network_architecture: spec.networkArchitecture,
    variant_chars: variant.length,
    issues: [
      ...duplicateNames.map((name) => ({ type: "wizard_duplicate_hardware_name", name })),
      ...suffixViolations.map((name) => ({ type: "wizard_role_suffix_in_hardware_name", name })),
      ...missingCommunicationSystems.map((system) => ({ type: "wizard_missing_communication_system", system })),
      ...incompleteChains.slice(0, 10).map((chain) => ({ type: "wizard_incomplete_chain_or_signal_size", hardware_name: chain.hardware_name })),
      ...(countDeviation > 2.5 ? [{ type: "wizard_count_deviation", deviation: countDeviation }] : []),
    ],
  };
}

async function api(projectId, method, endpoint, body) {
  const url = `${BASE_URL}${endpoint}`;
  let response;
  try {
    response = await fetch(url, {
      method,
      headers: {
        "Content-Type": "application/json",
        "X-Project-ID": projectId,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    const cause = error?.cause ? ` cause=${error.cause.code ?? error.cause.message ?? error.cause}` : "";
    throw new Error(`${method} ${endpoint} fetch failed:${cause}`);
  }
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(`${method} ${endpoint} failed ${response.status}: ${text}`);
  }
  return data;
}

function objectPayload(type, data) {
  return {
    ...data,
    source: "manual",
    provenance: {
      source: "neuanlage-50x-qa",
      generated_by: "stress-neuanlage-50x",
    },
    review_state: "reviewed",
    approval_state: "pending",
    created_by: "qa-stress-neuanlage",
  };
}

async function createChain(projectId, chain, sequence) {
  const hardware = await api(projectId, "POST", "/hardware-nodes", objectPayload("hardware", {
    name: chain.hardware_name,
    description: chain.hardware_description ?? "QA-generierter Hardware-Knoten aus Musterdatei.",
    domain: chain.domain ?? "automotive",
    device_type: chain.device_type,
    identity: {
      role: chain.device_type,
      qa_sequence: sequence,
      source_chain: chain.hardware_name,
    },
  }));

  const fn = await api(projectId, "POST", "/functions", objectPayload("function", {
    name: chain.function_name,
    description: chain.function_description ?? "QA-generierte Funktion aus Musterdatei.",
    domain: chain.domain ?? "automotive",
    hardware_node_id: hardware.id,
  }));

  const networkSuffix = String((sequence % 20) + 1).padStart(2, "0");
  const networkId = `qa-${chain.interface_type.toLowerCase()}-${networkSuffix}`;
  const iface = await api(projectId, "POST", "/interfaces", objectPayload("interface", {
    name: chain.interface_name,
    description: chain.interface_description ?? "QA-generiertes Interface aus Musterdatei.",
    domain: chain.domain ?? "automotive",
    hardware_node_id: hardware.id,
    function_id: fn.id,
    interface_type: chain.interface_type,
    configuration: {
      network_id: networkId,
      qa_sequence: sequence,
    },
  }));

  const message = await api(projectId, "POST", "/messages", objectPayload("message", {
    name: chain.message_name,
    description: chain.message_description ?? "QA-generierte Nachricht aus Musterdatei.",
    domain: chain.domain ?? "automotive",
    interface_id: iface.id,
    message_id_hex: `0x${(0x100 + sequence).toString(16).toUpperCase()}`,
    direction: "tx",
    cycle_ms: chain.cycle_ms ?? 10,
    dlc: chain.dlc ?? 8,
  }));

  await api(projectId, "POST", "/signals", objectPayload("signal", {
    name: chain.signal_name,
    display_name: chain.signal_name,
    description: chain.signal_description ?? "QA-generiertes Signal aus Musterdatei.",
    domain: chain.domain ?? "automotive",
    message_id: message.id,
    start_bit: 0,
    length_bits: chain.length_bits ?? 16,
    byte_order: "little_endian",
    data_type: "uint",
    factor: 1,
    offset_value: 0,
    unit: "",
    min_value: 0,
    max_value: 1,
  }));
}

async function mapLimit(items, limit, iteratee) {
  let nextIndex = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (nextIndex < items.length) {
      const index = nextIndex;
      nextIndex += 1;
      await iteratee(items[index], index);
    }
  });
  await Promise.all(workers);
}

async function listAll(projectId, endpoint) {
  const data = await api(projectId, "GET", `${endpoint}?limit=1000`);
  return data.items ?? data;
}

async function runOne(sample, index) {
  const projectId = `qa-neuanlage-${BATCH_ID}-${String(index + 1).padStart(2, "0")}`;
  const variant = createVariant(sample, index);
  const spec = extractEngineeringSpecification(variant);
  const wizard = wizardChecks(spec, variant, index);
  const scopeRules = {
    hardware_counts: {
      sensors: spec.targetCounts.sensors,
      actuators: spec.targetCounts.actuators,
      ecus: spec.targetCounts.ecus,
      gateways: spec.targetCounts.gateways,
    },
    communication_systems: spec.communicationSystems,
    enforcement: "exact",
    explicit: spec.targetCounts.explicit,
  };

  await api(projectId, "POST", "/projects/reset", { project_id: projectId });
  await api(projectId, "PATCH", "/workflow/context", { engineering_scope_rules: scopeRules });

  try {
    await mapLimit(spec.chains, CHAIN_CONCURRENCY, (chain, chainIndex) =>
      createChain(projectId, chain, chainIndex + 1),
    );

    const [hardware, functions, interfaces, messages, signals] = await Promise.all([
      listAll(projectId, "/hardware-nodes"),
      listAll(projectId, "/functions"),
      listAll(projectId, "/interfaces"),
      listAll(projectId, "/messages"),
      listAll(projectId, "/signals"),
    ]);

    const actual = { gateways: 0, ecus: 0, sensors: 0, actuators: 0 };
    for (const item of hardware) {
      const role = normalizeRole(item.device_type);
      if (role in actual) actual[role] += 1;
    }

    const names = hardware.map((item) => item.name);
    const duplicates = names.filter((name, pos) => names.indexOf(name) !== pos);
    const suffixViolations = names.filter((name) => !ensureNoRoleSuffix(name));
    const deviation = percentDeviation(actual, EXPECTED);
    const chainCount = spec.chains.length;
    const countChecks = {
      hardware: hardware.length === chainCount,
      functions: functions.length === chainCount,
      interfaces: interfaces.length === chainCount,
      messages: messages.length === chainCount,
      signals: signals.length === chainCount,
    };
    const pass =
      wizard.pass &&
      deviation <= 2.5 &&
      suffixViolations.length === 0 &&
      duplicates.length === 0 &&
      Object.values(countChecks).every(Boolean);

    return {
      run: index + 1,
      projectId,
      pass,
      wizard,
      deviation,
      extracted: {
        chains: chainCount,
        target_counts: spec.targetCounts,
        communication_systems: spec.communicationSystems,
        architecture: spec.networkArchitecture,
      },
      actual,
      objectCounts: {
        hardware: hardware.length,
        functions: functions.length,
        interfaces: interfaces.length,
        messages: messages.length,
        signals: signals.length,
      },
      issues: [
        ...wizard.issues,
        ...duplicates.map((name) => ({ type: "duplicate_hardware_name", name })),
        ...suffixViolations.map((name) => ({ type: "role_suffix_in_hardware_name", name })),
        ...Object.entries(countChecks)
          .filter(([, ok]) => !ok)
          .map(([entity]) => ({ type: "object_count_mismatch", entity })),
      ],
    };
  } finally {
    await api(projectId, "POST", "/projects/reset", { project_id: projectId });
  }
}

async function main() {
  const sample = await fs.readFile(SAMPLE_PATH, "utf8");
  const results = [];
  for (let index = 0; index < RUNS; index += 1) {
    try {
      const result = await runOne(sample, index);
      results.push(result);
      console.log(
        `${String(index + 1).padStart(2, "0")}/${RUNS} ${result.pass ? "PASS" : "FAIL"} deviation=${result.deviation}% project=${result.projectId}`,
      );
    } catch (error) {
      const failure = {
        run: index + 1,
        pass: false,
        deviation: 100,
        error: error instanceof Error ? error.message : String(error),
      };
      results.push(failure);
      console.log(`${String(index + 1).padStart(2, "0")}/${RUNS} FAIL ${failure.error}`);
    }
  }

  const failed = results.filter((result) => !result.pass);
  const wizardFailed = results.filter((result) => !result.wizard?.pass);
  const maxDeviation = Math.max(...results.map((result) => result.deviation ?? 100));
  const maxWizardDeviation = Math.max(...results.map((result) => result.wizard?.count_deviation_percent ?? 100));
  const report = {
    generated_at: new Date().toISOString(),
    sample_path: SAMPLE_PATH,
    runs: RUNS,
    quality_threshold_percent: 2.5,
    expected: EXPECTED,
    summary: {
      passed: RUNS - failed.length,
      failed: failed.length,
      wizard_passed: RUNS - wizardFailed.length,
      wizard_failed: wizardFailed.length,
      max_deviation_percent: maxDeviation,
      max_wizard_deviation_percent: maxWizardDeviation,
      threshold_met: failed.length === 0 && maxDeviation <= 2.5,
      wizard_threshold_met: wizardFailed.length === 0 && maxWizardDeviation <= 2.5,
    },
    results,
  };

  await fs.mkdir(REPORT_DIR, { recursive: true });
  await fs.writeFile(REPORT_PATH, JSON.stringify(report, null, 2), "utf8");
  console.log(`report=${REPORT_PATH}`);

  if (failed.length > 0 || maxDeviation > 2.5) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
