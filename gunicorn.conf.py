"""
Production Gunicorn Configuration for DataNova Platform on Render.
Optimized for high-concurrency analytics workloads, AI timeouts, and memory safety.
"""

import os
import multiprocessing

# Port binding: Render injects the PORT environment variable
port = os.getenv("PORT", "5000")
bind = f"0.0.0.0:{port}"

# Concurrency configuration:
# 2 workers with 4 threads each provides 8 concurrent request handlers
# while staying safely within Render's 512 MB memory limit.
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
threads = int(os.getenv("PYTHON_MAX_THREADS", "4"))
worker_class = "gthread"

# Timeout: Generous 120-second timeout to allow heavy ML training,
# deep statistical EDA, and AI synthesis calls without 502/504 errors.
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
keepalive = 5

# Memory Leak Prevention: Automatically restart workers after serving
# 1,000 requests (with random jitter to prevent simultaneous worker restarts).
max_requests = 1000
max_requests_jitter = 50

# Logging: Stream directly to stdout/stderr for Render live logs dashboard
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")

# Process naming
proc_name = "datanova_app"
