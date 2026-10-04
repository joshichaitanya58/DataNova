import os
import sys
import tempfile
import logging
import traceback
from flask import Flask, jsonify, request
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()


def create_app():
    """
    Application factory to create and configure the Flask app.
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    template_dir = os.path.join(base_dir, 'templates')
    static_dir = os.path.join(base_dir, 'static')

    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=template_dir,
        static_folder=static_dir
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

    secret_key = os.getenv('SECRET_KEY') or os.getenv('FLASK_SECRET_KEY')
    if not secret_key:
        secret_key = 'datanova-production-default-secret-key-please-set-in-env'
        logging.warning("SECRET_KEY is not set in environment. Using fallback secret key.")

    # Determine safe upload folder for local or serverless/Vercel environments
    if os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
        upload_folder = os.path.join(tempfile.gettempdir(), 'uploads')
    else:
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
        if not os.getenv('VERCEL'):
            os.makedirs(app.instance_path, exist_ok=True)
        os.makedirs(upload_folder, exist_ok=True)
    except OSError as e:
        app.logger.warning(f"Could not create primary upload folder, using system temp dir: {e}")
        upload_folder = os.path.join(tempfile.gettempdir(), 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        app.config['UPLOAD_FOLDER'] = upload_folder

    # --- Auto-Initialize Database Schema & Tables ---
    try:
        from database.db_connector import init_db
        init_db()
    except Exception as e:
        app.logger.warning(f"Database auto-initialization deferred or failed: {e}")

    # --- Load Persistent System Settings (MySQL Database primary, JSON fallback) ---
    from .services.system_settings_service import load_merged_system_settings
    default_settings = {
        # General
        'platform_name': 'DataNova Analytics Platform',
        'default_role': 'developer',
        'max_file_size_mb': '50',
        'allowed_extensions': '.csv, .xlsx, .xls, .json',
        'allow_user_registration': True,
        'maintenance_mode': False,
        # Security
        'session_timeout': '60',
        'max_login_attempts': '5',
        'lockout_duration_mins': '15',
        'enforce_strong_passwords': True,
        'require_email_verification': False,
        # Email & SMTP
        'smtp_host': 'smtp.gmail.com',
        'smtp_port': '587',
        'sender_email': 'noreply@datanova.com',
        'smtp_username': '',
        'smtp_password': '',
        'smtp_encryption': 'tls',
        # AI & Limits
        'ai_insights_enabled': True,
        'ai_model': 'gemini-2.0-flash',
        'ai_max_tokens': '1024',
        'ai_temperature': '0.7',
        'auto_eda_on_upload': True
    }
    app.config['SYSTEM_SETTINGS'] = load_merged_system_settings(default_settings, app.instance_path)

    bcrypt.init_app(app)


    # --- Register Blueprints ---
    from . import auth, dashboards, api
    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboards.bp)
    app.register_blueprint(api.bp, url_prefix='/api')

    # Start background file retention cleanup (both local instance/uploads and Google Drive)
    from .services import gdrive_service
    if not (os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME')):
        gdrive_service.start_background_retention_cleanup()
    if gdrive_service.is_configured():
        app.logger.info("Google Drive Cloud Storage: ACTIVE & CONFIGURED")
    else:
        app.logger.info("Google Drive Cloud Storage: PENDING CREDENTIALS (Local Instance Storage Fallback Active)")


    @app.route('/sw.js')
    def serve_sw():
        """Serves the Service Worker file to avoid 404 logs from browser requests."""
        return app.send_static_file('sw.js')

    @app.route('/favicon.ico')
    def serve_favicon():
        """Serves the favicon file to avoid 404 logs from browser requests."""
        return app.send_static_file('assets/favicon.png')

    @app.route('/static/uploads/<path:filename>')
    def serve_uploaded_static_file(filename):
        """Serves uploaded static files (support attachments, etc.) directly from Google Drive in memory."""
        from flask import Response, send_from_directory
        rel_path = gdrive_service.get_relative_drive_path(f"uploads/{filename}")
        file_bytes = gdrive_service.get_file_bytes(rel_path)
        if file_bytes:
            import mimetypes
            mime, _ = mimetypes.guess_type(filename)
            return Response(file_bytes, mimetype=mime or 'application/octet-stream')

        uploads_folder = os.path.join(app.static_folder, 'uploads')
        if os.path.exists(os.path.join(uploads_folder, filename)):
            return send_from_directory(uploads_folder, filename)
        return "File not found", 404



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
            if request.path == '/api/system/live_sync' and status_code == 200:
                # Suppress terminal log spam for routine background heartbeat
                pass
            elif status_code < 300:
                tag = f"\033[92m[API SUCCESS {status_code}]\033[0m"
                print(f"{tag} {request.method} \033[1m{request.path}\033[0m | Time: {duration_ms}ms", flush=True)
            elif status_code < 400:
                tag = f"\033[93m[API REDIRECT {status_code}]\033[0m"
                print(f"{tag} {request.method} \033[1m{request.path}\033[0m | Time: {duration_ms}ms", flush=True)
            else:
                tag = f"\033[91;1m[API ERROR {status_code}]\033[0m"
                print(f"{tag} {request.method} \033[1m{request.path}\033[0m | Time: {duration_ms}ms", flush=True)
        else:
            if status_code >= 400:
                tag = f"\033[91m[PAGE ERROR {status_code}]\033[0m"
                print(f"{tag} {request.method} {request.path} | Time: {duration_ms}ms", flush=True)
        # Add Cache-Control for static assets to reduce browser response time
        if request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'public, max-age=86400'

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