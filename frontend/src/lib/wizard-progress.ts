export function parameterProgressTarget(configured: boolean, toolState: string | undefined, statusProgress: number) {
  if (toolState === "input-streaming" || toolState === "input-available") return 90;
  if (configured || toolState === "output-available") return statusProgress;
  return 0;
}

export function symbolicProgressAt(from: number, to: number, elapsedMs: number) {
  const elapsed = Math.max(0, Math.min(1, elapsedMs / 1600));
  const eased = 1 - (1 - elapsed) ** 3;
  return Math.round(Math.max(0, Math.min(100, from + (to - from) * eased)));
}
