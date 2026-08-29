export type RoutingApprovalEntry = {
  id: string;
  route_code?: string | null;
  revision?: number | null;
  status?: string | null;
  approval_state?: string | null;
  validation?: { valid?: boolean | null } | null;
  created_at?: string | null;
  modified_at?: string | null;
};

export type RoutingApprovalProgress<T extends RoutingApprovalEntry = RoutingApprovalEntry> = {
  routes: T[];
  total: number;
  approved: number;
  pending: number;
  awaitingValidation: number;
  awaitingApproval: number;
  complete: boolean;
};

const INACTIVE_ROUTE_STATUSES = new Set([
  "OUTDATED",
  "SUPERSEDED",
  "REJECTED",
  "DEPRECATED",
]);

function routeKey(route: RoutingApprovalEntry) {
  return String(route.route_code || route.id).trim().toUpperCase();
}

function routeTimestamp(route: RoutingApprovalEntry) {
  const timestamp = Date.parse(String(route.modified_at || route.created_at || ""));
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function isNewerRoute(candidate: RoutingApprovalEntry, current: RoutingApprovalEntry) {
  const candidateRevision = Number(candidate.revision) || 0;
  const currentRevision = Number(current.revision) || 0;
  if (candidateRevision !== currentRevision) return candidateRevision > currentRevision;

  const candidateTimestamp = routeTimestamp(candidate);
  const currentTimestamp = routeTimestamp(current);
  if (candidateTimestamp !== currentTimestamp) return candidateTimestamp > currentTimestamp;

  return candidate.id.localeCompare(current.id) > 0;
}

export function currentRoutingEntries<T extends RoutingApprovalEntry>(routes: readonly T[]): T[] {
  const latestByRoute = new Map<string, T>();

  for (const route of routes) {
    const key = routeKey(route);
    const current = latestByRoute.get(key);
    if (!current || isNewerRoute(route, current)) latestByRoute.set(key, route);
  }

  return [...latestByRoute.values()].filter((route) => {
    const status = String(route.status || "").toUpperCase();
    const approvalState = String(route.approval_state || "").toUpperCase();
    return !INACTIVE_ROUTE_STATUSES.has(status) && approvalState !== "REJECTED";
  });
}

export function routingApprovalProgress<T extends RoutingApprovalEntry>(
  entries: readonly T[],
): RoutingApprovalProgress<T> {
  const routes = currentRoutingEntries(entries);
  const approved = routes.filter(
    (route) => route.validation?.valid === true
      && String(route.approval_state || "").toUpperCase() === "APPROVED",
  ).length;
  const awaitingValidation = routes.filter((route) => route.validation?.valid !== true).length;
  const awaitingApproval = routes.filter(
    (route) => route.validation?.valid === true
      && String(route.approval_state || "").toUpperCase() !== "APPROVED",
  ).length;

  return {
    routes,
    total: routes.length,
    approved,
    pending: routes.length - approved,
    awaitingValidation,
    awaitingApproval,
    complete: routes.length > 0 && approved === routes.length,
  };
}
