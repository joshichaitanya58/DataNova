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

                cursor.execute("SELECT COUNT(*) as count FROM reports WHERE user_id = %s", (user_id,))
                kpi_data['reports_generated'] = (cursor.fetchone() or {}).get('count', 0)

                # Active Dataset Profile KPI calculations (bind to active df if present, otherwise clean defaults)
                if df is not None and not df.empty:
                    kpi_data['rows_analyzed'] = len(df)
                    kpi_data['missing_values'] = int(df.isnull().sum().sum())
                    kpi_data['duplicates_found'] = int(df.duplicated().sum())
                    total_cells = len(df) * len(df.columns)
                    if total_cells > 0:
                        quality_score = max(0, (1 - (kpi_data['missing_values'] / total_cells)) * 100)
                        kpi_data['data_quality'] = f"{quality_score:.1f}%"
                    else:
                        kpi_data['data_quality'] = 'N/A'
                else:
                    kpi_data['rows_analyzed'] = 0
                    kpi_data['missing_values'] = 0
                    kpi_data['duplicates_found'] = 0
                    kpi_data['data_quality'] = 'N/A'

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

                cursor.execute("SELECT file_name, status, uploaded_at FROM datasets WHERE user_id = %s ORDER BY uploaded_at DESC LIMIT 3", (user_id,))
                recent_ds = cursor.fetchall() or []
                for ds in recent_ds:
                    if not isinstance(ds, dict) and cursor.description:
                        cols = [d[0] for d in cursor.description]
                        ds = dict(zip(cols, ds))
                    fn = ds.get('file_name', 'Dataset')
                    st = (ds.get('status') or 'uploaded').lower()
                    if st in ['ready', 'completed']:
                        msg_str = f"Dataset '{fn}' successfully processed & ready."
                        icon_str = 'bi-check2-circle'
                    elif st in ['error', 'failed']:
                        msg_str = f"Dataset '{fn}' processing encountered an issue."
                        icon_str = 'bi-exclamation-triangle'
                    else:
                        msg_str = f"Dataset '{fn}' status: {st.capitalize()}."
                        icon_str = 'bi-clock-history'

                    kpi_data['notifications'].append({
                        'icon': icon_str,
                        'text': msg_str,
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
            total_rows = len(df)
            total_cols = len(df.columns)
            total_cells = total_rows * total_cols
            total_missing = int(df.isnull().sum().sum())
            completeness_pct = round((1.0 - (total_missing / (total_cells or 1))) * 100, 1)

            insights.append(f"Dataset Dimensions: <b>{total_rows:,} records</b> across <b>{total_cols} columns</b> ({len(num_cols)} numerical, {len(cat_cols)} categorical). Completeness: <b>{completeness_pct}%</b>.")

            # Scan top 3 categorical columns
            for c_col in cat_cols[:3]:
                vc = df[c_col].dropna().value_counts()
                if not vc.empty:
                    top_name, top_cnt = vc.index[0], vc.values[0]
                    pct = round((top_cnt / (total_rows or 1)) * 100, 1)
                    insights.append(f"<b>{c_col}</b>: '{top_name}' is the top category ({pct}% of total records across {df[c_col].nunique()} distinct classes).")

            # Scan top 3 numeric columns (excluding non-predictive/ID columns)
            from .ml_service import is_id_or_non_predictive_column
            clean_num_cols = [c for c in num_cols if not is_id_or_non_predictive_column(c, df[c])]
            if not clean_num_cols:
                clean_num_cols = num_cols

            for n_col in clean_num_cols[:3]:
                s = pd.to_numeric(df[n_col], errors='coerce').dropna()
                if not s.empty:
                    avg_val = s.mean()
                    med_val = s.median()
                    max_val = s.max()
                    min_val = s.min()
                    insights.append(f"<b>{n_col}</b>: Mean value is <b>{avg_val:,.2f}</b> (Median = {med_val:,.2f}, Range = {min_val:,.2f} to {max_val:,.2f}).")

            # Highest correlation pair across ALL numeric columns
            if len(clean_num_cols) >= 2:
                highest_abs_corr = 0.0
                best_pair = None
                best_corr_val = 0.0

                corr_df = df[clean_num_cols].apply(pd.to_numeric, errors='coerce').corr()
                for i in range(len(clean_num_cols)):
                    for j in range(i + 1, len(clean_num_cols)):
                        c1, c2 = clean_num_cols[i], clean_num_cols[j]
                        val = corr_df.loc[c1, c2]
                        if not np.isnan(val) and abs(val) > highest_abs_corr:
                            highest_abs_corr = abs(val)
                            best_corr_val = val
                            best_pair = (c1, c2)

                if best_pair and highest_abs_corr > 0.05:
                    direction = "positive" if best_corr_val > 0 else "negative"
                    if highest_abs_corr >= 0.7:
                        strength = "strong"
                    elif highest_abs_corr >= 0.4:
                        strength = "moderate"
                    else:
                        strength = "weak"
                    corr_str = f"{strength} {direction}"
                    insights.append(f"Strongest correlation pair: <b>{best_pair[0]}</b> and <b>{best_pair[1]}</b> show {corr_str} relationship (r = <b>{best_corr_val:+.2f}</b>).")

            if total_missing > 0:
                insights.append(f"Data Health: Contains <b>{total_missing:,} missing cells</b> available for automated data imputation.")
            else:
                insights.append("Data Health: Dataset is <b>100% complete</b> with 0 missing cells detected.")

            kpi_data['statistical_insights'] = insights
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
                # Real Histogram distribution values (smart sampled to 5000 points max for high performance)
                hist_sample = valid_num.sample(n=min(len(valid_num), 5000), random_state=42) if len(valid_num) > 5000 else valid_num
                kpi_data['viz_preview']['hist'] = {
                    'values': hist_sample.tolist()
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
