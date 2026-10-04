"""
Google Drive Storage Service for DataNova Platform (Requests-based Engine).
Handles secure, production-grade uploading, downloading, caching, and deletion
of dataset files (raw & processed) and support attachments on Google Drive.
Uses Python 'requests' + 'google.auth' for robust Windows SSL and proxy compatibility.
"""

import os
import io
import json
import logging
import time
import shutil
import threading
import requests
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)

_CREDS = None
_CREDS_EXPIRY = 0
_FOLDER_CACHE: Dict[str, str] = {}
SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive']


def get_relative_drive_path(local_path: str) -> str:
    """
    Converts a local filesystem path into a standardized relative Google Drive path.
    Example:
      '.../instance/uploads/raw/user_1/abc.csv' -> 'raw/user_1/abc.csv'
      '.../instance/uploads/processed/user_1/12.pkl' -> 'processed/user_1/12.pkl'
      '.../static/uploads/support/support_xyz.png' -> 'support/support_xyz.png'
    """
    if not local_path:
        return ""
    normalized = local_path.replace('\\', '/')
    if '/raw/' in normalized:
        return 'raw/' + normalized.split('/raw/')[-1]
    elif '/processed/' in normalized:
        return 'processed/' + normalized.split('/processed/')[-1]
    elif '/support/' in normalized:
        return 'support/' + normalized.split('/support/')[-1]
    elif '/uploads/' in normalized:
        return normalized.split('/uploads/')[-1]
    else:
        return os.path.basename(normalized)


def _get_credentials():
    """Initializes credentials object supporting OAuth Refresh Token or Service Account."""
    global _CREDS
    if _CREDS is not None:
        return _CREDS

    try:
        from google.oauth2 import service_account
        from google.oauth2.credentials import Credentials

        # Method 1: OAuth Refresh Token (Primary for Personal Gmail 15GB Storage)
        client_id = (os.getenv('GDRIVE_CLIENT_ID') or os.getenv('GOOGLE_CLIENT_ID') or '').strip()
        client_secret = (os.getenv('GDRIVE_CLIENT_SECRET') or os.getenv('GOOGLE_CLIENT_SECRET') or '').strip()
        refresh_token = (os.getenv('GDRIVE_REFRESH_TOKEN') or '').strip()

        if client_id and client_secret and refresh_token and 'your_google' not in client_secret:
            _CREDS = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=SCOPES
            )
            logger.info("Google Drive authenticated using OAuth Refresh Token (Personal Drive 15GB).")
            return _CREDS

        # Method 2: Service Account File Path
        sa_file = (os.getenv('GDRIVE_SERVICE_ACCOUNT_FILE') or '').strip()
        if sa_file:
            if not os.path.isabs(sa_file):
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
                candidate = os.path.normpath(os.path.join(base_dir, sa_file))
                if os.path.exists(candidate):
                    sa_file = candidate
            if os.path.exists(sa_file):
                try:
                    _CREDS = service_account.Credentials.from_service_account_file(sa_file, scopes=SCOPES)
                    logger.info(f"Google Drive authenticated using Service Account File: {sa_file}")
                    return _CREDS
                except Exception as e:
                    logger.error(f"Error loading service account file '{sa_file}': {e}")

        # Method 3: Service Account JSON String
        sa_json_str = (os.getenv('GDRIVE_SERVICE_ACCOUNT_JSON') or '').strip()
        if sa_json_str:
            try:
                info = json.loads(sa_json_str)
                _CREDS = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
                logger.info("Google Drive authenticated using GDRIVE_SERVICE_ACCOUNT_JSON.")
                return _CREDS
            except Exception as e:
                logger.error(f"Error parsing GDRIVE_SERVICE_ACCOUNT_JSON: {e}")

        return None

    except Exception as e:
        logger.error(f"Failed to initialize Google Drive credentials: {e}")
        return None


def _get_access_token() -> Optional[str]:
    """Refreshes and returns a valid Bearer Access Token."""
    creds = _get_credentials()
    if not creds:
        return None

    try:
        import google.auth.transport.requests
        req = google.auth.transport.requests.Request()
        creds.refresh(req)
        return creds.token
    except Exception as e:
        logger.error(f"Failed to refresh Google Drive access token: {e}")
        return None


def is_configured() -> bool:
    """Checks if Google Drive credentials and Root Folder ID are present."""
    root_id = (os.getenv('GDRIVE_FOLDER_ID') or '').strip()
    if not root_id:
        return False
    token = _get_access_token()
    return token is not None


def _get_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}"
    }


