import type { ModelSimulationTrace, RuntimeRouteMetric } from "../../../shared/api/types";

export type LoadPoint = ModelSimulationTrace["bus_load"][number];
export const CHART_COLORS = ["var(--accent)", "#2478b5", "#b86a15", "#9854a6", "#c04454", "#16877d"];
export function loadWindow(points: LoadPoint[], ids: string[], start: number, end: number) {
  const selected = new Set(ids);
  return points.filter(p => selected.has(p.network_id) && Number.isFinite(p.time_s) && p.time_s >= 0
    && p.time_s >= start && p.time_s <= end && Number.isFinite(p.load_percent) && p.load_percent >= 0)
    .toSorted((a, b) => a.time_s - b.time_s || a.network_id.localeCompare(b.network_id));
}
export function extremaSample(points: LoadPoint[]) {
  if (points.length <= 800) return points;
  const selected = new Set([0, points.length - 1]);
  const size = Math.ceil(points.length / 399);
  for (let start = 0; start < points.length; start += size) {
    let low = start, high = start;
    for (let i = start + 1; i < Math.min(start + size, points.length); i++) {
      if (points[i].load_percent < points[low].load_percent) low = i;
      if (points[i].load_percent > points[high].load_percent) high = i;
    }
    selected.add(low); selected.add(high);
  }
  return [...selected].toSorted((a, b) => a - b).map(i => points[i]);
}
export function zoomWindow(start: number, end: number, total: number, factor: number) {
  const span = Math.min(total, Math.max(total / 100, (end - start) * factor));
  const nextStart = Math.max(0, Math.min(total - span, (start + end - span) / 2));
  return [nextStart, nextStart + span] as const;
}
export function jitterAssessment(route: RuntimeRouteMetric) {
  const received = (route as RuntimeRouteMetric & { received_event_count?: number }).received_event_count;
  const hasIntervals = received === undefined ? Number.isFinite(route.actual_max_cycle_ms) && route.actual_max_cycle_ms > 0 : received >= 2;
  if (!hasIntervals || !Number.isFinite(route.configured_cycle_ms) || route.configured_cycle_ms <= 0
    || !Number.isFinite(route.maximum_jitter_ms) || route.maximum_jitter_ms < 0) return "Keine bewertbaren Intervalle";
  if (route.jitter_limit_ms == null || !Number.isFinite(route.jitter_limit_ms) || route.jitter_limit_ms < 0) return "Grenze offen";
  return route.maximum_jitter_ms > route.jitter_limit_ms + 1e-7 ? "Grenze überschritten" : "Innerhalb der Grenze";
}
export function forecastUnderAssumptions(source: unknown) {
  if (!source || typeof source !== "object" || !("networks" in source) || !Array.isArray(source.networks)) return null;
  const rows = source.networks.filter((r: Record<string, unknown>) => r.capacity_applicable !== false);
  if (!rows.length) return null;
  const values = (field: string) => rows.map((r: Record<string, unknown>) => {
    const assumption = r.simulation_capacity as Record<string, unknown> | undefined;
    return r.capacity_verified === true ? r[field] : assumption?.status === "CALCULATED_UNDER_ASSUMPTIONS" ? assumption[field] : undefined;
  });
  const peak = values("peak_load_percent"), reserve = values("capacity_reserve_percent");
  const valid = (items: unknown[]): items is number[] => items.every(v => typeof v === "number" && Number.isFinite(v));
  return { peak: valid(peak) && peak.every(v => v >= 0) ? Math.max(...peak) : null,
    reserve: valid(reserve) ? Math.min(...reserve) : null, networks: rows.length };
}
