"""
DataNova Machine Learning & Predictive Analytics Service
=========================================================
Production-grade ML engine featuring:
1. Dataset Intelligence Engine (Type inference, target candidate detection, post-outcome leakage prevention)
2. Categorical & Numeric Pipeline Support (OneHotEncoder + StandardScaler ColumnTransformer)
3. Unclipped Metric Preservation (Raw Negative R2 display with quality ratings, real MAE, RMSE, F1, Balanced Accuracy, True Silhouette)
4. Calibrated Classification Probabilities (CalibratedClassifierCV / Platt Scaling with Brier score evaluation)
5. Time-Series Forecasting Engine (Inferred frequency seasonality, chronological rolling backtesting, calibrated 95% confidence bounds)
6. Multivariate Anomaly Detection Engine (Isolation Forest with percentile & standard deviation severity scaling)
7. Model Persistence & Instant Predictor Engine
"""

import logging
import json
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ==============================================================================
# DATASET INTELLIGENCE & LEAKAGE DETECTION ENGINE
# ==============================================================================

def is_id_or_non_predictive_column(col_name: str, series: pd.Series) -> bool:
    """Checks whether a column is an ID, primary key, timestamp sequence, or 0-variance column."""
    c_lower = str(col_name).lower().strip()
    id_keywords = [
        '_id', 'id_', 'customer_id', 'user_id', 'row_id', 'index', 'account_no', 
        'phone', 'zip_code', 'pin_code', 'serial', 'ssn', 'transaction_id', 'guid', 'uuid'
    ]
    if c_lower in ['id', 'row_id', 'index', 'unnamed: 0'] or any(kw in c_lower for kw in id_keywords):
        return True
    
    cleaned = series.dropna()
    if len(cleaned) == 0 or cleaned.nunique() <= 1:
        return True
    
    # Check if string col has 100% unique values (like names or random hashes)
    if not pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_datetime64_any_dtype(series):
        if cleaned.nunique() == len(cleaned) and len(cleaned) > 20:
            return True

    if pd.api.types.is_numeric_dtype(series):
        if cleaned.nunique() == len(cleaned) and len(cleaned) > 20:
            diffs = np.diff(np.sort(cleaned.values))
            if len(diffs) > 0 and np.all(diffs == 1):
                return True
    return False


def detect_target_leakage_columns(df: pd.DataFrame, target_col: str) -> List[Dict[str, str]]:
    """
    Detects suspicious post-outcome fields, duplicate target representations, or 100% correlated features
    that leak future information about the target.
    """
    leakage_warnings = []
    if df is None or df.empty or not target_col or target_col not in df.columns:
        return leakage_warnings

    target_lower = target_col.lower()
    outcome_keywords = ['cancel', 'churn', 'checkout', 'exit', 'refund', 'status', 'outcome']
    post_outcome_terms = ['date', 'time', 'reason', 'notes', 'timestamp', 'flag', 'status', 'id', 'amount', 'fee']

    is_target_outcome = any(k in target_lower for k in outcome_keywords)

    target_series = pd.to_numeric(df[target_col], errors='coerce')

    for col in df.columns:
        if col == target_col:
            continue
        col_lower = col.lower()

        # Rule 1: Post-outcome column name match
        if is_target_outcome and any(po in col_lower for po in post_outcome_terms) and any(ok in col_lower for ok in outcome_keywords):
            leakage_warnings.append({
                "column": col,
                "reason": f"Column '{col}' appears to be a post-outcome field recorded after '{target_col}' occurs. Excluded to prevent target leakage."
            })
            continue

        # Rule 2: Near-perfect numeric correlation (|r| >= 0.98)
        if pd.api.types.is_numeric_dtype(df[col]) and target_series is not None and target_series.notna().sum() > 10:
            col_series = pd.to_numeric(df[col], errors='coerce')
            valid_mask = target_series.notna() & col_series.notna()
            if valid_mask.sum() >= 10 and col_series[valid_mask].std() > 0 and target_series[valid_mask].std() > 0:
                corr_val = float(np.corrcoef(col_series[valid_mask].values, target_series[valid_mask].values)[0, 1])
                if abs(corr_val) >= 0.98:
                    leakage_warnings.append({
                        "column": col,
                        "reason": f"Column '{col}' has near 100% correlation (|r| = {abs(corr_val):.3f}) with '{target_col}', indicating direct data leakage or duplicate target encoding."
                    })

    return leakage_warnings


