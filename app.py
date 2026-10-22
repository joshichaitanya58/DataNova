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
    is_render = bool(os.getenv('RENDER') or os.getenv('IS_PULL_REQUEST'))
    
    # Render assigns dynamic PORT; fall back to FLASK_PORT or 5000
    raw_port = os.getenv('PORT') or os.getenv('FLASK_PORT') or '5000'
    port = int(raw_port) if str(raw_port).isdigit() else 5000
    
    # In cloud/Render environment, bind to 0.0.0.0 so incoming requests are accepted
    default_host = '0.0.0.0' if (is_render or os.getenv('PORT')) else '127.0.0.1'
    host = os.getenv('FLASK_HOST', default_host)
    
    debug_env = os.getenv('FLASK_DEBUG', '0').lower() in ('true', '1', 't')
    if is_render:
        debug_env = False  # Always force production mode on Render

    extra_files = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if debug_env:
        app.config['TEMPLATES_AUTO_RELOAD'] = True
        for extra_dir in ['templates', 'static', 'datanova']:
            target_path = os.path.join(base_dir, extra_dir)
            if os.path.exists(target_path):
                for root, dirs, files in os.walk(target_path):
                    for file in files:
                        extra_files.append(os.path.join(root, file))

    logger.info(f"DataNova Server starting on http://{host}:{port} (Render: {is_render})")

    app.run(
        host=host,
        port=port,
        debug=debug_env,
        use_reloader=debug_env,
        extra_files=extra_files if debug_env else None
    )