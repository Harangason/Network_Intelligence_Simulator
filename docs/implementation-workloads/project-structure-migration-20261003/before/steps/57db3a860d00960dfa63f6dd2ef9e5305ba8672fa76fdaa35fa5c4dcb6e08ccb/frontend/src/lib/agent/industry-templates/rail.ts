import type { IndustrySensorTemplate, IndustryTemplateProfile } from "./types.ts";

const sensors: IndustrySensorTemplate[] = [
  ["TrainSpeedSensor", "Zuggeschwindigkeit", "Ethernet", "km/h", 0, 400, 0.1, 20],
  ["BrakePressureSensor", "Bremsleitungsdruck", "CAN", "bar", 0, 12, 0.01, 10],
  ["DoorStateSensor", "TuerStatus", "CAN", "code", 0, 7, 1, 50],
  ["BogiesVibrationSensor", "Drehgestellschwingung", "CAN", "mm/s", 0, 100, 0.01, 20],
  ["PantographCurrentSensor", "Stromabnehmerstrom", "Ethernet", "A", 0, 2000, 1, 50],
  ["AxleTemperatureSensor", "Achslagertemperatur", "CAN", "degC", -40, 180, 0.1, 100],
  ["PassengerCountSensor", "Fahrgastzahl", "Ethernet", "count", 0, 2000, 1, 1000],
  ["SignalAspectSensor", "Signalbegriff", "Ethernet", "code", 0, 255, 1, 100],
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

export const railTemplateProfile: IndustryTemplateProfile = {
  gatewayName: "TrainGateway",
  id: "rail",
  label: "Rail",
  sensorTemplates: sensors,
  systemVariants: [
    "TrainControl",
    "BrakeControl",
    "DoorControl",
    "TractionControl",
    "PassengerInformation",
    "HVACControl",
    "PantographControl",
    "Bogiesensorik",
    "SignallingInterface",
    "EventRecorder",
    "WaysideCommunication",
    "EnergyMetering",
    "CouplingControl",
    "LightingControl",
    "SafetyInterlock",
  ],
};
