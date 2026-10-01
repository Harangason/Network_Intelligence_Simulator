# Assistant Graph

Reusable animation primitives for the Network Intelligence Assistant bubble.

- `assistantGraph.types.ts` defines public graph and state types.
- `graphStates.ts` contains visual state presets for idle, listening, thinking, responding, warning, and error.
- `graphAnimation.ts` contains the lightweight requestAnimationFrame controller logic.
- `index.ts` is the public library entrypoint.

React rendering lives in `src/components/assistant/` so the animation model can be reused by other assistant surfaces without pulling in panel or widget behavior.
