export function routingEnabled(item?: unknown): boolean {
  const configuration = item && typeof item === "object" && "configuration" in item ? item.configuration : undefined;
  const routing = configuration && typeof configuration === "object" && "routing" in configuration ? configuration.routing : undefined;
  return !routing || typeof routing !== "object" || !("enabled" in routing) || routing.enabled !== false;
}

export function withRoutingPermission(configuration: unknown, enabled: boolean): Record<string, unknown> {
  const current = configuration && typeof configuration === "object" && !Array.isArray(configuration)
    ? configuration as Record<string, unknown> : {};
  const routing = current.routing && typeof current.routing === "object" && !Array.isArray(current.routing)
    ? current.routing as Record<string, unknown> : {};
  return { ...current, routing: { ...routing, enabled } };
}
