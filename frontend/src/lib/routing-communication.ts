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

export function communicationPage<T>(items: T[], page: number, pageSize = ROUTING_COMMUNICATION_PAGE_SIZE) {
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  const currentPage = Math.min(Math.max(1, page), totalPages);
  return {
    currentPage,
    totalPages,
    items: items.slice((currentPage - 1) * pageSize, currentPage * pageSize),
  };
}
