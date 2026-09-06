import os
import sys
import logging
from datanova import create_app

# Configure verbose terminal logging format for all modules
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s [%(name)s]: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
# Mute noisy 3rd party debug loggers (matplotlib, font_manager, PIL, urllib3)
for noisy_logger in ['matplotlib', 'matplotlib.font_manager', 'PIL', 'urllib3', 'kiwisolver']:
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

app = create_app()

if __name__ == "__main__":
    if not app.config.get('SECRET_KEY'):
        import secrets
        random_key = secrets.token_hex(32)
        app.config['SECRET_KEY'] = random_key
        logger.warning(
            "SECRET_KEY not found in environment. A random key has been generated. "
            "For production, set SECRET_KEY in your .env file."
        )

    app.config['TEMPLATES_AUTO_RELOAD'] = True

    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug_env = os.getenv('FLASK_DEBUG', '1').lower() in ('true', '1', 't')

    extra_files = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for extra_dir in ['templates', 'static', 'datanova']:
        target_path = os.path.join(base_dir, extra_dir)
        if os.path.exists(target_path):
            for root, dirs, files in os.walk(target_path):
                for file in files:
                    extra_files.append(os.path.join(root, file))

    logger.info(f"DataNova Server active on http://{host}:{port} | Verbose Terminal Error Logging Enabled.")

    app.run(
        host=host,
        port=port,
        debug=debug_env,
        use_reloader=True,
        extra_files=extra_files
    )