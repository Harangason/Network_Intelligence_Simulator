export type TopologyClusterProfileKey =
  | "generic"
  | "automotive"
  | "industrial_automation"
  | "energy"
  | "aerospace"
  | "rail"
  | "marine"
  | "building_automation"
  | "robotics_ros";

export type TopologyClusterRule = {
  key: string;
  label: string;
  role: "source" | "controller" | "plant" | "actuation" | "infrastructure" | "service";
  terms: string[];
  related: string[];
};

export type TopologyClusterLesson = {
  left: string;
  right: string;
  weight: number;
  updatedAt: string;
};

const LEARNING_STORAGE_PREFIX = "networkis:topology-cluster-lessons:v1:";

const PROFILE_ALIASES: Record<string, TopologyClusterProfileKey> = {
  auto: "automotive",
  automotive: "automotive",
  can: "automotive",
  car: "automotive",
  fahrzeug: "automotive",
  industrial: "industrial_automation",
  industrialautomation: "industrial_automation",
  industrial_automation: "industrial_automation",
  manufacturing: "industrial_automation",
  plc: "industrial_automation",
  energy: "energy",
  grid: "energy",
  aerospace: "aerospace",
  aviation: "aerospace",
  rail: "rail",
  railway: "rail",
  marine: "marine",
  building: "building_automation",
  buildingautomation: "building_automation",
  building_automation: "building_automation",
  robotics: "robotics_ros",
  ros: "robotics_ros",
  ros2: "robotics_ros",
  roboticsros: "robotics_ros",
};

const GENERIC_RULES: TopologyClusterRule[] = [
  { key: "control", label: "Regelung", role: "controller", terms: ["control", "controller", "steuerung", "regelung", "ecu", "plc"], related: ["sensorics", "actuation", "diagnostics"] },
  { key: "sensorics", label: "Sensorik", role: "source", terms: ["sensor", "messung", "measurement", "input", "perception"], related: ["control"] },
  { key: "actuation", label: "Aktorik", role: "actuation", terms: ["actuator", "aktor", "stellglied", "output", "valve", "motor"], related: ["control"] },
  { key: "energy", label: "Energie", role: "infrastructure", terms: ["energy", "energie", "power", "battery", "batterie", "versorgung"], related: ["control", "actuation"] },
  { key: "diagnostics", label: "Diagnose", role: "service", terms: ["diagnose", "diagnostic", "service", "trace", "logging"], related: ["control"] },
];

const AUTOMOTIVE_RULES: TopologyClusterRule[] = [
  { key: "powertrain_motor", label: "Motor / Antrieb", role: "controller", terms: ["motor", "engine", "antrieb", "drive", "powertrain", "drossel", "throttle", "turbo", "boost", "ladedruck", "ansaugluft", "kraftstoff", "fuel", "oel", "oil"], related: ["powertrain_exhaust", "powertrain_transmission", "emobility", "energy"] },
  { key: "powertrain_exhaust", label: "Abgasnachbehandlung", role: "plant", terms: ["abgas", "abgasnachbehandlung", "exhaust", "emission", "egr", "agr", "harnstoff", "urea", "scr", "katalysator", "catalyst"], related: ["powertrain_motor", "powertrain_transmission"] },
  { key: "powertrain_transmission", label: "Getriebe", role: "plant", terms: ["getriebe", "gear", "transmission", "kupplung", "clutch", "torque", "moment"], related: ["powertrain_motor", "emobility"] },
  { key: "emobility", label: "E-Mobilitaet", role: "plant", terms: ["elektromotor", "emotor", "electricmotor", "inverter", "traction", "hv", "hochvolt", "charging", "laden", "ladegeraet", "obc", "dcdc"], related: ["powertrain_motor", "powertrain_transmission", "energy"] },
  { key: "energy", label: "Energie / HV", role: "infrastructure", terms: ["energie", "energy", "batterie", "battery", "bms", "bordnetz", "alternator", "generator", "spannung", "voltage", "strom", "current", "zellspannung", "soc", "soh"], related: ["emobility", "powertrain_motor", "body_comfort"] },
  { key: "chassis", label: "Fahrdynamik", role: "controller", terms: ["bremse", "brake", "lenkung", "steering", "fahrwerk", "suspension", "reifen", "tire", "rad", "wheel", "yaw", "pitch", "roll"], related: ["driver_assistance", "powertrain_motor"] },
  { key: "driver_assistance", label: "Fahrerassistenz", role: "source", terms: ["adas", "fahrerassistenz", "radar", "kamera", "camera", "lidar", "park", "parking", "spur", "lane", "ultraschall"], related: ["chassis", "body_comfort"] },
  { key: "body_comfort", label: "Karosserie / Komfort", role: "actuation", terms: ["karosserie", "body", "bodycontrol", "comfort", "komfort", "wischer", "wiper", "tuer", "tuere", "door", "fenster", "window", "seat", "sitz", "keyless", "wegfahrsperre", "heckklappe", "tailgate", "schiebedach", "sunroof"], related: ["energy", "lighting", "climate"] },
  { key: "climate", label: "Klima / Thermik", role: "actuation", terms: ["klima", "climate", "hvac", "thermal", "kuehlung", "cooling", "coolant", "thermo", "compressor", "kompressor"], related: ["energy", "body_comfort", "emobility"] },
  { key: "lighting", label: "Licht", role: "actuation", terms: ["licht", "light", "lamp", "illumination", "scheinwerfer"], related: ["body_comfort", "energy"] },
  { key: "infotainment", label: "Infotainment", role: "service", terms: ["infotainment", "display", "kombiinstrument", "headup", "audio", "sound", "telematik", "navigation", "connectivity", "konnektivitaet"], related: ["body_comfort", "diagnostics"] },
  { key: "diagnostics", label: "Diagnose", role: "service", terms: ["diagnose", "diagnostic", "service", "uds", "obd", "logging", "trace"], related: ["powertrain_motor", "energy", "infotainment"] },
];

