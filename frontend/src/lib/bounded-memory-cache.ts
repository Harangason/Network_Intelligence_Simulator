export type BoundedMemoryCacheOptions = {
  maxEntries: number;
  ttlMs: number;
  maxValueBytes?: number;
};

type CacheEntry<VALUE> = {
  value: VALUE;
  updatedAt: number;
  expiresAt: number;
  bytes: number;
};

function valueBytes(value: unknown): number {
  try {
    return new TextEncoder().encode(JSON.stringify(value)).length;
  } catch {
    return 0;
  }
}

export class BoundedMemoryCache<KEY, VALUE> {
  private readonly entries = new Map<KEY, CacheEntry<VALUE>>();

  constructor(private readonly options: BoundedMemoryCacheOptions) {
    if (options.maxEntries < 1) throw new Error("BoundedMemoryCache benötigt mindestens einen Eintrag.");
    if (options.ttlMs < 1) throw new Error("BoundedMemoryCache benötigt eine positive TTL.");
  }

  get size() {
    this.prune();
    return this.entries.size;
  }

  get(key: KEY): VALUE | undefined {
    const entry = this.entries.get(key);
    if (!entry) return undefined;
    if (entry.expiresAt <= Date.now()) {
      this.entries.delete(key);
      return undefined;
    }
    this.entries.delete(key);
    this.entries.set(key, entry);
    return entry.value;
  }

  set(key: KEY, value: VALUE): boolean {
    const bytes = valueBytes(value);
    if (this.options.maxValueBytes && bytes > this.options.maxValueBytes) return false;
    const now = Date.now();
    this.entries.delete(key);
    this.entries.set(key, { value, updatedAt: now, expiresAt: now + this.options.ttlMs, bytes });
    this.prune();
    return true;
  }

  delete(key: KEY): boolean {
    return this.entries.delete(key);
  }

  clear() {
    this.entries.clear();
  }

  values(): VALUE[] {
    this.prune();
    return [...this.entries.values()].map((entry) => entry.value);
  }

  stats() {
    this.prune();
    const bytes = [...this.entries.values()].reduce((total, entry) => total + entry.bytes, 0);
    return {
      entries: this.entries.size,
      maxEntries: this.options.maxEntries,
      bytes,
      maxValueBytes: this.options.maxValueBytes ?? null,
      ttlMs: this.options.ttlMs,
    };
  }

  private prune() {
    const now = Date.now();
    for (const [key, entry] of this.entries) {
      if (entry.expiresAt <= now) this.entries.delete(key);
    }
    while (this.entries.size > this.options.maxEntries) {
      const oldest = this.entries.keys().next().value;
      if (oldest === undefined) break;
      this.entries.delete(oldest);
    }
  }
}
