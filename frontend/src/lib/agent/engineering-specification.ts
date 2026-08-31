/** Device roles belong to device_type; technical identifiers remain unchanged. */
export function normalizeHardwareName(value: string): string {
  const original = value.trim();
  return original.replace(/(?:[-_ ]?(?:ECU|Gateway|Sensor|Aktor|Aktuator|Actuator|Controller|Steuerger(?:ä|ae|a|�)t))+([-_ ]\d+)?$/i, "$1")
    .replace(/^[-_ ]+|[-_ ]+$/g, "") || original;
}

export type ExtractedEngineeringChain = {
  hardware_name: string;
  hardware_description: string;
  device_type: string;
  function_name: string;
  function_description: string;
  interface_name: string;
  interface_type: string;
  message_name: string;
  message_id_hex: string;
  direction: "tx";
  cycle_ms: number;
  dlc: number;
  signal_name: string;
  signal_display_name: string;
  start_bit: number;
  length_bits: number;
  byte_order: "little_endian";
  data_type: "signed" | "unsigned";
  factor: number;
  offset_value: number;
  unit?: string;
  min_value?: number;
  max_value?: number;
  domain: string;
};

export type ExtractedEngineeringSpecification = {
  chains: ExtractedEngineeringChain[];
  domain: string;
  interfaceType: string;
  communicationSystems: string[];
  networkArchitecture: NetworkArchitectureMode;
  targetCounts: EngineeringTargetCounts;
};

export type NetworkArchitectureMode = "eva" | "ecu_gateway" | "gateway_direct" | "hybrid_ai";

export type EngineeringHardwareCounts = {
  sensors: number;
  actuators: number;
  ecus: number;
  gateways: number;
};

export type EngineeringTargetCounts = EngineeringHardwareCounts & {
  explicit: boolean;
};

type ArchitectureTemplate = {
  hardwareName: string;
  deviceType: "SensorController" | "ActuatorController" | "ECU" | "Gateway";
  signalName: string;
  interfaceType: string;
  cycleMs: number;
  unit?: string;
  minValue?: number;
  maxValue?: number;
  factor?: number;
};

type HardwareOccurrence = {
  index: number;
  name: string;
};

function generatedSignalBitLength(input: {
  minValue?: number;
  maxValue?: number;
  factor?: number;
  offsetValue?: number;
  dataType?: "signed" | "unsigned";
}) {
  const min = typeof input.minValue === "number" && Number.isFinite(input.minValue) ? input.minValue : 0;
  const max = typeof input.maxValue === "number" && Number.isFinite(input.maxValue) ? input.maxValue : 255;
  const factor = typeof input.factor === "number" && Number.isFinite(input.factor) && input.factor !== 0 ? input.factor : 1;
  const offset = typeof input.offsetValue === "number" && Number.isFinite(input.offsetValue) ? input.offsetValue : 0;
  const rawValues = [min, max].map((value) => Math.round((value - offset) / factor));
  const rawMin = Math.min(...rawValues);
  const rawMax = Math.max(...rawValues);
  const signed = input.dataType === "signed" || rawMin < 0;
  for (let width = 1; width <= 64; width += 1) {
    if (signed) {
      if (rawMin >= -(2 ** (width - 1)) && rawMax < 2 ** (width - 1)) return width;
    } else if (rawMax < 2 ** width) {
      return width;
    }
  }
  return 64;
}

function generatedMessageDlc(lengthBits: number) {
  return Math.max(1, Math.ceil(Math.max(1, lengthBits) / 8));
}

const INLINE_HARDWARE_PATTERN = /\b[\p{L}\d][\p{L}\d_-]*(?:sensor|actuator|aktuator|aktor|ecu|gateway|plc|controller|steuergeraet|steuergerät)\b/giu;
const GENERIC_INLINE_HARDWARE_LABELS = new Set([
  "sensor",
  "actuator", "aktuator", "aktor",
  "ecu",
  "gateway",
  "plc",
  "controller",
  "steuergeraet",
]);

const GENERIC_HARDWARE_LABELS = new Set([
  "hardware",
  "hardware objekte",
  "hardware objekt",
  "sensor",
  "sensors",
  "sensoren",
  "actuator", "actuators", "aktuator", "aktuatoren", "aktor", "aktoren",
  "ecu",
  "ecus",
  "gateway",
  "gateways",
  "plc",
  "controller",
  "steuergeraet",
]);

const PARAMETER_LABEL_PATTERN =
  /^(bereich|messbereich|signal|aufloesung|auflösung|schrittweite|sollwert|grenzwerte?|kommunikationsprotokoll|kreistellen|warnhinweis|mindest|maximum|minimum|parameter|technische parameter|funktions parameter|verwendung|aufgaben|eingänge?|eingaenge?|ausgänge?|ausgaenge?|mögliche werte|moegliche werte|beispielregeln?)/i;

const PROSE_HARDWARE_LABEL_PATTERN =
  /^(verwendung|verarbeitet|verarbeitung|kommunikation|verbindung|beispiel|beispielsweise|aufgaben?|eingänge?|eingaenge?|ausgänge?|ausgaenge?)\b/i;

