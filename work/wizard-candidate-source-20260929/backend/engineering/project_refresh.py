"""Refresh derived checks without editing architecture or route approvals."""
from .communication_repair import load_plan
from .pagination import all_pages
from .routing.repository import list_routes
from .routing.validation import RoutingValidator
from .capacity.service import CapacityTimingService, PreflightService
from .workflow.service import WorkflowStatusService
from .project_context import current_project_id


def refresh_project():
    project = current_project_id()
    workflow = WorkflowStatusService(project)
    for step in ('engineering_model', 'routing', 'network_editor', 'parameters'):
        workflow.refresh_source_status(step, actor='project-refresh')
    # Outdated current routes still need inspection. Superseded/rejected routes
    # are history; no inspection here edits their immutable definitions.
    routes = [route for route in all_pages(list_routes)
              if route['status'] not in {'REJECTED', 'SUPERSEDED', 'DEPRECATED'}]
    planner, _ = load_plan()
    validation = RoutingValidator(project, physical_planner=planner).validate_table(routes)
    findings = [{**item, 'severity': 'ERROR'} for item in validation['table_errors']]
    for route, result in zip(routes, validation['results']):
        for key, severity in (('errors', 'ERROR'), ('warnings', 'WARNING')):
            findings.extend({**item, 'severity': severity, 'object_type': 'RoutingEntry',
                'object_id': str(route['id']), 'object_name': route['name'], 'route_code': route['route_code']}
                for item in result[key])
    capacity = CapacityTimingService(project).calculate()
    result = PreflightService(project).run(routing_findings=findings)
    state = workflow.get(summary=True)
    settings = (state.get('context') or {}).get('engineering_wizard_settings') or {}
    return {**result, 'project_id': project, 'project_name': settings.get('project_name') or project,
            'checked_routes': len(routes), 'capacity_snapshot_id': capacity['snapshot_id']}
