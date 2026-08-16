from flask import Blueprint, request, jsonify
from services.knowledge_service import KnowledgeService
import os
import uuid

knowledge_bp = Blueprint('knowledge', __name__)
service = KnowledgeService()


def success_response(data=None, message='success'):
    return jsonify({'code': 200, 'data': data, 'message': message})


def error_response(message, code=400):
    return jsonify({'code': code, 'data': None, 'message': message}), code


@knowledge_bp.route('/knowledge', methods=['GET'])
def get_knowledge_list():
    category_id = request.args.get('category_id', type=int)
    keyword = request.args.get('keyword')
    tag_id = request.args.get('tag_id', type=int)
    tag_ids_str = request.args.get('tag_ids')
    tag_ids = None
    if tag_ids_str:
        tag_ids = [int(t.strip()) for t in tag_ids_str.split(',') if t.strip()]
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 50, type=int)

    items, total = service.get_all(
        category_id=category_id,
        keyword=keyword,
        tag_id=tag_id,
        tag_ids=tag_ids,
        page=page,
        page_size=page_size
    )
    return success_response({
        'items': items,
        'total': total,
        'page': page,
        'page_size': page_size
    })


@knowledge_bp.route('/knowledge', methods=['POST'])
def create_knowledge():
    body = request.get_json(silent=True)
    if not body:
        return error_response('request body is required')
    if not body.get('title'):
        return error_response('title is required')
    if not body.get('category_id'):
        return error_response('category_id is required')

    try:
        kp = service.create(
            title=body['title'],
            content=body.get('content', ''),
            category_id=body['category_id'],
            tag_ids=body.get('tag_ids')
        )
        return success_response(kp, 'created')
    except Exception as e:
        return error_response(str(e))


@knowledge_bp.route('/knowledge/<int:kp_id>', methods=['GET'])
def get_knowledge(kp_id):
    kp = service.get_by_id(kp_id)
    if not kp:
        return error_response('knowledge point not found', 404)
    return success_response(kp)


@knowledge_bp.route('/knowledge/<int:kp_id>', methods=['PUT'])
def update_knowledge(kp_id):
    body = request.get_json(silent=True)
    if not body:
        return error_response('request body is required')

    try:
        kp = service.update(
            kp_id=kp_id,
            title=body.get('title'),
            content=body.get('content'),
            category_id=body.get('category_id'),
            tag_ids=body.get('tag_ids')
        )
        if not kp:
            return error_response('knowledge point not found', 404)
        return success_response(kp, 'updated')
    except Exception as e:
        return error_response(str(e))


@knowledge_bp.route('/knowledge/<int:kp_id>', methods=['DELETE'])
def delete_knowledge(kp_id):
    ok = service.delete(kp_id)
    if not ok:
        return error_response('knowledge point not found', 404)
    return success_response(message='deleted')


@knowledge_bp.route('/knowledge/<int:kp_id>/duplicate', methods=['POST'])
def duplicate_knowledge(kp_id):
    try:
        kp = service.duplicate(kp_id)
        if not kp:
            return error_response('knowledge point not found', 404)
        return success_response(kp, 'duplicated')
    except Exception as e:
        return error_response(str(e))


@knowledge_bp.route('/knowledge/import', methods=['POST'])
def import_knowledge():
    body = request.get_json(silent=True)
    if not body:
        return error_response('request body is required')

    # 兼容两种格式：直接传数组 或 传 {items: [...]}
    if isinstance(body, list):
        items = body
    elif isinstance(body, dict) and body.get('items'):
        items = body['items']
    else:
        return error_response('items is required')

    try:
        result = service.import_batch(items)
        return success_response(result, 'import completed')
    except Exception as e:
        return error_response(str(e))


@knowledge_bp.route('/knowledge/export', methods=['POST'])
def export_knowledge():
    body = request.get_json(silent=True)
    if not body or not body.get('ids'):
        return error_response('ids is required')
    try:
        ids = body['ids']
        fmt = body.get('format', 'json')
        fields = body.get('fields')
        data = service.export_data(ids, format=fmt, fields=fields)
        filename = 'knowledge_export.' + fmt
        return success_response({'content': data, 'format': fmt, 'filename': filename})
    except Exception as e:
        return error_response(str(e))


STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
UPLOAD_DIR = os.path.join(STATIC_DIR, 'uploads')

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp'}


@knowledge_bp.route('/upload', methods=['POST'])
def upload_image():
    # 兼容旧参数 image 和新参数 file
    if 'file' in request.files:
        file = request.files['file']
    elif 'image' in request.files:
        file = request.files['image']
    else:
        return {'code': 400, 'data': None, 'message': 'no file uploaded'}, 400

    if file.filename == '':
        return {'code': 400, 'data': None, 'message': 'empty filename'}, 400

    ext = os.path.splitext(file.filename)[1].lower() or '.png'
    is_image = ext in IMAGE_EXTENSIONS

    if is_image:
        sub_dir = os.path.join(UPLOAD_DIR, 'images')
        url_prefix = '/uploads/images/'
    else:
        sub_dir = os.path.join(UPLOAD_DIR, 'files')
        url_prefix = '/uploads/files/'

    os.makedirs(sub_dir, exist_ok=True)
    filename = str(uuid.uuid4())[:8] + ext
    filepath = os.path.join(sub_dir, filename)
    file.save(filepath)

    url = url_prefix + filename
    name = file.filename

    if is_image:
        return {'code': 200, 'data': {
            'type': 'image',
            'url': url,
            'markdown': '![' + name + '](' + url + ')',
            'filename': filename
        }, 'message': 'ok'}
    else:
        return {'code': 200, 'data': {
            'type': 'file',
            'url': url,
            'markdown': '[' + name + '](' + url + ')',
            'filename': filename
        }, 'message': 'ok'}