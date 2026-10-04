import hashlib
import secrets
import logging
import time
import json
import threading
import hmac
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from database.db_connector import get_db_connection

logger = logging.getLogger(__name__)

ALL_SCOPES = [
    "datasets:read",
    "datasets:write",
    "analysis:read",
    "analysis:execute",
    "ml:execute",
    "reports:read"
]


def hash_api_key(raw_key: str) -> str:
    """Computes a secure SHA-256 hash of an API key token."""
    if not raw_key:
        return ""
    return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()


def mask_api_key(raw_key: str) -> str:
    """Returns a masked representation of an API key (e.g. dn_live_...a8f2)."""
    if not raw_key or len(raw_key) < 12:
        return "dn_live_..."
    prefix = raw_key[:8]
    suffix = raw_key[-4:]
    return f"{prefix}...{suffix}"


def generate_api_key_token(environment: str = 'live') -> Tuple[str, str, str]:
    """
    Generates a secure 32-character hex API key token.
    Prefixes: 'dn_live_' or 'dn_test_'.
    Returns: (raw_key, key_hash, masked_key)
    """
    env_clean = 'test' if environment.lower() == 'test' else 'live'
    prefix = f"dn_{env_clean}_"
    random_hex = secrets.token_hex(16)
    raw_key = f"{prefix}{random_hex}"
    key_hash = hash_api_key(raw_key)
    masked_key = mask_api_key(raw_key)
    return raw_key, key_hash, masked_key


def get_or_create_api_key(user_id: int, conn=None) -> str:
    """
    Fetches user's active raw API key from users table or developer_api_keys,
    or generates a new unique key if absent. Returns the full raw API key.
    """
    if not user_id:
        return ""

    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    raw_val = ""
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT api_key FROM users WHERE id = %s", (user_id,))
                u_row = cursor.fetchone()
                
                cursor.execute("SELECT id FROM developer_api_keys WHERE user_id = %s", (user_id,))
                has_key_record = cursor.fetchone()

                if u_row and u_row.get('api_key'):
                    raw_val = u_row['api_key']
                    if not has_key_record:
                        khash = hash_api_key(raw_val)
                        env = 'test' if raw_val.startswith('dn_test_') else 'live'
                        prefix = f"dn_{env}_"
                        last_chars = raw_val[-4:] if len(raw_val) >= 4 else '0000'
                        scopes_str = ",".join(ALL_SCOPES)
                        cursor.execute("""
                            INSERT INTO developer_api_keys (user_id, key_name, key_prefix, key_hash, key_last_chars, environment, scopes, status)
                            VALUES (%s, 'Default Live Key', %s, %s, %s, %s, %s, 'active')
                        """, (user_id, prefix, khash, last_chars, env, scopes_str))
                        conn.commit()
                else:
                    res = create_developer_key(user_id, key_name="Default Live Key", environment="live", conn=conn)
                    raw_val = res.get('raw_key') or res.get('api_key') or ""
        except Exception as e:
            logger.error(f"Error in get_or_create_api_key for user {user_id}: {e}")
        finally:
            if close_conn:
                try:
                    conn.close()
                except Exception:
                    pass

    return raw_val


