import os
import sys

# Ensure root workspace directory is in python sys.path for Vercel Serverless environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
