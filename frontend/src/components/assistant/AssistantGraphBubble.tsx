"use client";

import { useEffect, useState } from "react";
import { AssistantGraphCanvas } from "./AssistantGraphCanvas";
import type { AssistantGraphColors, AssistantGraphState } from "@/lib/assistant-graph";

type AssistantGraphBubbleProps = {
  size?: number;
  state?: AssistantGraphState;
  active?: boolean;
  reducedMotion?: boolean;
  nodeCount?: number;
  onClick?: () => void;
  title?: string;
};

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(media.matches);
    const update = () => setReduced(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  return reduced;
}

function nodeCountForSize(size: number, requested?: number) {
  if (requested) return Math.min(9, Math.max(5, requested));
  if (size <= 36) return 5;
  if (size >= 80) return 9;
  return 7;
}

export function AssistantGraphBubble({
  size = 56,
  state = "idle",
  active = false,
  reducedMotion,
  nodeCount,
  onClick,
  title = "AI Assistant",
}: AssistantGraphBubbleProps) {
  const [hover, setHover] = useState(false);
  const prefersReducedMotion = usePrefersReducedMotion();
  const finalReducedMotion = reducedMotion ?? prefersReducedMotion;
  const resolvedNodeCount = nodeCountForSize(size, nodeCount);
  const [colors, setColors] = useState<AssistantGraphColors>({
    bubble: "#121820",
    bubbleBorder: "#334151",
    node: "#f2f5f7",
    edge: "#8f9baa",
    active: "#9fea4e",
    warning: "#f7c65b",
    error: "#ff6b6b",
    text: "#080b0f",
  });

  useEffect(() => {
    const styles = getComputedStyle(document.documentElement);
    const token = (name: string, fallback: string) => styles.getPropertyValue(name).trim() || fallback;
    setColors({
      bubble: token("--surface-raised", "#121820"),
      bubbleBorder: token("--border-strong", "#334151"),
      node: token("--text", "#f2f5f7"),
      edge: token("--muted", "#8f9baa"),
      active: token("--accent", "#9fea4e"),
      warning: token("--warning", "#f7c65b"),
      error: token("--danger", "#ff6b6b"),
      text: token("--background", "#080b0f"),
    });
  }, []);

  return (
    <button
      aria-label={title}
      className={`assistant-graph-bubble ${active ? "active" : ""}`}
      onBlur={() => setHover(false)}
      onClick={onClick}
      onFocus={() => setHover(true)}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{ width: size, height: size }}
      title={title}
      type="button"
    >
      <AssistantGraphCanvas
        active={active}
        colors={colors}
        hover={hover}
        nodeCount={resolvedNodeCount}
        reducedMotion={finalReducedMotion}
        size={size}
        state={state}
      />
    </button>
  );
}
