
import html as _html
import json
import logging
import re
import warnings
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from database.db_connector import get_db_connection

logger = logging.getLogger(__name__)

RANDOM_STATE = 42
MIN_REG_ROWS = 20
MIN_CLF_ROWS = 20
MAX_OHE_CARDINALITY = 50
CV_ROW_CAP = 5000
TARGET_KEYWORD_ORDER = ['sales', 'revenue', 'profit', 'price', 'amount', 'adr', 'total', 'quantity', 'lead_time']


# ==============================================================================
# GENERIC HELPERS
# ==============================================================================

def _esc(value: Any) -> str:
    """HTML-escape any dataset-derived text before it is placed into html_content."""
    return _html.escape(str(value), quote=True)


def _row_label(idx: Any) -> Any:
    """User-facing record id that maps back to the ORIGINAL dataset row (1-based for default index)."""
    try:
        if isinstance(idx, (int, np.integer)):
            return int(idx) + 1
    except Exception:
        pass
    return str(idx)


def _name_tokens(col_name: str) -> List[str]:
    s = re.sub(r'([a-z])([A-Z])', r'\1 \2', str(col_name))
    return [t for t in re.split(r'[^a-z0-9]+', s.lower()) if t]


def is_postal_or_geographic_id(col_name: str, series: Optional[pd.Series] = None) -> bool:
    """Checks whether a column is a postal code, zip code, or geographic identifier."""
    c_lower = str(col_name).lower().strip()
    geo_keywords = [
        'postal', 'postcode', 'post_code', 'postal_code', 'postal code',
        'zip', 'zipcode', 'zip_code', 'zip code', 'pincode', 'pin_code', 'pin code',
        'area_code', 'areacode', 'country_code', 'region_code', 'state_code'
    ]
    return any(k in c_lower for k in geo_keywords)


_ID_TOKENS = {'id', 'uuid', 'guid', 'ssn', 'serial', 'idx', 'phone', 'mobile',
              'zip', 'zipcode', 'pincode', 'postcode', 'postal'}


def _name_looks_like_id(col_name: str) -> bool:
    """Token based (so 'paid_amount' / 'price_index' / 'valid' are NOT treated as IDs)."""
    c_lower = str(col_name).lower().strip()
    if c_lower.startswith('unnamed'):
        return True
    tokens = _name_tokens(col_name)
    if not tokens:
        return False
    if any(t in _ID_TOKENS for t in tokens):
        return True
    if tokens in (['index'], ['row', 'index'], ['row', 'no'], ['row', 'num']):
        return True
    for a, b in zip(tokens, tokens[1:]):
        if a in ('account', 'acct', 'order', 'invoice', 'transaction') and b in ('no', 'num', 'number'):
            return True
    return is_postal_or_geographic_id(col_name)


def looks_like_datetime(series: pd.Series, col_name: str = "") -> bool:
    """True for datetime dtype or text columns that really parse as dates."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if pd.api.types.is_numeric_dtype(series):
        return False
    name = str(col_name).lower()
    if not any(k in name for k in ['date', 'time', 'timestamp', 'year', 'month', 'period', 'day']):
        return False
    if any(ex in name for ex in ['lead_time', 'nights', 'duration', 'hour', 'count', 'time_in', 'time_to']):
        return False
    sample = series.dropna().astype(str).head(200)
    if len(sample) == 0:
        return False
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        try:
            parsed = pd.to_datetime(sample, errors='coerce')
        except Exception:
            return False
    return bool(parsed.notna().mean() >= 0.9)


def is_id_or_non_predictive_column(col_name: str, series: pd.Series) -> bool:
    """ID / primary key / sequence / constant column check (name is token based, cardinality is ratio based)."""
    if _name_looks_like_id(col_name):
        return True
    cleaned = series.dropna()
    n = len(cleaned)
    if n == 0:
        return True
    try:
        n_unique = cleaned.nunique()
    except TypeError:
        return True
    if n_unique <= 1:
        return True
    if pd.api.types.is_datetime64_any_dtype(series):
        return False
    if not pd.api.types.is_numeric_dtype(series):
        # free-text / hash like columns: (almost) every value unique
        if n > 20 and n_unique / n >= 0.95:
            return True
    elif not pd.api.types.is_bool_dtype(series):
        if n > 20 and n_unique == n:
            diffs = np.diff(np.sort(cleaned.values.astype(float)))
            if len(diffs) > 0 and np.all(diffs == 1):
                return True
    return False


def _coerce_numeric_like(series: pd.Series) -> Optional[pd.Series]:
    """'1,234.50', '$20', '15%' -> numbers, when >= 90% of non-null values parse."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return None
    cleaned = series.astype(str).str.replace(r'[,\s$€£₹%]', '', regex=True)
    cleaned = cleaned.where(series.notna(), None)
    converted = pd.to_numeric(cleaned, errors='coerce')
    if converted.notna().sum() / len(non_null) >= 0.90:
        return converted
    return None


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Copy + numeric-looking text -> numeric + inf -> NaN. Never mutates the caller's frame."""
    out = df.copy()
    for c in out.columns:
        s = out[c]
        if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            out[c] = s.replace([np.inf, -np.inf], np.nan)
        elif s.dtype == object:
            if _name_looks_like_id(c) or looks_like_datetime(s, c):
                continue
            conv = _coerce_numeric_like(s)
            if conv is not None:
                out[c] = conv.replace([np.inf, -np.inf], np.nan)
    return out


def _target_keyword_rank(col: str) -> Optional[int]:
    c = str(col).lower()
    for i, k in enumerate(TARGET_KEYWORD_ORDER):
        if k in c:
            return i
    return None


def pick_default_target(cols: List[str]) -> Optional[str]:
    best = None
    for pos, c in enumerate(cols):
        r = _target_keyword_rank(c)
        if r is not None and (best is None or (r, pos) < best[0]):
            best = ((r, pos), c)
    if best:
        return best[1]
    return cols[0] if cols else None


# ==============================================================================
# DATASET INTELLIGENCE & LEAKAGE DETECTION ENGINE
# ==============================================================================

def check_target_suitability(col_name: str, series: Optional[pd.Series] = None, modality: str = 'regression') -> Dict[str, Any]:
    """Guardrail: is the selected column a sensible prediction target?"""
    if not col_name:
        return {"is_suitable": False, "warning_type": "empty", "warning": "No target column selected.", "recommendation": None}

    if is_postal_or_geographic_id(col_name, series):
        return {
            "is_suitable": False,
            "warning_type": "categorical_id",
            "warning": f"'{col_name}' is a categorical/geographical ID column. Consider using it in Classification or Frequency analysis instead of Regression.",
            "recommendation": "Select a continuous numerical target (such as Sales, Profit, Quantity, Revenue, Price, or Cost) for Regression."
        }

    if series is not None:
        if is_id_or_non_predictive_column(col_name, series):
            return {
                "is_suitable": False,
                "warning_type": "id_column",
                "warning": f"'{col_name}' appears to be an identifier or non-predictive column with no statistical relationship to other fields.",
                "recommendation": "Choose a numerical business metric with meaningful continuous variation."
            }
        if modality == 'regression':
            if not pd.api.types.is_numeric_dtype(series):
                return {
                    "is_suitable": False, "warning_type": "non_numeric",
                    "warning": f"'{col_name}' is not numeric, so it cannot be used as a regression target.",
                    "recommendation": "Pick a numeric KPI, or use Classification for categorical targets."
                }
            if series.dropna().nunique() <= 2:
                return {
                    "is_suitable": False, "warning_type": "binary_target",
                    "warning": f"'{col_name}' has only {series.dropna().nunique()} distinct values; regression is a poor fit for it.",
                    "recommendation": "Use Classification for binary / discrete targets."
                }

    return {"is_suitable": True, "warning_type": None, "warning": None, "recommendation": None}


def detect_target_leakage_columns(df: pd.DataFrame, target_col: str) -> List[Dict[str, str]]:
    """Flag likely post-outcome fields and clear duplicate target encodings.

    High correlation alone is not proof of leakage: a genuine predictor such as
    Quantity can be strongly related to Sales. Such columns are therefore not
    automatically removed unless there is stronger evidence of target copying.
    """
    warnings_found: List[Dict[str, str]] = []
    if df is None or df.empty or not target_col or target_col not in df.columns:
        return warnings_found

    target_lower = str(target_col).lower()
    outcome_keywords = ('cancel', 'churn', 'checkout', 'exit', 'refund', 'status', 'outcome')
    post_outcome_terms = ('reason', 'notes', 'timestamp', 'flag', 'status', 'outcome', 'refund')
    is_target_outcome = any(k in target_lower for k in outcome_keywords)
    target_num = pd.to_numeric(df[target_col], errors='coerce')
    target_name = re.sub(r'[^a-z0-9]+', '', target_lower)

    for col in df.columns:
        if col == target_col:
            continue
        col_lower = str(col).lower()
        if is_target_outcome and any(term in col_lower for term in post_outcome_terms) and any(
            term in col_lower for term in outcome_keywords
        ):
            warnings_found.append({
                'column': col,
                'reason': f"'{col}' may be recorded after '{target_col}' occurs; review for target leakage."
            })
            continue

        col_num = pd.to_numeric(df[col], errors='coerce')
        mask = target_num.notna() & col_num.notna() & np.isfinite(target_num) & np.isfinite(col_num)
        if int(mask.sum()) < 10:
            continue
        a = target_num.loc[mask].to_numpy(dtype=float)
        b = col_num.loc[mask].to_numpy(dtype=float)
        same_values = np.allclose(a, b, rtol=1e-9, atol=1e-12)
        col_name = re.sub(r'[^a-z0-9]+', '', col_lower)
        target_like_name = (
            col_name in {f'target{target_name}', f'{target_name}target',
                         f'actual{target_name}', f'{target_name}actual'}
            or col_name in {'target', 'label', 'ytrue', 'actualtarget'}
        )
        if same_values and (target_like_name or target_name in col_name):
            warnings_found.append({
                'column': col,
                'reason': f"'{col}' appears to duplicate target '{target_col}' and may cause target leakage."
            })
    return warnings_found


def _classification_leak_cols(df: pd.DataFrame, feature_cols: List[str], target_col: str) -> List[Dict[str, str]]:
    """Features that are a 1:1 relabelling of the class target (e.g. 'status' vs 'status_code')."""
    out = []
    t = df[target_col].astype(str)
    t_n = t.nunique()
    for c in feature_cols:
        if c == target_col:
            continue
        s = df[c]
        try:
            f_n = s.nunique()
            if f_n != t_n or f_n > 50:
                continue
            pair = pd.DataFrame({'f': s.astype(str), 't': t}).dropna()
            if (pair.groupby('f')['t'].nunique() == 1).all() and (pair.groupby('t')['f'].nunique() == 1).all():
                out.append({"column": c, "reason": f"'{c}' is a one-to-one encoding of target '{target_col}' (leakage). Removed."})
        except Exception:
            continue
    return out


def _compat(ok: bool, good: str, bad: str) -> Dict[str, Any]:
    return {"is_trainable": bool(ok), "reason": good if ok else bad}


