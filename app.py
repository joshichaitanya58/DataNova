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
logger = logging.getLogger(__name__)
app = create_app()

if __name__ == "__main__":

    app.config['TEMPLATES_AUTO_RELOAD'] = True

    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('PORT', os.getenv('FLASK_PORT', 5000)))
    debug_env = os.getenv('FLASK_DEBUG', '0').lower() in ('true', '1', 't')

    extra_files = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for extra_dir in ['templates', 'static', 'datanova']:
        target_path = os.path.join(base_dir, extra_dir)
        if os.path.exists(target_path):
            for root, dirs, files in os.walk(target_path):
                for file in files:
                    extra_files.append(os.path.join(root, file))

    logger.info(f"DataNova Server active on http://{host}:{port}")

    app.run(
        host=host,
        port=port,
        debug=debug_env,
        use_reloader=True,
        extra_files=extra_files
    )