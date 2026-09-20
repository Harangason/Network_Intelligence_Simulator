import type { ExtractedEngineeringChain } from './engineering-specification.ts';

export const ACTUATOR_COMMANDS = {
  OPEN_CLOSE: { length_bits: 1, data_type: 'unsigned', unit: 'code', factor: 1,
    min_value: 0, max_value: 1, semantic: { semantic_type: 'BOOLEAN', meaning: 'Ventil öffnen oder schließen' },
    data: { enum_values: { CLOSE: 0, OPEN: 1 }, default_value: 'CLOSE' } },
  POSITION: { length_bits: 10, data_type: 'unsigned', unit: '%', factor: 0.1,
    min_value: 0, max_value: 100, semantic: { semantic_type: 'NUMERIC', meaning: 'Angeforderte Stellposition' },
    data: { minimum: 0, maximum: 100, resolution: 0.1 } },
} as const;

export function actuatorCommands(text: string): Record<string, unknown> {
  const raw = text.match(/^- (?:Weitere Hinweise:\s*-\s*)?Aktor-Befehle:\s*(\{[^\r\n]*\})\s*$/m)?.[1];
  try {
    const value: unknown = JSON.parse(raw ?? '{}');
    return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
  } catch { return {}; }
}

export function actuatorCommandChoice(command: unknown): string {
  if (!command || typeof command !== 'object' || Array.isArray(command)) return '';
  // Preserve custom encodings; only our exact selections are shown as presets.
  return Object.entries(ACTUATOR_COMMANDS).find(([, value]) => JSON.stringify(command) === JSON.stringify(value))?.[0] ?? 'CUSTOM';
}

export function actuatorCommandLabel(role: string, name: string, purpose = ''): string {
  if (role !== 'ACTUATOR') return '';
  return /ventil|valve/i.test(`${name} ${purpose}`) ? 'Ventilbefehl' : 'Aktorbefehl';
}

export function unresolvedActuatorCommands(chains: ExtractedEngineeringChain[], text: string): string[] {
  const commands = actuatorCommands(text);
  return [...new Set(chains.filter(chain => chain.device_type === 'ActuatorController'
    && !actuatorCommandChoice(commands[chain.hardware_name])
    && !(chain.configuration?.actuator_command_template as { source?: string } | undefined)?.source?.startsWith('wizard-')
    && !/(?:Schaltausgang|SchaltausgangActuator|Stellglied|StellgliedActuator)$/.test(chain.hardware_name))
    .map(chain => chain.hardware_name))];
}

export function selectActuatorCommand(text: string, name: string, choice: string, source = text): string {
  if (!(choice in ACTUATOR_COMMANDS)) return text;
  const commands = actuatorCommands(source);
  commands[name] = ACTUATOR_COMMANDS[choice as keyof typeof ACTUATOR_COMMANDS];
  return `${text.replace(/\n?^- (?:Weitere Hinweise:\s*-\s*)?Aktor-Befehle:[^\r\n]*$/gm, '').trim()}\n- Aktor-Befehle: ${JSON.stringify(commands)}`;
}
