"""Exercise corrected command validation and approval in a rolled-back transaction."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.engineering.db import RequestUnit, close_pool
from backend.engineering.project_context import activate_project, reset_project
from backend.engineering.repository import create_object
from backend.engineering.routing.repository import get_route, save_validation, approve_routes
from backend.engineering.routing.validation import RoutingValidator
from backend.engineering.models import EngineeringValidationError

project = 'network-project-20260909082213746-780a13ef'
route_id = '79af0d80-8577-4eb7-af93-6dd5d29766e0'
token = activate_project(project)
unit = RequestUnit(project)
try:
    validator = RoutingValidator(project_id=project)
    invalid = validator.validate(get_route(route_id), exclude_route_id=route_id)
    assert 'COMMAND_SIGNALS_MISSING' in {e['code'] for e in invalid['errors']}
    conflict = save_validation(route_id, invalid, actor='regression-test')
    assert conflict['approval_state'] == 'PENDING'
    assert conflict['approved_at'] is None
    try:
        approve_routes([route_id], actor='regression-test')
        raise AssertionError('Invalid command was approved')
    except EngineeringValidationError:
        pass
    create_object('Signal', {
        'name': 'RollbackOnlyCommand', 'message_id': '73cbaf4f-f0c2-477e-a5bb-d39dc8acc900',
        'start_bit': 0, 'length_bits': 1, 'byte_order': 'little_endian',
        'data_type': 'unsigned', 'factor': 1, 'offset_value': 0, 'min_value': 0, 'max_value': 1,
    })
    validation = validator.validate(get_route(route_id), exclude_route_id=route_id)
    assert validation['valid'], validation['errors']
    ready = save_validation(route_id, validation, actor='regression-test')
    assert ready['status'] == 'READY_FOR_REVIEW'
    assert ready['approval_state'] == 'PENDING'
    approved = approve_routes([route_id], actor='regression-test')[0]
    assert approved['status'] == approved['approval_state'] == 'APPROVED'
    assert approved['approved_at'] is not None
    print(json.dumps({'invalid_blocked': True, 'corrected_ready': True, 'reapproved': True, 'persisted_test_data': False}))
finally:
    unit.close()
    reset_project(token)
    close_pool()
