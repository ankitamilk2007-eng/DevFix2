from flask import Blueprint, request, jsonify
from ..services.ai_service import ai_service
from ..services.verifier_service import verifier_service

debug_bp = Blueprint('debug', __name__)

@debug_bp.route('/api/diagnose', methods=['POST'])
def diagnose_error():
    data = request.get_json() or {}
    language = data.get('language', 'python')
    code = data.get('code', '')
    traceback = data.get('traceback', '')
    context = data.get('context', '')

    if not code or not code.strip():
        return jsonify({'error': 'Source code cannot be empty.'}), 400
    if not traceback or not traceback.strip():
        return jsonify({'error': 'Error traceback is required for diagnosis.'}), 400
    if language != 'python':
        return jsonify({'error': f"Language '{language}' adapter is in development. Only Python is enabled."}), 400

    try:
        diagnosis = ai_service.generate_diagnosis(language, code, traceback, context)
        proposed_fix = ai_service.generate_proposed_fix(language, code, traceback, diagnosis)

        return jsonify({
            'success': True,
            'diagnosis': diagnosis,
            'proposedFix': proposed_fix
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@debug_bp.route('/api/propose-fix', methods=['POST'])
def propose_fix():
    data = request.get_json() or {}
    language = data.get('language', 'python')
    code = data.get('code', '')
    traceback = data.get('traceback', '')
    diagnosis = data.get('diagnosis', {})

    if not code:
        return jsonify({'error': 'Source code is required.'}), 400

    try:
        proposed_fix = ai_service.generate_proposed_fix(language, code, traceback, diagnosis)
        return jsonify({
            'success': True,
            'proposedFix': proposed_fix
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@debug_bp.route('/api/verify', methods=['POST'])
def verify_fix():
    data = request.get_json() or {}
    language = data.get('language', 'python')
    original_code = data.get('originalCode', '')
    proposed_code = data.get('proposedCode') or data.get('approvedCode', '')
    tests = data.get('tests', [])
    expected_output = data.get('expectedOutput') or data.get('expected_output')

    if not proposed_code:
        return jsonify({'error': 'Proposed code is required for verification.'}), 400

    try:
        verification = verifier_service.verify_fix(
            language=language,
            original_code=original_code,
            proposed_code=proposed_code,
            tests=tests,
            expected_output=expected_output
        )
        return jsonify({
            'success': True,
            'verification': verification
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
