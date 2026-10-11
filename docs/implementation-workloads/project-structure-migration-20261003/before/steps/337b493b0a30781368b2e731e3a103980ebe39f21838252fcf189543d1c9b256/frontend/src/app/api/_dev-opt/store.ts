import type { Catalog, SimulationJob } from "@/lib/types";
import { BoundedMemoryCache } from "@/lib/bounded-memory-cache";
import { simulationFormatDefinitions, simulationFormatExtension } from "@/lib/simulation-formats";

// DEV-OPT: These Next.js-only fixtures keep the isolated v0 frontend preview
// editable when the Python service is not started. Vercel Services routes /api
// to Flask in deployed environments, so this module is not the production API.
const formats = simulationFormatDefinitions.map((format) => format.id);

const technology = (
  id: string,
  family: string,
  medium: string,
  topology: string,
  default_bitrate: number | null,
  max_payload_bytes: number,
  native_formats: string[] = [],
  kind = "bus",
) => ({ id, family, medium, topology, default_bitrate, max_payload_bytes, native_formats, kind });

export const devCatalog: Catalog = {
  technology_count: 35,
  formats,
  domains: [
    {
      id: "automotive",
      label: "Automotive",
      technologies: [
        technology("can", "automotive", "differential_pair", "bus", 500_000, 8, ["blf", "dbc", "asc", "trc"]),
        technology("can_fd", "automotive", "differential_pair", "bus", 2_000_000, 64, ["blf", "dbc", "asc", "trc"]),
        technology("can_xl", "automotive", "differential_pair", "bus", 10_000_000, 2048),
        technology("lin", "automotive", "single_wire", "bus", 19_200, 8),
        technology("flexray", "automotive", "differential_pair", "bus_or_star", 10_000_000, 254),
        technology("automotive_ethernet", "automotive", "single_or_quad_pair", "switched_star", 1_000_000_000, 1500, ["pcap", "pcapng"]),
        technology("someip", "automotive", "ethernet", "switched", null, 1400, ["pcap", "pcapng"], "protocol"),
      ],
    },
    {
      id: "industrial_automation",
      label: "Industrial Automation",
      technologies: [
        technology("profibus", "industrial", "rs485_or_fiber", "bus", 12_000_000, 244),
        technology("profinet", "industrial", "ethernet", "switched", 100_000_000, 1440, ["pcap", "pcapng"]),
        technology("ethercat", "industrial", "ethernet", "line_ring_star", 100_000_000, 1486, ["pcap", "pcapng"]),
        technology("modbus_rtu", "industrial", "rs485", "bus", 115_200, 253),
        technology("modbus_tcp", "industrial", "ethernet", "switched", 100_000_000, 260, ["pcap", "pcapng"]),
        technology("opc_ua", "industrial", "ethernet", "switched", null, 65_535, ["pcap", "pcapng"], "protocol"),
      ],
    },
    {
      id: "embedded_systems",
      label: "Embedded Systems",
      technologies: [
        technology("i2c", "embedded", "two_wire", "bus", 400_000, 255),
        technology("spi", "embedded", "synchronous_serial", "point_to_multipoint", 10_000_000, 4096),
        technology("uart", "embedded", "serial", "point_to_point", 115_200, 1024),
        technology("rs485", "embedded_industrial", "differential_serial", "bus", 10_000_000, 4096),
        technology("usb", "embedded", "differential_pair", "tiered_star", 480_000_000, 1024),
        technology("pcie", "embedded", "differential_lanes", "point_to_point_fabric", 8_000_000_000, 4096),
      ],
    },
    {
      id: "aerospace",
      label: "Aerospace / Defense",
      technologies: [
        technology("arinc429", "aerospace", "shielded_twisted_pair", "point_to_point", 100_000, 4),
        technology("arinc664_afdx", "aerospace", "redundant_ethernet", "switched_star", 100_000_000, 1471, ["pcap", "pcapng"]),
        technology("mil_std_1553", "aerospace_defense", "dual_redundant_pair", "bus", 1_000_000, 64),
        technology("spacewire", "aerospace", "differential_pairs", "point_to_point_network", 200_000_000, 65_535),
      ],
    },
    {
      id: "generic_networking",
      label: "Generic Networking",
      technologies: [
        technology("ethernet", "general", "copper_or_fiber", "switched_star", 1_000_000_000, 1500, ["pcap", "pcapng"]),
        technology("ipv4", "general", "network_layer", "routed", null, 65_535, ["pcap", "pcapng"], "protocol"),
        technology("ipv6", "general", "network_layer", "routed", null, 65_575, ["pcap", "pcapng"], "protocol"),
        technology("udp", "general", "transport_layer", "routed", null, 65_507, ["pcap", "pcapng"], "protocol"),
        technology("tcp", "general", "transport_layer", "routed", null, 65_535, ["pcap", "pcapng"], "protocol"),
      ],
    },
  ],
};

