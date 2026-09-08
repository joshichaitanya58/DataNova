from flask import Blueprint, request, jsonify, session, current_app, flash, redirect, url_for
import os
import pandas as pd
import numpy as np
import uuid
import random
import json
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from io import BytesIO
import seaborn as sns
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
    analyst_service
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
            missing_info.append({
                'name': col,
                'count': int(count),
                'percentage': round(percentage, 2),
                'semantic_type': col_semantic_type
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
        return jsonify({'success': False, 'message': f'Could not process file: {e}'}), 500

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

    if not dataset_id: 
        log_api_call(request.path, 'failure')
        return jsonify({'success': False, 'message': 'Dataset ID is missing.'}), 400

    try:
        df = load_dataframe(dataset_id, session['id'])
        analysis_result = pipeline_service.analyze_dataset(df, generate_ai=generate_ai)

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
        return record['file_path'] if record else None
    finally:
        if conn:
            conn.close()


def get_processed_path(dataset_id, user_id):
    processed_dir = os.path.join(
        current_app.config['UPLOAD_FOLDER'],
        "processed",
        f"user_{user_id}"
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


def save_dataframe(df, dataset_id, user_id):
    processed_path = get_processed_path(dataset_id, user_id)
    df.to_pickle(processed_path)
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


@bp.route('/ai_suggest_cleaning', methods=['POST'])
@roles_required('admin', 'manager', 'analyst')
def ai_suggest_cleaning():
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

        return jsonify({'success': True, 'message': 'Dataset and all associated files have been deleted.'})

    except Exception as e:
        current_app.logger.exception(f"Error deleting dataset: {e}")
        return jsonify({'success': False, 'message': f'An error occurred: {e}'}), 500
    finally:
        if conn:
            conn.close()


@bp.route('/export_eda_report/<int:dataset_id>', methods=['GET'])
@roles_required('admin', 'manager', 'analyst')
def export_eda_report(dataset_id):
    """
    Generates and downloads a full standalone HTML EDA Report.
    """
    try:
        df = load_dataframe(dataset_id, session['id'])
        analysis_result = pipeline_service.analyze_dataset(df, generate_ai=True)
        report_html = report_service.generate_eda_html_report(analysis_result)

        return current_app.response_class(
            report_html,
            mimetype='text/html',
            headers={"Content-disposition": f"inline; filename=DataNova_EDA_Report_Dataset_{dataset_id}.html"}
        )
    except Exception as e:
        current_app.logger.exception(f"Error generating EDA report for dataset {dataset_id}: {e}")
        return jsonify({'success': False, 'message': f'Could not generate report: {e}'}), 500


@bp.route('/export_pdf/<int:dataset_id>', methods=['GET'])
@roles_required('admin', 'manager', 'analyst')
def export_pdf_report(dataset_id):
    """Generates and downloads a PDF Executive Report using ReportLab."""
    try:
        df = load_dataframe(dataset_id, session['id'])
        analysis_result = pipeline_service.analyze_dataset(df, generate_ai=True)
        pdf_bytes = report_service.generate_pdf_report_bytes(analysis_result)

        return current_app.response_class(
            pdf_bytes,
            mimetype='application/pdf',
            headers={"Content-disposition": f"attachment; filename=DataNova_Report_Dataset_{dataset_id}.pdf"}
        )
    except Exception as e:
        current_app.logger.exception(f"Error generating PDF report for dataset {dataset_id}: {e}")
        return jsonify({'success': False, 'message': f'Could not generate PDF: {e}'}), 500


@bp.route('/export_word/<int:dataset_id>', methods=['GET'])
@roles_required('admin', 'manager', 'analyst')
def export_word_report(dataset_id):
    """Generates and downloads a Microsoft Word (.docx) Report."""
    try:
        df = load_dataframe(dataset_id, session['id'])
        analysis_result = pipeline_service.analyze_dataset(df, generate_ai=True)
        word_bytes = report_service.generate_word_report_bytes(analysis_result)

        return current_app.response_class(
            word_bytes,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            headers={"Content-disposition": f"attachment; filename=DataNova_Report_Dataset_{dataset_id}.docx"}
        )
    except Exception as e:
        current_app.logger.exception(f"Error generating Word report: {e}")
        return jsonify({'success': False, 'message': f'Could not generate Word doc: {e}'}), 500


@bp.route('/export_ppt/<int:dataset_id>', methods=['GET'])
@roles_required('admin', 'manager', 'analyst')
def export_ppt_report(dataset_id):
    """Generates and downloads a PowerPoint (.pptx) Presentation."""
    try:
        df = load_dataframe(dataset_id, session['id'])
        analysis_result = pipeline_service.analyze_dataset(df, generate_ai=True)
        ppt_bytes = report_service.generate_ppt_report_bytes(analysis_result)

        return current_app.response_class(
            ppt_bytes,
            mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
            headers={"Content-disposition": f"attachment; filename=DataNova_Presentation_Dataset_{dataset_id}.pptx"}
        )
    except Exception as e:
        current_app.logger.exception(f"Error generating PPT presentation: {e}")
        return jsonify({'success': False, 'message': f'Could not generate PPT: {e}'}), 500


@bp.route('/export_excel/<int:dataset_id>', methods=['GET'])
@roles_required('admin', 'manager', 'analyst')
def export_excel_report(dataset_id):
    """Generates and downloads a multi-sheet Excel (.xlsx) Report."""
    try:
        df = load_dataframe(dataset_id, session['id'])
        analysis_result = pipeline_service.analyze_dataset(df, generate_ai=True)
        excel_bytes = report_service.generate_excel_report_bytes(df, analysis_result)

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
        plot_base64 = chart_service.generate_custom_chart(df, x_col, y_col, chart_type, agg_func)

        response = {
            'success': True,
            'title': f"{chart_type.capitalize()} Chart: {x_col}" + (f" vs {y_col}" if y_col else ""),
            'plot': plot_base64,
            'chart_type': chart_type
        }
        log_api_call(request.path, 'success')
        return jsonify(response)
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

        outlier_summary = f"Total Outliers Detected: {outliers_report.get('total_outlier_count', 0)}."

        lang_instruction = "Answer in clear, direct English."
        if language == "hi":
            lang_instruction = "उत्तर पूरी तरह से स्पष्ट और सरल हिंदी (हिंदी भाषा) में दें।"
        elif language == "mr":
            lang_instruction = "उत्तर संपूर्णपणे सोप्या आणि स्पष्ट मराठी (मराठी भाषा) मध्ये द्या."

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

        --- Top Category Drivers ---
        {top_bottom_summary}

        --- Correlation Summary ---
        {correlation_summary}

        --- User Question ---
        "{question}"

        Provide a clear, direct, and factual answer based ONLY on the metrics above.
        """

        ai_answer = ai_helper.generate_ai_completion(prompt, expect_json=False)
        log_api_call(request.path, 'success', is_ai_call=True)
        return jsonify({'success': True, 'answer': ai_answer})
    except Exception as e:
        current_app.logger.exception(f"Error in /api/ask_data: {e}")
        log_api_call(request.path, 'failure', is_ai_call=True)
        return jsonify({'success': False, 'message': f'An error occurred while asking the AI: {e}'}), 500

# =========================================================================
# --- ADMIN API ENDPOINTS ---
# =========================================================================

@bp.route('/admin/users', methods=['GET'])
@roles_required('admin')
def admin_get_users():
    """Returns list of all registered users."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, first_name, last_name, email, role, created_at FROM users ORDER BY created_at DESC"
            )
            users = cursor.fetchall()
            for u in users:
                if 'created_at' in u and u['created_at']:
                    u['created_at'] = u['created_at'].strftime('%Y-%m-%d %H:%M')
        return jsonify({'success': True, 'users': users})
    finally:
        conn.close()


@bp.route('/admin/create_user', methods=['POST'])
@roles_required('admin')
def admin_create_user():
    """Creates a new user account with role validation."""
    data = request.get_json() or {}
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'viewer').lower()

    success, msg, status_code = create_user_account(
        first_name=first_name,
        last_name=last_name,
        email=email,
        password=password,
        role=role,
        allowed_roles=ALLOWED_ROLES
    )

    if success:
        return jsonify({'success': True, 'message': f'User "{first_name} {last_name}" created successfully!'})
    else:
        return jsonify({'success': False, 'message': msg}), status_code


@bp.route('/admin/update_user_role', methods=['POST'])
@roles_required('admin')
def admin_update_user_role():
    """Updates role for a specific user after role validation."""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    new_role = str(data.get('role', '')).lower().strip()

    if not user_id or not new_role:
        return jsonify({'success': False, 'message': 'User ID and role are required.'}), 400

    if new_role not in ALLOWED_ROLES:
        return jsonify({'success': False, 'message': 'Invalid role specified.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))
        conn.commit()
        return jsonify({'success': True, 'message': f'User role updated to {new_role}.'})
    finally:
        conn.close()


@bp.route('/admin/delete_user', methods=['POST'])
@roles_required('admin')
def admin_delete_user():
    """Deletes a user account."""
    data = request.get_json() or {}
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'success': False, 'message': 'User ID is required.'}), 400

    if user_id == session['id']:
        return jsonify({'success': False, 'message': 'Cannot delete your own admin account.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        return jsonify({'success': True, 'message': 'User deleted successfully.'})
    finally:
        conn.close()


@bp.route('/admin/export_logs', methods=['GET'])
@roles_required('admin')
def admin_export_logs():
    """Exports API usage logs for security auditing."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT l.id, u.email, l.endpoint, l.status, l.is_ai_call, l.called_at
                FROM api_usage_logs l
                JOIN users u ON l.user_id = u.id
                ORDER BY l.called_at DESC
                LIMIT 500
            """)
            logs = cursor.fetchall()
            for l in logs:
                if 'called_at' in l and l['called_at']:
                    l['called_at'] = str(l['called_at'])

        log_json = json.dumps(logs, indent=2)
        return current_app.response_class(
            log_json,
            mimetype='application/json',
            headers={"Content-disposition": "attachment; filename=DataNova_System_Logs.json"}
        )
    finally:
        conn.close()


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
    """Shares a dashboard/report with other users/roles."""
    data = request.get_json() or {}
    title = data.get('title', 'Shared Analysis')
    shared_with_role = data.get('shared_with_role', 'all')
    dataset_id = session.get('active_dataset_id')

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO shared_dashboards (owner_id, shared_with_role, title, dataset_id) VALUES (%s, %s, %s, %s)",
                (session['id'], shared_with_role, title, dataset_id)
            )
        conn.commit()
        return jsonify({'success': True, 'message': f'Dashboard "{title}" shared successfully with {shared_with_role}!'})
    except Exception as e:
        current_app.logger.exception(f"Share failed: {e}")
        return jsonify({'success': False, 'message': 'An error occurred while sharing the dashboard.'}), 500
    finally:
        conn.close()


# =========================================================================
# --- VIEWER API ENDPOINTS ---
# =========================================================================

@bp.route('/viewer/shared_dashboards', methods=['GET'])
@roles_required('admin', 'manager', 'analyst', 'viewer')
def viewer_shared_dashboards():
    """Returns list of shared dashboards accessible by user (DN-SEC-003)."""
    user_role = session.get('role', 'viewer')
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT s.id, s.title, s.created_at, u.first_name, u.last_name, d.file_name
                FROM shared_dashboards s
                JOIN users u ON s.owner_id = u.id
                LEFT JOIN datasets d ON s.dataset_id = d.id
                WHERE s.owner_id = %s OR s.shared_with_role = %s OR s.shared_with_role = 'all'
                ORDER BY s.created_at DESC LIMIT 10
            """, (session['id'], user_role))
            dashboards = cursor.fetchall()
            for d in dashboards:
                if 'created_at' in d and d['created_at']:
                    d['created_at'] = d['created_at'].strftime('%d %b %Y')
        return jsonify({'success': True, 'dashboards': dashboards})
    finally:
        conn.close()


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


@bp.route('/api/manager/business_metrics', methods=['GET'])
@bp.route('/api/manager/dashboard_data', methods=['GET'])
@roles_required('admin', 'manager')
def get_manager_dashboard_data_api():
    """Returns dynamic business metrics, chart datasets, insights, and predictions for Manager Dashboard."""
    try:
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
                            current_app.logger.warning(f"Could not load dataframe for manager API: {ex}")
            except Exception as ex:
                current_app.logger.warning(f"DB query error in manager API: {ex}")

        analytics = manager_service.get_manager_full_dashboard_analytics(df, conn, session.get('id'))

        if conn:
            try:
                conn.close()
            except Exception:
                pass

        log_api_call('/api/manager/dashboard_data', 'success')
        return jsonify({
            'success': True,
            'metrics': analytics,
            'data': analytics
        })
    except Exception as e:
        log_api_call('/api/manager/dashboard_data', 'failure')
        return jsonify({'success': False, 'message': f'Failed to retrieve manager analytics: {e}'}), 500


@bp.route('/api/viewer/dashboard_data', methods=['GET'])
@roles_required('admin', 'manager', 'analyst', 'viewer')
def get_viewer_dashboard_data_api():
    """Returns dynamic shared dashboards, reports, and analytics for Viewer Dashboard."""
    try:
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