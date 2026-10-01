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

export function proposedDeviceConnection(name: string, technologies: string[]): { technology: string; reason: string } | null {
  const available = new Map(technologies.map(technology => [technology.toLowerCase().replace(/[^a-z0-9]/g, ''), technology]));
  if (available.size === 1) return { technology: technologies[0], reason: 'Einzige bestätigte Netzwerktechnologie im Auftrag' };
  const pick = (technology: string, reason: string) => {
    const selected = available.get(technology.toLowerCase().replace(/[^a-z0-9]/g, ''));
    return selected ? { technology: selected, reason } : null;
  };
  if (/gateway|edge|backbone|computer/i.test(name)) return pick('Ethernet', 'Genannter Backbone oder Edge-Anschluss');
  if (/position|servo|linear|motion|motor|drive|achse|axis/i.test(name))
    return pick('EtherCAT', 'Zeitkritische Bewegungsfunktion');
  if (/plc|sps|ventil|valve|temperatur|temperature|druck|pressure|durchfluss|flow/i.test(name))
    return pick('ProfiNET', 'Prozess- oder Steuerungsteilnehmer');
  return null;
}