def create_developer_key(user_id: int, key_name: str = "Default API Key", environment: str = "live", scopes: List[str] = None, conn=None) -> Dict[str, Any]:
    """
    Creates a new production API key for user.
    The raw secret key is returned for user copying,
    and its hash is saved to developer_api_keys while raw_key is saved to users.api_key.
    """
    if not user_id:
        return {'success': False, 'message': 'Invalid user account ID.'}

    if not scopes:
        scopes = ALL_SCOPES.copy()

    scopes_str = ",".join(scopes)
    env_clean = 'test' if environment.lower() == 'test' else 'live'
    raw_key, key_hash, masked_key = generate_api_key_token(env_clean)
    last_chars = raw_key[-4:]
    prefix = f"dn_{env_clean}_"

    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO developer_api_keys (user_id, key_name, key_prefix, key_hash, key_last_chars, environment, scopes, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'active')
                """, (user_id, key_name, prefix, key_hash, last_chars, env_clean, scopes_str))
                key_id = cursor.lastrowid
                cursor.execute("UPDATE users SET api_key = %s WHERE id = %s", (raw_key, user_id))
                conn.commit()

            return {
                'success': True,
                'key_id': key_id,
                'raw_key': raw_key,
                'api_key': raw_key,
                'secret_key': raw_key,
                'masked_key': masked_key,
                'key_name': key_name,
                'environment': env_clean,
                'scopes': scopes,
                'message': 'API Key generated successfully! Please store this key safely.'
            }
        except Exception as e:
            logger.error(f"Error creating developer key for user {user_id}: {e}")
            return {'success': False, 'message': f'Failed to create API key: {str(e)}'}
        finally:
            if close_conn:
                try:
                    conn.close()
                except Exception:
                    pass

    return {'success': False, 'message': 'Database connection error.'}


def list_developer_api_keys(user_id: int, conn=None) -> List[Dict[str, Any]]:
    """Lists all active and revoked API keys for a developer."""
    if not user_id:
        return []

    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    keys = []
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, key_name, key_prefix, key_last_chars, environment, scopes, status, last_used_at, created_at
                    FROM developer_api_keys
                    WHERE user_id = %s
                    ORDER BY id DESC
                """, (user_id,))
                rows = cursor.fetchall() or []
                for r in rows:
                    last_used_str = r['last_used_at'].strftime('%Y-%m-%d %H:%M:%S') if r.get('last_used_at') else 'Never'
                    created_str = r['created_at'].strftime('%Y-%m-%d %H:%M:%S') if r.get('created_at') else 'Recent'
                    scope_list = [s.strip() for s in r.get('scopes', '').split(',') if s.strip()]
                    masked = f"{r.get('key_prefix', 'dn_live_')}...{r.get('key_last_chars', '')}"
                    keys.append({
                        'id': r['id'],
                        'key_name': r['key_name'],
                        'masked_key': masked,
                        'environment': r['environment'],
                        'scopes': scope_list,
                        'status': r['status'],
                        'last_used_at': last_used_str,
                        'created_at': created_str
                    })
        except Exception as e:
            logger.error(f"Error listing API keys for user {user_id}: {e}")
        finally:
            if close_conn:
                try:
                    conn.close()
                except Exception:
                    pass

    return keys


