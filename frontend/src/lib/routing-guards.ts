export const ROUTING_READ_TIMEOUT_MS = 15_000;
export const ROUTING_WRITE_TIMEOUT_MS = 180_000;
export const MAX_ROUTING_ITEMS = 100_000;

export function routingRequestSignal(signal: AbortSignal | null | undefined, timeout: number): AbortSignal {
  return signal ?? AbortSignal.timeout(timeout);
}

export function isRoutingTimeoutError(error: unknown): boolean {
  return error instanceof DOMException && ["AbortError", "TimeoutError"].includes(error.name);
}

export function assertRoutingItemLimit(itemCount: number): void {
  if (itemCount >= MAX_ROUTING_ITEMS) {
    throw new Error(`Die Routing-Liste überschreitet das Sicherheitslimit von ${MAX_ROUTING_ITEMS} Einträgen.`);
  }
}
