import os
import logging
from datanova import create_app

# Configure logging for the entry point
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = create_app()

if __name__ == "__main__":
    # Safety check: ensure SECRET_KEY is set
    if not app.config.get('SECRET_KEY'):
        # Generate a random key if missing (for development only)
        import secrets
        random_key = secrets.token_hex(32)
        app.config['SECRET_KEY'] = random_key
        logger.warning(
            "SECRET_KEY not found in environment. A random key has been generated. "
            "For production, set SECRET_KEY in your .env file."
        )

    # Optional: allow host/port/debug to be overridden by env vars
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')

    app.run(
        host=host,
        port=port,
        debug=debug,
        use_reloader=True  # reloader is automatically enabled when debug=True
    )