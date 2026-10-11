import type { IndustrySensorTemplate, IndustryTemplateProfile } from "./types.ts";

const sensors: IndustrySensorTemplate[] = [
  ["TemperatureSensor", "Temperatur", "CAN", "degC", -40, 125, 0.1, 100],
  ["VoltageSensor", "Spannung", "CAN", "V", 0, 1000, 0.1, 50],
  ["CurrentSensor", "Strom", "CAN", "A", -1000, 1000, 0.1, 50],
  ["PressureSensor", "Druck", "CAN", "bar", 0, 250, 0.1, 50],
  ["PositionSensor", "Position", "CAN", "mm", -10000, 10000, 0.01, 20],
  ["SpeedSensor", "Geschwindigkeit", "CAN", "rpm", -20000, 20000, 1, 10],
  ["StatusSensor", "Status", "CAN", "code", 0, 255, 1, 100],
  ["HealthSensor", "HealthStatus", "Ethernet", "code", 0, 15, 1, 1000],
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

export const genericTemplateProfile: IndustryTemplateProfile = {
  gatewayName: "SystemGateway",
  id: "generic",
  label: "industrieunabhaengig",
  sensorTemplates: sensors,
  systemVariants: [
    "SystemControl",
    "SignalAcquisition",
    "DataProcessing",
    "CommunicationHub",
    "SafetyMonitor",
    "PowerManagement",
    "TimingControl",
    "InterfaceBridge",
    "Diagnostics",
    "OperatorPanel",
  ],
};
