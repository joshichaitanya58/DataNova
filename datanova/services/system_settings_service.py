"""
DataNova Production-Ready System Settings Service
Handles persistent storage of system settings in MySQL Database,
ensuring multi-process, multi-node, containerized, and serverless compatibility.
"""

import os
import json
import logging
from database.db_connector import get_db_connection

logger = logging.getLogger(__name__)


def _parse_setting_value(val_str: str):
    """Converts string values stored in DB back to appropriate python types (bool, int, float, dict, list)."""
    if val_str is None:
        return None
    val_clean = str(val_str).strip()
    if val_clean.lower() == 'true':
        return True
    if val_clean.lower() == 'false':
        return False
    
    try:
        if val_clean.isdigit() or (val_clean.startswith('-') and val_clean[1:].isdigit()):
            return int(val_clean)
        return float(val_clean)
    except ValueError:
        pass

    if (val_clean.startswith('{') and val_clean.endswith('}')) or (val_clean.startswith('[') and val_clean.endswith(']')):
        try:
            return json.loads(val_clean)
        except Exception:
            pass

    return val_str


def get_system_settings_from_db():
    """
    Reads key-value system settings directly from MySQL `system_settings` table.
    Returns a dict of parsed settings or empty dict if DB is unreachable.
    """
    conn = get_db_connection(raise_on_error=False)
    if not conn:
        return {}

    settings = {}
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT setting_key, setting_value FROM system_settings")
            rows = cursor.fetchall() or []
            for row in rows:
                key = row.get('setting_key')
                raw_val = row.get('setting_value')
                if key:
                    settings[key] = _parse_setting_value(raw_val)
    except Exception as e:
        logger.warning(f"Could not load system_settings from MySQL database: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return settings


def save_system_settings_to_db(settings_dict: dict, instance_path: str = None):
    """
    Persists settings dictionary strictly into MySQL `system_settings` table (upsert).
    Does NOT create or write to any local JSON file.
    """
    if not isinstance(settings_dict, dict):
        return False

    # 1. Save strictly to MySQL Database
    conn = get_db_connection(raise_on_error=False)
    if conn:
        try:
            with conn.cursor() as cursor:
                for key, val in settings_dict.items():
                    if isinstance(val, (dict, list)):
                        str_val = json.dumps(val)
                    elif isinstance(val, bool):
                        str_val = 'true' if val else 'false'
                    else:
                        str_val = str(val) if val is not None else ''

                    cursor.execute(
                        """
                        INSERT INTO system_settings (setting_key, setting_value)
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
                        """,
                        (str(key), str_val)
                    )
            conn.commit()
            logger.info("Successfully persisted system settings to MySQL database.")
        except Exception as e:
            logger.error(f"Error saving system settings to MySQL database: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # 2. Cleanup old system_settings.json if it exists on disk
    if instance_path:
        try:
            settings_file = os.path.join(instance_path, 'system_settings.json')
            if os.path.exists(settings_file):
                os.remove(settings_file)
        except Exception as e:
            logger.warning(f"Note: Could not remove old settings file: {e}")

    return True


def load_merged_system_settings(default_settings: dict, instance_path: str = None) -> dict:
    """
    Loads system settings strictly from MySQL DB (`system_settings` table),
    falling back to code defaults if DB is unavailable.
    Does NOT read from any local JSON file.
    """
    merged = default_settings.copy()

    # Load from MySQL Database settings (overrides default dictionary)
    db_settings = get_system_settings_from_db()
    if db_settings:
        merged.update(db_settings)

    # Cleanup old system_settings.json if it exists on disk
    if instance_path:
        try:
            settings_file = os.path.join(instance_path, 'system_settings.json')
            if os.path.exists(settings_file):
                os.remove(settings_file)
        except Exception:
            pass

    return merged