const COUNT_WORDS: Record<string, number> = {
  ein: 1,
  eine: 1,
  einem: 1,
  einen: 1,
  einer: 1,
  eins: 1,
  zwei: 2,
  drei: 3,
  vier: 4,
  fuenf: 5,
  funf: 5,
  sechs: 6,
  sieben: 7,
  acht: 8,
  neun: 9,
  zehn: 10,
};

const COUNT_TOKEN = "(\\d+|ein|eine|einem|einen|einer|eins|zwei|drei|vier|fuenf|funf|sechs|sieben|acht|neun|zehn)";

export function extractNetworkArchitectureMode(text: string): NetworkArchitectureMode {
  const explicit = text.match(/Netzarchitektur-ID:\s*(eva|ecu_gateway|gateway_direct|hybrid_ai)\b/i)?.[1]
    ?.toLowerCase() as NetworkArchitectureMode | undefined;
  if (explicit) return explicit;
  if (/KI-Kombination|Kombination\s+aus\s+Variante\s*2\s*(?:\+|und)\s*3/i.test(text)) return "hybrid_ai";
  if (/Variante\s*3|Gateway-direkt/i.test(text)) return "gateway_direct";
  if (/Variante\s*2|ECU-vermittelt/i.test(text)) return "ecu_gateway";
  if (/Variante\s*1|einfaches?\s+EVA/i.test(text)) return "eva";
  return "gateway_direct";
}

const ECU_NAMES = [
  "Thermal-ECU",
  "Motion-ECU",
  "Batteriemanagement-ECU",
  "Motorsteuerung-ECU",
  "Getriebesteuerung-ECU",
  "Bremsregelung-ECU",
  "Lenkung-ECU",
  "Fahrwerk-ECU",
  "Klimatisierung-ECU",
  "BodyControl-ECU",
  "Fahrertuer-ECU",
  "Beifahrertuer-ECU",
  "FondtuerLinks-ECU",
  "FondtuerRechts-ECU",
  "Fahrersitz-ECU",
  "Beifahrersitz-ECU",
  "Aussenlicht-ECU",
  "Innenlicht-ECU",
  "Airbag-ECU",
  "Kombiinstrument-ECU",
  "Infotainment-ECU",
  "Telematik-ECU",
  "Diagnose-ECU",
  "Fahrerassistenz-ECU",
  "Energieversorgung-ECU",
  "Ladesteuerung-ECU",
  "Invertersteuerung-ECU",
  "Elektromotorsteuerung-ECU",
  "Thermomanagement-ECU",
  "Kraftstoffsystem-ECU",
  "Abgasnachbehandlung-ECU",
  "Daempferregelung-ECU",
  "Stabilitaetsregelung-ECU",
  "Reifendruckkontrolle-ECU",
  "Parkassistenz-ECU",
  "Radarverarbeitung-ECU",
  "Kameraverarbeitung-ECU",
  "Ultraschallverarbeitung-ECU",
  "Zentralrechner-ECU",
  "Konnektivitaet-ECU",
  "Wegfahrsperre-ECU",
  "KeylessEntry-ECU",
  "Wischersteuerung-ECU",
  "Schiebedach-ECU",
  "Heckklappe-ECU",
  "Anhaengersteuerung-ECU",
  "Hinterachslenkung-ECU",
  "Fahrdynamik-ECU",
  "Soundsystem-ECU",
  "HeadUpDisplay-ECU",
] as const;

const POSITIONAL_SENSOR_FAMILIES = [
  { name: "WheelSpeed", signal: "Raddrehzahl", unit: "rpm", min: 0, max: 2500, factor: 1, cycle: 5 },
  { name: "TirePressure", signal: "Reifendruck", unit: "kPa", min: 0, max: 500, factor: 1, cycle: 100 },
  { name: "TireTemperature", signal: "Reifentemperatur", unit: "degC", min: -40, max: 180, factor: 0.1, cycle: 100 },
  { name: "BrakeTemperature", signal: "Bremstemperatur", unit: "degC", min: -40, max: 900, factor: 0.5, cycle: 50 },
  { name: "SuspensionTravel", signal: "Federweg", unit: "mm", min: -150, max: 150, factor: 0.1, cycle: 10 },
  { name: "WheelLoad", signal: "Radlast", unit: "N", min: 0, max: 15000, factor: 1, cycle: 10 },
  { name: "DamperPosition", signal: "Daempferposition", unit: "%", min: 0, max: 100, factor: 0.1, cycle: 10 },
  { name: "WheelAcceleration", signal: "Radbeschleunigung", unit: "m/s2", min: -100, max: 100, factor: 0.01, cycle: 5 },
  { name: "BrakePressure", signal: "Bremsdruck", unit: "bar", min: 0, max: 250, factor: 0.1, cycle: 5 },
  { name: "WheelTorque", signal: "Raddrehmoment", unit: "Nm", min: -5000, max: 5000, factor: 1, cycle: 5 },
  { name: "WheelAngle", signal: "Radwinkel", unit: "deg", min: -60, max: 60, factor: 0.01, cycle: 10 },
  { name: "TireWear", signal: "Reifenverschleiss", unit: "mm", min: 0, max: 12, factor: 0.01, cycle: 1000 },
] as const;

