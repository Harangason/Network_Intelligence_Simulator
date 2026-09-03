import type { ExtractedEngineeringChain, NetworkArchitectureMode } from "./engineering-specification";

type RouteRule = {
  source: string[];
  targets: string[];
};

export type SemanticRoutePlan = {
  source: ExtractedEngineeringChain;
  destinations: ExtractedEngineeringChain[];
};

const ROUTE_RULES: RouteRule[] = [
  { source: ["airbag", "crash", "impact", "seatbelt", "gurt"], targets: ["airbag", "rueckhalt"] },
  { source: ["brakepressure", "bremsdruck", "braketemperature", "bremstemperatur", "brakepedal", "bremspedal"], targets: ["bremsregelung", "stabilitaetsregelung"] },
  { source: ["tirepressure", "reifendruck", "tiretemperature", "reifentemperatur", "tirewear", "reifenverschleiss"], targets: ["reifendruckkontrolle"] },
  { source: ["damperposition", "daempferposition"], targets: ["daempferregelung", "fahrwerk"] },
  { source: ["suspensiontravel", "federweg", "wheelload", "radlast", "verticalacceleration", "vertikalbeschleunigung"], targets: ["fahrwerk", "daempferregelung"] },
  { source: ["wheelangle", "radwinkel", "steeringangle", "lenkwinkel", "steeringtorque", "lenkmoment"], targets: ["lenkung", "hinterachslenkung"] },
  { source: ["wheelacceleration", "radbeschleunigung", "wheeltorque", "raddrehmoment", "longitudinalacceleration", "laengsbeschleunigung", "lateralacceleration", "querbeschleunigung", "yawrate", "gierrate", "pitchrate", "nickrate", "rollrate"], targets: ["stabilitaetsregelung", "fahrdynamik"] },
  { source: ["wheelspeed", "raddrehzahl"], targets: ["bremsregelung", "stabilitaetsregelung", "fahrdynamik"] },
  { source: ["transmissionoiltemperature", "getriebeoeltemperatur", "transmissioninput", "getriebeeingang", "transmissionoutput", "getriebeausgang", "clutchposition", "kupplungsstellung", "gearselector", "gangwahl"], targets: ["getriebesteuerung"] },
  { source: ["exhaustgastemperature", "abgastemperatur", "egrvalve", "agrventil", "urealevel", "harnstoff"], targets: ["abgasnachbehandlung"] },
  { source: ["batterytemperature", "batterietemperatur", "batterycoolant", "batteriekuehl", "batterycurrent", "batteriestrom", "batteryvoltage", "batteriespannung", "cellvoltage", "zellspannung"], targets: ["batteriemanagement", "thermomanagement"] },
  { source: ["invertertemperature", "invertertemperatur", "dclink", "zwischenkreis"], targets: ["invertersteuerung"] },
  { source: ["motorspeed", "elektromotordrehzahl", "motorcurrent", "motorstrom"], targets: ["elektromotorsteuerung", "motorsteuerung"] },
  { source: ["enginespeed", "motordrehzahl", "motortemperature", "motortemperatur", "engineoilpressure", "motoroeldruck", "boostpressure", "ladedruck", "turbospeed", "turbolader", "acceleratorposition", "fahrpedal", "throttleposition", "drosselklappe"], targets: ["motorsteuerung", "thermal"] },
  { source: ["fuelpressure", "kraftstoffdruck", "fuellevel", "kraftstofffuellstand"], targets: ["kraftstoffsystem"] },
  { source: ["cabintemperature", "innenraumtemperatur", "ambienttemperature", "aussentemperatur", "refrigerantpressure", "kaeltemitteldruck"], targets: ["klima", "klimatisierung", "thermal", "thermomanagement"] },
  { source: ["coolanttemperature", "kuehlmitteltemperatur", "oiltemperature", "oeltemperatur", "intakeairtemperature", "ansauglufttemperatur", "coolantlevel", "kuehlmittelfuellstand", "oillevel", "oelfuellstand", "temperature", "temperatur"], targets: ["thermal", "thermomanagement", "klimatisierung"] },
  { source: ["alternatorcurrent", "generatorstrom", "accessorycurrent", "nebenverbraucherstrom", "lowvoltagesupply", "bordnetzspannung"], targets: ["energieversorgung"] },
  { source: ["frontradardistance", "frontabstand", "rearradardistance", "heckabstand"], targets: ["radarverarbeitung", "fahrerassistenz"] },
  { source: ["rain", "regenintensitaet", "washerfluid", "waschwasser"], targets: ["wischersteuerung", "bodycontrol"] },
  { source: ["ambientlight", "umgebungshelligkeit"], targets: ["aussenlicht", "bodycontrol"] },
];

