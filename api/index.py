import os
import sys

# Ensure root directory is in sys.path so datanova and database modules are found
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from app import app

# WSGI handler for Vercel
app_handler = app