const CENTRAL_SENSOR_DEFINITIONS = [
  ["CoolantTemperature", "Kuehlmitteltemperatur", "degC", -40, 150, 0.1, 20],
  ["OilTemperature", "Oeltemperatur", "degC", -40, 180, 0.1, 20],
  ["IntakeAirTemperature", "Ansauglufttemperatur", "degC", -40, 120, 0.1, 20],
  ["ExhaustGasTemperature", "Abgastemperatur", "degC", 0, 1100, 1, 10],
  ["CabinTemperature", "Innenraumtemperatur", "degC", -40, 85, 0.1, 100],
  ["AmbientTemperature", "Aussentemperatur", "degC", -50, 85, 0.1, 500],
  ["BatteryTemperature", "Batterietemperatur", "degC", -40, 100, 0.1, 50],
  ["InverterTemperature", "Invertertemperatur", "degC", -40, 180, 0.1, 20],
  ["MotorTemperature", "Motortemperatur", "degC", -40, 200, 0.1, 20],
  ["TransmissionOilTemperature", "Getriebeoeltemperatur", "degC", -40, 180, 0.1, 50],
  ["EngineSpeed", "Motordrehzahl", "rpm", 0, 9000, 1, 5],
  ["MotorSpeed", "Elektromotordrehzahl", "rpm", -20000, 20000, 1, 5],
  ["TransmissionInputSpeed", "Getriebeeingangsdrehzahl", "rpm", 0, 12000, 1, 5],
  ["TransmissionOutputSpeed", "Getriebeausgangsdrehzahl", "rpm", 0, 12000, 1, 5],
  ["TurboSpeed", "Turboladerdrehzahl", "rpm", 0, 250000, 10, 10],
  ["EngineOilPressure", "Motoroeldruck", "bar", 0, 12, 0.01, 10],
  ["FuelPressure", "Kraftstoffdruck", "bar", 0, 2500, 0.1, 10],
  ["BoostPressure", "Ladedruck", "kPa", 0, 400, 0.1, 10],
  ["RefrigerantPressure", "Kaeltemitteldruck", "bar", 0, 40, 0.01, 100],
  ["BatteryCoolantPressure", "Batteriekuehldruck", "bar", 0, 10, 0.01, 100],
  ["BatteryCurrent", "Batteriestrom", "A", -1000, 1000, 0.1, 10],
  ["MotorCurrent", "Motorstrom", "A", -1500, 1500, 0.1, 5],
  ["AlternatorCurrent", "Generatorstrom", "A", -300, 300, 0.1, 50],
  ["AccessoryCurrent", "Nebenverbraucherstrom", "A", 0, 300, 0.1, 100],
  ["BatteryVoltage", "Batteriespannung", "V", 0, 1000, 0.1, 10],
  ["DCLinkVoltage", "Zwischenkreisspannung", "V", 0, 1200, 0.1, 5],
  ["LowVoltageSupply", "Bordnetzspannung", "V", 0, 32, 0.01, 100],
  ["CellVoltageMin", "MinimaleZellspannung", "V", 0, 5, 0.001, 50],
  ["CellVoltageMax", "MaximaleZellspannung", "V", 0, 5, 0.001, 50],
  ["SteeringAngle", "Lenkwinkel", "deg", -720, 720, 0.1, 5],
  ["SteeringTorque", "Lenkmoment", "Nm", -30, 30, 0.01, 5],
  ["AcceleratorPosition", "Fahrpedalstellung", "%", 0, 100, 0.1, 10],
  ["BrakePedalPosition", "Bremspedalstellung", "%", 0, 100, 0.1, 10],
  ["ClutchPosition", "Kupplungsstellung", "%", 0, 100, 0.1, 20],
  ["GearSelectorPosition", "Gangwahlstellung", "code", 0, 15, 1, 50],
  ["ThrottlePosition", "Drosselklappenstellung", "%", 0, 100, 0.1, 10],
  ["EGRValvePosition", "AGRVentilstellung", "%", 0, 100, 0.1, 20],
  ["LongitudinalAcceleration", "Laengsbeschleunigung", "m/s2", -30, 30, 0.01, 5],
  ["LateralAcceleration", "Querbeschleunigung", "m/s2", -30, 30, 0.01, 5],
  ["VerticalAcceleration", "Vertikalbeschleunigung", "m/s2", -30, 30, 0.01, 5],
  ["YawRate", "Gierrate", "deg/s", -300, 300, 0.01, 5],
  ["PitchRate", "Nickrate", "deg/s", -300, 300, 0.01, 5],
  ["RollRate", "Rollrate", "deg/s", -300, 300, 0.01, 5],
  ["FuelLevel", "Kraftstofffuellstand", "%", 0, 100, 0.1, 500],
  ["UreaLevel", "Harnstofffuellstand", "%", 0, 100, 0.1, 500],
  ["WasherFluidLevel", "Waschwasserfuellstand", "%", 0, 100, 0.1, 1000],
  ["CoolantLevel", "Kuehlmittelfuellstand", "%", 0, 100, 0.1, 500],
  ["OilLevel", "Oelfuellstand", "%", 0, 100, 0.1, 500],
  ["FrontRadarDistance", "Frontabstand", "m", 0, 300, 0.1, 20],
  ["RearRadarDistance", "Heckabstand", "m", 0, 200, 0.1, 20],
  ["Rain", "Regenintensitaet", "%", 0, 100, 0.1, 100],
  ["AmbientLight", "Umgebungshelligkeit", "lx", 0, 150000, 1, 200],
] as const;

