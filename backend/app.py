import os
import sys
from pathlib import Path

# Add project root to sys.path so package imports resolve cleanly
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load .env if present
env_path = current_dir.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

from backend.database.db import init_db
from backend.routes.health import health_bp
from backend.routes.debug import debug_bp
from backend.routes.sessions import sessions_bp

def create_app():
    app = Flask(__name__)

    # Configure CORS for local development
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    # Initialize SQLite database
    init_db()

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(debug_bp)
    app.register_blueprint(sessions_bp)

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Resource not found', 'status': 404}), 404

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({'error': 'Bad request', 'status': 400}), 400

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({'error': 'Internal server error', 'status': 500}), 500

    return app

if __name__ == '__main__':
    port = int(os.environ.get('FLASK_PORT', 5000))
    app = create_app()
    print(f"====================================================")
    print(f"DevFix AI Flask Backend Server")
    print(f"Listening on: http://127.0.0.1:{port}")
    print(f"Health check: http://127.0.0.1:{port}/api/health")
    print(f"====================================================")
    app.run(host='127.0.0.1', port=port, debug=False)