const GATEWAY_ECU_SEGMENT_SIZE = 6;

const GENERIC_ROUTE_TOKENS = new Set([
  "automotive", "controller", "data", "ecu", "erfassung", "generated", "hardware",
  "message", "sensor", "signal", "status", "steuerung",
]);

export function semanticRouteKey(value: string) {
  return value
    .toLowerCase()
    .replace(/ä/g, "ae")
    .replace(/ö/g, "oe")
    .replace(/ü/g, "ue")
    .replace(/ß/g, "ss")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function compactKey(value: string) {
  return semanticRouteKey(value).replace(/\s+/g, "");
}

function chainText(chain: ExtractedEngineeringChain) {
  return compactKey([
    chain.hardware_name,
    chain.hardware_description,
    chain.function_name,
    chain.function_description,
    chain.signal_name,
    chain.signal_display_name,
  ].join(" "));
}

function meaningfulTokens(value: string) {
  return semanticRouteKey(value)
    .split(" ")
    .filter((token) => token.length > 3 && !GENERIC_ROUTE_TOKENS.has(token));
}

export function semanticRouteScore(
  sensor: ExtractedEngineeringChain,
  processor: ExtractedEngineeringChain,
) {
  const source = chainText(sensor);
  const processorBase = compactKey(processor.hardware_name).replace(/ecu$/, "");
  const target = compactKey(`${processor.hardware_name} ${processor.function_name} ${processor.hardware_description}`);
  let semanticScore = 0;

  for (const rule of ROUTE_RULES) {
    const sourceSpecificity = Math.max(0, ...rule.source
      .filter((term) => source.includes(term))
      .map((term) => term.length));
    if (sourceSpecificity === 0) continue;
    const exactTargetIndex = rule.targets.findIndex((term) => processorBase === term);
    if (exactTargetIndex >= 0) {
      semanticScore = Math.max(semanticScore, 1_000 + sourceSpecificity * 20 - exactTargetIndex * 80);
      continue;
    }
    const relatedTargetIndex = rule.targets.findIndex((term) => target.includes(term));
    if (relatedTargetIndex >= 0) {
      semanticScore = Math.max(semanticScore, 700 + sourceSpecificity * 20 - relatedTargetIndex * 60);
    }
  }

  const processorName = compactKey(processor.hardware_name);
  if (processorName.length > 3 && source.includes(processorName)) semanticScore = Math.max(semanticScore, 900);
  const targetTokens = meaningfulTokens(processor.hardware_name);
  const commonTokens = meaningfulTokens(sensor.hardware_name).filter((token) => targetTokens.includes(token));
  semanticScore += commonTokens.length * 60;

  if (semanticScore <= 0) return 0;
  return semanticScore + (sensor.interface_type === processor.interface_type ? 20 : 0);
}

export function semanticProcessorForSensor(
  sensor: ExtractedEngineeringChain,
  processors: ExtractedEngineeringChain[],
) {
  return processors
    .map((processor) => ({ processor, score: semanticRouteScore(sensor, processor) }))
    .filter((candidate) => candidate.score > 0)
    .sort((left, right) =>
      right.score - left.score || left.processor.hardware_name.localeCompare(right.processor.hardware_name, "de"),
    )[0]?.processor;
}

function gatewayForProcessor(
  processor: ExtractedEngineeringChain,
  gateways: ExtractedEngineeringChain[],
) {
  const processorTokens = new Set(meaningfulTokens(processor.hardware_name));
  return gateways
    .map((gateway) => {
      const gatewayKey = compactKey(gateway.hardware_name);
      const sharedTokens = meaningfulTokens(gateway.hardware_name)
        .filter((token) => processorTokens.has(token));
      const centralFallback = /(system|zentral|central).*gateway|gateway.*(system|zentral|central)/.test(gatewayKey);
      return {
        gateway,
        score: sharedTokens.length * 1_000 + (centralFallback ? 100 : 0),
      };
    })
    .sort((left, right) =>
      right.score - left.score || left.gateway.hardware_name.localeCompare(right.gateway.hardware_name, "de"),
    )[0]?.gateway;
}

function processorSegments(processors: ExtractedEngineeringChain[], size = GATEWAY_ECU_SEGMENT_SIZE) {
  const ordered = [...processors].sort((left, right) => (
    canonicalInterfaceKey(left.interface_type).localeCompare(canonicalInterfaceKey(right.interface_type))
    || left.hardware_name.localeCompare(right.hardware_name, "de-DE", { numeric: true, sensitivity: "base" })
  ));
  const segments: ExtractedEngineeringChain[][] = [];
  for (let index = 0; index < ordered.length; index += size) {
    segments.push(ordered.slice(index, index + size));
  }
  return segments;
}

export function semanticRoutePlans(
  chains: ExtractedEngineeringChain[],
  architecture: NetworkArchitectureMode = "ecu_gateway",
): SemanticRoutePlan[] {
  const sensors = chains.filter((chain) => semanticRouteKey(chain.device_type).includes("sensor"));
  const actuators = chains.filter((chain) => /actuator|aktor/.test(semanticRouteKey(chain.device_type)));
  const gateways = chains.filter((chain) => semanticRouteKey(chain.device_type).includes("gateway"));
  const endpoints = [...sensors, ...actuators];
  const processors = chains.filter((chain) => !endpoints.includes(chain) && !gateways.includes(chain));
  const plans: SemanticRoutePlan[] = [];

  if (architecture === "gateway_direct") {
    for (const participant of [...endpoints, ...processors]) {
      const gateway = gatewayForProcessor(participant, gateways);
      if (gateway) plans.push({ source: participant, destinations: [gateway] });
    }
  } else {
    for (const [endpointIndex, endpoint] of endpoints.entries()) {
      const actuator = /actuator|aktor/.test(semanticRouteKey(endpoint.device_type));
      const processor = semanticProcessorForSensor(endpoint, processors)
        ?? (actuator && processors.length ? processors[endpointIndex % processors.length] : undefined);
      const gateway = gatewayForProcessor(endpoint, gateways);
      const directInHybrid = architecture === "hybrid_ai"
        && (canonicalInterfaceKey(endpoint.interface_type) === "ethernet" || !processor);
      if (actuator && processor) {
        if (processor) plans.push({ source: processor, destinations: [endpoint] });
      } else if (directInHybrid && gateway) plans.push({ source: endpoint, destinations: [gateway] });
      else if (processor) plans.push({ source: endpoint, destinations: [processor] });
    }
    if (architecture === "sensor_ecu_actuator") {
      // Pure local control loop: endpoint <-> ECU only, no Gateway/BCM route layer.
    } else if (architecture === "gateway_ecu_segments") {
      for (const segment of processorSegments(processors)) {
        const gateway = gatewayForProcessor(segment[0], gateways);
        if (gateway && segment.length) plans.push({ source: gateway, destinations: segment });
      }
    } else {
      for (const processor of processors) {
        const gateway = gatewayForProcessor(processor, gateways);
        if (gateway) plans.push({ source: processor, destinations: [gateway] });
      }
    }
  }
  if (!plans.length && chains.length >= 2) {
    plans.push({ source: chains[0], destinations: chains.slice(1) });
  }

  const unique = new Map<string, SemanticRoutePlan>();
  for (const plan of plans) {
    const key = [plan.source.hardware_name, ...plan.destinations.map((item) => item.hardware_name)]
      .map(semanticRouteKey)
      .join("->");
    unique.set(key, plan);
  }
  return [...unique.values()];
}

function canonicalInterfaceKey(value: string) {
  return semanticRouteKey(value).replace(/\s+/g, "");
}