def revoke_developer_key(user_id: int, key_id: int, conn=None) -> Dict[str, Any]:
    """Revokes a specific API key."""
    if not user_id or not key_id:
        return {'success': False, 'message': 'Invalid parameters.'}

    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE developer_api_keys SET status = 'revoked' WHERE id = %s AND user_id = %s
                """, (key_id, user_id))
                conn.commit()
            return {'success': True, 'message': 'API Key successfully revoked.'}
        except Exception as e:
            logger.error(f"Error revoking API key {key_id}: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if close_conn:
                try:
                    conn.close()
                except Exception:
                    pass

    return {'success': False, 'message': 'Database connection error.'}


def generate_new_api_key(user_id: int, conn=None) -> Dict[str, Any]:
    """
    Revokes current active key(s) for user and generates a new live key.
    """
    if not user_id:
        return {'success': False, 'message': 'Invalid user account.'}

    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE developer_api_keys SET status = 'revoked' WHERE user_id = %s AND status = 'active'
                """, (user_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error revoking previous keys for user {user_id}: {e}")

    res = create_developer_key(user_id, key_name="Regenerated Live Key", environment="live", conn=conn)

    if close_conn and conn:
        try:
            conn.close()
        except Exception:
            pass

    return res


def verify_api_key(raw_key: str, required_scope: Optional[str] = None, conn=None) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[str]]:
    """
    Verifies an incoming raw API key against hashed stored keys in database.
    Checks status='active' and enforces required_scope if provided.
    Returns: (user_dict, key_dict, error_message)
    """
    if not raw_key:
        return None, None, "Missing API authentication key."

    raw_key = raw_key.strip().strip('"\'')
    khash = hash_api_key(raw_key)

    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    if not conn:
        return None, None, "Database connection failed during API key verification."

    try:
        with conn.cursor() as cursor:
            # 1. Look up active key in developer_api_keys by key_hash
            cursor.execute("""
                SELECT k.id as key_id, k.user_id, k.key_name, k.environment, k.scopes, k.status,
                       u.id, u.first_name, u.last_name, u.email, u.role, u.organization, u.status as user_status
                FROM developer_api_keys k
                JOIN users u ON k.user_id = u.id
                WHERE k.key_hash = %s AND k.status = 'active'
            """, (khash,))
            row = cursor.fetchone()

            if not row:
                # 2. Check if users table has this exact key as current active api_key
                cursor.execute("""
                    SELECT id, first_name, last_name, email, role, organization, status as user_status
                    FROM users WHERE api_key = %s
                """, (raw_key,))
                u_row = cursor.fetchone()
                if u_row:
                    if u_row.get('user_status') != 'active':
                        return None, None, "Associated user account is deactivated."
                    # Sync / activate key record in developer_api_keys
                    cursor.execute("SELECT id FROM developer_api_keys WHERE key_hash = %s", (khash,))
                    existing_k = cursor.fetchone()
                    prefix = raw_key[:8] if len(raw_key) >= 8 else 'dn_live_'
                    last_chars = raw_key[-4:] if len(raw_key) >= 4 else '0000'
                    if existing_k:
                        cursor.execute("UPDATE developer_api_keys SET status = 'active' WHERE id = %s", (existing_k['id'],))
                        key_id = existing_k['id']
                    else:
                        cursor.execute("""
                            INSERT INTO developer_api_keys (user_id, key_name, key_prefix, key_hash, key_last_chars, environment, scopes, status)
                            VALUES (%s, 'Active Primary Key', %s, %s, %s, 'live', %s, 'active')
                        """, (u_row['id'], prefix, khash, last_chars, ",".join(ALL_SCOPES)))
                        key_id = cursor.lastrowid
                    conn.commit()
                    key_dict = {
                        'key_id': key_id,
                        'environment': 'live',
                        'scopes': ALL_SCOPES
                    }
                    user_dict = u_row
                    return user_dict, key_dict, None

                # 3. Check if developer_api_keys has a revoked or deactivated record for this key hash
                cursor.execute("""
                    SELECT k.status, u.status as user_status FROM developer_api_keys k
                    JOIN users u ON k.user_id = u.id WHERE k.key_hash = %s
                """, (khash,))
                st_row = cursor.fetchone()
                if st_row:
                    st = str(st_row.get('status', '')).lower()
                    if st == 'revoked':
                        return None, None, "This API key has been revoked and is no longer valid. Please use an active API key from Developer Dashboard."
                    elif st == 'expired':
                        return None, None, "This API key has expired."
                    elif st != 'active':
                        return None, None, "This API key has been deactivated."
                return None, None, "Invalid or unauthorized API key."

            key_status = str(row.get('status', '')).lower()
            if key_status == 'revoked':
                return None, None, "This API key has been revoked and is no longer valid. Please use an active API key from Developer Dashboard."
            elif key_status == 'expired':
                return None, None, "This API key has expired."
            elif key_status != 'active':
                return None, None, "This API key has been deactivated."

            if row.get('user_status') != 'active':
                return None, None, "Associated developer account is deactivated."

            # Verify required scope if specified
            key_scopes = [s.strip() for s in row.get('scopes', '').split(',') if s.strip()]
            if required_scope and required_scope not in key_scopes and "admin" not in key_scopes:
                return None, None, f"API key lacks required scope: '{required_scope}'."

            # Update last_used_at timestamp
            try:
                cursor.execute("UPDATE developer_api_keys SET last_used_at = NOW() WHERE id = %s", (row['key_id'],))
                conn.commit()
            except Exception:
                pass

            user_dict = {
                'id': row['user_id'],
                'first_name': row['first_name'],
                'last_name': row['last_name'],
                'email': row['email'],
                'role': row['role'],
                'organization': row['organization']
            }
            key_dict = {
                'key_id': row['key_id'],
                'key_name': row['key_name'],
                'environment': row['environment'],
                'scopes': key_scopes
            }
            return user_dict, key_dict, None
    except Exception as e:
        logger.error(f"Error verifying API key: {e}")
        return None, None, f"API key validation error: {str(e)}"
    finally:
        if close_conn:
            try:
                conn.close()
            except Exception:
                pass


def log_api_telemetry(user_id: int, endpoint: str, status_code: int = 200, method: str = 'GET',
                      request_id: str = None, api_key_id: int = None, environment: str = 'live',
                      response_time_ms: int = 0, dataset_id: int = None, analysis_id: str = None,
                      error_code: str = None, error_message: str = None, request_params: dict = None,
                      response_summary: dict = None, is_ai_call: bool = False, conn=None):
    """
    Logs structured API telemetry for developer debugging, metrics, and call logs.
    """
    if not user_id:
        return

    if not request_id:
        request_id = f"req_{secrets.token_hex(8)}"

    status_str = str(status_code)
    req_params_str = json.dumps(request_params)[:1000] if request_params else None
    res_summary_str = json.dumps(response_summary)[:1000] if response_summary else None

    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO api_usage_logs
                    (user_id, request_id, api_key_id, environment, endpoint, method, status_code, status,
                     response_time_ms, dataset_id, analysis_id, error_code, error_message, request_params, response_summary, is_ai_call)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id, request_id, api_key_id, environment, endpoint, method, status_code, status_str,
                    response_time_ms, dataset_id, analysis_id, error_code, error_message, req_params_str, res_summary_str, is_ai_call
                ))
                conn.commit()
        except Exception as e:
            logger.warning(f"Error logging API telemetry: {e}")
        finally:
            if close_conn:
                try:
                    conn.close()
                except Exception:
                    pass