const INDUSTRY_RULES: Partial<Record<TopologyClusterProfileKey, TopologyClusterRule[]>> = {
  automotive: AUTOMOTIVE_RULES,
  generic: GENERIC_RULES,
  industrial_automation: [
    { key: "motion", label: "Antriebe / Achsen", role: "actuation", terms: ["drive", "axis", "achse", "motor", "servo", "umrichter"], related: ["control", "safety"] },
    { key: "control", label: "PLC / Steuerung", role: "controller", terms: ["plc", "steuerung", "controller", "io", "ioline"], related: ["motion", "safety", "process"] },
    { key: "process", label: "Prozess", role: "plant", terms: ["process", "prozess", "anlage", "maschine", "station", "batch"], related: ["control", "motion"] },
    { key: "safety", label: "Safety", role: "service", terms: ["safety", "sicher", "notaus", "estop"], related: ["control", "motion"] },
  ],
  energy: [
    { key: "battery", label: "Batterie / Speicher", role: "plant", terms: ["battery", "batterie", "bms", "soc", "soh", "storage"], related: ["inverter", "grid"] },
    { key: "inverter", label: "Inverter / PCS", role: "actuation", terms: ["inverter", "inv", "pcs", "converter", "umrichter"], related: ["battery", "grid"] },
    { key: "grid", label: "Netz / Schutz", role: "infrastructure", terms: ["grid", "netz", "breaker", "schalter", "frequency", "schutz"], related: ["inverter", "metering"] },
    { key: "metering", label: "Messung", role: "source", terms: ["meter", "messung", "voltage", "current", "power"], related: ["grid"] },
  ],
};

const PROFILE_ORDER: Record<string, string[]> = {
  automotive: ["powertrain_motor", "powertrain_exhaust", "powertrain_transmission", "emobility", "energy", "chassis", "driver_assistance", "body_comfort", "climate", "lighting", "infotainment", "diagnostics"],
  generic: ["control", "sensorics", "actuation", "energy", "diagnostics"],
};

