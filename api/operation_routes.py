from flask import Blueprint
from services.operation_service import OperationService

operation_bp = Blueprint('operation', __name__)
service = OperationService()


@operation_bp.route('/operations', methods=['GET'])
def list_operations():
    ops = service.get_recent(50)
    return {'code': 200, 'data': ops, 'message': 'success'}


@operation_bp.route('/operations/<int:op_id>/undo', methods=['POST'])
def undo_operation(op_id):
    ok, msg = service.undo_operation(op_id)
    if not ok:
        return {'code': 400, 'data': None, 'message': msg}, 400
    return {'code': 200, 'data': None, 'message': msg}


@operation_bp.route('/operations/<int:op_id>/undo_all', methods=['POST'])
def undo_all_operations(op_id):
    ok, msg = service.undo_from(op_id)
    if not ok:
        return {'code': 400, 'data': None, 'message': msg}, 400
    return {'code': 200, 'data': None, 'message': msg}