def get_available_endpoints() -> List[Dict[str, Any]]:
    """
    Returns the complete structured DataNova REST API Catalog (v1).
    Includes parameters, response schemas, and multi-language code examples.
    """
    return [
        {
            'id': 'v1_health',
            'name': 'API System Health Check',
            'category': 'System',
            'method': 'GET',
            'path': '/api/v1/health',
            'description': 'Returns current operational status of API, database, analysis, and ML engines.',
            'auth_required': False,
            'scope': None,
            'params': [],
            'sample_response': {
                'success': True,
                'request_id': 'req_health_001',
                'status': 'operational',
                'services': {
                    'api': 'operational',
                    'database': 'operational',
                    'analysis_engine': 'operational',
                    'ml_engine': 'operational'
                },
                'timestamp': '2026-09-27T17:34:00Z'
            }
        },
        {
            'id': 'v1_upload_dataset',
            'name': 'Upload Dataset (CSV, Excel)',
            'category': 'Datasets',
            'method': 'POST',
            'path': '/api/v1/datasets/upload',
            'description': 'Uploads a CSV or Excel dataset file, validates schema, and registers dataset metadata.',
            'auth_required': True,
            'scope': 'datasets:write',
            'params': [{'name': 'file', 'type': 'file', 'required': True, 'description': 'Multipart form dataset file'}],
            'sample_response': {
                'success': True,
                'request_id': 'req_up_8f92',
                'data': {
                    'dataset_id': 101,
                    'file_name': 'sales_data_2026.csv',
                    'row_count': 5000,
                    'column_count': 12,
                    'file_size_bytes': 458920,
                    'status': 'uploaded'
                }
            }
        },
        {
            'id': 'v1_list_datasets',
            'name': 'List & Search Datasets',
            'category': 'Datasets',
            'method': 'GET',
            'path': '/api/v1/datasets',
            'description': 'Returns paginated list of uploaded datasets with sorting and search filters.',
            'auth_required': True,
            'scope': 'datasets:read',
            'params': [
                {'name': 'page', 'type': 'integer', 'required': False, 'description': 'Page number (default: 1)'},
                {'name': 'limit', 'type': 'integer', 'required': False, 'description': 'Items per page (default: 20)'},
                {'name': 'search', 'type': 'string', 'required': False, 'description': 'Filter by filename'}
            ],
            'sample_response': {
                'success': True,
                'request_id': 'req_list_102',
                'data': {
                    'datasets': [
                        {'id': 101, 'file_name': 'sales_data.csv', 'row_count': 5000, 'column_count': 12, 'uploaded_at': '2026-09-27 10:00:00'}
                    ],
                    'pagination': {'total': 1, 'page': 1, 'limit': 20, 'pages': 1}
                }
            }
        },
        {
            'id': 'v1_preview_dataset',
            'name': 'Safe Dataset Preview',
            'category': 'Datasets',
            'method': 'GET',
            'path': '/api/v1/datasets/<id>/preview',
            'description': 'Retrieves dataset schema, data types, row/column counts, null counts, and sample records.',
            'auth_required': True,
            'scope': 'datasets:read',
            'params': [{'name': 'id', 'type': 'integer', 'required': True, 'description': 'Dataset ID'}],
            'sample_response': {
                'success': True,
                'request_id': 'req_prev_301',
                'data': {
                    'dataset_id': 101,
                    'file_name': 'sales_data.csv',
                    'row_count': 5000,
                    'column_count': 12,
                    'columns': ['Region', 'Revenue', 'Units'],
                    'dtypes': {'Region': 'object', 'Revenue': 'float64', 'Units': 'int64'},
                    'missing_values': {'Revenue': 12, 'Units': 0},
                    'sample_records': [
                        {'Region': 'North', 'Revenue': 4500.0, 'Units': 22}
                    ]
                }
            }
        },
        {
            'id': 'v1_eda_analysis',
            'name': 'Automated EDA & Statistics',
            'category': 'Analysis',
            'method': 'POST',
            'path': '/api/v1/analysis/eda',
            'description': 'Performs full statistical summary, missing value analysis, duplicate detection, and correlation matrix.',
            'auth_required': True,
            'scope': 'analysis:execute',
            'params': [{'name': 'dataset_id', 'type': 'integer', 'required': True}],
            'sample_response': {
                'success': True,
                'request_id': 'req_eda_401',
                'data': {
                    'dataset_id': 101,
                    'summary': {'rows': 5000, 'columns': 12, 'quality_score': 92.5},
                    'missing_values': {'Revenue': 15},
                    'duplicates': 4,
                    'correlation': {'Revenue': {'Units': 0.87}}
                }
            }
        },
        {
            'id': 'v1_clean_dataset',
            'name': 'Data Cleaning & Preprocessing',
            'category': 'Analysis',
            'method': 'POST',
            'path': '/api/v1/analysis/clean',
            'description': 'Executes automated deduplication, null imputation, and data type normalization.',
            'auth_required': True,
            'scope': 'analysis:execute',
            'params': [{'name': 'dataset_id', 'type': 'integer', 'required': True}],
            'sample_response': {
                'success': True,
                'request_id': 'req_clean_501',
                'data': {
                    'dataset_id': 102,
                    'original_dataset_id': 101,
                    'operations': [{'column': 'Revenue', 'operation': 'median_imputation', 'affected_rows': 15}],
                    'cleaned_rows': 4996,
                    'removed_duplicates': 4
                }
            }
        },
        {
            'id': 'v1_visualizations',
            'name': 'Automatic Visualization Payload',
            'category': 'Analysis',
            'method': 'POST',
            'path': '/api/v1/analysis/visualizations',
            'description': 'Generates intelligent Plotly/Chart.js chart payloads (histograms, scatter, heatmaps) for column types.',
            'auth_required': True,
            'scope': 'analysis:execute',
            'params': [{'name': 'dataset_id', 'type': 'integer', 'required': True}],
            'sample_response': {
                'success': True,
                'request_id': 'req_viz_601',
                'data': {
                    'dataset_id': 101,
                    'charts': [
                        {'chart_id': 'chart_001', 'type': 'histogram', 'title': 'Revenue Distribution', 'data': {}}
                    ]
                }
            }
        },
        {
            'id': 'v1_auto_pipeline',
            'name': 'Complete Auto Analysis Pipeline',
            'category': 'Analysis',
            'method': 'POST',
            'path': '/api/v1/analysis/auto',
            'description': 'Runs complete DataNova pipeline (EDA, Cleaning, Charts, Insights, AutoML Recommendations).',
            'auth_required': True,
            'scope': 'analysis:execute',
            'params': [
                {'name': 'dataset_id', 'type': 'integer', 'required': True}
            ],
            'sample_response': {
                'success': True,
                'request_id': 'req_auto_701',
                'data': {
                    'analysis_id': 'an_8f92ab31',
                    'dataset_id': 101,
                    'status': 'completed',
                    'eda': {'rows': 5000, 'columns': 12},
                    'insights': [{'title': 'Strong Revenue Growth Detected'}],
                    'ml_recommendations': [{'model': 'RandomForestRegressor'}]
                }
            }
        },
        {
            'id': 'v1_ml_classification',
            'name': 'ML Classification Training',
            'category': 'Machine Learning',
            'method': 'POST',
            'path': '/api/v1/ml/classification',
            'description': 'Trains Classification models (RandomForestClassifier, LogisticRegression) with accuracy/F1 evaluation.',
            'auth_required': True,
            'scope': 'ml:execute',
            'params': [
                {'name': 'dataset_id', 'type': 'integer', 'required': True},
                {'name': 'target_column', 'type': 'string', 'required': False}
            ],
            'sample_response': {
                'success': True,
                'request_id': 'req_ml_c101',
                'data': {
                    'model_id': 'model_101_classification',
                    'model_name': 'RandomForestClassifier',
                    'metrics': {'accuracy': 0.945, 'precision': 0.938, 'f1_score': 0.941},
                    'feature_importance': {'Price': 0.58, 'Qty': 0.42}
                }
            }
        },
        {
            'id': 'v1_ml_regression',
            'name': 'ML Regression Training',
            'category': 'Machine Learning',
            'method': 'POST',
            'path': '/api/v1/ml/regression',
            'description': 'Trains Regression models (RandomForestRegressor, LinearRegression) with R2/RMSE evaluation.',
            'auth_required': True,
            'scope': 'ml:execute',
            'params': [
                {'name': 'dataset_id', 'type': 'integer', 'required': True},
                {'name': 'target_column', 'type': 'string', 'required': False}
            ],
            'sample_response': {
                'success': True,
                'request_id': 'req_ml_r101',
                'data': {
                    'model_id': 'model_101_regression',
                    'model_name': 'RandomForestRegressor',
                    'metrics': {'r2_score': 0.912, 'rmse': 18.4, 'mae': 12.1},
                    'feature_importance': {'Units': 0.65, 'Price': 0.35}
                }
            }
        },
        {
            'id': 'v1_analysis_code',
            'name': 'Get Generated Analysis Code',
            'category': 'Code & Export',
            'method': 'GET',
            'path': '/api/v1/analysis/<id>/code',
            'description': 'Returns auto-generated Python Pandas/Seaborn script for reproducible local execution.',
            'auth_required': True,
            'scope': 'reports:read',
            'params': [{'name': 'id', 'type': 'integer', 'required': True}],
            'sample_response': {
                'success': True,
                'request_id': 'req_code_1001',
                'data': {
                    'dataset_id': 101,
                    'language': 'python',
                    'code': 'import pandas as pd\ndf = pd.read_csv("dataset.csv")\n...'
                }
            }
        },
        {
            'id': 'v1_analysis_report',
            'name': 'Get Analysis Executive Report',
            'category': 'Code & Export',
            'method': 'GET',
            'path': '/api/v1/analysis/<id>/report',
            'description': 'Returns executive report JSON containing dataset stats, quality metrics, and AI insights.',
            'auth_required': True,
            'scope': 'reports:read',
            'params': [{'name': 'id', 'type': 'integer', 'required': True}],
            'sample_response': {
                'success': True,
                'request_id': 'req_rep_1101',
                'data': {
                    'dataset_id': 101,
                    'report_name': 'Sales_Analysis_Report',
                    'summary': {'rows': 5000, 'columns': 12}
                }
            }
        },

        {
            'id': 'v1_ask_your_data',
            'name': 'Ask Your Data Natural Language Q&A',
            'category': 'Analysis',
            'method': 'POST',
            'path': '/api/v1/ask',
            'description': 'Natural Language Query endpoint for interactive data questions.',
            'auth_required': True,
            'scope': 'analysis:execute',
            'params': [{'name': 'dataset_id', 'type': 'integer', 'required': True}, {'name': 'question', 'type': 'string', 'required': True}],
            'sample_response': {'success': True, 'question': 'Top product?', 'answer': 'Calculated top item is Product A.'}
        },
        {
            'id': 'v1_ml_clustering',
            'name': 'ML K-Means Clustering',
            'category': 'Machine Learning',
            'method': 'POST',
            'path': '/api/v1/ml/clustering',
            'description': 'Runs K-Means clustering model segmentation on numerical dataset features.',
            'auth_required': True,
            'scope': 'ml:execute',
            'params': [{'name': 'dataset_id', 'type': 'integer', 'required': True}, {'name': 'n_clusters', 'type': 'integer', 'required': False}],
            'sample_response': {'success': True, 'model_name': 'KMeans(n_clusters=3)', 'metrics': {'silhouette_score': 0.68}}
        },
        {
            'id': 'v1_openapi',
            'name': 'OpenAPI 3.0 Specification',
            'category': 'System',
            'method': 'GET',
            'path': '/api/v1/openapi.json',
            'description': 'Returns raw OpenAPI 3.0 JSON schema specification for Swagger UI or Postman.',
            'auth_required': False,
            'scope': None,
            'params': [],
            'sample_response': {'openapi': '3.0.3', 'info': {'title': 'DataNova API', 'version': '1.0.0'}}
        }
    ]