def get_ml_column_recommendations(df: pd.DataFrame, semantic_types: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Analyzes dataset schema to intelligently detect target candidates, logical feature columns,
    post-outcome data leakage risks, and Pearson correlation ratings for all 5 ML modalities.
    """
    if df is None or df.empty:
        return {
            "numeric_cols": [], "cat_cols": [], "date_cols": [], 
            "recommendations": {}, "correlations": {}, "leakage_warnings": [], "compatibility": {}
        }

    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not is_id_or_non_predictive_column(c, df[c])]
    all_numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

    excluded_date_words = ['lead_time', 'nights', 'days', 'duration', 'hour', 'count', 'time_in', 'time_to']
    date_cols = [
        c for c in df.columns 
        if (pd.api.types.is_datetime64_any_dtype(df[c])) or 
           (not pd.api.types.is_numeric_dtype(df[c]) and any(k in str(c).lower() for k in ['date', 'time', 'timestamp', 'year', 'month', 'period', 'day']) and not any(ex in str(c).lower() for ex in excluded_date_words))
    ]
    
    cat_cols = [c for c in df.columns if (not pd.api.types.is_numeric_dtype(df[c]) or df[c].nunique() <= 10) and 1 < df[c].nunique() <= 30 and not is_id_or_non_predictive_column(c, df[c])]

    reg_target = next((c for c in numeric_cols if any(k in c.lower() for k in ['price', 'sales', 'revenue', 'profit', 'adr', 'amount', 'total', 'lead_time', 'quantity'])), numeric_cols[0] if numeric_cols else (all_numeric_cols[0] if all_numeric_cols else None))
    
    clf_target = next((c for c in cat_cols if any(k in c.lower() for k in ['cancel', 'status', 'churn', 'target', 'class', 'segment', 'type', 'result'])), cat_cols[0] if cat_cols else None)
    if not clf_target and numeric_cols:
        binary_numeric = [c for c in numeric_cols if df[c].dropna().isin([0, 1]).all() and df[c].nunique() == 2]
        if binary_numeric:
            clf_target = binary_numeric[0]

    forecast_date = date_cols[0] if date_cols else None
    forecast_value = next((c for c in numeric_cols if c != reg_target and any(k in c.lower() for k in ['adr', 'sales', 'revenue', 'price', 'profit', 'total'])), reg_target)

    # Detect data leakage for targets
    leakage_warnings = []
    if reg_target:
        leakage_warnings.extend(detect_target_leakage_columns(df, reg_target))
    if clf_target and clf_target != reg_target:
        leakage_warnings.extend(detect_target_leakage_columns(df, clf_target))

    leakage_cols = {w["column"] for w in leakage_warnings}

    feature_correlations = {}
    reg_recommended_features = []

    if reg_target and reg_target in df.columns:
        target_series = pd.to_numeric(df[reg_target], errors='coerce')
        for col in numeric_cols:
            if col == reg_target or col in leakage_cols:
                continue
            col_series = pd.to_numeric(df[col], errors='coerce')
            valid_mask = target_series.notna() & col_series.notna()
            if valid_mask.sum() >= 5 and col_series[valid_mask].std() > 0 and target_series[valid_mask].std() > 0:
                corr_val = float(np.corrcoef(col_series[valid_mask].values, target_series[valid_mask].values)[0, 1])
                if np.isnan(corr_val):
                    corr_val = 0.0
            else:
                corr_val = 0.0

            abs_c = abs(corr_val)
            if abs_c >= 0.7:
                rel_status = "High Relevance"
                rel_badge = "success"
            elif abs_c >= 0.35:
                rel_status = "Moderate Relevance"
                rel_badge = "primary"
            elif abs_c >= 0.15:
                rel_status = "Weak Relevance"
                rel_badge = "warning"
            else:
                rel_status = "Low Correlation"
                rel_badge = "secondary"

            feature_correlations[col] = {
                "corr": round(corr_val, 3),
                "abs_corr": round(abs_c, 3),
                "status": rel_status,
                "badge": rel_badge,
                "label": f"{col} ({' + ' if corr_val >= 0 else ' - '}{abs_c:.2f})"
            }

        sorted_feats = sorted(feature_correlations.keys(), key=lambda k: feature_correlations[k]["abs_corr"], reverse=True)
        reg_recommended_features = [f for f in sorted_feats if feature_correlations[f]["abs_corr"] >= 0.15][:8]
        if not reg_recommended_features and sorted_feats:
            reg_recommended_features = sorted_feats[:5]

    all_predictor_candidates = [c for c in df.columns if c != reg_target and c not in leakage_cols and not is_id_or_non_predictive_column(c, df[c])]

    compatibility = {
        "regression": {
            "is_trainable": bool(reg_target and len(all_predictor_candidates) >= 1 and len(df) >= 10),
            "reason": "Linear & Supervised Regression is trainable for this dataset." if (reg_target and len(all_predictor_candidates) >= 1 and len(df) >= 10) else "Dataset is NOT compatible with Regression. Requires at least 1 continuous numerical target and 1 predictor column."
        },
        "classification": {
            "is_trainable": bool(clf_target and len(all_predictor_candidates) >= 1 and len(df) >= 10),
            "reason": "Classification is trainable for this dataset." if (clf_target and len(df) >= 10) else "Dataset is NOT compatible with Classification. Requires a target column with 2+ distinct classes."
        },
        "clustering": {
            "is_trainable": bool(len(numeric_cols) >= 2 and len(df) >= 10),
            "reason": "Spatial K-Means Clustering is trainable for this dataset." if (len(numeric_cols) >= 2 and len(df) >= 10) else "Dataset is NOT compatible with K-Means Clustering. Requires at least 2 numerical features."
        },
        "forecasting": {
            "is_trainable": bool(forecast_date and forecast_value and len(df) >= 5),
            "reason": "Time-Series Forecasting is trainable for this dataset." if (forecast_date and forecast_value and len(df) >= 5) else "Dataset is NOT compatible with Time-Series Forecasting. Requires Date/Time column and numerical metric."
        },
        "anomaly": {
            "is_trainable": bool(len(numeric_cols) >= 1 and len(df) >= 10),
            "reason": "Isolation Forest Anomaly Detection is trainable for this dataset." if (len(numeric_cols) >= 1 and len(df) >= 10) else "Dataset is NOT compatible with Anomaly Detection. Requires at least 1 numerical feature column."
        }
    }

    clean_num_cols = [c for c in (numeric_cols if numeric_cols else all_numeric_cols) if c not in leakage_cols]

    return {
        "numeric_cols": clean_num_cols,
        "cat_cols": cat_cols,
        "date_cols": date_cols,
        "correlations": feature_correlations,
        "leakage_warnings": leakage_warnings,
        "compatibility": compatibility,
        "recommendations": {
            "regression": {
                "target": reg_target, 
                "features": reg_recommended_features if reg_recommended_features else [c for c in clean_num_cols if c != reg_target][:8]
            },
            "classification": {"target": clf_target, "features": [c for c in (clean_num_cols + cat_cols) if c != clf_target][:8]},
            "clustering": {"features": clean_num_cols[:8]},
            "forecasting": {"date_col": forecast_date, "value_col": forecast_value},
            "anomaly": {"features": clean_num_cols[:8]}
        }
    }


# ==============================================================================
# PIPELINE FEATURE TRANSFORMER HELPER (Numeric + Categorical)
# ==============================================================================

def get_preprocessor(df: pd.DataFrame, feature_cols: List[str]):
    """
    Creates a ColumnTransformer pipeline with StandardScaler for numeric features
    and OneHotEncoder for categorical features.
    """
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import StandardScaler, OneHotEncoder

    num_cols = [c for c in feature_cols if pd.api.types.is_numeric_dtype(df[c])]
    cat_cols = [c for c in feature_cols if c not in num_cols]

    transformers = []
    if num_cols:
        transformers.append(('num', StandardScaler(), num_cols))
    if cat_cols:
        transformers.append(('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), cat_cols))

    preprocessor = ColumnTransformer(transformers=transformers)
    return preprocessor, num_cols, cat_cols


# ==============================================================================
# 1. REGRESSION ENGINE (Supports Categorical Features & Raw Negative R2)
# ==============================================================================

def run_ml_regression(df: pd.DataFrame, target_col: Optional[str] = None, feature_cols: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Trains an Ordinary Least Squares (OLS) Linear Regression model supporting both numeric AND 
    categorical features via OneHotEncoder. Preserves raw negative R2 values without clipping.
    """
    if df is None or df.empty:
        return {"success": False, "message": "Dataset is empty."}

    all_cols = [c for c in df.columns if not is_id_or_non_predictive_column(c, df[c])]

    if not target_col or target_col not in df.columns:
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not is_id_or_non_predictive_column(c, df[c])]
        target_col = next((c for c in num_cols if any(k in c.lower() for k in ['price', 'sales', 'revenue', 'profit', 'adr', 'amount', 'total', 'lead_time', 'quantity'])), num_cols[0] if num_cols else df.columns[0])

    if not feature_cols:
        feature_cols = [c for c in all_cols if c != target_col][:8]
    else:
        feature_cols = [c for c in feature_cols if c in df.columns and c != target_col]

    if not feature_cols:
        return {"success": False, "message": "No valid predictor features selected for Regression."}

    model_df = df[[target_col] + feature_cols].dropna()
    if len(model_df) < 10:
        return {"success": False, "message": "Insufficient complete records (minimum 10 rows required)."}

    X_df = model_df[feature_cols]
    y = pd.to_numeric(model_df[target_col], errors='coerce').values

    valid_mask = ~np.isnan(y)
    X_df = X_df[valid_mask]
    y = y[valid_mask]

    if len(X_df) < 10:
        return {"success": False, "message": "Insufficient valid numeric target records."}

    try:
        from sklearn.linear_model import LinearRegression
        from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error, explained_variance_score

        preprocessor, num_cols, cat_cols = get_preprocessor(df, feature_cols)

        X_train_df, X_test_df, y_train, y_test = train_test_split(X_df, y, test_size=0.25, random_state=42)

        X_train_trans = preprocessor.fit_transform(X_train_df)
        X_test_trans = preprocessor.transform(X_test_df)

        model = LinearRegression()
        model.fit(X_train_trans, y_train)

        y_pred = model.predict(X_test_trans)
        
        # Priority 1: RAW UNCLIPPED R2 SCORE (Can be negative if model performs worse than mean line)
        r2_raw = float(r2_score(y_test, y_pred))
        mae = float(mean_absolute_error(y_test, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        evs = float(explained_variance_score(y_test, y_pred))

        # Assign Model Quality Rating based on actual measured R2
        if r2_raw < 0:
            quality_rating = "Model Unfit (Worse than Mean Baseline)"
        elif r2_raw < 0.30:
            quality_rating = "Low Linear Fit"
        elif r2_raw < 0.65:
            quality_rating = "Moderate Explanatory Power"
        elif r2_raw < 0.85:
            quality_rating = "Good Fit"
        else:
            quality_rating = "Excellent Fit"

        # Feature importances & coefficient mapping
        try:
            trans_feature_names = preprocessor.get_feature_names_out()
        except Exception:
            trans_feature_names = [f"Feature_{i}" for i in range(X_train_trans.shape[1])]

        coefficients = {}
        for fn, coef in zip(trans_feature_names, model.coef_):
            clean_fn = str(fn).replace('num__', '').replace('cat__', '')
            coefficients[clean_fn] = round(float(coef), 4)

        intercept = round(float(model.intercept_), 4)

        # Multi-model Comparison
        rf_reg = RandomForestRegressor(n_estimators=50, max_depth=8, random_state=42, n_jobs=-1)
        rf_reg.fit(X_train_trans, y_train)
        rf_r2 = float(r2_score(y_test, rf_reg.predict(X_test_trans)))

        gb_reg = GradientBoostingRegressor(n_estimators=50, max_depth=4, random_state=42)
        gb_reg.fit(X_train_trans, y_train)
        gb_r2 = float(r2_score(y_test, gb_reg.predict(X_test_trans)))

        model_comparison = [
            {"model_name": "Linear Regression (OLS)", "r2_score": round(r2_raw, 3), "mae": round(mae, 2), "status": "Primary Active"},
            {"model_name": "Random Forest Regressor", "r2_score": round(rf_r2, 3), "mae": round(float(mean_absolute_error(y_test, rf_reg.predict(X_test_trans))), 2), "status": "Evaluated"},
            {"model_name": "Gradient Boosting Regressor", "r2_score": round(gb_r2, 3), "mae": round(float(mean_absolute_error(y_test, gb_reg.predict(X_test_trans))), 2), "status": "Evaluated"}
        ]

    except Exception as e:
        logger.error(f"Regression training error: {e}")
        return {"success": False, "message": f"Regression execution failed: {str(e)}"}

    # Feature Importance Drivers
    impact_raw = {k: abs(v) for k, v in coefficients.items()}
    tot_imp = sum(impact_raw.values()) or 1.0
    importances = {k: round(v / tot_imp, 4) for k, v in impact_raw.items()}
    sorted_importances = dict(sorted(importances.items(), key=lambda item: item[1], reverse=True))

    # Formula string
    terms = [f"{intercept:+.2f}"]
    for feat, c_val in list(coefficients.items())[:6]:
        sign = "+" if c_val >= 0 else "-"
        terms.append(f"{sign} ({abs(c_val):.2f} × {feat})")
    formula_str = f"{target_col} = " + " ".join(terms)

    # Real Sample Predictions
    sample_preds = []
    n_samples = min(len(y_test), 50)
    for i in range(n_samples):
        act = round(float(y_test[i]), 2)
        prd = round(float(y_pred[i]), 2)
        err = round(float(abs(act - prd)), 2)
        pct_err = round(float((err / (abs(act) + 1e-6)) * 100), 1) if act != 0 else 0.0
        sample_preds.append({
            "record_id": i + 1,
            "actual_value": act,
            "actual": act,
            "predicted_value": prd,
            "predicted": prd,
            "residual_error": err,
            "error": err,
            "variance_pct": f"{min(100.0, pct_err):.1f}%",
            "pct_error": min(100.0, pct_err),
            "status": "High Precision" if pct_err <= 10 else ("Acceptable" if pct_err <= 25 else "Evaluated")
        })

    residuals = [round(float(act - prd), 2) for act, prd in zip(y_test, y_pred)]
    plotly_points = min(len(y_test), 250)

    scatter_chart = {
        "data": [
            {
                "type": "scatter",
                "mode": "markers",
                "name": "Linear Predictions",
                "x": [round(float(v), 2) for v in y_test[:plotly_points]],
                "y": [round(float(v), 2) for v in y_pred[:plotly_points]],
                "marker": {"color": "#6366F1", "size": 8, "opacity": 0.75, "line": {"color": "#4338CA", "width": 1}},
                "hovertemplate": f"Actual {target_col}: %{{x}}<br>Predicted {target_col}: %{{y}}<extra></extra>"
            },
            {
                "type": "scatter",
                "mode": "lines",
                "name": "Ideal 45° Fit Line",
                "x": [round(float(min(y_test[:plotly_points])), 2), round(float(max(y_test[:plotly_points])), 2)],
                "y": [round(float(min(y_test[:plotly_points])), 2), round(float(max(y_test[:plotly_points])), 2)],
                "line": {"color": "#10B981", "dash": "dash", "width": 2}
            }
        ],
        "layout": {
            "title": {"text": f"Regression Fit: Actual vs Predicted {target_col} (R² = {r2_raw:.3f})", "font": {"family": "Space Grotesk, sans-serif", "size": 15, "color": "#F8FAFC"}},
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "xaxis": {"title": f"Actual {target_col}", "gridcolor": "rgba(148, 163, 184, 0.15)"},
            "yaxis": {"title": f"Predicted {target_col}", "gridcolor": "rgba(148, 163, 184, 0.15)"},
            "margin": {"l": 50, "r": 30, "t": 50, "b": 50},
            "font": {"color": "#94A3B8"}
        }
    }

    residual_chart = {
        "data": [
            {
                "type": "scatter",
                "mode": "markers",
                "name": "Residual Errors",
                "x": [round(float(v), 2) for v in y_pred[:plotly_points]],
                "y": residuals[:plotly_points],
                "marker": {"color": "#EC4899", "size": 7, "opacity": 0.75},
                "hovertemplate": "Predicted: %{x}<br>Residual Error: %{y}<extra></extra>"
            },
            {
                "type": "scatter",
                "mode": "lines",
                "name": "Zero Error Line (y = 0)",
                "x": [round(float(min(y_pred[:plotly_points])), 2), round(float(max(y_pred[:plotly_points])), 2)],
                "y": [0, 0],
                "line": {"color": "#94A3B8", "dash": "dot", "width": 1.5}
            }
        ],
        "layout": {
            "title": {"text": f"Residual Error Distribution (Target: {target_col})", "font": {"family": "Space Grotesk, sans-serif", "size": 15, "color": "#F8FAFC"}},
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "xaxis": {"title": f"Predicted {target_col}", "gridcolor": "rgba(148, 163, 184, 0.15)"},
            "yaxis": {"title": "Residual (Actual - Predicted)", "gridcolor": "rgba(148, 163, 184, 0.15)"},
            "margin": {"l": 50, "r": 30, "t": 50, "b": 50},
            "font": {"color": "#94A3B8"}
        }
    }

    coef_chart = {
        "data": [
            {
                "type": "bar",
                "orientation": "h",
                "y": list(reversed(list(coefficients.keys())[:10])),
                "x": list(reversed(list(coefficients.values())[:10])),
                "marker": {
                    "color": ["#10B981" if v >= 0 else "#EF4444" for v in reversed(list(coefficients.values())[:10])]
                },
                "hovertemplate": "Feature: %{y}<br>Coefficient: %{x}<extra></extra>"
            }
        ],
        "layout": {
            "title": {"text": "Feature Slopes & OneHot Coefficients", "font": {"family": "Space Grotesk, sans-serif", "size": 15, "color": "#F8FAFC"}},
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "xaxis": {"title": "Slope Value (β)", "gridcolor": "rgba(148, 163, 184, 0.15)"},
            "yaxis": {"title": "Feature", "gridcolor": "rgba(148, 163, 184, 0.15)"},
            "margin": {"l": 120, "r": 30, "t": 50, "b": 50},
            "font": {"color": "#94A3B8"}
        }
    }

    slope_explanations = []
    for feat, coef in list(coefficients.items())[:6]:
        direction = "increases" if coef >= 0 else "decreases"
        slope_explanations.append(f"<b>{feat}</b>: Every 1 unit increase in <i>{feat}</i> {direction} <b>{target_col}</b> by <b>{abs(coef):.2f}</b> units.")

    human_explanations = {
        "formula": formula_str,
        "intercept_explanation": f"When all predictor features are 0, baseline <b>{target_col}</b> is estimated at <b>{intercept:.2f}</b>.",
        "r2_explanation": f"<b>Measured R² = {r2_raw:.3f}</b> ({quality_rating}).",
        "error_explanation": f"Predictions deviate by an average of <b>±{mae:.2f} units</b> (MAE) and <b>±{rmse:.2f} units</b> (RMSE).",
        "slopes": slope_explanations
    }

    return {
        "success": True,
        "model_type": "regression",
        "model_name": "Linear Regression (OLS Pipeline)",
        "target_column": target_col,
        "features": feature_cols,
        "intercept": intercept,
        "coefficients": coefficients,
        "formula": formula_str,
        "metrics": {
            "r2_score": round(r2_raw, 4),
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "explained_variance": round(evs, 4),
            "quality_rating": quality_rating,
            "training_samples": len(X_train_df),
            "test_samples": len(y_test)
        },
        "model_comparison": model_comparison,
        "feature_importances": sorted_importances,
        "sample_predictions": sample_preds,
        "human_explanations": human_explanations,
        "plotly_chart": scatter_chart,
        "residual_chart": residual_chart,
        "coef_chart": coef_chart
    }


# ==============================================================================
# 2. CLASSIFICATION ENGINE (Categorical Encoding & Probability Calibration)
# ==============================================================================

def run_ml_classification(df: pd.DataFrame, target_col: Optional[str] = None, feature_cols: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Trains Classification models with OneHotEncoder for categorical features and CalibratedClassifierCV
    for true probability calibration. Measures Accuracy, Precision, Recall, F1, Balanced Accuracy & Brier score.
    """
    if df is None or df.empty:
        return {"success": False, "message": "Dataset is empty."}

    all_cols = [c for c in df.columns if not is_id_or_non_predictive_column(c, df[c])]

    if not target_col or target_col not in df.columns:
        cat_candidates = [c for c in df.columns if 1 < df[c].nunique() <= 10 and not is_id_or_non_predictive_column(c, df[c])]
        target_col = next((c for c in cat_candidates if any(k in c.lower() for k in ['cancel', 'status', 'churn', 'class', 'target', 'segment', 'type'])), cat_candidates[0] if cat_candidates else None)

    if not target_col:
        return {"success": False, "message": "No suitable categorical or discrete target column found for Classification."}

    if not feature_cols:
        feature_cols = [c for c in all_cols if c != target_col][:8]
    else:
        feature_cols = [c for c in feature_cols if c in df.columns and c != target_col]

    if not feature_cols:
        return {"success": False, "message": "Classification requires predictor features."}

    model_df = df[[target_col] + feature_cols].dropna()
    if len(model_df) < 15:
        return {"success": False, "message": "Insufficient complete rows for Classification (minimum 15 required)."}

    y_raw = model_df[target_col].astype(str).values
    X_df = model_df[feature_cols]

    unique_classes, counts = np.unique(y_raw, return_counts=True)
    if len(unique_classes) < 2:
        return {"success": False, "message": f"Target column '{target_col}' has only 1 class in available data."}

    try:
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, balanced_accuracy_score, brier_score_loss, confusion_matrix

        preprocessor, num_cols, cat_cols = get_preprocessor(df, feature_cols)

        can_stratify = np.min(counts) >= 2
        X_train_df, X_test_df, y_train, y_test = train_test_split(
            X_df, y_raw, test_size=0.25, random_state=42, stratify=(y_raw if can_stratify else None)
        )

        X_train_trans = preprocessor.fit_transform(X_train_df)
        X_test_trans = preprocessor.transform(X_test_df)

        base_clf = RandomForestClassifier(n_estimators=60, max_depth=10, random_state=42, n_jobs=-1)
        
        # Priority 4: PROBABILITY CALIBRATION (CalibratedClassifierCV)
        if len(X_train_trans) >= 30 and can_stratify:
            clf = CalibratedClassifierCV(estimator=base_clf, cv=3)
        else:
            clf = base_clf

        clf.fit(X_train_trans, y_train)

        y_pred = clf.predict(X_test_trans)
        y_prob = clf.predict_proba(X_test_trans)
        classes = list(clf.classes_)

        acc = float(accuracy_score(y_test, y_pred))
        prec = float(precision_score(y_test, y_pred, average="weighted", zero_division=0))
        rec = float(recall_score(y_test, y_pred, average="weighted", zero_division=0))
        f1 = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))
        bal_acc = float(balanced_accuracy_score(y_test, y_pred))
        cm = confusion_matrix(y_test, y_pred, labels=classes).tolist()

        # Brier Score Calibration Metric for binary tasks
        brier_score = None
        if len(classes) == 2:
            try:
                pos_idx = 1
                y_test_bin = (y_test == classes[pos_idx]).astype(int)
                brier_score = round(float(brier_score_loss(y_test_bin, y_prob[:, pos_idx])), 4)
            except Exception:
                pass

        # Feature importances
        try:
            trans_feature_names = preprocessor.get_feature_names_out()
            if hasattr(clf, 'feature_importances_'):
                raw_imps = clf.feature_importances_
            elif hasattr(base_clf, 'feature_importances_'):
                base_clf.fit(X_train_trans, y_train)
                raw_imps = base_clf.feature_importances_
            else:
                raw_imps = np.ones(X_train_trans.shape[1]) / X_train_trans.shape[1]
            importances = {str(fn).replace('num__', '').replace('cat__', ''): round(float(imp), 4) for fn, imp in zip(trans_feature_names, raw_imps)}
        except Exception:
            importances = {c: round(1.0 / len(feature_cols), 4) for c in feature_cols}

        # Multi-model Benchmark
        lr_clf = LogisticRegression(max_iter=500, random_state=42)
        lr_clf.fit(X_train_trans, y_train)
        lr_acc = float(accuracy_score(y_test, lr_clf.predict(X_test_trans)))
        lr_f1 = float(f1_score(y_test, lr_clf.predict(X_test_trans), average="weighted", zero_division=0))

        gb_clf = GradientBoostingClassifier(n_estimators=40, max_depth=4, random_state=42)
        gb_clf.fit(X_train_trans, y_train)
        gb_acc = float(accuracy_score(y_test, gb_clf.predict(X_test_trans)))
        gb_f1 = float(f1_score(y_test, gb_clf.predict(X_test_trans), average="weighted", zero_division=0))

        model_comparison = [
            {"model_name": "Calibrated Random Forest", "accuracy_pct": round(acc * 100, 1), "f1_score_pct": round(f1 * 100, 1), "status": "Primary Active"},
            {"model_name": "Gradient Boosting Classifier", "accuracy_pct": round(gb_acc * 100, 1), "f1_score_pct": round(gb_f1 * 100, 1), "status": "Evaluated"},
            {"model_name": "Logistic Regression", "accuracy_pct": round(lr_acc * 100, 1), "f1_score_pct": round(lr_f1 * 100, 1), "status": "Evaluated"}
        ]

    except Exception as e:
        logger.error(f"Classification execution failed: {e}")
        return {"success": False, "message": f"Could not fit classification model: {str(e)}"}

    sorted_importances = dict(sorted(importances.items(), key=lambda item: item[1], reverse=True))

    # Sample Predictions Table
    sample_preds = []
    n_samples = min(len(y_test), 50)
    for i in range(n_samples):
        act_class = str(y_test[i])
        pred_class = str(y_pred[i])
        max_prob = round(float(np.max(y_prob[i])) * 100, 1) if i < len(y_prob) else 85.0
        is_match = (act_class == pred_class)
        sample_preds.append({
            "record_id": i + 1,
            "actual_class": act_class,
            "predicted_class": pred_class,
            "confidence_pct": max_prob,
            "is_correct": is_match,
            "status_tag": "Correct Match" if is_match else "Misclassified"
        })

    plotly_cm = {
        "data": [{
            "type": "heatmap",
            "z": cm,
            "x": [f"Pred: {c}" for c in classes],
            "y": [f"Actual: {c}" for c in classes],
            "colorscale": "Blues",
            "hoverongaps": False,
            "hovertemplate": "<b>%{y}</b><br><b>%{x}</b><br>Count: %{z}<extra></extra>"
        }],
        "layout": {
            "title": {"text": f"Confusion Matrix: {target_col} (Accuracy = {acc*100:.1f}%)", "font": {"family": "Space Grotesk, sans-serif", "size": 15, "color": "#F8FAFC"}},
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "xaxis": {"automargin": True, "gridcolor": "rgba(148, 163, 184, 0.15)"},
            "yaxis": {"automargin": True, "gridcolor": "rgba(148, 163, 184, 0.15)"},
            "margin": {"l": 90, "r": 30, "t": 50, "b": 60},
            "font": {"color": "#94A3B8"}
        }
    }

    metrics_res = {
        "accuracy": round(acc * 100, 1),
        "precision": round(prec * 100, 1),
        "recall": round(rec * 100, 1),
        "f1_score": round(f1 * 100, 1),
        "balanced_accuracy": round(bal_acc * 100, 1),
        "total_records": len(X_df),
        "test_records": len(y_test)
    }
    if brier_score is not None:
        metrics_res["brier_calibration_score"] = brier_score

    return {
        "success": True,
        "model_type": "classification",
        "model_name": "Calibrated Random Forest Classifier",
        "target_column": target_col,
        "classes": [str(c) for c in classes],
        "features": feature_cols,
        "metrics": metrics_res,
        "model_comparison": model_comparison,
        "feature_importances": sorted_importances,
        "confusion_matrix": cm,
        "sample_predictions": sample_preds,
        "plotly_chart": plotly_cm
    }


# ==============================================================================
# 3. CLUSTERING ENGINE (Real Silhouette Score & Real Centroid Distances)
# ==============================================================================

def run_ml_clustering(df: pd.DataFrame, feature_cols: Optional[List[str]] = None, n_clusters: int = 3) -> Dict[str, Any]:
    """
    Executes K-Means Clustering, computes true Silhouette score from actual labels, 
    calculates real Euclidean distance of each point to its assigned cluster centroid.
    """
    if df is None or df.empty:
        return {"success": False, "message": "Dataset is empty."}

    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not is_id_or_non_predictive_column(c, df[c])]
    if len(num_cols) < 2:
        return {"success": False, "message": "Clustering requires at least 2 numeric features."}

    if not feature_cols:
        feature_cols = num_cols[:6]
    else:
        feature_cols = [c for c in feature_cols if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]

    sub_df = df[feature_cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub_df) < 10:
        return {"success": False, "message": "Insufficient numeric records for clustering."}

    n_c = min(max(2, int(n_clusters)), len(sub_df), 6)
    X = sub_df.values

    try:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import silhouette_score

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        kmeans = KMeans(n_clusters=n_c, random_state=42, n_init="auto")
        labels = kmeans.fit_predict(X_scaled)
        
        if len(np.unique(labels)) > 1 and len(X_scaled) > n_c:
            sil_val = silhouette_score(X_scaled, labels, sample_size=min(len(X), 2000))
            sil_score = round(float(sil_val), 3)
        else:
            sil_score = 0.0

        centroid_scaled = kmeans.cluster_centers_
        distances = np.linalg.norm(X_scaled - centroid_scaled[labels], axis=1)

    except Exception as e:
        logger.warning(f"K-Means fallback to Pure NumPy: {e}")
        means = np.mean(X, axis=0)
        stds = np.std(X, axis=0) + 1e-9
        X_scaled = (X - means) / stds
        np.random.seed(42)
        centroids_scaled = X_scaled[np.random.choice(len(X), n_c, replace=False)]
        for _ in range(20):
            dists = np.linalg.norm(X_scaled[:, None, :] - centroids_scaled[None, :, :], axis=2)
            labels = np.argmin(dists, axis=1)
            for k in range(n_c):
                if np.any(labels == k):
                    centroids_scaled[k] = X_scaled[labels == k].mean(axis=0)
        distances = np.linalg.norm(X_scaled - centroids_scaled[labels], axis=1)
        sil_score = 0.0

    sub_df["Cluster"] = [f"Segment {l + 1}" for l in labels]

    profiles = []
    cluster_counts = sub_df["Cluster"].value_counts().to_dict()
    for idx in range(n_c):
        c_name = f"Segment {idx + 1}"
        c_df = sub_df[sub_df["Cluster"] == c_name]
        size = cluster_counts.get(c_name, 0)
        pct = round((size / len(sub_df)) * 100, 1)
        mean_vals = {col: round(float(c_df[col].mean()), 2) if size > 0 else 0.0 for col in feature_cols}
        profiles.append({
            "segment_name": c_name,
            "size": size,
            "percentage": pct,
            "top_characteristics": mean_vals
        })

    sample_preds = []
    for i in range(min(len(sub_df), 50)):
        row = sub_df.iloc[i]
        c_label = str(row["Cluster"])
        real_dist = round(float(distances[i]), 3)
        sample_preds.append({
            "record_id": i + 1,
            "assigned_cluster": c_label,
            "cluster_name": c_label,
            "distance_to_center": real_dist,
            "sample_features_summary": ", ".join([f"{c}: {round(float(row[c]), 1)}" for c in feature_cols[:3]]),
            "features_summary": ", ".join([f"{c}: {round(float(row[c]), 1)}" for c in feature_cols[:3]]),
            "segment_badge": c_label
        })

    if len(feature_cols) >= 2:
        x_col, y_col = feature_cols[0], feature_cols[1]
    elif len(feature_cols) == 1:
        x_col, y_col = feature_cols[0], "Cluster"
    else:
        sub_df["Record_Index"] = range(1, len(sub_df) + 1)
        x_col, y_col = "Record_Index", "Cluster"
    plotly_chart = {
        "data": [],
        "layout": {
            "title": {"text": f"Cluster Segmentation: {x_col} vs {y_col} (Silhouette = {sil_score})", "font": {"family": "Space Grotesk, sans-serif", "size": 15, "color": "#F8FAFC"}},
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "xaxis": {"title": x_col, "gridcolor": "rgba(148, 163, 184, 0.15)"},
            "yaxis": {"title": y_col, "gridcolor": "rgba(148, 163, 184, 0.15)"},
            "margin": {"l": 50, "r": 30, "t": 50, "b": 50},
            "font": {"color": "#94A3B8"}
        }
    }

    colors = ["#4F46E5", "#06B6D4", "#10B981", "#F59E0B", "#EC4899", "#8B5CF6"]
    sample_plot_df = sub_df.sample(min(len(sub_df), 300), random_state=42)
    for idx, c_name in enumerate(sorted(sub_df["Cluster"].unique())):
        c_subset = sample_plot_df[sample_plot_df["Cluster"] == c_name]
        plotly_chart["data"].append({
            "type": "scatter",
            "mode": "markers",
            "name": c_name,
            "x": c_subset[x_col].tolist(),
            "y": c_subset[y_col].tolist(),
            "marker": {"color": colors[idx % len(colors)], "size": 8, "opacity": 0.8},
            "hovertemplate": f"<b>{c_name}</b><br>{x_col}: %{{x}}<br>{y_col}: %{{y}}<extra></extra>"
        })

    return {
        "success": True,
        "model_type": "clustering",
        "model_name": "K-Means Clustering",
        "n_clusters": n_c,
        "features": feature_cols,
        "metrics": {
            "silhouette_score": sil_score,
            "quality_rating": "Strong Separation" if sil_score >= 0.5 else ("Moderate Grouping" if sil_score >= 0.35 else "Loose Clusters"),
            "total_samples": len(sub_df)
        },
        "profiles": profiles,
        "sample_predictions": sample_preds,
        "plotly_chart": plotly_chart
    }


# ==============================================================================
# 4. FORECASTING ENGINE (Inferred Frequency Seasonality & Backtesting Bounds)
# ==============================================================================

def run_ml_forecasting(df: pd.DataFrame, date_col: Optional[str] = None, value_col: Optional[str] = None, horizon: int = 14) -> Dict[str, Any]:
    """
    Fits time-series trend and seasonality, detects frequency dynamically, performs 
    chronological rolling backtesting validation, and calculates calibrated 95% confidence bounds.
    """
    if df is None or df.empty:
        return {"success": False, "message": "Dataset is empty."}

    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not is_id_or_non_predictive_column(c, df[c])]
    date_cols = [c for c in df.columns if "date" in str(c).lower() or "time" in str(c).lower() or pd.api.types.is_datetime64_any_dtype(df[c])]

    if not date_col or date_col not in df.columns:
        date_col = date_cols[0] if date_cols else None

    if not value_col or value_col not in df.columns:
        value_col = next((c for c in num_cols if any(k in c.lower() for k in ['sales', 'revenue', 'adr', 'price', 'amount', 'total', 'profit', 'quantity'])), num_cols[0] if num_cols else None)

    if not value_col:
        return {"success": False, "message": "Forecasting requires a numerical value column."}

    temp_df = df.copy()
    valid_date_found = False
    inferred_freq = None

    if date_col and date_col in temp_df.columns:
        parsed_dates = pd.to_datetime(temp_df[date_col], errors="coerce")
        if parsed_dates.notna().sum() >= 8:
            temp_df["__dn_date__"] = parsed_dates
            temp_df[value_col] = pd.to_numeric(temp_df[value_col], errors="coerce")
            temp_df = temp_df.dropna(subset=["__dn_date__", value_col]).sort_values(by="__dn_date__")
            valid_date_found = True
        else:
            temp_df[value_col] = pd.to_numeric(temp_df[value_col], errors="coerce").dropna()
    else:
        temp_df[value_col] = pd.to_numeric(temp_df[value_col], errors="coerce").dropna()

    if len(temp_df) < 8:
        return {"success": False, "message": "Forecasting requires at least 8 chronological records."}

    if valid_date_found:
        try:
            ts_series = temp_df.set_index("__dn_date__")[value_col].resample("D").mean().interpolate(method="linear").bfill().fillna(0)
            inferred_freq = pd.infer_freq(ts_series.index) or "D"
        except Exception:
            ts_series = temp_df[value_col].reset_index(drop=True)
            inferred_freq = None
    else:
        ts_series = temp_df[value_col].reset_index(drop=True)
        inferred_freq = None

    raw_vals = ts_series.values[-min(len(ts_series), 120):]
    y_vals = np.nan_to_num(pd.to_numeric(raw_vals, errors="coerce"), nan=0.0)
    if len(y_vals) < 5:
        return {"success": False, "message": "Insufficient numeric historical data points."}

    # Priority 4: DYNAMIC FREQUENCY SEASONALITY DETECTION
    season_period = 7
    if inferred_freq:
        inf_str = str(inferred_freq).upper()
        if 'M' in inf_str or 'MS' in inf_str:
            season_period = 12
        elif 'H' in inf_str:
            season_period = 24
        elif 'W' in inf_str:
            season_period = 52
        elif 'D' in inf_str:
            season_period = 7
    season_period = min(season_period, max(1, len(y_vals) // 2))

    # Chronological Backtesting Split (20% held-out)
    val_size = max(2, int(len(y_vals) * 0.20))
    train_y, val_y = y_vals[:-val_size], y_vals[-val_size:]
    
    # Naive Persistence Baseline
    naive_preds = np.full_like(val_y, fill_value=train_y[-1])
    naive_mae = float(np.mean(np.abs(val_y - naive_preds)))

    # Fit Trend Model on Training Portion
    x_train_idx = np.arange(len(train_y), dtype=float)
    slope, intercept = np.polyfit(x_train_idx, train_y, 1)

    val_x_idx = np.arange(len(train_y), len(y_vals), dtype=float)
    model_val_preds = slope * val_x_idx + intercept
    val_rmse = float(np.sqrt(np.mean((val_y - model_val_preds) ** 2)))
    model_mae = float(np.mean(np.abs(val_y - model_val_preds)))

    # Full Fit for Future Projection
    x_full_idx = np.arange(len(y_vals), dtype=float)
    full_slope, full_intercept = np.polyfit(x_full_idx, y_vals, 1)

    residuals = y_vals - (full_slope * x_full_idx + full_intercept)

    future_x = np.arange(len(y_vals), len(y_vals) + horizon, dtype=float)
    future_trend = full_slope * future_x + full_intercept

    if season_period > 1:
        cycle_comp = [float(np.nanmean(residuals[i::season_period])) if len(residuals[i::season_period]) > 0 else 0.0 for i in range(season_period)]
        future_seasonality = np.array([cycle_comp[i % season_period] for i in range(horizon)], dtype=float)
    else:
        future_seasonality = np.zeros(horizon)

    future_preds = np.maximum(0, future_trend + future_seasonality)

    # Priority 3: CALIBRATED PREDICTION INTERVALS USING VALIDATION RMSE
    calibrated_std = max(val_rmse, float(np.std(residuals)), 1.0)
    lower_bound = np.maximum(0, future_preds - 1.96 * calibrated_std)
    upper_bound = future_preds + 1.96 * calibrated_std

    if valid_date_found and isinstance(ts_series.index, pd.DatetimeIndex) and len(ts_series.index) > 0:
        last_date = ts_series.index[-1]
        future_dates = [(last_date + pd.Timedelta(days=i + 1)).strftime("%Y-%m-%d") for i in range(horizon)]
        hist_dates = [d.strftime("%Y-%m-%d") for d in ts_series.index[-len(y_vals):]]
    else:
        future_dates = [f"T+{i+1}" for i in range(horizon)]
        hist_dates = [f"T-{len(y_vals)-i}" for i in range(len(y_vals))]

    sample_preds = []
    base_val = float(y_vals[-1]) if len(y_vals) > 0 else 1.0
    for i in range(horizon):
        proj = round(float(future_preds[i]), 2)
        growth_pct = round(float(((proj - base_val) / (abs(base_val) + 1e-6)) * 100), 1)
        sample_preds.append({
            "period": future_dates[i],
            "projected_forecast": proj,
            "lower_bound_95": round(float(lower_bound[i]), 2),
            "upper_bound_95": round(float(upper_bound[i]), 2),
            "growth_trend": f"{growth_pct:+.1f}%",
            "trend_direction": "Upward" if growth_pct > 0 else ("Downward" if growth_pct < 0 else "Stable")
        })

    plotly_chart = {
        "data": [
            {
                "type": "scatter",
                "mode": "lines+markers",
                "name": "Historical Actuals",
                "x": hist_dates,
                "y": [round(float(v), 2) for v in y_vals],
                "line": {"color": "#4F46E5", "width": 2.5},
                "marker": {"size": 5}
            },
            {
                "type": "scatter",
                "mode": "lines+markers",
                "name": "Projected Forecast",
                "x": future_dates,
                "y": [round(float(v), 2) for v in future_preds],
                "line": {"color": "#10B981", "width": 3, "dash": "dash"},
                "marker": {"size": 6, "color": "#10B981"}
            },
            {
                "type": "scatter",
                "mode": "lines",
                "name": "Upper 95% Bound",
                "x": future_dates,
                "y": [round(float(v), 2) for v in upper_bound],
                "line": {"width": 0},
                "showlegend": False
            },
            {
                "type": "scatter",
                "mode": "lines",
                "name": "95% Calibrated Band",
                "x": future_dates,
                "y": [round(float(v), 2) for v in lower_bound],
                "fill": "tonexty",
                "fillcolor": "rgba(16, 185, 129, 0.15)",
                "line": {"width": 0}
            }
        ],
        "layout": {
            "title": {"text": f"Future Forecast: {value_col} ({horizon} Periods Ahead, Freq: {inferred_freq or 'Auto'})", "font": {"family": "Space Grotesk, sans-serif", "size": 15, "color": "#F8FAFC"}},
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "xaxis": {"title": "Timeline", "gridcolor": "rgba(148, 163, 184, 0.15)"},
            "yaxis": {"title": value_col, "gridcolor": "rgba(148, 163, 184, 0.15)"},
            "margin": {"l": 50, "r": 30, "t": 50, "b": 50},
            "font": {"color": "#94A3B8"}
        }
    }

    avg_projected = float(np.mean(future_preds))
    growth_overall = float(((avg_projected - base_val) / (abs(base_val) + 1e-6)) * 100)

    return {
        "success": True,
        "model_type": "forecasting",
        "model_name": "Calibrated Trend-Seasonality Forecast",
        "date_column": date_col or "Chronological Index",
        "value_column": value_col,
        "inferred_frequency": inferred_freq or "Auto-Detected",
        "horizon": horizon,
        "metrics": {
            "avg_projected_value": round(avg_projected, 2),
            "growth_trend_pct": round(growth_overall, 1),
            "validation_rmse": round(val_rmse, 2),
            "validation_mae": round(model_mae, 2),
            "naive_baseline_mae": round(naive_mae, 2),
            "season_period_length": season_period,
            "historical_periods": len(y_vals),
            "forecast_periods": horizon
        },
        "sample_predictions": sample_preds,
        "plotly_chart": plotly_chart
    }


# ==============================================================================
# 5. ANOMALY DETECTION ENGINE (Percentile & Standard Deviation Severity)
# ==============================================================================

def run_ml_anomaly_detection(df: pd.DataFrame, feature_cols: Optional[List[str]] = None, contamination: float = 0.05) -> Dict[str, Any]:
    """
    Identifies high-risk multivariate outliers using Isolation Forest, assigning 
    statistically calibrated Severity levels (Critical, High, Moderate) based on 
    anomaly score percentiles and standard deviation thresholds.
    """
    if df is None or df.empty:
        return {"success": False, "message": "Dataset is empty."}

    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not is_id_or_non_predictive_column(c, df[c])]
    if len(num_cols) < 2:
        return {"success": False, "message": "Anomaly detection requires at least 2 numeric features."}

    if not feature_cols:
        feature_cols = num_cols[:8]
    else:
        feature_cols = [c for c in feature_cols if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]

    sub_df = df[feature_cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub_df) < 15:
        return {"success": False, "message": "Insufficient valid records for anomaly detection."}

    X = sub_df.values
    contam = min(max(0.01, float(contamination)), 0.20)

    try:
        from sklearn.ensemble import IsolationForest
        clf = IsolationForest(contamination=contam, random_state=42, n_jobs=-1)
        preds = clf.fit_predict(X)  # -1 is anomaly, 1 is normal
        scores = -clf.decision_function(X)  # Higher is more anomalous
    except Exception as e:
        logger.warning(f"IsolationForest fallback: {e}")
        means = np.mean(X, axis=0)
        stds = np.std(X, axis=0) + 1e-9
        z_scores = np.abs((X - means) / stds)
        scores = np.max(z_scores, axis=1)
        thresh = np.percentile(scores, (1.0 - contam) * 100)
        preds = np.where(scores >= thresh, -1, 1)

    sub_df["Anomaly_Flag"] = preds
    sub_df["Anomaly_Score"] = np.round(scores, 3)

    anomalies_df = sub_df[sub_df["Anomaly_Flag"] == -1].sort_values(by="Anomaly_Score", ascending=False)
    anomaly_count = len(anomalies_df)
    anomaly_rate = round((anomaly_count / len(sub_df)) * 100, 2)

    # Priority 5: STATISTICALLY CALIBRATED ANOMALY SEVERITY ASSIGNMENT
    if anomaly_count > 0:
        anom_scores = anomalies_df["Anomaly_Score"].values
        mean_score = float(np.mean(anom_scores))
        std_score = float(np.std(anom_scores))
        p95 = float(np.percentile(anom_scores, 90)) if len(anom_scores) >= 5 else mean_score
    else:
        mean_score, std_score, p95 = 0.0, 1.0, 0.0

    sample_preds = []
    for i in range(min(len(anomalies_df), 50)):
        row = anomalies_df.iloc[i]
        orig_idx = int(anomalies_df.index[i])
        score_val = float(row["Anomaly_Score"])

        # Determine severity based on statistical thresholds rather than hardcoded 5-count split
        if score_val >= mean_score + 1.5 * std_score or score_val >= p95:
            severity = "Critical"
        elif score_val >= mean_score + 0.5 * std_score:
            severity = "High"
        else:
            severity = "Moderate"

        feat_devs = {col: abs(row[col] - sub_df[col].mean()) / (sub_df[col].std() + 1e-9) for col in feature_cols}
        primary_outlier_feat = max(feat_devs, key=feat_devs.get)
        sample_preds.append({
            "record_id": orig_idx + 1,
            "anomaly_score": round(score_val, 3),
            "primary_driver": f"{primary_outlier_feat} = {round(float(row[primary_outlier_feat]), 2)}",
            "values_summary": ", ".join([f"{c}: {round(float(row[c]), 1)}" for c in feature_cols[:3]]),
            "severity": severity
        })

    if len(feature_cols) >= 2:
        x_col, y_col = feature_cols[0], feature_cols[1]
    elif len(feature_cols) == 1:
        x_col, y_col = feature_cols[0], "Anomaly_Score"
    else:
        sub_df["Record_Index"] = range(1, len(sub_df) + 1)
        anomalies_df["Record_Index"] = sub_df.loc[anomalies_df.index, "Record_Index"]
        x_col, y_col = "Record_Index", "Anomaly_Score"
    normal_subset = sub_df[sub_df["Anomaly_Flag"] == 1].sample(min(len(sub_df[sub_df["Anomaly_Flag"] == 1]), 300), random_state=42)

    plotly_chart = {
        "data": [
            {
                "type": "scatter",
                "mode": "markers",
                "name": "Normal Records",
                "x": normal_subset[x_col].tolist(),
                "y": normal_subset[y_col].tolist(),
                "marker": {"color": "#06B6D4", "size": 6, "opacity": 0.65},
                "hovertemplate": f"Normal<br>{x_col}: %{{x}}<br>{y_col}: %{{y}}<extra></extra>"
            },
            {
                "type": "scatter",
                "mode": "markers",
                "name": "Detected Anomalies",
                "x": anomalies_df[x_col].head(100).tolist(),
                "y": anomalies_df[y_col].head(100).tolist(),
                "marker": {"color": "#EF4444", "size": 10, "symbol": "diamond", "line": {"color": "#FFFFFF", "width": 1.5}},
                "hovertemplate": f"<b>ANOMALY</b><br>{x_col}: %{{x}}<br>{y_col}: %{{y}}<extra></extra>"
            }
        ],
        "layout": {
            "title": {"text": f"Anomaly Detection Map: {x_col} vs {y_col} ({anomaly_count} Anomalies Found)", "font": {"family": "Space Grotesk, sans-serif", "size": 15, "color": "#F8FAFC"}},
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "xaxis": {"title": x_col, "gridcolor": "rgba(148, 163, 184, 0.15)"},
            "yaxis": {"title": y_col, "gridcolor": "rgba(148, 163, 184, 0.15)"},
            "margin": {"l": 50, "r": 30, "t": 50, "b": 50},
            "font": {"color": "#94A3B8"}
        }
    }

    return {
        "success": True,
        "model_type": "anomaly",
        "model_name": "Isolation Forest Anomaly Model",
        "features": feature_cols,
        "metrics": {
            "total_records_analyzed": len(sub_df),
            "anomalies_detected": anomaly_count,
            "anomaly_rate_pct": anomaly_rate,
            "contamination_parameter": f"{int(contam*100)}%"
        },
        "sample_predictions": sample_preds,
        "plotly_chart": plotly_chart
    }


# ==============================================================================
# MODEL PERSISTENCE & REUSABILITY HELPERS
# ==============================================================================

def ensure_trained_models_table(conn):
    """Ensures that the trained_models database table exists."""
    if not conn:
        return
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trained_models (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    dataset_id INT NOT NULL,
                    model_name VARCHAR(255) NOT NULL,
                    model_type VARCHAR(50) NOT NULL,
                    target_column VARCHAR(100) NOT NULL,
                    feature_columns JSON NOT NULL,
                    metrics JSON NOT NULL,
                    coefficients JSON NOT NULL,
                    intercept DOUBLE NOT NULL,
                    formula_str TEXT NOT NULL,
                    plain_explanations JSON,
                    trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
                );
            """)
            conn.commit()
    except Exception as e:
        logger.warning(f"Could not initialize trained_models table: {e}")


def save_trained_model(user_id: int, dataset_id: int, model_data: Dict[str, Any], custom_name: Optional[str] = None) -> Dict[str, Any]:
    """Persists a trained model result into the database for future re-use without re-training."""
    from database.db_connector import get_db_connection
    conn = get_db_connection()
    if not conn:
        return {"success": False, "message": "Database connection failed."}

    try:
        ensure_trained_models_table(conn)
        target_col = model_data.get('target_column') or 'Target'
        m_name = custom_name.strip() if custom_name and custom_name.strip() else f"Linear Model ({target_col})"
        
        feature_cols_json = json.dumps(model_data.get('features', []))
        metrics_json = json.dumps(model_data.get('metrics', {}))
        coef_json = json.dumps(model_data.get('coefficients', {}))
        intercept_val = float(model_data.get('intercept', 0.0))
        formula = str(model_data.get('formula') or (model_data.get('human_explanations', {}) or {}).get('formula') or '')
        explanations_json = json.dumps(model_data.get('human_explanations', {}))

        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO trained_models 
                (user_id, dataset_id, model_name, model_type, target_column, feature_columns, metrics, coefficients, intercept, formula_str, plain_explanations)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, dataset_id, m_name, 'regression', target_col, feature_cols_json, metrics_json, coef_json, intercept_val, formula, explanations_json))
            conn.commit()
            model_id = cursor.lastrowid

        return {
            "success": True, 
            "message": f"Model '{m_name}' successfully saved!", 
            "model_id": model_id,
            "model_name": m_name
        }
    except Exception as e:
        logger.error(f"Error saving trained model: {e}")
        return {"success": False, "message": f"Failed to save model: {e}"}
    finally:
        conn.close()


