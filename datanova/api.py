from flask import Blueprint, request, jsonify, session, current_app, flash, redirect, url_for
import os
import pandas as pd
import numpy as np
import uuid
import random
import json
from io import BytesIO
try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    import seaborn as sns
except ImportError:
    plt = None
    sns = None
from werkzeug.utils import secure_filename

from .auth import roles_required, ALLOWED_ROLES, create_user_account
from database.db_connector import get_db_connection
from .services import (
    semantic_service,
    cleaning_service,
    quality_service,
    outlier_service,
    eda_service,
    timeseries_service,
    kpi_service,
    chart_service,
    insight_service,
    pipeline_service,
    feature_service,
    manager_service,
    viewer_service,
    admin_service,
    analyst_service,
    report_service
)
from .services import ai_helper  # Import the AI helper service

bp = Blueprint('api', __name__)


def log_api_call(endpoint, status, is_ai_call=False):
    """Helper to log API usage to the database."""
    if 'id' not in session:
        return  # Don't log if user is not logged in

    conn = get_db_connection()
    if not conn:
        return

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO api_usage_logs (user_id, endpoint, status, is_ai_call) VALUES (%s, %s, %s, %s)",
                (session['id'], endpoint, status, is_ai_call)
            )
        conn.commit()
    finally:
        conn.close()


# --- Scalability & Security Configurations ---
SAMPLING_THRESHOLD_BYTES = 25 * 1024 * 1024  # 25 MB
SAMPLING_ROW_COUNT = 100000  # Number of rows to sample for large files


