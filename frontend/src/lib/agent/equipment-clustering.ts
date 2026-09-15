import { addAutomotiveFunctionOutputs, isEngineeringControllerDevice, normalizeHardwareName, type ExtractedEngineeringChain } from "./engineering-specification.ts";
import type { EquipmentAssignmentLearningSuggestion } from "../engineering-api.ts";
import {
  compareTopologyClusterKeys,
  resolveTopologyClusterProfile,
  topologyClusterFamilyForKey,
  topologyClusterForText,
} from "../topology-cluster-knowledge.ts";

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
  tree?: EquipmentEcuBranch[];
  unassigned?: EquipmentDeviceLeaf[];
  hmi_routes?: EquipmentHmiRoute[];
  validation?: { valid: boolean; warnings: string[] };
};

export type EquipmentDeviceLeaf = {
  name: string;
  deviceType: string;
  interfaceType: string;
  confidence: number;
  reason: string;
};

export type EquipmentTermMeaning = {
  english: string;
  german: string;
  system: string;
};

const EQUIPMENT_MEANINGS: Array<{ pattern: RegExp; meaning: EquipmentTermMeaning }> = [
  { pattern: /ambienttemperature/i, meaning: { english: "Ambient temperature", german: "Außentemperatur", system: "Klima / Thermik" } },
  { pattern: /accessorycurrent/i, meaning: { english: "Accessory electrical current", german: "Stromaufnahme der Nebenverbraucher", system: "Energieversorgung / Bordnetz" } },
  { pattern: /suspensiontravel/i, meaning: { english: "Suspension travel", german: "Federweg", system: "Fahrwerk / Fahrdynamik" } },
  { pattern: /damperposition/i, meaning: { english: "Damper position", german: "Dämpferposition", system: "Fahrwerk / Fahrdynamik" } },
  { pattern: /tirepressure/i, meaning: { english: "Tire pressure", german: "Reifendruck", system: "Fahrwerk / Fahrdynamik" } },
  { pattern: /airbag/i, meaning: { english: "Airbag / restraint system", german: "Airbag- / Rückhaltesystem", system: "Passive Sicherheit" } },
  { pattern: /door/i, meaning: { english: "Door control", german: "Türsteuerung", system: "Karosserie / Komfort" } },
  { pattern: /seat/i, meaning: { english: "Seat control", german: "Sitzsteuerung", system: "Karosserie / Komfort" } },
  { pattern: /batterytemperature/i, meaning: { english: "Battery temperature", german: "Batterietemperatur", system: "Energieversorgung" } },
  { pattern: /batteryvoltage/i, meaning: { english: "Battery voltage", german: "Batteriespannung", system: "Energieversorgung" } },
  { pattern: /batterycurrent/i, meaning: { english: "Battery current", german: "Batteriestrom", system: "Energieversorgung" } },
];

export function equipmentTermMeaning(name: string): EquipmentTermMeaning {
  const known = EQUIPMENT_MEANINGS.find((entry) => entry.pattern.test(name))?.meaning;
  if (known) return known;
  const readable = keyText(name).replace(/\b\w/g, (char) => char.toUpperCase());
  return { english: readable || name, german: "Keine eindeutige Fachübersetzung hinterlegt", system: "Fachliche Zuordnung prüfen" };
}

export type EquipmentEcuBranch = {
  name: string;
  interfaceType: string;
  functions?: Array<{ name: string; signals: string[] }>;
  sensors: EquipmentDeviceLeaf[];
  actuators: EquipmentDeviceLeaf[];
};

export type EquipmentHmiRoute = {
  source: string;
  target: string;
  signals: string[];
  excluded_signals?: string[];
  path: string[];
};

export function hmiSignalKey(route: EquipmentHmiRoute, signal: string) {
  return JSON.stringify([route.source, route.target, signal]);
}