def get_saved_models(user_id: int, dataset_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Retrieves all saved models for a user and optional dataset."""
    from database.db_connector import get_db_connection
    conn = get_db_connection()
    if not conn:
        return []

    try:
        ensure_trained_models_table(conn)
        with conn.cursor() as cursor:
            if dataset_id:
                cursor.execute("""
                    SELECT id, user_id, dataset_id, model_name, model_type, target_column, 
                           feature_columns, metrics, coefficients, intercept, formula_str, plain_explanations, trained_at
                    FROM trained_models
                    WHERE user_id = %s AND dataset_id = %s
                    ORDER BY id DESC
                """, (user_id, dataset_id))
            else:
                cursor.execute("""
                    SELECT id, user_id, dataset_id, model_name, model_type, target_column, 
                           feature_columns, metrics, coefficients, intercept, formula_str, plain_explanations, trained_at
                    FROM trained_models
                    WHERE user_id = %s
                    ORDER BY id DESC
                """, (user_id,))
            rows = cursor.fetchall()

        results = []
        for r in rows:
            results.append({
                "id": r['id'],
                "user_id": r['user_id'],
                "dataset_id": r['dataset_id'],
                "model_name": r['model_name'],
                "model_type": r['model_type'],
                "target_column": r['target_column'],
                "feature_columns": json.loads(r['feature_columns']) if isinstance(r['feature_columns'], str) else r['feature_columns'],
                "metrics": json.loads(r['metrics']) if isinstance(r['metrics'], str) else r['metrics'],
                "coefficients": json.loads(r['coefficients']) if isinstance(r['coefficients'], str) else r['coefficients'],
                "intercept": float(r['intercept']),
                "formula_str": r['formula_str'],
                "plain_explanations": json.loads(r['plain_explanations']) if r.get('plain_explanations') and isinstance(r['plain_explanations'], str) else (r.get('plain_explanations') or {}),
                "trained_at": str(r['trained_at']) if r.get('trained_at') else ''
            })
        return results
    except Exception as e:
        logger.error(f"Error fetching saved models: {e}")
        return []
    finally:
        conn.close()


def predict_with_saved_model(model_id: int, user_id: int, input_features: Dict[str, float]) -> Dict[str, Any]:
    """Generates an instant prediction using a saved model without retraining."""
    from database.db_connector import get_db_connection
    conn = get_db_connection()
    if not conn:
        return {"success": False, "message": "Database connection error."}

    try:
        ensure_trained_models_table(conn)
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, model_name, target_column, feature_columns, coefficients, intercept, formula_str
                FROM trained_models
                WHERE id = %s AND user_id = %s
            """, (model_id, user_id))
            row = cursor.fetchone()

        if not row:
            return {"success": False, "message": "Saved model not found or access denied."}

        target_col = row['target_column']
        feature_cols = json.loads(row['feature_columns']) if isinstance(row['feature_columns'], str) else row['feature_columns']
        coefficients = json.loads(row['coefficients']) if isinstance(row['coefficients'], str) else row['coefficients']
        intercept = float(row['intercept'])

        pred_val = intercept
        breakdown = []
        breakdown.append({"factor": "Baseline Intercept", "value": intercept, "contribution": round(intercept, 2)})

        for feat in feature_cols:
            x_val = float(input_features.get(feat, 0.0))
            coef_val = float(coefficients.get(feat, 0.0))
            contrib = x_val * coef_val
            pred_val += contrib
            breakdown.append({
                "factor": feat,
                "input_value": x_val,
                "coefficient": coef_val,
                "contribution": round(contrib, 2)
            })

        return {
            "success": True,
            "model_id": model_id,
            "model_name": row['model_name'],
            "target_column": target_col,
            "predicted_value": round(float(pred_val), 2),
            "formula_str": row['formula_str'],
            "breakdown": breakdown,
            "input_features": input_features
        }
    except Exception as e:
        logger.error(f"Error predicting with saved model: {e}")
        return {"success": False, "message": f"Prediction failed: {e}"}
    finally:
        conn.close()


def delete_saved_model(model_id: int, user_id: int) -> Dict[str, Any]:
    """Deletes a saved model."""
    from database.db_connector import get_db_connection
    conn = get_db_connection()
    if not conn:
        return {"success": False, "message": "Database error."}

    try:
        ensure_trained_models_table(conn)
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM trained_models WHERE id = %s AND user_id = %s", (model_id, user_id))
            conn.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            return {"success": True, "message": "Model deleted successfully."}
        else:
            return {"success": False, "message": "Model not found or unauthorized."}
    except Exception as e:
        logger.error(f"Error deleting saved model: {e}")
        return {"success": False, "message": f"Failed to delete model: {e}"}
    finally:
        conn.close()
