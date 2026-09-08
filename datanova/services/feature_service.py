import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


def generate_automated_features(df, semantic_types):
    """
    Automatically creates new analytical features:
    - Datetime Features: Year, Month, Quarter, DayOfWeek, Is_Weekend
    - Financial Ratio Features: Profit_Margin_Pct (if Sales & Profit present)
    - Numeric Range Bins (Age Group, Income Tier)

    Args:
        df (pd.DataFrame): Input dataset
        semantic_types (dict): Column semantic type mapping

    Returns:
        tuple: (modified dataframe, list of new feature column names)
    """
    if df.empty:
        return df, []

    df = df.copy()
    new_features = []

    # 1. Datetime Features
    date_cols = [c for c, t in semantic_types.items() if t == "datetime" and c in df.columns]

    for date_col in date_cols:
        dt_series = pd.to_datetime(df[date_col], errors="coerce")
        if dt_series.notna().any():
            year_col = f"{date_col}_Year"
            month_col = f"{date_col}_Month"
            quarter_col = f"{date_col}_Quarter"
            weekday_col = f"{date_col}_DayOfWeek"
            weekend_col = f"{date_col}_Is_Weekend"

            if year_col not in df.columns:
                df[year_col] = dt_series.dt.year
                new_features.append(year_col)

            if month_col not in df.columns:
                df[month_col] = dt_series.dt.month
                new_features.append(month_col)

            if quarter_col not in df.columns:
                df[quarter_col] = dt_series.dt.quarter
                new_features.append(quarter_col)

            if weekday_col not in df.columns:
                df[weekday_col] = dt_series.dt.day_name()
                new_features.append(weekday_col)

            if weekend_col not in df.columns:
                df[weekend_col] = dt_series.dt.dayofweek.isin([5, 6]).astype(int)
                new_features.append(weekend_col)

            logger.debug(f"Generated datetime features from '{date_col}': {[year_col, month_col, quarter_col, weekday_col, weekend_col]}")

    # 2. Ratio Features (Sales & Profit)
    lower_cols = {str(c).lower(): c for c in df.columns}
    sales_col = lower_cols.get("sales") or lower_cols.get("revenue")
    profit_col = lower_cols.get("profit") or lower_cols.get("net_profit")

    if sales_col and profit_col and "Profit_Margin_Pct" not in df.columns:
        s_vals = pd.to_numeric(df[sales_col], errors="coerce")
        p_vals = pd.to_numeric(df[profit_col], errors="coerce")

        # Avoid division by zero; NaN will remain NaN
        margin = np.where(s_vals != 0, (p_vals / s_vals) * 100.0, 0.0)
        df["Profit_Margin_Pct"] = np.round(margin, 2)
        new_features.append("Profit_Margin_Pct")
        logger.debug(f"Generated Profit_Margin_Pct from '{sales_col}' and '{profit_col}'")

    # 3. Age Binning Feature (if Age column exists)
    age_col = lower_cols.get("age")
    if age_col and "Age_Group" not in df.columns:
        a_vals = pd.to_numeric(df[age_col], errors="coerce")
        if a_vals.notna().any():
            bins = [0, 18, 35, 50, 65, 120]
            labels = ["Youth (<18)", "Young Adult (18-34)", "Adult (35-49)", "Middle Aged (50-64)", "Senior (65+)"]
            # Use right=False to include 18 in Young Adult, 35 in Adult, etc.
            df["Age_Group"] = pd.cut(a_vals, bins=bins, labels=labels, right=False).astype(str)
            # Replace 'nan' for values outside the bins with 'Unknown'
            df["Age_Group"] = df["Age_Group"].replace('nan', 'Unknown')
            new_features.append("Age_Group")
            logger.debug(f"Generated Age_Group from '{age_col}'")

    return df, new_features