export function selectDeviceConnectionInTask(text: string, name: string, technology: string): string {
  const marker = text.match(/^- Geräteanschlüsse:\s*(\{[^\r\n]*\})\s*$/m)?.[1];
  let connections: Record<string, string> = {};
  try {
    const parsed: unknown = marker ? JSON.parse(marker) : {};
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      connections = parsed as Record<string, string>;
    }
  } catch {
    // An explicit reviewed choice replaces an incomplete manual marker.
  }
  if (technology) connections[name] = technology;
  else delete connections[name];
  return `${text.replace(/\n?^- Geräteanschlüsse:[^\r\n]*$/gm, "").trim()}\n- Geräteanschlüsse: ${JSON.stringify(connections)}`;
}