const PROFILE_FAMILIES: Partial<Record<TopologyClusterProfileKey, Record<string, { key: string; label: string }>>> = {
  automotive: {
    powertrain_motor: { key: "powertrain", label: "Antriebsstrang" },
    powertrain_exhaust: { key: "powertrain", label: "Antriebsstrang" },
    powertrain_transmission: { key: "powertrain", label: "Antriebsstrang" },
    emobility: { key: "powertrain", label: "Antriebsstrang" },
    energy: { key: "energy", label: "Energieversorgung" },
    chassis: { key: "chassis", label: "Fahrwerk / Fahrdynamik" },
    driver_assistance: { key: "driver_assistance", label: "Fahrerassistenz" },
    body_comfort: { key: "body_comfort", label: "Karosserie / Komfort" },
    climate: { key: "climate", label: "Klima / Thermik" },
    lighting: { key: "body_comfort", label: "Karosserie / Komfort" },
    infotainment: { key: "infotainment", label: "Infotainment" },
    diagnostics: { key: "diagnostics", label: "Diagnose" },
  },
  industrial_automation: {
    motion: { key: "machine", label: "Maschine / Motion" },
    control: { key: "machine", label: "Maschine / Motion" },
    process: { key: "process", label: "Prozess" },
    safety: { key: "safety", label: "Safety" },
  },
  energy: {
    battery: { key: "conversion", label: "Speicher / Umwandlung" },
    inverter: { key: "conversion", label: "Speicher / Umwandlung" },
    grid: { key: "grid", label: "Netz / Schutz" },
    metering: { key: "grid", label: "Netz / Schutz" },
  },
};

const PROFILE_SYSTEM_ALIASES: Partial<Record<TopologyClusterProfileKey, Record<string, string>>> = {
  automotive: {
    motion: "motorsteuerung",
    antrieb: "motorsteuerung",
    antriebs: "motorsteuerung",
    motor: "motorsteuerung",
    motorsteuergeraet: "motorsteuerung",
    motorsteuerung: "motorsteuerung",
    getriebe: "getriebesteuerung",
    getriebesteuergeraet: "getriebesteuerung",
    getriebesteuerung: "getriebesteuerung",
    lenkungs: "lenkung",
    lenkung: "lenkung",
    klima: "klimatisierung",
    klimatisierung: "klimatisierung",
    thermal: "thermomanagement",
    thermomanagement: "thermomanagement",
  },
};

export function normalizeTopologyClusterText(value: unknown) {
  return String(value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ä/g, "ae")
    .replace(/ö/g, "oe")
    .replace(/ü/g, "ue")
    .replace(/ß/g, "ss")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function compact(value: unknown) {
  return normalizeTopologyClusterText(value).replace(/\s+/g, "");
}

function rulesFor(profile: TopologyClusterProfileKey) {
  return [...(INDUSTRY_RULES[profile] ?? []), ...GENERIC_RULES];
}

export function resolveTopologyClusterProfile(industry?: string): TopologyClusterProfileKey {
  const key = compact(industry);
  return PROFILE_ALIASES[key] ?? "generic";
}

export function inferTopologyClusterProfileFromText(text: string, industry?: string): TopologyClusterProfileKey {
  const explicit = compact(industry);
  if (explicit && PROFILE_ALIASES[explicit]) return PROFILE_ALIASES[explicit];
  const normalized = normalizeTopologyClusterText(text);
  const compactText = compact(text);
  const scored = (Object.keys(INDUSTRY_RULES) as TopologyClusterProfileKey[])
    .filter((profile) => profile !== "generic")
    .map((profile) => ({
      profile,
      score: (INDUSTRY_RULES[profile] ?? []).reduce((total, rule) => (
        total + rule.terms.reduce((subtotal, term) => {
          const needle = compact(term);
          return subtotal + (needle.length >= 4 && (compactText.includes(needle) || normalized.includes(normalizeTopologyClusterText(term))) ? 1 : 0);
        }, 0)
      ), 0),
    }))
    .sort((left, right) => right.score - left.score);
  return scored[0] && scored[0].score >= 3 ? scored[0].profile : "generic";
}

export function topologyClusterForText(text: string, industry?: string) {
  const profile = inferTopologyClusterProfileFromText(text, industry);
  const normalized = normalizeTopologyClusterText(text);
  const compactText = compact(text);
  const tokens = new Set(normalized.split(/\s+/).filter(Boolean));
  const scoreRules = (rules: TopologyClusterRule[]) => rules
    .map((rule, index) => ({
      index,
      rule,
      score: rule.terms.reduce((total, term) => {
        const needle = compact(term);
        return total + (tokens.has(needle) || (needle.length >= 4 && compactText.includes(needle)) ? needle.length : 0);
      }, 0),
    }))
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score || left.index - right.index);
  const industryMatches = scoreRules(INDUSTRY_RULES[profile] ?? []);
  const scored = industryMatches.length > 0 ? industryMatches : scoreRules(GENERIC_RULES);
  return scored[0]?.rule ?? {
    key: `system:${compactText || "unknown"}`,
    label: normalized ? normalized.replace(/\b\w/g, (char) => char.toUpperCase()) : "System",
    role: "controller" as const,
    terms: [],
    related: [],
  };
}

