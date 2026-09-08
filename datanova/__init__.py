import os
from flask import Flask, jsonify
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()


def create_app():
    """
    Application factory to create and configure the Flask app.
    """
    # Determine absolute paths for templates and static folders
    base_dir = os.path.abspath(os.path.dirname(__file__))
    templates_dir = os.path.abspath(os.path.join(base_dir, '..', 'templates'))
    static_dir = os.path.abspath(os.path.join(base_dir, '..', 'static'))

    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=templates_dir,
        static_folder=static_dir
    )

    # --- Load environment variables ---
    from dotenv import load_dotenv
    load_dotenv()

    # Ensure SECRET_KEY is set (fallback for serverless preview/build)
    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        secret_key = os.getenv('SECRET_KEY', 'datanova-secret-production-key-change-in-env')

    # Determine upload directory: Use /tmp in serverless/read-only environments
    import tempfile
    is_serverless = os.getenv('VERCEL') is not None or os.getenv('AWS_LAMBDA_FUNCTION_NAME') is not None
    if is_serverless:
        upload_folder = os.path.join(tempfile.gettempdir(), 'datanova_uploads')
    else:
        upload_folder = os.path.join(app.instance_path, 'uploads')

    app.config.from_mapping(
        SECRET_KEY=secret_key,
        UPLOAD_FOLDER=upload_folder,
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,  # 50 MB upload limit
        # Charting Colors
        PRIMARY_COLOR='#4F46E5',
        VIOLET_COLOR='#7C3AED',
        CYAN_COLOR='#06B6D4',
        GREEN_COLOR='#10B981',
    )

    # Ensure upload directory exists safely
    try:
        if not is_serverless:
            os.makedirs(app.instance_path, exist_ok=True)
        os.makedirs(upload_folder, exist_ok=True)
    except OSError as e:
        # Fallback to temp directory if instance directory is read-only
        upload_folder = os.path.join(tempfile.gettempdir(), 'datanova_uploads')
        app.config['UPLOAD_FOLDER'] = upload_folder
        try:
            os.makedirs(upload_folder, exist_ok=True)
        except OSError:
            pass
        app.logger.warning(f"Using temp upload folder due to: {e}")

    # Initialize extensions
    bcrypt.init_app(app)

    # --- Register Blueprints ---
    from . import auth, dashboards, api
    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboards.bp)
    app.register_blueprint(api.bp, url_prefix='/api')

    # --- Custom Error Handlers ---
    @app.errorhandler(413)
    def request_entity_too_large(error):
        """Handles file uploads that are too large."""
        return jsonify({
            'success': False,
            'message': 'File is too large. The maximum allowed size is 50 MB.'
        }), 413

    return app