def _get_or_create_folder(folder_name: str, parent_id: str, token: str) -> Optional[str]:
    """Finds or creates a folder on Google Drive inside parent_id using requests."""
    cache_key = f"{parent_id}/{folder_name}"
    if cache_key in _FOLDER_CACHE:
        return _FOLDER_CACHE[cache_key]

    try:
        query = f"'{parent_id}' in parents and name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        url = "https://www.googleapis.com/drive/v3/files"
        params = {
            "q": query,
            "spaces": "drive",
            "fields": "files(id, name)",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true"
        }

        resp = requests.get(url, headers=_get_headers(token), params=params, timeout=12)
        if resp.status_code == 200:
            files = resp.json().get('files', [])
            if files:
                folder_id = files[0]['id']
                _FOLDER_CACHE[cache_key] = folder_id
                return folder_id

        # Create subfolder if not found
        payload = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id]
        }
        create_resp = requests.post(
            url,
            headers={**_get_headers(token), "Content-Type": "application/json"},
            json=payload,
            params={"supportsAllDrives": "true"},
            timeout=12
        )
        if create_resp.status_code in (200, 201):
            folder_id = create_resp.json().get('id')
            logger.info(f"Created Google Drive subfolder: {folder_name} (ID: {folder_id})")
            _FOLDER_CACHE[cache_key] = folder_id
            return folder_id
        else:
            logger.error(f"Failed to create drive subfolder '{folder_name}': {create_resp.status_code} {create_resp.text}")
            return None

    except Exception as e:
        logger.error(f"Error getting/creating Drive folder '{folder_name}': {e}")
        return None


def _resolve_target_folder(relative_path: str, token: str) -> Tuple[Optional[str], str]:
    """Resolves folder hierarchy on Google Drive based on relative path."""
    root_id = (os.getenv('GDRIVE_FOLDER_ID') or '').strip()
    if not root_id:
        return None, os.path.basename(relative_path)

    clean_path = relative_path.replace('\\', '/').strip('/')
    parts = clean_path.split('/')
    filename = parts[-1]
    folder_parts = parts[:-1]

    current_parent = root_id
    for folder_name in folder_parts:
        current_parent = _get_or_create_folder(folder_name, current_parent, token)
        if not current_parent:
            return None, filename

    return current_parent, filename


