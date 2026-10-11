import type { AssistantGraphState } from "./assistantGraph.types";

export type AssistantGraphStateConfig = {
  driftSpeed: number;
  amplitude: number;
  pulseCount: number;
  centerPulse: number;
  edgeActivity: number;
  damping: number;
};

export const GRAPH_STATE_CONFIG: Record<AssistantGraphState, AssistantGraphStateConfig> = {
  idle: {
    driftSpeed: 0.55,
    amplitude: 0.028,
    pulseCount: 1,
    centerPulse: 0.16,
    edgeActivity: 0.26,
    damping: 0.12,
  },
  listening: {
    driftSpeed: 0.75,
    amplitude: 0.034,
    pulseCount: 2,
    centerPulse: 0.32,
    edgeActivity: 0.38,
    damping: 0.14,
  },
  thinking: {
    driftSpeed: 0.92,
    amplitude: 0.044,
    pulseCount: 4,
    centerPulse: 0.52,
    edgeActivity: 0.58,
    damping: 0.16,
  },
  responding: {
    driftSpeed: 0.82,
    amplitude: 0.038,
    pulseCount: 3,
    centerPulse: 0.42,
    edgeActivity: 0.48,
    damping: 0.15,
  },
  warning: {
    driftSpeed: 0.62,
    amplitude: 0.028,
    pulseCount: 1,
    centerPulse: 0.22,
    edgeActivity: 0.32,
    damping: 0.12,
  },
  error: {
    driftSpeed: 0.25,
    amplitude: 0.012,
    pulseCount: 0,
    centerPulse: 0.08,
    edgeActivity: 0.12,
    damping: 0.08,
  },
};

export function interpolateConfig(
  current: AssistantGraphStateConfig,
  target: AssistantGraphStateConfig,
  factor: number,
): AssistantGraphStateConfig {
  return {
    driftSpeed: current.driftSpeed + (target.driftSpeed - current.driftSpeed) * factor,
    amplitude: current.amplitude + (target.amplitude - current.amplitude) * factor,
    pulseCount: current.pulseCount + (target.pulseCount - current.pulseCount) * factor,
    centerPulse: current.centerPulse + (target.centerPulse - current.centerPulse) * factor,
    edgeActivity: current.edgeActivity + (target.edgeActivity - current.edgeActivity) * factor,
    damping: current.damping + (target.damping - current.damping) * factor,
  };
}
