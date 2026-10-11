"use client";

import { type ReactNode, useEffect, useRef } from "react";

const CONTROLS = "input, select, textarea, label, a, [contenteditable]:not([contenteditable='false']), button:not([data-drag-scroll-handle]), [role='button']:not([data-drag-scroll-handle])";

export function RoutingScrollArea({ children, className, label }: {
  children: ReactNode;
  className: string;
  label: string;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = scrollRef.current;
    if (!node) return;
    let gesture: { id: number; x: number; y: number; left: number; top: number; dragging: boolean } | null = null;
    let suppressClick = false;

    const finish = () => {
      const current = gesture;
      gesture = null;
      node.classList.remove("is-drag-pending", "is-panning");
      if (!current) return;
      suppressClick = current.dragging;
      if (node.hasPointerCapture(current.id)) node.releasePointerCapture(current.id);
    };
    const onPointerDown = (event: PointerEvent) => {
      suppressClick = false;
      if (event.pointerType !== "mouse" || event.button !== 0 || !event.isPrimary
        || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
      if (!(event.target instanceof Element) || event.target.closest(CONTROLS)) return;
      // Leave the native scrollbars available for dragging, too.
      const rect = node.getBoundingClientRect();
      if (event.clientX >= rect.left + node.clientLeft + node.clientWidth
        || event.clientY >= rect.top + node.clientTop + node.clientHeight) return;
      if (node.scrollWidth <= node.clientWidth && node.scrollHeight <= node.clientHeight) return;
      gesture = { id: event.pointerId, x: event.clientX, y: event.clientY,
        left: node.scrollLeft, top: node.scrollTop, dragging: false };
      node.classList.add("is-drag-pending");
    };
    const onPointerMove = (event: PointerEvent) => {
      if (!gesture || gesture.id !== event.pointerId) return;
      if (!(event.buttons & 1)) { finish(); return; }
      const dx = event.clientX - gesture.x;
      const dy = event.clientY - gesture.y;
      if (!gesture.dragging) {
        if (Math.hypot(dx, dy) < 6) return;
        gesture.dragging = true;
        node.classList.add("is-panning");
        // Capture only after a drag starts: ordinary clicks keep their original target.
        node.setPointerCapture(event.pointerId);
      }
      event.preventDefault();
      node.scrollLeft = gesture.left - dx;
      node.scrollTop = gesture.top - dy;
    };
    const onPointerEnd = (event: PointerEvent) => {
      if (gesture?.id === event.pointerId) finish();
    };
    const onClick = (event: MouseEvent) => {
      // Releasing a drag must not select a route or open the matrix wizard.
      // The next pointerdown resets this; keyboard activation remains available.
      if (!suppressClick || event.detail === 0) return;
      suppressClick = false;
      event.preventDefault();
      event.stopPropagation();
    };
    const onDragStart = (event: DragEvent) => { if (gesture) event.preventDefault(); };
    const scrollHorizontally = (delta: number) => {
      const before = node.scrollLeft;
      node.scrollLeft += delta;
      return before !== node.scrollLeft;
    };
    const onWheel = (event: WheelEvent) => {
      if (event.ctrlKey || event.metaKey) return;
      const delta = event.deltaX || (event.shiftKey ? event.deltaY : 0);
      const units = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? node.clientWidth : 1;
      if (delta && scrollHorizontally(delta * units)) event.preventDefault();
    };
    const onAuxInput = (event: MouseEvent) => {
      if (event.button !== 3 && event.button !== 4) return;
      if (scrollHorizontally(event.button === 3 ? -260 : 260)) event.preventDefault();
    };

    node.addEventListener("pointerdown", onPointerDown);
    node.addEventListener("lostpointercapture", onPointerEnd);
    node.addEventListener("click", onClick, true);
    node.addEventListener("dragstart", onDragStart);
    node.addEventListener("wheel", onWheel, { passive: false });
    node.addEventListener("mousedown", onAuxInput);
    node.addEventListener("mouseup", onAuxInput);
    node.addEventListener("auxclick", onAuxInput);
    window.addEventListener("pointermove", onPointerMove, { passive: false });
    window.addEventListener("pointerup", onPointerEnd);
    window.addEventListener("pointercancel", onPointerEnd);
    window.addEventListener("blur", finish);
    return () => {
      finish();
      node.removeEventListener("pointerdown", onPointerDown);
      node.removeEventListener("lostpointercapture", onPointerEnd);
      node.removeEventListener("click", onClick, true);
      node.removeEventListener("dragstart", onDragStart);
      node.removeEventListener("wheel", onWheel);
      node.removeEventListener("mousedown", onAuxInput);
      node.removeEventListener("mouseup", onAuxInput);
      node.removeEventListener("auxclick", onAuxInput);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerEnd);
      window.removeEventListener("pointercancel", onPointerEnd);
      window.removeEventListener("blur", finish);
    };
  }, []);

  return <div aria-describedby="routing-drag-hint" aria-label={label} className={`${className} routing-drag-scroll`} ref={scrollRef} role="region" tabIndex={0}>{children}</div>;
}
