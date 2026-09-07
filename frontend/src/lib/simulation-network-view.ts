import { physicalNetworkAssignments, type NetworkTopology } from "./topology.ts";
import type { ModelSimulationTrace, RuntimeNetworkMetric, RuntimeRouteMetric } from "./types";

type TraceFrame = ModelSimulationTrace["frames"][number];

function unique(values: Array<string | null | undefined>): string[] {
  return [...new Set(values.map((value) => String(value ?? "").trim()).filter(Boolean))];
}

function participantNames(topology?: Partial<NetworkTopology>): Map<string, string> {
  const names = new Map<string, string>();
  for (const node of topology?.nodes ?? []) {
    names.set(node.id, node.name);
    if (node.engineeringId) names.set(node.engineeringId, node.name);
  }
  return names;
}

function resolveNames(ids: Array<string | null | undefined>, names: Map<string, string>): string[] {
  return unique(ids.map((id) => names.get(String(id ?? "")) ?? id));
}

function semanticNetworkName(frames: TraceFrame[], topology?: Partial<NetworkTopology>): string {
  if (!topology?.nodes?.length || !topology.edges?.length || !frames.length) return "";
  const routeIds = new Set(frames.map((frame) => frame.route_id));
  const assignments = physicalNetworkAssignments({ nodes: topology.nodes, edges: topology.edges });
  const counts = new Map<string, number>();
  for (const edge of topology.edges) {
    const matched = Object.values(edge.routingMetadata ?? {}).some((route) => (
      routeIds.has(route.routeId)
      || [...routeIds].some((routeId) => routeId === `route-${route.routeCode}` || routeId.startsWith(`route-${route.routeCode}-`))
    ));
    if (!matched) continue;
    const name = assignments.get(edge.id)?.name;
    if (name) counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  return [...counts.entries()].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))[0]?.[0] ?? "";
}

export function technologyLabel(technology: string): string {
  return {
    can_fd: "CAN FD",
    automotive_ethernet: "Automotive Ethernet",
    lin: "LIN",
    flexray: "FlexRay",
  }[technology.toLowerCase()] ?? technology.replaceAll("_", " ").toUpperCase();
}

export function formatParticipants(participants: string[], maximum = 3): string {
  if (!participants.length) return "nicht ermittelt";
  const visible = participants.slice(0, maximum);
  const remaining = participants.length - visible.length;
  return `${visible.join(", ")}${remaining > 0 ? ` +${remaining}` : ""}`;
}

export function runtimeNetworkPresentation(
  network: RuntimeNetworkMetric,
  frames: TraceFrame[],
  topology?: Partial<NetworkTopology>,
) {
  const names = participantNames(topology);
  const networkFrames = frames.filter((frame) => frame.network === network.network_id);
  const traceSenders = networkFrames.map((frame) => [
    frame.source_logical_address,
    frame.source_name || names.get(String(frame.sender ?? "")) || frame.sender,
  ].filter(Boolean).join(" · "));
  const traceReceivers = networkFrames.flatMap((frame) => (
    (frame.receivers ?? []).map((receiver, index) => [
      frame.destination_logical_addresses?.[index],
      frame.destination_names?.[index] || names.get(String(receiver)) || receiver,
    ].filter(Boolean).join(" · "))
  ));
  const senders = unique(traceSenders.length ? traceSenders : network.senders ?? []);
  const receivers = unique(traceReceivers.length ? traceReceivers : network.receivers ?? []);
  const configuredName = String(network.network_name ?? "").trim();
  const semanticName = semanticNetworkName(networkFrames, topology);
  const fallbackOwner = receivers[0] ?? senders[0];
  const name = configuredName && configuredName !== network.network_id
    ? configuredName
    : semanticName
      ? semanticName
    : fallbackOwner
      ? `${fallbackOwner} · ${technologyLabel(network.technology)}`
      : technologyLabel(network.technology);
  return { name, senders, receivers };
}

export function runtimeRoutePresentation(
  route: RuntimeRouteMetric,
  frames: TraceFrame[],
  topology?: Partial<NetworkTopology>,
) {
  const names = participantNames(topology);
  const firstFrame = frames.find((frame) => frame.route_id === route.route_id);
  const senderName = String(firstFrame?.source_name || route.sender || names.get(String(firstFrame?.sender ?? "")) || firstFrame?.sender || "nicht ermittelt");
  const sender = [firstFrame?.source_logical_address, senderName].filter(Boolean).join(" · ");
  const receiverNames = firstFrame?.destination_names?.length
    ? firstFrame.destination_names
    : route.receivers?.length ? route.receivers : resolveNames(firstFrame?.receivers ?? [], names);
  const receivers = unique(receiverNames.map((name, index) => (
    [firstFrame?.destination_logical_addresses?.[index], name].filter(Boolean).join(" · ")
  )));
  const technicalName = String(route.route_name || route.route_id);
  const generatedName = technicalName === route.route_id || /^(?:route-)?RT-/i.test(technicalName);
  return {
    name: generatedName ? `${sender} → ${formatParticipants(receivers, 2)}` : technicalName,
    sender,
    receivers,
  };
}
