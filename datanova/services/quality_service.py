import logging
from datetime import timedelta
import pandas as pd
from . import ai_helper

logger = logging.getLogger(__name__)


def calculate_quality_score(df, semantic_types=None, invalid_count=0, outlier_count=0):
    """
    Calculates Data Quality Index 3.0 (0 to 100) based on 6 core industry dimensions:
    - Completeness (20%): Non-null cell ratio
    - Uniqueness (20%): Non-duplicate row ratio
    - Validity (15%): Converted valid cell ratio
    - Accuracy / Outlier Score (15%): Ratio of normal (non-outlier) values
    - Consistency (15%): Categorical & string formatting consistency
    - Timeliness (15%): Recency of data based on datetime columns

    Args:
        df (pd.DataFrame): Input dataset
        semantic_types (dict, optional): Column semantic type mapping
        invalid_count (int): Number of invalid cells (from validation)
        outlier_count (int): Number of outlier cells

    Returns:
        dict: Quality score, grade, component scores, and recommendations.
    """
    if semantic_types is None:
        from . import semantic_service
        semantic_types = semantic_service.classify_dataframe(df)

    total_rows = len(df)
    total_cols = len(df.columns)
    total_cells = total_rows * total_cols

    if total_cells == 0:
        return {
            "score": 0.0,
            "grade": "F",
            "completeness": 0.0,
            "uniqueness": 0.0,
            "validity": 0.0,
            "accuracy": 0.0,
            "consistency": 0.0,
            "timeliness": 0.0,
            "missing_cells": 0,
            "duplicate_rows": 0,
            "invalid_cells": invalid_count,
            "outlier_cells": outlier_count,
            "recommendations": ["Dataset is empty. Please upload a valid dataset."]
        }

    weights = {
        "completeness": 0.20,
        "uniqueness": 0.20,
        "validity": 0.15,
        "accuracy": 0.15,
        "consistency": 0.15,
        "timeliness": 0.15
    }

    # 1. Completeness
    missing_cells = int(df.isna().sum().sum())
    completeness = max(0.0, (1.0 - (missing_cells / total_cells)) * 100.0)

    # 2. Uniqueness
    duplicate_rows = int(df.duplicated().sum())
    uniqueness = max(0.0, (1.0 - (duplicate_rows / max(total_rows, 1))) * 100.0)

    # 3. Validity
    validity = max(0.0, (1.0 - (invalid_count / max(total_cells, 1))) * 100.0)

    # 4. Accuracy / Outlier Score
    numeric_cols = df.select_dtypes(include=['number']).columns
    total_numeric_cells = total_rows * len(numeric_cols) if len(numeric_cols) > 0 else 1
    accuracy = max(0.0, (1.0 - (outlier_count / max(total_numeric_cells, 1))) * 100.0)

    # 5. Consistency (Whitespace & Mixed-Case)
    cat_cols = [c for c, t in semantic_types.items() if t == "categorical" and c in df.columns]
    inconsistent_count = 0
    for col in cat_cols:
        sample = df[col].dropna().astype(str)
        if sample.empty:
            continue
        # Check for unstripped spaces
        unstripped = sample.str.contains(r'^\s+|\s+$', regex=True).sum()
        inconsistent_count += int(unstripped)
        # Check for mixed-case inconsistencies (e.g., "USA" and "usa")
        if sample.nunique() > 1:
            lower_unique = sample.str.lower().nunique()
            if lower_unique < sample.nunique():
                inconsistent_count += (sample.nunique() - lower_unique)

    total_cat_cells = total_rows * len(cat_cols) if len(cat_cols) > 0 else 1
    consistency = max(0.0, (1.0 - (inconsistent_count / max(total_cat_cells, 1))) * 100.0)

    # 6. Timeliness (DN-DATA-001)
    date_cols = [c for c, t in semantic_types.items() if t == "datetime" and c in df.columns]
    timeliness = 100.0  # Default to perfect if no date column
    if date_cols:
        # Use format='mixed' to suppress UserWarning and handle various date formats efficiently.
        # This informs pandas to expect and parse multiple formats without falling back to slower,
        # element-wise parsing which triggers the warning.
        date_series = pd.to_datetime(df[date_cols[0]], errors='coerce', format='mixed')
        latest_date = date_series.max()
        if pd.notna(latest_date):
            now = pd.Timestamp.now()
            # If dataset max date is older than 2 years from today, penalize age factor
            age_days = (now - latest_date).days
            if age_days > 730:
                freshness_factor = max(0.1, 1.0 - (age_days - 730) / 3650)
            else:
                freshness_factor = 1.0

            one_year_ago = latest_date - timedelta(days=365)
            recent_records = (date_series >= one_year_ago).sum()
            span_timeliness = (recent_records / max(total_rows, 1)) * 100
            timeliness = span_timeliness * freshness_factor
        else:
            timeliness = 0
    else:
        # If no date column, remove timeliness from weighting and redistribute
        total_weight = 1.0 - weights["timeliness"]
        for k in weights:
            if k != "timeliness":
                weights[k] = weights[k] / total_weight
        weights["timeliness"] = 0

    # Weighted Overall Score 3.0
    score = (completeness * weights["completeness"]) + \
            (uniqueness * weights["uniqueness"]) + \
            (validity * weights["validity"]) + \
            (accuracy * weights["accuracy"]) + \
            (consistency * weights["consistency"]) + \
            (timeliness * weights["timeliness"])
    score = round(float(score), 2)

    # Determine Letter Grade
    if score >= 90:
        grade = "A+"
    elif score >= 80:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 50:
        grade = "C"
    else:
        grade = "F"

    # Actionable Recommendations
    recommendations = []
    if missing_cells > 0:
        recommendations.append(f"Impute or clean {missing_cells} missing values ({round((missing_cells/total_cells)*100, 1)}% missing).")
    if duplicate_rows > 0:
        recommendations.append(f"Remove {duplicate_rows} duplicate rows to improve uniqueness.")
    if outlier_count > 0:
        recommendations.append(f"Inspect {outlier_count} detected numeric outliers across measure columns.")
    if inconsistent_count > 0 and consistency < 95:
        recommendations.append(f"Standardize {inconsistent_count} inconsistent text entries (whitespace or mixed-case).")
    if timeliness < 70 and date_cols:
        recommendations.append(f"Data may be outdated. Only {round(timeliness,1)}% of records are from the last year.")
    if not recommendations:
        recommendations.append("Dataset health is excellent! Ready for advanced analytics.")

    return {
        "score": score,
        "grade": grade,
        "completeness": round(completeness, 2),
        "uniqueness": round(uniqueness, 2),
        "validity": round(validity, 2),
        "accuracy": round(accuracy, 2),
        "consistency": round(consistency, 2),
        "timeliness": round(timeliness, 2) if date_cols else "N/A",
        "missing_cells": missing_cells,
        "duplicate_rows": duplicate_rows,
        "invalid_cells": invalid_count,
        "outlier_cells": outlier_count,
        "recommendations": recommendations
    }


