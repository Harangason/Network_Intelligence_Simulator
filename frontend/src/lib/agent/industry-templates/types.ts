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
  label: string;
  sensorTemplates: readonly IndustrySensorTemplate[];
  systemVariants: readonly string[];
};