export function topologyClusterAffinity(leftKey: string, rightKey: string, industry?: string, lessons: TopologyClusterLesson[] = []) {
  if (!leftKey || !rightKey || leftKey === rightKey) return leftKey === rightKey ? 1000 : 0;
  const profile = resolveTopologyClusterProfile(industry);
  const rules = rulesFor(profile);
  const left = rules.find((rule) => rule.key === leftKey);
  const right = rules.find((rule) => rule.key === rightKey);
  const profileScore = (left?.related.includes(rightKey) ? 80 : 0) + (right?.related.includes(leftKey) ? 80 : 0);
  const lessonScore = lessons
    .filter((lesson) => (lesson.left === leftKey && lesson.right === rightKey) || (lesson.left === rightKey && lesson.right === leftKey))
    .reduce((total, lesson) => total + Math.min(120, lesson.weight * 18), 0);
  return profileScore + lessonScore;
}

export function compareTopologyClusterKeys(leftKey: string, rightKey: string, industry?: string) {
  const profile = resolveTopologyClusterProfile(industry);
  const order = PROFILE_ORDER[profile] ?? PROFILE_ORDER.generic;
  const leftIndex = order.indexOf(leftKey);
  const rightIndex = order.indexOf(rightKey);
  return (leftIndex < 0 ? Number.MAX_SAFE_INTEGER : leftIndex) - (rightIndex < 0 ? Number.MAX_SAFE_INTEGER : rightIndex)
    || leftKey.localeCompare(rightKey, "de");
}

export function topologyClusterFamilyForKey(clusterKey: string, industry?: string) {
  const profile = resolveTopologyClusterProfile(industry);
  const configured = PROFILE_FAMILIES[profile]?.[clusterKey];
  if (configured) return configured;
  const rule = rulesFor(profile).find((candidate) => candidate.key === clusterKey);
  return { key: clusterKey, label: rule?.label ?? "Systemgruppe" };
}

export function topologySystemIdentityForText(text: string, industry?: string) {
  const profile = resolveTopologyClusterProfile(industry);
  const normalized = normalizeTopologyClusterText(text)
    .replace(/\b(?:ecu|gateway|controller|steuergeraet|steuergerat)\b(?:\s+\d+)?$/i, "")
    .trim();
  const key = normalized.replace(/\s+/g, "") || "system";
  return PROFILE_SYSTEM_ALIASES[profile]?.[key] ?? key;
}

function lessonStorageKey(projectId: string) {
  return `${LEARNING_STORAGE_PREFIX}${projectId || "default"}`;
}

export function readTopologyClusterLessons(projectId: string): TopologyClusterLesson[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(lessonStorageKey(projectId)) ?? "[]") as TopologyClusterLesson[];
    return Array.isArray(parsed) ? parsed.filter((item) => item.left && item.right && Number.isFinite(item.weight)) : [];
  } catch {
    return [];
  }
}

export function recordTopologyClusterNeighborLesson(projectId: string, left: string, right: string) {
  if (typeof window === "undefined" || !left || !right || left === right) return;
  const [first, second] = [left, right].sort();
  const lessons = readTopologyClusterLessons(projectId);
  const existing = lessons.find((lesson) => lesson.left === first && lesson.right === second);
  const next = existing
    ? lessons.map((lesson) => lesson === existing ? { ...lesson, weight: lesson.weight + 1, updatedAt: new Date().toISOString() } : lesson)
    : [...lessons, { left: first, right: second, weight: 1, updatedAt: new Date().toISOString() }];
  window.localStorage.setItem(lessonStorageKey(projectId), JSON.stringify(next.slice(-80)));
}

export function topologyClusterKnowledgeSummary(projectId: string, industry?: string) {
  const lessons = readTopologyClusterLessons(projectId);
  const profile = resolveTopologyClusterProfile(industry);
  const rules = rulesFor(profile);
  const ruleSummary = rules
    .map((rule) => `${rule.label}: ${rule.related.join(", ") || "keine feste Nachbarschaft"}`)
    .slice(0, 14);
  const lessonSummary = lessons
    .sort((left, right) => right.weight - left.weight)
    .slice(0, 12)
    .map((lesson) => `${lesson.left} neben ${lesson.right} (${lesson.weight})`);
  return {
    profile,
    ruleSummary,
    lessonSummary,
  };
}
