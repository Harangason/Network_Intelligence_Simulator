import type { IndustrySensorTemplate, IndustryTemplateProfile } from "./types.ts";

const sensors: IndustrySensorTemplate[] = [
  ["PortUtilizationSensor", "PortAuslastung", "Ethernet", "%", 0, 100, 0.01, 100],
  ["PacketDropSensor", "Paketverlust", "Ethernet", "%", 0, 100, 0.001, 100],
  ["LatencySensor", "Latenz", "Ethernet", "ms", 0, 10000, 0.001, 100],
  ["JitterSensor", "Jitter", "Ethernet", "ms", 0, 1000, 0.001, 100],
  ["TemperatureSensor", "Geraetetemperatur", "Ethernet", "degC", -20, 110, 0.1, 1000],
  ["FanSpeedSensor", "Luefterdrehzahl", "Ethernet", "rpm", 0, 30000, 1, 1000],
  ["LinkStateSensor", "LinkStatus", "Ethernet", "code", 0, 7, 1, 100],
  ["ErrorCounterSensor", "Fehlerzaehler", "Ethernet", "count", 0, 1000000, 1, 1000],
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

export const genericNetworkingTemplateProfile: IndustryTemplateProfile = {
  gatewayName: "NetworkGateway",
  id: "generic_networking",
  label: "Generic Networking",
  sensorTemplates: sensors,
  systemVariants: [
    "CoreSwitch",
    "DistributionSwitch",
    "AccessSwitch",
    "EdgeRouter",
    "Firewall",
    "LoadBalancer",
    "WirelessController",
    "NetworkManagement",
    "TimeServer",
    "TelemetryCollector",
    "StorageGateway",
    "ApplicationGateway",
    "DnsResolver",
    "VpnConcentrator",
    "MonitoringNode",
  ],
};