function cleanLabel(value: string) {
  return value
    .replace(/[*_`#]/g, "")
    .replace(/\s*:\s*$/, "")
    .replace(/\s+/g, " ")
    .trim();
}

function normalized(value: string) {
  return value
    .toLowerCase()
    .replace(/ä/g, "ae")
    .replace(/ö/g, "oe")
    .replace(/ü/g, "ue")
    .replace(/ß/g, "ss")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function countValue(value: string) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : COUNT_WORDS[value] ?? 0;
}

function specificationBody(text: string) {
  const marker = /Konkrete Aufgabe des Nutzers[^\r\n]*:/i.exec(text);
  if (!marker) return text;
  const body = text.slice(marker.index + marker[0].length);
  const end = body.search(/\r?\n\r?\n(?:Verbindliche Kanonisierung bei der Projektanlage:|Starte jetzt)/i);
  return end >= 0 ? body.slice(0, end) : body;
}

function requestedCount(text: string, nounPattern: string, modifierPattern = "") {
  const modifiers = modifierPattern ? `(?:(?:${modifierPattern})\\s+){0,2}` : "";
  const pattern = new RegExp(`\\b${COUNT_TOKEN}\\s+${modifiers}${nounPattern}\\b`, "g");
  // Numbered UI choices and adjacent lines are not hardware quantity statements.
  return text.split(/\r?\n/).reduce((maximum, line) => {
    const source = normalized(line
      .replace(/^\s*#{1,6}\s+/, "")
      .replace(/^\s*\d+[.)]\s+/, "")
      .replace(/\bVariante\s+\d+(?:\s*(?:\+|und)\s*\d+)?/gi, "Variante"));
    return [...source.matchAll(pattern)].reduce((count, match) => Math.max(count, countValue(match[1] ?? "")), maximum);
  }, 0);
}

export function extractEngineeringTargetCounts(text: string): EngineeringTargetCounts {
  const body = specificationBody(text);
  const sensors = requestedCount(body, "sensor(?:en|s)?", "technische|physikalische|logische|fahrzeugrelevante");
  const actuators = requestedCount(body, "(?:actuator(?:s)?|aktuator(?:en)?|aktor(?:en)?)", "technische|physikalische|logische|einfache");
  const ecus = requestedCount(body, "ecu(?:s)?", "funktions|zentrale|typische|weitere");
  const gateways = requestedCount(body, "gateway(?:s)?", "zentralen|zentrales|zentraler|zentrale|einziges|einzigen");
  return {
    sensors,
    actuators,
    ecus,
    gateways,
    explicit: sensors > 0 || actuators > 0 || ecus > 0 || gateways > 0,
  };
}

function chainCounts(chains: ExtractedEngineeringChain[]) {
  return chains.reduce(
    (counts, chain) => {
      if (chain.device_type === "SensorController") counts.sensors += 1;
      else if (chain.device_type === "ActuatorController") counts.actuators += 1;
      else if (chain.device_type === "Gateway") counts.gateways += 1;
      else if (chain.device_type === "ECU") counts.ecus += 1;
      return counts;
    },
    { sensors: 0, actuators: 0, ecus: 0, gateways: 0 },
  );
}

function ecuInterfaceType(name: string) {
  if (/infotainment|telematik|diagnose|fahrerassistenz|radar|kamera|zentralrechner|konnektivitaet/i.test(name)) {
    return "Ethernet";
  }
  if (/tuer|sitz|licht|keyless|wischer|schiebedach|heckklappe|soundsystem|headup/i.test(name)) {
    return "LIN";
  }
  return "CAN_FD";
}

function architectureTemplates(): ArchitectureTemplate[] {
  const positions = [
    ["FrontLeft", "VorneLinks"],
    ["FrontRight", "VorneRechts"],
    ["RearLeft", "HintenLinks"],
    ["RearRight", "HintenRechts"],
  ] as const;
  const positionalSensors = POSITIONAL_SENSOR_FAMILIES.flatMap((family) => positions.map(([name, signal]) => ({
    hardwareName: `${name}${family.name}Sensor`,
    deviceType: "SensorController" as const,
    signalName: `${family.signal}${signal}`,
    interfaceType: family.cycle >= 100 ? "LIN" : "CAN_FD",
    cycleMs: family.cycle,
    unit: family.unit,
    minValue: family.min,
    maxValue: family.max,
    factor: family.factor,
  })));
  const centralSensors = CENTRAL_SENSOR_DEFINITIONS.map(([name, signal, unit, min, max, factor, cycle]) => ({
    hardwareName: `${name}Sensor`,
    deviceType: "SensorController" as const,
    signalName: signal,
    interfaceType: /Radar/.test(name) ? "Ethernet" : cycle >= 200 ? "LIN" : "CAN_FD",
    cycleMs: cycle,
    unit,
    minValue: min,
    maxValue: max,
    factor,
  }));
  const ecus = ECU_NAMES.map((name) => ({
    hardwareName: name,
    deviceType: "ECU" as const,
    signalName: `${identifier(baseName(name))}Status`,
    interfaceType: ecuInterfaceType(name),
    cycleMs: ecuInterfaceType(name) === "LIN" ? 100 : ecuInterfaceType(name) === "Ethernet" ? 20 : 10,
    unit: "code",
    minValue: 0,
    maxValue: 255,
    factor: 1,
  }));
  const actuators = ECU_NAMES.flatMap((name) => ["Stellglied", "Schaltausgang"].map((kind) => ({
    hardwareName: `${baseName(name)}${kind}Actuator`,
    deviceType: "ActuatorController" as const,
    signalName: `${identifier(baseName(name))}${kind}Status`,
    interfaceType: ecuInterfaceType(name),
    cycleMs: ecuInterfaceType(name) === "LIN" ? 100 : 20,
    unit: kind === "Stellglied" ? "%" : "code",
    minValue: 0,
    maxValue: kind === "Stellglied" ? 100 : 1,
    factor: kind === "Stellglied" ? 0.1 : 1,
  })));
  return [
    ...positionalSensors,
    ...centralSensors,
    ...actuators,
    ...ecus,
    {
      hardwareName: "System-Gateway",
      deviceType: "Gateway",
      signalName: "GatewayStatus",
      interfaceType: "Ethernet",
      cycleMs: 20,
      unit: "code",
      minValue: 0,
      maxValue: 255,
      factor: 1,
    },
  ];
}

function chainFromTemplate(template: ArchitectureTemplate, index: number, domain: string): ExtractedEngineeringChain {
  const hardwareId = identifier(template.hardwareName);
  const dataType = (template.minValue ?? 0) < 0 ? "signed" : "unsigned";
  const lengthBits = generatedSignalBitLength({
    minValue: template.minValue,
    maxValue: template.maxValue,
    factor: template.factor,
    dataType,
  });
  const functionSuffix = template.deviceType === "SensorController"
    ? "Erfassung"
    : template.deviceType === "Gateway"
      ? "Kommunikation"
      : "Steuerung";
  return {
    hardware_name: template.hardwareName,
    hardware_description: `Aus dem geforderten Fahrzeugarchitektur-Skalierungsziel abgeleiteter ${template.deviceType}.`,
    device_type: template.deviceType,
    function_name: `${hardwareId}_${functionSuffix}`,
    function_description: `Fachfunktion fuer ${template.hardwareName} im skalierten Musterprojekt.`,
    interface_name: `${hardwareId}_${template.interfaceType}`,
    interface_type: template.interfaceType,
    message_name: `${hardwareId}Data`,
    message_id_hex: `0x${(0x180 + index).toString(16).toUpperCase()}`,
    direction: "tx",
    cycle_ms: template.cycleMs,
    dlc: generatedMessageDlc(lengthBits),
    signal_name: template.signalName,
    signal_display_name: template.signalName,
    start_bit: 0,
    length_bits: lengthBits,
    byte_order: "little_endian",
    data_type: dataType,
    factor: template.factor ?? 1,
    offset_value: 0,
    unit: template.unit,
    min_value: template.minValue,
    max_value: template.maxValue,
    domain,
  };
}

function expandArchitectureChains(
  recognizedChains: ExtractedEngineeringChain[],
  requested: EngineeringTargetCounts,
  domain: string,
  communicationSystems: string[],
  overrides: Partial<EngineeringHardwareCounts> = {},
) {
  const recognizedCounts = chainCounts(recognizedChains);
  const targets: EngineeringTargetCounts = {
    sensors: requested.sensors || recognizedCounts.sensors,
    actuators: requested.actuators || recognizedCounts.actuators,
    ecus: requested.ecus || recognizedCounts.ecus,
    gateways: requested.gateways || recognizedCounts.gateways,
    ...overrides,
    explicit: requested.explicit || Object.keys(overrides).length > 0,
  };
  const retainedCounts = { sensors: 0, actuators: 0, ecus: 0, gateways: 0 };
  const chains = targets.explicit
    ? recognizedChains.filter((chain) => {
      const category = chain.device_type === "SensorController"
        ? "sensors"
        : chain.device_type === "ActuatorController" ? "actuators"
        : chain.device_type === "Gateway"
          ? "gateways"
          : chain.device_type === "ECU"
            ? "ecus"
            : null;
      if (!category) return true;
      if (retainedCounts[category] >= targets[category]) return false;
      retainedCounts[category] += 1;
      return true;
    })
    : [...recognizedChains];
  const names = new Set(chains.map((chain) => normalized(normalizeHardwareName(chain.hardware_name))));
  if (!targets.explicit) return { chains, targets };

  const templates = architectureTemplates();
  const targetFor = (deviceType: ArchitectureTemplate["deviceType"]) => (
    deviceType === "SensorController" ? targets.sensors : deviceType === "ActuatorController" ? targets.actuators : deviceType === "Gateway" ? targets.gateways : targets.ecus
  );
  for (const template of templates) {
    const current = chainCounts(chains);
    const currentCount = template.deviceType === "SensorController"
      ? current.sensors
      : template.deviceType === "ActuatorController" ? current.actuators
      : template.deviceType === "Gateway"
        ? current.gateways
        : current.ecus;
    if (currentCount >= targetFor(template.deviceType)) continue;
    const key = normalized(normalizeHardwareName(template.hardwareName));
    if (names.has(key)) continue;
    const allowedInterfaceType = communicationSystems.includes(template.interfaceType)
      ? template.interfaceType
      : communicationSystems.length
        ? communicationSystems[chains.length % communicationSystems.length]
        : undefined;
    chains.push(chainFromTemplate(
      allowedInterfaceType ? { ...template, interfaceType: allowedInterfaceType } : template,
      chains.length,
      domain,
    ));
    names.add(key);
  }
  // Additional instances keep the same technical template and a stable unique name.
  for (const deviceType of ["SensorController", "ActuatorController", "ECU", "Gateway"] as const) {
    const candidates = templates.filter((template) => template.deviceType === deviceType);
    let current = chains.filter((chain) => chain.device_type === deviceType).length;
    for (let instance = 0; current < targetFor(deviceType); instance += 1) {
      const template = candidates[instance % candidates.length];
      const hardwareName = `${template.hardwareName}-${2 + Math.floor(instance / candidates.length)}`;
      if (names.has(normalized(normalizeHardwareName(hardwareName)))) continue;
      const interfaceType = communicationSystems.includes(template.interfaceType) || !communicationSystems.length
        ? template.interfaceType : communicationSystems[instance % communicationSystems.length];
      chains.push(chainFromTemplate({ ...template, hardwareName, interfaceType }, chains.length, domain));
      names.add(normalized(normalizeHardwareName(hardwareName)));
      current += 1;
    }
  }
  return { chains, targets };
}

function headingLabel(line: string) {
  const bold = line.match(/^\s*(?:(?:[-*]|\d+\.)\s+)?\*\*(.+?)\*\*(?:\s*:|\s*$)/)?.[1];
  if (bold) return cleanLabel(bold);
  const bullet = line.match(/^\s*(?:[-*]|\d+\.)\s+(.+?)\s*$/)?.[1];
  if (!bullet) return "";
  // Compact specifications often put type and parameters on the same bullet.
  // Only the leading label identifies the hardware participant.
  return cleanLabel(bullet.split(/\s*[:,]\s*/, 1)[0] ?? "");
}

function isCountedHardwareGroup(value: string) {
  const key = normalized(value);
  return new RegExp(
    `^${COUNT_TOKEN}\\s+(?:(?:technische|physikalische|logische|fahrzeugrelevante|funktions|zentrale|zentralen|zentrales|zentraler|typische|weitere|einziges|einzigen)\\s+){0,2}(?:sensor(?:en|s)?|actuator(?:s)?|aktuator(?:en)?|aktor(?:en)?|ecu(?:s)?|gateway(?:s)?)$`,
  ).test(key);
}

function hardwareName(label: string) {
  const name = cleanLabel(label);
  const key = normalized(name);
  if (!key || GENERIC_HARDWARE_LABELS.has(key)) return "";
  if (PROSE_HARDWARE_LABEL_PATTERN.test(key)) return "";
  const typeMentions = key.match(/\b(?:sensor(?:en|s)?|actuator(?:s)?|aktuator(?:en)?|aktor(?:en)?|ecu(?:s)?|gateway(?:s)?|plc(?:s)?|controller(?:s)?|steuergeraet(?:e)?)\b/g) ?? [];
  const countedGroup = isCountedHardwareGroup(name);
  if (typeMentions.length > 1 || countedGroup) return "";
  return /(?:sensor|actuator|aktuator|aktor|ecu|gateway|plc|controller|steuergeraet)$/i.test(key.replace(/\s+/g, ""))
    ? name
    : "";
}

function inlineHardwareNames(line: string) {
  if (isCountedHardwareGroup(cleanLabel(line))) return [];
  const names = line.match(INLINE_HARDWARE_PATTERN) ?? [];
  return names
    .map((name) => cleanLabel(name))
    .filter((name) => !GENERIC_INLINE_HARDWARE_LABELS.has(normalized(name)))
    .filter((name) => Boolean(hardwareName(name)));
}

function impliedHardwareNames(line: string) {
  const key = normalized(line);
  const names: string[] = [];
  if (/\b(?:sensor|sensoren)\b/.test(key) && /\bmotorstrom\b/.test(key)) {
    names.push("Motorstromsensor");
  }
  if (/\bgateway\b/.test(key) && /\b(?:verbindet|koppelt|vermittelt|uebertraegt|ueberbrueckt)\b/.test(key)) {
    names.push("System-Gateway");
  }
  return names;
}

function deviceType(name: string) {
  const key = normalized(name);
  if (key.includes("gateway")) return "Gateway";
  if (key.includes("sensor")) return "SensorController";
  if (/actuator|aktuator|aktor/.test(key)) return "ActuatorController";
  if (key.includes("plc")) return "PLC";
  if (key.includes("controller")) return "GenericDevice";
  return "ECU";
}

function protocolFrom(text: string) {
  const key = normalized(text);
  if (key.includes("can fd") || key.includes("canfd")) return "CAN_FD";
  if (key.includes("ethercat")) return "EtherCAT";
  if (key.includes("profinet")) return "ProfiNET";
  if (key.includes("automotive ethernet") || key.includes("ethernet")) return "Ethernet";
  if (key.includes("modbus tcp")) return "ModbusTCP";
  if (key.includes("opc ua")) return "OPCUA";
  return "CAN";
}

export function extractCommunicationSystems(text: string) {
  const key = normalized(text);
  const systems: string[] = [];
  if (/\blin\b/.test(key)) systems.push("LIN");
  if (/\bcan fd\b|\bcanfd\b/.test(key)) systems.push("CAN_FD");
  else if (/\bcan\b/.test(key)) systems.push("CAN");
  if (/\bautomotive ethernet\b|\bethernet\b/.test(key)) systems.push("Ethernet");
  if (/\bethercat\b/.test(key)) systems.push("EtherCAT");
  if (/\bprofinet\b/.test(key)) systems.push("ProfiNET");
  if (/\bmodbus tcp\b/.test(key)) systems.push("ModbusTCP");
  if (/\bopc ua\b/.test(key)) systems.push("OPCUA");
  return [...new Set(systems)];
}

function domainFrom(text: string) {
  const key = normalized(text);
  if (/automotive|fahrzeug|ecu|can fd/.test(key)) return "automotive";
  if (/industrial|plc|profinet|ethercat/.test(key)) return "industrial_automation";
  if (/aerospace|arinc|avionik/.test(key)) return "aerospace";
  return "generic";
}

function numeric(value: string | undefined) {
  if (!value) return undefined;
  const result = Number(value.replace(",", "."));
  return Number.isFinite(result) ? result : undefined;
}

function rangeFrom(text: string) {
  const match = text
    .replace(/−/g, "-")
    .match(/(-?\d+(?:[,.]\d+)?)\s*(?:°\s*c|a|u\s*\/\s*min|\/\s*min)?\s*(?:bis|–|—)\s*\+?(-?\d+(?:[,.]\d+)?)/i);
  return { min: numeric(match?.[1]), max: numeric(match?.[2]) };
}

function factorFrom(text: string, unit: string | undefined) {
  const match = text.match(/(?:auflösung|aufloesung|schrittweite)\s*:?\s*(-?\d+(?:[,.]\d+)?)/i);
  const explicit = numeric(match?.[1]);
  if (explicit !== undefined) return explicit;
  return unit === "degC" || unit === "A" ? 0.1 : 1;
}

function unitFrom(text: string) {
  if (/°\s*c/i.test(text)) return "degC";
  if (/u\s*\/\s*min|\/\s*min/i.test(text)) return "rpm";
  if (/(^|\s)\d+(?:[,.]\d+)?\s*a\b/i.test(text)) return "A";
  return undefined;
}

function baseName(name: string) {
  return name
    .replace(/[-_\s]*(sensor|ecu|gateway|plc|controller|steuergeraet)$/i, "")
    .replace(/[^a-zA-Z0-9äöüÄÖÜß]+/g, " ")
    .trim() || name;
}

function identifier(value: string) {
  const words = value.replace(/[^a-zA-Z0-9äöüÄÖÜß]+/g, " ").trim().split(/\s+/);
  return words.map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join("");
}

function functionName(name: string, contexts: string[]) {
  for (const line of contexts) {
    const explicit = cleanLabel(line).match(/^\s*(?:[-*]\s*)?funktion(?:sname)?\s*:\s*(.+?)\s*$/i)?.[1];
    if (explicit) return `${identifier(name)}_${identifier(explicit)}`;
  }
  const key = normalized(name);
  if (key.includes("sensor")) return `${identifier(name)}_Erfassung`;
  if (key.includes("gateway")) return `${identifier(name)}_Kommunikation`;
  return `${identifier(name)}_Steuerung`;
}

function signalName(name: string, context: string) {
  const key = normalized(name);
  if (key.includes("drehzahl")) return "Drehzahl";
  if (key.includes("motorstrom")) return "Motorstrom";
  if (key.includes("thermal")) return "Solltemperatur";
  if (key.includes("motion")) return "Temperaturgrenzwert";
  if (key.includes("temperatur")) return "Temperatur";
  if (/warnhinweis/i.test(context)) return `${identifier(baseName(name))}Warnung`;
  if (key.includes("gateway")) return "GatewayStatus";
  return `${identifier(baseName(name))}Status`;
}

export function extractEngineeringSpecification(text: string, overrides: Partial<EngineeringHardwareCounts> = {}): ExtractedEngineeringSpecification {
  const lines = specificationBody(text).split(/\r?\n/);
  const occurrences = lines.flatMap((line, index): HardwareOccurrence[] => {
    const headingName = hardwareName(headingLabel(line));
    const names = [headingName, ...inlineHardwareNames(line), ...impliedHardwareNames(line)].filter(Boolean);
    return [...new Map(names.map((name) => [normalized(normalizeHardwareName(name)), name])).values()].map((name) => ({ index, name }));
  });
  const contexts = new Map<string, { name: string; lines: string[] }>();
  occurrences.forEach((occurrence, occurrenceIndex) => {
    const nextIndex = occurrences[occurrenceIndex + 1]?.index ?? lines.length;
    const key = normalized(normalizeHardwareName(occurrence.name));
    const existing = contexts.get(key) ?? { name: occurrence.name, lines: [] };
    existing.lines.push(...lines.slice(occurrence.index, Math.max(occurrence.index + 1, nextIndex)));
    contexts.set(key, existing);
  });

  const domain = domainFrom(text);
  const interfaceType = protocolFrom(text);
  const communicationSystems = extractCommunicationSystems(text);
  const networkArchitecture = extractNetworkArchitectureMode(text);
  const recognizedChains = [...contexts.values()].map((entry, index): ExtractedEngineeringChain => {
    const context = entry.lines.map((line) => cleanLabel(line)).filter(Boolean).join("; ");
    const range = rangeFrom(context);
    const unit = unitFrom(context);
    const factor = factorFrom(context, unit);
    const signal = signalName(entry.name, context);
    const hardwareId = identifier(entry.name);
    const dataType = (range.min ?? 0) < 0 ? "signed" : "unsigned";
    const lengthBits = generatedSignalBitLength({
      minValue: range.min,
      maxValue: range.max,
      factor,
      dataType,
    });
    return {
      hardware_name: entry.name,
      hardware_description: context.slice(0, 1000),
      device_type: deviceType(entry.name),
      function_name: functionName(entry.name, entry.lines),
      function_description: `Aus Nutzerspezifikation abgeleitete Funktion. ${context}`.slice(0, 1000),
      interface_name: `${hardwareId}_${interfaceType}`,
      interface_type: interfaceType,
      message_name: `${hardwareId}Data`,
      message_id_hex: `0x${(0x180 + index).toString(16).toUpperCase()}`,
      direction: "tx",
      cycle_ms: 10,
      dlc: generatedMessageDlc(lengthBits),
      signal_name: signal,
      signal_display_name: signal,
      start_bit: 0,
      length_bits: lengthBits,
      byte_order: "little_endian",
      data_type: dataType,
      factor,
      offset_value: 0,
      unit,
      min_value: range.min,
      max_value: range.max,
      domain,
    };
  });

  const requestedTargets = extractEngineeringTargetCounts(text);
  const expanded = expandArchitectureChains(
    recognizedChains,
    requestedTargets,
    domain,
    communicationSystems,
    { ...confirmedHardwareCounts(text), ...overrides },
  );

  return {
    chains: expanded.chains.map((chain) => ({ ...chain, hardware_name: normalizeHardwareName(chain.hardware_name) })),
    domain,
    interfaceType,
    communicationSystems,
    networkArchitecture,
    targetCounts: expanded.targets,
  };
}

export function confirmedHardwareCounts(text: string): Partial<EngineeringHardwareCounts> {
  const header = text.split(/Konkrete Aufgabe des Nutzers/i, 1)[0];
  const raw = header.match(/^- Hardware-Sollwerte:\s*(\{[^\r\n]+\})\s*$/m)?.[1];
  if (!raw) return {};
  const counts = JSON.parse(raw) as EngineeringHardwareCounts;
  for (const key of ["sensors", "actuators", "ecus", "gateways"] as const) {
    if (!Number.isSafeInteger(counts[key]) || counts[key] < 0 || counts[key] > 1000) {
      throw new Error(`Ungueltiger Hardware-Sollwert: ${key}`);
    }
  }
  return counts;
}

export function isEngineeringReviewRequest(text: string) {
  const task = text.split(/Konkrete Aufgabe des Nutzers\s*:/i).at(-1)?.trim() ?? text.trim();
  return /^(?:bewerte|pr[uü]fe|pruefe|analysiere|review|evaluate|analyze)\b/i.test(task);
}

export function isStructuredEngineeringSpecification(text: string) {
  if (isEngineeringReviewRequest(text)) return false;
  const extracted = extractEngineeringSpecification(text);
  const parameterEvidence = /(messbereich|auflösung|aufloesung|schrittweite|sollwert|grenzwert|kommunikationsprotokoll|funktions.parameter)/i.test(text);
  return extracted.chains.length >= 2 || (extracted.chains.length === 1 && parameterEvidence);
}
