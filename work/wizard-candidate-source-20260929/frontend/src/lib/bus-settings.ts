export const DEFAULT_BUS_PARTICIPANT_LIMITS: Record<string, number> = {
  can: 64, can_fd: 64, can_xl: 64, lin: 64, automotive_ethernet: 256, flexray: 64,
};
export const BUS_SETTING_LABELS: Record<string, string> = {
  can: "CAN", can_fd: "CAN-FD", can_xl: "CAN-XL", lin: "LIN", automotive_ethernet: "Ethernet", flexray: "FlexRay",
};
export function busSettingKey(value: string): string {
  const key = value.toLowerCase().replace(/^detected:/, "").replace(/[^a-z0-9]/g, "");
  return ({canfd: "can_fd", canxl: "can_xl", ethernet: "automotive_ethernet", automotiveethernet: "automotive_ethernet", someip: "automotive_ethernet"} as Record<string, string>)[key] ?? key;
}
export function normalizeBusLimits(value: unknown): Record<string, number> {
  const result = {...DEFAULT_BUS_PARTICIPANT_LIMITS};
  if (value && typeof value === "object" && !Array.isArray(value)) {
    for (const [key, limit] of Object.entries(value)) {
      if (busSettingKey(key) in result && Number.isInteger(limit) && (limit === 0 || limit >= 2) && limit <= 100000) result[busSettingKey(key)] = limit;
    }
  }
  return result;
}
export function busBranchCapacity(limits: Record<string, number>, technology: string): number {
  const limit = limits[busSettingKey(technology)] ?? 0;
  return limit ? limit - 1 : 100000;
}
