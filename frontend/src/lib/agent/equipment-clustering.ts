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
    terms: ["klima", "klimatisierung", "climate", "hvac", "heizung", "heater", "ventilation", "blower", "cabin", "innenraum", "ambient", "aussen", "thermo", "thermal", "thermomanagement", "coolant", "kuehlmittel", "compressor", "kompressor", "refrigerant", "kaeltemittel"],
    preferredNetworks: ["canfd", "can"],
    recommendation: "Thermik, Regelung und Komfortsignale gemeinsam bewerten.",
  },
  {
    id: "lighting",
    label: "Licht",
    terms: ["licht", "innenlicht", "aussenlicht", "ambientlight", "light", "lamp", "illumination"],
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
    terms: ["safety", "sicherheit", "restraint", "airbag", "brake", "bremse", "brems", "brakepedal", "bremsregelung", "stability", "stabilitaet", "stabilitat", "stabilitaetsregelung"],
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
      "fahrwerk", "fahrdynamik", "reifendruck", "tirepressure", "tire", "reifen", "wheel", "rad", "wheelspeed",
      "wheelload", "wheelangle", "wheeltorque", "tirewear", "suspensiontravel",
    ],
    preferredNetworks: ["ethernet", "canfd", "can"],
    recommendation: "Umfeld-, Park- und Fahrdynamiksignale gemeinsam auf Latenz, Bandbreite und Sensorfusion pruefen.",
  },
  {
    id: "energy",
    label: "Energie",
    terms: ["energy", "energie", "energieversorgung", "battery", "batterie", "batteriemanagement", "power", "spannung", "voltage", "current", "strom", "bordnetz", "alternator", "generator", "dclink", "zellspannung", "inverter", "ladesteuerung"],
    preferredNetworks: ["canfd", "can", "lin"],
    recommendation: "Versorgungs- und Batteriethemen als belastbaren Systemrahmen planen.",
  },
  {
    id: "motion",
    label: "Antrieb",
    terms: ["drive", "motion", "antrieb", "engine", "motor", "elektromotor", "gear", "getriebe", "transmission", "traction", "steering", "lenkung", "hinterachslenkung", "accelerator", "fahrpedal", "clutch", "kupplung", "throttle", "drossel", "boost", "intake", "ansaugluft", "turbo", "oil", "oel", "kraftstoff", "fuel", "exhaust", "abgas", "abgasnachbehandlung", "egr", "agrventil", "urea", "harnstoff"],
    preferredNetworks: ["canfd", "ethernet", "can"],
    recommendation: "Antriebsnahe Regelungsdaten mit Latenz- und Lastreserve behandeln.",
  },
  {
    id: "body_comfort",
    label: "Karosserie und Komfort",
    terms: ["karosserie", "body", "bodycontrol", "comfort", "komfort", "schiebedach", "sunroof", "heckklappe", "tailgate", "anhaenger", "trailer", "wischer", "washer", "wasch", "rain", "regen", "seat", "sitz", "fahrersitz", "beifahrersitz", "window", "fenster", "door", "tuer", "fahrertuer", "beifahrertuer", "fondtuer"],
    preferredNetworks: ["lin", "canfd", "can"],
    recommendation: "Lokale Komfortfunktionen zusammenhalten und langsame Segmente bewusst abgrenzen.",
  },
  {
    id: "infotainment",
    label: "Infotainment und Anzeige",
    terms: ["infotainment", "headup", "headupdisplay", "display", "kombiinstrument", "sound", "soundsystem", "audio", "telematik", "connectivity", "konnektivitaet", "navigation"],
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

const FALLBACK_CLUSTER_BY_DEVICE_TYPE: Record<string, { id: string; label: string; preferredNetworks: string[]; recommendation: string }> = {
  SensorController: {
    id: "fallback:sensors",
    label: "Allgemeine Sensorik",
    preferredNetworks: ["canfd", "lin", "ethernet", "can"],
    recommendation: "Nicht eindeutig zugeordnete Sensoren gemeinsam pruefen und danach fachlich auf Steuergeraete verteilen.",
  },
  ActuatorController: {
    id: "fallback:actuators",
    label: "Allgemeine Aktorik",
    preferredNetworks: ["lin", "canfd", "can"],
    recommendation: "Nicht eindeutig zugeordnete Aktoren nicht einzeln als Systemcluster behandeln, sondern gemeinsam nach Funktion verteilen.",
  },
  ECU: {
    id: "fallback:controllers",
    label: "Allgemeine Steuergeraete",
    preferredNetworks: ["canfd", "ethernet", "can"],
    recommendation: "Nicht eindeutig zugeordnete Steuergeraete als Review-Gruppe behalten und nicht als zufaellige Einzelcluster fortschreiben.",
  },
};

const SHORT_COMPOUND_TERMS = new Set([
  "egr",
  "agr",
  "hvac",
  "lin",
  "oil",
  "oel",
  "rad",
  "tuer",
  "light",
  "licht",
  "motor",
  "boost",
  "turbo",
  "fuel",
  "gear",
  "rain",
  "regen",
]);

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

function keyTokens(value: string) {
  return keyText(value).split(" ").filter(Boolean);
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
  const semantic = record(chain.semantic);
  const data = record(chain.data);
  return [
    chain.hardware_name,
    chain.hardware_description,
    text(semantic.category),
    text(semantic.system_frame),
    text(semantic.systemFrame),
    text(data.system_frame),
  ].filter(Boolean).join(" ");
}

function ruleFor(chain: ExtractedEngineeringChain) {
  const corpus = chainCorpus(chain);
  const compactCorpus = compactKey(corpus);
  const tokens = new Set(keyTokens(corpus));
  const scored = CLUSTER_RULES
    .map((rule, index) => {
      const score = rule.terms.reduce((total, term) => {
        const compactTerm = compactKey(term);
        if (!compactTerm) return total;
        const exactMatch = tokens.has(compactTerm);
        const compoundMatch = compactTerm.length > 5 || SHORT_COMPOUND_TERMS.has(compactTerm)
          ? compactCorpus.includes(compactTerm)
          : false;
        return exactMatch || compoundMatch ? total + Math.max(1, compactTerm.length) : total;
      }, 0);
      return { index, rule, score };
    })
    .filter((candidate) => candidate.score > 0)
    .sort((left, right) => right.score - left.score || left.index - right.index);
  return scored[0]?.rule;
}

function explicitSystemName(chain: ExtractedEngineeringChain) {
  const semantic = record(chain.semantic);
  const candidates = [
    semantic.system_frame,
    semantic.systemFrame,
    semantic.system,
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

function uniqueDevices(devices: ExtractedEngineeringChain[]) {
  const byHardware = new Map<string, ExtractedEngineeringChain>();
  for (const chain of devices) {
    const key = `${chain.device_type}:${compactKey(chain.hardware_name)}`;
    if (!byHardware.has(key)) byHardware.set(key, chain);
  }
  return [...byHardware.values()];
}

function fallbackClusterFor(chain: ExtractedEngineeringChain) {
  return FALLBACK_CLUSTER_BY_DEVICE_TYPE[chain.device_type] ?? {
    id: `system:${slug(inferredSystemName(chain))}`,
    label: displayLabel(inferredSystemName(chain)),
    preferredNetworks: [chain.interface_type, "canfd", "can", "lin"],
    recommendation: "Fachlich zusammenhaengende Teilnehmer als Systemrahmen pruefen.",
  };
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
      const fallback = explicit ? null : fallbackClusterFor(chain);
      const label = rule?.label ?? displayLabel(explicit || fallback?.label || inferredSystemName(chain));
      const id = rule ? `rule:${rule.id}` : explicit ? `system:${slug(label)}` : fallback?.id ?? `system:${slug(label)}`;
      const bucket = buckets.get(id) ?? {
        label,
        recommendation: rule?.recommendation ?? fallback?.recommendation ?? "Fachlich zusammenhaengende Teilnehmer als Systemrahmen pruefen.",
        preferredNetworks: rule?.preferredNetworks ?? fallback?.preferredNetworks ?? [chain.interface_type, "canfd", "can", "lin"],
        devices: [],
      };
      bucket.devices.push(chain);
      buckets.set(id, bucket);
    });

  return [...buckets.entries()]
    .map(([id, bucket]) => {
      const network = recommendedNetwork(networkOptions, bucket.preferredNetworks);
      const sortedDevices = uniqueDevices(bucket.devices).sort((left, right) => left.hardware_name.localeCompare(right.hardware_name, "de"));
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
