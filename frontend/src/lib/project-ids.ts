const NETWORK_PROJECT_RANDOM_BYTES = 8;

type CryptoLike = {
  randomUUID?: () => string;
  getRandomValues?: <T extends Uint8Array>(array: T) => T;
};

function randomHexSegment(length: number, cryptoSource: CryptoLike | undefined = globalThis.crypto): string {
  const nativeUuid = typeof cryptoSource?.randomUUID === "function" ? cryptoSource.randomUUID() : "";
  const uuidSegment = nativeUuid.replace(/-/g, "").slice(0, length);
  if (uuidSegment.length >= length) return uuidSegment;

  if (typeof cryptoSource?.getRandomValues === "function") {
    const bytes = cryptoSource.getRandomValues(new Uint8Array(NETWORK_PROJECT_RANDOM_BYTES));
    return Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("").slice(0, length);
  }

  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`.replace(/[^a-z0-9]/gi, "").slice(0, length);
}

export function createNetworkProjectId(cryptoSource?: CryptoLike): string {
  const stamp = new Date().toISOString().replace(/[-:T.Z]/g, "").slice(0, 17);
  return `network-project-${stamp}-${randomHexSegment(8, cryptoSource)}`;
}

