import { normalizeHardwareName, type ExtractedEngineeringChain } from "./engineering-specification.ts";

export type EquipmentNetworkOption = {
  id: string;
  label: string;
  count?: number;
};

export type EquipmentClusterAssignment = {
  cluster_id: string;
  label: string;
  selected: boolean;
  network_id: string;
  network_label: string;
  bus_name: string;
  devices: number;
  counts: Record<string, number>;
  evidence: string[];
};

export type EquipmentCluster = {
  id: string;
  label: string;
  recommendation: string;
  recommendedNetworkId: string;
  recommendedNetworkLabel: string;
  counts: Record<string, number>;
  devices: ExtractedEngineeringChain[];
  evidence: string[];
};

const CLUSTER_RULES: Array<{ id: string; label: string; terms: string[]; preferredNetworks: string[]; recommendation: string }> = [
  {
    id: "climate",
    label: "Klima",
    terms: ["klima", "climate", "hvac", "heizung", "heater", "ventilation", "blower", "temperature", "temperatur", "thermo", "thermal", "compressor", "kompressor", "refrigerant", "kaeltemittel"],
    preferredNetworks: ["canfd", "can"],
    recommendation: "Thermik, Regelung und Komfortsignale gemeinsam bewerten.",
  },
  {
    id: "lighting",
    label: "Licht",
    terms: ["licht", "light", "lamp", "illumination"],
    preferredNetworks: ["lin", "canfd", "can"],
    recommendation: "Lokale Lichtsignale zusammenhalten und bei Lastspitzen auf mehrere Segmente verteilen.",
  },
  {
    id: "access_security",
    label: "Zugang und Diebstahlschutz",
    terms: ["wegfahrsperre", "immobilizer", "keyless", "access", "zugang", "key", "schluessel", "theft", "diebstahl"],
    preferredNetworks: ["canfd", "can", "lin"],
    recommendation: "Zugangs- und Freigabepfade getrennt pruefen, auch wenn sie technisch am Gateway haengen.",
  },
  {
    id: "safety",
    label: "Sicherheit",
    terms: ["safety", "restraint", "airbag", "brake", "bremse", "stability", "stabilitaet", "stabilitat"],
    preferredNetworks: ["canfd", "can", "ethernet"],
    recommendation: "Safety-nahe Teilnehmer gemeinsam pruefen und nicht blind auf langsame Busse legen.",
  },
  {
    id: "driver_assistance",
    label: "Fahrerassistenz",
    terms: [
      "adas", "fahrerassistenz", "driverassist", "driver assistance", "parkassistenz", "parkassist", "parking",
      "ultraschall", "ultrasonic", "radar", "lidar", "kamera", "camera", "frontkamera", "heckkamera",
      "lane", "spur", "acceleration", "beschleunigung", "verticalacceleration", "lateralacceleration",
      "longitudinalacceleration", "pitchrate", "yawrate", "rollrate", "damper", "daempfer", "suspension",
      "fahrwerk", "reifendruck", "tirepressure",
    ],
    preferredNetworks: ["ethernet", "canfd", "can"],
    recommendation: "Umfeld-, Park- und Fahrdynamiksignale gemeinsam auf Latenz, Bandbreite und Sensorfusion pruefen.",
  },
  {
    id: "energy",
    label: "Energie",
    terms: ["energy", "energie", "battery", "batterie", "power", "spannung", "voltage", "current", "strom"],
    preferredNetworks: ["canfd", "can", "lin"],
    recommendation: "Versorgungs- und Batteriethemen als belastbaren Systemrahmen planen.",
  },
  {
    id: "motion",
    label: "Antrieb",
    terms: ["drive", "motion", "antrieb", "engine", "motor", "gear", "getriebe", "traction", "steering", "lenkung", "throttle", "turbo", "oil", "oel", "kraftstoff", "fuel", "exhaust", "abgas"],
    preferredNetworks: ["canfd", "ethernet", "can"],
    recommendation: "Antriebsnahe Regelungsdaten mit Latenz- und Lastreserve behandeln.",
  },
  {
    id: "body_comfort",
    label: "Karosserie und Komfort",
    terms: ["karosserie", "body", "comfort", "komfort", "schiebedach", "sunroof", "heckklappe", "tailgate", "wischer", "washer", "wasch", "seat", "sitz", "window", "fenster", "door", "tuer"],
    preferredNetworks: ["lin", "canfd", "can"],
    recommendation: "Lokale Komfortfunktionen zusammenhalten und langsame Segmente bewusst abgrenzen.",
  },
  {
    id: "infotainment",
    label: "Infotainment und Anzeige",
    terms: ["infotainment", "headup", "display", "sound", "audio", "telematik", "connectivity", "konnektivitaet", "navigation"],
    preferredNetworks: ["ethernet", "lin", "canfd"],
    recommendation: "Anzeige-, Audio- und Telematikpfade fachlich pruefen; unklare Stellglieder nicht automatisch als physische Aktoren freigeben.",
  },
  {
    id: "diagnostics",
    label: "Diagnose und Service",
    terms: ["diagnose", "diagnostic", "service", "maintenance", "wartung", "logging", "trace"],
    preferredNetworks: ["ethernet", "canfd", "can"],
    recommendation: "Diagnosepfade getrennt von zyklischer Regelkommunikation auswerten.",
  },
];

const FUNCTION_SUFFIX_PATTERN = /(?:schaltausgang|stellglied|status|state|mode|data|daten|signal|position|current|pressure|temperature|temperatur|voltage|spannung|level|niveau|flow|rate|switch|valve|aktor|aktuator)$/i;