def get_ml_column_recommendations(df: pd.DataFrame, semantic_types: Optional[Dict[str, str]] = None,
                                  reg_target: Optional[str] = None) -> Dict[str, Any]:
    """
    Detects target candidates, feature columns, leakage risks and relevance scores.
    Relevance for numeric features = max(|Pearson|, |Spearman|) so monotonic non-linear effects are not missed;
    categorical relevance = bias-adjusted correlation ratio (eta) computed on the rows where both values exist.
    Pass reg_target to score against the target actually used.
    """
    if df is None or df.empty:
        return {"numeric_cols": [], "cat_cols": [], "date_cols": [], "recommendations": {},
                "correlations": {}, "leakage_warnings": [], "target_warnings": {}, "compatibility": {}}

    df = prepare_dataframe(df)
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not is_id_or_non_predictive_column(c, df[c])]
    all_numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    date_cols = [c for c in df.columns if looks_like_datetime(df[c], c)]

    cat_cols = []
    for c in df.columns:
        if c in date_cols or is_id_or_non_predictive_column(c, df[c]):
            continue
        nun = df[c].nunique()
        if (not pd.api.types.is_numeric_dtype(df[c]) or nun <= 10) and 1 < nun <= 30:
            cat_cols.append(c)

    target_warnings = {}
    for col in df.columns:
        suit = check_target_suitability(col, df[col], 'regression')
        if not suit.get('is_suitable'):
            target_warnings[col] = suit

    suitable_numeric = [c for c in numeric_cols if not is_postal_or_geographic_id(c, df[c]) and df[c].dropna().nunique() > 2]
    if reg_target and reg_target in df.columns and pd.api.types.is_numeric_dtype(df[reg_target]):
        reg_t = reg_target
    else:
        reg_t = pick_default_target(suitable_numeric) or pick_default_target(numeric_cols) or pick_default_target(all_numeric_cols)

    clf_candidates = [c for c in cat_cols if c != reg_t]
    clf_target = next((c for c in clf_candidates if any(k in c.lower() for k in ['cancel', 'status', 'churn', 'target', 'class', 'segment', 'type', 'result'])),
                      clf_candidates[0] if clf_candidates else None)
    if not clf_target and numeric_cols:
        binary_numeric = [c for c in numeric_cols if df[c].nunique() == 2 and df[c].dropna().isin([0, 1]).all()]
        if binary_numeric:
            clf_target = binary_numeric[0]

    forecast_date = date_cols[0] if date_cols else None
    forecast_value = next((c for c in numeric_cols if c != reg_t and any(k in c.lower() for k in ['adr', 'sales', 'revenue', 'price', 'profit', 'total'])), reg_t)

    leakage_warnings: List[Dict[str, str]] = []
    if reg_t:
        leakage_warnings.extend(detect_target_leakage_columns(df, reg_t))
    if clf_target and clf_target != reg_t:
        leakage_warnings.extend(_classification_leak_cols(df, [c for c in df.columns], clf_target))
    leakage_cols = {w["column"] for w in leakage_warnings}

    feature_correlations: Dict[str, Dict[str, Any]] = {}
    reg_recommended_features: List[str] = []

    def _badge(score: float, hi: float, mid: float, weak: float):
        if score >= hi:
            return "High Relevance", "success"
        if score >= mid:
            return "Moderate Relevance", "primary"
        if score >= weak:
            return "Weak Relevance", "warning"
        return "Low Correlation", "secondary"

    if reg_t and reg_t in df.columns:
        target_series = pd.to_numeric(df[reg_t], errors='coerce')

        for col in numeric_cols:
            if col == reg_t or col in leakage_cols:
                continue
            col_series = pd.to_numeric(df[col], errors='coerce')
            valid = target_series.notna() & col_series.notna()
            pearson = spearman = 0.0
            if valid.sum() >= 5 and col_series[valid].std() > 0 and target_series[valid].std() > 0:
                pearson = float(np.corrcoef(col_series[valid].values, target_series[valid].values)[0, 1])
                spearman = float(col_series[valid].rank().corr(target_series[valid].rank()))
                pearson = 0.0 if np.isnan(pearson) else pearson
                spearman = 0.0 if np.isnan(spearman) else spearman
            score = max(abs(pearson), abs(spearman))
            status, badge = _badge(score, 0.7, 0.35, 0.15)
            feature_correlations[col] = {
                "corr": round(pearson, 3), "abs_corr": round(score, 3), "spearman": round(spearman, 3),
                "status": status, "badge": badge,
                "label": f"{col} ({' + ' if pearson >= 0 else ' - '}{score:.2f})"
            }

        for col in cat_cols:
            if col == reg_t or col in leakage_cols:
                continue
            try:
                cat_df = pd.DataFrame({'cat': df[col], 'y': target_series}).dropna()
                eta = 0.0
                if len(cat_df) >= 10:
                    y = cat_df['y'].values
                    gm = float(np.mean(y))
                    sst = float(np.sum((y - gm) ** 2))
                    k = cat_df['cat'].nunique()
                    if sst > 0 and k > 1 and len(cat_df) > k:
                        g = cat_df.groupby('cat')['y']
                        ssb = float(sum(n * (m - gm) ** 2 for n, m in zip(g.size().values, g.mean().values)))
                        ssw = max(sst - ssb, 0.0)
                        msw = ssw / (len(cat_df) - k)
                        eta2_adj = max(0.0, (ssb - (k - 1) * msw) / (sst + msw))   # bias-adjusted (small groups don't inflate)
                        eta = float(np.sqrt(min(1.0, eta2_adj)))
            except Exception:
                eta = 0.0
            status, badge = _badge(eta, 0.35, 0.20, 0.10)
            feature_correlations[col] = {"corr": round(eta, 3), "abs_corr": round(eta, 3), "status": status,
                                         "badge": badge, "label": f"{col} (η={eta:.2f})"}

        sorted_feats = sorted(feature_correlations, key=lambda k: feature_correlations[k]["abs_corr"], reverse=True)
        # do NOT hard-drop low-correlation features (non-linear / interaction effects); just cap the count
        reg_recommended_features = sorted_feats[:10]

    predictor_candidates = [c for c in df.columns if c != reg_t and c not in leakage_cols and c not in date_cols
                            and not is_id_or_non_predictive_column(c, df[c])]
    n = len(df)
    reg_ok = bool(reg_t and len(predictor_candidates) >= 1 and n >= MIN_REG_ROWS)
    clf_ok = bool(clf_target and len(predictor_candidates) >= 1 and n >= MIN_CLF_ROWS)
    clus_ok = bool(len(numeric_cols) >= 2 and n >= 10)
    fc_ok = bool(forecast_date and forecast_value and n >= 8)
    an_ok = bool(len(numeric_cols) >= 1 and n >= 15)

    def _why(parts):
        return "Dataset is NOT compatible: " + "; ".join(parts) + "."

    reg_bad = [m for ok, m in [(bool(reg_t), "no continuous numeric target"), (len(predictor_candidates) >= 1, "no predictor column"),
                               (n >= MIN_REG_ROWS, f"needs >= {MIN_REG_ROWS} rows")] if not ok]
    clf_bad = [m for ok, m in [(bool(clf_target), "no target with 2+ classes"), (len(predictor_candidates) >= 1, "no predictor column"),
                               (n >= MIN_CLF_ROWS, f"needs >= {MIN_CLF_ROWS} rows")] if not ok]

    compatibility = {
        "regression": _compat(reg_ok, "Linear & Supervised Regression is trainable for this dataset.", _why(reg_bad or ["requirements not met"])),
        "classification": _compat(clf_ok, "Classification is trainable for this dataset.", _why(clf_bad or ["requirements not met"])),
        "clustering": _compat(clus_ok, "K-Means Clustering is trainable for this dataset.", "Dataset is NOT compatible with K-Means Clustering. Requires at least 2 numerical features and 10 rows."),
        "forecasting": _compat(fc_ok, "Time-Series Forecasting is trainable for this dataset.", "Dataset is NOT compatible with Time-Series Forecasting. Requires a Date/Time column, a numerical metric and 8+ rows."),
        "anomaly": _compat(an_ok, "Isolation Forest Anomaly Detection is trainable for this dataset.", "Dataset is NOT compatible with Anomaly Detection. Requires at least 1 numerical feature and 15 rows."),
    }

    clean_num_cols = [c for c in (numeric_cols if numeric_cols else all_numeric_cols) if c not in leakage_cols]

    return {
        "numeric_cols": clean_num_cols,
        "cat_cols": cat_cols,
        "date_cols": date_cols,
        "correlations": feature_correlations,
        "leakage_warnings": leakage_warnings,
        "target_warnings": target_warnings,
        "compatibility": compatibility,
        "recommendations": {
            "regression": {"target": reg_t,
                           "features": reg_recommended_features if reg_recommended_features else [c for c in clean_num_cols if c != reg_t][:8]},
            "classification": {"target": clf_target, "features": [c for c in (clean_num_cols + cat_cols) if c != clf_target][:12]},
            "clustering": {"features": clean_num_cols[:8]},
            "forecasting": {"date_col": forecast_date, "value_col": forecast_value},
            "anomaly": {"features": clean_num_cols[:8]},
        }
    }


# ==============================================================================
# PREPROCESSING PIPELINE (impute + scale numeric, impute + one-hot categorical)
# ==============================================================================

def split_feature_types(df: pd.DataFrame, feature_cols: List[str]) -> Tuple[List[str], List[str], List[Dict[str, str]]]:
    """Returns (numeric, categorical, dropped-with-reason). Nothing is dropped silently."""
    num_cols, cat_cols, dropped = [], [], []
    for c in feature_cols:
        if c not in df.columns:
            dropped.append({"column": c, "reason": "column not found"})
            continue
        s = df[c]
        if pd.api.types.is_datetime64_any_dtype(s) or looks_like_datetime(s, c):
            dropped.append({"column": c, "reason": "date/time column (not used as a plain feature)"})
        elif is_id_or_non_predictive_column(c, s):
            dropped.append({"column": c, "reason": "identifier / constant / non-predictive column"})
        elif pd.api.types.is_numeric_dtype(s):
            num_cols.append(c)
        else:
            nun = s.nunique(dropna=True)
            if nun > MAX_OHE_CARDINALITY:
                dropped.append({"column": c, "reason": f"high-cardinality categorical ({nun} > {MAX_OHE_CARDINALITY})"})
            else:
                cat_cols.append(c)
    return num_cols, cat_cols, dropped


def _make_ohe():
    from sklearn.preprocessing import OneHotEncoder
    try:
        return OneHotEncoder(handle_unknown='ignore', sparse_output=False)
    except TypeError:  # sklearn < 1.2
        return OneHotEncoder(handle_unknown='ignore', sparse=False)


def build_preprocessor(num_cols: List[str], cat_cols: List[str]):
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    transformers = []
    if num_cols:
        transformers.append(('num', Pipeline([('impute', SimpleImputer(strategy='median')),
                                              ('scale', StandardScaler())]), num_cols))
    if cat_cols:
        transformers.append(('cat', Pipeline([('impute', SimpleImputer(strategy='most_frequent')),
                                              ('onehot', _make_ohe())]), cat_cols))
    if not transformers:
        raise ValueError("No usable predictor features after validation.")
    return ColumnTransformer(transformers=transformers, remainder='drop')


def get_preprocessor(df: pd.DataFrame, feature_cols: List[str]):
    """Backward compatible wrapper -> (preprocessor, num_cols, cat_cols). Raises if nothing is usable."""
    num_cols, cat_cols, _ = split_feature_types(df, feature_cols)
    return build_preprocessor(num_cols, cat_cols), num_cols, cat_cols


def _clean_features(df: pd.DataFrame, num_cols: List[str], cat_cols: List[str]) -> pd.DataFrame:
    parts = {}
    for c in num_cols:
        parts[c] = pd.to_numeric(df[c], errors='coerce').astype(float).replace([np.inf, -np.inf], np.nan)
    for c in cat_cols:
        s = df[c]
        parts[c] = s.astype(object).where(s.notna(), np.nan).map(lambda v: v if pd.isna(v) else str(v))
    return pd.DataFrame(parts, index=df.index)[list(num_cols) + list(cat_cols)]


def _reg_metrics(y_true, y_pred) -> Dict[str, float]:
    from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
    return {
        "r2": float(r2_score(y_true, y_pred)),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
    }


# ==============================================================================
# 1. REGRESSION ENGINE
# ==============================================================================

def _build_regression_candidates(use_log: bool) -> Dict[str, Tuple[str, Any]]:
    from sklearn.linear_model import LinearRegression, RidgeCV
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.compose import TransformedTargetRegressor

    cands = {
        "ols": ("Linear Regression (OLS)", LinearRegression()),
        "ridge": ("Ridge Regression", RidgeCV(alphas=np.logspace(-2, 3, 12))),
        "random_forest": ("Random Forest Regressor",
                          RandomForestRegressor(n_estimators=100, max_depth=12, min_samples_leaf=2, random_state=RANDOM_STATE, n_jobs=-1)),
        "gradient_boosting": ("Gradient Boosting Regressor",
                              GradientBoostingRegressor(n_estimators=150, max_depth=3, learning_rate=0.08, subsample=0.8, random_state=RANDOM_STATE)),
    }
    if use_log:   # right-skewed, non-negative targets (sales, revenue...) are far easier to model on a log scale
        cands["ridge_log"] = ("Ridge Regression (log-target)",
                              TransformedTargetRegressor(regressor=RidgeCV(alphas=np.logspace(-2, 3, 12)),
                                                         func=np.log1p, inverse_func=np.expm1, check_inverse=False))
        cands["gradient_boosting_log"] = ("Gradient Boosting (log-target)",
                                          TransformedTargetRegressor(
                                              regressor=GradientBoostingRegressor(n_estimators=150, max_depth=3, learning_rate=0.08,
                                                                                  subsample=0.8, random_state=RANDOM_STATE),
                                              func=np.log1p, inverse_func=np.expm1, check_inverse=False))
    return cands


def _extract_linear_formula(pipe, num_cols: List[str], cat_cols: List[str]) -> Optional[Dict[str, Any]]:
    """Un-scaled coefficients of the ACTIVE linear model (OLS or Ridge) incl. one-hot categorical terms."""
    model = pipe.named_steps['model']
    prep = pipe.named_steps['prep']
    if not hasattr(model, 'coef_'):
        return None
    coef = np.ravel(model.coef_)
    names = list(prep.get_feature_names_out())
    n_num = sum(1 for n in names if n.startswith('num__'))
    intercept = float(np.ravel(model.intercept_)[0])

    coefs: Dict[str, float] = {}
    std_impact: Dict[str, float] = {}
    num_names = [n[5:] for n in names if n.startswith('num__')]
    if n_num:
        scaler = prep.named_transformers_['num'].named_steps['scale']
        for nm, w_s, mu, sd in zip(num_names, coef[:n_num], scaler.mean_, scaler.scale_):
            sd = sd if sd > 1e-12 else 1.0
            coefs[nm] = float(w_s / sd)
            intercept -= float(w_s * mu / sd)
            std_impact[nm] = abs(float(w_s))
    if len(names) > n_num:
        onehot = prep.named_transformers_['cat'].named_steps['onehot']
        keys = []
        for col, cats in zip(cat_cols, onehot.categories_):
            keys.extend([f"{col}={cat}" for cat in cats])
        cat_names = names[n_num:]
        if len(keys) != len(cat_names):
            keys = [n[5:] for n in cat_names]
        for k, w in zip(keys, coef[n_num:]):
            coefs[k] = float(w)
            std_impact[k] = abs(float(w))
    return {"intercept": intercept, "coefs": coefs, "std_impact": std_impact}


def _permutation_importance(pipe, X_test: pd.DataFrame, y_test, scoring: str, cols: List[str]) -> Dict[str, float]:
    """Model-agnostic importance at ORIGINAL column level (one-hot dummies are aggregated automatically)."""
    from sklearn.inspection import permutation_importance
    try:
        Xs, ys = X_test, np.asarray(y_test)
        if len(Xs) > 1500:
            rng = np.random.RandomState(RANDOM_STATE)
            pick = rng.choice(len(Xs), 1500, replace=False)
            Xs, ys = Xs.iloc[pick], ys[pick]
        r = permutation_importance(pipe, Xs, ys, n_repeats=5, random_state=RANDOM_STATE, scoring=scoring)
        imp = np.maximum(r.importances_mean, 0.0)
        tot = float(imp.sum())
        vals = (imp / tot) if tot > 0 else np.zeros_like(imp)
        return dict(sorted({c: round(float(v), 4) for c, v in zip(cols, vals)}.items(), key=lambda kv: kv[1], reverse=True))
    except Exception as e:
        logger.warning(f"Permutation importance failed: {e}")
        return {c: 0.0 for c in cols}


