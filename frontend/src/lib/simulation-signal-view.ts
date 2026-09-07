import type { ModelSignalPoint, ModelSignalSeries } from "./types";

export type SignalBehaviorFilter = "ALL" | "DYNAMIC" | "STATIC";
export type SignalKindFilter = "ALL" | "STATE" | "PHYSICAL" | "OTHER";

export function signalCurrentPoint(series: ModelSignalSeries, playhead: number) {
  return [...series.points].reverse().find((point) => point.time_s <= playhead) ?? series.points[0];
}

export function signalIsDynamic(series: ModelSignalSeries) {
  const values = series.points.map((point) => point.value).filter((value): value is number => value !== null);
  if (values.length < 2) return false;
  const first = values[0];
  const tolerance = Math.max(Math.abs(series.resolution || 0), Math.abs(series.maximum - series.minimum) * 0.00001, 1e-9);
  return values.some((value) => Math.abs(value - first) > tolerance);
}

export function signalKind(series: ModelSignalSeries): Exclude<SignalKindFilter, "ALL"> {
  const semantic = String(series.semantic_type ?? "").toUpperCase();
  if (["ENUM", "STATE", "BOOLEAN", "BITFIELD", "EVENT"].includes(semantic) || series.behavior_type === "STATE_MACHINE") return "STATE";
  if (series.behavior_type === "PHYSICS_MODEL" || series.model_label === "PHYSICS_BASED") return "PHYSICAL";
  return "OTHER";
}

export function formatSignalValue(series: ModelSignalSeries, point?: ModelSignalPoint) {
  if (!point || point.value === null) return "–";
  const raw = Number.isInteger(point.value) ? String(point.value) : Number(point.value).toFixed(Math.max(0, Math.min(3, String(series.resolution || 0.01).split(".")[1]?.length ?? 2)));
  const display = point.state ?? point.display_value;
  if (display !== null && display !== undefined && String(display).trim() && String(display) !== raw) {
    return `${display} (${raw})${series.unit ? ` ${series.unit}` : ""}`;
  }
  if (signalKind(series) === "STATE") return `Zustand ${raw} · Bezeichnung fehlt`;
  return `${raw}${series.unit ? ` ${series.unit}` : ""}`;
}

export function filterSignalSeries(
  series: ModelSignalSeries[],
  options: { search: string; behavior: SignalBehaviorFilter; kind: SignalKindFilter },
) {
  const query = options.search.trim().toLocaleLowerCase("de");
  return series.filter((item) => {
    if (query && !`${item.signal} ${item.unit} ${item.behavior_type} ${item.semantic_type ?? ""}`.toLocaleLowerCase("de").includes(query)) return false;
    const dynamic = signalIsDynamic(item);
    if (options.behavior === "DYNAMIC" && !dynamic) return false;
    if (options.behavior === "STATIC" && dynamic) return false;
    return options.kind === "ALL" || signalKind(item) === options.kind;
  });
}

export function initialSignalSelection(series: ModelSignalSeries[], limit = 18) {
  return [...series]
    .sort((left, right) => Number(signalIsDynamic(right)) - Number(signalIsDynamic(left)) || Number(signalKind(right) === "STATE") - Number(signalKind(left) === "STATE") || left.signal.localeCompare(right.signal))
    .slice(0, limit)
    .map((item) => item.signal_id);
}
