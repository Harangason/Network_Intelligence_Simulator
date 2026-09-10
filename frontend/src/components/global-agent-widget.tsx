"use client";

import {
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import { usePathname } from "next/navigation";
import { AssistantGraphBubble } from "@/components/assistant";
import { AgentChatCore } from "@/components/agent-chat-core";
import {
  ENGINEERING_AGENT_OPEN_EVENT,
} from "@/lib/agent-task-events";
import { listRoutes } from "@/lib/routing-api";
import {
  routingApprovalProgress,
  type RoutingApprovalProgress,
} from "@/lib/routing-approval";
import type { RoutingEntry } from "@/lib/types";
import { readUserSettings, SETTINGS_EVENT, type UserSettings } from "@/lib/user-settings";
import { WORKFLOW_CHANGED_EVENT } from "@/components/workflow-header";
import { ASSISTANT_CONTEXT_EVENT, readAssistantContext } from "@/lib/agent/assistant-context";
import type { AssistantGraphState } from "@/lib/assistant-graph";

type AgentPanelSize = {
  height: number;
  width: number;
};

type AgentPanelResizeAxis = "both" | "width";

type AgentPanelResizeState = AgentPanelSize & {
  axis: AgentPanelResizeAxis;
  pointerId: number;
  startX: number;
  startY: number;
};

function clampAgentPanelSize(size: AgentPanelSize): AgentPanelSize {
  const mobile = window.innerWidth <= 720;
  const gutter = mobile ? 16 : 28;
  const maxWidth = mobile ? window.innerWidth : Math.min(440, Math.max(280, window.innerWidth - gutter * 2));
  const maxHeight = Math.max(360, window.innerHeight - gutter * 2);
  const minWidth = Math.min(mobile ? 280 : 380, maxWidth);
  const minHeight = Math.min(mobile ? 360 : 440, maxHeight);

  return {
    width: Math.min(maxWidth, Math.max(minWidth, Math.round(size.width))),
    height: Math.min(maxHeight, Math.max(minHeight, Math.round(size.height))),
  };
}

export function GlobalAgentWidget() {
  const [selectedName, setSelectedName] = useState('');
  useEffect(() => {
    const update = () => setSelectedName(readAssistantContext().selected_object_refs[0]?.name ?? '');
    update(); window.addEventListener(ASSISTANT_CONTEXT_EVENT, update);
    return () => window.removeEventListener(ASSISTANT_CONTEXT_EVENT, update);
  }, []);
  const [activeProject, setActiveProject] = useState("default");
  const [settingsReady, setSettingsReady] = useState(false);
  const [open, setOpen] = useState(false);
  const [hasOpened, setHasOpened] = useState(false);
  const [draftRequest, setDraftRequest] = useState<{ id: number; text: string; projectId: string } | null>(null);
  const [agentState, setAgentState] = useState<AssistantGraphState>('idle');
  useEffect(() => { if (open) setHasOpened(true); }, [open]);
  const [approvalProgress, setApprovalProgress] = useState<RoutingApprovalProgress<RoutingEntry> | null>(null);
  const [panelSize, setPanelSize] = useState<AgentPanelSize | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const resizeStateRef = useRef<AgentPanelResizeState | null>(null);
  const pathname = usePathname();
  const isLandingPage = pathname === "/";

  const beginPanelResize = (
    axis: AgentPanelResizeAxis,
    event: ReactPointerEvent<HTMLButtonElement>,
  ) => {
    const panel = panelRef.current;
    if (!panel) return;
    const bounds = panel.getBoundingClientRect();
    resizeStateRef.current = {
      axis,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      width: bounds.width,
      height: bounds.height,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
    event.preventDefault();
  };

  const resizePanel = (event: ReactPointerEvent<HTMLButtonElement>) => {
    const resize = resizeStateRef.current;
    if (!resize || resize.pointerId !== event.pointerId) return;
    setPanelSize(clampAgentPanelSize({
      width: resize.width + resize.startX - event.clientX,
      height: resize.axis === "both"
        ? resize.height + resize.startY - event.clientY
        : resize.height,
    }));
  };

  const finishPanelResize = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (resizeStateRef.current?.pointerId !== event.pointerId) return;
    resizeStateRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const resizePanelWithKeyboard = (
    axis: AgentPanelResizeAxis,
    event: ReactKeyboardEvent<HTMLButtonElement>,
  ) => {
    const panel = panelRef.current;
    if (!panel) return;
    if (event.key === "Home") {
      setPanelSize(null);
      event.preventDefault();
      return;
    }
    const bounds = panel.getBoundingClientRect();
    let width = bounds.width;
    let height = bounds.height;
    if (event.key === "ArrowLeft") width += 40;
    else if (event.key === "ArrowRight") width -= 40;
    else if (axis === "both" && event.key === "ArrowUp") height += 40;
    else if (axis === "both" && event.key === "ArrowDown") height -= 40;
    else return;
    setPanelSize(clampAgentPanelSize({ width, height }));
    event.preventDefault();
  };

  const panelStyle = panelSize
    ? ({
        "--agent-widget-user-height": `${panelSize.height}px`,
        "--agent-widget-user-width": `${panelSize.width}px`,
      } as CSSProperties)
    : undefined;

  useEffect(() => {
    const initial = readUserSettings();
    setActiveProject(initial.activeProject);
    setOpen(!isLandingPage && initial.openAgentOnStart);
    setSettingsReady(true);
    const update = (event: Event) => {
      const next = (event as CustomEvent<UserSettings>).detail;
      setActiveProject(next.activeProject);
    };
    window.addEventListener(SETTINGS_EVENT, update);
    return () => {
      window.removeEventListener(SETTINGS_EVENT, update);
    };
  }, [isLandingPage]);

  useEffect(() => {
    if (isLandingPage || !settingsReady || !open) {
      setApprovalProgress(null);
      return;
    }

    let active = true;
    let checking = false;
    const checkRoutingApprovals = async () => {
      if (checking) return;
      checking = true;
      try {
        const next = routingApprovalProgress(await listRoutes());
        if (!active) return;
        setApprovalProgress(next);
        // Opening, focus and status polling are read-only. A workflow status
        // is never authorization to synthesize or dispatch an agent request.
      } catch {
        // A transient routing API failure must not discard the last known gate state.
      } finally {
        checking = false;
      }
    };
    const handleRoutingChange = () => void checkRoutingApprovals();

    void checkRoutingApprovals();
    const interval = window.setInterval(checkRoutingApprovals, 30_000);
    window.addEventListener(WORKFLOW_CHANGED_EVENT, handleRoutingChange);
    window.addEventListener("focus", handleRoutingChange);
    return () => {
      active = false;
      window.clearInterval(interval);
      window.removeEventListener(WORKFLOW_CHANGED_EVENT, handleRoutingChange);
      window.removeEventListener("focus", handleRoutingChange);
    };
  }, [activeProject, isLandingPage, open, settingsReady]);

  useEffect(() => {
    const openAgent = () => setOpen(true);
    const prepareQuestion = (event: Event) => {
      const text = String((event as CustomEvent<string>).detail ?? "").trim();
      if (text) setDraftRequest({ id: Date.now(), text, projectId: activeProject });
      setOpen(true);
    };
    window.addEventListener(ENGINEERING_AGENT_OPEN_EVENT, openAgent);
    window.addEventListener("engineering-agent:ask", prepareQuestion);
    return () => {
      window.removeEventListener(ENGINEERING_AGENT_OPEN_EVENT, openAgent);
      window.removeEventListener("engineering-agent:ask", prepareQuestion);
    };
  }, [activeProject]);

  return (
    <aside
      aria-label="Engineering-Assistent"
      className={`agent-widget ${open ? "is-open" : "is-collapsed"}`}
    >
        <div
          aria-hidden={!open}
          className="agent-widget-panel"
          hidden={!open}
          ref={panelRef}
          style={panelStyle}
        >
            <button
              aria-label="Breite des Assistentenfensters ändern"
              className="agent-widget-resize-handle is-width"
              onKeyDown={(event) => resizePanelWithKeyboard("width", event)}
              onPointerCancel={finishPanelResize}
              onPointerDown={(event) => beginPanelResize("width", event)}
              onPointerMove={resizePanel}
              onPointerUp={finishPanelResize}
              title="Breite ändern (Pos1 setzt zurück)"
              type="button"
            />
            <button
              aria-label="Breite und Höhe des Assistentenfensters ändern"
              className="agent-widget-resize-handle is-corner"
              onKeyDown={(event) => resizePanelWithKeyboard("both", event)}
              onPointerCancel={finishPanelResize}
              onPointerDown={(event) => beginPanelResize("both", event)}
              onPointerMove={resizePanel}
              onPointerUp={finishPanelResize}
              title="Breite und Höhe ändern (Pos1 setzt zurück)"
              type="button"
            />
            <div className="agent-widget-header">
              <div>
                <strong>Engineering Assistant</strong>
                <p className="agent-widget-context">{activeProject} · {pathname.split('/').filter(Boolean).at(-1) || 'Projekt'}{selectedName ? ` · ${selectedName}` : ''}</p>
              </div>
              <button
                aria-label="Engineering-Assistent schließen"
                className="agent-widget-close"
                onClick={() => setOpen(false)}
                title="AI Assistant minimieren"
                type="button"
              >
                x
              </button>
            </div>

            <div className="agent-widget-body">
              {(open || hasOpened) && (
                <AgentChatCore
                  compact
                  key={activeProject}
                  projectId={activeProject}
                  draftRequest={draftRequest?.projectId === activeProject ? draftRequest : null}
                  routingApprovalComplete={approvalProgress?.complete === true}
                  onStateChange={setAgentState}
                />
              )}
            </div>
        </div>
        {!open && (
          <AssistantGraphBubble
            active={agentState === 'thinking' || agentState === 'responding'}
            onClick={() => setOpen(true)}
            size={64}
            state={agentState}
            title="AI Assistant öffnen"
          />
        )}
    </aside>
  );
}
