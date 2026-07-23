import type { ArtifactDownload, Catalog, SimulationJob, Technology } from "./types";

const technology = (id: string, family: string, medium: string, topology: string, bitrate: number, payload: number, native: string[] = []): Technology => ({
  id, kind: "network", family, medium, topology, default_bitrate: bitrate, max_payload_bytes: payload, native_formats: native,
});

export const localCatalog: Catalog = {
  technology_count: 18,
  formats: ["universal-jsonl", "universal-csv"],
  domains: [
    { id: "automotive", label: "Automotive", technologies: [technology("can_fd", "CAN", "Differential bus", "Bus", 2000000, 64, ["candump"]), technology("automotive_ethernet", "Ethernet", "Twisted pair", "Switched", 100000000, 1500, ["pcap"]), technology("lin", "LIN", "Single wire", "Bus", 19200, 8)] },
    { id: "industrial", label: "Industrial Automation", technologies: [technology("profinet", "Industrial Ethernet", "Ethernet", "Switched", 100000000, 1440, ["pcap"]), technology("modbus_tcp", "Modbus", "Ethernet", "Client/server", 100000000, 253)] },
    { id: "aerospace", label: "Aerospace", technologies: [technology("arinc429", "ARINC", "Shielded pair", "Point-to-point", 100000, 4), technology("mil_std_1553", "MIL-STD-1553", "Dual bus", "Command/response", 1000000, 32)] },
    { id: "iot", label: "IoT & Sensor Networks", technologies: [technology("mqtt", "MQTT", "IP", "Broker", 10000000, 65535), technology("lorawan", "LoRaWAN", "Radio", "Star-of-stars", 50000, 242)] },
    { id: "telecom", label: "Telecommunication", technologies: [technology("ethernet", "Ethernet", "Fiber / copper", "Switched", 1000000000, 1500, ["pcap"]), technology("5g_nr", "5G NR", "Radio", "Cellular", 100000000, 65535)] },
    { id: "energy", label: "Energy & Smart Grid", technologies: [technology("iec61850", "IEC 61850", "Ethernet", "Station bus", 100000000, 1500), technology("dnp3", "DNP3", "Serial / IP", "Master/outstation", 115200, 2048)] },
    { id: "robotics", label: "Robotics", technologies: [technology("ethercat", "EtherCAT", "Ethernet", "Line / ring", 100000000, 1486, ["pcap"]), technology("ros2_dds", "DDS", "IP", "Publish/subscribe", 1000000000, 65535)] },
    { id: "medical", label: "Medical Devices", technologies: [technology("hl7", "HL7", "IP", "Client/server", 100000000, 65535), technology("ble", "Bluetooth LE", "Radio", "Star", 2000000, 251)] },
  ],
};

const STORAGE_KEY = "communication-simulator-jobs-v1";

function readJobs(): Record<string, SimulationJob> {
  if (typeof window === "undefined") return {};
  try { return JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "{}"); } catch { return {}; }
}

function saveJob(job: SimulationJob) {
  if (typeof window === "undefined") return;
  const jobs = readJobs();
  jobs[job.id] = job;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(jobs));
}

function download(name: string, content: string, index: number): ArtifactDownload {
  return { index, name, url: `data:text/plain;charset=utf-8,${encodeURIComponent(content)}` };
}

function numberValue(value: unknown, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function createLocalSimulation(rawPayload: Record<string, unknown>, validateOnly: boolean): SimulationJob {
  const config = (rawPayload.config && typeof rawPayload.config === "object" ? rawPayload.config : rawPayload) as Record<string, unknown>;
  const duration = numberValue(config.duration_s, 1);
  const cycle = numberValue(config.cycle_ms, 100);
  const nodes = numberValue(config.node_count, 2);
  const maxEvents = numberValue(config.max_events, 100000);
  const dropout = numberValue(config.dropout_probability, 0);
  const corruption = numberValue(config.corruption_probability, 0);
  const payloadBytes = numberValue(config.payload_bytes, 8);
  const technologyId = String(config.technology ?? "custom");
  const seed = numberValue(config.seed, 42);
  const formats = Array.isArray(config.formats) ? config.formats.map(String) : ["universal-jsonl"];

  if (duration <= 0 || cycle <= 0 || nodes < 2) throw new Error("Dauer und Zyklus müssen positiv sein; mindestens zwei Knoten sind erforderlich.");
  if (dropout < 0 || dropout > 1 || corruption < 0 || corruption > 1) throw new Error("Dropout und Korruption müssen zwischen 0 und 1 liegen.");
  if (!validateOnly && formats.length === 0) throw new Error("Wähle mindestens ein Ausgabeformat.");

  const theoreticalEvents = Math.ceil((duration * 1000) / cycle) * nodes;
  const events = validateOnly ? 0 : Math.max(0, Math.min(maxEvents, Math.round(theoreticalEvents * (1 - dropout))));
  const warnings: string[] = [];
  if (theoreticalEvents > maxEvents) warnings.push(`Eventlimit aktiv: ${maxEvents.toLocaleString("de-DE")} von ${theoreticalEvents.toLocaleString("de-DE")} Ereignissen erzeugt.`);
  if (dropout > 0.1) warnings.push("Hohe Dropout-Wahrscheinlichkeit kann die Trace-Abdeckung reduzieren.");
  if (corruption > 0.05) warnings.push("Erhöhte Korruptionsrate erkannt.");

  const id = `local-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
  const createdAt = new Date().toISOString();
  const rows = Array.from({ length: Math.min(events, 50) }, (_, index) => ({ timestamp_ms: Number((index * cycle / Math.max(nodes, 1)).toFixed(3)), source: `node-${index % nodes + 1}`, target: `node-${(index + 1) % nodes + 1}`, technology: technologyId, payload_bytes: payloadBytes, valid: ((seed * 9301 + index * 49297) % 233280) / 233280 >= corruption }));
  const artifacts = validateOnly ? [] : formats.map((format, index) => format === "universal-csv"
    ? download(`${id}.csv`, `timestamp_ms,source,target,technology,payload_bytes,valid\n${rows.map((row) => Object.values(row).join(",")).join("\n")}`, index)
    : download(`${id}.${format === "candump" ? "log" : format === "pcap" ? "pcap.txt" : "jsonl"}`, rows.map((row) => JSON.stringify(row)).join("\n"), index));

  const job: SimulationJob = {
    id, status: "completed", validate_only: validateOnly, created_at: createdAt, updated_at: createdAt, error: null,
    result: { status: "completed", output_dir: "browser://local-simulator", warnings, hardware_validation: { valid: true, findings: [] }, trace: { events, routes: nodes * (nodes - 1), technologies: [technologyId], duration_s: duration } },
    artifact_downloads: artifacts,
  };
  saveJob(job);
  return job;
}

export function getLocalSimulation(id: string): SimulationJob {
  const job = readJobs()[id];
  if (!job) throw new Error("Dieser lokale Simulationslauf wurde nicht gefunden. Starte im Studio einen neuen Lauf.");
  return job;
}