type DevJob = SimulationJob & { request: Record<string, unknown> };

const jobs = new BoundedMemoryCache<string, DevJob>({
  maxEntries: 30,
  ttlMs: 60 * 60 * 1000,
  maxValueBytes: 1_000_000,
});

function requestedFormats(payload: Record<string, unknown>): string[] {
  const config = payload.config;
  const value = config && typeof config === "object" && "formats" in config
    ? (config as Record<string, unknown>).formats
    : payload.formats;
  return Array.isArray(value) && value.length ? value.map(String) : ["universal-jsonl", "universal-csv"];
}

export function createDevJob(payload: Record<string, unknown>, validateOnly: boolean): SimulationJob {
  const id = `dev-opt-${crypto.randomUUID()}`;
  const now = new Date().toISOString();
  const duration = Number(payload.duration_s ?? 1);
  const cycle = Math.max(Number(payload.cycle_ms ?? 100), 1);
  const nodes = Math.max(Number(payload.node_count ?? 2), 2);
  const eventCount = validateOnly ? 0 : Math.max(1, Math.round((duration * 1000 / cycle) * nodes));
  const selectedFormats = requestedFormats(payload);
  const selectedTechnology = String(payload.technology ?? "configured_topology");

  const job: DevJob = {
    id,
    status: "completed",
    validate_only: validateOnly,
    created_at: now,
    updated_at: now,
    error: null,
    request: payload,
    result: {
      status: validateOnly ? "validated" : "completed",
      output_dir: `dev-opt://${id}`,
      warnings: ["DEV-OPT: Lokales Vorschauergebnis; keine physikalische Backend-Simulation ausgeführt."],
      hardware_validation: { valid: true, findings: [] },
      trace: { events: eventCount, routes: Math.max(nodes - 1, 1), technologies: [selectedTechnology], duration_s: duration },
    },
    artifact_downloads: validateOnly
      ? []
      : selectedFormats.map((format, index) => ({
          index,
          name: `dev-opt-trace.${simulationFormatExtension(format)}`,
          url: `/api/simulations/${id}/artifacts/${encodeURIComponent(format)}`,
        })),
  };
  jobs.set(id, job);
  return job;
}

export function getDevJob(id: string): SimulationJob | undefined {
  return jobs.get(id);
}

export function listDevJobs(): SimulationJob[] {
  return jobs.values().sort((a, b) => b.created_at.localeCompare(a.created_at));
}

export function getDevArtifact(id: string, format: string): { body: string; type: string; name: string } | undefined {
  const job = jobs.get(id);
  if (!job || job.validate_only) return undefined;
  const normalized = decodeURIComponent(format).toLowerCase();
  const record = { timestamp_s: 0, source: "dev-node-1", destination: "dev-node-2", technology: "DEV-OPT", payload_hex: "00ff10" };
  if (normalized.includes("csv")) {
    return { body: `timestamp_s,source,destination,technology,payload_hex\n${Object.values(record).join(",")}\n`, type: "text/csv; charset=utf-8", name: "dev-opt-trace.csv" };
  }
  return { body: `${JSON.stringify(record)}\n`, type: "application/x-ndjson; charset=utf-8", name: "dev-opt-trace.jsonl" };
}
