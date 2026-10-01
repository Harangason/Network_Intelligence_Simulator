import { aerospaceTemplateProfile } from "./aerospace.ts";
import { automotiveTemplateProfile } from "./automotive.ts";
import { buildingAutomationTemplateProfile } from "./building-automation.ts";
import { embeddedSystemsTemplateProfile } from "./embedded-systems.ts";
import { energyTemplateProfile } from "./energy.ts";
import { genericTemplateProfile } from "./generic.ts";
import { genericNetworkingTemplateProfile } from "./generic-networking.ts";
import { industrialAutomationTemplateProfile } from "./industrial-automation.ts";
import { marineTemplateProfile } from "./marine.ts";
import { railTemplateProfile } from "./rail.ts";
import { roboticsRosTemplateProfile } from "./robotics-ros.ts";
import type { IndustryTemplateProfile } from "./types.ts";

export const INDUSTRY_TEMPLATE_PROFILES: Record<string, IndustryTemplateProfile> = {
  aerospace: aerospaceTemplateProfile,
  automotive: automotiveTemplateProfile,
  building_automation: buildingAutomationTemplateProfile,
  embedded_systems: embeddedSystemsTemplateProfile,
  energy: energyTemplateProfile,
  generic: genericTemplateProfile,
  generic_networking: genericNetworkingTemplateProfile,
  industrial_automation: industrialAutomationTemplateProfile,
  marine: marineTemplateProfile,
  rail: railTemplateProfile,
  robotics_ros: roboticsRosTemplateProfile,
} satisfies Record<string, IndustryTemplateProfile>;

export function industryTemplateProfile(domain: string): IndustryTemplateProfile {
  return INDUSTRY_TEMPLATE_PROFILES[domain] ?? INDUSTRY_TEMPLATE_PROFILES.generic;
}

export function industryTemplateLabel(domain: string): string {
  return industryTemplateProfile(domain).label;
}

export type { IndustrySensorTemplate, IndustryTemplateProfile } from "./types.ts";
