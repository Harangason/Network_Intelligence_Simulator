import type { IndustrySensorTemplate, IndustryTemplateProfile } from "./types.ts";

const sensors: IndustrySensorTemplate[] = [
  ["GridVoltageSensor", "Netzspannung", "ModbusTCP", "V", 0, 1200, 0.1, 20],
  ["GridCurrentSensor", "Netzstrom", "ModbusTCP", "A", -5000, 5000, 0.1, 20],
  ["FrequencySensor", "Netzfrequenz", "Ethernet", "Hz", 45, 65, 0.001, 20],
  ["BatterySocSensor", "Batterieladezustand", "ModbusTCP", "%", 0, 100, 0.1, 100],
  ["TransformerTemperatureSensor", "Transformatortemperatur", "ModbusTCP", "degC", -40, 180, 0.1, 100],
  ["BreakerStateSensor", "SchalterStatus", "Ethernet", "code", 0, 7, 1, 20],
  ["InverterPowerSensor", "Umrichterleistung", "Ethernet", "kW", -10000, 10000, 0.1, 20],
  ["InsulationResistanceSensor", "Isolationswiderstand", "ModbusTCP", "kohm", 0, 100000, 1, 1000],
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

export const energyTemplateProfile: IndustryTemplateProfile = {
  gatewayName: "EnergyGateway",
  id: "energy",
  label: "Energy",
  sensorTemplates: sensors,
  systemVariants: [
    "Umrichtersteuerung",
    "Batteriespeicher",
    "Netzschutz",
    "Schaltanlage",
    "Transformatorueberwachung",
    "Solarwechselrichter",
    "Windturbinenregelung",
    "Ladeinfrastruktur",
    "Lastmanagement",
    "Messstellenbetrieb",
    "MicrogridController",
    "Generatorsteuerung",
    "Frequenzregelung",
    "Leistungsschalter",
    "Erdschlussueberwachung",
  ],
};
