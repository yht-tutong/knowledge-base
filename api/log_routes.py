"""日志查看 API"""
import os
from flask import Blueprint, jsonify, request

log_bp = Blueprint('log', __name__)
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')


@log_bp.route('/logs', methods=['GET'])
def list_logs():
    """列出所有日志文件"""
    if not os.path.isdir(LOG_DIR):
        return jsonify({'code': 0, 'data': [], 'message': 'ok'})

    files = []
    for f in os.listdir(LOG_DIR):
        if f.endswith('.log'):
            path = os.path.join(LOG_DIR, f)
            stat = os.stat(path)
            files.append({
                'name': f,
                'size': stat.st_size,
                'modified': stat.st_mtime,
            })
    files.sort(key=lambda x: x['modified'], reverse=True)
    return jsonify({'code': 0, 'data': files, 'message': 'ok'})


@log_bp.route('/logs/<filename>', methods=['GET'])
def read_log(filename):
    """读取日志文件内容"""
    path = os.path.join(LOG_DIR, filename)
    if not os.path.isfile(path) or not filename.endswith('.log'):
        return jsonify({'code': 1, 'message': '文件不存在'}), 404

    lines_param = request.args.get('lines', '200')
    try:
        lines = int(lines_param)
    except ValueError:
        lines = 200

    with open(path, 'r', encoding='utf-8') as f:
        all_lines = f.readlines()

    total = len(all_lines)
    content = ''.join(all_lines[-lines:])

    return jsonify({
        'code': 0,
        'data': {
            'filename': filename,
            'total_lines': total,
            'content': content,
        },
        'message': 'ok',
    })