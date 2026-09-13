import pandas as pd
import numpy as np
import importlib
import logging

try:
    _sklearn_ensemble = importlib.import_module("sklearn.ensemble")
    IsolationForest = getattr(_sklearn_ensemble, "IsolationForest")
    HAS_SKLEARN = True
except (ImportError, ModuleNotFoundError, AttributeError):
    IsolationForest = None
    HAS_SKLEARN = False

logger = logging.getLogger(__name__)


def detect_outliers_iqr(series):
    """
    Detects numerical outliers using the Interquartile Range (IQR) method.

    Args:
        series (pd.Series): Numeric series to analyze

    Returns:
        dict: Contains count, percentage, lower_bound, upper_bound, and indices of outliers
    """
    series = series.dropna()

    if len(series) < 4:
        return {
            "count": 0,
            "percentage": 0.0,
            "lower_bound": None,
            "upper_bound": None,
            "indices": []
        }

    q1 = float(series.quantile(0.25))
    q3 = float(series.quantile(0.75))
    iqr = q3 - q1

    lower_bound = q1 - (1.5 * iqr)
    upper_bound = q3 + (1.5 * iqr)

    outliers_mask = (series < lower_bound) | (series > upper_bound)
    outlier_count = int(outliers_mask.sum())
    outlier_percentage = round((outlier_count / len(series)) * 100.0, 2)
    outlier_indices = series[outliers_mask].index.tolist()

    return {
        "count": outlier_count,
        "percentage": outlier_percentage,
        "lower_bound": round(lower_bound, 4),
        "upper_bound": round(upper_bound, 4),
        "indices": outlier_indices
    }


def detect_outliers_zscore(series, threshold=3.0):
    """
    Detects numerical outliers using standard Z-score (|Z| > threshold).

    Args:
        series (pd.Series): Numeric series to analyze
        threshold (float): Z-score threshold (must be positive, default: 3.0)

    Returns:
        dict: Contains count, percentage, threshold, and indices of outliers
    """
    if not isinstance(threshold, (int, float)) or threshold <= 0:
        raise ValueError("Z-score threshold must be a positive number.")

    series = series.dropna()
    if len(series) < 4:
        return {"count": 0, "percentage": 0.0, "threshold": threshold, "indices": []}

    mean = series.mean()
    std = series.std()

    if std == 0:
        return {"count": 0, "percentage": 0.0, "threshold": threshold, "indices": []}

    z_scores = np.abs((series - mean) / std)
    outliers_mask = z_scores > threshold
    outlier_count = int(outliers_mask.sum())
    outlier_percentage = round((outlier_count / len(series)) * 100.0, 2)
    outlier_indices = series[outliers_mask].index.tolist()

    return {
        "count": outlier_count,
        "percentage": outlier_percentage,
        "threshold": threshold,
        "indices": outlier_indices
    }


def detect_outliers_isolation_forest(df, measure_columns, contamination=0.05):
    """
    Multivariate outlier detection using Isolation Forest (ML model).

    Args:
        df (pd.DataFrame): Input dataframe
        measure_columns (list): List of numeric column names to use
        contamination (float or str): Expected proportion of outliers (default: 0.05 or 'auto')

    Returns:
        dict: Contains count, percentage, analyzed_rows, and indices of outliers
    """
    if not HAS_SKLEARN or len(measure_columns) == 0 or len(df) < 10:
        logger.debug("Isolation Forest not available or insufficient data.")
        return {"count": 0, "percentage": 0.0, "original_rows": len(df), "analyzed_rows": 0, "indices": []}

    # Subset to measure columns and convert to numeric
    sub_df = df[measure_columns].apply(pd.to_numeric, errors="coerce")

    # Remove columns with zero variance (constant values)
    constant_cols = [col for col in sub_df.columns if sub_df[col].dropna().nunique() <= 1]
    if constant_cols:
        sub_df = sub_df.drop(columns=constant_cols)
        logger.debug(f"Dropped constant columns for Isolation Forest: {constant_cols}")

    original_rows = len(df)
    sub_df = sub_df.dropna()
    analyzed_rows = len(sub_df)

    if analyzed_rows < 10:
        logger.debug("Not enough data points after cleaning for Isolation Forest.")
        return {"count": 0, "percentage": 0.0, "original_rows": original_rows, "analyzed_rows": analyzed_rows, "indices": []}

    try:
        cont_val = contamination if (isinstance(contamination, float) and 0.0 < contamination <= 0.5) or contamination == 'auto' else 0.05
        clf = IsolationForest(contamination=cont_val, random_state=42)
        preds = clf.fit_predict(sub_df)
        anomalies_mask = preds == -1
        anom_count = int(anomalies_mask.sum())
        anom_pct = round((anom_count / analyzed_rows) * 100.0, 2)
        anom_indices = sub_df[anomalies_mask].index.tolist()

        return {
            "count": anom_count,
            "percentage": anom_pct,
            "original_rows": original_rows,
            "analyzed_rows": analyzed_rows,
            "contamination": cont_val,
            "indices": anom_indices
        }
    except Exception as e:
        logger.exception(f"Isolation Forest error: {e}")
        return {"count": 0, "percentage": 0.0, "original_rows": original_rows, "analyzed_rows": analyzed_rows, "indices": []}