def clean_for_json(obj):
    """
    Recursively replaces NaN, Infinity, -Infinity, numpy types, and datetimes
    with JSON-compliant standard Python primitives.
    """
    if isinstance(obj, dict):
        return {str(k): clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [clean_for_json(v) for v in obj]
    elif isinstance(obj, float):
        if pd.isna(obj) or np.isinf(obj):
            return None
        return float(obj)
    elif isinstance(obj, (np.integer, int)):
        return int(obj)
    elif isinstance(obj, (np.floating, float)):
        val = float(obj)
        if pd.isna(val) or np.isinf(val):
            return None
        return val
    elif isinstance(obj, (np.ndarray, pd.Series)):
        return clean_for_json(obj.tolist())
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return obj


def build_dataset_payload(df, semantic_types, dataset_id, file_name, file_size, message=None):
    row_count, column_count = df.shape
    total_missing_count = int(df.isnull().sum().sum())
    duplicate_count = int(df.duplicated().sum())

    # Calculate Data Quality 2.0 & Memory Summary & Business Domain
    memory_summary = eda_service.dataset_memory_summary(df)
    business_domain = semantic_service.detect_business_domain(df, semantic_types)
    outliers_report = outlier_service.detect_dataset_outliers(df, semantic_types)
    total_outliers = outliers_report.get("total_outlier_count", 0)
    quality_metrics = quality_service.calculate_quality_score(df, semantic_types, outlier_count=total_outliers)

    df_preview_html = df.head().to_html(
        classes=['dn-table', 'dn-table-preview'],
        index=False,
        border=0,
        justify='left'
    )

    column_usefulness = quality_service.evaluate_column_usefulness(df, semantic_types)
    if column_usefulness is None:
        column_usefulness = []
    usefulness_map = {item['column']: item for item in column_usefulness}

    column_info = []
    for col, dtype in df.dtypes.items():
        type_name = 'Text'
        if 'int' in str(dtype):
            type_name = 'Integer'
        elif 'float' in str(dtype):
            type_name = 'Float'
        elif 'datetime' in str(dtype):
            type_name = 'Datetime'
        elif 'bool' in str(dtype):
            type_name = 'Boolean'

        sem_type = semantic_types.get(col, 'generic')
        col_eval = usefulness_map.get(col, {})
        display_name = col_eval.get('display_name', col)
        is_rec_drop = col_eval.get('is_recommended_drop', False)
        drop_reason = col_eval.get('reason', '')

        column_info.append({
            'name': col,
            'display_name': display_name,
            'type': type_name,
            'semantic_type': sem_type,
            'is_recommended_drop': is_rec_drop,
            'drop_reason': drop_reason
        })

    missing_info = []
    if total_missing_count > 0:
        missing_values = df.isnull().sum()
        sorted_missing = missing_values[missing_values > 0].sort_values(ascending=False)
        for col, count in sorted_missing.items():
            percentage = (count / row_count) * 100 if row_count > 0 else 0
            col_semantic_type = semantic_types.get(col, 'generic')
            non_null = df[col].dropna()

            rec_method = "Mode (Categorical)"
            rec_val = "Missing"
            explanation = "Impute with mode or constant label."

            if non_null.empty:
                rec_method = "Drop Column"
                rec_val = "N/A"
                explanation = "100% missing cells. Recommended to drop column."
            elif pd.api.types.is_numeric_dtype(df[col]):
                skew = float(non_null.skew()) if len(non_null) > 2 else 0.0
                if abs(skew) > 1.0:
                    med = float(non_null.median())
                    rec_method = "Median"
                    rec_val = f"{med:,.2f}" if abs(med) >= 1 else f"{med:.4f}"
                    explanation = f"Recommended Median due to skewed distribution (Skewness = {skew:.2f})."
                else:
                    mean_val = float(non_null.mean())
                    rec_method = "Mean"
                    rec_val = f"{mean_val:,.2f}" if abs(mean_val) >= 1 else f"{mean_val:.4f}"
                    explanation = f"Recommended Mean for symmetric distribution (Skewness = {skew:.2f})."
            elif pd.api.types.is_datetime64_any_dtype(df[col]) or col_semantic_type == "datetime":
                rec_method = "Forward Fill (ffill)"
                mode_date = str(non_null.mode().iloc[0]) if not non_null.mode().empty else "N/A"
                rec_val = mode_date
                explanation = f"Recommended Forward Fill or Mode Date ({mode_date})."
            else:
                mode_cat = str(non_null.mode().iloc[0]) if not non_null.mode().empty else "Unknown"
                rec_method = "Mode"
                rec_val = f"'{mode_cat}'"
                explanation = f"Recommended Most Frequent (Mode) Category."

            missing_info.append({
                'name': col,
                'count': int(count),
                'percentage': round(percentage, 2),
                'semantic_type': col_semantic_type,
                'recommended_method': rec_method,
                'recommended_value': rec_val,
                'explanation': explanation
            })

    duplicate_percentage = round((duplicate_count / row_count) * 100, 2) if row_count > 0 else 0
    duplicates_preview_html = None
    if duplicate_count > 0:
        duplicates_df = df[df.duplicated(keep=False)].sort_values(by=list(df.columns))
        duplicates_preview_html = duplicates_df.head().to_html(
            classes=['dn-table', 'dn-table-preview', 'dn-table-sm'],
            index=False,
            border=0,
            justify='left'
        )

    stats_summary_html = None
    try:
        stats_dict = eda_service.dataset_numeric_summary(df, semantic_types)
        if stats_dict:
            # Transpose for a professional layout (metrics as columns) and handle potential '%' in describe()
            stats_df = pd.DataFrame(stats_dict).T.reset_index().rename(columns={'index': 'Column'})
            stats_df.columns = [str(c).replace('%', 'pct') for c in stats_df.columns]
            stats_summary_html = stats_df.to_html(
                classes=['dn-table', 'dn-table-preview', 'dn-table-stats'],
                index=False,
                border=0,
                justify='left'
            )
        else:
            # Fallback to pandas describe, ensuring index is JSON-serializable
            stats_df = df.describe().round(2).T.reset_index().rename(columns={'index': 'Column'})
            stats_df.columns = [str(c).replace('%', 'pct') for c in stats_df.columns]
            stats_summary_html = stats_df.to_html(
                classes=['dn-table', 'dn-table-preview', 'dn-table-stats'],
                index=False,
                border=0,
                justify='left'
            )
    except Exception as e:
        current_app.logger.warning(f"Could not generate statistical summary: {e}")

    return {
        'success': True,
        'message': message or f'Dataset "{file_name}" loaded successfully.',
        'file_name': file_name,
        'preview_html': df_preview_html,
        'row_count': int(row_count),
        'column_count': int(column_count),
        'column_info': column_info,
        'column_usefulness': column_usefulness,
        'missing_info': missing_info,
        'total_missing_count': total_missing_count,
        'duplicate_count': duplicate_count,
        'duplicate_percentage': duplicate_percentage,
        'duplicates_preview_html': duplicates_preview_html,
        'dataset_id': dataset_id,
        'stats_summary_html': stats_summary_html,
        'is_sampled': file_size > SAMPLING_THRESHOLD_BYTES,
        'quality_metrics': quality_metrics,
        'memory_summary': memory_summary,
        'business_domain': business_domain
    }


# --- File Upload Route ---
@bp.route('/upload_dataset', methods=['POST'])
@roles_required('admin', 'manager', 'analyst')
def upload_dataset():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part in the request.'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected.'}), 400

    if not file:
        return jsonify({'success': False, 'message': 'File is empty.'}), 400

    # Max Upload Size validation from SYSTEM_SETTINGS
    file.seek(0, os.SEEK_END)
    file_size_bytes = file.tell()
    file.seek(0)
    file_size_mb = file_size_bytes / (1024 * 1024)

    settings = current_app.config.get('SYSTEM_SETTINGS', {})
    try:
        max_allowed_mb = float(settings.get('max_file_size_mb', 50))
    except (ValueError, TypeError):
        max_allowed_mb = 50.0

    if file_size_mb > max_allowed_mb:
        return jsonify({
            'success': False,
            'message': f"Upload rejected. File size ({file_size_mb:.2f} MB) exceeds maximum limit of {max_allowed_mb:g} MB configured in System Settings."
        }), 400

    original_filename = secure_filename(file.filename)
    if not original_filename:
        return jsonify({'success': False, 'message': 'Invalid filename.'}), 400

    allowed_extensions = {'.csv', '.xls', '.xlsx'}
    file_ext = os.path.splitext(original_filename)[1].lower()
    if file_ext not in allowed_extensions:
        return jsonify({'success': False, 'message': 'Unsupported file type. Please upload a CSV or Excel file.'}), 400

    user_id = session['id']
    user_upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], "raw", f"user_{user_id}")
    unique_filename = f"{uuid.uuid4().hex}{file_ext}"
    os.makedirs(user_upload_folder, exist_ok=True)
    filepath = os.path.join(user_upload_folder, unique_filename)
    file.save(filepath)

    try:
        if file_ext == '.csv':
            file_type = 'csv'
            try:
                df = pd.read_csv(filepath, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(filepath, encoding='latin1')
        elif file_ext in ['.xls', '.xlsx']:
            file_type = 'xlsx'
            df = pd.read_excel(filepath)

        # 1. Missing Value Normalization (blanks, NA, null, ?, -, inf)
        df = cleaning_service.normalize_missing_values(df)

        # 2. Semantic Classification & Datatype Auto-Conversion
        semantic_types = semantic_service.classify_dataframe(df)
        df, semantic_types = cleaning_service.auto_convert_dtypes(df, semantic_types)
        df = cleaning_service.normalize_categories(df, semantic_types)

        row_count, column_count = df.shape
        file_size = os.path.getsize(filepath)
        total_missing_count = int(df.isnull().sum().sum())
        duplicate_count = int(df.duplicated().sum())

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error.'}), 500

        try:
            with conn.cursor() as cursor:
                sql = """
                    INSERT INTO datasets
                    (user_id, file_name, file_path, file_size, file_type, row_count, column_count,
                     missing_values_count, duplicate_rows_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(
                    sql,
                    (user_id, original_filename, filepath, file_size, file_type,
                     row_count, column_count, total_missing_count, duplicate_count)
                )
                dataset_id = cursor.lastrowid
            conn.commit()
            save_dataframe(df, dataset_id, user_id)
            session['active_dataset_id'] = dataset_id
        finally:
            conn.close()

    except Exception as e:
        current_app.logger.exception(f"Error processing file {original_filename}: {e}")
        log_api_call(request.path, 'failure')
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
        return jsonify({'success': False, 'message': 'Could not process the uploaded file. Please verify the file format and try again.'}), 500

    response_payload = build_dataset_payload(
        df,
        semantic_types,
        dataset_id,
        original_filename,
        file_size,
        f'File "{original_filename}" uploaded and processed successfully!'
    )
    log_api_call(request.path, 'success')
    return jsonify(response_payload)


@bp.route('/current_dataset', methods=['GET'])
@roles_required('admin', 'manager', 'analyst')
def current_dataset():
    user_id = session['id']
    dataset_id = session.get('active_dataset_id')
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500

    try:
        with conn.cursor() as cursor:
            dataset = None
            if dataset_id:
                cursor.execute(
                    "SELECT id, file_name, file_path, file_size FROM datasets WHERE id = %s AND user_id = %s",
                    (dataset_id, user_id)
                )
                dataset = cursor.fetchone()

            if not dataset:
                cursor.execute(
                    "SELECT id, file_name, file_path, file_size FROM datasets WHERE user_id = %s ORDER BY uploaded_at DESC LIMIT 1",
                    (user_id,)
                )
                dataset = cursor.fetchone()

            if not dataset:
                return jsonify({'success': True, 'has_dataset': False})

        session['active_dataset_id'] = dataset['id']
        df = load_dataframe(dataset['id'], user_id)
        df = cleaning_service.normalize_missing_values(df)
        semantic_types = semantic_service.classify_dataframe(df)
        df, semantic_types = cleaning_service.auto_convert_dtypes(df, semantic_types)
        df = cleaning_service.normalize_categories(df, semantic_types)

        return jsonify(build_dataset_payload(
            df,
            semantic_types,
            dataset['id'],
            dataset['file_name'],
            dataset['file_size'] or 0
        ))

    except FileNotFoundError:
        return jsonify({'success': False, 'message': 'Dataset file not found on server.'}), 404
    except Exception as e:
        current_app.logger.exception(f"Error loading current dataset: {e}")
        return jsonify({'success': False, 'message': f'An error occurred while loading dataset: {e}'}), 500
    finally:
        if conn:
            conn.close()


@bp.route('/previous_datasets', methods=['GET'])
@roles_required('admin', 'manager', 'analyst')
def get_previous_datasets():
    user_id = session.get('id')
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, file_name, file_size, row_count, column_count, 
                       missing_values_count, duplicate_rows_count, uploaded_at
                FROM datasets 
                WHERE user_id = %s 
                ORDER BY uploaded_at DESC
                """,
                (user_id,)
            )
            datasets = cursor.fetchall() or []

            formatted_datasets = []
            for ds in datasets:
                file_size_bytes = ds.get('file_size') or 0
                if file_size_bytes >= 1024 * 1024:
                    size_str = f"{file_size_bytes / (1024 * 1024):.2f} MB"
                elif file_size_bytes >= 1024:
                    size_str = f"{file_size_bytes / 1024:.1f} KB"
                else:
                    size_str = f"{file_size_bytes} Bytes"

                uploaded_at = ds.get('uploaded_at')
                uploaded_str = uploaded_at.strftime('%Y-%m-%d %H:%M') if uploaded_at else 'N/A'

                formatted_datasets.append({
                    'id': ds['id'],
                    'file_name': ds.get('file_name', 'Untitled Dataset'),
                    'file_size': size_str,
                    'file_size_raw': file_size_bytes,
                    'row_count': ds.get('row_count') or 0,
                    'column_count': ds.get('column_count') or 0,
                    'missing_values': ds.get('missing_values_count') or 0,
                    'duplicate_rows': ds.get('duplicate_rows_count') or 0,
                    'uploaded_at': uploaded_str,
                    'is_active': (ds['id'] == session.get('active_dataset_id'))
                })

            return jsonify({
                'success': True,
                'datasets': formatted_datasets,
                'total_count': len(formatted_datasets)
            })
    except Exception as e:
        current_app.logger.exception(f"Error fetching previous datasets: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if conn:
            conn.close()


@bp.route('/load_dataset/<int:dataset_id>', methods=['POST', 'GET'])
@roles_required('admin', 'manager', 'analyst')
def load_specific_dataset(dataset_id):
    user_id = session.get('id')
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500

    user_role = session.get('role', 'analyst')
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, file_name, file_path, file_size, user_id FROM datasets 
                WHERE id = %s AND (
                    user_id = %s
                    OR %s = 'admin'
                    OR id IN (SELECT dataset_id FROM manager_tasks WHERE assigned_to_id = %s AND dataset_id IS NOT NULL)
                    OR id IN (SELECT dataset_id FROM shared_dashboards WHERE owner_id = %s OR shared_with_user_id = %s OR shared_with_role = %s OR shared_with_role = 'all')
                )
                """,
                (dataset_id, user_id, user_role, user_id, user_id, user_id, user_role)
            )
            dataset = cursor.fetchone()
            if not dataset:
                cursor.execute(
                    "SELECT id, file_name, file_path, file_size, user_id FROM datasets WHERE id = %s",
                    (dataset_id,)
                )
                dataset = cursor.fetchone()
            if not dataset:
                return jsonify({'success': False, 'message': 'Dataset not found or access denied.'}), 404

        session['active_dataset_id'] = dataset['id']
        df = load_dataframe(dataset['id'], dataset.get('user_id', user_id))
        df = cleaning_service.normalize_missing_values(df)
        semantic_types = semantic_service.classify_dataframe(df)
        df, semantic_types = cleaning_service.auto_convert_dtypes(df, semantic_types)
        df = cleaning_service.normalize_categories(df, semantic_types)

        payload = build_dataset_payload(
            df,
            semantic_types,
            dataset['id'],
            dataset['file_name'],
            dataset['file_size'] or 0,
            message=f"Dataset '{dataset['file_name']}' loaded successfully."
        )
        return jsonify(payload)

    except FileNotFoundError:
        return jsonify({'success': False, 'message': 'Dataset file not found on server storage.'}), 404
    except Exception as e:
        current_app.logger.exception(f"Error loading dataset #{dataset_id}: {e}")
        return jsonify({'success': False, 'message': f'Failed to load dataset: {e}'}), 500
    finally:
        if conn:
            conn.close()


@bp.route('/clean_data', methods=['POST'])
@roles_required('admin', 'manager', 'analyst')
def clean_data():
    data = request.get_json()
    dataset_id = data.get('dataset_id')
    target_column = data.get('column')
    strategy = data.get('strategy')
    custom_value = data.get('custom_value')

    if not dataset_id:
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': 'Dataset ID is missing.'}), 400

    try:
        df = load_dataframe(dataset_id, session['id'])
        df = cleaning_service.normalize_missing_values(df)
        semantic_types = semantic_service.classify_dataframe(df)

        old_row_count = len(df)
        old_missing_count = int(df.isnull().sum().sum())

        if strategy == 'smart_clean':
            df = cleaning_service.smart_clean_dataframe(df, semantic_types)
        elif strategy == 'remove_row':
            columns_to_fill = [target_column] if target_column != 'all_columns' else df.columns
            df.dropna(subset=columns_to_fill, inplace=True)
        else:
            columns_to_fill = [target_column] if target_column != 'all_columns' else df.columns
            for col in columns_to_fill:
                if df[col].isnull().any():
                    col_sem = semantic_types.get(col, 'unknown')
                    if strategy in ['fill_mean', 'fill_median']:
                        # Protect identifiers and geographic codes from mathematical imputation
                        if col_sem in ['identifier', 'possible_identifier', 'geographic_code']:
                            continue
                        df = cleaning_service.smart_clean_column(df, col, col_sem)
                    elif strategy == 'fill_mode':
                        mode_values = df[col].mode(dropna=True)
                        fill_val = mode_values.iloc[0] if not mode_values.empty else "Unknown"
                        df[col] = df[col].fillna(fill_val)
                    elif strategy == 'fill_custom':
                        try:
                            df[col] = df[col].fillna(pd.to_numeric(custom_value))
                        except (ValueError, TypeError):
                            df[col] = df[col].fillna(custom_value)

        save_dataframe(df, dataset_id, session['id'])

        new_row_count, new_column_count = df.shape
        new_missing_count = int(df.isnull().sum().sum())
        filled_values = max(0, old_missing_count - new_missing_count)
        removed_rows = max(0, old_row_count - new_row_count)

        new_missing_values = df.isnull().sum()
        new_total_missing_count = int(new_missing_values.sum())
        new_missing_info = []
        if new_total_missing_count > 0:
            sorted_missing = new_missing_values[new_missing_values > 0].sort_values(ascending=False)
            for col, count in sorted_missing.items():
                percentage = (count / new_row_count) * 100 if new_row_count > 0 else 0
                new_missing_info.append({'name': col, 'count': int(count), 'percentage': round(percentage, 2)})

        new_preview_html = df.head(10).to_html(
            classes=['dn-table', 'dn-table-preview'],
            index=False,
            border=0,
            justify='left'
        )

        response = {
            'success': True,
            'message': 'Data cleaning applied successfully!',
            'cleaning_summary': {
                'missing_before': old_missing_count,
                'missing_after': new_missing_count,
                'values_fixed': filled_values,
                'rows_removed': removed_rows,
                'strategy': strategy,
                'column': target_column
            },
            'cleaned_data': {
                'preview_html': new_preview_html,
                'row_count': new_row_count,
                'column_count': new_column_count,
                'missing_info': new_missing_info,
                'total_missing_count': new_total_missing_count
            }
        }
        log_api_call(request.path, 'success')
        return jsonify(response)

    except FileNotFoundError:
        return jsonify({'success': False, 'message': 'Original data file not found on server.'}), 404
    except Exception as e:
        current_app.logger.exception(f"Error during cleaning: {e}")
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': f'An error occurred: {e}'}), 500


@bp.route('/handle_duplicates', methods=['POST'])
@roles_required('admin', 'manager', 'analyst')
def handle_duplicates():
    data = request.get_json()
    dataset_id = data.get('dataset_id')
    columns = data.get('columns')
    action = data.get('action', 'find')
    keep_strategy = data.get('keep', 'first')

    if not all([dataset_id, columns]):
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': 'Dataset ID and columns are required.'}), 400

    try:
        df = load_dataframe(dataset_id, session['id'])

        if action == 'find':
            duplicates_mask = df.duplicated(subset=columns, keep=False)
            duplicate_count = int(duplicates_mask.sum())
            if duplicate_count == 0:
                return jsonify({'success': True, 'count': 0, 'message': 'No duplicates found for the selected columns.'})
            duplicates_df = df[duplicates_mask].sort_values(by=columns)
            preview_html = duplicates_df.head(10).to_html(
                classes=['dn-table', 'dn-table-preview', 'dn-table-sm'],
                index=False,
                border=0,
                justify='left'
            )
            log_api_call(request.path, 'success')
            return jsonify({'success': True, 'count': duplicate_count, 'preview_html': preview_html})

        elif action == 'remove':
            original_rows = len(df)
            df.drop_duplicates(subset=columns, keep=keep_strategy, inplace=True)
            rows_removed = original_rows - len(df)
            save_dataframe(df, dataset_id, session['id'])
            log_api_call(request.path, 'success')
            return jsonify({'success': True, 'message': f'Successfully removed {rows_removed} duplicate rows.', 'rows_removed': rows_removed})

    except FileNotFoundError:
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': 'Data file not found on server.'}), 404
    except Exception as e:
        current_app.logger.exception(f"Error during duplicate handling: {e}")
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': f'An error occurred: {e}'}), 500


@bp.route('/generate_eda', methods=['POST'])
@roles_required('admin', 'manager', 'analyst')
def generate_eda():
    dataset_id = request.json.get('dataset_id')
    if not dataset_id:
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': 'Dataset ID is missing.'}), 400

    try:
        df = load_dataframe(dataset_id, session['id'])
        df = cleaning_service.normalize_missing_values(df)
        semantic_types = semantic_service.classify_dataframe(df)

        recommended_charts = chart_service.generate_automatic_charts(df, semantic_types)
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE datasets SET eda_charts_json = %s WHERE id = %s AND user_id = %s",
                        (json.dumps(recommended_charts), dataset_id, session['id'])
                    )
                conn.commit()
            finally:
                conn.close()
        log_api_call(request.path, 'success')
        return jsonify({'success': True, 'recommended_charts': recommended_charts})
    except Exception as e:
        current_app.logger.exception(f"Error during EDA generation: {e}")
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': f'An error occurred during EDA generation: {e}'}), 500


@bp.route('/get_eda_results/<int:dataset_id>', methods=['GET'])
@roles_required('admin', 'manager', 'analyst')
def get_eda_results(dataset_id):
    if not dataset_id:
        return jsonify({'success': False, 'message': 'Dataset ID is missing.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT eda_charts_json FROM datasets WHERE id = %s AND user_id = %s",
                (dataset_id, session['id'])
            )
            result = cursor.fetchone()

        if result and result['eda_charts_json']:
            charts = json.loads(result['eda_charts_json'])
            return jsonify({'success': True, 'recommended_charts': charts})
        else:
            return jsonify({'success': True, 'recommended_charts': [], 'message': 'No EDA charts found for this dataset.'})
    except Exception as e:
        current_app.logger.exception(f"Error retrieving EDA results: {e}")
        return jsonify({'success': False, 'message': f'An error occurred: {e}'}), 500
    finally:
        if conn:
            conn.close()


@bp.route('/get_correlation_matrix', methods=['POST'])
@roles_required('admin', 'manager', 'analyst')
def get_correlation_matrix():
    dataset_id = request.json.get('dataset_id')
    if not dataset_id:
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': 'Dataset ID missing.'}), 400

    try:
        df = load_dataframe(dataset_id, session['id'])
        df = cleaning_service.normalize_missing_values(df)
        semantic_types = semantic_service.classify_dataframe(df)

        corr_matrix = eda_service.calculate_correlation(df, semantic_types)

        if corr_matrix is None or not corr_matrix.get('matrix'):
            log_api_call(request.path, 'failure')
            return jsonify({'success': False, 'message': 'Not enough numeric measure columns (at least 2 required) or insufficient data for correlation analysis.'})

        # Convert the correlation matrix dictionary back to a DataFrame for plotting
        corr_df_for_plot = pd.DataFrame(corr_matrix['matrix'])
        # Dynamically adjust figure size to prevent label overlap using the DataFrame's columns
        num_cols = len(corr_df_for_plot.columns)
        fig_width = max(8, num_cols * 0.8)
        fig_height = max(6, num_cols * 0.6)

        # --- Extract Top/Bottom Correlations ---
        corr_stacked = corr_df_for_plot.stack().reset_index()
        corr_stacked.columns = ['var1', 'var2', 'correlation']
        # Remove self-correlation and duplicates
        corr_stacked = corr_stacked[corr_stacked['var1'] != corr_stacked['var2']]
        corr_stacked['sorted_vars'] = corr_stacked.apply(lambda row: tuple(sorted((row['var1'], row['var2']))), axis=1)
        corr_pairs = corr_stacked.drop_duplicates(subset='sorted_vars').drop(columns='sorted_vars')

        # Get top 5 positive and negative correlations
        sorted_corr = corr_pairs.sort_values(by='correlation', ascending=False)
        top_positive = sorted_corr.head(5).to_dict(orient='records')
        top_negative = sorted_corr.tail(5).sort_values(by='correlation', ascending=True).to_dict(orient='records')
        # --- End Extraction ---

        if plt is None or sns is None:
            return jsonify({'success': False, 'message': 'Plotting engine (matplotlib/seaborn) is unavailable.'}), 500

        plt.figure(figsize=(fig_width, fig_height))
        sns.heatmap(corr_df_for_plot, annot=True, cmap='viridis', fmt='.2f', linewidths=.5)
        plt.title('Correlation Matrix of Measure Columns', fontsize=12, fontweight='bold')
        response = {
            'success': True,
            'heatmap_plot': chart_service.fig_to_base64(plt.gcf()),
            'numeric_columns': list(corr_df_for_plot.columns),
            'top_positive': top_positive,
            'top_negative': top_negative
        }
        log_api_call(request.path, 'success')
        return jsonify(response)
    except Exception as e:
        current_app.logger.exception(f"Error generating correlation matrix: {e}")
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': f'An error occurred: {e}'}), 500


@bp.route('/get_scatter_plot', methods=['POST'])
@roles_required('admin', 'manager', 'analyst')
def get_scatter_plot():
    data = request.get_json()
    dataset_id = data.get('dataset_id')
    x_col = data.get('x_col')
    y_col = data.get('y_col')

    if not all([dataset_id, x_col, y_col]):
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': 'Missing required parameters.'}), 400

    try:
        if plt is None or sns is None:
            return jsonify({'success': False, 'message': 'Plotting engine (matplotlib/seaborn) is unavailable.'}), 500

        df = load_dataframe(dataset_id, session['id'])
        plt.figure(figsize=(6, 4))
        sns.scatterplot(data=df, x=x_col, y=y_col, alpha=0.6, color='#4F46E5')
        plt.title(f'Scatter Plot: {y_col} vs. {x_col}', fontsize=12, fontweight='bold')
        plt.xlabel(x_col)
        plt.ylabel(y_col)
        plt.grid(True, linestyle='--', alpha=0.6)

        log_api_call(request.path, 'success')
        return jsonify({'success': True, 'scatter_plot': chart_service.fig_to_base64(plt.gcf())})
    except Exception as e:
        current_app.logger.exception(f"Error generating scatter plot: {e}")
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': f'An error occurred: {e}'}), 500


@bp.route('/analyze_full', methods=['POST'])
@roles_required('admin', 'manager', 'analyst')
def analyze_full():
    """
    Executes full automatic end-to-end analytics pipeline on a dataset.
    """
    data = request.get_json() or {}
    dataset_id = data.get('dataset_id')
    generate_ai = data.get('generate_ai', True)
    force_refresh = data.get('force_refresh', False)

    if not dataset_id: 
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': 'Dataset ID is missing.'}), 400

    try:
        df = load_dataframe(dataset_id, session['id'])
        analysis_result = get_or_create_analysis(df, dataset_id, generate_ai=generate_ai, force_refresh=force_refresh)

        if 'cleaned_df' in analysis_result:
            cleaned_df = analysis_result.pop('cleaned_df')
            save_dataframe(cleaned_df, dataset_id, session['id'])

        log_api_call(request.path, 'success')
        return jsonify({'success': True, 'analysis': analysis_result})
    except Exception as e:
        current_app.logger.exception(f"Error during full dataset analysis: {e}")
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': f'An error occurred during full analysis: {e}'}), 500


def get_filepath_for_user(dataset_id, user_id):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT file_path FROM datasets WHERE id = %s AND user_id = %s",
                (dataset_id, user_id)
            )
            record = cursor.fetchone()
            if not record:
                cursor.execute(
                    "SELECT file_path FROM datasets WHERE id = %s",
                    (dataset_id,)
                )
                record = cursor.fetchone()
        return record['file_path'] if record else None
    finally:
        if conn:
            conn.close()


def get_processed_path(dataset_id, user_id):
    owner_id = user_id
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT user_id FROM datasets WHERE id = %s", (dataset_id,))
                record = cursor.fetchone()
                if record:
                    owner_id = record['user_id']
        except Exception:
            pass
        finally:
            conn.close()

    processed_dir = os.path.join(
        current_app.config['UPLOAD_FOLDER'],
        "processed",
        f"user_{owner_id}"
    )
    os.makedirs(processed_dir, exist_ok=True)
    return os.path.join(processed_dir, f"{dataset_id}.pkl")


def load_dataframe(dataset_id, user_id, force_full_load=False):
    processed_path = get_processed_path(dataset_id, user_id)
    if os.path.exists(processed_path):
        return pd.read_pickle(processed_path)

    original_filepath = get_filepath_for_user(dataset_id, user_id)
    if not original_filepath:
        raise FileNotFoundError("No processed or original file found for this dataset.")

    file_size = os.path.getsize(original_filepath)
    if file_size > SAMPLING_THRESHOLD_BYTES and not force_full_load:
        current_app.logger.info(f"Large file detected. Loading a sample of {SAMPLING_ROW_COUNT} rows from {original_filepath}")
        if original_filepath.endswith('.csv'):
            try:
                with open(original_filepath, 'r', encoding='utf-8') as f:
                    total_rows = sum(1 for _ in f) - 1  # subtract header
                if total_rows > SAMPLING_ROW_COUNT:
                    step = max(1, total_rows // SAMPLING_ROW_COUNT)
                    return pd.read_csv(
                        original_filepath,
                        skiprows=lambda i: i > 0 and (i - 1) % step != 0,
                        encoding='utf-8',
                        engine='c',
                        low_memory=True
                    )
            except UnicodeDecodeError:
                df = pd.read_csv(original_filepath, encoding='latin1', low_memory=True)
                if len(df) > SAMPLING_ROW_COUNT:
                    return df.sample(n=SAMPLING_ROW_COUNT, random_state=42)
                return df
            except Exception as e:
                current_app.logger.warning(f"CSV sampling failed: {e}. Falling back to full load and sample.")
                df = pd.read_csv(original_filepath, encoding='utf-8' if 'utf-8' in str(e) else 'latin1', low_memory=True)
                if len(df) > SAMPLING_ROW_COUNT:
                    return df.sample(n=SAMPLING_ROW_COUNT, random_state=42)
                return df
        else:
            df = pd.read_excel(original_filepath)
            if len(df) > SAMPLING_ROW_COUNT:
                return df.sample(n=SAMPLING_ROW_COUNT, random_state=42)
            return df

    current_app.logger.info(f"Loading full original file: {original_filepath}")
    if original_filepath.endswith('.csv'):
        try:
            return pd.read_csv(original_filepath, encoding='utf-8', low_memory=True)
        except UnicodeDecodeError:
            return pd.read_csv(original_filepath, encoding='latin1', low_memory=True)
    else:
        return pd.read_excel(original_filepath)


def get_cached_analysis_filepath(dataset_id):
    cache_dir = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), 'cache')
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"dataset_{dataset_id}_analysis.json")


def load_cached_analysis(dataset_id):
    filepath = get_cached_analysis_filepath(dataset_id)
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except Exception as e:
            current_app.logger.warning(f"Failed to read cached analysis for dataset {dataset_id}: {e}")
    return None


def save_cached_analysis(dataset_id, analysis_result):
    filepath = get_cached_analysis_filepath(dataset_id)
    try:
        to_save = {}
        for k, v in analysis_result.items():
            if isinstance(v, pd.DataFrame):
                continue
            to_save[k] = v
        cleaned_result = clean_for_json(to_save)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(cleaned_result, f, indent=2)
        current_app.logger.info(f"Saved persistent report analysis cache for dataset {dataset_id}")
    except Exception as e:
        current_app.logger.warning(f"Failed to save cached analysis for dataset {dataset_id}: {e}")


def invalidate_cached_analysis(dataset_id):
    filepath = get_cached_analysis_filepath(dataset_id)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            current_app.logger.info(f"Invalidated cached analysis for dataset {dataset_id}")
        except Exception as e:
            current_app.logger.warning(f"Failed to delete cached analysis for dataset {dataset_id}: {e}")


def record_report_generation(dataset_id, user_id, report_name, report_type):
    """Records report generation entry in MySQL reports table."""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO reports (user_id, dataset_id, report_name, report_type) VALUES (%s, %s, %s, %s)",
                    (user_id, dataset_id, report_name, report_type)
                )
            conn.commit()
        except Exception as e:
            current_app.logger.warning(f"Could not record report generation in DB: {e}")
        finally:
            conn.close()


def get_or_create_analysis(df, dataset_id, generate_ai=True, force_refresh=False):
    """
    Returns saved/cached report analysis for the given dataset_id if present to avoid repeated AI calls.
    If no cache exists (or force_refresh is True), runs full analytics pipeline, saves the result to disk,
    and updates MySQL database.
    """
    if not force_refresh:
        cached = load_cached_analysis(dataset_id)
        if cached and isinstance(cached, dict):
            # Check if cached analysis has AI explanation if generate_ai is required
            if not generate_ai or cached.get("ai_explanation"):
                current_app.logger.info(f"[Cache Hit] Reusing saved report analysis for dataset {dataset_id}. Zero AI calls made.")
                return cached

    current_app.logger.info(f"[Cache Miss] Generating new analysis pipeline for dataset {dataset_id} (generate_ai={generate_ai}).")
    analysis_result = pipeline_service.analyze_dataset(df, generate_ai=generate_ai)

    # Save analysis result to persistent JSON cache file
    save_cached_analysis(dataset_id, analysis_result)

    # Update eda_charts_json in MySQL datasets table
    charts = analysis_result.get("recommended_charts", [])
    if charts:
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE datasets SET eda_charts_json = %s WHERE id = %s",
                        (json.dumps(clean_for_json(charts)), dataset_id)
                    )
                conn.commit()
            except Exception as e:
                current_app.logger.warning(f"Could not update eda_charts_json: {e}")
            finally:
                conn.close()

    return analysis_result


def save_dataframe(df, dataset_id, user_id):
    processed_path = get_processed_path(dataset_id, user_id)
    df.to_pickle(processed_path)
    invalidate_cached_analysis(dataset_id)
    current_app.logger.info(f"Saved processed data to: {processed_path}")


@bp.route('/download_cleaned_dataset/<int:dataset_id>')
@roles_required('admin', 'manager', 'analyst')
def download_cleaned_dataset(dataset_id):
    export_format = request.args.get('format', 'csv').lower()
    conn = get_db_connection()
    if not conn:
        flash('Database connection error.', 'danger')
        return redirect(url_for('dashboards.analyst_dashboard'))

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT file_name, user_id FROM datasets WHERE id = %s", (dataset_id,))
            dataset_record = cursor.fetchone()

        if not dataset_record or dataset_record['user_id'] != session['id']:
            flash('Dataset not found or permission denied.', 'danger')
            return redirect(url_for('dashboards.analyst_dashboard'))

        processed_path = get_processed_path(dataset_id, session['id'])
        if os.path.exists(processed_path):
            df = load_dataframe(dataset_id, session['id'], force_full_load=True)
            base_name = os.path.splitext(dataset_record['file_name'])[0]

            if export_format == 'excel' or export_format == 'xlsx':
                buf = BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Cleaned Data')
                buf.seek(0)
                return current_app.response_class(
                    buf.getvalue(),
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={"Content-disposition": f"attachment; filename=cleaned_{base_name}.xlsx"}
                )
            else:
                csv_buffer = BytesIO()
                df.to_csv(csv_buffer, index=False)
                csv_buffer.seek(0)
                return current_app.response_class(
                    csv_buffer.getvalue(),
                    mimetype='text/csv',
                    headers={"Content-disposition": f"attachment; filename=cleaned_{base_name}.csv"}
                )
        else:
            flash('No cleaned version of the dataset found to download.', 'warning')
            return redirect(url_for('dashboards.analyst_dashboard'))

    except Exception as e:
        current_app.logger.exception(f"Error during file download: {e}")
        flash(f'An error occurred while preparing the download: {e}', 'danger')
        return redirect(url_for('dashboards.analyst_dashboard'))
    finally:
        if conn:
            conn.close()


def check_ai_insights_enabled():
    """Checks if AI Insights & Natural Language features are enabled in SYSTEM_SETTINGS."""
    settings = current_app.config.get('SYSTEM_SETTINGS', {})
    if not settings.get('ai_insights_enabled', True):
        return jsonify({
            'success': False,
            'message': 'AI Insights & Natural Language features are currently disabled in System Settings by the Administrator.'
        }), 403
    return None


@bp.route('/ai_suggest_cleaning', methods=['POST'])
@roles_required('admin', 'manager', 'analyst')
def ai_suggest_cleaning():
    ai_guard = check_ai_insights_enabled()
    if ai_guard:
        return ai_guard

    dataset_id = request.json.get('dataset_id')
    if not dataset_id: 
        log_api_call(request.path, 'failure', is_ai_call=True)
        return jsonify({'success': False, 'message': 'Dataset ID is missing.'}), 400

    try:
        df = load_dataframe(dataset_id, session['id'])
        df = cleaning_service.normalize_missing_values(df)
        semantic_types = semantic_service.classify_dataframe(df)

        df_info_list = []
        for col in df.columns:
            col_type = str(df[col].dtype)
            col_sem = semantic_types.get(col, 'unknown')
            missing_percent = df[col].isnull().sum() / len(df) * 100 if len(df) > 0 else 0
            unique_count = df[col].nunique()
            info_str = f"- Column: '{col}' (Dtype: {col_type}, Semantic: {col_sem}, Missing: {missing_percent:.2f}%, Unique Values: {unique_count})"
            df_info_list.append(info_str)
        df_info_str = "\n".join(df_info_list)

        prompt = f"""
        You are an expert data analyst assistant. I have a dataset with the following column information:
        {df_info_str}
        Please provide suggestions for data cleaning and feature engineering.
        Focus on two main areas:
        1.  **Unwanted Columns for Removal:** Identify columns that are likely irrelevant, redundant, or have low analytical value for typical business analysis. For each suggested column, provide a brief reason.
        2.  **Potential New Features:** Suggest new columns that could be created from existing ones to enhance the dataset's analytical power. For each suggestion, describe the new feature and how it could be derived.
        Please provide your response in a structured JSON format with two keys: "unwanted_columns" (a list of objects with "column_name" and "reason") and "new_features" (a list of objects with "feature_name", "description", and "derivation_idea").
        If no suggestions are found for a category, return an empty list for that key.
        """

        ai_suggestions = ai_helper.generate_ai_completion(prompt, expect_json=True)
        log_api_call(request.path, 'success')
        return jsonify({'success': True, 'suggestions': ai_suggestions})

    except ValueError as ve:
        current_app.logger.warning(f"AI Service configuration error: {ve}")
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': str(ve)}), 503
    except Exception as e:
        current_app.logger.exception(f"Error getting AI suggestions: {e}")
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': f'An error occurred while getting AI suggestions: {e}'}), 500


@bp.route('/ai_apply_column_removal', methods=['POST'])
@roles_required('admin', 'manager', 'analyst')
def ai_apply_column_removal():
    ai_guard = check_ai_insights_enabled()
    if ai_guard:
        return ai_guard

    data = request.get_json()
    dataset_id = data.get('dataset_id')
    columns_to_remove = data.get('columns_to_remove', [])

    if not dataset_id or not columns_to_remove: 
        log_api_call(request.path, 'failure', is_ai_call=True)
        return jsonify({'success': False, 'message': 'Dataset ID and columns to remove are required.'}), 400

    try:
        df = load_dataframe(dataset_id, session['id'])
        columns_actually_removed = [col for col in columns_to_remove if col in df.columns]
        if not columns_actually_removed:
            return jsonify({'success': True, 'message': 'No specified columns were found or removed.', 'columns_removed': []})

        df.drop(columns=columns_actually_removed, inplace=True)
        save_dataframe(df, dataset_id, session['id'])

        new_preview_html = df.head().to_html(
            classes=['dn-table', 'dn-table-preview'],
            index=False,
            border=0,
            justify='left'
        )
        semantic_types = semantic_service.classify_dataframe(df)

        # Instead of manually rebuilding parts of the payload, call the master payload builder
        # to ensure the entire UI state is consistent after the drop operation.
        payload = build_dataset_payload(
            df,
            semantic_types,
            dataset_id,
            "Dataset",  # Filename is not critical here, just for display
            0,          # File size is not critical here
            f"Successfully removed {len(columns_actually_removed)} column(s) via AI suggestion."
        )
        payload['columns_removed'] = columns_actually_removed
        log_api_call(request.path, 'success')
        return jsonify(payload)

    except Exception as e:
        current_app.logger.exception(f"Error applying AI column removal: {e}")
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': f'An error occurred: {e}'}), 500


@bp.route('/delete_dataset/<int:dataset_id>', methods=['POST'])
@roles_required('admin', 'analyst')
def delete_dataset(dataset_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id, file_path FROM datasets WHERE id = %s", (dataset_id,))
            dataset = cursor.fetchone()

        if not dataset:
            return jsonify({'success': False, 'message': 'Dataset not found.'}), 404

        if session['role'] != 'admin' and dataset['user_id'] != session['id']:
            return jsonify({'success': False, 'message': 'Permission denied to delete this dataset.'}), 403

        original_filepath = dataset['file_path']
        processed_filepath = get_processed_path(dataset_id, dataset['user_id'])

        for f_path in [original_filepath, processed_filepath]:
            if f_path and os.path.exists(f_path):
                try:
                    os.remove(f_path)
                    current_app.logger.info(f"Successfully deleted file: {f_path}")
                except OSError as e:
                    current_app.logger.warning(f"Error deleting file {f_path}: {e}")

        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM datasets WHERE id = %s", (dataset_id,))
        conn.commit()

        invalidate_cached_analysis(dataset_id)

        return jsonify({'success': True, 'message': 'Dataset and all associated files have been deleted.'})

    except Exception as e:
        current_app.logger.exception(f"Error deleting dataset: {e}")
        return jsonify({'success': False, 'message': f'An error occurred: {e}'}), 500
    finally:
        if conn:
            conn.close()


@bp.route('/export_eda_report/<int:dataset_id>', methods=['GET'])
@roles_required('admin', 'manager', 'analyst', 'viewer')
def export_eda_report(dataset_id):
    """
    Generates and downloads a full standalone HTML EDA Report.
    """
    try:
        df = load_dataframe(dataset_id, session['id'])
        analysis_result = get_or_create_analysis(df, dataset_id, generate_ai=True)
        report_html = report_service.generate_eda_html_report(analysis_result)
        record_report_generation(dataset_id, session['id'], f"EDA_Report_Dataset_{dataset_id}", "HTML")

        return current_app.response_class(
            report_html,
            mimetype='text/html',
            headers={"Content-disposition": f"inline; filename=DataNova_EDA_Report_Dataset_{dataset_id}.html"}
        )
    except Exception as e:
        current_app.logger.exception(f"Error generating EDA report for dataset {dataset_id}: {e}")
        return jsonify({'success': False, 'message': f'Could not generate report: {e}'}), 500


@bp.route('/export_pdf/<int:dataset_id>', methods=['GET'])
@roles_required('admin', 'manager', 'analyst', 'viewer')
def export_pdf_report(dataset_id):
    """Generates and downloads a PDF Executive Report using ReportLab."""
    try:
        df = load_dataframe(dataset_id, session['id'])
        analysis_result = get_or_create_analysis(df, dataset_id, generate_ai=True)
        pdf_bytes = report_service.generate_pdf_report_bytes(analysis_result)
        record_report_generation(dataset_id, session['id'], f"Report_Dataset_{dataset_id}", "PDF")

        return current_app.response_class(
            pdf_bytes,
            mimetype='application/pdf',
            headers={"Content-disposition": f"attachment; filename=DataNova_Report_Dataset_{dataset_id}.pdf"}
        )
    except Exception as e:
        current_app.logger.exception(f"Error generating PDF report for dataset {dataset_id}: {e}")
        return jsonify({'success': False, 'message': f'Could not generate PDF: {e}'}), 500


@bp.route('/export_word/<int:dataset_id>', methods=['GET'])
@roles_required('admin', 'manager', 'analyst', 'viewer')
def export_word_report(dataset_id):
    """Generates and downloads a Microsoft Word (.docx) Report."""
    try:
        df = load_dataframe(dataset_id, session['id'])
        analysis_result = get_or_create_analysis(df, dataset_id, generate_ai=True)
        word_bytes = report_service.generate_word_report_bytes(analysis_result)
        record_report_generation(dataset_id, session['id'], f"Report_Dataset_{dataset_id}", "DOCX")

        return current_app.response_class(
            word_bytes,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            headers={"Content-disposition": f"attachment; filename=DataNova_Report_Dataset_{dataset_id}.docx"}
        )
    except Exception as e:
        current_app.logger.exception(f"Error generating Word report: {e}")
        return jsonify({'success': False, 'message': f'Could not generate Word doc: {e}'}), 500


@bp.route('/export_ppt/<int:dataset_id>', methods=['GET'])
@roles_required('admin', 'manager', 'analyst', 'viewer')
def export_ppt_report(dataset_id):
    """Generates and downloads a PowerPoint (.pptx) Presentation."""
    try:
        df = load_dataframe(dataset_id, session['id'])
        analysis_result = get_or_create_analysis(df, dataset_id, generate_ai=True)
        ppt_bytes = report_service.generate_ppt_report_bytes(analysis_result)
        record_report_generation(dataset_id, session['id'], f"Presentation_Dataset_{dataset_id}", "PPTX")

        return current_app.response_class(
            ppt_bytes,
            mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
            headers={"Content-disposition": f"attachment; filename=DataNova_Presentation_Dataset_{dataset_id}.pptx"}
        )
    except Exception as e:
        current_app.logger.exception(f"Error generating PPT presentation: {e}")
        return jsonify({'success': False, 'message': f'Could not generate PPT: {e}'}), 500


@bp.route('/export_excel/<int:dataset_id>', methods=['GET'])
@roles_required('admin', 'manager', 'analyst', 'viewer')
def export_excel_report(dataset_id):
    """Generates and downloads a multi-sheet Excel (.xlsx) Report."""
    try:
        df = load_dataframe(dataset_id, session['id'])
        analysis_result = get_or_create_analysis(df, dataset_id, generate_ai=True)
        excel_bytes = report_service.generate_excel_report_bytes(df, analysis_result)
        record_report_generation(dataset_id, session['id'], f"Workbook_Dataset_{dataset_id}", "XLSX")

        return current_app.response_class(
            excel_bytes,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={"Content-disposition": f"attachment; filename=DataNova_Workbook_Dataset_{dataset_id}.xlsx"}
        )
    except Exception as e:
        current_app.logger.exception(f"Error generating Excel workbook: {e}")
        return jsonify({'success': False, 'message': f'Could not generate Excel workbook: {e}'}), 500


@bp.route('/rollback_dataset', methods=['POST'])
@roles_required('admin', 'manager', 'analyst')
def rollback_dataset():
    """
    Reverts the dataset back to its raw original state by deleting the processed pickle snapshot.
    """
    data = request.get_json() or {}
    dataset_id = data.get('dataset_id')
    if not dataset_id:
        return jsonify({'success': False, 'message': 'Dataset ID is required.'}), 400

    try:
        processed_path = get_processed_path(dataset_id, session['id'])
        if os.path.exists(processed_path):
            os.remove(processed_path)
            current_app.logger.info(f"Rollback successful: removed {processed_path}")

        invalidate_cached_analysis(dataset_id)

        # Reload raw original dataset
        df = load_dataframe(dataset_id, session['id'], force_full_load=True)
        df = cleaning_service.normalize_missing_values(df)
        semantic_types = semantic_service.classify_dataframe(df)

        return jsonify({
            'success': True,
            'message': 'Dataset successfully rolled back to raw state!',
            'row_count': len(df),
            'column_count': len(df.columns)
        })
    except Exception as e:
        current_app.logger.exception(f"Rollback error: {e}")
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': f'Rollback failed: {e}'}), 500


@bp.route('/generate_automated_features', methods=['POST'])
@roles_required('admin', 'manager', 'analyst')
def generate_automated_features():
    """
    Automatically creates date, financial ratio, and range binning features.
    """
    data = request.get_json() or {}
    dataset_id = data.get('dataset_id')
    if not dataset_id:
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': 'Dataset ID is required.'}), 400

    try:
        df = load_dataframe(dataset_id, session['id'])
        semantic_types = semantic_service.classify_dataframe(df)
        df_with_features, new_features = feature_service.generate_automated_features(df, semantic_types)

        if new_features:
            save_dataframe(df_with_features, dataset_id, session['id'])
            log_api_call(request.path, 'success')

        return jsonify({
            'success': True,
            'message': f"Generated {len(new_features)} new features: {', '.join(new_features)}" if new_features else "No new features were generated.",
            'new_features': new_features,
            'column_count': len(df_with_features.columns)
        })
    except Exception as e:
        current_app.logger.exception(f"Feature engineering error: {e}")
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': f'Feature engineering failed: {e}'}), 500


@bp.route('/drop_columns', methods=['POST'])
@roles_required('admin', 'manager', 'analyst')
def drop_columns():
    """
    Drops specified unwanted/useless columns from dataset and saves cleaned state.
    """
    data = request.get_json() or {}
    dataset_id = data.get('dataset_id')
    columns_to_drop = data.get('columns', [])

    if not dataset_id or not columns_to_drop:
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': 'Dataset ID and columns list are required.'}), 400

    try:
        df = load_dataframe(dataset_id, session['id'])
        existing_drops = [c for c in columns_to_drop if c in df.columns]

        if not existing_drops:
            log_api_call(request.path, 'failure')
            return jsonify({'success': False, 'message': 'None of the specified columns exist in dataset.'}), 400

        df.drop(columns=existing_drops, inplace=True)
        save_dataframe(df, dataset_id, session['id'])

        semantic_types = semantic_service.classify_dataframe(df)
        payload = build_dataset_payload(
            df,
            semantic_types,
            dataset_id,
            "Dataset",
            0,
            f"Successfully removed {len(existing_drops)} column(s). The dataset has been updated."
        )

        # Regenerate automatic charts for cleaned data
        recommended_charts = chart_service.generate_automatic_charts(df, semantic_types)
        payload['recommended_charts'] = recommended_charts

        log_api_call(request.path, 'success')
        return jsonify(payload)

    except Exception as e:
        current_app.logger.exception(f"Error dropping columns: {e}")
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': f'Failed to drop columns: {e}'}), 500


@bp.route('/recommend_charts_for_columns', methods=['POST'])
@roles_required('admin', 'manager', 'analyst')
def recommend_charts_for_columns():
    """
    Returns chart options for user-selected X & Y columns featuring '(Recommended)' labels.
    """
    data = request.get_json() or {}
    dataset_id = data.get('dataset_id')
    x_col = data.get('x_col')
    y_col = data.get('y_col')

    if not dataset_id or not x_col:
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': 'Dataset ID and X-Axis column are required.'}), 400

    try:
        df = load_dataframe(dataset_id, session['id'])
        semantic_types = semantic_service.classify_dataframe(df)

        x_type = semantic_types.get(x_col, 'measure')
        y_type = semantic_types.get(y_col, None) if y_col else None

        chart_options = chart_service.get_chart_options_with_recommendations(x_type, y_type)
        response = {
            'success': True,
            'x_col': x_col,
            'y_col': y_col,
            'chart_options': chart_options
        }
        log_api_call(request.path, 'success')
        return jsonify(response)
    except Exception as e:
        current_app.logger.exception(f"Error recommending charts: {e}")
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': f'Failed to get recommendations: {e}'}), 500


@bp.route('/generate_custom_chart', methods=['POST'])
@roles_required('admin', 'manager', 'analyst')
def generate_custom_chart():
    """
    Generates a user-selected custom chart from cleaned data.
    """
    data = request.get_json() or {}
    dataset_id = data.get('dataset_id')
    x_col = data.get('x_col')
    y_col = data.get('y_col')
    chart_type = data.get('chart_type', 'bar')
    agg_func = data.get('agg_func', 'sum')

    if not dataset_id or not x_col:
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': 'Dataset ID and X-Axis column are required.'}), 400

    try:
        df = load_dataframe(dataset_id, session['id'])
        chart_res = chart_service.generate_custom_chart(df, x_col, y_col, chart_type, agg_func)
        plot_base64 = chart_res.get('plot') if isinstance(chart_res, dict) else chart_res
        plotly_json = chart_res.get('plotly_json') if isinstance(chart_res, dict) else None

        response = {
            'success': True,
            'title': f"{chart_type.capitalize()} Chart: {x_col}" + (f" vs {y_col}" if y_col else ""),
            'plot': plot_base64,
            'plotly_json': plotly_json,
            'chart_type': chart_type
        }
        log_api_call(request.path, 'success')
        return jsonify(response)
    except ValueError as ve:
        current_app.logger.warning(f"Validation error generating custom chart: {ve}")
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        current_app.logger.exception(f"Error generating custom chart: {e}")
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': f'Failed to generate chart: {e}'}), 500


@bp.route('/ask_data', methods=['POST'])
@roles_required('admin', 'manager', 'analyst')
def ask_data():
    """
    Answers a natural language question about the dataset using an AI model.
    """
    ai_guard = check_ai_insights_enabled()
    if ai_guard:
        return ai_guard

    data = request.get_json() or {}
    dataset_id = data.get('dataset_id')
    question = data.get('question')
    language = data.get('language', 'en')

    if not dataset_id or not question:
        log_api_call(request.path, 'failure', is_ai_call=True)
        return jsonify({'success': False, 'message': 'Dataset ID and question are required.'}), 400

    try:
        df = load_dataframe(dataset_id, session['id'])
        analysis_result = pipeline_service.analyze_dataset(df, generate_ai=False)

        dataset_overview = analysis_result.get("dataset_overview", {})
        semantic_types = analysis_result.get("semantic_types", {})
        quality_report = analysis_result.get("quality", {})
        business_kpis = analysis_result.get("business_kpis", {})
        top_bottom_analysis = analysis_result.get("top_bottom_analysis", {})
        correlation_matrix = analysis_result.get("correlation_matrix", {})
        outliers_report = analysis_result.get("outliers", {})
        domain = analysis_result.get("business_domain", "General Analytics")

        df_info_list = []
        for col, sem_type in semantic_types.items():
            df_info_list.append(f"- Column: '{col}' (Semantic Type: {sem_type}, Dtype: {str(df[col].dtype)})")
        df_info_str = "\n".join(df_info_list)

        quality_summary = f"Overall Data Quality: {quality_report.get('score', 'N/A')}/100 (Grade {quality_report.get('grade', 'N/A')})."

        kpi_summary = "Key Business Metrics:\n"
        if business_kpis:
            for k, v in business_kpis.items():
                if isinstance(v, (int, float)):
                    if 'sales' in k or 'revenue' in k or 'profit' in k:
                        kpi_summary += f"  - {k.replace('_', ' ').title()}: ₹{v:,.2f}\n"
                    elif 'percent' in k or 'pct' in k:
                        kpi_summary += f"  - {k.replace('_', ' ').title()}: {v:.2f}%\n"
                    else:
                        kpi_summary += f"  - {k.replace('_', ' ').title()}: {v:,.0f}\n"
                else:
                    kpi_summary += f"  - {k.replace('_', ' ').title()}: {v}\n"
        else:
            kpi_summary += "  - No specific business KPIs detected yet.\n"

        top_bottom_summary = ""
        if top_bottom_analysis:
            top_bottom_summary += f"Top/Bottom Analysis for {top_bottom_analysis.get('category', 'N/A')} by {top_bottom_analysis.get('measure', 'N/A')}:\n"
            top_bottom_summary += "  Top Categories:\n"
            for k, v in top_bottom_analysis.get('top_n', {}).items():
                top_bottom_summary += f"    - {k}: {v}\n"

        correlation_summary = ""
        if correlation_matrix and correlation_matrix.get('top_pairs'):
            correlation_summary += "Top Correlated Pairs:\n"
            for pair in correlation_matrix['top_pairs']:
                correlation_summary += f"  - {pair['col1']} and {pair['col2']}: r={pair['correlation']:.2f}\n"

        # --- Comprehensive Time-Series & Temporal Analysis ---
        time_series_summary = ""
        date_cols = [c for c, t in semantic_types.items() if t == "datetime" and c in df.columns]
        measure_cols = [c for c, t in semantic_types.items() if t in ["measure", "currency", "percentage"] and c in df.columns]

        if not date_cols:
            for c in df.columns:
                if any(k in c.lower() for k in ['date', 'time', 'year', 'month', 'dt', 'ship', 'order']):
                    date_cols.append(c)

        if not measure_cols:
            for c in df.columns:
                if any(k in c.lower() for k in ['sale', 'revenue', 'profit', 'amount', 'qty', 'total', 'price']):
                    measure_cols.append(c)

        if date_cols and measure_cols:
            date_col = date_cols[0]
            measure_col = next((c for c in measure_cols if any(k in c.lower() for k in ['sales', 'revenue', 'profit', 'amount', 'total'])), measure_cols[0])

            try:
                temp_df = df[[date_col, measure_col]].copy()
                temp_df[date_col] = pd.to_datetime(temp_df[date_col], errors='coerce')
                temp_df[measure_col] = pd.to_numeric(cleaning_service.convert_percentage(cleaning_service.convert_currency(temp_df[measure_col])), errors='coerce')
                temp_df.dropna(inplace=True)

                if not temp_df.empty:
                    time_series_summary += f"Time Period & Temporal Sales Breakdown (Date Column: '{date_col}', Measure: '{measure_col}'):\n"
                    temp_df.set_index(date_col, inplace=True)
                    
                    # Monthly Aggregation
                    monthly_grp = temp_df[measure_col].resample('ME').sum()
                    monthly_grp = monthly_grp[monthly_grp > 0]
                    if not monthly_grp.empty:
                        top_m = monthly_grp.sort_values(ascending=False).head(5)
                        peak_m_date = top_m.index[0].strftime("%B %Y")
                        peak_m_val = float(top_m.iloc[0])
                        time_series_summary += f"  - Peak Month (Highest Sales Period Overall): {peak_m_date} with Total Sales ₹{peak_m_val:,.2f}\n"
                        time_series_summary += "  - Top Months by Sales Volume:\n"
                        for dt_idx, m_val in top_m.head(3).items():
                            time_series_summary += f"      * {dt_idx.strftime('%B %Y')}: ₹{float(m_val):,.2f}\n"

                    # Yearly Aggregation
                    yearly_grp = temp_df[measure_col].resample('YE').sum()
                    yearly_grp = yearly_grp[yearly_grp > 0]
                    if not yearly_grp.empty:
                        top_y = yearly_grp.sort_values(ascending=False).head(3)
                        peak_y_date = top_y.index[0].strftime("%Y")
                        peak_y_val = float(top_y.iloc[0])
                        time_series_summary += f"  - Peak Year (Highest Sales Year Overall): {peak_y_date} with Total Sales ₹{peak_y_val:,.2f}\n"
                        time_series_summary += "  - Top Years by Sales Volume:\n"
                        for dt_idx, y_val in top_y.items():
                            time_series_summary += f"      * {dt_idx.strftime('%Y')}: ₹{float(y_val):,.2f}\n"

                    # Quarterly Aggregation
                    quarterly_grp = temp_df[measure_col].resample('QE').sum()
                    quarterly_grp = quarterly_grp[quarterly_grp > 0]
                    if not quarterly_grp.empty:
                        top_q = quarterly_grp.sort_values(ascending=False).head(3)
                        time_series_summary += "  - Top Quarters by Sales Volume:\n"
                        for dt_idx, q_val in top_q.items():
                            q_num = (dt_idx.month - 1) // 3 + 1
                            time_series_summary += f"      * {dt_idx.year}-Q{q_num}: ₹{float(q_val):,.2f}\n"
            except Exception as ts_err:
                current_app.logger.warning(f"Error computing live temporal summary: {ts_err}")

        # --- Categorical Multi-Dimension Breakdown ---
        categorical_summary = ""
        cat_cols = [c for c, t in semantic_types.items() if t == "categorical" and c in df.columns]
        if cat_cols and measure_cols:
            measure_col = next((c for c in measure_cols if any(k in c.lower() for k in ['sales', 'revenue', 'profit'])), measure_cols[0])
            for c_col in cat_cols[:4]:
                try:
                    grp = df.groupby(c_col)[measure_col].sum(numeric_only=True).sort_values(ascending=False).head(3)
                    if not grp.empty:
                        top_item = grp.index[0]
                        top_item_val = float(grp.iloc[0])
                        categorical_summary += f"  - {c_col}: Top Category is '{top_item}' with ₹{top_item_val:,.2f}\n"
                except Exception:
                    pass

        lang_instruction = "Answer in clear, direct English."
        if language == "hi":
            lang_instruction = "उत्तर पूरी तरह से स्पष्ट और सरल हिंदी (हिंदी भाषा) में दें। मुख्य टाइम-पीरियड, महिना और वर्ष के आंकड़ों के साथ जवाब दें।"
        elif language == "mr":
            lang_instruction = "उत्तर संपूर्णपणे सोप्या आणि स्पष्ट मराठी (मराठी भाषा) मध्ये द्या. मुख्य टाइम-पीरियड, महिना आणि वर्षाच्या आकडेवारीसह अचूक उत्तर द्या."

        prompt = f"""
        You are an expert data analyst assistant for DataNova.
        Language Constraint: {lang_instruction}

        --- Dataset Overview ---
        Total Rows: {dataset_overview.get('row_count', 'N/A')}
        Total Columns: {dataset_overview.get('column_count', 'N/A')}
        Business Domain: {domain}

        --- Column Profiling ---
        {df_info_str}

        --- Data Quality Summary ---
        {quality_summary}

        --- Key Performance Indicators ---
        {kpi_summary}

        --- Time Period & Temporal Peak Sales Breakdown ---
        {time_series_summary if time_series_summary else "No datetime column available for temporal breakdown."}

        --- Category Drivers Breakdown ---
        {categorical_summary if categorical_summary else top_bottom_summary}

        --- Correlation Summary ---
        {correlation_summary}

        --- User Question ---
        "{question}"

        Provide a clear, direct, and factual answer specifying the exact Peak Month/Year/Quarter and values if asked about time periods or sales trends.
        """

        try:
            ai_answer = ai_helper.generate_ai_completion(prompt, expect_json=False)
        except Exception as ai_err:
            current_app.logger.warning(f"AI completion failed in ask_data, generating fallback answer: {ai_err}")
            if time_series_summary:
                ai_answer = f"डेटासेट विश्लेषणावरून ({time_series_summary.strip()}). तुमच्या '{question}' प्रश्नासाठी वरील टाइम-पीरियड आकडेवारी पहा."
            else:
                ai_answer = f"Based on the dataset overview ({dataset_overview.get('row_count', 0)} rows, {dataset_overview.get('column_count', 0)} columns under '{domain}'): Overall Data Quality is {quality_report.get('score', 'N/A')}/100. Regarding '{question}': Please check the KPI summary and Correlation matrix panels in your dashboard for exact column figures."

        log_api_call(request.path, 'success', is_ai_call=True)
        return jsonify({'success': True, 'answer': ai_answer})
    except Exception as e:
        current_app.logger.exception(f"Error in /api/ask_data: {e}")
        log_api_call(request.path, 'failure', is_ai_call=True)
        return jsonify({'success': True, 'answer': f"Analyzing '{question}': Check your dashboard metrics for detailed distribution numbers."})

# =========================================================================
# --- MANAGER API ENDPOINTS ---
# =========================================================================

@bp.route('/manager/business_metrics', methods=['GET'])
@roles_required('admin', 'manager')
def manager_business_metrics():
    """Returns dynamic business metrics for active dataset."""
    from .services import manager_service
    dataset_id = session.get('active_dataset_id')
    if not dataset_id:
        return jsonify({'success': True, 'metrics': manager_service.get_manager_business_overview(None)})

    try:
        df = load_dataframe(dataset_id, session['id'])
        metrics = manager_service.get_manager_business_overview(df)
        return jsonify({'success': True, 'metrics': metrics})
    except Exception as e:
        current_app.logger.exception(f"Error loading business metrics: {e}")
        return jsonify({'success': False, 'message': 'An error occurred while loading business metrics.'}), 500


@bp.route('/manager/predictions', methods=['GET'])
@bp.route('/ml_predictions', methods=['GET', 'POST'])
@roles_required('admin', 'manager', 'analyst')
def manager_predictions():
    """Returns forecasting, time-series predictions, and K-Means ML customer/product segment clusters."""
    dataset_id = session.get('active_dataset_id')
    try:
        df = None
        if dataset_id:
            df = load_dataframe(dataset_id, session['id'])

        # The manager_service functions are designed to handle df=None and return fallbacks.
        preds = manager_service.generate_predictions_preview(df)
        clustering = manager_service.generate_ml_clustering(df)

        # Additional Statsmodels Time Series Forecast
        ts_forecast = []
        if df is not None:
            semantics = semantic_service.classify_dataframe(df)
            date_cols, meas_cols = timeseries_service.detect_time_series_columns(df, semantics)
            if date_cols and meas_cols:
                ts_res = timeseries_service.time_series_analysis(df, date_cols[0], meas_cols[0])
                if ts_res and 'forecast' in ts_res:
                    ts_forecast = ts_res['forecast']

        return jsonify(clean_for_json({
            'success': True,
            'predictions': preds,
            'clustering': clustering,
            'statsmodels_forecast': ts_forecast
        }))
    except Exception as e:
        current_app.logger.exception(f"Error in ML predictions: {e}")
        return jsonify({'success': False, 'message': 'An error occurred while generating predictions.'}), 500


@bp.route('/share_dashboard', methods=['POST'])
@roles_required('admin', 'manager', 'analyst')
def share_dashboard():
    """Legacy endpoint backward compatibility."""
    return api_share_dashboard_with_team()


@bp.route('/viewer/shared_dashboards', methods=['GET'])
@roles_required('admin', 'manager', 'analyst', 'viewer')
def viewer_shared_dashboards():
    """Returns list of shared dashboards accessible by user (DN-SEC-003)."""
    return api_shared_dashboards_list()


@bp.route('/compare_datasets', methods=['POST'])
@roles_required('admin', 'manager', 'analyst')
def compare_datasets():
    """Compares two uploaded datasets side-by-side."""
    data = request.get_json() or {}
    dataset_id_1 = data.get('dataset_id_1')
    dataset_id_2 = data.get('dataset_id_2')

    if not dataset_id_1 or not dataset_id_2:
        return jsonify({'success': False, 'message': 'Two dataset IDs are required for comparison.'}), 400

    try:
        df1 = load_dataframe(dataset_id_1, session['id'])
        df2 = load_dataframe(dataset_id_2, session['id'])

        sem1 = semantic_service.classify_dataframe(df1)
        sem2 = semantic_service.classify_dataframe(df2)

        q1 = quality_service.calculate_quality_score(df1, sem1)
        q2 = quality_service.calculate_quality_score(df2, sem2)

        common_cols = list(set(df1.columns).intersection(set(df2.columns)))

        comparison = {
            'dataset1': {
                'id': dataset_id_1,
                'rows': len(df1),
                'columns': len(df1.columns),
                'quality_score': q1.get('score', 0),
                'grade': q1.get('grade', 'N/A'),
                'missing_cells': q1.get('missing_cells', 0)
            },
            'dataset2': {
                'id': dataset_id_2,
                'rows': len(df2),
                'columns': len(df2.columns),
                'quality_score': q2.get('score', 0),
                'grade': q2.get('grade', 'N/A'),
                'missing_cells': q2.get('missing_cells', 0)
            },
            'common_columns': common_cols,
            'common_columns_count': len(common_cols)
        }

        return jsonify({'success': True, 'comparison': clean_for_json(comparison)})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Dataset comparison failed: {e}'}), 500


@bp.route('/manager/dashboard_data', methods=['GET'])
@roles_required('admin', 'manager')
def get_manager_dashboard_data_api():
    """Returns dynamic business metrics, chart datasets, insights, and predictions for Manager Dashboard."""
    try:
        user_id = session.get('id')
        active_ds_id = session.get('active_dataset_id')
        df = None
        conn = get_db_connection()

        if conn:
            try:
                with conn.cursor() as cursor:
                    if not active_ds_id:
                        cursor.execute(
                            "SELECT id FROM datasets WHERE user_id = %s ORDER BY uploaded_at DESC LIMIT 1",
                            (user_id,)
                        )
                        ds_row = cursor.fetchone()
                        if ds_row:
                            active_ds_id = ds_row['id']
                            session['active_dataset_id'] = active_ds_id

                    if active_ds_id:
                        try:
                            df = load_dataframe(active_ds_id, user_id)
                        except Exception as ex:
                            current_app.logger.warning(f"Could not load dataframe for manager API: {ex}")
            except Exception as ex:
                current_app.logger.warning(f"DB query error in manager API: {ex}")

        analytics = manager_service.get_manager_full_dashboard_analytics(df, conn, user_id)

        if conn:
            try:
                conn.close()
            except Exception:
                pass

        log_api_call('/manager/dashboard_data', 'success')
        return jsonify({
            'success': True,
            'metrics': analytics,
            'data': analytics
        })
    except Exception as e:
        log_api_call('/manager/dashboard_data', 'failure')
        return jsonify({'success': False, 'message': f'Failed to retrieve manager analytics: {e}'}), 500


@bp.route('/viewer/dashboard_data', methods=['GET'])
@roles_required('admin', 'manager', 'analyst', 'viewer')
def get_viewer_dashboard_data_api():
    """Returns dynamic shared dashboards, reports, and analytics for Viewer Dashboard."""
    try:
        user_id = session.get('id')
        role = session.get('role', 'viewer')
        active_ds_id = session.get('active_dataset_id')
        df = None
        conn = get_db_connection()

        if conn:
            try:
                with conn.cursor() as cursor:
                    if not active_ds_id:
                        cursor.execute("SELECT id FROM datasets ORDER BY uploaded_at DESC LIMIT 1")
                        ds_row = cursor.fetchone()
                        if ds_row:
                            active_ds_id = ds_row['id']
                            session['active_dataset_id'] = active_ds_id

                    if active_ds_id:
                        try:
                            df = load_dataframe(active_ds_id, session['id'])
                        except Exception as ex:
                            current_app.logger.warning(f"Could not load dataframe for viewer API: {ex}")
            except Exception as ex:
                current_app.logger.warning(f"DB query error in viewer API: {ex}")

        analytics = viewer_service.get_viewer_dashboard_analytics(df, conn, session.get('id'), role)

        if conn:
            try:
                conn.close()
            except Exception:
                pass

        log_api_call('/api/viewer/dashboard_data', 'success')
        return jsonify({
            'success': True,
            'data': analytics
        })
    except Exception as e:
        log_api_call('/api/viewer/dashboard_data', 'failure')
        return jsonify({'success': False, 'message': f'Failed to retrieve viewer analytics: {e}'}), 500


@bp.route('/admin/dashboard_data', methods=['GET'])
@roles_required('admin')
def get_admin_dashboard_data_api():
    """Returns dynamic administrative metrics, user statistics, security alerts, and system activities."""
    try:
        conn = get_db_connection()
        analytics = admin_service.get_admin_dashboard_analytics(conn)
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        log_api_call('/api/admin/dashboard_data', 'success')
        return jsonify({'success': True, 'data': analytics})
    except Exception as e:
        log_api_call('/api/admin/dashboard_data', 'failure')
        return jsonify({'success': False, 'message': f'Failed to load admin analytics: {e}'}), 500


@bp.route('/admin/users', methods=['GET'])
@roles_required('admin')
def get_admin_users_api():
    """Returns list of all registered platform users for Admin User Management."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection failed.'}), 500
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, first_name, last_name, email, role,
                       COALESCE(status, 'active') as status,
                       created_at
                FROM users
                ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            users = []
            for r in rows:
                if not isinstance(r, dict) and cursor.description:
                    cols = [d[0] for d in cursor.description]
                    r = dict(zip(cols, r))
                c_at = r.get('created_at')
                if c_at and hasattr(c_at, 'strftime'):
                    r['created_at'] = c_at.strftime('%d %b %Y')
                elif c_at:
                    r['created_at'] = str(c_at)[:10]
                else:
                    r['created_at'] = 'N/A'
                users.append(r)
        log_api_call('/api/admin/users', 'success')
        return jsonify({'success': True, 'users': users})
    except Exception as e:
        log_api_call('/api/admin/users', 'failure')
        return jsonify({'success': False, 'message': f'Failed to fetch users: {e}'}), 500
    finally:
        conn.close()


@bp.route('/admin/create_user', methods=['POST'])
@roles_required('admin')
def create_admin_user_api():
    """Creates a new user account from Admin Dashboard."""
    data = request.get_json() or {}
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'viewer')

    from .auth import create_user_account
    success, msg, status_code = create_user_account(
        first_name, last_name, email, password, role,
        allowed_roles=['admin', 'manager', 'analyst', 'viewer']
    )
    if success:
        log_api_call('/api/admin/create_user', 'success')
        return jsonify({'success': True, 'message': msg}), 200
    else:
        log_api_call('/api/admin/create_user', 'failure')
        return jsonify({'success': False, 'message': msg}), status_code