function keyText(value: string) {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[_-]+/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

function compactKey(value: string) {
  return keyText(value).replace(/\s+/g, "");
}

function displayLabel(value: string) {
  const normalized = normalizeHardwareName(value).trim();
  const spaced = normalized
    .replace(/[_-]+/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\s+/g, " ")
    .trim();
  if (!spaced) return "Systemcluster";
  return spaced
    .split(" ")
    .map((part) => part ? `${part[0].toLocaleUpperCase("de")}${part.slice(1)}` : part)
    .join(" ");
}

function slug(value: string) {
  return compactKey(value).replace(/[^a-z0-9]+/g, "-") || "cluster";
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? value as Record<string, unknown> : {};
}

function text(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function chainCorpus(chain: ExtractedEngineeringChain) {
  return [
    chain.hardware_name,
    chain.hardware_description,
    chain.function_name,
    chain.function_description,
    chain.interface_name,
    chain.message_name,
    chain.signal_name,
    chain.signal_display_name,
    text(record(chain.semantic).category),
    text(record(chain.semantic).system_frame),
    text(record(chain.semantic).systemFrame),
  ].filter(Boolean).join(" ");
}

function ruleFor(chain: ExtractedEngineeringChain) {
  const corpus = compactKey(chainCorpus(chain));
  return CLUSTER_RULES.find((rule) => rule.terms.some((term) => corpus.includes(compactKey(term))));
}

function explicitSystemName(chain: ExtractedEngineeringChain) {
  const semantic = record(chain.semantic);
  const candidates = [
    semantic.system_frame,
    semantic.systemFrame,
    semantic.system,
    semantic.category,
    record(chain.data).system_frame,
  ].map(text).filter(Boolean);
  return candidates.find((candidate) => compactKey(candidate).length > 2) ?? "";
}

function inferredSystemName(chain: ExtractedEngineeringChain) {
  const normalized = normalizeHardwareName(chain.hardware_name);
  const withoutSuffix = normalized.replace(FUNCTION_SUFFIX_PATTERN, "").trim();
  const candidate = withoutSuffix || normalized || chain.function_name || "Systemcluster";
  const tokens = displayLabel(candidate).split(" ").filter(Boolean);
  return tokens.slice(0, 3).join(" ") || "Systemcluster";
}

function optionMatches(option: EquipmentNetworkOption, preference: string) {
  const optionKey = compactKey(`${option.id} ${option.label}`);
  const preferred = compactKey(preference);
  if (preferred === "canfd") return optionKey.includes("canfd") || optionKey.includes("can-fd");
  if (preferred === "lin") return optionKey.includes("lin");
  if (preferred === "ethernet") return optionKey.includes("ethernet");
  if (preferred === "can") return optionKey.includes("can") && !optionKey.includes("canfd");
  return optionKey.includes(preferred);
}

function recommendedNetwork(options: EquipmentNetworkOption[], preferences: string[]) {
  const viable = options.filter((option) => (option.count ?? 1) > 0);
  const pool = viable.length ? viable : options;
  for (const preference of preferences) {
    const match = pool.find((option) => optionMatches(option, preference));
    if (match) return match;
  }
  return pool[0] ?? { id: "", label: "Noch kein Netz" };
}

function deviceCounts(devices: ExtractedEngineeringChain[]) {
  return devices.reduce<Record<string, number>>((counts, chain) => {
    counts[chain.device_type] = (counts[chain.device_type] ?? 0) + 1;
    return counts;
  }, {});
}

export function buildEquipmentClusters(
  chains: ExtractedEngineeringChain[],
  networkOptions: EquipmentNetworkOption[],
): EquipmentCluster[] {
  const buckets = new Map<string, { label: string; recommendation: string; preferredNetworks: string[]; devices: ExtractedEngineeringChain[] }>();

  chains
    .filter((chain) => chain.device_type !== "Gateway")
    .forEach((chain) => {
      const rule = ruleFor(chain);
      const explicit = explicitSystemName(chain);
      const label = rule?.label ?? displayLabel(explicit || inferredSystemName(chain));
      const id = rule ? `rule:${rule.id}` : `system:${slug(label)}`;
      const bucket = buckets.get(id) ?? {
        label,
        recommendation: rule?.recommendation ?? "Fachlich zusammenhaengende Teilnehmer als Systemrahmen pruefen.",
        preferredNetworks: rule?.preferredNetworks ?? [chain.interface_type, "canfd", "can", "lin"],
        devices: [],
      };
      bucket.devices.push(chain);
      buckets.set(id, bucket);
    });

  return [...buckets.entries()]
    .map(([id, bucket]) => {
      const network = recommendedNetwork(networkOptions, bucket.preferredNetworks);
      const sortedDevices = [...bucket.devices].sort((left, right) => left.hardware_name.localeCompare(right.hardware_name, "de"));
      return {
        id,
        label: bucket.label,
        recommendation: bucket.recommendation,
        recommendedNetworkId: network.id,
        recommendedNetworkLabel: network.label,
        counts: deviceCounts(sortedDevices),
        devices: sortedDevices,
        evidence: sortedDevices.slice(0, 6).map((chain) => chain.hardware_name),
      };
    })
    .sort((left, right) => right.devices.length - left.devices.length || left.label.localeCompare(right.label, "de"));
}

export function equipmentClusterSummary(assignments: EquipmentClusterAssignment[]) {
  return assignments
    .filter((assignment) => assignment.selected)
    .map((assignment) => `${assignment.label} -> ${assignment.network_label} / ${assignment.bus_name} (${assignment.devices} Teilnehmer)`)
    .join("; ");
}
