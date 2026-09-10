/** Domain words, not model BPE tokens: identity matching needs word boundaries.
 * Unknown compounds remain intact instead of matching arbitrary substrings.
 */
const PARTS = new Set((
  "fahrwerk fahrdynamik fahrer beifahrer sitz tuer tuere fond links rechts vorne hinten " +
  "daempfer regelung steuerung brems bremse bremsen sensorik lenkung hinterachs allrad anhaenger " +
  "motor elektro abgas nachbehandlung getriebe kraftstoff reifen druck kontrolle " +
  "bordnetz management batterie energie versorgung kuehl mittel kreislauf oel temperatur " +
  "innen aussen licht raum wischer heck klappe schiebe dach assistenz ultraschall " +
  "schalt ausgang stellglied erfassung zustand befehl status funktion signal sensor controller actuator " +
  "front rear left right upper lower engine electric oil coolant exhaust gas temperature " +
  "suspension travel damper position wheel speed load angle torque acceleration pressure " +
  "brake tire seatbelt seat door radar lidar camera voltage current battery fuel level " +
  "throttle turbo boost transmission clutch gear selector cabin ambient light rain " +
  "cell min max urea valve egr intake air yaw pitch roll rate longitudinal lateral vertical " +
  "control body comfort power train inverter charging charge thermal heating cooling " +
  "axle bearing bogie vibration traction diagnostic gateway input output data health quality mode " +
  "robot motion arm conveyor belt spindle pump room floor hvac water tank powertrain system sound dc link accelerator pedal washer fluid"
).split(/\s+/));

const SORTED_PARTS = [...PARTS].sort((a, b) => b.length - a.length);
const TOKEN_CACHE = new Map<string, readonly string[]>();

function splitCompound(word: string): string[] {
  if (PARTS.has(word)) return [word];
  const memo = new Map<number, string[] | null>();
  const split = (offset: number): string[] | null => {
    if (offset === word.length) return [];
    if (memo.has(offset)) return memo.get(offset)!;
    for (const part of SORTED_PARTS) {
      if (!word.startsWith(part, offset)) continue;
      const tail = split(offset + part.length);
      if (tail) { const result = [part, ...tail]; memo.set(offset, result); return result; }
    }
    memo.set(offset, null);
    return null;
  };
  return split(0) ?? [word];
}

export function engineeringTokens(value: unknown): readonly string[] {
  const raw = String(value ?? "");
  const cached = TOKEN_CACHE.get(raw);
  if (cached) return cached;
  const text = raw
    .replace(/([A-ZÄÖÜ]+)([A-ZÄÖÜ][a-zäöüß])/g, "$1 $2")
    .replace(/([a-zäöüß0-9])([A-ZÄÖÜ])/g, "$1 $2")
    .toLowerCase().replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss")
    .normalize("NFKD").replace(/[\u0300-\u036f]/g, "");
  const tokens = Object.freeze(text.split(/[^a-z0-9]+/).filter(Boolean).flatMap(splitCompound));
  if (TOKEN_CACHE.size >= 4096) TOKEN_CACHE.delete(TOKEN_CACHE.keys().next().value!);
  TOKEN_CACHE.set(raw, tokens);
  return tokens;
}

export function containsEngineeringTerm(value: unknown, term: string): boolean {
  const tokens = engineeringTokens(value);
  const expected = engineeringTokens(term);
  return expected.length > 0 && tokens.some((_, index) => expected.every((part, i) => tokens[index + i] === part));
}
