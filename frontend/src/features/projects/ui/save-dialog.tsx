"use client";

import { useEffect, useRef, type ReactNode } from "react";

// An application dialog also works where browser prompt() is suppressed.
export function SaveDialog({ titleId, busy, onCancel, children }: {
  titleId: string; busy: boolean; onCancel: () => void; children: ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { dialog.current?.showModal(); }, []);
  return <dialog ref={dialog} aria-labelledby={titleId} className="project-dialog save-dialog" onCancel={event => {
    event.preventDefault();
    if (!busy) onCancel();
  }}>{children}</dialog>;
}