def get_developer_dashboard_analytics(user_id: int, conn=None) -> Dict[str, Any]:
    """
    Compiles full developer dashboard telemetry, API key management data,
    accurate call statistics, and recent detailed log inspection.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    active_key_masked = get_or_create_api_key(user_id, conn)
    keys_list = list_developer_api_keys(user_id, conn)

    total_api_calls = 0
    successful_calls = 0
    failed_calls = 0
    ai_calls = 0
    requests_today = 0
    recent_logs = []
    failed_logs = []
    daily_usage = {'labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], 'values': [0, 0, 0, 0, 0, 0, 0]}

    if conn and user_id:
        try:
            with conn.cursor() as cursor:
                # 1. Total API Calls count
                cursor.execute("SELECT COUNT(*) as count FROM api_usage_logs WHERE user_id = %s", (user_id,))
                row = cursor.fetchone()
                total_api_calls = row['count'] if row else 0

                # 2. Successful API Calls count (status starts with 2 or 'success')
                cursor.execute("""
                    SELECT COUNT(*) as count FROM api_usage_logs
                    WHERE user_id = %s AND (status_code BETWEEN 200 AND 299 OR status = 'success' OR status LIKE '2%%')
                """, (user_id,))
                row_s = cursor.fetchone()
                successful_calls = row_s['count'] if row_s else 0

                # 3. Failed Calls count
                cursor.execute("""
                    SELECT COUNT(*) as count FROM api_usage_logs
                    WHERE user_id = %s AND (status_code >= 400 OR status = 'failure' OR status LIKE '4%%' OR status LIKE '5%%')
                """, (user_id,))
                row_f = cursor.fetchone()
                failed_calls = row_f['count'] if row_f else 0

                # 4. Requests Today
                cursor.execute("""
                    SELECT COUNT(*) as count FROM api_usage_logs
                    WHERE user_id = %s AND DATE(called_at) = CURDATE()
                """, (user_id,))
                row_t = cursor.fetchone()
                requests_today = row_t['count'] if row_t else 0

                # 5. AI specific calls count
                cursor.execute("""
                    SELECT COUNT(*) as count FROM api_usage_logs WHERE user_id = %s AND is_ai_call = TRUE
                """, (user_id,))
                row_ai = cursor.fetchone()
                ai_calls = row_ai['count'] if row_ai else 0

                # 5b. Monthly API Calls count (current calendar month)
                cursor.execute("""
                    SELECT COUNT(*) as count FROM api_usage_logs
                    WHERE user_id = %s AND YEAR(called_at) = YEAR(CURDATE()) AND MONTH(called_at) = MONTH(CURDATE())
                """, (user_id,))
                row_m = cursor.fetchone()
                monthly_calls = row_m['count'] if row_m else 0

                # 6. Fetch recent 20 detailed API usage logs
                cursor.execute("""
                    SELECT id, request_id, endpoint, method, status_code, status, response_time_ms,
                           dataset_id, error_code, error_message, request_params, response_summary, is_ai_call, called_at
                    FROM api_usage_logs
                    WHERE user_id = %s
                    ORDER BY called_at DESC LIMIT 20
                """, (user_id,))
                logs_rows = cursor.fetchall() or []
                for l in logs_rows:
                    dt_str = l['called_at'].strftime('%Y-%m-%d %H:%M:%S') if l.get('called_at') else 'Recent'
                    req_id = l.get('request_id') or f"req_{l['id']}"
                    st_code = l.get('status_code') or (200 if (l.get('status') == 'success' or '20' in str(l.get('status'))) else 400)
                    log_item = {
                        'id': l['id'],
                        'request_id': req_id,
                        'endpoint': l['endpoint'],
                        'method': l.get('method') or 'GET',
                        'status_code': st_code,
                        'status': l['status'],
                        'response_time_ms': l.get('response_time_ms') or 45,
                        'dataset_id': l.get('dataset_id'),
                        'error_code': l.get('error_code'),
                        'error_message': l.get('error_message'),
                        'request_params': l.get('request_params'),
                        'response_summary': l.get('response_summary'),
                        'is_ai': bool(l.get('is_ai_call')),
                        'called_at': dt_str
                    }
                    recent_logs.append(log_item)
                    if st_code >= 400 or l.get('status') == 'failure':
                        failed_logs.append(log_item)
        except Exception as e:
            logger.warning(f"Error fetching API usage analytics for developer {user_id}: {e}")
        finally:
            if close_conn:
                try:
                    conn.close()
                except Exception:
                    pass

    endpoint_counts = {}
    if conn and user_id:
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT endpoint, COUNT(*) as cnt FROM api_usage_logs
                    WHERE user_id = %s
                    GROUP BY endpoint
                """, (user_id,))
                for r in cursor.fetchall() or []:
                    ep_name = r['endpoint']
                    cnt = r['cnt']
                    endpoint_counts[ep_name] = cnt
        except Exception as e:
            logger.warning(f"Error fetching endpoint call counts: {e}")

    success_rate = round((successful_calls / max(1, total_api_calls)) * 100, 1) if total_api_calls > 0 else 100.0
    endpoints = get_available_endpoints()
    monthly_limit = 2000
    remaining_quota = max(0, monthly_limit - monthly_calls)
    for ep in endpoints:
        p = ep.get('path', '')
        base_p = p.split('<')[0].rstrip('/') if '<' in p else p
        c_cnt = sum(cnt for ep_path, cnt in endpoint_counts.items() if ep_path == p or (base_p and ep_path.startswith(base_p)))
        ep['call_count'] = c_cnt
        ep['monthly_limit'] = monthly_limit

    return {
        'api_key': active_key_masked,
        'keys': keys_list,
        'metrics': {
            'total_api_calls': total_api_calls,
            'successful_calls': successful_calls,
            'failed_calls': failed_calls,
            'requests_today': requests_today,
            'monthly_calls': monthly_calls,
            'remaining_quota': remaining_quota,
            'success_rate': success_rate,
            'ai_calls': ai_calls,
            'endpoints_count': len(endpoints),
            'rate_limit': '2,000 / month',
            'monthly_limit': monthly_limit
        },
        'endpoints': endpoints,
        'recent_logs': recent_logs,
        'failed_logs': failed_logs[:10],
        'daily_usage': daily_usage
    }




