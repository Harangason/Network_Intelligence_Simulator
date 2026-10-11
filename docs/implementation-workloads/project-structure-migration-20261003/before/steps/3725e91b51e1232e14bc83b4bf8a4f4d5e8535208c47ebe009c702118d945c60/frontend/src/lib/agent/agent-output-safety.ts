export const AGENT_OUTPUT_REJECTED_NOTICE =
  "Agent-Ausgabe verworfen: Sie enthielt einen externen Beispiel-API-Aufruf oder einen imitierten Toolaufruf statt eines Simulator-Tools. Der Auftrag wurde nicht abgeschlossen.";

export const AGENT_OUTPUT_RECOVERY_CONTEXT =
  "Die vorherige Assistentenantwort wurde von der Anwendung als unsichere externe API- oder Pseudo-Tool-Ausgabe verworfen. Sie wurde nicht ausgeführt und der ursprüngliche Nutzerauftrag ist noch nicht abgeschlossen. Bei einer Frage nach dem Abbruch oder einer Aufforderung zum Fortsetzen muss der letzte echte Nutzerauftrag ausschließlich mit den bereitgestellten Simulator-Tools fortgeführt werden.";

const PSEUDO_TOOL_PATTERN = /<\/?tool_call\b|<function(?:=|\s|>)|<\/?arguments\b/i;
const COMPLETE_PSEUDO_TOOL_PATTERN = /<tool_call\b[^>]*>[\s\S]*?<\/tool_call>/gi;
const UNSAFE_EXTERNAL_PATTERN =
  /(example\.com|your(?:\\?_)?api(?:\\?_)?token|requests\.(post|get|put|delete)|auth\s*=\s*\(|api[_\\]?token\s*=|keine spezifischen gr(?:ü|ue)nde[\s\S]{0,80}api.?funktionalit(?:ä|ae)t eingestellt|api.?funktionalit(?:ä|ae)t[\s\S]{0,50}(eingestellt|nicht auffindbar))/i;

export type AgentTextSafety = {
  blocked: boolean;
  displayText: string;
  reason: "external-api" | "pseudo-tool" | null;
};

export function inspectAgentText(text: string): AgentTextSafety {
  const pseudoTool = PSEUDO_TOOL_PATTERN.test(text);
  const externalApi = UNSAFE_EXTERNAL_PATTERN.test(text);
  if (!pseudoTool && !externalApi) {
    return { blocked: false, displayText: text.trim(), reason: null };
  }

  const withoutPseudoTools = text.replace(COMPLETE_PSEUDO_TOOL_PATTERN, "").trim();
  const withoutCodeBlocks = withoutPseudoTools.replace(/```[\s\S]*?```/g, "").trim();
  const safeRemainder = PSEUDO_TOOL_PATTERN.test(withoutCodeBlocks) || UNSAFE_EXTERNAL_PATTERN.test(withoutCodeBlocks)
    ? ""
    : withoutCodeBlocks;
  return {
    blocked: true,
    displayText: safeRemainder
      ? `${safeRemainder}\n\n${AGENT_OUTPUT_REJECTED_NOTICE}`
      : AGENT_OUTPUT_REJECTED_NOTICE,
    reason: pseudoTool ? "pseudo-tool" : "external-api",
  };
}
