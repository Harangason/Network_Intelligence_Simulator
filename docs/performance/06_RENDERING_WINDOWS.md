# Rendering Windows

Renderers must use stable windows:

- Matrix views keep the visible row count stable and scroll inside the surface.
- Graph views render viewport nodes and visible edges.
- Trace views use bounded event windows or ring buffers.
- Tables prefer virtualization or constrained scroll regions over page-level
  growth.

