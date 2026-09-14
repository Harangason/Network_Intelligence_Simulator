"use client";
import { useEffect, useState } from 'react';
import { parseAgentResponse } from './agent-response';
import type { EngineeringAgentEvent } from './engineering-agent';

/** Read durable results while the authorized server worker continues the job. */
export function useGoalResponse(event: EngineeringAgentEvent, projectId: string) {
  const workload = String(event.workload?.workload_id ?? '');
  const key = `${projectId}:${workload}`;
  const enabled = workload.startsWith('goal-') && ['FOLLOWUP_PENDING', 'SIMULATION_RUNNING'].includes(String(event.status || event.workload?.status));
  const [resolved, setResolved] = useState<{key: string; value: EngineeringAgentEvent} | null>(null);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      let complete = false;
      try {
        if (document.visibilityState === 'visible') {
          const response = await fetch(`/api/engineering/agent/execution-goals/${encodeURIComponent(workload)}/response`, {
            headers: {'X-Project-ID': projectId}, cache: 'no-store', signal: controller.signal,
          });
          const result = await response.json();
          if (response.ok && result.success && result.data?.agent_response) {
            const value = parseAgentResponse(result.data.agent_response);
            controller.signal.throwIfAborted();
            if (value.workload?.workload_id === workload) {
              setResolved({key, value: value as EngineeringAgentEvent});
              complete = !['FOLLOWUP_PENDING', 'SIMULATION_RUNNING'].includes(value.status);
            }
          }
        }
      } catch { /* Keep the durable last result and retry; never issue a write. */ }
      if (!complete && !controller.signal.aborted) timer = setTimeout(() => void poll(), 5000);
    };
    void poll();
    return () => {controller.abort(); clearTimeout(timer);};
  }, [enabled, key, projectId, workload]);
  return enabled && resolved?.key === key ? resolved.value : event;
}
