import pandas as pd
import numpy as np
import logging

try:
    from scipy import stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

logger = logging.getLogger(__name__)


def numeric_statistics(series):
    """
    Computes comprehensive descriptive statistics including Mean, Median, Std, Variance, CV, Range, MAD, Skewness, and Kurtosis.
    """
    series = series.dropna()

    if series.empty:
        return {}

    numeric_series = pd.to_numeric(series, errors="coerce").dropna()
    if numeric_series.empty:
        return {}

    mean_val = float(numeric_series.mean())
    std_val = float(numeric_series.std()) if len(numeric_series) > 1 else 0.0
    var_val = float(numeric_series.var()) if len(numeric_series) > 1 else 0.0
    min_val = float(numeric_series.min())
    max_val = float(numeric_series.max())
    median_val = float(numeric_series.median())

    # Coefficient of Variation (CV) & Mean Absolute Deviation (MAD)
    cv_val = round((std_val / abs(mean_val)) * 100, 2) if mean_val != 0 else 0.0
    mad_val = round(float((numeric_series - mean_val).abs().mean()), 4)
    val_range = round(max_val - min_val, 4)

    unique_cnt = int(numeric_series.nunique())
    total_cnt = int(len(numeric_series))
    unique_ratio = round(unique_cnt / max(total_cnt, 1), 4)

    return {
        "count": total_cnt,
        "unique_count": unique_cnt,
        "unique_ratio": unique_ratio,
        "mean": round(mean_val, 4),
        "median": round(median_val, 4),
        "std": round(std_val, 4),
        "variance": round(var_val, 4),
        "cv": cv_val,
        "mad": mad_val,
        "min": round(min_val, 4),
        "max": round(max_val, 4),
        "range": val_range,
        "skewness": round(float(numeric_series.skew()), 4) if len(numeric_series) > 2 else 0.0,
        "kurtosis": round(float(numeric_series.kurt()), 4) if len(numeric_series) > 3 else 0.0
    }


def dataset_numeric_summary(df, semantic_types):
    """
    Generates numeric statistics for all measure, currency, and percentage columns.
    """
    summary = {}
    valid_types = ["measure", "currency", "percentage"]
    for column, sem_type in semantic_types.items():
        if sem_type in valid_types and column in df.columns:
            stats_res = numeric_statistics(df[column])
            if stats_res:
                summary[column] = stats_res
    return summary


def calculate_correlation(df, semantic_types=None, method="pearson"):
    """
    Calculates correlation matrix strictly for numeric columns (measures, currency, percentage, or auto-detected numeric).
    Computes p-values for statistical significance and extracts top correlated pairs.
    """
    if df is None or df.empty:
        return None

    if semantic_types is None:
        semantic_types = {}

    valid_types = ["measure", "currency", "percentage", "numeric", "number", "integer", "float"]
    valid_columns = [
        col for col, sem_type in semantic_types.items()
        if sem_type in valid_types and col in df.columns
    ]

    # If semantic_types didn't identify enough columns, fallback to all numeric convertible columns in df
    if len(valid_columns) < 2:
        for col in df.columns:
            if col not in valid_columns:
                try:
                    converted = pd.to_numeric(df[col], errors="coerce")
                    if converted.notna().sum() >= 2:
                        valid_columns.append(col)
                except Exception:
                    pass

    if len(valid_columns) < 2:
        return None

    numeric_df = df[valid_columns].apply(pd.to_numeric, errors="coerce")

    # Filter out columns with zero variance / all NaN / constant
    non_constant_cols = [
        col for col in numeric_df.columns
        if numeric_df[col].dropna().nunique() > 1
    ]

    if len(non_constant_cols) < 2:
        logger.debug("Not enough variable numeric columns for correlation analysis.")
        return None

    # Calculate pairwise correlation matrix using min_periods=2 so scattered missing values don't wipe out everything
    corr_df = numeric_df[non_constant_cols].corr(method=method, min_periods=2).round(4)
    # Fill any remaining NaNs in correlation matrix with 0.0
    corr_df = corr_df.fillna(0.0)

    p_matrix = pd.DataFrame(index=non_constant_cols, columns=non_constant_cols, dtype=object)
    top_pairs = []

    cols = list(non_constant_cols)
    for i in range(len(cols)):
        for j in range(len(cols)):
            col1, col2 = cols[i], cols[j]
            if i == j:
                p_matrix.loc[col1, col2] = 0.0  # Correlation with itself is 1, p-value is 0
            else:
                pair_data = numeric_df[[col1, col2]].dropna()
                if len(pair_data) < 3 or pair_data[col1].std() == 0 or pair_data[col2].std() == 0:
                    r_val = corr_df.loc[col1, col2]
                    p_val = 1.0  # Not significant if constant or too few points
                else:
                    try:
                        if HAS_SCIPY:
                            if method == "spearman":
                                r_val, p_val = stats.spearmanr(pair_data[col1], pair_data[col2])
                            elif method == "kendall":
                                r_val, p_val = stats.kendalltau(pair_data[col1], pair_data[col2])
                            else:
                                r_val, p_val = stats.pearsonr(pair_data[col1], pair_data[col2])
                        else:
                            r_val, p_val = corr_df.loc[col1, col2], None  # Truthful None when SciPy is unavailable
                        
                        p_matrix.loc[col1, col2] = round(float(p_val), 5) if p_val is not None else "N/A"

                        if i < j:  # Only add each pair once
                            r_val = float(r_val) if not pd.isna(r_val) else 0.0
                            # Define relationship strength based on absolute correlation value
                            if r_val > 0.6:
                                rel_type = "Strong Positive"
                            elif r_val > 0.3:
                                rel_type = "Moderate Positive"
                            elif r_val < -0.6:
                                rel_type = "Strong Negative"
                            elif r_val < -0.3:
                                rel_type = "Moderate Negative"
                            else:
                                rel_type = "Weak"

                            if p_val is None:
                                sig = "N/A (SciPy Required)"
                            else:
                                sig = "Statistically Significant" if (p_val is not None and p_val < 0.05) else "Not Significant"

                            top_pairs.append({
                                "col1": col1,
                                "col2": col2,
                                "correlation": round(r_val, 4),
                                "p_value": round(float(p_val), 5) if p_val is not None else None,
                                "relationship": rel_type,
                                "significance": sig
                            })
                    except Exception as e:
                        logger.warning(f"Error calculating correlation for {col1} and {col2}: {e}")
                        p_matrix.loc[col1, col2] = 1.0  # Default to not significant on error

    top_pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)

    return {
        "matrix": corr_df.to_dict(),
        "p_values": p_matrix.to_dict(),
        "top_pairs": top_pairs[:10]
    }


