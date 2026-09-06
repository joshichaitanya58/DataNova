import re
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def detect_semantic_type(series, column_name):
    """
    Detects the semantic role of a pandas series for analytical decision making.

    Possible semantic types:
    - 'identifier': Unique key / ID column (e.g. Customer_ID, Order_ID)
    - 'geographic_code': Postal / Zip / Pincode / Country / State columns
    - 'boolean': Logical True/False or binary flags
    - 'datetime': Date, time, or timestamp column
    - 'currency': Monetary metric (Sales, Revenue, Profit, Cost, Price)
    - 'percentage': Percentage metric (Discount, Rate, Margin, Growth %)
    - 'measure': Continuous numerical metric (Age, Quantity, Score, Weight, Lat/Lon)
    - 'possible_identifier': Numeric high-uniqueness integer columns that act like keys
    - 'categorical': Distinct category column (Region, Segment, Status)
    - 'text': High-cardinality descriptive text (Comments, Descriptions)
    - 'unknown': Empty or all-null series

    Args:
        series (pd.Series): Column data
        column_name (str): Name of the column

    Returns:
        str: Semantic type label
    """
    name = str(column_name).lower().strip()
    non_null = series.dropna()

    if non_null.empty:
        return "unknown"

    total_count = len(non_null)
    unique_count = series.nunique(dropna=True)
    unique_ratio = unique_count / max(total_count, 1)

    # 1. Coordinates (Latitude / Longitude are continuous measures)
    if name in ["latitude", "lat", "longitude", "lon", "long"]:
        return "measure"

    # 2. Geographic Codes / Locations
    geo_words = ["postal", "zipcode", "zip_code", "pincode", "zip", "country", "state", "city", "region", "province", "territory"]
    if any(word in name for word in geo_words):
        return "geographic_code"

    # 3. Identifiers (precise token / regex matching)
    id_pattern = re.compile(r'(^|_)(id|uuid|guid|key|num|no|code)($|_)', re.IGNORECASE)
    id_explicit = ["customer_id", "order_id", "transaction_id", "invoice", "sku", "patient_id", "employee_id"]
    if name in id_explicit or id_pattern.search(name):
        if not any(kw in name for kw in ["type", "name", "category", "desc", "title", "keyboard"]):
            return "identifier"

    # 4. Boolean check
    if pd.api.types.is_bool_dtype(series):
        return "boolean"

    if unique_count <= 2 and set(non_null.unique()).issubset({0, 1, '0', '1', True, False, 'true', 'false', 'True', 'False', 'Y', 'N'}):
        return "boolean"

    # 5. Datetime check
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series) or series.dtype == "object":
        sample = non_null.astype(str).head(100)

        # Check explicit currency symbol
        if sample.str.contains(r"[₹\$€£]", regex=True).any():
            return "currency"

        # Check explicit percentage symbol
        if sample.str.contains(r"%", regex=False).any():
            return "percentage"

        date_keywords = ["date", "time", "timestamp", "dt", "year", "month", "day"]
        has_date_keyword = any(k in name for k in date_keywords)

        if has_date_keyword or sample.str.contains(r'[-/:]', regex=True).any():
            try:
                parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
                date_ratio = parsed.notna().mean() if len(parsed) > 0 else 0.0
                if date_ratio >= 0.7:
                    return "datetime"
            except Exception:
                pass

    # 6. Numeric columns (Currency vs Percentage vs Measures vs Identifiers)
    if pd.api.types.is_numeric_dtype(series):
        currency_words = ["sales", "profit", "revenue", "amount", "price", "cost", "income", "salary", "expense", "budget", "total_sales", "net_profit"]
        if any(w in name for w in currency_words):
            return "currency"

        pct_words = ["discount", "rate", "percent", "pct", "ratio", "margin", "growth"]
        if any(w in name for w in pct_words):
            return "percentage"

        measure_keywords = ["age", "qty", "quantity", "score", "count", "weight", "height", "depth", "volume", "units"]
        has_measure_keyword = any(k in name for k in measure_keywords)

        if unique_ratio > 0.95 and not has_measure_keyword and pd.api.types.is_integer_dtype(series):
            return "possible_identifier"

        return "measure"

    # 7. Categorical vs Text
    if unique_count <= 60 or unique_ratio <= 0.05:
        return "categorical"

    return "text"


def classify_dataframe(df):
    """
    Classifies all columns of a dataframe into semantic types.

    Args:
        df (pd.DataFrame): Input dataset

    Returns:
        dict: Mapping of column name to semantic type
    """
    result = {}
    for column in df.columns:
        result[column] = detect_semantic_type(df[column], column)
    logger.debug(f"Classified {len(result)} columns into semantic types.")
    return result


def detect_business_domain(df, semantic_types=None):
    """
    Infers business domain context based on column names and semantic types.

    Domains considered:
    - 'Retail / E-Commerce'
    - 'Finance & Banking'
    - 'HR & Workforce'
    - 'Healthcare'
    - 'SaaS / Subscriptions'
    - 'Hospitality / Travel'
    - 'General Analytics' (fallback)

    Args:
        df (pd.DataFrame): Input dataset
        semantic_types (dict, optional): Mapping of column name to semantic type

    Returns:
        str: Inferred business domain
    """
    if semantic_types is None:
        semantic_types = classify_dataframe(df)

    col_names = [str(c).lower() for c in df.columns]

    retail_keywords = ["sales", "order", "product", "category", "sku", "ship", "customer", "quantity", "segment", "store"]
    finance_keywords = ["balance", "credit", "debit", "loan", "account", "interest", "transaction", "portfolio", "roi", "exposure"]
    hr_keywords = ["employee", "salary", "department", "tenure", "attrition", "hire", "job", "performance", "rating"]
    healthcare_keywords = ["patient", "diagnosis", "doctor", "hospital", "dosage", "treatment", "bmi", "blood_pressure"]
    saas_keywords = ["mrr", "arr", "churn", "subscription", "plan", "active_users", "seats", "cac", "ltv"]
    hospitality_keywords = ["hotel", "booking", "room", "guest", "reservation", "check_in", "check_out", "stay", "occupancy", "resort"]

    match_counts = {
        "Retail / E-Commerce": sum(1 for k in retail_keywords if any(k in c for c in col_names)),
        "Finance & Banking": sum(1 for k in finance_keywords if any(k in c for c in col_names)),
        "HR & Workforce": sum(1 for k in hr_keywords if any(k in c for c in col_names)),
        "Healthcare": sum(1 for k in healthcare_keywords if any(k in c for c in col_names)),
        "SaaS / Subscriptions": sum(1 for k in saas_keywords if any(k in c for c in col_names)),
        "Hospitality / Travel": sum(1 for k in hospitality_keywords if any(k in c for c in col_names))
    }

    # Boost scores based on semantic types
    currency_cols = [c for c, t in semantic_types.items() if t == "currency"]
    if currency_cols and match_counts["Retail / E-Commerce"] > 0:
        match_counts["Retail / E-Commerce"] += len(currency_cols)
    if currency_cols and match_counts["Finance & Banking"] > 0:
        match_counts["Finance & Banking"] += len(currency_cols)

    best_domain = max(match_counts, key=match_counts.get)
    if match_counts[best_domain] == 0:
        logger.info("No clear business domain detected. Defaulting to 'General Analytics'.")
        return "General Analytics"

    logger.info(f"Detected business domain: {best_domain} (score: {match_counts[best_domain]})")
    return best_domain