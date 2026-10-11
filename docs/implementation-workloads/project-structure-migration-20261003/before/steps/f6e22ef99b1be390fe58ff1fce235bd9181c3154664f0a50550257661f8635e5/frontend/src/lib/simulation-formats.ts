export type SimulationFormatGroupId = "universal" | "can" | "ethernet" | "data";

export type SimulationFormatDefinition = {
  id: string;
  group: SimulationFormatGroupId;
  label: string;
  description: string;
};

export const simulationFormatDefinitions: SimulationFormatDefinition[] = [
  { id: "universal-jsonl", group: "universal", label: "JSONL", description: "Universeller Ereignisstrom" },
  { id: "universal-csv", group: "universal", label: "CSV", description: "Universelle Tabellenablage" },
  { id: "jsonl", group: "data", label: "JSONL", description: "Rohdaten als JSON Lines" },
  { id: "csv", group: "data", label: "CSV", description: "Tabellarische Rohdaten" },
  { id: "json", group: "data", label: "JSON", description: "Strukturierte Rohdaten" },
  { id: "log", group: "data", label: "LOG", description: "Textuelles Trace-Log" },
  { id: "txt", group: "data", label: "TXT", description: "Lesbarer Text-Export" },
  { id: "xml", group: "data", label: "XML", description: "Strukturierter XML-Export" },
  { id: "yaml", group: "data", label: "YAML", description: "YAML-Konfiguration" },
  { id: "yml", group: "data", label: "YML", description: "YAML-Kurzformat" },
  { id: "blf", group: "can", label: "BLF", description: "Vector-nahes CAN/CAN-FD Binärtrace" },
  { id: "asc", group: "can", label: "ASC", description: "CAN ASCII Trace" },
  { id: "trc", group: "can", label: "TRC", description: "PCAN Trace" },
  { id: "dbc", group: "can", label: "DBC", description: "CAN Signal- und Nachrichten-Datenbank" },
  { id: "arxml", group: "can", label: "ARXML", description: "AUTOSAR Austauschformat" },
  { id: "fibex", group: "can", label: "FIBEX", description: "Netzwerk- und Signalbeschreibung" },
  { id: "mdf", group: "can", label: "MDF", description: "Messdatenformat 3.x" },
  { id: "mf4", group: "can", label: "MF4", description: "Messdatenformat 4.x" },
  { id: "pcap", group: "ethernet", label: "PCAP", description: "Ethernet Paketmitschnitt" },
  { id: "pcapng", group: "ethernet", label: "PCAPNG", description: "Next Generation Paketmitschnitt" },
];

export const defaultSimulationFormats = ["universal-jsonl", "universal-csv"];

export const simulationFormatGroupLabels: Record<SimulationFormatGroupId, string> = {
  universal: "Universell",
  can: "CAN / Fahrzeugdaten",
  ethernet: "Ethernet",
  data: "Daten / Text",
};

export function mergeSimulationFormats(...groups: Array<readonly string[] | undefined | null>) {
  const knownOrder = new Map(simulationFormatDefinitions.map((format, index) => [format.id, index]));
  return Array.from(new Set(groups.flatMap((group) => group ?? []).map(String)))
    .filter(Boolean)
    .sort((left, right) => (knownOrder.get(left) ?? 10_000) - (knownOrder.get(right) ?? 10_000));
}

export function describeSimulationFormat(format: string): SimulationFormatDefinition {
  return simulationFormatDefinitions.find((item) => item.id === format) ?? {
    id: format,
    group: "data",
    label: format.toUpperCase(),
    description: "Natives Simulatorformat",
  };
}

export function groupSimulationFormats(formats: readonly string[]) {
  const orderedGroups: SimulationFormatGroupId[] = ["universal", "can", "ethernet", "data"];
  const byGroup = new Map<SimulationFormatGroupId, SimulationFormatDefinition[]>();
  for (const format of formats) {
    const definition = describeSimulationFormat(format);
    byGroup.set(definition.group, [...(byGroup.get(definition.group) ?? []), definition]);
  }
  return orderedGroups
    .map((group) => ({ id: group, label: simulationFormatGroupLabels[group], formats: byGroup.get(group) ?? [] }))
    .filter((group) => group.formats.length > 0);
}

export function simulationFormatExtension(format: string) {
  if (format === "universal-jsonl") return "jsonl";
  if (format === "universal-csv") return "csv";
  if (format === "fibex") return "fibex.xml";
  if (format === "pcap") return "pcap.txt";
  return format;
}