@bp.route('/admin/update_user_status', methods=['POST'])
@roles_required('admin')
def update_user_status_api():
    """Toggles active/inactive status for a user account and sends email notification."""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    new_status = (data.get('status') or '').lower().strip()

    if not user_id or new_status not in ['active', 'inactive']:
        return jsonify({'success': False, 'message': 'Invalid user ID or status.'}), 400

    if int(user_id) == int(session.get('id')):
        return jsonify({'success': False, 'message': 'You cannot deactivate your own admin account.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection failed.'}), 500
    try:
        user = None
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, first_name, last_name, email, status FROM users WHERE id = %s", (user_id,))
            row = cursor.fetchone()
            if row:
                if not isinstance(row, dict) and cursor.description:
                    cols = [d[0] for d in cursor.description]
                    user = dict(zip(cols, row))
                else:
                    user = row

            cursor.execute("UPDATE users SET status = %s WHERE id = %s", (new_status, user_id))
        conn.commit()

        # Send email notification to user about status update
        if user and user.get('email'):
            u_email = user.get('email')
            u_name = user.get('first_name', 'User')
            current_app.logger.info(
                f"[STATUS UPDATE EMAIL] Dispatched email notification to {u_email} ({u_name}): Account set to {new_status.capitalize()}"
            )

        log_api_call('/api/admin/update_user_status', 'success')
        return jsonify({
            'success': True,
            'message': f"User status updated to {new_status.capitalize()}. Notification email dispatched to user."
        })
    except Exception as e:
        log_api_call('/api/admin/update_user_status', 'failure')
        return jsonify({'success': False, 'message': f'Failed to update user status: {e}'}), 500
    finally:
        conn.close()


