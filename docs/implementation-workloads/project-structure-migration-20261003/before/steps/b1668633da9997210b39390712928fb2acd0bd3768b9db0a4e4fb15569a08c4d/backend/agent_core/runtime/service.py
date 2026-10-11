"""One runtime entry point shared by chat and future non-chat adapters."""
from __future__ import annotations

from typing import Any, Callable

from .capability_registry import CapabilityRegistry
from .completion import CompletionEvaluator
from .context_resolver import ContextResolver
from .executor import EngineeringExecutor
from .goal_resolver import GoalResolver
from .planner import EngineeringPlanner
from .recovery import RecoveryManager, recipient_resume
from .result import ResultComposer
from .workload import EngineeringWorkload, WorkloadManager, WorkloadStatus


class EngineeringAssistantService:
    """Resolve a durable goal, select registered capabilities, execute and assess."""

    def __init__(self, client, *, reasoner=None, agent_factory=None, persist: Callable[[dict], None] | None = None):
        self.client = client
        self.reasoner = reasoner
        self.agent_factory = agent_factory
        self.persist = persist or (lambda _workload: None)
        self.context_resolver = ContextResolver()
        self.executor = EngineeringExecutor(client)
        self.goal_resolver = GoalResolver()
        self.capabilities = CapabilityRegistry()
        self.planner = EngineeringPlanner()
        self.completion = CompletionEvaluator()
        self.recovery = RecoveryManager()
        self.result_composer = ResultComposer()
        self.workloads = WorkloadManager(self.persist)

    async def execute(self, prompt: str, context: Any, *, emit=None, history=None, saved_state=None) -> dict:
        resolved_context = self.context_resolver.resolve(context, saved_state)
        from .hardware_intent import resume_hardware_request
        prompt, resumed_id = resume_hardware_request(prompt, resolved_context)
        from .goal_resolver import recipient_repair_followup
        repair_followup = recipient_repair_followup(prompt, resolved_context)
        if repair_followup:
            prompt, resumed_id = repair_followup['original_request'], repair_followup['source_workload_id']
        recovery = recipient_resume(prompt, resolved_context)
        if recovery:
            prompt, resumed_id = recovery['original_request'], recovery['source_workload_id']
        goal = self.goal_resolver.resolve(prompt, resolved_context, resolved_context.get("active_workload"))
        if resumed_id:
            goal = goal.model_copy(update={'goal_id': resumed_id})
        workload_model = EngineeringWorkload(workload_id=goal.goal_id, goal=goal,
            project_id=str(goal.project_context.get("project_id") or "unknown"), status=WorkloadStatus.PLANNING,
            result={"request_revision": getattr(context, "project_draft_revision", None), "follow_up_of": goal.follow_up_of})
        if repair_followup:
            workload_model.result['contextual_repair'] = repair_followup
        if recovery:
            workload_model.result['recovery'] = recovery
            workload_model.created_at = resolved_context['active_workload'].get('created_at') or workload_model.created_at
            if recovery['blocked']:
                workload_model.failure = recovery['previous_failure']
        workload = workload_model.model_dump(mode="json")
        self.workloads.save(workload_model)
        try:
            available_tools = await self.client.tools()
            capability = self.capabilities.resolve(goal.goal_type, available_tools)
            workload["capability"] = capability
            workload_model.capability = capability
            workload_model.plan = self.planner.plan(goal, capability)
            workload_model.status = WorkloadStatus.IN_PROGRESS if capability["available"] else WorkloadStatus.NOT_SUPPORTED_WITH_CAPABILITY_GAP
            self.workloads.save(workload_model)
            def runtime_emit(event):
                event.setdefault("metadata", {}).update({"engineering_goal_id": goal.goal_id,
                    "engineering_goal_type": goal.goal_type.value, "capability_id": capability["capability_id"]})
                if emit:
                    emit(event)
            runtime_emit({"type": "PROGRESS", "status": "PLANNING", "text": "Engineering-Ziel und ausführbare Fachfähigkeiten wurden aufgelöst.",
                          "metadata": {"goal": goal.model_dump(mode="json"), "capability": capability}})
            if not capability["available"]:
                result = {"run_id": getattr(getattr(context, "input_envelope", None), "run_ref", ""),
                          "status": "NOT_SUPPORTED_WITH_CAPABILITY_GAP", "events": [],
                          "context": context.model_dump(), "trace": [], "proposals": []}
                message = (f"Dieser Auftrag ist derzeit nicht ausführbar. Für {goal.goal_type.value} fehlt die registrierte Laufzeitfähigkeit "
                           f"{capability['capability_id']}; verfügbar sind: {', '.join(capability['available_tools']) or 'keine'}. Die Anforderung bleibt erhalten.")
                from ..api.agent_response import AgentResponse
                event = AgentResponse(type="RESULT", status="NOT_SUPPORTED_WITH_CAPABILITY_GAP", text=message,
                    metadata={"goal": goal.model_dump(mode="json"), "capability": capability,
                              "failure_code": "NOT_SUPPORTED_WITH_CAPABILITY_GAP"}).model_dump(mode="json", exclude_none=True)
                result["events"].append(event)
                runtime_emit(event)
            else:
                result = await self.executor.execute(goal, context, resolved_context,
                    emit=runtime_emit, available_tools={item.get('name') for item in available_tools})
                if result is None:
                    agent = self.agent_factory(self.client, reasoner=self.reasoner) if self.agent_factory else None
                    if agent is None:
                        from ..core.engineering_agent import EngineeringAgent
                        agent = EngineeringAgent(self.client, reasoner=self.reasoner)
                    result = await agent.run(prompt, context, emit=runtime_emit, history=history)
            runtime_result = self.result_composer.compose(goal, workload, result.get("events", []))
            failure = next((event.get('metadata', {}).get('failure') for event in reversed(result.get('events', []))
                            if event.get('metadata', {}).get('failure')), None)
            if failure:
                workload_model.failure = failure
            status_text = {
                "COMPLETED": "Engineering-Ziel abgeschlossen; die angeforderten Ergebnisse sind durch aktuelle Modelldaten oder Prüfevidenz belegt.",
                "READY_FOR_REVIEW": "Der Änderungsvorschlag ist vorbereitet. Deine Freigabe ist noch erforderlich; bis dahin bleibt das kanonische Modell unverändert.",
                "WAITING_FOR_ENGINEERING_DECISION": "Der Auftrag wartet auf die angezeigte Engineering-Entscheidung. Danach kann derselbe gespeicherte Workload fortgesetzt werden.",
                "INCOMPLETE": "Der Auftrag ist noch nicht vollständig nachgewiesen. Offene Zielbedingungen und Befunde stehen in der vorherigen Antwort.",
                "BLOCKED_WITH_EXPLICIT_CAUSE": "Der Auftrag ist mit einem konkreten Ausführungsgrund blockiert. Die Anforderung und ihr Workload bleiben gespeichert.",
                "NOT_SUPPORTED_WITH_CAPABILITY_GAP": "Für diesen Auftrag fehlt eine ausführbare, registrierte NIS-Fähigkeit. Die Anforderung bleibt gespeichert.",
            }.get(runtime_result.status, "Der Engineering-Auftrag wurde ausgewertet.")
            from ..api.agent_response import AgentResponse
            terminal = AgentResponse(type="PROGRESS", status=runtime_result.status, text=status_text,
                metadata={"engineering_goal_id": goal.goal_id, "engineering_goal_type": goal.goal_type.value,
                          "workload_id": goal.goal_id, "runtime_result": runtime_result.model_dump(mode="json"),
                          "evidence_refs": runtime_result.evidence_refs}).model_dump(mode="json", exclude_none=True)
            runtime_emit(terminal)
            result.setdefault("events", []).append(terminal)
            workload_model.status = WorkloadStatus(runtime_result.status)
            workload_model.evidence = runtime_result.evidence_refs
            workload_model.result = {"status": result.get("status"), "event_ids": [item.get("id") for item in result.get("events", [])],
                "request_revision": getattr(context, "project_draft_revision", None), "follow_up_of": goal.follow_up_of,
                "completion": runtime_result.model_dump(mode="json")}
            if repair_followup:
                workload_model.result['contextual_repair'] = repair_followup
            if recovery:
                inspected = next((event.get('metadata', {}).get('details', {}).get('recovery_evidence')
                    for event in reversed(result.get('events', []))
                    if event.get('metadata', {}).get('details', {}).get('recovery_evidence')), None)
                workload_model.result['recovery'] = {**recovery, **(inspected or {})}
            self.workloads.save(workload_model)
            result["runtime"] = runtime_result.model_dump(mode="json") | {"capability": capability}
            return result
        except Exception as error:
            failure = self.recovery.classify(error)
            workload_model.status = WorkloadStatus(failure["status"])
            workload_model.failure = {k: failure[k] for k in ("code", "category", "retryable", "message")}
            self.workloads.save(workload_model)
            raise