export function selectHmiSignals(routes: EquipmentHmiRoute[], selections: Record<string, boolean> = {}): EquipmentHmiRoute[] {
  return routes.map(route => ({ ...route,
    signals: route.signals.filter(signal => selections[hmiSignalKey(route, signal)] === true),
    excluded_signals: route.signals.filter(signal => selections[hmiSignalKey(route, signal)] !== true),
  }));
}

export type EquipmentCluster = {
  id: string;
  label: string;
  recommendation: string;
  recommendedNetworkId: string;
  recommendedNetworkLabel: string;
  counts: Record<string, number>;
  devices: ExtractedEngineeringChain[];
  evidence: string[];
  clusterKey: string;
  controllers: EquipmentEcuBranch[];
  unassigned: EquipmentDeviceLeaf[];
  hmiRoutes: EquipmentHmiRoute[];
};

const CLUSTER_RULES: Array<{ id: string; label: string; terms: string[]; preferredNetworks: string[]; recommendation: string }> = [
  {
    id: "climate",
    label: "Klima",
    terms: ["klima", "klimatisierung", "climate", "kuehlkreislauf", "hvac", "heizung", "heater", "ventilation", "blower", "cabin", "innenraum", "ambient", "aussen", "thermo", "thermal", "thermomanagement", "coolant", "kuehlmittel", "compressor", "kompressor", "refrigerant", "kaeltemittel"],
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
    terms: ["drive", "motion", "antrieb", "drehmoment", "engine", "motor", "elektromotor", "gear", "getriebe", "transmission", "traction", "steering", "lenkung", "hinterachslenkung", "accelerator", "fahrpedal", "clutch", "kupplung", "throttle", "drossel", "boost", "intake", "ansaugluft", "turbo", "oil", "oel", "kraftstoff", "fuel", "exhaust", "abgas", "abgasnachbehandlung", "egr", "agrventil", "urea", "harnstoff"],
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
  return FALLBACK_CLUSTER_BY_DEVICE_TYPE[chain.device_type]
    ?? (isEngineeringControllerDevice(chain.device_type) ? FALLBACK_CLUSTER_BY_DEVICE_TYPE.ECU : undefined)
    ?? {
    id: `system:${slug(inferredSystemName(chain))}`,
    label: displayLabel(inferredSystemName(chain)),
    preferredNetworks: [chain.interface_type, "canfd", "can", "lin"],
    recommendation: "Fachlich zusammenhaengende Teilnehmer als Systemrahmen pruefen.",
  };
}

function profilePreferences(profile: string, familyKey: string, devices: ExtractedEngineeringChain[]) {
  const critical = devices.some((chain) => chain.cycle_ms <= 20)
    || /safety|brake|traction|powertrain|fahrwerk|signalling/.test(familyKey);
  const highBandwidth = devices.some((chain) => /ethernet/i.test(chain.interface_type))
    || /infotainment|passenger|wayside|diagnostics/.test(familyKey);
  if (profile === "rail" && highBandwidth) return ["trdp", "etb", "ethernet", "wtb", "mvb"];
  if (profile === "rail" && critical) return ["mvb", "etb", "wtb", "can", "lin"];
  if (profile === "rail") return ["mvb", "wtb", "etb", "trdp"];
  if (highBandwidth) return ["ethernet", "canfd", "can", "lin"];
  if (critical) return ["canfd", "ethernet", "can", "lin"];
  if (profile === "automotive" && /body|climate|lighting/.test(familyKey)) return ["lin", "canfd", "can"];
  return ["canfd", "can", "ethernet", "lin"];
}

function instanceOrdinal(value: string) {
  return Number(value.match(/(?:-|_|\s)(\d+)$/)?.[1] ?? 1);
}

function ownershipStem(value: string) {
  return compactKey(normalizeHardwareName(value))
    .replace(/\d+$/, "")
    .replace(/(?:schaltausgang|stellglied|actuator|aktuator|aktor|sensor|controller|steuergeraet|steuerung|control|erfassung|plc|sps)$/g, "");
}

function deviceLeaf(chain: ExtractedEngineeringChain, confidence: number, reason: string): EquipmentDeviceLeaf {
  return {
    name: chain.hardware_name,
    deviceType: chain.device_type,
    interfaceType: chain.interface_type,
    confidence,
    reason,
  };
}

function controllerBranches(
  devices: ExtractedEngineeringChain[],
  industry?: string,
  learnedAssignments: EquipmentAssignmentLearningSuggestion[] = [],
) {
  const controllers = devices.filter((chain) => isEngineeringControllerDevice(chain.device_type));
  const endpoints = devices.filter((chain) => chain.device_type === "SensorController" || chain.device_type === "ActuatorController");
  const branches = controllers.map((controller) => ({
    name: controller.hardware_name,
    interfaceType: controller.interface_type,
    sensors: [] as EquipmentDeviceLeaf[],
    actuators: [] as EquipmentDeviceLeaf[],
  }));
  const unassigned: EquipmentDeviceLeaf[] = [];

  for (const endpoint of endpoints) {
    const configuredOwner = typeof endpoint.configuration?.functional_owner === "string"
      ? endpoint.configuration.functional_owner
      : "";
    const learned = learnedAssignments.find((suggestion) => compactKey(suggestion.endpoint_name) === compactKey(endpoint.hardware_name));
    const explicitOwnerName = configuredOwner || learned?.controller_name || "";
    const explicitOwner = controllers.find((controller) => compactKey(controller.hardware_name) === compactKey(explicitOwnerName));
    if (explicitOwner) {
      const branch = branches.find((candidate) => candidate.name === explicitOwner.hardware_name)!;
      const leaf = deviceLeaf(
        endpoint,
        learned?.confidence ?? 1,
        configuredOwner ? endpoint.configuration?.functional_owner_source === 'explicit_user_statement'
          ? "Vom Nutzer ausdrücklich diesem Controller zugeordnet."
          : "Vom Vollständigkeitsgenerator fachlich an diesen Controller gebunden."
          : learned?.reason ?? "Aus bestätigter Controller-Zuordnung übernommen.",
      );
      if (endpoint.device_type === "SensorController") branch.sensors.push(leaf);
      else branch.actuators.push(leaf);
      continue;
    }
    const endpointStem = ownershipStem(endpoint.hardware_name);
    const endpointCluster = topologyClusterForText(chainCorpus(endpoint), industry);
    const ranked = controllers
      .map((controller, index) => {
        const controllerStem = ownershipStem(controller.hardware_name);
        const sameStem = endpointStem.length >= 4 && controllerStem.length >= 4
          && (endpointStem.includes(controllerStem) || controllerStem.includes(endpointStem));
        const sameOrdinal = instanceOrdinal(endpoint.hardware_name) === instanceOrdinal(controller.hardware_name);
        const sameSystem = topologyClusterForText(chainCorpus(controller), industry).key === endpointCluster.key;
        return { controller, index, score: (sameStem ? 1_000 : 0) + (sameOrdinal ? 80 : 0) + (sameSystem ? 160 : 0) };
      })
      .sort((left, right) => right.score - left.score || left.controller.hardware_name.localeCompare(right.controller.hardware_name, "de"));
    const best = ranked[0];
    const tiedBest = Boolean(best && ranked[1] && ranked[1].score === best.score);
    const uniqueFamilyOwner = controllers.length === 1 ? controllers[0] : undefined;
    const owner = best?.score >= 240 && (!tiedBest || best.score >= 1_000) ? best.controller : uniqueFamilyOwner;
    if (!owner) {
      unassigned.push(deviceLeaf(endpoint, 0, controllers.length
        ? "Mehrere fachlich mögliche Controller; Zuordnung muss bestätigt werden."
        : "Kein Controller vorhanden. Controller ergänzen oder die Anforderung korrigieren."));
      continue;
    }
    const branch = branches.find((candidate) => candidate.name === owner.hardware_name)!;
    const reason = best?.score >= 1_000
      ? "Gemeinsamer Systemname und Instanzbezug."
      : best?.score >= 240
        ? "Gleicher fachlicher Systemzweig."
        : "Einziger Controller im fachlichen Systemzweig.";
    const leaf = deviceLeaf(endpoint, best?.score >= 1_000 ? 0.98 : best?.score >= 240 ? 0.82 : 0.68, reason);
    if (endpoint.device_type === "SensorController") branch.sensors.push(leaf);
    else branch.actuators.push(leaf);
  }
  return { branches, unassigned };
}

function graphClusterFor(chain: ExtractedEngineeringChain, industry: string) {
  const cluster = topologyClusterForText(chainCorpus(chain), industry);
  const family = topologyClusterFamilyForKey(cluster.key, industry);
  return {
    id: `family:${family.key}`,
    key: cluster.key,
    familyKey: family.key,
    label: family.label,
  };
}

function displayRoutesForClusters(clusters: EquipmentCluster[], allDevices: ExtractedEngineeringChain[]) {
  const hmis = uniqueDevices(allDevices).filter((chain) => isEngineeringControllerDevice(chain.device_type)
    && /kombiinstrument|headup|display|anzeige|infotainment|passengerinformation|fahrgastinformation|hmi/i.test(chain.hardware_name));
  if (!hmis.length) return;
  for (const cluster of clusters) {
    const sources = cluster.devices.filter((chain) => isEngineeringControllerDevice(chain.device_type));
    cluster.hmiRoutes = sources.flatMap((source) => hmis.filter(target => target.hardware_name !== source.hardware_name).map((target) => ({
      source: source.hardware_name,
      target: target.hardware_name,
      signals: [...new Set(allDevices
        .filter((chain) => chain.hardware_name === source.hardware_name)
        .map((chain) => chain.signal_name || chain.signal_display_name)
        .filter(Boolean))],
      path: [source.hardware_name, cluster.recommendedNetworkLabel, "Gateway", target.hardware_name],
    })));
  }
}

export type EquipmentClusterIssue = {
  code: "lin-cycle" | "lin-cluster" | "owner";
  message: string;
  action: string;
  affected: Array<{ name: string; detail: string }>;
};

export function reviewedEquipmentCluster(cluster: EquipmentCluster, assignment: EquipmentClusterAssignment, chains: ExtractedEngineeringChain[]): EquipmentCluster {
  const controllers = assignment.tree ?? cluster.controllers;
  const unassigned = assignment.unassigned ?? cluster.unassigned;
  const names = new Set([...controllers.flatMap(branch => [branch.name, ...branch.sensors.map(leaf => leaf.name), ...branch.actuators.map(leaf => leaf.name)]), ...unassigned.map(leaf => leaf.name)]);
  return { ...cluster, controllers, unassigned, devices: chains.filter(chain => names.has(chain.hardware_name)) };
}

export function equipmentClusterBusIssues(cluster: EquipmentCluster, networkId: string, networkLabel = ""): EquipmentClusterIssue[] {
  const network = compactKey(`${networkId} ${networkLabel}`);
  const issues: EquipmentClusterIssue[] = [];
  const fast = cluster.devices.filter(chain => Number.isFinite(chain.cycle_ms) && chain.cycle_ms > 0 && chain.cycle_ms <= 20);
  if (network.includes("lin") && fast.length) {
    issues.push({ code: "lin-cycle", message: `LIN-Prüfregel: ${new Set(fast.map(chain => chain.hardware_name)).size} Teilnehmer mit Zykluszeit ≤ 20 ms.`,
      action: "Bustechnik dieses Clusters prüfen oder die betroffenen Teilnehmer einem geeigneten Buszweig zuordnen. Die Zykluszeit nicht nur zur Beseitigung der Warnung erhöhen; Kapazität und funktionales Timing separat nachweisen.",
      affected: fast.map(chain => ({ name: chain.hardware_name, detail: `${chain.signal_display_name || chain.signal_name || chain.message_name}: ${chain.cycle_ms} ms · Schnittstelle ${chain.interface_type}` })) });
  }
  if (network.includes("lin") && /safety|bremse|antrieb|traction|fahrwerk|signalling/.test(cluster.label.toLowerCase())) {
    issues.push({ code: "lin-cluster", message: `Bustechnik des gesamten Clusters „${cluster.label}“: LIN erfordert eine begründete Ausnahme.`,
      action: "Die Prüfregel stammt aus der Clusterbezeichnung, nicht aus einem nachgewiesenen Fehler eines einzelnen Geräts. Bustechnik und Funktionsanforderungen dieses Systemzweigs prüfen.", affected: [] });
  }
  if (cluster.unassigned.length) issues.push({ code: "owner", message: `${cluster.unassigned.length} Sensoren/Aktoren ohne eindeutige Controller-Zuordnung.`,
    action: "Diese Teilnehmer im Bereich ohne Controller-Zuordnung zuordnen.",
    affected: cluster.unassigned.map(leaf => ({ name: leaf.name, detail: leaf.reason })) });
  return issues;
}

export function equipmentClusterBusWarnings(cluster: EquipmentCluster, networkId: string, networkLabel = "") {
  return equipmentClusterBusIssues(cluster, networkId, networkLabel).map(issue =>
    `${issue.message} ${issue.action}${issue.affected.length ? ` Betroffen: ${issue.affected.map(item => `${item.name} (${item.detail})`).join("; ")}` : ""}`);
}

export function buildEquipmentClusters(
  chains: ExtractedEngineeringChain[],
  networkOptions: EquipmentNetworkOption[],
  industry?: string,
  learnedAssignments: EquipmentAssignmentLearningSuggestion[] = [],
): EquipmentCluster[] {
  chains = addAutomotiveFunctionOutputs(chains, chains[0]?.domain || industry || "");
  const profile = resolveTopologyClusterProfile(industry || chains[0]?.domain);
  const graphMode = Boolean(industry);
  const buckets = new Map<string, { label: string; clusterKey: string; recommendation: string; preferredNetworks: string[]; devices: ExtractedEngineeringChain[] }>();
  const controllerGraphs = graphMode
    ? uniqueDevices(chains)
      .filter((chain) => isEngineeringControllerDevice(chain.device_type))
      .map((chain) => ({ name: chain.hardware_name, stem: ownershipStem(chain.hardware_name), graph: graphClusterFor(chain, profile) }))
    : [];

  chains
    .filter((chain) => chain.device_type !== "Gateway")
    .forEach((chain) => {
      const stem = ownershipStem(chain.hardware_name);
      const configuredOwner = typeof chain.configuration?.functional_owner === "string" ? chain.configuration.functional_owner : "";
      const learnedOwner = learnedAssignments.find((suggestion) => compactKey(suggestion.endpoint_name) === compactKey(chain.hardware_name))?.controller_name ?? "";
      const ownerName = configuredOwner || learnedOwner;
      const inheritedGraph = (chain.device_type === "SensorController" || chain.device_type === "ActuatorController")
        ? controllerGraphs.find((candidate) => ownerName && compactKey(candidate.name) === compactKey(ownerName))?.graph
          ?? controllerGraphs.find((candidate) => stem.length >= 3 && candidate.stem === stem)?.graph
          ?? (controllerGraphs.length === 1 ? controllerGraphs[0].graph : undefined)
        : undefined;
      const graph = graphMode ? inheritedGraph ?? controllerGraphs.find(candidate => candidate.name === chain.hardware_name)?.graph ?? graphClusterFor(chain, profile) : null;
      const rule = ruleFor(chain);
      const explicit = explicitSystemName(chain);
      const fallback = explicit ? null : fallbackClusterFor(chain);
      const label = graph?.label ?? rule?.label ?? displayLabel(explicit || fallback?.label || inferredSystemName(chain));
      const id = graph?.id ?? (rule ? `rule:${rule.id}` : explicit ? `system:${slug(label)}` : fallback?.id ?? `system:${slug(label)}`);
      const bucket = buckets.get(id) ?? {
        label,
        clusterKey: graph?.key ?? rule?.id ?? id,
        recommendation: rule?.recommendation ?? fallback?.recommendation ?? "Fachlich zusammenhaengende Teilnehmer als Systemrahmen pruefen.",
        preferredNetworks: rule?.preferredNetworks ?? fallback?.preferredNetworks ?? [chain.interface_type, "canfd", "can", "lin"],
        devices: [],
      };
      bucket.devices.push(chain);
      buckets.set(id, bucket);
    });

  const clusters = [...buckets.entries()]
    .map(([id, bucket]) => {
      const sortedDevices = uniqueDevices(bucket.devices).sort((left, right) => left.hardware_name.localeCompare(right.hardware_name, "de"));
      const preferences = graphMode ? profilePreferences(profile, id, sortedDevices) : bucket.preferredNetworks;
      const network = recommendedNetwork(networkOptions, preferences);
      const ownership = controllerBranches(sortedDevices, profile, learnedAssignments);
      for (const branch of ownership.branches as EquipmentEcuBranch[]) {
        const functions = new Map<string, string[]>();
        for (const chain of chains.filter(item => item.hardware_name === branch.name && item.configuration?.functional_output_template)) {
          functions.set(chain.function_name, [...new Set([...(functions.get(chain.function_name) ?? []), chain.signal_name])]);
        }
        branch.functions = [...functions].map(([name, signals]) => ({ name, signals }));
      }
      return {
        id,
        label: bucket.label,
        clusterKey: bucket.clusterKey,
        recommendation: bucket.recommendation,
        recommendedNetworkId: network.id,
        recommendedNetworkLabel: network.label,
        counts: deviceCounts(sortedDevices),
        devices: sortedDevices,
        evidence: sortedDevices.slice(0, 6).map((chain) => chain.hardware_name),
        controllers: ownership.branches,
        unassigned: ownership.unassigned,
        hmiRoutes: [],
      };
    })
    .sort((left, right) => compareTopologyClusterKeys(left.clusterKey, right.clusterKey, profile)
      || left.label.localeCompare(right.label, "de"));
  displayRoutesForClusters(clusters, chains);
  return clusters;
}

export function equipmentClusterSummary(assignments: EquipmentClusterAssignment[]) {
  return assignments
    .filter((assignment) => assignment.selected)
    .map((assignment) => `${assignment.label} -> ${assignment.network_label} / ${assignment.bus_name} (${assignment.devices} Teilnehmer)`)
    .join("; ");
}

export function equipmentClusterGraphPrompt(assignments: EquipmentClusterAssignment[], architectureId?: string) {
  return assignments
    .filter((assignment) => assignment.selected)
    .map((assignment) => ({
      cluster_id: assignment.cluster_id,
      label: assignment.label,
      network_id: assignment.network_id,
      network_label: assignment.network_label,
      bus_name: assignment.bus_name,
      ...(architectureId === 'sensor_ecu_actuator' ? { controller_status_scope: 'INTERNAL' } : {}),
      controllers: (assignment.tree ?? []).map((controller) => ({
        ecu: controller.name,
        sensors: controller.sensors.map((sensor) => sensor.name),
        actuators: controller.actuators.map((actuator) => actuator.name),
      })),
      unassigned: (assignment.unassigned ?? []).map((device) => device.name),
      hmi_routes: (assignment.hmi_routes ?? []).map((route) => ({
        source: route.source,
        target: route.target,
        signals: route.signals,
        ...(route.excluded_signals ? { excluded_signals: route.excluded_signals } : {}),
        path: route.path,
      })),
      warnings: assignment.validation?.warnings ?? [],
    }));
}
