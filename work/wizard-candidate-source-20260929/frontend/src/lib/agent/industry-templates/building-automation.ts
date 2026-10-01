import type { IndustrySensorTemplate, IndustryTemplateProfile } from "./types.ts";

const sensors: IndustrySensorTemplate[] = [
  ["RoomTemperatureSensor", "Raumtemperatur", "ModbusTCP", "degC", -20, 60, 0.1, 100],
  ["Co2Sensor", "CO2Konzentration", "ModbusTCP", "ppm", 0, 5000, 1, 1000],
  ["HumiditySensor", "Luftfeuchte", "ModbusTCP", "%", 0, 100, 0.1, 1000],
  ["OccupancySensor", "BelegungStatus", "Ethernet", "code", 0, 1, 1, 100],
  ["LightLevelSensor", "Beleuchtungsstaerke", "ModbusTCP", "lx", 0, 100000, 1, 500],
  ["SmokeDetectorSensor", "RauchmelderStatus", "Ethernet", "code", 0, 3, 1, 100],
  ["EnergyMeterSensor", "Energieverbrauch", "Ethernet", "kWh", 0, 100000, 0.1, 1000],
  ["WaterLeakSensor", "LeckageStatus", "ModbusTCP", "code", 0, 1, 1, 1000],
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

export const buildingAutomationTemplateProfile: IndustryTemplateProfile = {
  gatewayName: "GebaeudeGateway",
  id: "building_automation",
  label: "Building Automation",
  sensorTemplates: sensors,
  systemVariants: [
    "Gebaeudeleittechnik",
    "HVACRegelung",
    "Lichtsteuerung",
    "Zutrittskontrolle",
    "Brandmeldeanlage",
    "Aufzugssteuerung",
    "Energiezaehler",
    "Beschattung",
    "Raumautomation",
    "Sicherheitszentrale",
    "Lueftungsanlage",
    "Waermeerzeugung",
    "Kuehlanlage",
    "Parkleitsystem",
    "Wasserleckage",
  ],
};
