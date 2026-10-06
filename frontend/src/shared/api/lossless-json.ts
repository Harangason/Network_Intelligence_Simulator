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
