export type SimulationScope = {
  mode: "ALL" | "MESSAGE" | "SIGNAL" | "SELECTED";
  include_all: boolean;
  message_ids: string[];
  signal_ids: string[];
  reason: string;
};

export function simulationScopeFrom(value: unknown): SimulationScope {
  const raw = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const mode = ["MESSAGE", "SIGNAL", "SELECTED"].includes(String(raw.mode)) && raw.include_all !== true
    ? raw.mode as SimulationScope["mode"] : "ALL";
  const ids = (items: unknown) => Array.isArray(items) ? [...new Set(items.filter((item): item is string => typeof item === "string" && Boolean(item)))].sort() : [];
  return { mode, include_all: mode === "ALL", message_ids: mode === "ALL" ? [] : ids(raw.message_ids),
    signal_ids: mode === "ALL" ? [] : ids(raw.signal_ids), reason: mode === "ALL" ? "" : String(raw.reason ?? "") };
}

export function simulationScopeValid(scope: SimulationScope): boolean {
  return scope.include_all || Boolean((scope.message_ids.length + scope.signal_ids.length) && scope.reason.trim());
}

export function sameSimulationScope(left: SimulationScope, right: SimulationScope): boolean {
  return JSON.stringify(simulationScopeFrom(left)) === JSON.stringify(simulationScopeFrom(right));
}
