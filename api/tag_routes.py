import sqlite3
from flask import Blueprint, request, jsonify
from services.tag_service import TagService

tag_bp = Blueprint('tag', __name__)
service = TagService()


def success_response(data=None, message='success'):
    return jsonify({'code': 200, 'data': data, 'message': message})


def error_response(message, code=400):
    return jsonify({'code': code, 'data': None, 'message': message}), code


@tag_bp.route('/tags', methods=['GET'])
def get_tags():
    tags = service.get_all()
    return success_response(tags)


@tag_bp.route('/tags', methods=['POST'])
def create_tag():
    body = request.get_json(silent=True)
    if not body or not body.get('name'):
        return error_response('name is required')
    try:
        tag = service.create(
            name=body['name'],
            shape=body.get('shape', 'ellipse'),
            color=body.get('color', '')
        )
        return success_response(tag.to_dict(), 'created')
    except sqlite3.IntegrityError as e:
        if 'UNIQUE constraint failed' in str(e.args[0]):
            return error_response('标签名称已存在')
        return error_response(str(e))
    except Exception as e:
        return error_response(str(e))


@tag_bp.route('/tags/<int:tag_id>', methods=['DELETE'])
def delete_tag(tag_id):
    ok = service.delete(tag_id)
    if not ok:
        return error_response('tag not found', 404)
    return success_response(message='deleted')


@tag_bp.route('/tags/batch_delete', methods=['POST'])
def batch_delete_tags():
    body = request.get_json(silent=True)
    if not body or not body.get('ids'):
        return error_response('ids is required')
    ids = body['ids']
    if not isinstance(ids, list) or len(ids) == 0:
        return error_response('ids must be a non-empty array')
    try:
        count = service.batch_delete(ids)
        return success_response({'deleted': count}, '已删除 ' + str(count) + ' 个标签')
    except Exception as e:
        return error_response(str(e))