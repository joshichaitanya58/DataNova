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
        threshold (float): Z-score threshold (default: 3.0)

    Returns:
        dict: Contains count, percentage, threshold, and indices of outliers
    """
    series = series.dropna()
    if len(series) < 4:
        return {"count": 0, "percentage": 0.0, "indices": []}

    mean = series.mean()
    std = series.std()

    if std == 0:
        return {"count": 0, "percentage": 0.0, "indices": []}

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


def detect_outliers_isolation_forest(df, measure_columns):
    """
    Multivariate outlier detection using Isolation Forest (ML model).

    Args:
        df (pd.DataFrame): Input dataframe
        measure_columns (list): List of numeric column names to use

    Returns:
        dict: Contains count, percentage, and indices of outliers
    """
    if not HAS_SKLEARN or len(measure_columns) == 0 or len(df) < 10:
        logger.debug("Isolation Forest not available or insufficient data.")
        return {"count": 0, "percentage": 0.0, "indices": []}

    # Subset to measure columns and convert to numeric
    sub_df = df[measure_columns].apply(pd.to_numeric, errors="coerce")

    # Remove columns with zero variance (constant values)
    constant_cols = [col for col in sub_df.columns if sub_df[col].dropna().nunique() <= 1]
    if constant_cols:
        sub_df = sub_df.drop(columns=constant_cols)
        logger.debug(f"Dropped constant columns for Isolation Forest: {constant_cols}")

    # Drop rows with any NaN
    sub_df = sub_df.dropna()

    if len(sub_df) < 10:
        logger.debug("Not enough data points after cleaning for Isolation Forest.")
        return {"count": 0, "percentage": 0.0, "indices": []}

    try:
        clf = IsolationForest(contamination=0.05, random_state=42)
        preds = clf.fit_predict(sub_df)
        anomalies_mask = preds == -1
        anom_count = int(anomalies_mask.sum())
        anom_pct = round((anom_count / len(sub_df)) * 100.0, 2)
        anom_indices = sub_df[anomalies_mask].index.tolist()

        return {
            "count": anom_count,
            "percentage": anom_pct,
            "indices": anom_indices
        }
    except Exception as e:
        logger.warning(f"Isolation Forest error: {e}")
        return {"count": 0, "percentage": 0.0, "indices": []}


def detect_dataset_outliers(df, semantic_types):
    """
    Performs multi-method outlier detection (IQR, Z-Score, Isolation Forest)
    strictly on measure/currency columns.

    Args:
        df (pd.DataFrame): Input dataset
        semantic_types (dict): Column semantic type mapping

    Returns:
        dict: Outlier report with per-column results, multivariate results, and total count
    """
    valid_types = ["measure", "currency", "percentage"]
    measure_cols = [
        column for column, sem_type in semantic_types.items()
        if sem_type in valid_types and column in df.columns
    ]

    outliers_report = {
        "by_column": {},
        "multivariate_isolation_forest": None,
        "total_outlier_count": 0
    }

    all_outlier_indices = set()

    for column in measure_cols:
        series = pd.to_numeric(df[column], errors="coerce")
        iqr_res = detect_outliers_iqr(series)
        z_res = detect_outliers_zscore(series)

        column_outliers = set(iqr_res["indices"]).union(set(z_res["indices"]))
        all_outlier_indices.update(column_outliers)

        outliers_report["by_column"][column] = {
            "iqr": iqr_res,
            "zscore": z_res,
            "combined_count": len(column_outliers)
        }

    # Run Isolation Forest if measure columns present
    iso_res = None
    if measure_cols:
        iso_res = detect_outliers_isolation_forest(df, measure_cols)
        outliers_report["multivariate_isolation_forest"] = iso_res
        if iso_res and iso_res.get("indices"):
            all_outlier_indices.update(set(iso_res["indices"]))

    outliers_report["total_outlier_count"] = len(all_outlier_indices)
    return outliers_report