def run_ml_regression(df: pd.DataFrame, target_col: Optional[str] = None, feature_cols: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Leak-free regression AutoML.
      split -> (auto) feature selection on TRAIN rows only -> training-only imputation/scaling ->
      K-fold CV on the training set to choose among OLS / Ridge / RF / GB (+ log-target variants for skewed
      targets) by MAE (RMSE tie-break) -> chosen model scored ONCE on the untouched hold-out set.
    Post-processing (non-negative clipping) is applied inside CV and test scoring, so reported metrics always
    describe exactly the predictions that are displayed.
    """
    if df is None or df.empty:
        return {"success": False, "message": "Dataset is empty."}

    df = prepare_dataframe(df)

    # ---- target validation ---------------------------------------------------
    if not target_col or target_col not in df.columns:
        num_candidates = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not is_id_or_non_predictive_column(c, df[c])
                          and df[c].dropna().nunique() > 2]
        target_col = pick_default_target(num_candidates)
        if not target_col:
            return {"success": False, "message": "No continuous numeric target column found. Select a numeric KPI (Sales, Profit, Price...) or use Classification."}

    y_all = pd.to_numeric(df[target_col], errors='coerce').replace([np.inf, -np.inf], np.nan)
    valid_target = y_all.notna()
    n_input = len(df)
    n_invalid_target = int((~valid_target).sum())
    if int(valid_target.sum()) < MIN_REG_ROWS:
        return {"success": False, "message": f"Insufficient valid numeric target records ({int(valid_target.sum())}); minimum {MIN_REG_ROWS} required."}
    if y_all[valid_target].nunique() <= 2 or float(y_all[valid_target].std()) == 0.0:
        return {"success": False, "message": f"Target '{target_col}' is constant or has <= 2 distinct values; it is not a continuous regression target."}

    work = df.loc[valid_target].copy()
    y = y_all.loc[valid_target]

    # ---- split FIRST (no test-set information may influence feature selection) --
    from sklearn.model_selection import train_test_split, KFold, cross_val_predict
    from sklearn.pipeline import Pipeline
    from sklearn.base import clone
    from sklearn.dummy import DummyRegressor
    from sklearn.metrics import explained_variance_score

    pos = np.arange(len(work))
    tr_pos, te_pos = train_test_split(pos, test_size=0.25, random_state=RANDOM_STATE)
    train_df, test_df = work.iloc[tr_pos], work.iloc[te_pos]
    y_train, y_test = y.iloc[tr_pos], y.iloc[te_pos]

    # ---- feature selection on TRAIN only --------------------------------------
    auto_selected = False
    leakage_removed: List[Dict[str, str]] = []
    if feature_cols:
        feature_cols = [c for c in feature_cols if c in work.columns and c != target_col]
        leak = detect_target_leakage_columns(train_df, target_col)
        leak_set = {w["column"] for w in leak}
        feature_cols = [c for c in feature_cols if c not in leak_set]
        leakage_removed = leak
    else:
        auto_selected = True
        recs = get_ml_column_recommendations(train_df, reg_target=target_col)
        feature_cols = recs.get("recommendations", {}).get("regression", {}).get("features", [])
        leakage_removed = recs.get("leakage_warnings", [])
        if not feature_cols:
            leak_set = {w["column"] for w in leakage_removed}
            feature_cols = [c for c in train_df.columns if c != target_col and c not in leak_set][:10]

    num_cols, cat_cols, dropped_features = split_feature_types(work, feature_cols)
    valid_features = num_cols + cat_cols
    if not valid_features:
        reasons = "; ".join(f"{d['column']}: {d['reason']}" for d in dropped_features[:5])
        return {"success": False, "message": "No usable predictor features after validation." + (f" ({reasons})" if reasons else "")}

    try:
        X_train = _clean_features(train_df, num_cols, cat_cols)
        X_test = _clean_features(test_df, num_cols, cat_cols)

        non_negative = bool((y_train >= 0).all())          # clip only when negatives are impossible in the target's domain
        skew = float(y_train.skew()) if len(y_train) > 2 else 0.0
        use_log = non_negative and skew > 1.0

        template = build_preprocessor(num_cols, cat_cols)
        candidates = _build_regression_candidates(use_log)

        def _post(pred):
            pred = np.asarray(pred, dtype=float)
            pred = np.nan_to_num(pred, nan=float(y_train.mean()), posinf=float(y_train.max()), neginf=float(y_train.min()))
            return np.maximum(0.0, pred) if non_negative else pred

        # CV on (capped) training rows
        n_tr = len(X_train)
        k = 5 if n_tr >= 100 else 3
        kf = KFold(n_splits=min(k, n_tr), shuffle=True, random_state=RANDOM_STATE)
        if n_tr > CV_ROW_CAP:
            sel = np.random.RandomState(RANDOM_STATE).choice(n_tr, CV_ROW_CAP, replace=False)
            X_cv, y_cv = X_train.iloc[sel], y_train.iloc[sel]
        else:
            X_cv, y_cv = X_train, y_train

        base_cv = _reg_metrics(y_cv, _post(cross_val_predict(
            Pipeline([('prep', clone(template)), ('model', DummyRegressor(strategy='mean'))]), X_cv, y_cv, cv=kf)))

        results: Dict[str, Dict[str, Any]] = {}
        for key, (disp, est) in candidates.items():
            try:
                pipe = Pipeline([('prep', clone(template)), ('model', clone(est))])
                cv_m = _reg_metrics(y_cv, _post(cross_val_predict(pipe, X_cv, y_cv, cv=kf)))
                pipe.fit(X_train, y_train)
                pred_te = _post(pipe.predict(X_test))
                te_m = _reg_metrics(y_test, pred_te)
                results[key] = {"name": disp, "pipe": pipe, "pred": pred_te, "cv": cv_m, "test": te_m}
            except Exception as ce:
                logger.warning(f"Candidate '{key}' failed: {ce}")
        if not results:
            return {"success": False, "message": "All regression candidates failed to train."}

        # ---- model selection on CROSS-VALIDATION (never on the test set), MAE first, RMSE tie-break
        active_key = min(results, key=lambda kk: (round(results[kk]["cv"]["mae"], 6), results[kk]["cv"]["rmse"]))
        active = results[active_key]
        active_name = f"{active['name']} (AutoML Best Fit)"
        raw_test_pred = np.asarray(active["pipe"].predict(X_test), dtype=float)
        clipped_count = int(np.sum(raw_test_pred < 0.0)) if non_negative else 0
        y_pred = active["pred"]                       # final post-processed predictions
        test_m = _reg_metrics(y_test, y_pred)         # metrics match the displayed predictions
        r2_raw, mae, rmse = test_m["r2"], test_m["mae"], test_m["rmse"]
        evs = float(explained_variance_score(y_test, y_pred))

        base_pred_te = np.full(len(y_test), float(y_train.mean()))
        base_te = _reg_metrics(y_test, base_pred_te)
        beats_baseline = mae < base_te["mae"]

        target_suit = check_target_suitability(target_col, df[target_col], 'regression')
        target_warning = target_suit.get("warning") if not target_suit.get("is_suitable") else None

        fit_alert = None
        is_weak_fit = False
        if r2_raw < 0 or not beats_baseline:
            is_weak_fit = True
            quality_rating = "Poor Fit (No better than baseline)" if r2_raw >= 0 else "Poor Fit (Negative R²)"
            fit_alert = {
                "type": "danger", "badge": "⚠️ Poor Fit / Baseline Worse",
                "message": (f"Poor Fit: best model by cross-validation ({active['name']}) scores R² = {r2_raw:.4f} and MAE {mae:,.2f} "
                            f"vs {base_te['mae']:,.2f} for a simple mean baseline on unseen rows. The selected features do not explain "
                            f"'{target_col}'. Add informative features or review the target; do not rely on these predictions.")
            }
        elif r2_raw < 0.25:
            is_weak_fit = True
            quality_rating = "Low Explanatory Fit"
            fit_alert = {"type": "warning", "badge": "⚠️ Low Fit / Needs Improvement",
                         "message": f"Low Explanatory Fit (R² = {r2_raw:.4f}). Features explain only {round(r2_raw * 100, 1)}% of variance in '{target_col}'."}
        elif r2_raw < 0.60:
            quality_rating = "Moderate Explanatory Power"
        elif r2_raw < 0.85:
            quality_rating = "Strong Fit (Good Predictive Power)"
        else:
            quality_rating = "Exceptional Fit"

        # ---- formula: ONLY when the active model is really linear (OLS/Ridge), using ITS coefficients
        linear_info = _extract_linear_formula(active["pipe"], num_cols, cat_cols) if active_key in ("ols", "ridge") else None
        if linear_info:
            raw_intercept = linear_info["intercept"]
            unscaled_coefs = {k_: round(v, 4) for k_, v in linear_info["coefs"].items()}
            ranked_terms = sorted(linear_info["std_impact"], key=lambda t: linear_info["std_impact"][t], reverse=True)
            shown = ranked_terms[:6]
            terms = [f"{raw_intercept:+.2f}"]
            for t in shown:
                c_val = unscaled_coefs[t]
                terms.append(f"{'+' if c_val >= 0 else '-'} ({abs(c_val):.2f} × {t})")
            formula_str = f"{target_col} = " + " ".join(terms)
            if len(ranked_terms) > len(shown):
                formula_str += f"  [top {len(shown)} of {len(ranked_terms)} terms shown - simplified]"
            if cat_cols:
                formula_str += "  (categorical terms are 'column=value' offsets)"
        else:
            raw_intercept = 0.0
            unscaled_coefs = {}
            ranked_terms = []

        # ---- feature importance: permutation importance on the hold-out set, any model type
        sorted_importances = _permutation_importance(active["pipe"], X_test, y_test, 'neg_mean_absolute_error', valid_features)
        if not linear_info:
            top_drivers = list(sorted_importances.keys())[:3]
            formula_str = (f"{target_col} = {active['name']} (non-linear model - no single closed-form formula) "
                           f"• Top Drivers: {', '.join(top_drivers)}")

        model_comparison = []
        for key, info in results.items():
            model_comparison.append({
                "model_key": key,
                "model_name": info["name"],
                "r2_score": round(info["test"]["r2"], 4),
                "mae": round(info["test"]["mae"], 2),
                "rmse": round(info["test"]["rmse"], 2),
                "cv_mae": round(info["cv"]["mae"], 2),
                "cv_rmse": round(info["cv"]["rmse"], 2),
                "cv_r2": round(info["cv"]["r2"], 4),
                "status": "Primary Active (Best Fit)" if key == active_key else "Evaluated",
            })
        model_comparison.append({
            "model_key": "baseline", "model_name": "Mean Baseline (reference)",
            "r2_score": round(base_te["r2"], 4), "mae": round(base_te["mae"], 2), "rmse": round(base_te["rmse"], 2),
            "cv_mae": round(base_cv["mae"], 2), "cv_rmse": round(base_cv["rmse"], 2), "cv_r2": round(base_cv["r2"], 4),
            "status": "Reference",
        })

    except Exception as e:
        logger.exception("Regression training error")
        return {"success": False, "message": f"Regression execution failed: {str(e)}"}

    # ---- sample predictions (original-row ids, safe percentage error) ----------
    y_test_arr = y_test.values
    test_index = y_test.index
    sample_preds = []
    for i in range(min(len(y_test_arr), 50)):
        act = round(float(y_test_arr[i]), 2)
        prd = round(float(y_pred[i]), 2)
        diff = round(act - prd, 2)
        abs_err = round(abs(diff), 2)
        pct_err = round(abs_err / abs(act) * 100, 1) if abs(act) > 1e-8 else None   # undefined when actual is 0

        if pct_err is None:
            status_text, status_type, var_txt = "N/A (actual = 0)", "secondary", "N/A"
        else:
            var_txt = f"{pct_err:.1f}%"
            if pct_err <= 15.0:
                status_text, status_type = "Accurate (±15%)", "success"
            elif pct_err <= 35.0:
                status_text, status_type = "Moderate (±35%)", "warning"
            else:
                status_text, status_type = "High Deviation", "danger"

        sample_preds.append({
            "record_id": _row_label(test_index[i]),
            "source_row": _row_label(test_index[i]),
            "actual_value": act, "actual": act,
            "predicted_value": prd, "predicted": prd,
            "residual_error": diff, "error": diff,
            "abs_error": abs_err,
            "variance_pct": var_txt,
            "pct_error": pct_err,
            "status": status_text, "status_type": status_type,
        })

    n_pts = min(len(y_test_arr), 250)
    residuals = [round(float(a - p), 2) for a, p in zip(y_test_arr, y_pred)]
    base_layout = {
        "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
        "margin": {"l": 50, "r": 30, "t": 50, "b": 50}, "font": {"color": "#94A3B8"},
    }

    def _title(t):
        return {"text": t, "font": {"family": "Space Grotesk, sans-serif", "size": 15, "color": "#F8FAFC"}}

    if n_pts > 0 and len(y_pred) == len(y_test_arr):
        lo = float(min(np.min(y_test_arr[:n_pts]), np.min(y_pred[:n_pts])))
        hi = float(max(np.max(y_test_arr[:n_pts]), np.max(y_pred[:n_pts])))
        scatter_data = [
            {"type": "scatter", "mode": "markers", "name": f"{active['name']} Predictions",
             "x": [round(float(v), 2) for v in y_test_arr[:n_pts]], "y": [round(float(v), 2) for v in y_pred[:n_pts]],
             "marker": {"color": "#6366F1", "size": 8, "opacity": 0.75, "line": {"color": "#4338CA", "width": 1}},
             "hovertemplate": f"Actual {target_col}: %{{x}}<br>Predicted {target_col}: %{{y}}<extra></extra>"},
            {"type": "scatter", "mode": "lines", "name": "Ideal 45° Fit Line",
             "x": [round(lo, 2), round(hi, 2)], "y": [round(lo, 2), round(hi, 2)],
             "line": {"color": "#10B981", "dash": "dash", "width": 2}},
        ]
        resid_data = [
            {"type": "scatter", "mode": "markers", "name": "Residual Errors",
             "x": [round(float(v), 2) for v in y_pred[:n_pts]], "y": residuals[:n_pts],
             "marker": {"color": "#EC4899", "size": 7, "opacity": 0.75},
             "hovertemplate": "Predicted: %{x}<br>Residual Error: %{y}<extra></extra>"},
            {"type": "scatter", "mode": "lines", "name": "Zero Error Line (y = 0)",
             "x": [round(float(np.min(y_pred[:n_pts])), 2), round(float(np.max(y_pred[:n_pts])), 2)], "y": [0, 0],
             "line": {"color": "#94A3B8", "dash": "dot", "width": 1.5}},
        ]
    else:
        scatter_data, resid_data = [], []

    scatter_chart = {"data": scatter_data, "layout": {
        "title": _title(f"Regression Fit: Actual vs Predicted {target_col} (R² = {r2_raw:.3f})"),
        "xaxis": {"title": f"Actual {target_col}", "gridcolor": "rgba(148, 163, 184, 0.15)"},
        "yaxis": {"title": f"Predicted {target_col}", "gridcolor": "rgba(148, 163, 184, 0.15)"}, **base_layout}}
    residual_chart = {"data": resid_data, "layout": {
        "title": _title(f"Residual Error Distribution (Target: {target_col})"),
        "xaxis": {"title": f"Predicted {target_col}", "gridcolor": "rgba(148, 163, 184, 0.15)"},
        "yaxis": {"title": "Residual (Actual - Predicted)", "gridcolor": "rgba(148, 163, 184, 0.15)"}, **base_layout}}

    top_imp = list(sorted_importances.items())[:10]
    coef_chart = {"data": [{
        "type": "bar", "orientation": "h",
        "y": [k_ for k_, _ in reversed(top_imp)], "x": [v for _, v in reversed(top_imp)],
        "marker": {"color": "#10B981"},
        "hovertemplate": "Feature: %{y}<br>Permutation Importance: %{x}<extra></extra>"}],
        "layout": {"title": _title("Top Predictive Feature Drivers (permutation importance)"),
                   "xaxis": {"title": "Relative Importance", "gridcolor": "rgba(148, 163, 184, 0.15)"},
                   "yaxis": {"title": "Feature", "gridcolor": "rgba(148, 163, 184, 0.15)"},
                   **{**base_layout, "margin": {"l": 120, "r": 30, "t": 50, "b": 50}}}}

    slope_explanations = []
    for t in ranked_terms[:6]:
        coef = unscaled_coefs[t]
        direction = "increases" if coef >= 0 else "decreases"
        if "=" in t:
            col, val = t.split("=", 1)
            slope_explanations.append(f"<b>{_esc(col)} = {_esc(val)}</b>: this category {direction} <b>{_esc(target_col)}</b> by <b>{abs(coef):.2f}</b> units relative to the model's baseline mix.")
        else:
            slope_explanations.append(f"<b>{_esc(t)}</b>: every 1 unit increase in <i>{_esc(t)}</i> {direction} <b>{_esc(target_col)}</b> by <b>{abs(coef):.2f}</b> units.")

    human_explanations = {
        "formula": formula_str,
        "intercept_explanation": (f"When baseline predictors are 0, baseline <b>{_esc(target_col)}</b> is estimated at <b>{raw_intercept:.2f}</b>."
                                  if linear_info else "Active model is non-linear, so there is no single intercept."),
        "r2_explanation": f"<b>Measured R² = {r2_raw:.3f}</b> ({_esc(quality_rating)}). Active Architecture: <b>{_esc(active_name)}</b>. Selected by cross-validated MAE; scored on {len(y_test)} unseen rows.",
        "error_explanation": f"Predictions deviate by an average of <b>±{mae:.2f} units</b> (MAE) and <b>±{rmse:.2f} units</b> (RMSE); a mean-only baseline would deviate by ±{base_te['mae']:.2f}.",
        "slopes": slope_explanations,
    }

    small_sample = len(work) < 100
    return {
        "success": True,
        "model_type": "regression",
        "model_name": active_name,
        "active_model_key": active_key,
        "target_column": target_col,
        "features": valid_features,
        "feature_columns": valid_features,
        "numeric_features": num_cols,
        "categorical_features": cat_cols,
        "intercept": round(raw_intercept, 4),
        "coefficients": unscaled_coefs,
        "linear_formula_available": bool(linear_info),
        "clip_non_negative": non_negative,
        "formula": formula_str,
        "metrics": {
            "r2_score": round(r2_raw, 4),
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "explained_variance": round(evs, 4),
            "cv_mae": round(active["cv"]["mae"], 2),
            "cv_rmse": round(active["cv"]["rmse"], 2),
            "cv_r2": round(active["cv"]["r2"], 4),
            "baseline_mae": round(base_te["mae"], 2),
            "mae_improvement_vs_baseline_pct": round((1 - mae / base_te["mae"]) * 100, 1) if base_te["mae"] > 0 else 0.0,
            "quality_rating": quality_rating,
            "training_samples": int(len(X_train)),
            "test_samples": int(len(y_test)),
        },
        "data_quality": {
            "rows_input": int(n_input),
            "rows_dropped_invalid_target": n_invalid_target,
            "rows_used": int(len(work)),
            "features_auto_selected": auto_selected,
            "features_dropped": dropped_features,
            "leakage_removed": leakage_removed,
            "predictions_clipped_to_zero": clipped_count,
            "log_target_candidates_used": use_log,
            "small_sample_warning": "Fewer than 100 usable rows: metrics are noisy." if small_sample else None,
        },
        "target_warning": target_warning,
        "is_weak_fit": is_weak_fit,
        "fit_alert": fit_alert,
        "model_comparison": model_comparison,
        "feature_importances": sorted_importances,
        "sample_predictions": sample_preds,
        "human_explanations": human_explanations,
        "plotly_chart": scatter_chart,
        "residual_chart": residual_chart,
        "coef_chart": coef_chart,
    }


# ==============================================================================
# 2. CLASSIFICATION ENGINE
# ==============================================================================

def run_ml_classification(df: pd.DataFrame, target_col: Optional[str] = None, feature_cols: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Class-balanced LogReg / Random Forest / Gradient Boosting compared by cross-validated balanced accuracy,
    winner (tree models) probability-calibrated, scored once on a stratified hold-out set.
    """
    if df is None or df.empty:
        return {"success": False, "message": "Dataset is empty."}

    df = prepare_dataframe(df)

    def _is_discrete_candidate(c):
        s = df[c]
        if is_id_or_non_predictive_column(c, s) or looks_like_datetime(s, c):
            return False
        nun = s.nunique()
        if not (1 < nun <= 10):
            return False
        if pd.api.types.is_numeric_dtype(s):
            v = s.dropna().values
            return bool(np.all(np.equal(np.mod(v, 1), 0)))
        return True

    if not target_col or target_col not in df.columns:
        cat_candidates = [c for c in df.columns if _is_discrete_candidate(c)]
        target_col = next((c for c in cat_candidates if any(k in c.lower() for k in ['cancel', 'status', 'churn', 'class', 'target', 'segment', 'type'])),
                          cat_candidates[0] if cat_candidates else None)
    if not target_col:
        return {"success": False, "message": "No suitable categorical or discrete target column found for Classification."}

    t_raw = df[target_col]
    t_valid = t_raw.notna() & (t_raw.astype(str).str.strip() != '') & (t_raw.astype(str).str.lower().str.strip() != 'nan')
    y_str = t_raw.where(t_valid).astype(object).map(lambda v: v if pd.isna(v) else str(v))
    counts_all = y_str.value_counts()
    rare = counts_all[counts_all < 3].index.tolist()
    keep = t_valid & ~y_str.isin(rare)
    if keep.sum() < MIN_CLF_ROWS:
        return {"success": False, "message": f"Insufficient complete rows for Classification (minimum {MIN_CLF_ROWS} required)."}
    if y_str[keep].nunique() < 2:
        return {"success": False, "message": f"Target column '{target_col}' has only 1 usable class in available data."}
    if y_str[keep].nunique() > 20:
        return {"success": False, "message": f"Target '{target_col}' has too many classes ({y_str[keep].nunique()}) for classification."}

    work = df.loc[keep].copy()
    y = y_str.loc[keep].astype(str)

    from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_predict
    from sklearn.pipeline import Pipeline
    from sklearn.base import clone
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score, balanced_accuracy_score,
                                 brier_score_loss, confusion_matrix)

    pos = np.arange(len(work))
    n_classes = int(y.nunique())
    test_count = max(int(np.ceil(0.25 * len(pos))), n_classes)
    test_count = min(test_count, len(pos) - n_classes)
    if test_count < n_classes or len(pos) - test_count < n_classes:
        return {"success": False, "message": "Not enough records per class for a reliable stratified train/test split."}
    tr_pos, te_pos = train_test_split(pos, test_size=test_count, random_state=RANDOM_STATE, stratify=y.values)
    train_df, test_df = work.iloc[tr_pos], work.iloc[te_pos]
    y_train, y_test = y.iloc[tr_pos], y.iloc[te_pos]

    leakage_removed: List[Dict[str, str]] = []
    if feature_cols:
        feature_cols = [c for c in feature_cols if c in work.columns and c != target_col]
    else:
        feature_cols = [c for c in work.columns if c != target_col]
    leak = _classification_leak_cols(train_df, feature_cols, target_col)
    leak_set = {w["column"] for w in leak}
    leakage_removed = leak
    feature_cols = [c for c in feature_cols if c not in leak_set]

    num_cols, cat_cols, dropped_features = split_feature_types(work, feature_cols)
    # keep a manageable, stable feature set (numeric first, then categorical)
    num_cols, cat_cols = num_cols[:15], cat_cols[:10]
    valid_features = num_cols + cat_cols
    if not valid_features:
        return {"success": False, "message": "Classification requires usable predictor features (no usable predictor features after validation)."}

    try:
        X_train = _clean_features(train_df, num_cols, cat_cols)
        X_test = _clean_features(test_df, num_cols, cat_cols)
        template = build_preprocessor(num_cols, cat_cols)

        cands = {
            "logreg": ("Logistic Regression", LogisticRegression(max_iter=1000, class_weight='balanced', random_state=RANDOM_STATE)),
            "random_forest": ("Random Forest Classifier", RandomForestClassifier(n_estimators=120, max_depth=12, min_samples_leaf=2,
                                                                                  class_weight='balanced_subsample', random_state=RANDOM_STATE, n_jobs=-1)),
            "gradient_boosting": ("Gradient Boosting Classifier", GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=RANDOM_STATE)),
        }

        min_class_train = int(y_train.value_counts().min())
        n_splits = min(5, min_class_train)
        use_cv = n_splits >= 2
        if len(X_train) > CV_ROW_CAP:
            sel = np.random.RandomState(RANDOM_STATE).choice(len(X_train), CV_ROW_CAP, replace=False)
            X_cv, y_cv = X_train.iloc[sel], y_train.iloc[sel]
            use_cv = use_cv and int(y_cv.value_counts().min()) >= n_splits
        else:
            X_cv, y_cv = X_train, y_train

        results = {}
        for key, (disp, est) in cands.items():
            try:
                pipe = Pipeline([('prep', clone(template)), ('model', clone(est))])
                cv_bal = cv_f1 = None
                if use_cv:
                    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
                    cvp = cross_val_predict(pipe, X_cv, y_cv, cv=skf)
                    cv_bal = float(balanced_accuracy_score(y_cv, cvp))
                    cv_f1 = float(f1_score(y_cv, cvp, average='macro', zero_division=0))
                pipe.fit(X_train, y_train)
                pt = pipe.predict(X_test)
                results[key] = {
                    "name": disp, "pipe": pipe, "cv_bal": cv_bal, "cv_f1": cv_f1,
                    "acc": float(accuracy_score(y_test, pt)),
                    "f1": float(f1_score(y_test, pt, average='weighted', zero_division=0)),
                    "macro_f1": float(f1_score(y_test, pt, average='macro', zero_division=0)),
                }
            except Exception as ce:
                logger.warning(f"Classifier '{key}' failed: {ce}")
        if not results:
            return {"success": False, "message": "All classification candidates failed to train."}

        if use_cv:
            active_key = max(results, key=lambda kk: (results[kk]["cv_bal"], results[kk]["cv_f1"]))
        else:
            active_key = "random_forest" if "random_forest" in results else next(iter(results))
        active = results[active_key]

        # probability calibration for tree models (logistic regression is already calibrated)
        calibrated = False
        clf = active["pipe"]
        if active_key != "logreg" and min_class_train >= 6:
            cal_method = 'isotonic' if len(X_train) >= 1000 else 'sigmoid'
            try:
                try:
                    cal = CalibratedClassifierCV(estimator=clone(active["pipe"]), method=cal_method, cv=3)
                except TypeError:
                    cal = CalibratedClassifierCV(base_estimator=clone(active["pipe"]), method=cal_method, cv=3)
                cal.fit(X_train, y_train)
                clf = cal
                calibrated = True
            except Exception as ce:
                logger.warning(f"Calibration skipped: {ce}")

        y_pred = clf.predict(X_test)
        y_prob = clf.predict_proba(X_test)
        classes = [str(c) for c in clf.classes_]

        acc = float(accuracy_score(y_test, y_pred))
        prec = float(precision_score(y_test, y_pred, average="weighted", zero_division=0))
        rec = float(recall_score(y_test, y_pred, average="weighted", zero_division=0))
        f1 = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))
        macro_f1 = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
        bal_acc = float(balanced_accuracy_score(y_test, y_pred))
        cm = confusion_matrix(y_test, y_pred, labels=classes).tolist()
        majority_acc = float(y_test.value_counts(normalize=True).max())

        brier_score = None
        if len(classes) == 2:
            try:
                brier_score = round(float(brier_score_loss((y_test.values == classes[1]).astype(int), y_prob[:, 1])), 4)
            except Exception:
                pass

        importances = _permutation_importance(clf, X_test, y_test, 'balanced_accuracy', valid_features)
        active_name = f"{'Calibrated ' if calibrated else ''}{active['name']}"

        model_comparison = []
        for key, info in results.items():
            is_act = key == active_key
            model_comparison.append({
                "model_key": key,
                "model_name": f"Calibrated {info['name']}" if (is_act and calibrated) else info["name"],
                "accuracy_pct": round((acc if is_act else info["acc"]) * 100, 1),
                "f1_score_pct": round((f1 if is_act else info["f1"]) * 100, 1),
                "cv_balanced_accuracy_pct": round(info["cv_bal"] * 100, 1) if info["cv_bal"] is not None else None,
                "status": "Primary Active (Best CV)" if is_act else "Evaluated",
            })
    except Exception as e:
        logger.exception("Classification execution failed")
        return {"success": False, "message": f"Could not fit classification model: {str(e)}"}

    test_index = y_test.index
    y_test_arr = y_test.values
    sample_preds = []
    for i in range(min(len(y_test_arr), 50)):
        act_class, pred_class = str(y_test_arr[i]), str(y_pred[i])
        is_match = act_class == pred_class
        sample_preds.append({
            "record_id": _row_label(test_index[i]),
            "actual_class": act_class, "predicted_class": pred_class,
            "confidence_pct": round(float(np.max(y_prob[i])) * 100, 1),
            "is_correct": is_match,
            "status_tag": "Correct Match" if is_match else "Misclassified",
        })

    plotly_cm = {
        "data": [{"type": "heatmap", "z": cm, "x": [f"Pred: {c}" for c in classes], "y": [f"Actual: {c}" for c in classes],
                  "colorscale": "Blues", "hoverongaps": False,
                  "hovertemplate": "<b>%{y}</b><br><b>%{x}</b><br>Count: %{z}<extra></extra>"}],
        "layout": {"title": {"text": f"Confusion Matrix: {target_col} (Accuracy = {acc * 100:.1f}%)",
                             "font": {"family": "Space Grotesk, sans-serif", "size": 15, "color": "#F8FAFC"}},
                   "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
                   "xaxis": {"automargin": True}, "yaxis": {"automargin": True},
                   "margin": {"l": 90, "r": 30, "t": 50, "b": 60}, "font": {"color": "#94A3B8"}},
    }

    metrics_res = {
        "accuracy": round(acc * 100, 1), "precision": round(prec * 100, 1), "recall": round(rec * 100, 1),
        "f1_score": round(f1 * 100, 1), "macro_f1": round(macro_f1 * 100, 1),
        "balanced_accuracy": round(bal_acc * 100, 1),
        "majority_class_baseline_accuracy": round(majority_acc * 100, 1),
        "total_records": int(len(work)), "test_records": int(len(y_test)),
    }
    if brier_score is not None:
        metrics_res["brier_calibration_score"] = brier_score

    alert = None
    if acc <= majority_acc + 0.01 and bal_acc < 0.6:
        alert = {"type": "warning", "badge": "⚠️ Weak Classifier",
                 "message": f"Accuracy ({acc * 100:.1f}%) is not better than always predicting the majority class ({majority_acc * 100:.1f}%). Add more informative features."}

    return {
        "success": True,
        "model_type": "classification",
        "model_name": f"{active_name}",
        "active_model_key": active_key,
        "target_column": target_col,
        "classes": classes,
        "features": valid_features,
        "metrics": metrics_res,
        "fit_alert": alert,
        "data_quality": {"rare_classes_removed": [str(r) for r in rare], "features_dropped": dropped_features,
                         "leakage_removed": leakage_removed, "probabilities_calibrated": calibrated},
        "model_comparison": model_comparison,
        "feature_importances": importances,
        "confusion_matrix": cm,
        "sample_predictions": sample_preds,
        "plotly_chart": plotly_cm,
    }


