from flask import Blueprint, request, jsonify
from ..database.models import SessionModel

sessions_bp = Blueprint('sessions', __name__)

@sessions_bp.route('/api/sessions', methods=['GET'])
def get_sessions():
    try:
        sessions = SessionModel.get_all()
        return jsonify(sessions), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@sessions_bp.route('/api/sessions/<session_id>', methods=['GET'])
def get_session(session_id):
    try:
        session = SessionModel.get_by_id(session_id)
        if session:
            return jsonify(session), 200
        return jsonify({'error': 'Session not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@sessions_bp.route('/api/sessions', methods=['POST'])
def save_session():
    data = request.get_json() or {}
    try:
        saved = SessionModel.upsert(data)
        return jsonify(saved), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@sessions_bp.route('/api/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    try:
        success = SessionModel.delete(session_id)
        if success:
            return jsonify({'success': True, 'deletedId': session_id}), 200
        return jsonify({'error': 'Session not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