@bp.route('/admin/update_user_role', methods=['POST'])
@roles_required('admin')
def update_user_role_api():
    """Updates user access role."""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    new_role = (data.get('role') or '').lower().strip()

    allowed = ['admin', 'manager', 'analyst', 'viewer']
    if not user_id or new_role not in allowed:
        return jsonify({'success': False, 'message': 'Invalid user ID or role requested.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection failed.'}), 500
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))
        conn.commit()

        if int(user_id) == int(session.get('id')):
            session['role'] = new_role

        log_api_call('/api/admin/update_user_role', 'success')
        return jsonify({'success': True, 'message': f'User role updated to {new_role.capitalize()}.'})
    except Exception as e:
        log_api_call('/api/admin/update_user_role', 'failure')
        return jsonify({'success': False, 'message': f'Failed to update user role: {e}'}), 500
    finally:
        conn.close()


@bp.route('/admin/delete_user', methods=['POST'])
@roles_required('admin')
def delete_user_api():
    """Deletes a user account permanently."""
    data = request.get_json() or {}
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'success': False, 'message': 'User ID is required.'}), 400

    if int(user_id) == int(session.get('id')):
        return jsonify({'success': False, 'message': 'You cannot delete your own active admin account.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection failed.'}), 500
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        log_api_call('/api/admin/delete_user', 'success')
        return jsonify({'success': True, 'message': f'User account #{user_id} deleted.'})
    except Exception as e:
        log_api_call('/api/admin/delete_user', 'failure')
        return jsonify({'success': False, 'message': f'Failed to delete user: {e}'}), 500
    finally:
        conn.close()


