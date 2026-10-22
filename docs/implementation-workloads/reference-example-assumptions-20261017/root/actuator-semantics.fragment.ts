export function proposedActuatorCommand(name: string, purpose = ''): { choice: 'OPEN_CLOSE' | 'POSITION'; reason: string } | null {
  // A drive name does not define its commanded physical quantity. Keep torque
  // and speed requirements available for a reviewed custom wire definition.
  if (/drehmoment|torque|drehzahl|rotational[ -]?speed|\brpm\b/i.test(purpose)) return null;
  if (/ventil|valve/i.test(name) && /\bproportional\w*\b/i.test(purpose))
    return { choice: 'POSITION', reason: 'Proportionales Ventil: Stellposition als editierbare Entwurfsvorgabe' };
  if (/(?:Schaltausgang|SchaltausgangActuator)$/.test(name))
    return { choice: 'OPEN_CLOSE', reason: 'Schaltausgang: Auf/Zu als editierbare Entwurfsvorgabe' };
  if (/(?:Stellglied|StellgliedActuator)$/.test(name))
    return { choice: 'POSITION', reason: 'Stellglied: 0–100 %, Auflösung 0,1 % als editierbare Entwurfsvorgabe' };
  if (/ventil|valve|relais|relay|schalt/i.test(name))
    return { choice: 'OPEN_CLOSE', reason: 'Schaltendes Stellglied; binärer Entwurf, Kodierung prüfen' };
  const meaning = `${name} ${purpose}`;
  const relativePosition = /0\s*(?:[-–—]|\.\.|bis|to)\s*100\s*%|(?:relative\w*\s+(?:stell)?position)|(?:stell)?position\s+(?:in\s+)?(?:prozent|percent)/i;
  if (/(?:stell)?position/i.test(meaning) && relativePosition.test(meaning))
    return { choice: 'POSITION', reason: 'Relative Stellposition: 0–100-%-Entwurf, Bereich und Auflösung prüfen' };
  return null;
}