def evaluate_column_usefulness(df, semantic_types):
    """
    Evaluates dataset columns for analytical value and identifies candidates for removal/dropping
    using hyper-intelligent deterministic rules (without requiring external AI APIs).

    Detects:
    1. 100% or high missing values (>= 50%)
    2. Single constant (zero variance) columns
    3. Quasi-constant columns (>= 99% single value ratio)
    4. Exact duplicate columns (identical data across columns)
    5. High-cardinality ID / Row index / UUID columns
    6. High collinearity / redundant numerical pairs (corr >= 0.98)
    7. Unnamed / export noise columns ('Unnamed: 0', 'index', etc.)

    Args:
        df (pd.DataFrame): Input dataset
        semantic_types (dict): Column semantic type mapping

    Returns:
        list: List of dicts with column evaluation details.
    """
    total_rows = max(len(df), 1)
    results = []
    seen_columns_data = {}

    # Pre-compute exact duplicate columns
    duplicate_map = {}
    for col in df.columns:
        col_series = df[col].astype(str)
        col_hash = hash(tuple(col_series))
        if col_hash in seen_columns_data:
            duplicate_map[col] = seen_columns_data[col_hash]
        else:
            seen_columns_data[col_hash] = col

    # Pre-compute collinear numeric columns
    collinear_map = {}
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and df[c].dropna().nunique() > 1]
    if len(numeric_cols) >= 2:
        try:
            corr_matrix = df[numeric_cols].corr().abs()
            for i in range(len(numeric_cols)):
                for j in range(i + 1, len(numeric_cols)):
                    c1, c2 = numeric_cols[i], numeric_cols[j]
                    # NOTE: guard on c2 (the column that would be marked redundant),
                    # not c1 - c2 is the dict key, so this is what must stay unique.
                    if c2 not in collinear_map and corr_matrix.loc[c1, c2] >= 0.98:
                        collinear_map[c2] = (c1, round(corr_matrix.loc[c1, c2], 3))
        except Exception as e:
            logger.debug(f"Collinearity check skipped: {e}")

    for col in df.columns:
        series = df[col]
        non_null_cnt = int(series.notna().sum())
        missing_cnt = total_rows - non_null_cnt
        missing_pct = round((missing_cnt / total_rows) * 100.0, 2)
        unique_cnt = int(series.nunique(dropna=True))
        sem_type = semantic_types.get(col, "unknown")

        is_drop = False
        reason = "Useful analytical column."
        tag = ""

        col_lower = str(col).lower().strip()

        # 1. Junk / Unnamed Export Artifact
        if col_lower in ["unnamed: 0", "index", "level_0", "_id", "id_0"]:
            is_drop = True
            tag = " (Junk Artifact)"
            reason = f"System/Export artifact index column '{col}'."

        # 2. 100% Missing
        elif non_null_cnt == 0:
            is_drop = True
            tag = " (Not Required)"
            reason = "100% missing cells (no data available)."

        # 3. Zero Variance / Constant Value
        elif unique_cnt == 1:
            is_drop = True
            tag = " (Not Required)"
            val = str(series.dropna().iloc[0]) if non_null_cnt > 0 else ""
            reason = f"Single constant value '{val}' across all rows (zero variance)."

        # 4. Quasi-Constant (>= 99% single value concentration)
        elif non_null_cnt > 10:
            top_val_count = series.value_counts(dropna=True).iloc[0]
            top_val_ratio = round((top_val_count / non_null_cnt) * 100.0, 2)
            if top_val_ratio >= 99.0:
                is_drop = True
                tag = " (Quasi-Constant)"
                top_val = str(series.value_counts(dropna=True).index[0])
                reason = f"99%+ rows contain the exact same value '{top_val}' ({top_val_ratio}% dominant)."

        # 5. Exact Duplicate Column
        if not is_drop and col in duplicate_map:
            is_drop = True
            tag = " (Duplicate)"
            reason = f"100% duplicate data content of column '{duplicate_map[col]}'."

        # 6. High Missing Rate (>= 50%)
        elif not is_drop and missing_pct >= 50.0:
            is_drop = True
            tag = " (High Nulls)"
            reason = f"High missing value percentage ({missing_pct}% cells missing)."

        # 7. High-Cardinality Row Identifier / Index
        elif not is_drop and (sem_type in ["identifier", "possible_identifier"] or any(k in col_lower for k in ["_id", "row_id", "serial", "guid", "uuid"])):
            if unique_cnt == total_rows or (unique_cnt >= total_rows * 0.95 and total_rows > 20):
                is_drop = True
                tag = " (Identifier)"
                reason = f"High cardinality primary key/row identifier with {unique_cnt} unique values."

        # 8. High Collinearity / Redundant Numeric Pair
        elif not is_drop and col in collinear_map:
            primary_col, corr_val = collinear_map[col]
            is_drop = True
            tag = " (Redundant)"
            reason = f"Extremely high correlation ({corr_val}) with '{primary_col}' (redundant feature)."

        # 9. Uninformative Raw Noise Text
        elif not is_drop and sem_type in ["text"] and unique_cnt == total_rows and total_rows > 50:
            if not any(k in col_lower for k in ["name", "code", "id", "date", "sales", "revenue", "profit", "amount"]):
                is_drop = True
                tag = " (Low Value)"
                reason = "High-cardinality unstructured noise text without aggregate analytical metrics."

        display_name = f"{col}{tag}" if tag else col

        results.append({
            "column": col,
            "display_name": display_name,
            "is_recommended_drop": is_drop,
            "tag": tag.strip(),
            "reason": reason,
            "missing_pct": missing_pct,
            "unique_cnt": unique_cnt,
            "semantic_type": sem_type
        })

    return results