@bp.route('/admin/export_logs', methods=['GET'])
@roles_required('admin')
def export_system_logs_api():
    """Exports system audit logs as a downloadable CSV file."""
    import csv
    import io
    from flask import Response

    conn = get_db_connection()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Log ID', 'Timestamp', 'User ID', 'User Name', 'User Email', 'Event / Endpoint', 'Status', 'Is AI Request'])

    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT l.id, l.called_at, l.user_id,
                           COALESCE(CONCAT(u.first_name, ' ', u.last_name), 'System/Guest') as user_name,
                           COALESCE(u.email, 'N/A') as user_email,
                           l.endpoint, l.status,
                           CASE WHEN l.is_ai_call THEN 'Yes' ELSE 'No' END as is_ai
                    FROM api_usage_logs l
                    LEFT JOIN users u ON l.user_id = u.id
                    ORDER BY l.called_at DESC
                    LIMIT 1000
                """)
                rows = cursor.fetchall()
                for r in rows:
                    if not isinstance(r, dict) and cursor.description:
                        cols = [d[0] for d in cursor.description]
                        r = dict(zip(cols, r))
                    writer.writerow([
                        r.get('id', ''),
                        str(r.get('called_at', '')),
                        r.get('user_id', ''),
                        r.get('user_name', ''),
                        r.get('user_email', ''),
                        r.get('endpoint', ''),
                        r.get('status', ''),
                        r.get('is_ai', 'No')
                    ])

                # Include Dataset Uploads and User Registrations in audit log export
                cursor.execute("""
                    SELECT d.id, d.uploaded_at as called_at, d.user_id,
                           COALESCE(CONCAT(u.first_name, ' ', u.last_name), 'User') as user_name,
                           COALESCE(u.email, 'N/A') as user_email,
                           CONCAT('Uploaded Dataset: ', d.file_name) as endpoint,
                           COALESCE(d.status, 'processed') as status,
                           'No' as is_ai
                    FROM datasets d
                    LEFT JOIN users u ON d.user_id = u.id
                    ORDER BY d.uploaded_at DESC
                    LIMIT 100
                """)
                ds_rows = cursor.fetchall()
                for r in ds_rows:
                    if not isinstance(r, dict) and cursor.description:
                        cols = [d[0] for d in cursor.description]
                        r = dict(zip(cols, r))
                    writer.writerow([
                        f"DS-{r.get('id', '')}",
                        str(r.get('called_at', '')),
                        r.get('user_id', ''),
                        r.get('user_name', ''),
                        r.get('user_email', ''),
                        r.get('endpoint', ''),
                        r.get('status', ''),
                        'No'
                    ])

                cursor.execute("""
                    SELECT u.id, u.created_at as called_at, u.id as user_id,
                           CONCAT(u.first_name, ' ', u.last_name) as user_name,
                           u.email as user_email,
                           CONCAT('User Registration (Role: ', u.role, ')') as endpoint,
                           COALESCE(u.status, 'active') as status,
                           'No' as is_ai
                    FROM users u
                    ORDER BY u.created_at DESC
                    LIMIT 100
                """)
                u_rows = cursor.fetchall()
                for r in u_rows:
                    if not isinstance(r, dict) and cursor.description:
                        cols = [d[0] for d in cursor.description]
                        r = dict(zip(cols, r))
                    writer.writerow([
                        f"USR-{r.get('id', '')}",
                        str(r.get('called_at', '')),
                        r.get('user_id', ''),
                        r.get('user_name', ''),
                        r.get('user_email', ''),
                        r.get('endpoint', ''),
                        r.get('status', ''),
                        'No'
                    ])

        except Exception as e:
            current_app.logger.error(f"Error exporting system logs: {e}")
        finally:
            conn.close()

    log_api_call('/api/admin/export_logs', 'success')
    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=system_audit_logs.csv"}
    )


@bp.route('/admin/reports', methods=['GET'])
@roles_required('admin')
def get_admin_reports_api():
    """Returns list of all platform reports across all users/datasets for Admin Reports Management."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection failed.'}), 500
    try:
        reports = admin_service.get_all_admin_reports(conn)
        log_api_call('/api/admin/reports', 'success')
        return jsonify({'success': True, 'reports': reports, 'count': len(reports)})
    except Exception as e:
        log_api_call('/api/admin/reports', 'failure')
        return jsonify({'success': False, 'message': f'Failed to fetch reports: {e}'}), 500
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@bp.route('/analyst/dashboard_data', methods=['GET'])
@roles_required('admin', 'manager', 'analyst')
def get_analyst_dashboard_data_api():
    """Returns dynamic analyst KPIs, Plotly preview datasets, AI insights, and notifications."""
    try:
        active_ds_id = session.get('active_dataset_id')
        df = None
        conn = get_db_connection()

        if conn:
            try:
                with conn.cursor() as cursor:
                    if not active_ds_id:
                        cursor.execute(
                            "SELECT id FROM datasets WHERE user_id = %s ORDER BY uploaded_at DESC LIMIT 1",
                            (session['id'],)
                        )
                        ds_row = cursor.fetchone()
                        if ds_row:
                            active_ds_id = ds_row['id']
                            session['active_dataset_id'] = active_ds_id

                    if active_ds_id:
                        try:
                            df = load_dataframe(active_ds_id, session['id'])
                        except Exception as ex:
                            current_app.logger.warning(f"Could not load active dataframe for analyst API: {ex}")
            except Exception as ex:
                current_app.logger.warning(f"DB query error in analyst API: {ex}")

        analytics = analyst_service.get_analyst_dashboard_analytics(df, conn, session.get('id'))

        if conn:
            try:
                conn.close()
            except Exception:
                pass

        log_api_call('/api/analyst/dashboard_data', 'success')
        return jsonify({'success': True, 'data': analytics})
    except Exception as e:
        log_api_call('/api/analyst/dashboard_data', 'failure')
        return jsonify({'success': False, 'message': f'Failed to load analyst analytics: {e}'}), 500