def distribution_analysis(series):
    """
    Detects distribution shape, skewness, and normality for a numeric series.
    """
    series = pd.to_numeric(series, errors="coerce").dropna()
    if len(series) < 5:
        return {
            "distribution_type": "Insufficient Data",
            "is_normal": False,
            "skewness_type": "Unknown"
        }

    skewness = float(series.skew())
    kurtosis = float(series.kurt())

    # Shapiro-Wilk test for normality (sampled if large).
    is_normal = None
    if HAS_SCIPY:
        sample_for_norm = series.sample(min(len(series), 500), random_state=42)
        try:
            _, p_val = stats.shapiro(sample_for_norm)
            is_normal = bool(p_val > 0.05)
        except Exception as e:
            logger.warning(f"Shapiro test failed: {e}")
            is_normal = None

    if is_normal is None:
        is_normal = abs(skewness) < 0.5 and abs(kurtosis) < 1.0

    if is_normal:
        dist_type = "Normal (Gaussian)"
    elif skewness > 1.0:
        dist_type = "Highly Right-Skewed (Positive)"
    elif skewness > 0.5:
        dist_type = "Moderately Right-Skewed"
    elif skewness < -1.0:
        dist_type = "Highly Left-Skewed (Negative)"
    elif skewness < -0.5:
        dist_type = "Moderately Left-Skewed"
    else:
        dist_type = "Symmetric Non-Normal"

    return {
        "distribution_type": dist_type,
        "is_normal": is_normal,
        "skewness": round(skewness, 4),
        "kurtosis": round(kurtosis, 4)
    }


def category_analysis(df, semantic_types):
    """
    Performs Pareto and frequency analysis on categorical columns.
    """
    results = {}
    cat_cols = [c for c, t in semantic_types.items() if t in ["categorical", "text"] and c in df.columns]

    for col in cat_cols:
        series = df[col].dropna().astype(str)
        if series.empty:
            continue

        counts = series.value_counts()
        total = len(series)
        unique_cnt = len(counts)

        cardinality = "Low Cardinality" if unique_cnt <= 10 else ("Medium Cardinality" if unique_cnt <= 50 else "High Cardinality")

        top_10 = [{"category": k, "count": int(v), "percentage": round((v / total) * 100, 2)} for k, v in counts.head(10).items()]
        bottom_10 = [{"category": k, "count": int(v), "percentage": round((v / total) * 100, 2)} for k, v in counts.tail(10).items()]

        # Pareto 80/20 driver calculation
        cumulative_pct = (counts.cumsum() / total) * 100
        drivers_for_80 = int((cumulative_pct < 80).sum()) + 1
        pareto_pct = round((drivers_for_80 / unique_cnt) * 100, 2) if unique_cnt > 0 else 0.0

        results[col] = {
            "cardinality": cardinality,
            "unique_categories": unique_cnt,
            "top_categories": top_10,
            "bottom_categories": bottom_10,
            "pareto_drivers_80_pct": drivers_for_80,
            "pareto_ratio": pareto_pct
        }

    return results


def dataset_memory_summary(df):
    """
    Calculates detailed memory usage and datatype breakdown for a dataset.
    """
    memory_bytes = int(df.memory_usage(deep=True).sum())

    if memory_bytes < 1024 * 1024:
        formatted_memory = f"{round(memory_bytes / 1024, 2)} KB"
    else:
        formatted_memory = f"{round(memory_bytes / (1024 * 1024), 2)} MB"

    dtype_counts = {}
    for col, dtype in df.dtypes.items():
        dt_str = str(dtype)
        if "int" in dt_str:
            dtype_counts["Integer"] = dtype_counts.get("Integer", 0) + 1
        elif "float" in dt_str:
            dtype_counts["Float"] = dtype_counts.get("Float", 0) + 1
        elif "datetime" in dt_str:
            dtype_counts["Datetime"] = dtype_counts.get("Datetime", 0) + 1
        elif "bool" in dt_str:
            dtype_counts["Boolean"] = dtype_counts.get("Boolean", 0) + 1
        else:
            dtype_counts["Object/Text"] = dtype_counts.get("Object/Text", 0) + 1

    return {
        "memory_bytes": memory_bytes,
        "formatted_memory": formatted_memory,
        "datatype_breakdown": dtype_counts,
        "total_cells": int(df.shape[0] * df.shape[1])
    }