import type { IndustrySensorTemplate, IndustryTemplateProfile } from "./types.ts";

const sensors: IndustrySensorTemplate[] = [
  ["EngineRpmSensor", "Maschinendrehzahl", "CAN", "rpm", 0, 3000, 1, 50],
  ["FuelFlowSensor", "Kraftstoffdurchfluss", "CAN", "l/h", 0, 20000, 0.1, 100],
  ["RudderAngleSensor", "Ruderwinkel", "CAN", "deg", -45, 45, 0.01, 20],
  ["BallastLevelSensor", "Ballastfuellstand", "CAN", "%", 0, 100, 0.1, 500],
  ["BilgeLevelSensor", "Bilgenstand", "CAN", "mm", 0, 2000, 1, 100],
  ["RadarTargetSensor", "RadarzielStatus", "Ethernet", "code", 0, 255, 1, 20],
  ["WindSpeedSensor", "Windgeschwindigkeit", "Ethernet", "m/s", 0, 80, 0.1, 100],
  ["FireZoneSensor", "BrandzonenStatus", "CAN", "code", 0, 15, 1, 100],
].map(([hardwareName, signalName, interfaceType, unit, minValue, maxValue, factor, cycleMs]) => ({
  cycleMs: Number(cycleMs),
  factor: Number(factor),
  hardwareName: String(hardwareName),
  interfaceType: String(interfaceType),
  maxValue: Number(maxValue),
  minValue: Number(minValue),
  signalName: String(signalName),
  unit: String(unit),
}));

export const marineTemplateProfile: IndustryTemplateProfile = {
  gatewayName: "ShipGateway",
  id: "marine",
  label: "Marine",
  sensorTemplates: sensors,
  systemVariants: [
    "PropulsionControl",
    "NavigationBridge",
    "BallastControl",
    "BilgeMonitoring",
    "PowerManagement",
    "RadarConsole",
    "Autopilot",
    "EngineRoomMonitoring",
    "CargoControl",
    "FireDetection",
    "SteeringGear",
    "CommunicationConsole",
    "DynamicPositioning",
    "FuelTransfer",
    "AlarmManagement",
  ],
};
