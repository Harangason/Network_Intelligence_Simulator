/** Preserve protocol integers outside JavaScript's exact range as decimal text.
 * Scan JSON tokens before parsing so both browsers and Node preserve original
 * digits, including nested saved values and their provenance. JSON.parse still
 * owns syntax validation; text inside quoted strings is never rewritten.
 */
export function parseLosslessJson(text: string): unknown {
  const tokens = /"(?:[^"\\]|\\[\s\S])*"|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/g;
  return JSON.parse(text.replace(tokens, token => {
    if (token.startsWith('"') || /[.eE]/.test(token)) return token;
    const integer = BigInt(token);
    return integer > BigInt(Number.MAX_SAFE_INTEGER) || integer < BigInt(Number.MIN_SAFE_INTEGER)
      ? JSON.stringify(token) : token;
  }));
}

export async function readLosslessJson(response: Response): Promise<unknown> {
  return parseLosslessJson(await response.text());
}

/** A successful status never turns an interrupted/invalid body into success. */
export async function readApiJson(response: Response): Promise<unknown> {
  let payload: unknown;
  try {
    payload = await readLosslessJson(response);
  } catch (error) {
    if (response.ok) throw error;
    throw new Error(`API-Fehler ${response.status}`);
  }
  if (!response.ok) {
    const detail = payload && typeof payload === 'object' && 'error' in payload
      ? (payload as { error?: unknown }).error : undefined;
    throw new Error(typeof detail === 'string' ? detail : `API-Fehler ${response.status}`);
  }
  return payload;
}