def get_key_rate_limit_status(key_id: Optional[int] = None, user_id: Optional[int] = None, monthly_limit: int = 2000, per_minute_limit: int = 60, conn=None) -> Dict[str, Any]:
    """
    Computes real, usage-based rate limit status for an API key / user.
    Enforces both monthly quota (2,000 req/month) and burst rate limit (60 req/minute).
    Returns: dict with keys 'allowed', 'is_allowed', 'limit', 'remaining', 'reset', 'retry_after', 'message'
    """
    now = datetime.now()
    if now.month == 12:
        next_month_start = datetime(now.year + 1, 1, 1)
    else:
        next_month_start = datetime(now.year, now.month + 1, 1)
    reset_timestamp = int(next_month_start.timestamp())

    if not user_id and not key_id:
        return {
            'allowed': True,
            'is_allowed': True,
            'limit': monthly_limit,
            'remaining': monthly_limit,
            'reset': reset_timestamp,
            'retry_after': 0,
            'message': 'OK'
        }

    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    monthly_count = 0
    minute_count = 0

    if conn:
        try:
            with conn.cursor() as cursor:
                if key_id:
                    cursor.execute("""
                        SELECT COUNT(*) as cnt FROM api_usage_logs
                        WHERE api_key_id = %s AND YEAR(called_at) = YEAR(CURDATE()) AND MONTH(called_at) = MONTH(CURDATE())
                    """, (key_id,))
                    row = cursor.fetchone()
                    if row:
                        monthly_count = row.get('cnt', 0)

                    cursor.execute("""
                        SELECT COUNT(*) as cnt FROM api_usage_logs
                        WHERE api_key_id = %s AND called_at >= NOW() - INTERVAL 1 MINUTE
                    """, (key_id,))
                    row_min = cursor.fetchone()
                    if row_min:
                        minute_count = row_min.get('cnt', 0)
                else:
                    cursor.execute("""
                        SELECT COUNT(*) as cnt FROM api_usage_logs
                        WHERE user_id = %s AND YEAR(called_at) = YEAR(CURDATE()) AND MONTH(called_at) = MONTH(CURDATE())
                    """, (user_id,))
                    row = cursor.fetchone()
                    if row:
                        monthly_count = row.get('cnt', 0)

                    cursor.execute("""
                        SELECT COUNT(*) as cnt FROM api_usage_logs
                        WHERE user_id = %s AND called_at >= NOW() - INTERVAL 1 MINUTE
                    """, (user_id,))
                    row_min = cursor.fetchone()
                    if row_min:
                        minute_count = row_min.get('cnt', 0)
        except Exception as e:
            logger.warning(f"Error checking rate limit status: {e}")
        finally:
            if close_conn:
                try:
                    conn.close()
                except Exception:
                    pass

    # Check per-minute burst rate limit
    if minute_count >= per_minute_limit:
        return {
            'allowed': False,
            'is_allowed': False,
            'limit': per_minute_limit,
            'remaining': 0,
            'reset': int(time.time() + 10),
            'retry_after': 10,
            'message': f'Burst rate limit exceeded ({per_minute_limit} requests/min). Retrying with exponential backoff...'
        }

    monthly_remaining = max(0, monthly_limit - monthly_count)
    is_allowed = monthly_count < monthly_limit
    retry_after = 0 if is_allowed else max(1, reset_timestamp - int(time.time()))

    return {
        'allowed': is_allowed,
        'is_allowed': is_allowed,
        'limit': monthly_limit,
        'remaining': monthly_remaining,
        'reset': reset_timestamp,
        'retry_after': retry_after,
        'message': 'OK' if is_allowed else f'API monthly rate limit of {monthly_limit} requests per month exceeded.'
    }


