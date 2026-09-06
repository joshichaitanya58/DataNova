import os
import sys
import logging
import traceback
from flask import Flask, jsonify, request
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()


def create_app():
    """
    Application factory to create and configure the Flask app.
    """
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder='../templates',
        static_folder='../static'
    )

    # --- Configure Terminal Logging & Suppress Noisy 3rd-Party Debuggers ---
    for noisy in ['matplotlib', 'matplotlib.font_manager', 'PIL', 'urllib3', 'kiwisolver', 'werkzeug']:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Disable Werkzeug's default verbose HTTP request logger to use our clean API logger
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

    app.logger.setLevel(logging.INFO)

    # --- Load environment variables ---
    from dotenv import load_dotenv
    load_dotenv()

    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        raise RuntimeError(
            "SECRET_KEY environment variable is not set. "
            "Please set it in your .env file or environment."
        )

    upload_folder = os.path.join(app.instance_path, 'uploads')

    app.config.from_mapping(
        SECRET_KEY=secret_key,
        UPLOAD_FOLDER=upload_folder,
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,  # 50 MB upload limit
        TEMPLATES_AUTO_RELOAD=True,
        PRIMARY_COLOR='#4F46E5',
        VIOLET_COLOR='#7C3AED',
        CYAN_COLOR='#06B6D4',
        GREEN_COLOR='#10B981',
    )

    try:
        os.makedirs(app.instance_path, exist_ok=True)
        os.makedirs(upload_folder, exist_ok=True)
    except OSError as e:
        app.logger.warning(f"Could not create required directories: {e}")

    # --- Load Persistent System Settings ---
    import json
    settings_file = os.path.join(app.instance_path, 'system_settings.json')
    default_settings = {
        'smtp_host': 'smtp.gmail.com',
        'smtp_port': '587',
        'sender_email': 'noreply@datanova.com',
        'default_role': 'viewer',
        'maintenance_mode': False,
        'session_timeout': '60',
        'max_file_size_mb': '50',
        'ai_insights_enabled': True
    }
    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                saved_settings = json.load(f)
                default_settings.update(saved_settings)
        except Exception as e:
            app.logger.error(f"Error loading system_settings.json: {e}")

    app.config['SYSTEM_SETTINGS'] = default_settings

    bcrypt.init_app(app)

    # --- Register Blueprints ---
    from . import auth, dashboards, api
    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboards.bp)
    app.register_blueprint(api.bp, url_prefix='/api')

    @app.route('/sw.js')
    def serve_sw():
        """Serves the Service Worker file to avoid 404 logs from browser requests."""
        return app.send_static_file('sw.js')

    @app.route('/favicon.ico')
    def serve_favicon():
        """Serves the favicon file to avoid 404 logs from browser requests."""
        return app.send_static_file('assets/favicon.png')

    # --- High-Visibility Development Request & API Call Middleware ---
    import time
    from flask import session, flash, redirect, url_for
    @app.before_request
    def _enforce_session_timeout_and_timer():
        request._start_time = time.time()
        
        # --- Session Timeout Enforcement ---
        if session.get('loggedin'):
            last_activity = session.get('last_activity')
            now = time.time()
            settings = app.config.get('SYSTEM_SETTINGS', {})
            try:
                timeout_minutes = int(settings.get('session_timeout', 60))
            except (ValueError, TypeError):
                timeout_minutes = 60

            # If user has been inactive longer than session_timeout minutes, expire session
            if last_activity and (now - last_activity) > (timeout_minutes * 60):
                session.clear()
                if request.path.startswith('/api/') or request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': 'Session expired due to inactivity. Please log in again.'}), 401
                flash('Session expired due to inactivity. Please log in again.', 'warning')
                return redirect(url_for('auth.login'))

            session['last_activity'] = now

    @app.after_request
    def _log_request_summary(response):
        if hasattr(request, '_start_time'):
            duration_ms = round((time.time() - request._start_time) * 1000, 1)
        else:
            duration_ms = 0

        status_code = response.status_code
        status_tag = f"[{status_code}]"

        # Highlight API endpoints vs page routes
        if request.path.startswith('/api/'):
            if status_code < 300:
                tag = f"\033[92m[API SUCCESS {status_code}]\033[0m"
            elif status_code < 400:
                tag = f"\033[93m[API REDIRECT {status_code}]\033[0m"
            else:
                tag = f"\033[91;1m[API ERROR {status_code}]\033[0m"
            print(f"{tag} {request.method} \033[1m{request.path}\033[0m | Time: {duration_ms}ms", flush=True)
        else:
            if status_code >= 400:
                tag = f"\033[91m[PAGE ERROR {status_code}]\033[0m"
                print(f"{tag} {request.method} {request.path} | Time: {duration_ms}ms", flush=True)
            elif not request.path.startswith('/static/'):
                tag = f"\033[94m[PAGE]\033[0m"
                print(f"{tag} {request.method} {request.path} ({status_code}) | Time: {duration_ms}ms", flush=True)
        return response

    # --- Clear Error & Traceback Terminal Formatting ---
    @app.errorhandler(Exception)
    def handle_unhandled_exception(e):
        """Logs clear, high-visibility exception stack trace directly to terminal stdout."""
        tb = traceback.format_exc()
        
        # Extract location of error
        err_lines = [line.strip() for line in tb.splitlines() if "datanova" in line or "app.py" in line]
        location = err_lines[-1] if err_lines else "Unknown Location"

        print(f"\n\033[91;1m================================ EXCEPTION ERROR DETECTED ================================\033[0m", flush=True)
        print(f"\033[93m[API / ENDPOINT]:\033[0m {request.method} {request.url}", flush=True)
        print(f"\033[93m[ERROR TYPE]:\033[0m    {type(e).__name__}: {str(e)}", flush=True)
        print(f"\033[93m[LOCATION]:\033[0m      {location}", flush=True)
        print(f"\033[91m[FULL TRACEBACK]:\033[0m\n{tb}", flush=True)
        print(f"\033[91;1m==========================================================================================\033[0m\n", flush=True)

        if request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'message': f'Internal Server Error: {str(e)}',
                'error_type': type(e).__name__
            }), 500

        return f"<h3>500 Internal Server Error</h3><pre>{tb}</pre>" if app.debug else "500 Internal Server Error", 500

    @app.errorhandler(404)
    def handle_404_error(e):
        print(f"\033[93m[404 NOT FOUND]\033[0m {request.method} {request.path}", flush=True)
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'message': 'API endpoint not found (404).'}), 404
        return e, 404

    @app.errorhandler(403)
    def handle_403_error(e):
        print(f"\033[91m[403 FORBIDDEN]\033[0m {request.method} {request.path}", flush=True)
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'message': 'Access forbidden (403).'}), 403
        return e, 403

    @app.errorhandler(413)
    def request_entity_too_large(error):
        app.logger.warning(f"[413 PAYLOAD TOO LARGE] File upload exceeds limit.")
        return jsonify({
            'success': False,
            'message': 'File is too large. Maximum allowed size is 50 MB.'
        }), 413

    return app