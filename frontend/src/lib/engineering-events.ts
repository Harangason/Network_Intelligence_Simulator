import type { EngineeringResource } from "@/lib/types";

export const ENGINEERING_MODEL_CHANGED_EVENT = "engineering:model-changed";

export type EngineeringModelChangedDetail = {
  resource: EngineeringResource | "relations";
  id: string;
  name: string;
};

export function publishEngineeringModelChanged(detail: EngineeringModelChangedDetail) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent<EngineeringModelChangedDetail>(ENGINEERING_MODEL_CHANGED_EVENT, { detail }));
}