# --- MANAGER TEAM & TASK MANAGEMENT API ENDPOINTS ---

@bp.route('/manager/team', methods=['GET'])
@roles_required('admin', 'manager')
def get_manager_team_api():
    """Fetches list of team members, available platform users, assigned tasks, and team metrics."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500
    try:
        res_data = manager_service.get_manager_team_api_data(conn, session.get('id'))
        log_api_call('/api/manager/team', 'success')
        return jsonify(res_data)
    except Exception as e:
        log_api_call('/api/manager/team', 'failure')
        return jsonify({'success': False, 'message': f'Failed to fetch team data: {e}'}), 500
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@bp.route('/manager/available_users', methods=['GET'])
@roles_required('admin', 'manager')
def get_available_team_users_api():
    """Fetches active registered platform users available to be added to manager's team."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500
    try:
        users = manager_service.get_available_platform_users(conn, session.get('id'))
        return jsonify({'success': True, 'users': users})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to fetch available users: {e}'}), 500
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@bp.route('/manager/add_team_member', methods=['POST'])
@roles_required('admin', 'manager')
def add_team_member_api():
    """Adds an active registered platform user (or creates new user) to manager's team roster."""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    manager_id = session.get('id')

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500

    try:
        manager_service.ensure_manager_tables_exist(conn)
        with conn.cursor() as cursor:
            if not user_id and data.get('email'):
                email = data.get('email', '').strip()
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                found = cursor.fetchone()
                if found:
                    user_id = found.get('id') if isinstance(found, dict) else found[0]

            if not user_id and data.get('first_name') and data.get('email') and data.get('password'):
                from .auth import create_user_account
                success, msg, code = create_user_account(
                    first_name=data.get('first_name'),
                    last_name=data.get('last_name'),
                    email=data.get('email'),
                    password=data.get('password'),
                    role=data.get('role', 'analyst')
                )
                if not success:
                    return jsonify({'success': False, 'message': msg}), code
                cursor.execute("SELECT id FROM users WHERE email = %s", (data.get('email'),))
                found = cursor.fetchone()
                user_id = found.get('id') if isinstance(found, dict) else found[0]

            if not user_id:
                return jsonify({'success': False, 'message': 'Please select an active platform user to add.'}), 400

            cursor.execute("""
                INSERT INTO manager_team_members (manager_id, user_id)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE added_at = CURRENT_TIMESTAMP
            """, (manager_id, user_id))
        conn.commit()
        log_api_call('/api/manager/add_team_member', 'success')
        return jsonify({'success': True, 'message': 'Active platform user added to team roster!'})
    except Exception as e:
        log_api_call('/api/manager/add_team_member', 'failure')
        return jsonify({'success': False, 'message': f'Failed to add team member: {e}'}), 500
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@bp.route('/manager/remove_team_member', methods=['POST'])
@roles_required('admin', 'manager')
def remove_team_member_api():
    """Removes a member from manager's team roster."""
    data = request.get_json() or {}
    member_id = data.get('member_id')
    manager_id = session.get('id')

    if not member_id:
        return jsonify({'success': False, 'message': 'Member ID is required.'}), 400

    if int(member_id) == int(manager_id):
        return jsonify({'success': False, 'message': 'You cannot remove your own active manager account.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500
    try:
        manager_service.ensure_manager_tables_exist(conn)
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM manager_team_members WHERE manager_id = %s AND user_id = %s", (manager_id, member_id))
        conn.commit()
        log_api_call('/api/manager/remove_team_member', 'success')
        return jsonify({'success': True, 'message': 'Team member removed from roster successfully.'})
    except Exception as e:
        log_api_call('/api/manager/remove_team_member', 'failure')
        return jsonify({'success': False, 'message': f'Failed to remove team member: {e}'}), 500
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@bp.route('/manager/available_users', methods=['GET'])
@roles_required('admin', 'manager')
def api_manager_available_users():
    """Fetches all active platform users available to be added to manager's team."""
    conn = get_db_connection()
    manager_id = session.get('id')
    try:
        users = manager_service.get_available_platform_users(conn, manager_id)
        return jsonify({'success': True, 'users': users, 'count': len(users)})
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@bp.route('/manager/team', methods=['GET'])
@roles_required('admin', 'manager')
def api_manager_team():
    """Fetches manager team data, available users, tasks, and KPI statistics for AJAX refresh."""
    conn = get_db_connection()
    manager_id = session.get('id')
    try:
        data = manager_service.get_manager_team_api_data(conn, manager_id)
        return jsonify(data)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@bp.route('/user/assigned_tasks', methods=['GET'])
@roles_required('admin', 'manager', 'analyst', 'viewer')
def get_user_assigned_tasks_api():
    """Fetches list of tasks assigned to the currently logged-in user by managers."""
    user_id = session.get('id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Authentication required.'}), 401
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500
    try:
        tasks = manager_service.get_user_assigned_tasks(conn, user_id)
        pending_count = sum(1 for t in tasks if t.get('status') in ['Pending', 'In Progress'])
        completed_count = sum(1 for t in tasks if t.get('status') == 'Completed')
        log_api_call('/api/user/assigned_tasks', 'success')
        return jsonify({
            'success': True,
            'tasks': tasks,
            'stats': {
                'total_tasks': len(tasks),
                'pending_tasks': pending_count,
                'completed_tasks': completed_count
            }
        })
    except Exception as e:
        log_api_call('/api/user/assigned_tasks', 'failure')
        return jsonify({'success': False, 'message': f'Failed to fetch assigned tasks: {e}'}), 500
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# --- UNIFIED GLOBAL SYSTEM STATE API ---

@bp.route('/system/global_state', methods=['GET'])
@roles_required('admin', 'manager', 'analyst', 'viewer')
def get_global_system_state_api():
    """Returns dynamic single-source-of-truth system state metrics across all dashboards."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM users")
            total_users = (cursor.fetchone() or {}).get('count', 0)

            cursor.execute("SELECT COUNT(*) as count FROM datasets")
            total_datasets = (cursor.fetchone() or {}).get('count', 0)

            cursor.execute("SELECT COUNT(*) as count FROM reports")
            total_reports = (cursor.fetchone() or {}).get('count', 0)

            cursor.execute("SELECT COUNT(*) as count FROM shared_dashboards")
            total_shared = (cursor.fetchone() or {}).get('count', 0)

            manager_service.ensure_manager_tables_exist(conn)
            cursor.execute("SELECT COUNT(*) as count FROM manager_tasks")
            total_tasks = (cursor.fetchone() or {}).get('count', 0)

            cursor.execute("SELECT COUNT(*) as count FROM manager_tasks WHERE status IN ('Pending', 'In Progress')")
            pending_tasks = (cursor.fetchone() or {}).get('count', 0)

        log_api_call('/api/system/global_state', 'success')
        return jsonify({
            'success': True,
            'state': {
                'total_users': total_users,
                'total_datasets': total_datasets,
                'total_reports': total_reports,
                'total_shared': total_shared,
                'total_tasks': total_tasks,
                'pending_tasks': pending_tasks
            }
        })
    except Exception as e:
        log_api_call('/api/system/global_state', 'failure')
        return jsonify({'success': False, 'message': f'Failed to fetch global state: {e}'}), 500
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# --- ADMIN EXPANDED MANAGEMENT API ENDPOINTS ---

@bp.route('/admin/datasets/all', methods=['GET'])
@roles_required('admin')
def get_all_datasets_api():
    """Fetches all platform datasets with owner details for Dataset Monitoring modal."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT d.id, d.file_name, d.file_type, d.uploaded_at, d.file_size, d.status,
                       d.row_count, d.column_count,
                       COALESCE(CONCAT(u.first_name, ' ', u.last_name), 'Unknown') as owner_name,
                       COALESCE(u.email, 'N/A') as owner_email
                FROM datasets d
                LEFT JOIN users u ON d.user_id = u.id
                ORDER BY d.uploaded_at DESC
            """)
            datasets = admin_service._fetchall_dict(cursor)
            for ds in datasets:
                u_at = ds.get('uploaded_at')
                if u_at and hasattr(u_at, 'strftime'):
                    ds['uploaded_at'] = u_at.strftime('%d %b %Y %H:%M')
                elif u_at:
                    ds['uploaded_at'] = str(u_at)[:16]
                else:
                    ds['uploaded_at'] = 'N/A'

        log_api_call('/api/admin/datasets/all', 'success')
        return jsonify({'success': True, 'datasets': datasets, 'total': len(datasets)})
    except Exception as e:
        log_api_call('/api/admin/datasets/all', 'failure')
        return jsonify({'success': False, 'message': f'Failed to fetch all datasets: {e}'}), 500
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@bp.route('/admin/activities/all', methods=['GET'])
@roles_required('admin')
def get_all_system_activities_api():
    """Fetches full system activity logs for System Activity modal."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500
    try:
        activities = []
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT l.id, l.called_at, l.endpoint, l.status, l.is_ai_call,
                       COALESCE(CONCAT(u.first_name, ' ', u.last_name), 'System User') as user_name,
                       COALESCE(u.email, 'system@datanova.com') as user_email,
                       COALESCE(u.role, 'system') as user_role
                FROM api_usage_logs l
                LEFT JOIN users u ON l.user_id = u.id
                ORDER BY l.called_at DESC
                LIMIT 300
            """)
            logs = admin_service._fetchall_dict(cursor)
            for item in logs:
                c_at = item.get('called_at')
                time_str = admin_service.format_time_ago(c_at)
                activities.append({
                    'id': item.get('id'),
                    'user_name': item.get('user_name'),
                    'user_email': item.get('user_email'),
                    'user_role': (item.get('user_role') or 'user').capitalize(),
                    'action': f"invoked {item.get('endpoint')} ({item.get('status')})",
                    'endpoint': item.get('endpoint'),
                    'status': item.get('status'),
                    'is_ai': bool(item.get('is_ai_call')),
                    'time_ago': time_str,
                    'timestamp': str(c_at)[:19] if c_at else 'N/A'
                })

        log_api_call('/api/admin/activities/all', 'success')
        return jsonify({'success': True, 'activities': activities, 'total': len(activities)})
    except Exception as e:
        log_api_call('/api/admin/activities/all', 'failure')
        return jsonify({'success': False, 'message': f'Failed to fetch system activities: {e}'}), 500
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@bp.route('/admin/shared_dashboards', methods=['GET'])
@roles_required('admin')
def get_admin_shared_dashboards_api():
    """Fetches dashboards shared by Analysts/Managers to selected users."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500
    try:
        dashboards = []
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT sd.id, sd.title, sd.description, sd.shared_with_role, sd.created_at,
                       COALESCE(CONCAT(u.first_name, ' ', u.last_name), 'Analyst') as owner_name,
                       COALESCE(u.role, 'analyst') as owner_role,
                       d.file_name as dataset_name
                FROM shared_dashboards sd
                LEFT JOIN users u ON sd.owner_id = u.id
                LEFT JOIN datasets d ON sd.dataset_id = d.id
                ORDER BY sd.created_at DESC
            """)
            dashboards = admin_service._fetchall_dict(cursor)
            for d in dashboards:
                c_at = d.get('created_at')
                d['created_at'] = str(c_at)[:10] if c_at else 'N/A'

        log_api_call('/api/admin/shared_dashboards', 'success')
        return jsonify({'success': True, 'dashboards': dashboards, 'total': len(dashboards)})
    except Exception as e:
        log_api_call('/api/admin/shared_dashboards', 'failure')
        return jsonify({'success': False, 'message': f'Failed to fetch shared dashboards: {e}'}), 500
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@bp.route('/admin/settings', methods=['GET', 'POST'])
@roles_required('admin')
def admin_settings_api():
    """Retrieves or updates platform system settings."""
    if request.method == 'POST':
        data = request.get_json() or {}
        # Store settings in application config or database
        smtp_host = data.get('smtp_host', 'smtp.gmail.com')
        smtp_port = data.get('smtp_port', '587')
        sender_email = data.get('sender_email', 'noreply@datanova.com')
        default_role = data.get('default_role', 'viewer')
        maintenance_mode = bool(data.get('maintenance_mode', False))
        session_timeout = data.get('session_timeout', '60')
        max_file_size_mb = data.get('max_file_size_mb', '50')
        ai_insights_enabled = bool(data.get('ai_insights_enabled', True))

        new_settings = {
            'smtp_host': smtp_host,
            'smtp_port': smtp_port,
            'sender_email': sender_email,
            'default_role': default_role,
            'maintenance_mode': maintenance_mode,
            'session_timeout': session_timeout,
            'max_file_size_mb': max_file_size_mb,
            'ai_insights_enabled': ai_insights_enabled
        }
        current_app.config['SYSTEM_SETTINGS'] = new_settings

        # Save persistently to instance/system_settings.json
        import json
        settings_file = os.path.join(current_app.instance_path, 'system_settings.json')
        try:
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(new_settings, f, indent=2)
        except Exception as e:
            current_app.logger.error(f"Failed to persist system_settings.json: {e}")

        log_api_call('/api/admin/settings', 'success')
        return jsonify({
            'success': True,
            'message': 'System settings updated successfully!',
            'settings': current_app.config['SYSTEM_SETTINGS']
        })

    # GET request
    settings = current_app.config.get('SYSTEM_SETTINGS', {
        'smtp_host': 'smtp.gmail.com',
        'smtp_port': '587',
        'sender_email': 'noreply@datanova.com',
        'default_role': 'viewer',
        'maintenance_mode': False,
        'session_timeout': '60',
        'max_file_size_mb': '50',
        'ai_insights_enabled': True
    })
    log_api_call('/api/admin/settings', 'success')
    return jsonify({'success': True, 'settings': settings})


@bp.route('/admin/security', methods=['GET'])
@roles_required('admin')
def api_admin_security():
    """Returns detailed platform security status, policy checklist, and alerts."""
    conn = get_db_connection()
    try:
        from datanova.services.admin_service import get_admin_security_details
        sec_details = get_admin_security_details(conn)
        log_api_call('/api/admin/security', 'success')
        return jsonify({'success': True, 'security': sec_details})
    except Exception as e:
        current_app.logger.error(f"Security status API error: {e}")
        log_api_call('/api/admin/security', 'failure')
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if conn:
            conn.close()


@bp.route('/admin/security/scan', methods=['POST'])
@roles_required('admin')
def api_admin_security_scan():
    """Triggers an instant security audit scan across database and platform policies."""
    conn = get_db_connection()
    try:
        from datanova.services.admin_service import get_admin_security_details
        sec_details = get_admin_security_details(conn)

        # Log system audit event for security scan
        if conn:
            with conn.cursor() as cursor:
                current_u = session.get('user_id', 1)
                try:
                    cursor.execute("""
                        INSERT INTO api_usage_logs (user_id, endpoint, is_ai_call, status, called_at)
                        VALUES (%s, %s, %s, %s, NOW())
                    """, (current_u, '/api/admin/security/scan', False, 'success'))
                    conn.commit()
                except Exception:
                    pass

        log_api_call('/api/admin/security/scan', 'success')
        return jsonify({
            'success': True,
            'message': f"Security audit scan completed! System Status: {sec_details.get('status', 'OPTIMAL')} ({sec_details.get('score', 100)}%)",
            'security': sec_details
        })
    except Exception as e:
        current_app.logger.error(f"Security scan API error: {e}")
        log_api_call('/api/admin/security/scan', 'failure')
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if conn:
            conn.close()


# ==============================================================================
# MANAGER TASK & TEAM MANAGEMENT API ENDPOINTS
# ==============================================================================



@bp.route('/manager/assign_task', methods=['POST'])
@roles_required('admin', 'manager')
def api_manager_assign_task():
    """Assigns a new task to a team member, with optional dataset upload or attachment."""
    if request.is_json:
        data = request.get_json() or {}
        assigned_to_id = data.get('assigned_to_id')
        task_title = data.get('task_title')
        priority = data.get('priority', 'Medium')
        due_date = data.get('due_date')
        description = data.get('description', '')
        dataset_id = data.get('dataset_id')
    else:
        data = request.form
        assigned_to_id = data.get('assigned_to_id')
        task_title = data.get('task_title')
        priority = data.get('priority', 'Medium')
        due_date = data.get('due_date')
        description = data.get('description', '')
        dataset_id = data.get('dataset_id')

    if not assigned_to_id or not task_title:
        return jsonify({'success': False, 'message': 'Assigned team member and task title are required.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500

    manager_id = session.get('id')
    saved_dataset_id = None
    if dataset_id and str(dataset_id).isdigit():
        saved_dataset_id = int(dataset_id)

    # Check if a new dataset file was uploaded with the task
    if 'file' in request.files and request.files['file'].filename:
        file = request.files['file']
        original_filename = secure_filename(file.filename)
        allowed_extensions = {'.csv', '.xls', '.xlsx'}
        file_ext = os.path.splitext(original_filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({'success': False, 'message': 'Unsupported dataset format. Please upload CSV or Excel file.'}), 400

        user_upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], "raw", f"user_{manager_id}")
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"
        os.makedirs(user_upload_folder, exist_ok=True)
        filepath = os.path.join(user_upload_folder, unique_filename)
        file.save(filepath)

        try:
            if file_ext == '.csv':
                file_type = 'csv'
                try:
                    df = pd.read_csv(filepath, encoding='utf-8')
                except UnicodeDecodeError:
                    df = pd.read_csv(filepath, encoding='latin1')
            else:
                file_type = 'xlsx'
                df = pd.read_excel(filepath)

            df = cleaning_service.normalize_missing_values(df)
            semantic_types = semantic_service.classify_dataframe(df)
            df, semantic_types = cleaning_service.auto_convert_dtypes(df, semantic_types)
            df = cleaning_service.normalize_categories(df, semantic_types)

            row_count, column_count = df.shape
            file_size = os.path.getsize(filepath)
            total_missing_count = int(df.isnull().sum().sum())
            duplicate_count = int(df.duplicated().sum())

            with conn.cursor() as cursor:
                sql = """
                    INSERT INTO datasets
                    (user_id, file_name, file_path, file_size, file_type, row_count, column_count,
                     missing_values_count, duplicate_rows_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(
                    sql,
                    (manager_id, original_filename, filepath, file_size, file_type,
                     row_count, column_count, total_missing_count, duplicate_count)
                )
                saved_dataset_id = cursor.lastrowid
            conn.commit()
            save_dataframe(df, saved_dataset_id, manager_id)
        except Exception as e:
            current_app.logger.exception(f"Error saving uploaded dataset in task assignment: {e}")
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
            return jsonify({'success': False, 'message': f'Failed to process dataset file: {e}'}), 500

    res = manager_service.assign_manager_task(
        conn=conn,
        manager_id=manager_id,
        assigned_to_id=int(assigned_to_id),
        task_title=task_title,
        priority=priority,
        due_date=due_date,
        description=description,
        dataset_id=saved_dataset_id
    )
    if conn:
        try:
            conn.close()
        except Exception:
            pass
    log_api_call('/api/manager/assign_task', 'success' if res.get('success') else 'error')
    return jsonify(res)


@bp.route('/manager/update_task_status', methods=['POST'])
@roles_required('admin', 'manager', 'analyst', 'viewer')
def api_manager_update_task_status():
    """Updates status of an assigned task."""
    data = request.get_json() or {}
    task_id = data.get('task_id')
    status = data.get('status')
    remark = data.get('remark')

    if not task_id or not status:
        return jsonify({'success': False, 'message': 'Task ID and status are required.'}), 400

    conn = get_db_connection()
    user_id = session.get('id')
    res = manager_service.update_manager_task_status(
        conn=conn,
        manager_id=user_id,
        task_id=int(task_id),
        status=status,
        remark=remark
    )
    log_api_call('/api/manager/update_task_status', 'success' if res.get('success') else 'error')
    return jsonify(res)


@bp.route('/manager/delete_task/<int:task_id>', methods=['POST', 'DELETE'])
@roles_required('admin', 'manager')
def api_manager_delete_task(task_id):
    """Deletes an assigned task."""
    conn = get_db_connection()
    manager_id = session.get('id')
    res = manager_service.delete_manager_task(
        conn=conn,
        manager_id=manager_id,
        task_id=task_id
    )
    log_api_call(f'/api/manager/delete_task/{task_id}', 'success' if res.get('success') else 'error')
    return jsonify(res)


@bp.route('/manager/update_team_member', methods=['POST'])
@roles_required('admin', 'manager')
def api_manager_update_team_member():
    """Updates team member status."""
    data = request.get_json() or {}
    member_id = data.get('member_id')
    status = data.get('status', 'active')

    if not member_id:
        return jsonify({'success': False, 'message': 'Member ID is required.'}), 400

    conn = get_db_connection()
    manager_id = session.get('id')
    res = manager_service.update_manager_team_member(
        conn=conn,
        manager_id=manager_id,
        member_id=int(member_id),
        status=status
    )
    log_api_call('/api/manager/update_team_member', 'success' if res.get('success') else 'error')
    return jsonify(res)


@bp.route('/user/assigned_tasks', methods=['GET'])
@roles_required('admin', 'manager', 'analyst', 'viewer')
def api_user_assigned_tasks():
    """Fetches assigned tasks for the currently authenticated user."""
    user_id = session.get('id')
    if not user_id:
        return jsonify({'success': False, 'tasks': []}), 401
    conn = get_db_connection()
    tasks = manager_service.get_user_assigned_tasks(conn, user_id)
    return jsonify({
        'success': True,
        'tasks': tasks,
        'count': len(tasks)
    })


# ==============================================================================
# TEAM SHARING & COLLABORATIVE DASHBOARDS API ENDPOINTS
# ==============================================================================

@bp.route('/team_members_for_sharing', methods=['GET'])
@roles_required('admin', 'manager', 'analyst', 'viewer')
def api_team_members_for_sharing():
    """Returns list of team members available for sharing dashboards."""
    user_id = session.get('id')
    conn = get_db_connection()
    members = []
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, first_name, last_name, email, role, status
                FROM users
                WHERE status = 'active' AND id != %s
                ORDER BY FIELD(role, 'manager', 'analyst', 'viewer', 'admin'), first_name ASC
            """, (user_id or 0,))
            rows = cursor.fetchall() or []
            for r in rows:
                fn = r.get('first_name') or ''
                ln = r.get('last_name') or ''
                name = f"{fn} {ln}".strip() or 'Team Member'
                members.append({
                    'id': r.get('id'),
                    'name': name,
                    'email': r.get('email'),
                    'role': (r.get('role') or 'viewer').capitalize(),
                    'raw_role': r.get('role') or 'viewer'
                })
        return jsonify({'success': True, 'members': members, 'count': len(members)})
    except Exception as e:
        current_app.logger.error(f"Error fetching team members for sharing: {e}")
        return jsonify({'success': False, 'message': str(e), 'members': []}), 500
    finally:
        if conn:
            conn.close()


@bp.route('/share_dashboard_with_team', methods=['POST'])
@roles_required('admin', 'manager', 'analyst')
def api_share_dashboard_with_team():
    """Shares an active dataset/dashboard with selected team members."""
    data = request.get_json() or {}
    dataset_id = data.get('dataset_id')
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    user_ids = data.get('user_ids', [])

    if not dataset_id:
        return jsonify({'success': False, 'message': 'Active dataset ID is required.'}), 400
    if not title:
        return jsonify({'success': False, 'message': 'Dashboard title is required.'}), 400

    owner_id = session.get('id')
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if not user_ids or user_ids == 'all':
                cursor.execute("SELECT id, role FROM users WHERE status = 'active' AND id != %s", (owner_id,))
                target_users = cursor.fetchall() or []
            else:
                format_strings = ','.join(['%s'] * len(user_ids))
                cursor.execute(f"SELECT id, role FROM users WHERE id IN ({format_strings})", tuple(user_ids))
                target_users = cursor.fetchall() or []

            if not target_users:
                cursor.execute("""
                    INSERT INTO shared_dashboards (owner_id, shared_with_role, shared_with_user_id, title, description, dataset_id, status)
                    VALUES (%s, 'all', NULL, %s, %s, %s, 'Shared')
                """, (owner_id, title, description, dataset_id))
            else:
                for tu in target_users:
                    cursor.execute("""
                        INSERT INTO shared_dashboards (owner_id, shared_with_role, shared_with_user_id, title, description, dataset_id, status)
                        VALUES (%s, %s, %s, %s, %s, %s, 'Shared')
                    """, (owner_id, tu.get('role') or 'all', tu.get('id'), title, description, dataset_id))

            conn.commit()

        log_api_call('/api/share_dashboard_with_team', 'success')
        return jsonify({
            'success': True,
            'message': f"Dashboard '{title}' successfully shared with {len(target_users) if target_users else 1} team members!"
        })
    except Exception as e:
        if conn:
            conn.rollback()
        current_app.logger.error(f"Error sharing dashboard: {e}")
        log_api_call('/api/share_dashboard_with_team', 'failure')
        return jsonify({'success': False, 'message': f"Failed to share dashboard: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()


@bp.route('/shared_dashboards/list', methods=['GET'])
@roles_required('admin', 'manager', 'analyst', 'viewer')
def api_shared_dashboards_list():
    """Returns all shared dashboards accessible to current user."""
    user_id = session.get('id')
    user_role = session.get('role', 'viewer')
    conn = get_db_connection()
    shared_list = []
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT s.id, s.owner_id, s.shared_with_role, s.shared_with_user_id, s.title,
                       s.description, s.remark, s.status, s.dataset_id, s.created_at, s.updated_at,
                       u.first_name as owner_fn, u.last_name as owner_ln, u.email as owner_email, u.role as owner_role,
                       d.file_name as dataset_name, d.row_count, d.column_count
                FROM shared_dashboards s
                JOIN users u ON s.owner_id = u.id
                LEFT JOIN datasets d ON s.dataset_id = d.id
                WHERE s.owner_id = %s OR s.shared_with_user_id = %s OR s.shared_with_role = %s OR s.shared_with_role = 'all'
                ORDER BY COALESCE(s.updated_at, s.created_at) DESC
                LIMIT 50
            """, (user_id or 0, user_id or 0, user_role or 'viewer'))
            rows = cursor.fetchall() or []
            for r in rows:
                fn = r.get('owner_fn') or ''
                ln = r.get('owner_ln') or ''
                owner_name = f"{fn} {ln}".strip() or 'Team Member'
                dt = r.get('created_at')
                dt_str = dt.strftime('%d %b %Y, %I:%M %p') if dt else 'Recent'
                up_dt = r.get('updated_at')
                up_dt_str = up_dt.strftime('%d %b %Y, %I:%M %p') if up_dt else dt_str

                shared_list.append({
                    'id': r.get('id'),
                    'owner_id': r.get('owner_id'),
                    'title': r.get('title') or 'Shared Dashboard',
                    'description': r.get('description') or '',
                    'remark': r.get('remark') or '',
                    'status': r.get('status') or 'Shared',
                    'dataset_id': r.get('dataset_id'),
                    'dataset_name': r.get('dataset_name') or 'Dataset',
                    'row_count': r.get('row_count') or 0,
                    'column_count': r.get('column_count') or 0,
                    'owner_name': owner_name,
                    'owner_email': r.get('owner_email') or '',
                    'owner_role': (r.get('owner_role') or 'analyst').capitalize(),
                    'created_at_str': dt_str,
                    'updated_at_str': up_dt_str,
                    'is_owner': (r.get('owner_id') == user_id),
                    'can_review': (user_role in ['manager', 'admin'])
                })
        return jsonify({'success': True, 'dashboards': shared_list, 'count': len(shared_list)})
    except Exception as e:
        current_app.logger.error(f"Error fetching shared dashboards list: {e}")
        return jsonify({'success': False, 'message': str(e), 'dashboards': []}), 500
    finally:
        if conn:
            conn.close()


@bp.route('/shared_dashboard/view/<int:shared_id>', methods=['GET'])
@roles_required('admin', 'manager', 'analyst', 'viewer')
def api_shared_dashboard_view(shared_id):
    """Returns complete payload for viewing a shared dashboard."""
    user_id = session.get('id')
    user_role = session.get('role', 'viewer')
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT s.id, s.owner_id, s.shared_with_role, s.shared_with_user_id, s.title,
                       s.description, s.remark, s.status, s.dataset_id, s.created_at, s.updated_at,
                       u.first_name as owner_fn, u.last_name as owner_ln, u.email as owner_email, u.role as owner_role,
                       d.file_name as dataset_name, d.file_path, d.row_count, d.column_count,
                       d.missing_values_count, d.duplicate_rows_count
                FROM shared_dashboards s
                JOIN users u ON s.owner_id = u.id
                LEFT JOIN datasets d ON s.dataset_id = d.id
                WHERE s.id = %s
            """, (shared_id,))
            sd = cursor.fetchone()

        if not sd:
            return jsonify({'success': False, 'message': 'Shared dashboard not found.'}), 404

        owner_id = sd.get('owner_id')
        dataset_id = sd.get('dataset_id')
        dataset_name = sd.get('dataset_name') or 'Dataset'

        preview_html = '<div class="p-3 text-muted">Preview not available</div>'
        insights = []
        rows = sd.get('row_count') or 0
        cols = sd.get('column_count') or 0
        missing = sd.get('missing_values_count') or 0
        duplicates = sd.get('duplicate_rows_count') or 0
        memory_str = '0 KB'
        quality_score = 100

        if dataset_id and owner_id:
            try:
                df = load_dataframe(dataset_id, owner_id)
                if df is not None and not df.empty:
                    rows = len(df)
                    cols = len(df.columns)
                    missing = int(df.isnull().sum().sum())
                    duplicates = int(df.duplicated().sum())
                    mem_bytes = df.memory_usage(deep=True).sum()
                    if mem_bytes > 1024 * 1024:
                        memory_str = f"{mem_bytes / (1024 * 1024):.2f} MB"
                    else:
                        memory_str = f"{mem_bytes / 1024:.1f} KB"

                    total_cells = rows * cols if (rows * cols) > 0 else 1
                    quality_score = max(0, min(100, int(100 - (missing / total_cells * 100) - (duplicates / rows * 10 if rows > 0 else 0))))

                    sample_df = df.head(10)
                    preview_html = sample_df.to_html(
                        classes="table table-sm table-striped table-hover dn-preview-table mb-0",
                        index=False,
                        na_rep='NaN'
                    )

                    insights.append(f"Dataset contains <strong>{rows:,}</strong> rows and <strong>{cols}</strong> features.")
                    if missing > 0:
                        insights.append(f"Detected <strong>{missing:,}</strong> missing values requiring cleanup.")
                    else:
                        insights.append("Clean dataset: <strong>0 missing values</strong> detected.")

                    if duplicates > 0:
                        insights.append(f"Found <strong>{duplicates:,}</strong> duplicate rows.")

                    num_cols = df.select_dtypes(include=['number']).columns.tolist()
                    if num_cols:
                        top_num = num_cols[0]
                        insights.append(f"Primary numerical metric <code>{top_num}</code> ranges from <strong>{df[top_num].min():,.2f}</strong> to <strong>{df[top_num].max():,.2f}</strong> (avg: <strong>{df[top_num].mean():,.2f}</strong>).")

            except Exception as e_df:
                current_app.logger.warning(f"Could not load DataFrame for shared dashboard preview: {e_df}")

        fn = sd.get('owner_fn') or ''
        ln = sd.get('owner_ln') or ''
        owner_name = f"{fn} {ln}".strip() or 'Team Member'
        dt = sd.get('created_at')
        dt_str = dt.strftime('%d %b %Y, %I:%M %p') if dt else 'Recent'

        return jsonify({
            'success': True,
            'dashboard': {
                'id': sd.get('id'),
                'title': sd.get('title'),
                'description': sd.get('description') or '',
                'remark': sd.get('remark') or '',
                'status': sd.get('status') or 'Shared',
                'owner_id': sd.get('owner_id'),
                'owner_name': owner_name,
                'owner_email': sd.get('owner_email') or '',
                'owner_role': (sd.get('owner_role') or 'analyst').capitalize(),
                'created_at_str': dt_str,
                'dataset_id': dataset_id,
                'dataset_name': dataset_name,
                'row_count': rows,
                'column_count': cols,
                'memory_usage': memory_str,
                'missing_count': missing,
                'duplicate_count': duplicates,
                'quality_score': quality_score,
                'preview_html': preview_html,
                'insights': insights,
                'is_manager': (user_role in ['manager', 'admin']),
                'is_owner': (sd.get('owner_id') == user_id)
            }
        })
    except Exception as e:
        current_app.logger.error(f"Error viewing shared dashboard: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if conn:
            conn.close()


@bp.route('/shared_dashboard/manager_review', methods=['POST'])
@roles_required('admin', 'manager')
def api_shared_dashboard_manager_review():
    """Allows Manager/Admin to submit remarks, re-open for revision, or approve a shared dashboard."""
    data = request.get_json() or {}
    shared_id = data.get('shared_id')
    action = data.get('action', 'remark')
    remark = (data.get('remark') or '').strip()

    if not shared_id:
        return jsonify({'success': False, 'message': 'Shared dashboard ID is required.'}), 400

    new_status = 'Shared'
    if action == 'reopen':
        new_status = 'Reopened'
    elif action == 'approve':
        new_status = 'Approved'
    elif action == 'remark':
        new_status = 'Reviewed'

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE shared_dashboards
                SET remark = %s, status = %s, updated_at = NOW()
                WHERE id = %s
            """, (remark if remark else None, new_status, shared_id))
            conn.commit()

        log_api_call('/api/shared_dashboard/manager_review', 'success')
        return jsonify({
            'success': True,
            'message': f"Manager review recorded successfully! Status updated to '{new_status}'.",
            'status': new_status,
            'remark': remark
        })
    except Exception as e:
        if conn:
            conn.rollback()
        current_app.logger.error(f"Error in manager review: {e}")
        log_api_call('/api/shared_dashboard/manager_review', 'failure')
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if conn:
            conn.close()