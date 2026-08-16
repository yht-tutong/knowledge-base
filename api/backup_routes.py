from flask import Blueprint, request, jsonify
from services.backup_service import BackupService

backup_bp = Blueprint('backup', __name__)
service = BackupService()


def success_response(data=None, message='success'):
    return jsonify({'code': 200, 'data': data, 'message': message})


def error_response(message, code=400):
    return jsonify({'code': code, 'data': None, 'message': message}), code


@backup_bp.route('/backups', methods=['GET'])
def list_backups():
    return success_response(service.list_backups())


@backup_bp.route('/backups', methods=['POST'])
def create_backup():
    body = request.get_json(silent=True) or {}
    note = body.get('note', '')
    result = service.create_backup(note=note)
    return {'code': 200, 'data': result, 'message': '备份创建成功'}


@backup_bp.route('/backups/<filename>/restore', methods=['POST'])
def restore_backup(filename):
    ok = service.restore_backup(filename)
    if not ok:
        return {'code': 404, 'data': None, 'message': '备份文件不存在'}, 404
    return {'code': 200, 'data': {'restart': True}, 'message': '恢复成功，即将重启'}


@backup_bp.route('/backups/<filename>', methods=['DELETE'])
def delete_backup(filename):
    ok = service.delete_backup(filename)
    if not ok:
        return error_response('backup not found', 404)
    return success_response(message='deleted')