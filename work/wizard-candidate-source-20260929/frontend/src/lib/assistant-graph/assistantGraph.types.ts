export type AssistantGraphState =
  | "idle"
  | "listening"
  | "thinking"
  | "responding"
  | "warning"
  | "error";

export type GraphNode = {
  id: string;
  x: number;
  y: number;
  baseX: number;
  baseY: number;
  vx: number;
  vy: number;
  radius: number;
  phase: number;
  activity: number;
};

export type GraphEdge = {
  source: string;
  target: string;
  activity: number;
};

export type AssistantGraphColors = {
  bubble: string;
  bubbleBorder: string;
  node: string;
  edge: string;
  active: string;
  warning: string;
  error: string;
  text: string;
};
