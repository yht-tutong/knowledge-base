from flask import Blueprint, request, jsonify
from services.category_service import CategoryService

category_bp = Blueprint('category', __name__)
service = CategoryService()


def success_response(data=None, message='success'):
    return jsonify({'code': 200, 'data': data, 'message': message})


def error_response(message, code=400):
    return jsonify({'code': code, 'data': None, 'message': message}), code


@category_bp.route('/categories', methods=['GET'])
def get_categories():
    categories = service.get_all()
    return success_response(categories)


@category_bp.route('/categories', methods=['POST'])
def create_category():
    body = request.get_json(silent=True)
    if not body or not body.get('name'):
        return error_response('name is required')
    try:
        category = service.create(name=body['name'], description=body.get('description', ''))
        return success_response(category.to_dict(), 'created')
    except Exception as e:
        return error_response(str(e))


@category_bp.route('/categories/<int:category_id>', methods=['GET'])
def get_category(category_id):
    category = service.get_by_id(category_id)
    if not category:
        return error_response('category not found', 404)
    return success_response(category.to_dict())


@category_bp.route('/categories/<int:category_id>', methods=['PUT'])
def update_category(category_id):
    body = request.get_json(silent=True)
    if not body:
        return error_response('request body is required')
    try:
        category = service.update(
            category_id=category_id,
            name=body.get('name'),
            description=body.get('description')
        )
        if not category:
            return error_response('category not found', 404)
        return success_response(category.to_dict(), 'updated')
    except Exception as e:
        return error_response(str(e))


@category_bp.route('/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    ok = service.delete(category_id)
    if not ok:
        return error_response('cannot delete this category', 400)
    return success_response(message='deleted')