# ==============================================================================
# 3. CLUSTERING ENGINE
# ==============================================================================

def run_ml_clustering(df: pd.DataFrame, feature_cols: Optional[List[str]] = None, n_clusters: int = 3) -> Dict[str, Any]:
    """K-Means with skew-aware scaling, true silhouette, Davies-Bouldin and a data-driven suggested k."""
    if df is None or df.empty:
        return {"success": False, "message": "Dataset is empty."}

    df = prepare_dataframe(df)
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not is_id_or_non_predictive_column(c, df[c])]
    if len(num_cols) < 2:
        return {"success": False, "message": "Clustering requires at least 2 numeric features."}

    if not feature_cols:
        feature_cols = num_cols[:6]
    else:
        feature_cols = [c for c in feature_cols if c in df.columns and pd.api.types.is_numeric_dtype(df[c])
                        and not is_id_or_non_predictive_column(c, df[c])]
    if len(feature_cols) < 2:
        return {"success": False, "message": "Clustering requires at least 2 valid numeric features."}

    sub_df = df[feature_cols].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(sub_df) < 10:
        return {"success": False, "message": "Insufficient numeric records for clustering."}

    try:
        requested_clusters = int(n_clusters or 3)
    except (TypeError, ValueError):
        requested_clusters = 3
    n_c = int(min(max(2, requested_clusters), len(sub_df) - 1, 8))
    X = sub_df.values.astype(float)

    # skew-aware transform: heavy right tails (sales, quantity) would otherwise dominate the distance metric
    X_t = X.copy()
    log_cols = []
    for j, c in enumerate(feature_cols):
        col = X[:, j]
        sk = pd.Series(col).skew()
        if col.min() >= 0 and not np.isnan(sk) and abs(sk) > 1.5:
            X_t[:, j] = np.log1p(col)
            log_cols.append(c)

    sil_score, db_score, inertia, suggested_k = None, None, None, n_c
    sil_by_k: Dict[str, float] = {}
    try:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import silhouette_score, davies_bouldin_score

        X_scaled = StandardScaler().fit_transform(X_t)
        sample_size = min(len(X_scaled), 2000)

        for k in range(2, min(6, len(sub_df) - 1) + 1):
            try:
                lab_k = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10).fit_predict(X_scaled)
                if len(np.unique(lab_k)) > 1:
                    sil_by_k[str(k)] = round(float(silhouette_score(X_scaled, lab_k, sample_size=sample_size, random_state=RANDOM_STATE)), 3)
            except Exception:
                continue
        if sil_by_k:
            suggested_k = int(max(sil_by_k, key=sil_by_k.get))

        kmeans = KMeans(n_clusters=n_c, random_state=RANDOM_STATE, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        if len(np.unique(labels)) > 1:
            sil_score = round(float(silhouette_score(X_scaled, labels, sample_size=sample_size, random_state=RANDOM_STATE)), 3)
            db_score = round(float(davies_bouldin_score(X_scaled, labels)), 3)
        inertia = round(float(kmeans.inertia_), 2)
        distances = np.linalg.norm(X_scaled - kmeans.cluster_centers_[labels], axis=1)
    except Exception as e:
        logger.warning(f"K-Means fallback to pure NumPy: {e}")
        X_scaled = (X_t - X_t.mean(axis=0)) / (X_t.std(axis=0) + 1e-9)
        rng = np.random.RandomState(RANDOM_STATE)
        centroids = X_scaled[rng.choice(len(X_scaled), n_c, replace=False)]
        for _ in range(30):
            labels = np.argmin(np.linalg.norm(X_scaled[:, None, :] - centroids[None, :, :], axis=2), axis=1)
            for k in range(n_c):
                if np.any(labels == k):
                    centroids[k] = X_scaled[labels == k].mean(axis=0)
        distances = np.linalg.norm(X_scaled - centroids[labels], axis=1)
        try:
            from sklearn.metrics import silhouette_score, davies_bouldin_score
            if 1 < len(np.unique(labels)) < len(labels):
                sample_size = min(len(X_scaled), 2000)
                sil_score = round(float(silhouette_score(X_scaled, labels, sample_size=sample_size, random_state=RANDOM_STATE)), 3)
                db_score = round(float(davies_bouldin_score(X_scaled, labels)), 3)
        except Exception as metric_error:
            logger.warning(f"Could not calculate fallback clustering metrics: {metric_error}")

    sub_df = sub_df.copy()
    sub_df["Cluster"] = [f"Segment {l + 1}" for l in labels]

    profiles = []
    cluster_counts = sub_df["Cluster"].value_counts().to_dict()
    overall_mean = {c: float(sub_df[c].mean()) for c in feature_cols}
    for idx in range(n_c):
        c_name = f"Segment {idx + 1}"
        c_df = sub_df[sub_df["Cluster"] == c_name]
        size = int(cluster_counts.get(c_name, 0))
        mean_vals = {col: round(float(c_df[col].mean()), 2) if size > 0 else 0.0 for col in feature_cols}
        vs_overall = {col: (round((mean_vals[col] / overall_mean[col] - 1) * 100, 1) if abs(overall_mean[col]) > 1e-9 else None) for col in feature_cols}
        profiles.append({"segment_name": c_name, "size": size, "percentage": round(size / len(sub_df) * 100, 1),
                         "top_characteristics": mean_vals, "vs_overall_avg_pct": vs_overall})

    sample_preds = []
    for i in range(min(len(sub_df), 50)):
        row = sub_df.iloc[i]
        c_label = str(row["Cluster"])
        summary = ", ".join([f"{c}: {round(float(row[c]), 1)}" for c in feature_cols[:3]])
        sample_preds.append({
            "record_id": _row_label(sub_df.index[i]),
            "assigned_cluster": c_label, "cluster_name": c_label,
            "distance_to_center": round(float(distances[i]), 3),
            "sample_features_summary": summary, "features_summary": summary, "segment_badge": c_label,
        })

    x_col, y_col = feature_cols[0], feature_cols[1]
    colors = ["#4F46E5", "#06B6D4", "#10B981", "#F59E0B", "#EC4899", "#8B5CF6", "#EF4444", "#14B8A6"]
    plot_df = sub_df.sample(min(len(sub_df), 300), random_state=RANDOM_STATE)
    chart_data = []
    for idx, c_name in enumerate(sorted(sub_df["Cluster"].unique())):
        subset = plot_df[plot_df["Cluster"] == c_name]
        chart_data.append({"type": "scatter", "mode": "markers", "name": c_name,
                           "x": subset[x_col].tolist(), "y": subset[y_col].tolist(),
                           "marker": {"color": colors[idx % len(colors)], "size": 8, "opacity": 0.8},
                           "hovertemplate": f"<b>{c_name}</b><br>{x_col}: %{{x}}<br>{y_col}: %{{y}}<extra></extra>"})
    plotly_chart = {"data": chart_data, "layout": {
        "title": {"text": f"Cluster Segmentation: {x_col} vs {y_col} (Silhouette = {sil_score if sil_score is not None else 'N/A'})",
                  "font": {"family": "Space Grotesk, sans-serif", "size": 15, "color": "#F8FAFC"}},
        "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
        "xaxis": {"title": x_col, "gridcolor": "rgba(148, 163, 184, 0.15)"},
        "yaxis": {"title": y_col, "gridcolor": "rgba(148, 163, 184, 0.15)"},
        "margin": {"l": 50, "r": 30, "t": 50, "b": 50}, "font": {"color": "#94A3B8"}}}

    return {
        "success": True,
        "model_type": "clustering",
        "model_name": "K-Means Clustering",
        "n_clusters": n_c,
        "features": feature_cols,
        "metrics": {
            "silhouette_score": sil_score,
            "davies_bouldin_index": db_score,
            "inertia": inertia,
            "n_clusters": n_c,
            "suggested_k": suggested_k,
            "silhouette_by_k": sil_by_k,
            "log_transformed_features": log_cols,
            "quality_rating": ("Not Available" if sil_score is None else ("Strong Separation" if sil_score >= 0.5 else ("Moderate Grouping" if sil_score >= 0.35 else "Loose Clusters"))),
            "total_samples": int(len(sub_df)),
        },
        "profiles": profiles,
        "sample_predictions": sample_preds,
        "plotly_chart": plotly_chart,
    }


# ==============================================================================
# 4. FORECASTING ENGINE
# ==============================================================================

def _parse_dates(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    best = None
    for dayfirst in (False, True):
        parsed = None
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            try:
                parsed = pd.to_datetime(series, errors='coerce', dayfirst=dayfirst, format='mixed')
            except (TypeError, ValueError):
                try:
                    parsed = pd.to_datetime(series, errors='coerce', dayfirst=dayfirst)
                except Exception:
                    parsed = None
        if parsed is not None:
            cnt = int(parsed.notna().sum())
            # tie-break for ambiguous DD/MM vs MM/DD: prefer the reading that keeps rows in chronological
            # order, then the one with the most regular spacing
            valid = parsed.dropna()
            diffs = valid.diff().dropna().dt.total_seconds()
            mono = float((diffs >= 0).mean()) if len(diffs) else 0.0
            cv = float(diffs.std() / diffs.mean()) if len(diffs) > 1 and diffs.mean() > 0 else 9e9   # regular spacing wins
            key = (cnt, round(mono, 3), -round(cv, 3))
            if best is None or key > best[0]:
                best = (key, parsed)
    return best[1] if best else pd.Series(pd.NaT, index=series.index)


def _infer_rule(dates: pd.Series) -> Tuple[str, int]:
    d = pd.Series(dates).drop_duplicates().sort_values()
    if len(d) < 3:
        return "D", 7
    med = float(d.diff().dropna().dt.total_seconds().median()) / 86400.0
    if med <= 1.5:
        return "D", 7
    if med <= 10:
        return "W", 52
    if med <= 45:
        return "MS", 12
    if med <= 120:
        return "QS", 4
    return "YS", 1


def _detect_period(y: np.ndarray) -> int:
    """Autocorrelation based seasonality for series without dates."""
    n = len(y)
    if n < 12:
        return 1
    x = np.arange(n)
    resid = y - np.polyval(np.polyfit(x, y, 1), x)
    denom = float(np.sum(resid ** 2))
    if denom <= 0:
        return 1
    best_lag, best_acf = 1, 0.35
    for lag in range(2, min(60, n // 3) + 1):
        acf = float(np.sum(resid[:-lag] * resid[lag:]) / denom)
        if acf > best_acf:
            best_lag, best_acf = lag, acf
    return best_lag


def _fc_naive(y, h, p):
    return np.full(h, y[-1], dtype=float)


def _fc_mean(y, h, p):
    k = min(len(y), max(p if p > 1 else 3, 3))
    return np.full(h, float(np.mean(y[-k:])), dtype=float)


def _fc_seasonal_naive(y, h, p):
    if p <= 1 or len(y) < 2 * p:
        raise ValueError("not enough history")
    last = y[-p:]
    return np.array([last[i % p] for i in range(h)], dtype=float)


def _fc_trend(y, h, p):
    w = min(len(y), 120)
    seg = y[-w:]
    slope, intercept = np.polyfit(np.arange(w, dtype=float), seg, 1)
    return slope * np.arange(w, w + h, dtype=float) + intercept


def _fc_trend_seasonal(y, h, p):
    if p <= 1 or len(y) < 2 * p:
        raise ValueError("not enough history")
    w = min(len(y), max(2 * p, (120 // p) * p))
    seg = y[-w:]
    x = np.arange(w, dtype=float)
    slope, intercept = np.polyfit(x, seg, 1)
    resid = seg - (slope * x + intercept)
    cycle = np.array([np.mean(resid[i::p]) for i in range(p)])
    fx = np.arange(w, w + h, dtype=float)
    return slope * fx + intercept + np.array([cycle[(w + i) % p] for i in range(h)])


def _fc_damped_holt(y, h, p):
    """Damped-trend exponential smoothing with a small grid search on one-step error."""
    best, best_err = None, np.inf
    for a in (0.2, 0.4, 0.6, 0.8):
        for b in (0.05, 0.15, 0.3):
            level, trend, err = y[0], 0.0, 0.0
            for t in range(1, len(y)):
                pred = level + 0.9 * trend
                err += abs(y[t] - pred)
                new_level = a * y[t] + (1 - a) * (level + 0.9 * trend)
                trend = b * (new_level - level) + (1 - b) * 0.9 * trend
                level = new_level
            if err < best_err:
                best_err, best = err, (level, trend)
    level, trend = best
    out, damp = [], 0.0
    for i in range(1, h + 1):
        damp += 0.9 ** i
        out.append(level + damp * trend)
    return np.array(out, dtype=float)


_FC_METHODS = {
    "Naive (last value)": _fc_naive,
    "Moving Average": _fc_mean,
    "Seasonal Naive": _fc_seasonal_naive,
    "Linear Trend": _fc_trend,
    "Trend + Seasonality": _fc_trend_seasonal,
    "Damped Trend Smoothing": _fc_damped_holt,
}


def _backtest(y: np.ndarray, fn, p: int, val_size: int, folds: int, min_train: int) -> Optional[np.ndarray]:
    errs = []
    for f in range(folds):
        end = len(y) - f * val_size
        tr_end = end - val_size
        if tr_end < min_train:
            break
        pred = fn(y[:tr_end], val_size, p)
        errs.append(y[tr_end:end] - pred)
    return np.concatenate(errs) if errs else None


def run_ml_forecasting(df: pd.DataFrame, date_col: Optional[str] = None, value_col: Optional[str] = None, horizon: int = 14) -> Dict[str, Any]:
    """
    Aggregates to the data's real frequency (daily / weekly / monthly / quarterly / yearly), compares several
    forecasters with a rolling-origin backtest, keeps the best one and builds 95% bands from its backtest errors.
    """
    if df is None or df.empty:
        return {"success": False, "message": "Dataset is empty."}

    df = prepare_dataframe(df)
    try:
        horizon = int(horizon or 14)
    except (TypeError, ValueError):
        horizon = 14
    horizon = int(min(max(1, horizon), 365))

    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not is_id_or_non_predictive_column(c, df[c])]
    date_candidates = [c for c in df.columns if looks_like_datetime(df[c], c)]   # numeric 'lead_time' is no longer mistaken for a date

    if not date_col or date_col not in df.columns:
        date_col = date_candidates[0] if date_candidates else None
    if not value_col or value_col not in df.columns:
        value_col = pick_default_target([c for c in num_cols if c != date_col])
    if not value_col:
        return {"success": False, "message": "Forecasting requires a numerical value column."}

    values = pd.to_numeric(df[value_col], errors="coerce").replace([np.inf, -np.inf], np.nan)
    notes: List[str] = []
    valid_date_found = False
    rule, period = None, 1

    if date_col:
        parsed = _parse_dates(df[date_col])
        tmp = pd.DataFrame({"d": parsed, "v": values}).dropna()
        if len(tmp) >= 8 and tmp["d"].nunique() >= 8:
            valid_date_found = True
            tmp = tmp.sort_values("d")
            rule, period = _infer_rule(tmp["d"])
            agg_sum = any(k in str(value_col).lower() for k in ['sales', 'revenue', 'amount', 'quantity', 'profit', 'total', 'count', 'orders', 'units'])
            grouped = tmp.set_index("d")["v"].resample(rule)
            if agg_sum:
                ts = grouped.sum(min_count=1).fillna(0.0)    # periods without transactions have 0 sales
            else:
                ts = grouped.mean().interpolate(method="linear", limit_direction="both")
            ts = ts.iloc[-1500:]
        else:
            notes.append(f"Column '{date_col}' did not contain enough valid dates; forecasting on record order instead.")

    if not valid_date_found:
        vals = values.dropna().reset_index(drop=True)
        ts = vals
        period = 1

    y_all = np.asarray(ts.values, dtype=float)
    y_all = y_all[np.isfinite(y_all)]
    if len(y_all) < 8:
        return {"success": False, "message": "Forecasting requires at least 8 chronological records."}

    y_vals = y_all[-min(len(y_all), 1500):]
    if not valid_date_found:
        period = _detect_period(y_vals)
    if period > 1 and len(y_vals) < 2 * period:
        period = 1
    non_negative = bool(np.all(y_vals >= 0))

    val_size = max(2, min(horizon, len(y_vals) // 5))
    min_train = max(6, 2 * period if period > 1 else 6)
    folds = 3

    method_scores: Dict[str, Dict[str, Any]] = {}
    for name, fn in _FC_METHODS.items():
        try:
            errs = _backtest(y_vals, fn, period, val_size, folds, min_train)
            if errs is None or len(errs) == 0 or not np.all(np.isfinite(errs)):
                continue
            method_scores[name] = {"fn": fn, "errs": errs, "mae": float(np.mean(np.abs(errs))),
                                   "rmse": float(np.sqrt(np.mean(errs ** 2)))}
        except Exception:
            continue
    if not method_scores:
        return {"success": False, "message": "Not enough history to backtest any forecasting method."}

    best_name = min(method_scores, key=lambda m: (method_scores[m]["mae"], method_scores[m]["rmse"]))
    best = method_scores[best_name]
    naive_mae = method_scores.get("Naive (last value)", best)["mae"]

    future_preds = np.asarray(best["fn"](y_vals, horizon, period), dtype=float)
    if non_negative:
        future_preds = np.maximum(0.0, future_preds)

    sigma = max(float(np.std(best["errs"])), float(best["rmse"]) * 0.5, 0.02 * float(np.mean(np.abs(y_vals))), 1e-9)
    widen = np.sqrt(1.0 + 0.2 * np.arange(horizon))
    lower_bound = future_preds - 1.96 * sigma * widen
    upper_bound = future_preds + 1.96 * sigma * widen
    if non_negative:
        lower_bound = np.maximum(0.0, lower_bound)

    # _backtest appends the most recent validation fold first, so align its errors
    # with the most recent actual values when calculating MAPE.
    recent_errors = np.asarray(best["errs"][:val_size], dtype=float)
    last_actual = np.asarray(y_vals[-len(recent_errors):], dtype=float)
    nz = np.abs(last_actual) > 1e-9
    val_mape = None
    if len(recent_errors) == len(last_actual) and nz.any():
        val_mape = round(float(np.mean(np.abs(recent_errors[nz]) / np.abs(last_actual[nz])) * 100), 1)

    if valid_date_found:
        last_date = ts.index[-1]
        future_dates = [d.strftime("%Y-%m-%d") for d in pd.date_range(start=last_date, periods=horizon + 1, freq=rule)[1:]]
        hist_dates = [d.strftime("%Y-%m-%d") for d in ts.index[-min(len(ts), 120):]]
    else:
        future_dates = [f"T+{i + 1}" for i in range(horizon)]
        hist_dates = [f"T-{min(len(y_vals), 120) - i}" for i in range(min(len(y_vals), 120))]
    hist_vals = y_vals[-len(hist_dates):]

    base_k = min(len(y_vals), period if period > 1 else 3)
    base_val = float(np.mean(y_vals[-base_k:]))

    def _growth(v):
        return None if abs(base_val) < 1e-9 else round((v - base_val) / abs(base_val) * 100, 1)

    sample_preds = []
    for i in range(horizon):
        proj = round(float(future_preds[i]), 2)
        g = _growth(proj)
        direction = "Stable" if (g is not None and g == 0) else ("Upward" if proj > base_val else ("Downward" if proj < base_val else "Stable"))
        sample_preds.append({
            "period": future_dates[i],
            "projected_forecast": proj,
            "lower_bound_95": round(float(lower_bound[i]), 2),
            "upper_bound_95": round(float(upper_bound[i]), 2),
            "growth_trend": f"{g:+.1f}%" if g is not None else "N/A",
            "trend_direction": direction,
        })

    plotly_chart = {
        "data": [
            {"type": "scatter", "mode": "lines+markers", "name": "Historical Actuals", "x": hist_dates,
             "y": [round(float(v), 2) for v in hist_vals], "line": {"color": "#4F46E5", "width": 2.5}, "marker": {"size": 5}},
            {"type": "scatter", "mode": "lines+markers", "name": "Projected Forecast", "x": future_dates,
             "y": [round(float(v), 2) for v in future_preds], "line": {"color": "#10B981", "width": 3, "dash": "dash"},
             "marker": {"size": 6, "color": "#10B981"}},
            {"type": "scatter", "mode": "lines", "name": "Upper 95% Bound", "x": future_dates,
             "y": [round(float(v), 2) for v in upper_bound], "line": {"width": 0}, "showlegend": False},
            {"type": "scatter", "mode": "lines", "name": "95% Calibrated Band", "x": future_dates,
             "y": [round(float(v), 2) for v in lower_bound], "fill": "tonexty", "fillcolor": "rgba(16, 185, 129, 0.15)", "line": {"width": 0}},
        ],
        "layout": {
            "title": {"text": f"Future Forecast: {value_col} ({horizon} Periods Ahead, Freq: {rule or 'Sequence'}, Method: {best_name})",
                      "font": {"family": "Space Grotesk, sans-serif", "size": 15, "color": "#F8FAFC"}},
            "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
            "xaxis": {"title": "Timeline", "gridcolor": "rgba(148, 163, 184, 0.15)"},
            "yaxis": {"title": value_col, "gridcolor": "rgba(148, 163, 184, 0.15)"},
            "margin": {"l": 50, "r": 30, "t": 50, "b": 50}, "font": {"color": "#94A3B8"}},
    }

    avg_projected = float(np.mean(future_preds))
    growth_overall = _growth(avg_projected)

    model_comparison = [{"model_name": n, "backtest_mae": round(s["mae"], 2), "backtest_rmse": round(s["rmse"], 2),
                         "status": "Primary Active (Best Backtest)" if n == best_name else "Evaluated"}
                        for n, s in sorted(method_scores.items(), key=lambda kv: kv[1]["mae"])]

    return {
        "success": True,
        "model_type": "forecasting",
        "model_name": f"Auto Forecast ({best_name})",
        "selected_method": best_name,
        "date_column": date_col if valid_date_found else "Chronological Index",
        "value_column": value_col,
        "inferred_frequency": rule or "Sequence",
        "horizon": horizon,
        "notes": notes,
        "metrics": {
            "avg_projected_value": round(avg_projected, 2),
            "growth_trend_pct": growth_overall if growth_overall is not None else 0.0,
            "validation_rmse": round(best["rmse"], 2),
            "validation_mae": round(best["mae"], 2),
            "validation_mape_pct": val_mape,
            "naive_baseline_mae": round(naive_mae, 2),
            "beats_naive_baseline": bool(best["mae"] < naive_mae),
            "season_period_length": int(period),
            "historical_periods": int(len(y_vals)),
            "forecast_periods": horizon,
        },
        "model_comparison": model_comparison,
        "sample_predictions": sample_preds,
        "plotly_chart": plotly_chart,
    }


# ==============================================================================
# 5. ANOMALY DETECTION ENGINE
# ==============================================================================

def run_ml_anomaly_detection(df: pd.DataFrame, feature_cols: Optional[List[str]] = None, contamination: float = 0.05) -> Dict[str, Any]:
    """Isolation Forest + robust (median/MAD) z-scores for explainable drivers + statistical severity bands."""
    if df is None or df.empty:
        return {"success": False, "message": "Dataset is empty."}

    df = prepare_dataframe(df)
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not is_id_or_non_predictive_column(c, df[c])]
    if len(num_cols) < 1:
        return {"success": False, "message": "Anomaly detection requires at least 1 numeric feature."}

    if not feature_cols:
        feature_cols = num_cols[:8]
    else:
        feature_cols = [c for c in feature_cols if c in df.columns and pd.api.types.is_numeric_dtype(df[c])
                        and not is_id_or_non_predictive_column(c, df[c])]
    if not feature_cols:
        return {"success": False, "message": "No valid numeric features selected for anomaly detection."}

    sub_df = df[feature_cols].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().copy()
    if len(sub_df) < 15:
        return {"success": False, "message": "Insufficient valid records for anomaly detection."}

    X = sub_df.values.astype(float)
    try:
        contam = float(contamination)
    except (TypeError, ValueError):
        contam = 0.05
    if not np.isfinite(contam):
        contam = 0.05
    contam = min(max(0.01, contam), 0.20)

    med = np.median(X, axis=0)
    mad = np.median(np.abs(X - med), axis=0) * 1.4826
    mad = np.where(mad < 1e-9, np.std(X, axis=0) + 1e-9, mad)
    robust_z = (X - med) / mad

    try:
        from sklearn.ensemble import IsolationForest
        clf = IsolationForest(n_estimators=200, contamination=contam, random_state=RANDOM_STATE, n_jobs=-1)
        preds = clf.fit_predict(X)
        scores = -clf.decision_function(X)
    except Exception as e:
        logger.warning(f"IsolationForest fallback: {e}")
        scores = np.max(np.abs(robust_z), axis=1)
        thresh = np.percentile(scores, (1.0 - contam) * 100)
        preds = np.where(scores >= thresh, -1, 1)

    sub_df["Anomaly_Flag"] = preds
    sub_df["Anomaly_Score"] = np.round(scores, 3)
    z_by_index = {idx: robust_z[i] for i, idx in enumerate(sub_df.index)}

    anomalies_df = sub_df[sub_df["Anomaly_Flag"] == -1].sort_values(by="Anomaly_Score", ascending=False)
    anomaly_count = len(anomalies_df)
    anomaly_rate = round(anomaly_count / len(sub_df) * 100, 2)

    if anomaly_count > 0:
        anom_scores = anomalies_df["Anomaly_Score"].values
        mean_score, std_score = float(np.mean(anom_scores)), float(np.std(anom_scores))
        p90 = float(np.percentile(anom_scores, 90)) if anomaly_count >= 5 else float(np.max(anom_scores))
    else:
        mean_score, std_score, p90 = 0.0, 1.0, 0.0

    sample_preds = []
    for i in range(min(anomaly_count, 50)):
        row = anomalies_df.iloc[i]
        idx = anomalies_df.index[i]
        score_val = float(row["Anomaly_Score"])
        if score_val >= mean_score + 1.5 * std_score or score_val >= p90:
            severity = "Critical"
        elif score_val >= mean_score + 0.5 * std_score:
            severity = "High"
        else:
            severity = "Moderate"
        z_row = z_by_index[idx]
        j = int(np.argmax(np.abs(z_row)))
        driver = feature_cols[j]
        sample_preds.append({
            "record_id": _row_label(idx),
            "anomaly_score": round(score_val, 3),
            "primary_driver": f"{driver} = {round(float(row[driver]), 2)}",
            "driver_direction": "Unusually high" if z_row[j] > 0 else "Unusually low",
            "driver_robust_z": round(float(z_row[j]), 2),
            "values_summary": ", ".join([f"{c}: {round(float(row[c]), 1)}" for c in feature_cols[:3]]),
            "severity": severity,
        })

    x_col = feature_cols[0]
    y_col = feature_cols[1] if len(feature_cols) >= 2 else "Anomaly_Score"
    normals = sub_df[sub_df["Anomaly_Flag"] == 1]
    normal_subset = normals.sample(min(len(normals), 300), random_state=RANDOM_STATE) if len(normals) else normals

    plotly_chart = {
        "data": [
            {"type": "scatter", "mode": "markers", "name": "Normal Records",
             "x": normal_subset[x_col].tolist(), "y": normal_subset[y_col].tolist(),
             "marker": {"color": "#06B6D4", "size": 6, "opacity": 0.65},
             "hovertemplate": f"Normal<br>{x_col}: %{{x}}<br>{y_col}: %{{y}}<extra></extra>"},
            {"type": "scatter", "mode": "markers", "name": "Detected Anomalies",
             "x": anomalies_df[x_col].head(100).tolist(), "y": anomalies_df[y_col].head(100).tolist(),
             "marker": {"color": "#EF4444", "size": 10, "symbol": "diamond", "line": {"color": "#FFFFFF", "width": 1.5}},
             "hovertemplate": f"<b>ANOMALY</b><br>{x_col}: %{{x}}<br>{y_col}: %{{y}}<extra></extra>"},
        ],
        "layout": {
            "title": {"text": f"Anomaly Detection Map: {x_col} vs {y_col} ({anomaly_count} Anomalies Found)",
                      "font": {"family": "Space Grotesk, sans-serif", "size": 15, "color": "#F8FAFC"}},
            "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
            "xaxis": {"title": x_col, "gridcolor": "rgba(148, 163, 184, 0.15)"},
            "yaxis": {"title": y_col, "gridcolor": "rgba(148, 163, 184, 0.15)"},
            "margin": {"l": 50, "r": 30, "t": 50, "b": 50}, "font": {"color": "#94A3B8"}},
    }

    return {
        "success": True,
        "model_type": "anomaly",
        "model_name": "Isolation Forest Anomaly Model",
        "features": feature_cols,
        "metrics": {
            "total_records_analyzed": int(len(sub_df)),
            "anomalies_detected": int(anomaly_count),
            "anomaly_rate_pct": anomaly_rate,
            "contamination_parameter": f"{round(contam * 100)}%",
        },
        "sample_predictions": sample_preds,
        "plotly_chart": plotly_chart,
    }


# ==============================================================================
# MODEL PERSISTENCE & REUSABILITY (linear models: numeric AND categorical terms)
# ==============================================================================

def ensure_trained_models_table(conn):
    """Ensures that the trained_models database table exists."""
    if not conn:
        return False
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
        return True
    except Exception as e:
        logger.exception(f"Could not initialize trained_models table: {e}")
        return False


def save_trained_model(user_id: int, dataset_id: int, model_data: Dict[str, Any], custom_name: Optional[str] = None) -> Dict[str, Any]:
    """Persists a LINEAR regression result (OLS/Ridge) for instant re-use. Non-linear models cannot be stored as coefficients."""
    if not model_data or not model_data.get("success"):
        return {"success": False, "message": "No successful model result to save."}
    if model_data.get("model_type", "regression") != "regression":
        return {"success": False, "message": "Only regression models can be saved for instant prediction."}
    if not model_data.get("linear_formula_available", bool(model_data.get("coefficients"))):
        return {"success": False, "message": "The active model is non-linear (tree ensemble / log-target), which cannot be stored as a formula. "
                                             "Re-run with a linear model active, or use the live prediction table."}

    conn = get_db_connection()
    if not conn:
        return {"success": False, "message": "Database connection failed."}

    try:
        if not ensure_trained_models_table(conn):
            return {"success": False, "message": "Could not initialize trained_models table."}
        target_col = model_data.get('target_column') or 'Target'
        m_name = custom_name.strip() if custom_name and custom_name.strip() else f"Linear Model ({target_col})"
        metrics = dict(model_data.get('metrics', {}))
        metrics['clip_non_negative'] = bool(model_data.get('clip_non_negative', False))

        feature_cols_json = json.dumps(model_data.get('features', []))
        metrics_json = json.dumps(metrics)
        coef_json = json.dumps(model_data.get('coefficients', {}))
        intercept_val = float(model_data.get('intercept', 0.0))
        formula = str(model_data.get('formula') or (model_data.get('human_explanations', {}) or {}).get('formula') or '')
        explanations_json = json.dumps(model_data.get('human_explanations', {}))

        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO trained_models
                (user_id, dataset_id, model_name, model_type, target_column, feature_columns, metrics, coefficients, intercept, formula_str, plain_explanations)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, dataset_id, m_name, 'regression', target_col, feature_cols_json, metrics_json, coef_json,
                  intercept_val, formula, explanations_json))
            conn.commit()
            model_id = cursor.lastrowid

        return {"success": True, "message": f"Model '{m_name}' successfully saved!", "model_id": model_id, "model_name": m_name}
    except Exception as e:
        logger.error(f"Error saving trained model: {e}")
        return {"success": False, "message": f"Failed to save model: {e}"}
    finally:
        conn.close()


def _loads(value, default):
    if value is None:
        return default
    if isinstance(value, (bytes, bytearray)):
        value = value.decode('utf-8')
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return default
    return value


def get_saved_models(user_id: int, dataset_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Retrieves all saved models for a user and optional dataset."""
    conn = get_db_connection()
    if not conn:
        return []

    try:
        if not ensure_trained_models_table(conn):
            return []
        cols = ("id, user_id, dataset_id, model_name, model_type, target_column, feature_columns, metrics, "
                "coefficients, intercept, formula_str, plain_explanations, trained_at")
        with conn.cursor() as cursor:
            if dataset_id:
                cursor.execute(f"SELECT {cols} FROM trained_models WHERE user_id = %s AND dataset_id = %s ORDER BY id DESC", (user_id, dataset_id))
            else:
                cursor.execute(f"SELECT {cols} FROM trained_models WHERE user_id = %s ORDER BY id DESC", (user_id,))
            rows = cursor.fetchall()

        results = []
        for r in rows:
            results.append({
                "id": r['id'], "user_id": r['user_id'], "dataset_id": r['dataset_id'],
                "model_name": r['model_name'], "model_type": r['model_type'], "target_column": r['target_column'],
                "feature_columns": _loads(r['feature_columns'], []),
                "metrics": _loads(r['metrics'], {}),
                "coefficients": _loads(r['coefficients'], {}),
                "intercept": float(r['intercept']),
                "formula_str": r['formula_str'],
                "plain_explanations": _loads(r.get('plain_explanations'), {}),
                "trained_at": str(r['trained_at']) if r.get('trained_at') else '',
            })
        return results
    except Exception as e:
        logger.error(f"Error fetching saved models: {e}")
        return []
    finally:
        conn.close()


def predict_with_saved_model(model_id: int, user_id: int, input_features: Dict[str, Any]) -> Dict[str, Any]:
    """
    Instant prediction from a saved linear model. Numeric terms are 'column'; categorical terms are 'column=value'
    (the input supplies the category, the matching term is added). Missing numeric inputs are an ERROR, not a silent 0.
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "message": "Database connection error."}

    try:
        if not ensure_trained_models_table(conn):
            return {"success": False, "message": "Could not initialize trained_models table."}
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, model_name, target_column, feature_columns, metrics, coefficients, intercept, formula_str
                FROM trained_models WHERE id = %s AND user_id = %s
            """, (model_id, user_id))
            row = cursor.fetchone()

        if not row:
            return {"success": False, "message": "Saved model not found or access denied."}

        target_col = row['target_column']
        coefficients = _loads(row['coefficients'], {})
        metrics = _loads(row.get('metrics'), {})
        intercept = float(row['intercept'])
        input_features = input_features or {}

        numeric_terms = {k: v for k, v in coefficients.items() if "=" not in k}
        cat_terms: Dict[str, Dict[str, float]] = {}
        for k, v in coefficients.items():
            if "=" in k:
                col, val = k.split("=", 1)
                cat_terms.setdefault(col, {})[val] = float(v)

        missing = [c for c in list(numeric_terms) + list(cat_terms) if c not in input_features or input_features[c] in (None, "")]
        if missing:
            return {"success": False, "message": f"Missing required input value(s): {', '.join(missing)}."}

        pred_val = intercept
        breakdown = [{"factor": "Baseline Intercept", "value": intercept, "contribution": round(intercept, 2)}]
        for feat, coef in numeric_terms.items():
            try:
                x_val = float(input_features[feat])
            except (TypeError, ValueError):
                return {"success": False, "message": f"Input for '{feat}' must be numeric."}
            if not np.isfinite(x_val):
                return {"success": False, "message": f"Input for '{feat}' must be a finite number."}
            contrib = x_val * float(coef)
            pred_val += contrib
            breakdown.append({"factor": feat, "input_value": x_val, "coefficient": float(coef), "contribution": round(contrib, 2)})

        notes = []
        for col, levels in cat_terms.items():
            chosen = str(input_features[col])
            contrib = levels.get(chosen, 0.0)
            if chosen not in levels:
                notes.append(f"Category '{chosen}' for '{col}' was not seen in training; no category effect applied.")
            pred_val += contrib
            breakdown.append({"factor": f"{col}={chosen}", "input_value": chosen, "coefficient": contrib, "contribution": round(contrib, 2)})

        if metrics.get('clip_non_negative') and pred_val < 0:
            notes.append("Prediction clipped to 0 because the training target was never negative.")
            pred_val = 0.0

        return {
            "success": True, "model_id": model_id, "model_name": row['model_name'], "target_column": target_col,
            "predicted_value": round(float(pred_val), 2), "formula_str": row['formula_str'],
            "breakdown": breakdown, "notes": notes, "input_features": input_features,
        }
    except Exception as e:
        logger.error(f"Error predicting with saved model: {e}")
        return {"success": False, "message": f"Prediction failed: {e}"}
    finally:
        conn.close()


def delete_saved_model(model_id: int, user_id: int) -> Dict[str, Any]:
    """Deletes a saved model."""
    conn = get_db_connection()
    if not conn:
        return {"success": False, "message": "Database error."}

    try:
        if not ensure_trained_models_table(conn):
            return {"success": False, "message": "Could not initialize trained_models table."}
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM trained_models WHERE id = %s AND user_id = %s", (model_id, user_id))
            conn.commit()
            deleted = cursor.rowcount > 0
        if deleted:
            return {"success": True, "message": "Model deleted successfully."}
        return {"success": False, "message": "Model not found or unauthorized."}
    except Exception as e:
        logger.error(f"Error deleting saved model: {e}")
        return {"success": False, "message": f"Failed to delete model: {e}"}
    finally:
        conn.close()


# ==============================================================================
# OFFLINE STATISTICAL REASONING ASSISTANT (all dataset text is HTML-escaped)
# ==============================================================================

def _has(q: str, words: List[str]) -> bool:
    for w in words:
        if len(w) <= 4:
            if re.search(r'(?<![a-z0-9])' + re.escape(w) + r'(?![a-z0-9])', q):
                return True
        elif w in q:
            return True
    return False


def generate_ml_assistant_response(model_data: Dict[str, Any], query: str = "") -> Dict[str, Any]:
    """Plain-language explanations of any model result without external AI APIs."""
    if not model_data:
        return {"success": False, "message": "No active model data provided. Please fit or evaluate a model first."}

    modality = str(model_data.get('model_type', 'regression')).lower().strip()
    target_raw = str(model_data.get('target_column') or 'Target Variable')
    target_col = _esc(target_raw)
    features = [str(f) for f in (model_data.get('features') or [])]
    metrics = model_data.get('metrics') or {}
    coefficients = model_data.get('coefficients') or {}
    importances = model_data.get('feature_importances') or {}
    intercept = float(model_data.get('intercept', 0.0) or 0.0)
    formula_str = model_data.get('formula') or ''
    model_name = str(model_data.get('model_name') or 'Regression Model')
    is_linear = bool(model_data.get('linear_formula_available', bool(coefficients)))
    q = (query or "").lower().strip()

    intent = "general_explain"
    matched_feature = next((f for f in features if len(f) >= 3 and f.lower() in q), None)
    if matched_feature and not _has(q, ['which', 'top', 'highest', 'most']):
        intent = "feature_specific"
    elif _has(q, ['driver', 'feature', 'impact', 'weight', 'influence', 'kiska', 'affect', 'factor', 'highest', 'important', 'sabse']):
        intent = "drivers"
    elif _has(q, ['reliable', 'fit', 'health', 'accuracy', 'error', 'r2', 'rmse', 'mae', 'trust', 'production', 'kaisa', 'unfit', 'good', 'quality']):
        intent = "reliability"
    elif _has(q, ['summary', 'executive', 'stakeholder', 'brief', 'overview', 'report', 'management', 'takeaway', 'overall']):
        intent = "executive_summary"
    elif _has(q, ['improve', 'better', 'reduce error', 'increase accuracy', 'kaise badhaye', 'theek', 'fix', 'optimize', 'tune']):
        intent = "improve_tips"

    # ranking: permutation importance when present (comparable across features), else coefficient magnitude
    ranked_drivers: List[Tuple[str, Optional[float], float]] = []
    if importances:
        tot = sum(float(v) for v in importances.values()) or 1.0
        ranked_drivers = [(k, (float(coefficients[k]) if k in coefficients else None), float(v) / tot * 100)
                          for k, v in sorted(importances.items(), key=lambda kv: kv[1], reverse=True)]
    elif coefficients:
        tot = sum(abs(float(v)) for v in coefficients.values()) or 1.0
        ranked_drivers = [(k, float(v), abs(float(v)) / tot * 100)
                          for k, v in sorted(coefficients.items(), key=lambda kv: abs(float(kv[1])), reverse=True)]

    title = "Model Analysis & Plain Language Interpretation"
    html_parts: List[str] = []
    takeaways: List[str] = []
    followups: List[str] = []

    if modality == 'regression':
        r2 = float(metrics.get('r2_score', 0.0) or 0.0)
        mae = float(metrics.get('mae', 0.0) or 0.0)
        rmse = float(metrics.get('rmse', 0.0) or 0.0)
        base_mae = metrics.get('baseline_mae')
        test_samples = int(metrics.get('test_samples', 0) or 0)
        fit_txt = ("⚠️ Unfit model - it does not beat a simple average" if r2 < 0 else f"Explains {r2 * 100:.1f}% of variance")

        if intent == "drivers":
            title = f"Key Drivers & Predictor Impact on '{target_raw}'"
            if ranked_drivers:
                top_feat, top_coef, top_pct = ranked_drivers[0]
                html_parts.append(f"<p class='mb-2'>The model evaluated <strong>{len(ranked_drivers)} predictor features</strong>. Ranked by how much held-out accuracy depends on them:</p>")
                html_parts.append("<ul class='list-group list-group-flush mb-3 rounded-2 border'>")
                for rank, (feat, coef, pct) in enumerate(ranked_drivers, 1):
                    effect = ""
                    if coef is not None:
                        color = "success" if coef >= 0 else "danger"
                        effect = (f": each 1-unit increase {'raises' if coef >= 0 else 'lowers'} {target_col} by "
                                  f"<span class='badge bg-{color}-subtle text-{color} border'>{'+' if coef >= 0 else '-'}{abs(coef):.2f}</span>")
                    html_parts.append(
                        f"<li class='list-group-item d-flex justify-content-between align-items-center py-2'>"
                        f"<div><strong>#{rank} {_esc(feat)}</strong>{effect}</div>"
                        f"<span class='badge bg-primary-subtle text-primary border font-monospace'>{pct:.1f}% importance share</span></li>")
                html_parts.append("</ul>")
                takeaways = [f"🥇 Top Driver: '{top_feat}' ({top_pct:.1f}% share).",
                             f"To move {target_raw} most effectively, prioritise actions around {top_feat}."]
                if top_coef is not None:
                    takeaways.insert(1, f"Directional Effect: increasing '{top_feat}' {'increases' if top_coef >= 0 else 'decreases'} '{target_raw}'.")
            else:
                html_parts.append("<p>No driver information is available for this model.</p>")

        elif intent == "reliability":
            title = "Reliability & Goodness-of-Fit Health Check"
            if r2 < 0:
                badge = "<span class='badge bg-danger text-white'>🔴 Model Unfit (R² < 0)</span>"
                status_desc = (f"<strong>Warning: weak / unfit model.</strong> On unseen rows it performs worse than simply predicting the average of {target_col}. "
                               f"The selected features do not explain this target, or the target is an identifier rather than a measurable KPI.")
                action_tip = "Use a continuous numeric KPI as target, add informative features, or switch to Classification for discrete targets."
            elif r2 < 0.35:
                badge = "<span class='badge bg-warning text-dark'>🟡 Low Predictive Power</span>"
                status_desc = f"Features account for only <strong>{r2 * 100:.1f}%</strong> of variance in {target_col}. Predictions carry notable error."
                action_tip = "Include additional informative variables to boost explanatory power."
            elif r2 < 0.70:
                badge = "<span class='badge bg-info text-white'>🔵 Moderate Fit</span>"
                status_desc = f"Model captures <strong>{r2 * 100:.1f}%</strong> of target behavior. Suitable for directional business estimates."
                action_tip = "Add or engineer features (ratios, interactions) to reach >70% fit."
            else:
                badge = "<span class='badge bg-success text-white'>🟢 High Production Reliability</span>"
                status_desc = f"Strong fit - predictors explain <strong>{r2 * 100:.1f}%</strong> of the variance in {target_col}."
                action_tip = "Model is well calibrated and suitable for decision support."
            base_line = f" (a mean-only baseline is ±{float(base_mae):,.2f})" if base_mae is not None else ""
            html_parts.append(f"<div class='d-flex align-items-center gap-2 mb-2'>{badge} <span class='small text-muted'>Evaluated on {test_samples:,} unseen records · {_esc(model_name)}</span></div>")
            html_parts.append(f"<p class='mb-2'>{status_desc}</p>")
            html_parts.append(
                f"<div class='p-2 rounded-2 bg-body border mb-3 small'>"
                f"<div><strong>Margin of Error (MAE):</strong> typical deviation ±<strong>{mae:,.2f}</strong> units{base_line}.</div>"
                f"<div><strong>RMSE:</strong> <strong>{rmse:,.2f}</strong> units (penalises large misses).</div></div>")
            takeaways = [f"Goodness of Fit (R²): {r2:.4f} ({fit_txt}).",
                         f"Expected margin of error: ±{mae:,.2f} on unseen rows.", action_tip]

        elif intent == "executive_summary":
            title = f"Executive Brief: Predictive Model for '{target_raw}'"
            top_name = _esc(ranked_drivers[0][0]) if ranked_drivers else "Predictors"
            top_share = f"{ranked_drivers[0][2]:.1f}%" if ranked_drivers else "n/a"
            reliability = ("⚠️ Model unfit - do not use for decisions" if r2 < 0
                           else f"Explains {r2 * 100:.1f}% of target variance with ±{mae:,.2f} average deviation")
            html_parts.append(
                f"<div class='p-3 rounded-3 bg-body border mb-3'>"
                f"<h6 class='fw-bold text-primary mb-2'>Executive Takeaways for Leadership</h6>"
                f"<p class='small mb-2'>• <strong>Goal:</strong> forecast <em>{target_col}</em> from {len(features)} observed variables using <em>{_esc(model_name)}</em>.</p>"
                f"<p class='small mb-2'>• <strong>Reliability:</strong> {reliability}.</p>"
                f"<p class='small mb-0'>• <strong>Primary lever:</strong> <em>{top_name}</em> carries {top_share} of the model's predictive reliance.</p></div>")
            takeaways = [f"Executive confidence: {'unfit for decision-making' if r2 < 0 else f'approved for decision support ({r2 * 100:.1f}% R²)'}.",
                         f"Primary business lever: '{ranked_drivers[0][0]}'." if ranked_drivers else "No dominant lever identified.",
                         f"Validated on {test_samples:,} independent hold-out cases."]

        elif intent == "improve_tips":
            title = "Actionable Recommendations to Improve Model Accuracy"
            html_parts.append(
                "<p class='mb-2'>To boost predictive accuracy, consider:</p>"
                "<ol class='small text-body mb-3 ps-3 d-flex flex-column gap-2'>"
                "<li><strong>Use a continuous KPI target.</strong> IDs, postal codes and binary flags make regression meaningless.</li>"
                "<li><strong>Add informative features.</strong> Category, region, discount, quantity and date-derived fields often carry most of the signal.</li>"
                "<li><strong>Handle outliers.</strong> Check the Anomaly tab; extreme rows distort linear fits.</li>"
                "<li><strong>Prefer more data.</strong> 500+ clean rows give far more stable validation.</li>"
                "<li><strong>Skewed targets</strong> (sales, revenue) are automatically tested on a log scale.</li></ol>")
            takeaways = ["Keep targets continuous (Revenue, Profit, Sales, Cost).",
                         "Remove identifiers and constant columns from features.",
                         "Aim for R² >= 0.70 and an MAE clearly below the mean baseline."]

        elif intent == "feature_specific":
            feat = matched_feature or (features[0] if features else "Feature")
            title = f"Feature Impact Deep-Dive: '{feat}'"
            coef = coefficients.get(feat)
            share = next((p for f_, _, p in ranked_drivers if f_ == feat), None)
            body = f"<h6 class='fw-bold mb-2'>Impact Analysis for <span class='text-primary'>{_esc(feat)}</span></h6>"
            if coef is not None:
                coef = float(coef)
                word = "increases" if coef >= 0 else "decreases"
                body += (f"<p class='small mb-2'>• <strong>Slope (β):</strong> <code>{coef:+.4f}</code></p>"
                         f"<p class='small mb-2'>• Every 1 unit change in <em>{_esc(feat)}</em> {word} <em>{target_col}</em> by <strong>{abs(coef):,.2f}</strong> units (other features held constant).</p>"
                         f"<p class='small mb-0'>• A 10-unit increase shifts expected {target_col} by <strong>{coef * 10:+,.2f}</strong>.</p>")
                takeaways = [f"Coefficient (β) for {feat}: {coef:+.4f}", f"10-unit increase → {coef * 10:+,.2f} change in {target_raw}."]
            else:
                body += (f"<p class='small mb-0'>The active model ({_esc(model_name)}) is non-linear, so there is no single slope. "
                         f"This feature accounts for <strong>{(share or 0):.1f}%</strong> of the model's predictive reliance.</p>")
                takeaways = [f"{feat} carries {(share or 0):.1f}% of the model's importance."]
            html_parts.append(f"<div class='p-3 rounded-3 bg-body border mb-3'>{body}</div>")

        else:
            title = "Simple Plain-Language Explanation of Model & Predictions"
            feat_list = _esc(", ".join(features))
            html_parts.append(f"<p class='mb-2'>The active model is <strong>{_esc(model_name)}</strong>, predicting <strong>{target_col}</strong> from {len(features)} features ({feat_list}).</p>")
            if is_linear:
                html_parts.append(
                    f"<div class='p-2 rounded-2 bg-body border mb-3 small'><div class='fw-bold mb-1 text-primary'>Mathematical Formula:</div>"
                    f"<div class='font-monospace text-body mb-2'>{_esc(formula_str or f'{target_raw} = {intercept:.2f} + ...')}</div>"
                    f"<div>It starts at a baseline of <strong>{intercept:,.2f}</strong> and adds or subtracts each feature's contribution.</div></div>")
            else:
                html_parts.append("<div class='p-2 rounded-2 bg-body border mb-3 small'>This is a non-linear ensemble model: it learns patterns from many decision trees, so there is no single formula. Use the importance chart to see what drives predictions.</div>")
            html_parts.append(f"<p class='small mb-2 text-body'>• <strong>Model Fit:</strong> R² = <strong>{r2:.4f}</strong> ({_esc(fit_txt)}).</p>")
            html_parts.append(f"<p class='small mb-0 text-body'>• <strong>Prediction Accuracy:</strong> on unseen data, predictions are typically within ±<strong>{mae:,.2f}</strong> of actual outcomes.</p>")
            top_name = ranked_drivers[0][0] if ranked_drivers else "features"
            takeaways = [f"Strongest feature: '{top_name}'.", f"Typical margin of error: ±{mae:,.2f}."]
            if is_linear:
                takeaways.insert(0, f"Baseline intercept is {intercept:,.2f} when all features are zero.")

        followups = ["Which feature has the highest impact?", "Is this model reliable or fit?",
                     "Give me an executive summary for stakeholders", "How can I improve model accuracy?"]

    elif modality == 'classification':
        acc = float(metrics.get('accuracy', 0.0) or 0.0)
        f1 = float(metrics.get('f1_score', 0.0) or 0.0)
        prec = float(metrics.get('precision', 0.0) or 0.0)
        rec = float(metrics.get('recall', 0.0) or 0.0)
        maj = metrics.get('majority_class_baseline_accuracy')
        tot_records = int(metrics.get('total_records', 0) or 0)
        title = f"Classification Model Insights: '{target_raw}'"
        html_parts.append(f"<p class='mb-2'>This model categorises records into classes of <strong>{target_col}</strong> with overall accuracy <strong>{acc:.1f}%</strong>"
                          f"{f' (always guessing the biggest class gives {float(maj):.1f}%)' if maj is not None else ''}.</p>")
        html_parts.append(
            "<div class='row g-2 mb-3'>"
            f"<div class='col-6 col-md-3'><div class='p-2 rounded border bg-body text-center'><div class='small text-muted'>Accuracy</div><div class='fw-bold text-success fs-6'>{acc:.1f}%</div></div></div>"
            f"<div class='col-6 col-md-3'><div class='p-2 rounded border bg-body text-center'><div class='small text-muted'>F1-Score</div><div class='fw-bold text-primary fs-6'>{f1:.1f}%</div></div></div>"
            f"<div class='col-6 col-md-3'><div class='p-2 rounded border bg-body text-center'><div class='small text-muted'>Precision</div><div class='fw-bold text-info fs-6'>{prec:.1f}%</div></div></div>"
            f"<div class='col-6 col-md-3'><div class='p-2 rounded border bg-body text-center'><div class='small text-muted'>Recall</div><div class='fw-bold text-warning fs-6'>{rec:.1f}%</div></div></div></div>")
        takeaways = [f"Classification accuracy: {acc:.1f}% correct predictions.", f"Balanced F1-Score: {f1:.1f}%.",
                     f"Evaluated on {tot_records:,} dataset records."]
        followups = ["Explain Confusion Matrix in simple terms", "What is the difference between Precision and Recall?",
                     "How can I improve classification accuracy?"]

    elif modality == 'clustering':
        sil = float(metrics.get('silhouette_score', 0.0) or 0.0)
        n_c = int(metrics.get('n_clusters', model_data.get('n_clusters', 3)) or 3)
        sug = metrics.get('suggested_k')
        quality = str(metrics.get('quality_rating', 'Moderate Grouping'))
        tot_s = int(metrics.get('total_samples', 0) or 0)
        title = f"Customer & Entity Clustering Analysis ({n_c} Clusters)"
        html_parts.append(f"<p class='mb-2'>The algorithm partitioned <strong>{tot_s:,} records</strong> into <strong>{n_c} cohorts</strong> using multi-dimensional distance.</p>")
        sug_txt = f"<div class='mt-1'>Best silhouette in the tested range is at <strong>k = {int(sug)}</strong>.</div>" if sug else ""
        html_parts.append(
            f"<div class='p-2 rounded-2 bg-body border mb-3 small'><div><strong>Silhouette separation:</strong> <span class='badge bg-primary-subtle text-primary border'>{sil:.3f} ({_esc(quality)})</span></div>"
            f"<div class='text-muted mt-1'>Ranges from -1 to +1; higher means cleaner boundaries.</div>{sug_txt}</div>")
        takeaways = [f"Formed {n_c} cohorts.", f"Silhouette Score: {sil:.3f} ({quality}).",
                     "Use segment labels for tailored marketing or pricing strategies."]
        followups = ["What are the characteristics of each cluster?", "How does Silhouette score evaluate cluster quality?",
                     "Should I increase or decrease the number of clusters?"]

    elif modality == 'forecasting':
        avg_proj = float(metrics.get('avg_projected_value', 0.0) or 0.0)
        growth = float(metrics.get('growth_trend_pct', 0.0) or 0.0)
        val_rmse = float(metrics.get('validation_rmse', 0.0) or 0.0)
        horizon = int(metrics.get('forecast_periods', 14) or 14)
        method = _esc(model_data.get('selected_method', 'auto'))
        direction_badge = "success" if growth >= 0 else "danger"
        direction_text = "Upward Expansion" if growth >= 0 else "Downward Contraction"
        title = f"Time-Series Forecasting Horizon ({horizon} Periods Ahead)"
        html_parts.append(f"<p class='mb-2'>Projected <strong>{_esc(model_data.get('value_column', 'Value'))}</strong> shows a <strong>{direction_text}</strong> of "
                          f"<span class='badge bg-{direction_badge}-subtle text-{direction_badge} border'>{growth:+.1f}%</span> over the next {horizon} periods (method: {method}).</p>")
        html_parts.append(
            f"<div class='p-2 rounded-2 bg-body border mb-3 small'><div><strong>Projected average:</strong> {avg_proj:,.2f}</div>"
            f"<div><strong>Backtest error (RMSE):</strong> {val_rmse:,.2f}</div>"
            f"<div class='text-muted mt-1'>The 95% band is built from real backtest errors and widens further into the future.</div></div>")
        takeaways = [f"Forecast trend: {growth:+.1f}% ({direction_text}).", f"Projected mean: {avg_proj:,.2f} across {horizon} future steps.",
                     f"Backtest RMSE: ±{val_rmse:,.2f}."]
        followups = ["Explain the 95% Confidence Band in simple terms", "Is the future trend positive or negative?",
                     "What factors influence this forecast?"]

    else:
        anom_count = int(metrics.get('anomalies_detected', 0) or 0)
        anom_rate = float(metrics.get('anomaly_rate_pct', 0.0) or 0.0)
        contam = _esc(metrics.get('contamination_parameter', '5%'))
        title = "Anomaly Detection & Outlier Risk Report"
        html_parts.append(f"<p class='mb-2'>Isolation Forest flagged <strong>{anom_count} multivariate outliers</strong> ({anom_rate:.1f}% of evaluated data).</p>")
        html_parts.append(
            f"<div class='p-2 rounded-2 bg-body border mb-3 small'><div><strong>Detected outliers:</strong> <span class='badge bg-danger-subtle text-danger border'>{anom_count} records</span></div>"
            f"<div><strong>Configured sensitivity:</strong> {contam} contamination rate.</div>"
            f"<div class='text-muted mt-1'>Red diamonds deviate strongly from typical behaviour; each row names its main driver feature.</div></div>")
        takeaways = [f"Identified {anom_count} anomaly records ({anom_rate:.1f}% rate).",
                     "Outliers may be operational risks, data-entry errors, or rare genuine events.",
                     "Review the sample table for scores, severity and primary drivers."]
        followups = ["Why were these records flagged as anomalies?", "How does Isolation Forest detect outliers?",
                     "What actions should be taken on high-severity anomalies?"]

    return {
        "success": True,
        "query": query,
        "intent": intent,
        "title": title,
        "html_content": "".join(html_parts),
        "key_takeaways": takeaways,
        "suggested_questions": followups,
    }