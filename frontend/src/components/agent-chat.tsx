"use client";

import { AgentChatCore } from "@/components/agent-chat-core";

export function AgentChat() {
  return (
    <div className="workspace-grid">
      <div className="panel config-panel eng-agent-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Engineering-Assistent</p>
            <h2>Dialog mit dem Netzwerkmodell</h2>
          </div>
        </div>

        <AgentChatCore />
      </div>

      <aside className="side-column">
        <div className="panel overview-panel">
          <p className="eyebrow">Hinweis</p>
          <h2 style={{ fontSize: 16 }}>Vorschläge statt Auto-Änderungen</h2>
          <p className="muted" style={{ marginTop: 12, fontSize: 12, lineHeight: 1.6 }}>
            Der Agent kann Objekte nur als Entwurf (draft, unreviewed) anlegen.
            Freigabe und Review erfolgen im Tab &quot;Engineering-Modell&quot;.
          </p>
        </div>
      </aside>
    </div>
  );
}
