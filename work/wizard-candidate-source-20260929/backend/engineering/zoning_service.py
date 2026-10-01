"""Apply location partitions and every dependent binding in one transaction."""
from copy import deepcopy
from datetime import datetime, timezone
from . import db
from .models import EngineeringValidationError
from .pagination import all_pages
from .repository import list_objects, create_object, update_object
from .routing.repository import list_routes, create_route, update_route, get_route, save_validation, approve_routes
from .routing.validation import RoutingValidator
from .workflow.service import WorkflowStatusService
from .spatial_zoning import plan_zoning, VERSION


class SpatialZoningService:
    def __init__(self, project_id):
        self.project_id = project_id
        self.workflow = WorkflowStatusService(project_id)

    def plan(self, driving_side=None):
        state = self.workflow.get()
        side = driving_side or (state['parameters'].get('spatial_zoning') or {}).get('driving_side')
        if side not in {None, 'LHD', 'RHD'}: raise EngineeringValidationError('Lenkungsseite muss LHD oder RHD sein.')
        objects = {kind: all_pages(list_objects, kind) for kind in ('HardwareNode', 'HardwareNetworkInterface', 'Message', 'Interface', 'Signal')}
        return plan_zoning(state, objects, all_pages(list_routes), side)

    @staticmethod
    def preview(plan):
        return {k: plan[k] for k in ('token', 'policy', 'architecture', 'decisions', 'divisions', 'resources', 'unresolved_devices')} | {
            'changed_objects': len(plan['changes']), 'new_channels': len(plan['creations']), 'changed_routes': len(plan['routes'])}

    def apply(self, expected_token, driving_side=None, *, actor='spatial-zoning', approve_valid=False):
        own = db.RequestUnit(self.project_id) if db._request_unit.get() is None else None
        unit = own or db._request_unit.get()
        try:
            unit.acquire()
            plan = self.plan(driving_side)
            if not expected_token or expected_token != plan['token']:
                raise db.ConcurrentUpdateError('Die Grundlage der Zonierung wurde geändert. Bitte erneut prüfen.')
            state = self.workflow.get()
            refs = {}
            def resolve(value):
                if isinstance(value, dict): return {refs.get(k, k): resolve(v) for k, v in value.items()}
                if isinstance(value, list): return [resolve(v) for v in value]
                return refs.get(value, value) if isinstance(value, str) else value
            for change in plan['creations']:
                item = create_object(change['object_type'], {**resolve(change['data']), 'source': 'ai_generated',
                    'created_by': actor, 'approval_state': 'approved', 'review_state': 'reviewed'})
                refs[change['local_ref']] = str(item['id'])
            for (kind, key), values in plan['changes'].items():
                update_object(kind, key, {**resolve(values), 'modified_by': actor})
            for route in plan['routes']:
                if str(route['id']).startswith('$zone-route-'):
                    data = {k: resolve(route[k]) for k in ('name', 'description', 'source', 'destinations', 'payload', 'route', 'timing', 'routing_policy') if k in route}
                    item = create_route({**data, 'origin': 'NETWORK_EDITOR', 'created_by': actor})
                    refs[route['id']] = str(item['id'])
                else:
                    update_route(str(route['id']), {**resolve({k: route[k] for k in ('name', 'source', 'destinations', 'route')}),
                        'expected_revision': route['revision'], 'actor': actor, 'reason': 'Physische Einbauzonen getrennt.'})
            parameters = {**state['parameters'], 'networks': plan['networks'], 'spatial_zoning': plan['policy'],
                          'spatial_architecture': plan['architecture']}
            parameters.pop('communication_schedule', None)  # Slots belong to the old physical channels.
            self.workflow.save_parameters(parameters, actor=actor)
            db.flush_model_changes(actor=actor, reason='Einbauorte, lokale Busse und Nachrichtenbindungen gemeinsam zoniert.')
            topology = resolve(plan['topology'])
            from .topology_sync import sync_topology
            sync_topology({**topology, 'topology_id': 'studio-network'})
            db.flush_model_changes(actor=actor, reason='Kanonische physische Beziehungen mit Einbauzonen synchronisiert.')
            self.workflow.save_topology(topology, actor=actor)
            validator = RoutingValidator(self.project_id)
            valid = []
            for route in plan['routes']:
                key = refs.get(str(route['id']), str(route['id']))
                result = validator.validate(get_route(key), exclude_route_id=key)
                if not result.get('valid'):
                    raise EngineeringValidationError('Zonierung zurückgerollt: ' + route['name'] + ': ' +
                        '; '.join(e['message'] for e in result.get('errors', [])[:3]))
                save_validation(key, result, actor=actor); valid.append(key)
            if approve_valid and valid: approve_routes(valid, actor=actor)
            self.workflow.refresh_source_status('routing', actor=actor, reason='Routen der räumlichen Busaufteilung geprüft.')
            self.workflow.save_topology(topology, actor=actor)
            self.workflow.save_parameters(parameters, actor=actor)
            request = deepcopy(state.get('context', {}).get('wizard_request') or {})
            import re
            prompt = re.sub(r'^- Lenkungsseite:.*(?:\n|$)', '', request.get('prompt', ''), flags=re.M)
            if plan['policy']['driving_side']: prompt += '\n- Lenkungsseite: ' + plan['policy']['driving_side']
            request['prompt'] = prompt
            self.workflow.set_context({'wizard_request': request})
            receipt = {**self.preview(plan), 'version': VERSION, 'created_at': datetime.now(timezone.utc).isoformat(),
                       'valid_routes': len(valid), 'approved': bool(approve_valid)}
            parameters['spatial_zoning_receipt'] = receipt
            self.workflow.save_parameters(parameters, actor=actor)
            # Re-dimension and persist schedules for the new buses before capacity.
            from .capacity.sizing_service import CommunicationSizingService
            sizing = CommunicationSizingService(self.project_id)
            sizing_plan = sizing.preview()
            sizing_result = sizing.apply(sizing_plan['source_token'], actor=actor, approve_valid=approve_valid)
            from .capacity.service import CapacityTimingService
            capacity = CapacityTimingService(self.project_id).calculate()
            result = {'applied': True, 'zoning': receipt, 'dimensioning': sizing_result,
                      'capacity': {k: capacity.get(k) for k in ('id', 'status', 'is_outdated')}}
            if own: own.finish(True)
            return result
        finally:
            if own: own.close()
