import type { AssistantGraphState, GraphEdge, GraphNode } from "./assistantGraph.types";
import { GRAPH_STATE_CONFIG, interpolateConfig, type AssistantGraphStateConfig } from "./graphStates";

const BASE_LAYOUT = [
  [0.5, 0.5],
  [0.5, 0.22],
  [0.72, 0.32],
  [0.72, 0.68],
  [0.5, 0.78],
  [0.28, 0.68],
  [0.28, 0.32],
  [0.82, 0.5],
  [0.18, 0.5],
] as const;

const EDGE_LAYOUT = [
  [0, 1],
  [0, 2],
  [0, 3],
  [0, 4],
  [0, 5],
  [0, 6],
  [1, 2],
  [2, 3],
  [3, 4],
  [4, 5],
  [5, 6],
  [6, 1],
  [2, 7],
  [5, 8],
] as const;

export class AssistantGraphAnimationController {
  nodes: GraphNode[];
  edges: GraphEdge[];
  private config: AssistantGraphStateConfig;
  private state: AssistantGraphState;

  constructor(nodeCount: number, size: number, state: AssistantGraphState) {
    const count = Math.min(9, Math.max(5, Math.round(nodeCount)));
    this.state = state;
    this.config = GRAPH_STATE_CONFIG[state];
    this.nodes = BASE_LAYOUT.slice(0, count).map(([x, y], index) => ({
      id: `node-${index}`,
      x: x * size,
      y: y * size,
      baseX: x * size,
      baseY: y * size,
      vx: 0,
      vy: 0,
      radius: index === 0 ? size * 0.065 : size * 0.047,
      phase: index * 1.73,
      activity: index === 0 ? 1 : 0,
    }));
    this.edges = EDGE_LAYOUT.filter(([source, target]) => source < count && target < count).map(
      ([source, target], index) => ({
        source: `node-${source}`,
        target: `node-${target}`,
        activity: index % 3 === 0 ? 0.55 : 0.22,
      }),
    );
  }

  resize(size: number) {
    this.nodes.forEach((node, index) => {
      const [baseX, baseY] = BASE_LAYOUT[index];
      node.baseX = baseX * size;
      node.baseY = baseY * size;
      node.x = node.baseX;
      node.y = node.baseY;
      node.radius = index === 0 ? size * 0.065 : size * 0.047;
    });
  }

  updateState(state: AssistantGraphState) {
    this.state = state;
  }

  step(time: number, size: number, options: { hover: boolean; active: boolean; reducedMotion: boolean }) {
    const targetConfig = GRAPH_STATE_CONFIG[this.state];
    this.config = interpolateConfig(this.config, targetConfig, 0.045);
    const motionMultiplier = options.reducedMotion ? 0 : options.hover ? 1.1 : 1;
    const activityMultiplier = options.active || options.hover ? 1.2 : 1;
    const amplitude = size * this.config.amplitude * motionMultiplier;
    const safeMin = size * 0.15;
    const safeMax = size * 0.85;

    for (const node of this.nodes) {
      const targetX =
        node.baseX + Math.sin(time * this.config.driftSpeed + node.phase) * amplitude;
      const targetY =
        node.baseY + Math.cos(time * (this.config.driftSpeed * 0.78) + node.phase) * amplitude;
      node.vx += (targetX - node.x) * this.config.damping;
      node.vy += (targetY - node.y) * this.config.damping;
      node.vx *= 0.72;
      node.vy *= 0.72;
      node.x = Math.min(safeMax, Math.max(safeMin, node.x + node.vx));
      node.y = Math.min(safeMax, Math.max(safeMin, node.y + node.vy));
      node.activity =
        0.35 + Math.max(0, Math.sin(time * 1.4 + node.phase)) * 0.45 * activityMultiplier;
    }

    this.edges.forEach((edge, index) => {
      edge.activity =
        (0.22 + Math.max(0, Math.sin(time * 1.35 + index * 0.85)) * this.config.edgeActivity) *
        activityMultiplier;
    });
  }

  pulseCount(reducedMotion: boolean) {
    return reducedMotion ? 0 : Math.round(this.config.pulseCount);
  }

  centerPulse(time: number, reducedMotion: boolean) {
    const pulse = reducedMotion ? 0.08 : this.config.centerPulse;
    return 1 + Math.max(0, Math.sin(time * 2.6)) * pulse;
  }
}
