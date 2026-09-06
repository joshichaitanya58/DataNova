import logging
from typing import Optional, Dict, Any
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def get_analyst_dashboard_analytics(df: Optional[pd.DataFrame] = None, conn=None, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Compiles complete production-ready analyst dashboard analytics, live KPI counts,
    notifications, AI insights, and real Plotly visualization datasets.
    """
    kpi_data = {
        'total_datasets': 0,
        'rows_analyzed': 0,
        'missing_values': 0,
        'duplicates_found': 0,
        'reports_generated': 0,
        'data_quality': 'N/A',
        'notifications': [],
        'ai_insights': [],
        'viz_preview': {
            'bar': {'labels': [], 'values': []},
            'line': {'labels': [], 'values': []},
            'hist': {'values': []},
            'heatmap': {'x': [], 'y': [], 'z': []}
        }
    }

    # 1. Fetch User DB Metrics
    if conn and user_id:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as count FROM datasets WHERE user_id = %s", (user_id,))
                kpi_data['total_datasets'] = (cursor.fetchone() or {}).get('count', 0)

                cursor.execute("SELECT SUM(row_count) as total_rows FROM datasets WHERE user_id = %s", (user_id,))
                kpi_data['rows_analyzed'] = (cursor.fetchone() or {}).get('total_rows') or 0

                cursor.execute("SELECT SUM(missing_values_count) as total_missing FROM datasets WHERE user_id = %s", (user_id,))
                kpi_data['missing_values'] = (cursor.fetchone() or {}).get('total_missing') or 0

                cursor.execute("SELECT SUM(duplicate_rows_count) as total_duplicates FROM datasets WHERE user_id = %s", (user_id,))
                kpi_data['duplicates_found'] = (cursor.fetchone() or {}).get('total_duplicates') or 0

                cursor.execute("SELECT COUNT(*) as count FROM reports WHERE user_id = %s", (user_id,))
                kpi_data['reports_generated'] = (cursor.fetchone() or {}).get('count', 0)

                cursor.execute("SELECT SUM(row_count * column_count) as total_cells FROM datasets WHERE user_id = %s", (user_id,))
                total_cells = (cursor.fetchone() or {}).get('total_cells') or 0
                if total_cells > 0:
                    quality_score = max(0, (1 - (kpi_data['missing_values'] / total_cells)) * 100)
                    kpi_data['data_quality'] = f"{quality_score:.1f}%"

                # Notifications & Assigned Manager Tasks Data Flow
                try:
                    from . import manager_service
                    assigned_tasks = manager_service.get_user_assigned_tasks(conn, user_id)
                    kpi_data['assigned_tasks'] = assigned_tasks
                    kpi_data['pending_tasks_count'] = sum(1 for t in assigned_tasks if t.get('status') in ['Pending', 'In Progress', 'Reopened'])
                    for task in assigned_tasks:
                        st = task.get('status')
                        if st != 'Completed':
                            title = task.get('task_title', 'New Task')
                            mgr = task.get('manager_name', 'Manager')
                            due = task.get('due_date') or 'Flexible'
                            notif_label = f"Task Re-opened by {mgr}" if st == 'Reopened' else f"Task Assigned by {mgr}"
                            kpi_data['notifications'].insert(0, {
                                'icon': 'bi-card-checklist' if st != 'Reopened' else 'bi-arrow-counterclockwise',
                                'text': f"{notif_label}: '{title}' (Due: {due})",
                                'time': 'Action Required'
                            })
                except Exception as ex_t:
                    logger.debug(f"Manager tasks table notice: {ex_t}")

                cursor.execute("SELECT file_name, uploaded_at FROM datasets WHERE user_id = %s ORDER BY uploaded_at DESC LIMIT 3", (user_id,))
                recent_ds = cursor.fetchall() or []
                for ds in recent_ds:
                    if not isinstance(ds, dict) and cursor.description:
                        cols = [d[0] for d in cursor.description]
                        ds = dict(zip(cols, ds))
                    fn = ds.get('file_name', 'Dataset')
                    kpi_data['notifications'].append({
                        'icon': 'bi-check2-circle',
                        'text': f"Dataset '{fn}' successfully processed & ready.",
                        'time': 'Recent'
                    })
        except Exception as e:
            logger.warning(f"Error querying DB for analyst dashboard: {e}")

    # Fallback notification if empty
    if not kpi_data['notifications']:
        kpi_data['notifications'] = [
            {'icon': 'bi-cloud-upload', 'text': 'Upload a dataset to begin automated EDA.', 'time': 'System'}
        ]

    # 2. Analyze Active DataFrame (df)
    if df is not None and not df.empty:
        try:
            num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            cat_cols = df.select_dtypes(include=['object', 'category', 'string']).columns.tolist()

            # Dynamic Automated Statistical Insights from df
            insights = []
            if cat_cols:
                primary_cat = cat_cols[0]
                top_val = df[primary_cat].value_counts().head(1)
                if not top_val.empty:
                    val_name, val_count = top_val.index[0], top_val.values[0]
                    pct = round((val_count / len(df)) * 100, 1)
                    insights.append(f"<b>{primary_cat}</b>: '{val_name}' is the top category ({pct}% of total records).")

            if num_cols:
                primary_num = num_cols[0]
                mean_val = df[primary_num].mean()
                max_val = df[primary_num].max()
                insights.append(f"<b>{primary_num}</b>: Average value is <b>{mean_val:,.2f}</b> with peak at <b>{max_val:,.2f}</b>.")

                if len(num_cols) >= 2:
                    sec_num = num_cols[1]
                    corr_val = df[primary_num].corr(df[sec_num])
                    if not np.isnan(corr_val):
                        corr_str = "strong positive" if corr_val > 0.6 else "negative" if corr_val < -0.4 else "moderate"
                        insights.append(f"Correlation between <b>{primary_num}</b> and <b>{sec_num}</b> is {corr_str} (r = {corr_val:.2f}).")

            total_missing = df.isnull().sum().sum()
            if total_missing > 0:
                insights.append(f"Dataset contains <b>{total_missing} missing values</b> available for smart automated cleaning.")
            else:
                insights.append("Dataset is <b>100% complete</b> with 0 missing cells detected.")

            kpi_data['ai_insights'] = insights

            # Dynamic Real Data Plotly Previews from df
            if cat_cols and num_cols:
                grp = df.groupby(cat_cols[0])[num_cols[0]].sum().reset_index().head(6)
                kpi_data['viz_preview']['bar'] = {
                    'labels': grp[cat_cols[0]].astype(str).tolist(),
                    'values': grp[num_cols[0]].tolist()
                }
            elif cat_cols:
                vc = df[cat_cols[0]].value_counts().head(6)
                kpi_data['viz_preview']['bar'] = {
                    'labels': vc.index.astype(str).tolist(),
                    'values': vc.values.tolist()
                }

            if num_cols:
                primary_num = num_cols[0]
                valid_num = df[primary_num].dropna()

                # Real Line trend chart over record index
                series_vals = valid_num.head(20).tolist()
                kpi_data['viz_preview']['line'] = {
                    'labels': [f"Rec {i+1}" for i in range(len(series_vals))],
                    'values': series_vals
                }
                # Real Histogram distribution values
                kpi_data['viz_preview']['hist'] = {
                    'values': valid_num.tolist()
                }

                # Real Correlation heatmap across numerical columns
                if len(num_cols) >= 2:
                    sub_num = num_cols[:6]
                    corr_df = df[sub_num].corr().fillna(0)
                    kpi_data['viz_preview']['heatmap'] = {
                        'x': sub_num,
                        'y': sub_num,
                        'z': corr_df.values.round(2).tolist()
                    }

        except Exception as e:
            logger.warning(f"Error extracting dynamic insights from DataFrame: {e}")

    # Fallback Automated Insights if empty
    if not kpi_data['ai_insights']:
        kpi_data['ai_insights'] = [
            "Upload a dataset to generate real automated data profiling.",
            "Detect distributions, top performing categories, and key anomalies.",
            "Run automatic correlation matrix calculation across numerical variables."
        ]

    return kpi_data
