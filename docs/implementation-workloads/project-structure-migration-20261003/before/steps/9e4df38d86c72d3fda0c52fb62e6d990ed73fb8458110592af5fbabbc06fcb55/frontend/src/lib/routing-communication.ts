import type { RoutingEntry } from "./types";

export const ROUTING_COMMUNICATION_PAGE_SIZE = 25;

export type CommunicationState =
  | "received"
  | "via_gateway"
  | "blocked"
  | "ends_at_gateway"
  | "not_routed";

export type CommunicationAssessment = {
  state: CommunicationState;
  label: string;
  detail: string;
  repairable: boolean;
};

export type CommunicationRouteGroup = {
  key: string;
  messageId: string;
  fallbackLabel: string;
  routes: RoutingEntry[];
};

export type CommunicationRouteSelection = {
  route: RoutingEntry;
  assessment: CommunicationAssessment;
};

export function routeGatewayIds(route: RoutingEntry) {
  return route.route.gateways
    .map((gateway) => typeof gateway === "string" ? gateway : gateway.node_id ?? "")
    .filter(Boolean);
}

export function routeMessageIds(route: RoutingEntry) {
  return [...new Set([
    ...(route.payload.message_ids ?? []),
    ...(route.payload.message_id ? [route.payload.message_id] : []),
  ].filter(Boolean))];
}

export function groupCommunicationRoutes(routes: RoutingEntry[]): CommunicationRouteGroup[] {
  const groups = new Map<string, CommunicationRouteGroup>();

  routes.forEach((route) => {
    const messageIds = routeMessageIds(route);
    const fallbackLabel = String(route.payload.topic ?? route.payload.data_object ?? route.name).trim();
    const payloads = messageIds.length
      ? messageIds.map((messageId) => ({ key: `message:${messageId}`, messageId }))
      : [{ key: fallbackLabel ? `payload:${fallbackLabel}` : `route:${route.id}`, messageId: "" }];

    payloads.forEach(({ key, messageId }) => {
      const current = groups.get(key);
      if (current) {
        current.routes.push(route);
        return;
      }
      groups.set(key, { key, messageId, fallbackLabel, routes: [route] });
    });
  });

  return [...groups.values()];
}

export function relevantReceiverIds(routes: RoutingEntry[], senderId: string) {
  return [...new Set(routes
    .filter((route) => route.source.node_id === senderId)
    .flatMap((route) => route.destinations.map((destination) => destination.node_id)))];
}

export function assessCommunication(route: RoutingEntry, receiverId: string): CommunicationAssessment {
  const isDestination = route.destinations.some((destination) => destination.node_id === receiverId);
  const gateways = routeGatewayIds(route);
  const isBlocked = route.validation?.valid === false
    || route.status === "CONFLICT"
    || route.status === "REJECTED"
    || route.approval_state === "REJECTED";

  if (isDestination && isBlocked) {
    const issue = route.validation?.errors?.[0]?.message
      ?? route.validation?.warnings?.[0]?.message
      ?? "Die Route ist vorhanden, aber technisch nicht freigegeben.";
    return { state: "blocked", label: "Blockiert", detail: issue, repairable: true };
  }
  if (isDestination && gateways.length > 0) {
    return {
      state: "via_gateway",
      label: "Empfangen via Gateway",
      detail: `${gateways.length} Gateway${gateways.length === 1 ? "" : "s"} im Kommunikationspfad.`,
      repairable: false,
    };
  }
  if (isDestination) {
    return { state: "received", label: "Empfangen", detail: "Direkte TX/RX-Beziehung vorhanden.", repairable: false };
  }
  if (gateways.includes(receiverId)) {
    return {
      state: "ends_at_gateway",
      label: "Endet am Gateway",
      detail: "Die Botschaft erreicht diesen Knoten nur als Gateway, aber nicht als Consumer.",
      repairable: true,
    };
  }
  return {
    state: "not_routed",
    label: "Nicht empfangen",
    detail: "Für diesen Consumer ist kein vollständiger Routingpfad definiert.",
    repairable: true,
  };
}

const COMMUNICATION_STATE_PRIORITY: Record<CommunicationState, number> = {
  received: 0,
  via_gateway: 1,
  blocked: 2,
  ends_at_gateway: 3,
  not_routed: 4,
};

export function selectCommunicationRoute(routes: RoutingEntry[], receiverId: string): CommunicationRouteSelection | null {
  return routes
    .map((route, index) => ({ route, assessment: assessCommunication(route, receiverId), index }))
    .sort((left, right) =>
      COMMUNICATION_STATE_PRIORITY[left.assessment.state] - COMMUNICATION_STATE_PRIORITY[right.assessment.state]
      || Number(right.route.validation?.valid === true) - Number(left.route.validation?.valid === true)
      || Number(right.route.approval_state === "APPROVED") - Number(left.route.approval_state === "APPROVED")
      || routeGatewayIds(left.route).length - routeGatewayIds(right.route).length
      || left.index - right.index,
    )[0] ?? null;
}

export function communicationPage<T>(items: T[], page: number, pageSize = ROUTING_COMMUNICATION_PAGE_SIZE) {
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  const currentPage = Math.min(Math.max(1, page), totalPages);
  return {
    currentPage,
    totalPages,
    items: items.slice((currentPage - 1) * pageSize, currentPage * pageSize),
  };
}