def get_ai_column_suggestions(df, semantic_types):
    """
    Evaluates column usefulness using hyper-intelligent rule-based evaluation first.
    If available, enriches suggestions with LLM AI, otherwise returns rule-based results.
    """
    rule_results = evaluate_column_usefulness(df, semantic_types)

    try:
        df_info_list = []
        columns_to_send = df.columns[:50]

        for col in columns_to_send:
            col_type = str(df[col].dtype)
            col_sem = semantic_types.get(col, 'unknown')
            missing_percent = df[col].isnull().sum() / len(df) * 100 if len(df) > 0 else 0
            unique_count = df[col].nunique()
            info_str = f"- Column: '{col}' (Dtype: {col_type}, Semantic: {col_sem}, Missing: {missing_percent:.2f}%, Unique Values: {unique_count})"
            df_info_list.append(info_str)
        df_info_str = "\n".join(df_info_list)

        prompt = f"""
        You are an expert data analyst assistant. Analyze these columns:
        {df_info_str}

        Identify columns that are likely irrelevant, redundant, or low analytical value.
        Return JSON with key "unwanted_columns" containing objects with "column_name" and "reason".
        """

        ai_suggestions = ai_helper.generate_ai_completion(prompt, expect_json=True)

        if isinstance(ai_suggestions, dict) and "unwanted_columns" in ai_suggestions:
            unwanted_list = ai_suggestions["unwanted_columns"]
        elif isinstance(ai_suggestions, list):
            unwanted_list = ai_suggestions
        else:
            unwanted_list = []

        ai_unwanted = {
            item['column_name']: item.get('reason', 'Flagged by AI as low analytical value.')
            for item in unwanted_list
            if isinstance(item, dict) and 'column_name' in item
        }

        # Merge AI suggestions into the rule-based results
        for col_eval in rule_results:
            col_name = col_eval["column"]
            if col_name in ai_unwanted:
                if not col_eval["is_recommended_drop"]:
                    # Rules didn't flag it, but the AI did - add it as an AI-only suggestion
                    col_eval["is_recommended_drop"] = True
                    col_eval["tag"] = "AI Suggested"
                    col_eval["display_name"] = f"{col_name} (AI Suggested)"
                    col_eval["reason"] = ai_unwanted[col_name]
                else:
                    # Rules already flagged it - append the AI's reasoning for extra confidence
                    col_eval["reason"] = f"{col_eval['reason']} AI confirms: {ai_unwanted[col_name]}"

        return rule_results

    except Exception as e:
        logger.warning(f"AI column suggestion enrichment failed, falling back to rule-based results: {e}")
        return rule_results