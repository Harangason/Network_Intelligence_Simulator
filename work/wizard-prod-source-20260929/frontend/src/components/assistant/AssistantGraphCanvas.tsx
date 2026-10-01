"use client";

import { useEffect, useMemo, useRef } from "react";
import type { AssistantGraphColors, AssistantGraphState, GraphNode } from "@/lib/assistant-graph";
import { AssistantGraphAnimationController } from "@/lib/assistant-graph";

type AssistantGraphCanvasProps = {
  size: number;
  state: AssistantGraphState;
  active?: boolean;
  reducedMotion?: boolean;
  nodeCount: number;
  colors: AssistantGraphColors;
  hover?: boolean;
};

function bubblePath(context: CanvasRenderingContext2D, size: number) {
  const radius = size * 0.26;
  const tail = size * 0.16;
  const inset = size * 0.07;
  context.beginPath();
  context.moveTo(inset + radius, inset);
  context.lineTo(size - inset - radius, inset);
  context.quadraticCurveTo(size - inset, inset, size - inset, inset + radius);
  context.lineTo(size - inset, size - inset - radius - tail * 0.22);
  context.quadraticCurveTo(size - inset, size - inset, size - inset - radius, size - inset);
  context.lineTo(size * 0.55, size - inset);
  context.lineTo(size * 0.38, size - inset + tail);
  context.lineTo(size * 0.4, size - inset);
  context.lineTo(inset + radius, size - inset);
  context.quadraticCurveTo(inset, size - inset, inset, size - inset - radius);
  context.lineTo(inset, inset + radius);
  context.quadraticCurveTo(inset, inset, inset + radius, inset);
  context.closePath();
}

function resolveNode(nodes: GraphNode[], id: string) {
  return nodes.find((node) => node.id === id);
}

export function AssistantGraphCanvas({
  size,
  state,
  active = false,
  reducedMotion = false,
  nodeCount,
  colors,
  hover = false,
}: AssistantGraphCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const controller = useMemo(
    () => new AssistantGraphAnimationController(nodeCount, size, state),
    [nodeCount, size],
  );

  useEffect(() => {
    controller.resize(size);
  }, [controller, size]);

  useEffect(() => {
    controller.updateState(state);
  }, [controller, state]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    let frame = 0;
    let visible = true;
    let hidden = document.hidden;
    const pixelRatio = Math.max(1, window.devicePixelRatio || 1);
    canvas.width = Math.round(size * pixelRatio);
    canvas.height = Math.round(size * pixelRatio);
    canvas.style.width = `${size}px`;
    canvas.style.height = `${size}px`;
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);

    const observer = new IntersectionObserver(([entry]) => {
      visible = entry?.isIntersecting ?? true;
    });
    observer.observe(canvas);

    const onVisibility = () => {
      hidden = document.hidden;
    };
    document.addEventListener("visibilitychange", onVisibility);

    const draw = (timeMs: number) => {
      const time = timeMs / 1000;
      context.clearRect(0, 0, size, size);
      context.save();
      bubblePath(context, size);
      context.clip();

      context.fillStyle = colors.bubble;
      context.fillRect(0, 0, size, size);

      if (!hidden && visible) {
        controller.step(time, size, { hover, active, reducedMotion });
      }

      const lineWidth = Math.max(1, size * 0.018);
      context.lineCap = "round";
      for (const edge of controller.edges) {
        const source = resolveNode(controller.nodes, edge.source);
        const target = resolveNode(controller.nodes, edge.target);
        if (!source || !target) continue;
        context.strokeStyle =
          state === "error" && edge === controller.edges[1] ? colors.error : colors.edge;
        context.globalAlpha = state === "error" && edge === controller.edges[1] ? 0.58 : 0.26 + edge.activity * 0.45;
        context.lineWidth = lineWidth;
        context.beginPath();
        context.moveTo(source.x, source.y);
        context.lineTo(target.x, target.y);
        context.stroke();
      }

      const pulses = controller.pulseCount(reducedMotion);
      for (let index = 0; index < pulses; index += 1) {
        const edge = controller.edges[(index * 3 + Math.floor(time * 0.8)) % controller.edges.length];
        const source = resolveNode(controller.nodes, edge.source);
        const target = resolveNode(controller.nodes, edge.target);
        if (!source || !target) continue;
        const direction = state === "responding" && !edge.source.endsWith("-0") ? 1 : 0;
        const progress = (time * (0.22 + index * 0.035) + index * 0.28 + direction * 0.12) % 1;
        const x = source.x + (target.x - source.x) * progress;
        const y = source.y + (target.y - source.y) * progress;
        context.globalAlpha = 0.62;
        context.fillStyle = state === "warning" ? colors.warning : colors.active;
        context.beginPath();
        context.arc(x, y, Math.max(1.3, size * 0.024), 0, Math.PI * 2);
        context.fill();
      }

      controller.nodes.forEach((node, index) => {
        const isCenter = index === 0;
        const isProblem = state === "error" && index === 3;
        const pulse = isCenter ? controller.centerPulse(time, reducedMotion) : 1;
        context.globalAlpha = isCenter ? 0.95 : 0.7 + node.activity * 0.22;
        context.fillStyle = isProblem ? colors.error : state === "warning" && index === 5 ? colors.warning : isCenter ? colors.active : colors.node;
        context.beginPath();
        context.arc(node.x, node.y, node.radius * pulse, 0, Math.PI * 2);
        context.fill();
        context.globalAlpha = 0.28;
        context.strokeStyle = colors.text;
        context.lineWidth = Math.max(0.75, size * 0.01);
        context.stroke();
      });

      context.restore();
      context.globalAlpha = 1;
      context.lineWidth = Math.max(1, size * 0.018);
      context.strokeStyle = colors.bubbleBorder;
      bubblePath(context, size);
      context.stroke();

      frame = window.requestAnimationFrame(draw);
    };

    frame = window.requestAnimationFrame(draw);

    return () => {
      window.cancelAnimationFrame(frame);
      observer.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [active, colors, controller, hover, reducedMotion, size, state]);

  return <canvas aria-hidden="true" ref={canvasRef} />;
}
