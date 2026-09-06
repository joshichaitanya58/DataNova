import numpy as np
import pandas as pd

MISSING_TOKENS = [
    "", " ", "NA", "N/A", "na", "n/a", "null", "NULL",
    "None", "none", "?", "-", "--", "nan", "NaN", "NAN",
    "nil", "NIL", "<NA>", "undefined", "n.a.", "N.A."
]


def normalize_missing_values(df):
    """
    Normalizes dirty/string missing values into standard numpy NaN.
    Also handles infinity values.
    """
    df = df.copy()

    # Replace string missing tokens across all columns
    df.replace(MISSING_TOKENS, np.nan, inplace=True)

    # Handle infinite numeric values
    df.replace([np.inf, -np.inf], np.nan, inplace=True)

    return df


def convert_currency(series):
    """
    Converts currency strings like '₹1,200', '$500.50' into float.
    """
    if pd.api.types.is_numeric_dtype(series):
        return series

    cleaned = (
        series.astype(str)
        .str.replace("₹", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("€", "", regex=False)
        .str.replace("£", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def convert_percentage(series):
    """
    Converts percentage strings (e.g., '15.5%') or scaled numbers into float fractions (0.155).
    Unambiguously handles string vs decimal representation (DN-DATA-002).
    """
    if pd.api.types.is_numeric_dtype(series):
        series_float = series.astype(float)
        non_null = series_float.dropna()
        if not non_null.empty and non_null.abs().max() > 1.0:
            return series_float / 100.0
        return series_float

    str_s = series.astype(str)
    has_percent = str_s.str.contains("%", regex=False, na=False)

    cleaned = (
        str_s
        .str.replace("%", "", regex=False)
        .str.strip()
    )
    numeric = pd.to_numeric(cleaned, errors="coerce").astype(float)

    mask_scale = has_percent | (numeric.abs() > 1.0)
    scaled = numeric / 100.0
    return pd.Series(np.where(mask_scale, scaled, numeric), index=series.index, dtype=float)


def convert_datetime(series):
    """
    Parses datetime series with fallback coercions.
    """
    try:
        return pd.to_datetime(series, errors="coerce", format="mixed")
    except Exception:
        return pd.to_datetime(series, errors="coerce")


def auto_convert_dtypes(df, semantic_types):
    """
    Scans object/string columns for currency, percentage, and datetime patterns,
    converting them to proper numeric or datetime types.
    """
    df = df.copy()

    for col in df.columns:
        sem_type = semantic_types.get(col, "unknown")

        if df[col].dtype == "object" or str(df[col].dtype).startswith("string"):
            sample = df[col].dropna().astype(str).head(50)
            if sample.empty:
                continue

            # Check currency pattern
            if sample.str.contains(r"[₹\$€£]", regex=True).any():
                df[col] = convert_currency(df[col])
                semantic_types[col] = "measure"

            # Check percentage pattern
            elif sample.str.contains(r"%", regex=False).any():
                df[col] = convert_percentage(df[col])
                semantic_types[col] = "measure"

            # Check datetime pattern if classified as datetime
            elif sem_type == "datetime":
                df[col] = convert_datetime(df[col])

    return df, semantic_types


def normalize_categories(df, semantic_types):
    """
    Normalizes categorical text entries by stripping trailing spaces.
    """
    df = df.copy()
    for column, sem_type in semantic_types.items():
        if sem_type == "categorical" and (df[column].dtype == "object" or str(df[column].dtype).startswith("string")):
            df[column] = df[column].astype(str).str.strip()
    return df


def smart_clean_column(df, column, semantic_type):
    """
    Smart, skewness-aware missing value imputation for a single column.
    """
    df = df.copy()
    series = df[column]

    # Never invent IDs, keys, or geographic codes
    if semantic_type in ["identifier", "possible_identifier", "geographic_code"]:
        return df

    # Numeric measure cleaning
    if semantic_type in ["measure", "currency", "percentage"]:
        if not pd.api.types.is_numeric_dtype(series):
            series = convert_currency(series)
            series = convert_percentage(series)

        numeric = pd.to_numeric(series, errors="coerce")
        # If no valid numeric values, skip imputation
        if numeric.dropna().empty:
            return df

        skewness = numeric.skew()
        if pd.isna(skewness) or abs(skewness) > 1.0:
            fill_value = numeric.median()
        else:
            fill_value = numeric.mean()

        if pd.isna(fill_value):
            fill_value = 0

        df[column] = numeric.fillna(fill_value)

    # Categorical cleaning
    elif semantic_type == "categorical":
        mode = series.mode(dropna=True)
        fill_value = mode.iloc[0] if not mode.empty else "Unknown"
        df[column] = series.fillna(fill_value)

    # Text cleaning
    elif semantic_type == "text":
        df[column] = series.fillna("Unknown")

    return df


def smart_clean_dataframe(df, semantic_types):
    """
    Applies smart cleaning across all columns in a dataframe.
    """
    cleaned, semantic_types = auto_convert_dtypes(df, semantic_types)
    for column in cleaned.columns:
        cleaned = smart_clean_column(cleaned, column, semantic_types.get(column, "unknown"))
    return cleaned


def detect_business_key_duplicates(df, subset_columns=None):
    """
    Detects exact row duplicates and business-key subset duplicates.
    """
    exact_duplicates = int(df.duplicated().sum())

    if not subset_columns:
        subset_columns = [
            col for col in df.columns
            if any(k in str(col).lower() for k in ["id", "key", "num", "code", "date"])
        ]

    subset_duplicates = 0
    if subset_columns and len(subset_columns) > 0:
        valid_sub = [c for c in subset_columns if c in df.columns]
        if valid_sub:
            subset_duplicates = int(df.duplicated(subset=valid_sub).sum())

    return {
        "exact_duplicates_count": exact_duplicates,
        "exact_duplicates_pct": round((exact_duplicates / max(len(df), 1)) * 100, 2),
        "subset_keys_used": subset_columns,
        "subset_duplicates_count": subset_duplicates,
        "subset_duplicates_pct": round((subset_duplicates / max(len(df), 1)) * 100, 2)
    }


def apply_outlier_treatment(df, column, method='iqr', action='cap', factor=1.5):
    """
    Treats numerical outliers using IQR or Z-Score method by capping, trimming, or median imputation.
    """
    df = df.copy()
    if column not in df.columns or not pd.api.types.is_numeric_dtype(df[column]):
        return df

    series = df[column].dropna()
    if series.empty:
        return df

    if method == 'zscore':
        mean = series.mean()
        std = series.std()
        if std == 0:
            return df
        lower_bound = mean - factor * std
        upper_bound = mean + factor * std
    else:  # IQR default
        q25, q75 = series.quantile(0.25), series.quantile(0.75)
        iqr = q75 - q25
        lower_bound = q25 - factor * iqr
        upper_bound = q75 + factor * iqr

    if action == 'trim':
        df = df[(df[column] >= lower_bound) & (df[column] <= upper_bound) | df[column].isna()]
    elif action == 'impute':
        med = series.median()
        mask = (df[column] < lower_bound) | (df[column] > upper_bound)
        df.loc[mask, column] = med
    else:  # 'cap' default (winsorize)
        df[column] = df[column].clip(lower=lower_bound, upper=upper_bound)

    return df


def apply_column_scaling(df, column, method='standard'):
    """
    Applies Min-Max Scaling [0, 1] or Standard Z-Score Scaling to a numerical column.
    """
    df = df.copy()
    if column not in df.columns or not pd.api.types.is_numeric_dtype(df[column]):
        return df

    series = df[column]
    if method == 'minmax':
        min_val = series.min()
        max_val = series.max()
        if max_val != min_val and not pd.isna(max_val):
            df[f"{column}_minmax"] = (series - min_val) / (max_val - min_val)
    else:  # standard z-score
        mean = series.mean()
        std = series.std()
        if std != 0 and not pd.isna(std):
            df[f"{column}_scaled"] = (series - mean) / std

    return df


def apply_categorical_encoding(df, column, method='onehot'):
    """
    Applies One-Hot Encoding or Label Encoding to a categorical column.
    """
    df = df.copy()
    if column not in df.columns:
        return df

    # Skip if column is empty
    if df[column].dropna().empty:
        return df

    if method == 'label':
        df[f"{column}_encoded"] = df[column].astype('category').cat.codes
    else:  # one-hot
        encoded_dummies = pd.get_dummies(df[column], prefix=column, dtype=int)
        df = pd.concat([df, encoded_dummies], axis=1)

    return df


def generate_cleaning_audit(raw_df, cleaned_df, raw_quality, cleaned_quality):
    """
    Compares dataset state before and after intelligent cleaning.
    """
    raw_missing = int(raw_df.isna().sum().sum())
    cleaned_missing = int(cleaned_df.isna().sum().sum())

    raw_dups = int(raw_df.duplicated().sum())
    cleaned_dups = int(cleaned_df.duplicated().sum())

    return {
        "before": {
            "rows": len(raw_df),
            "missing_cells": raw_missing,
            "duplicate_rows": raw_dups,
            "quality_score": raw_quality.get("score", 0.0),
            "quality_grade": raw_quality.get("grade", "F")
        },
        "after": {
            "rows": len(cleaned_df),
            "missing_cells": cleaned_missing,
            "duplicate_rows": cleaned_dups,
            "quality_score": cleaned_quality.get("score", 0.0),
            "quality_grade": cleaned_quality.get("grade", "F")
        },
        "improvements": {
            "cells_imputed": raw_missing - cleaned_missing,
            "duplicates_removed": raw_dups - cleaned_dups,
            "quality_score_delta": round(cleaned_quality.get("score", 0.0) - raw_quality.get("score", 0.0), 2)
        }
    }