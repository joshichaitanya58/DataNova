"""
DataNova Keep-Alive Background Service for Cloud Deployments (Render / Free Tier Workaround)
==========================================================================================
Periodically sends lightweight HTTP GET requests to the public /health endpoint to prevent
free-tier hosting platforms (such as Render) from spinning down after 15 minutes of inactivity.
"""

import os
import time
import logging
import threading
import requests

logger = logging.getLogger(__name__)

_KEEP_ALIVE_THREAD_STARTED = False


def _get_target_health_url() -> str:
    """
    Resolves the public URL for the health check endpoint.
    Priority:
    1. KEEP_ALIVE_URL (.env)
    2. APP_URL (.env)
    3. RENDER_EXTERNAL_URL (Render environment variable, e.g. https://datanova.onrender.com)
    4. RENDER_EXTERNAL_HOSTNAME (e.g. datanova.onrender.com)
    """
    explicit_url = (os.getenv("KEEP_ALIVE_URL") or os.getenv("APP_URL") or "").strip()
    if explicit_url:
        return explicit_url.rstrip("/") + "/health"

    render_url = (os.getenv("RENDER_EXTERNAL_URL") or "").strip()
    if render_url:
        return render_url.rstrip("/") + "/health"

    render_hostname = (os.getenv("RENDER_EXTERNAL_HOSTNAME") or "").strip()
    if render_hostname:
        return f"https://{render_hostname}/health"

    return ""


def _ping_health_endpoint(target_url: str) -> bool:
    """Sends an external HTTP GET request to reset the hosting provider's inactivity timer."""
    headers = {
        "User-Agent": "DataNova-Internal-KeepAlive/1.0 (Self-Health-Probe)",
        "X-Keep-Alive": "true",
        "Accept": "application/json"
    }
    try:
        resp = requests.get(target_url, headers=headers, timeout=15)
        if resp.status_code == 200:
            logger.info(f"[Keep-Alive] Pinged {target_url} -> HTTP 200 OK. Hosting inactivity timer reset.")
            return True
        else:
            logger.warning(f"[Keep-Alive] Ping to {target_url} returned HTTP {resp.status_code}.")
            return False
    except requests.RequestException as req_err:
        logger.warning(f"[Keep-Alive] Ping to {target_url} failed: {req_err}")
        return False


def start_keep_alive_daemon(interval_seconds: int = 600):
    """
    Starts a background daemon thread that periodically pings the public health endpoint
    every `interval_seconds` (default: 600s / 10 minutes; comfortably before Render's 15m idle shutdown).
    """
    global _KEEP_ALIVE_THREAD_STARTED
    if _KEEP_ALIVE_THREAD_STARTED:
        return

    # Check if self-ping is explicitly disabled
    if os.getenv("ENABLE_SELF_PING", "true").lower() in ("false", "0", "no"):
        logger.info("[Keep-Alive] Self-ping daemon is disabled via ENABLE_SELF_PING=false.")
        return

    target_url = _get_target_health_url()

    def _worker():
        # Wait 45 seconds after initial boot to allow WSGI server and network to stabilize
        time.sleep(45)

        current_target = target_url or _get_target_health_url()
        if not current_target:
            # In local dev without RENDER_EXTERNAL_URL, check again periodically or idle silently
            logger.info("[Keep-Alive] No public URL found (RENDER_EXTERNAL_URL or APP_URL not set). Standing by.")

        while True:
            active_url = _get_target_health_url()
            if active_url:
                _ping_health_endpoint(active_url)
            time.sleep(interval_seconds)

    thread = threading.Thread(target=_worker, daemon=True, name="DataNovaKeepAliveWorker")
    thread.start()
    _KEEP_ALIVE_THREAD_STARTED = True
    if target_url:
        logger.info(f"[Keep-Alive] Background daemon active for '{target_url}' (Interval: {interval_seconds}s).")
    else:
        logger.info(f"[Keep-Alive] Background daemon active. Will auto-ping once public hostname is resolved.")
