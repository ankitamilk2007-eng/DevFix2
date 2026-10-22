from flask import Blueprint, jsonify
from ..services.ai_service import ai_service

health_bp = Blueprint('health', __name__)

@health_bp.route('/api/health', methods=['GET'])
def health_check():
    ai_status = ai_service.get_status()
    return jsonify({
        'status': 'ok',
        'backend': 'DevFix AI Flask REST API',
        'version': '1.0.0',
        'ai_provider': ai_status,
        'environment': {
            'python_version': '3.14+',
            'supported_languages': ['python']
        }
    }), 200

@health_bp.route('/api/languages', methods=['GET'])
def get_languages():
    return jsonify([
        {
            'id': 'python',
            'name': 'Python',
            'enabled': True,
            'version': '3.10+',
            'runner': 'CPython Subprocess'
        },
        {
            'id': 'java',
            'name': 'Java',
            'enabled': False,
            'version': 'OpenJDK 17/21',
            'runner': 'Coming Soon'
        },
        {
            'id': 'c',
            'name': 'C',
            'enabled': False,
            'version': 'GCC/Clang',
            'runner': 'Coming Soon'
        },
        {
            'id': 'cpp',
            'name': 'C++',
            'enabled': False,
            'version': 'G++ 13+',
            'runner': 'Coming Soon'
        },
        {
            'id': 'javascript',
            'name': 'JavaScript',
            'enabled': False,
            'version': 'Node.js 20+ LTS',
            'runner': 'Coming Soon'
        }
    ]), 200