def get_local_instance_path(relative_path: str) -> str:
    """
    Returns absolute path inside instance/uploads for a given relative path.
    Example: 'processed/user_5/37.pkl' -> 'D:/.../instance/uploads/processed/user_5/37.pkl'
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    clean_rel = (relative_path or '').replace('\\', '/').lstrip('/')
    if clean_rel.startswith('uploads/'):
        clean_rel = clean_rel[len('uploads/'):]
    return os.path.normpath(os.path.join(base_dir, 'instance', 'uploads', clean_rel))


def _save_to_local_instance(local_filepath_or_bytes, relative_path: str) -> Optional[str]:
    """
    Saves file bytes or source file directly to the local instance/uploads folder
    immediately without any delay.
    """
    if not relative_path:
        return None
    try:
        target_path = get_local_instance_path(relative_path)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        if isinstance(local_filepath_or_bytes, (str, os.PathLike)):
            if os.path.exists(local_filepath_or_bytes):
                if os.path.abspath(local_filepath_or_bytes) != os.path.abspath(target_path):
                    shutil.copy2(local_filepath_or_bytes, target_path)
            else:
                logger.error(f"[LOCAL STORAGE FALLBACK] Source file does not exist: {local_filepath_or_bytes}")
                return None
        elif isinstance(local_filepath_or_bytes, bytes):
            with open(target_path, 'wb') as f:
                f.write(local_filepath_or_bytes)
        elif hasattr(local_filepath_or_bytes, 'read'):
            try:
                local_filepath_or_bytes.seek(0)
            except Exception:
                pass
            content = local_filepath_or_bytes.read()
            with open(target_path, 'wb') as f:
                f.write(content)
        else:
            return None

        logger.info(f"[LOCAL STORAGE FALLBACK SUCCESS] Saved file to instance folder without delay: {target_path}")
        return target_path
    except Exception as e:
        logger.error(f"[LOCAL STORAGE FALLBACK ERROR] Failed to write {relative_path} locally: {e}")
        return None


def upload_to_drive(local_filepath_or_bytes, relative_path: str, mime_type: Optional[str] = None) -> Optional[str]:
    """
    Uploads a local file or bytes object to Google Drive.
    Guarantees the file is stored in local instance/uploads as a fallback without delay if Drive fails or times out.
    """
    # 1. ALWAYS guarantee local instance storage first without delay
    _save_to_local_instance(local_filepath_or_bytes, relative_path)

    root_id = (os.getenv('GDRIVE_FOLDER_ID') or '').strip()
    if not root_id:
        logger.warning(f"GDRIVE_FOLDER_ID not set. Saved {relative_path} locally in instance folder.")
        return None

    token = _get_access_token()
    if not token:
        logger.warning(f"Could not authenticate Drive token. Saved {relative_path} locally in instance folder.")
        return None

    try:
        folder_id, filename = _resolve_target_folder(relative_path, token)
        if not folder_id:
            logger.error(f"Could not resolve target drive folder for {relative_path}. File stored in local instance folder.")
            return None

        # Check existing file with fast timeout (4 sec connect, 10 sec read)
        query = f"'{folder_id}' in parents and name = '{filename}' and trashed = false"
        search_resp = requests.get(
            "https://www.googleapis.com/drive/v3/files",
            headers=_get_headers(token),
            params={
                "q": query,
                "fields": "files(id, name)",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true"
            },
            timeout=(4, 10)
        )

        existing_id = None
        if search_resp.status_code == 200:
            files = search_resp.json().get('files', [])
            if files:
                existing_id = files[0]['id']

        # Prepare payload content
        if isinstance(local_filepath_or_bytes, (str, os.PathLike)):
            if not os.path.exists(local_filepath_or_bytes):
                logger.error(f"Local file does not exist for upload: {local_filepath_or_bytes}")
                return None
            with open(local_filepath_or_bytes, 'rb') as f:
                content_bytes = f.read()
        elif isinstance(local_filepath_or_bytes, bytes):
            content_bytes = local_filepath_or_bytes
        elif hasattr(local_filepath_or_bytes, 'read'):
            try:
                local_filepath_or_bytes.seek(0)
            except Exception:
                pass
            content_bytes = local_filepath_or_bytes.read()
        else:
            logger.error(f"Unsupported payload type for upload: {type(local_filepath_or_bytes)}")
            return None

        file_mime = mime_type or 'application/octet-stream'

        if existing_id:
            # Update existing file content
            upload_url = f"https://www.googleapis.com/upload/drive/v3/files/{existing_id}?uploadType=media&supportsAllDrives=true"
            resp = requests.patch(
                upload_url,
                headers={
                    **_get_headers(token),
                    "Content-Type": file_mime
                },
                data=content_bytes,
                timeout=(4, 15)
            )
            if resp.status_code in (200, 201):
                logger.info(f"Updated file on Google Drive: {relative_path} (ID: {existing_id})")
                return existing_id
            else:
                _handle_api_error(resp, relative_path)
                return None
        else:
            # Create new file via multipart upload
            upload_url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true"
            metadata = {
                "name": filename,
                "parents": [folder_id]
            }

            files_payload = {
                'data': ('metadata', json.dumps(metadata), 'application/json; charset=UTF-8'),
                'file': (filename, content_bytes, file_mime)
            }

            resp = requests.post(
                upload_url,
                headers=_get_headers(token),
                files=files_payload,
                timeout=(4, 15)
            )

            if resp.status_code in (200, 201):
                file_id = resp.json().get('id')
                logger.info(f"Uploaded file to Google Drive: {relative_path} (ID: {file_id})")
                return file_id
            else:
                _handle_api_error(resp, relative_path)
                return None

    except Exception as e:
        logger.error(f"Error uploading {relative_path} to Google Drive ({e}). File safely stored in local instance folder.")
        return None


def _handle_api_error(resp, relative_path: str):
    """Parses and logs friendly Google Drive API error messages."""
    text = resp.text
    if "storageQuotaExceeded" in text or "403" in str(resp.status_code):
        logger.warning(
            f"[GDRIVE 403 QUOTA EXCEEDED] Could not upload '{relative_path}' using Service Account on personal Gmail Drive. "
            f"Personal Gmail accounts give 0 MB quota to Service Accounts. "
            f"Fix: Run 'python get_gdrive_refresh_token.py' once to generate your 15GB OAuth Refresh Token."
        )
    else:
        logger.error(f"Google Drive API error uploading {relative_path} ({resp.status_code}): {text}")


def download_from_drive(relative_path: str, destination_filepath: str) -> bool:
    """Downloads a file from Google Drive to local destination_filepath if missing."""
    # Check if local instance storage already has the file
    local_instance_path = get_local_instance_path(relative_path)
    if os.path.exists(local_instance_path) and os.path.getsize(local_instance_path) > 0:
        try:
            if os.path.abspath(local_instance_path) != os.path.abspath(destination_filepath):
                os.makedirs(os.path.dirname(destination_filepath), exist_ok=True)
                shutil.copy2(local_instance_path, destination_filepath)
            return True
        except Exception as e:
            logger.warning(f"Error copying from local instance path to '{destination_filepath}': {e}")

    token = _get_access_token()
    if not token:
        return False

    try:
        folder_id, filename = _resolve_target_folder(relative_path, token)
        if not folder_id:
            return False

        query = f"'{folder_id}' in parents and name = '{filename}' and trashed = false"
        search_resp = requests.get(
            "https://www.googleapis.com/drive/v3/files",
            headers=_get_headers(token),
            params={
                "q": query,
                "fields": "files(id, name)",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true"
            },
            timeout=(4, 10)
        )

        if search_resp.status_code != 200:
            return False

        files = search_resp.json().get('files', [])
        if not files:
            logger.warning(f"File not found on Google Drive: {relative_path}")
            return False

        file_id = files[0]['id']
        os.makedirs(os.path.dirname(destination_filepath), exist_ok=True)

        download_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&supportsAllDrives=true"
        dl_resp = requests.get(download_url, headers=_get_headers(token), stream=True, timeout=(4, 15))

        if dl_resp.status_code == 200:
            with open(destination_filepath, 'wb') as f:
                for chunk in dl_resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
            _save_to_local_instance(destination_filepath, relative_path)
            logger.info(f"Successfully downloaded file from Google Drive to local path: {destination_filepath}")
            return True
        else:
            logger.error(f"Failed to download {relative_path} from Drive ({dl_resp.status_code}): {dl_resp.text}")
            return False

    except Exception as e:
        logger.error(f"Error downloading {relative_path} from Google Drive: {e}")
        return False


def get_file_bytes(relative_path: str) -> Optional[bytes]:
    """
    Returns raw file bytes. Checks local instance/uploads folder first.
    If missing locally, downloads from Google Drive and caches to instance folder.
    """
    if not relative_path:
        return None

    # 1. Fast path: check local instance storage first
    local_path = get_local_instance_path(relative_path)
    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        try:
            with open(local_path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Error reading local instance file '{local_path}': {e}")

    # 2. Fallback: fetch from Google Drive
    token = _get_access_token()
    if not token:
        return None

    try:
        folder_id, filename = _resolve_target_folder(relative_path, token)
        if not folder_id:
            return None

        query = f"'{folder_id}' in parents and name = '{filename}' and trashed = false"
        search_resp = requests.get(
            "https://www.googleapis.com/drive/v3/files",
            headers=_get_headers(token),
            params={
                "q": query,
                "fields": "files(id, name)",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true"
            },
            timeout=(4, 10)
        )

        if search_resp.status_code != 200:
            return None

        files = search_resp.json().get('files', [])
        if not files:
            return None

        file_id = files[0]['id']
        download_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&supportsAllDrives=true"
        dl_resp = requests.get(download_url, headers=_get_headers(token), timeout=(4, 15))

        if dl_resp.status_code == 200:
            content_bytes = dl_resp.content
            # Cache bytes to local instance folder for future zero-delay access
            _save_to_local_instance(content_bytes, relative_path)
            return content_bytes
        else:
            logger.error(f"Failed to fetch file bytes for {relative_path} from Drive ({dl_resp.status_code}): {dl_resp.text}")
            return None

    except Exception as e:
        logger.error(f"Error fetching file bytes for {relative_path} from Google Drive: {e}")
        return None



def ensure_local_file(relative_path: str, local_filepath: str) -> bool:
    """Ensures that a file exists at local_filepath."""
    if os.path.exists(local_filepath) and os.path.getsize(local_filepath) > 0:
        return True
    return download_from_drive(relative_path, local_filepath)


def delete_from_drive(relative_path: str) -> bool:
    """Deletes a file from Google Drive matching relative_path."""
    token = _get_access_token()
    if not token:
        return False

    try:
        folder_id, filename = _resolve_target_folder(relative_path, token)
        if not folder_id:
            return False

        query = f"'{folder_id}' in parents and name = '{filename}' and trashed = false"
        search_resp = requests.get(
            "https://www.googleapis.com/drive/v3/files",
            headers=_get_headers(token),
            params={
                "q": query,
                "fields": "files(id, name)",
                "supportsAllDrives": "true"
            },
            timeout=12
        )

        if search_resp.status_code != 200:
            return False

        files = search_resp.json().get('files', [])
        for f in files:
            del_url = f"https://www.googleapis.com/drive/v3/files/{f['id']}?supportsAllDrives=true"
            requests.delete(del_url, headers=_get_headers(token), timeout=10)
            logger.info(f"Deleted file from Google Drive: {relative_path} (ID: {f['id']})")
        return True

    except Exception as e:
        logger.error(f"Error deleting {relative_path} from Google Drive: {e}")
        return False


_CLEANUP_THREAD_STARTED = False


def cleanup_local_expired_files(retention_days: Optional[int] = None) -> int:
    """
    Scans local instance/uploads folder and deletes any dataset/cache files
    modified more than `retention_days` ago (default 30 days or GDRIVE_RETENTION_DAYS in .env).
    Returns count of local files purged.
    """
    if retention_days is None:
        try:
            retention_days = int(os.getenv('GDRIVE_RETENTION_DAYS', '30'))
        except (ValueError, TypeError):
            retention_days = 30

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    uploads_dir = os.path.normpath(os.path.join(base_dir, 'instance', 'uploads'))
    if not os.path.exists(uploads_dir):
        return 0

    cutoff_time = time.time() - (retention_days * 86400)
    deleted_count = 0

    try:
        for root, dirs, files in os.walk(uploads_dir):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    file_mtime = os.path.getmtime(file_path)
                    if file_mtime < cutoff_time:
                        os.remove(file_path)
                        deleted_count += 1
                        logger.info(f"[LOCAL RETENTION CLEANUP] Auto-deleted expired local file (>{retention_days} days old): {file_path}")
                except Exception as fe:
                    logger.error(f"Error removing expired local file '{file_path}': {fe}")

        # Clean empty subfolders if any
        for root, dirs, files in os.walk(uploads_dir, topdown=False):
            for d in dirs:
                dir_path = os.path.join(root, d)
                try:
                    if not os.listdir(dir_path):
                        os.rmdir(dir_path)
                except Exception:
                    pass

        if deleted_count > 0:
            logger.info(f"[LOCAL RETENTION SUMMARY] Auto-purged {deleted_count} local files older than {retention_days} days from instance/uploads.")
        return deleted_count

    except Exception as e:
        logger.error(f"Error during local retention cleanup: {e}")
        return 0


def cleanup_expired_files(retention_days: Optional[int] = None) -> int:
    """
    Deletes dataset/cache/attachment files older than `retention_days` from both
    local instance/uploads storage and Google Drive.
    Returns count of total files purged.
    """
    if retention_days is None:
        try:
            retention_days = int(os.getenv('GDRIVE_RETENTION_DAYS', '30'))
        except (ValueError, TypeError):
            retention_days = 30

    # 1. Purge expired local files first
    local_deleted = cleanup_local_expired_files(retention_days)
    drive_deleted = 0

    token = _get_access_token()
    root_id = (os.getenv('GDRIVE_FOLDER_ID') or '').strip()

    if token and root_id:
        try:
            from datetime import datetime, timezone, timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
            cutoff_iso = cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')

            query = f"trashed = false and createdTime < '{cutoff_iso}' and mimeType != 'application/vnd.google-apps.folder'"
            url = "https://www.googleapis.com/drive/v3/files"
            params = {
                "q": query,
                "fields": "files(id, name, createdTime)",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
                "pageSize": 100
            }

            resp = requests.get(url, headers=_get_headers(token), params=params, timeout=20)
            if resp.status_code == 200:
                files = resp.json().get('files', [])
                for f in files:
                    file_id = f.get('id')
                    file_name = f.get('name')
                    del_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?supportsAllDrives=true"
                    del_resp = requests.delete(del_url, headers=_get_headers(token), timeout=15)
                    if del_resp.status_code in (200, 204):
                        drive_deleted += 1
                        logger.info(f"[GDRIVE RETENTION] Auto-deleted expired file from Drive (>{retention_days} days old): {file_name} (ID: {file_id})")

            if drive_deleted > 0:
                logger.info(f"[GDRIVE RETENTION SUMMARY] Auto-purged {drive_deleted} Drive files older than {retention_days} days.")

        except Exception as e:
            logger.error(f"Error during Google Drive retention cleanup: {e}")

    return local_deleted + drive_deleted


def start_background_retention_cleanup():
    """Starts a background daemon thread that runs retention cleanup periodically."""
    global _CLEANUP_THREAD_STARTED
    if _CLEANUP_THREAD_STARTED:
        return
    _CLEANUP_THREAD_STARTED = True

    def _worker():
        time.sleep(10)
        while True:
            try:
                cleanup_expired_files()
            except Exception as e:
                logger.error(f"Background retention worker error: {e}")
            time.sleep(12 * 3600)

    t = threading.Thread(target=_worker, daemon=True, name="RetentionCleanupWorker")
    t.start()

