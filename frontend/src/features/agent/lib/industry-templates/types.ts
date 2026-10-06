export type IndustrySensorTemplate = {
  hardwareName: string;
  signalName: string;
  interfaceType: string;
  cycleMs: number;
  unit?: string;
  minValue?: number;
  maxValue?: number;
  factor?: number;
};

export type IndustryTemplateProfile = {
  gatewayName?: string;
  id: string;
  ignoredSystemNames?: readonly string[];
  label: string;
  sensorTemplates: readonly IndustrySensorTemplate[];
  systemAliases?: Readonly<Record<string, string>>;
  systemVariants: readonly string[];
};
