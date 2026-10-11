export function uniqueMessagesById<MESSAGE extends { id: string }>(messages: readonly MESSAGE[]): MESSAGE[] {
  const seen = new Set<string>();
  const unique: MESSAGE[] = [];

  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (seen.has(message.id)) continue;
    seen.add(message.id);
    unique.push(message);
  }

  unique.reverse();
  return unique;
}