def detect_dataset_outliers(df, semantic_types, contamination=0.05):
    """
    Performs multi-method outlier detection (IQR, Z-Score, Isolation Forest)
    strictly on measure/currency columns with method attribution and multi-method consensus.

    Args:
        df (pd.DataFrame): Input dataset
        semantic_types (dict): Column semantic type mapping
        contamination (float): Isolation Forest contamination parameter (default: 0.05)

    Returns:
        dict: Detailed outlier report with per-column results, method breakdown, and consensus counts.
    """
    valid_types = ["measure", "currency", "percentage"]
    measure_cols = [
        column for column, sem_type in semantic_types.items()
        if sem_type in valid_types and column in df.columns
    ]

    outliers_report = {
        "by_column": {},
        "multivariate_isolation_forest": None,
        "summary": {
            "total_unique_outliers": 0,
            "iqr_flagged_count": 0,
            "zscore_flagged_count": 0,
            "isolation_forest_flagged_count": 0,
            "consensus_count": 0,
            "consensus_rate_pct": 0.0
        },
        "total_outlier_count": 0
    }

    method_tracker = {}  # idx -> set of method names
    iqr_all_indices = set()
    zscore_all_indices = set()

    for column in measure_cols:
        series = pd.to_numeric(df[column], errors="coerce")
        iqr_res = detect_outliers_iqr(series)
        z_res = detect_outliers_zscore(series)

        iqr_idx = set(iqr_res.get("indices", []))
        zscore_idx = set(z_res.get("indices", []))

        iqr_all_indices.update(iqr_idx)
        zscore_all_indices.update(zscore_idx)

        for idx in iqr_idx:
            method_tracker.setdefault(idx, set()).add("IQR")
        for idx in zscore_idx:
            method_tracker.setdefault(idx, set()).add("Z-Score")

        column_outliers = iqr_idx.union(zscore_idx)

        outliers_report["by_column"][column] = {
            "iqr": iqr_res,
            "zscore": z_res,
            "combined_count": len(column_outliers)
        }

    # Run Isolation Forest if measure columns present
    iso_indices = set()
    if measure_cols:
        iso_res = detect_outliers_isolation_forest(df, measure_cols, contamination=contamination)
        outliers_report["multivariate_isolation_forest"] = iso_res
        if iso_res and iso_res.get("indices"):
            iso_indices = set(iso_res["indices"])
            for idx in iso_indices:
                method_tracker.setdefault(idx, set()).add("Isolation Forest")

    total_unique = len(method_tracker)
    consensus_indices = [idx for idx, methods in method_tracker.items() if len(methods) >= 2]
    consensus_cnt = len(consensus_indices)
    consensus_pct = round((consensus_cnt / max(1, total_unique)) * 100.0, 1) if total_unique > 0 else 0.0

    outliers_report["summary"] = {
        "total_unique_outliers": total_unique,
        "iqr_flagged_count": len(iqr_all_indices),
        "zscore_flagged_count": len(zscore_all_indices),
        "isolation_forest_flagged_count": len(iso_indices),
        "consensus_count": consensus_cnt,
        "consensus_rate_pct": consensus_pct
    }
    outliers_report["total_outlier_count"] = total_unique

    return outliers_report