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

        # Division by zero produces NaN (undefined margin), not 0.0%
        margin = np.where((s_vals.notna()) & (s_vals != 0), (p_vals / s_vals) * 100.0, np.nan)
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


def perform_kmeans_clustering(df, semantic_types, n_clusters=3):
    """
    Applies K-Means Clustering to group similar data records and discover hidden segment patterns.

    Args:
        df (pd.DataFrame): Input dataset
        semantic_types (dict): Column semantic mappings
        n_clusters (int): Number of clusters to form (must be between 2 and 10)

    Returns:
        dict: Cluster summaries, centroids, sizes, and inertia.
    """
    if not isinstance(n_clusters, int) or not (2 <= n_clusters <= 10):
        return {"success": False, "message": "Number of clusters (n_clusters) must be an integer between 2 and 10."}

    numeric_cols = [
        col for col, stype in semantic_types.items()
        if stype in ["measure", "currency", "percentage"] and col in df.columns
    ]

    if len(numeric_cols) < 2 or len(df) < 10:
        return {"success": False, "message": "K-Means requires at least 2 numeric columns and 10 rows."}

    try:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        # Extract numeric sub-frame and drop missing rows
        sub_df = df[numeric_cols].apply(pd.to_numeric, errors="coerce").dropna()
        if len(sub_df) < 10:
            return {"success": False, "message": "Insufficient valid rows for K-Means clustering."}

        scaler = StandardScaler()
        scaled_data = scaler.fit_transform(sub_df)

        n_c = min(n_clusters, len(sub_df))
        kmeans = KMeans(n_clusters=n_c, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(scaled_data)

        # Un-scale cluster centroids back to original feature scale
        unscaled_centroids = scaler.inverse_transform(kmeans.cluster_centers_)
        centroids_dict = {}
        for idx, c_vector in enumerate(unscaled_centroids):
            centroids_dict[f"Cluster {idx + 1}"] = {
                col: round(float(val), 2) for col, val in zip(numeric_cols, c_vector)
            }

        # Build cluster summaries
        sub_df_copy = sub_df.copy()
        sub_df_copy["Cluster"] = [f"Cluster {l + 1}" for l in cluster_labels]

        cluster_summary = {}
        for cluster_name, group in sub_df_copy.groupby("Cluster"):
            means = group.drop(columns=["Cluster"]).mean().round(2).to_dict()
            cluster_summary[cluster_name] = {
                "size": len(group),
                "percentage": round((len(group) / len(sub_df)) * 100.0, 1),
                "feature_means": means
            }

        return {
            "success": True,
            "n_clusters": n_c,
            "total_samples": len(sub_df),
            "features_used": numeric_cols,
            "inertia": round(float(kmeans.inertia_), 2),
            "centroids": centroids_dict,
            "clusters": cluster_summary
        }
    except Exception as e:
        logger.warning(f"K-Means clustering error: {e}")
        return {"success": False, "message": f"K-Means failed: {e}"}


def run_random_forest_analysis(df, semantic_types):
    """
    Trains a Random Forest Regression model for target prediction, feature importance ranking, and R2 variance explanation.

    Args:
        df (pd.DataFrame): Input dataset
        semantic_types (dict): Column semantic mappings

    Returns:
        dict: Feature importances, target column, R2 score, and top predictive drivers.
    """
    numeric_cols = [
        col for col, stype in semantic_types.items()
        if stype in ["measure", "currency", "percentage"] and col in df.columns
    ]

    if len(numeric_cols) < 2 or len(df) < 15:
        return {"success": False, "message": "Random Forest requires at least 2 numeric columns and 15 rows."}

    try:
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.model_selection import train_test_split

        # Choose target: preference for Sales/Profit/Revenue/Price, else first numeric col
        target_col = next(
            (c for c in numeric_cols if c.lower() in ['sales', 'profit', 'revenue', 'price', 'quantity']),
            numeric_cols[0]
        )
        feature_cols = [c for c in numeric_cols if c != target_col]

        if not feature_cols:
            return {"success": False, "message": "No predictor features available for Random Forest."}

        sub_df = df[[target_col] + feature_cols].apply(pd.to_numeric, errors="coerce").dropna()
        if len(sub_df) < 15:
            return {"success": False, "message": "Insufficient complete rows for Random Forest."}

        X = sub_df[feature_cols]
        y = sub_df[target_col]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        rf = RandomForestRegressor(n_estimators=50, random_state=42)
        rf.fit(X_train, y_train)

        score = rf.score(X_test, y_test)
        importances = dict(zip(feature_cols, [round(float(imp), 4) for imp in rf.feature_importances_]))
        sorted_importances = dict(sorted(importances.items(), key=lambda item: item[1], reverse=True))

        return {
            "success": True,
            "target_column": target_col,
            "r2_score": round(float(score), 4),
            "feature_importances": sorted_importances,
            "top_predictor": list(sorted_importances.keys())[0] if sorted_importances else None
        }
    except Exception as e:
        logger.warning(f"Random Forest analysis error: {e}")
        return {"success": False, "message": f"Random Forest failed: {e}"}


def run_linear_regression_analysis(df, semantic_types):
    """
    Fits a Linear Regression model for predicting numerical targets (e.g. Sales, Revenue, Price).

    Args:
        df (pd.DataFrame): Input dataset
        semantic_types (dict): Column semantic mappings

    Returns:
        dict: Coefficients, intercept, R2 variance explained, and equation parameters.
    """
    numeric_cols = [
        col for col, stype in semantic_types.items()
        if stype in ["measure", "currency", "percentage"] and col in df.columns
    ]

    if len(numeric_cols) < 2 or len(df) < 10:
        return {"success": False, "message": "Linear Regression requires at least 2 numeric columns and 10 rows."}

    try:
        from sklearn.linear_model import LinearRegression
        from sklearn.model_selection import train_test_split

        target_col = next(
            (c for c in numeric_cols if c.lower() in ['sales', 'profit', 'revenue', 'price']),
            numeric_cols[0]
        )
        feature_cols = [c for c in numeric_cols if c != target_col]

        if not feature_cols:
            return {"success": False, "message": "No predictor features for Linear Regression."}

        sub_df = df[[target_col] + feature_cols].apply(pd.to_numeric, errors="coerce").dropna()
        if len(sub_df) < 10:
            return {"success": False, "message": "Insufficient rows for Linear Regression."}

        X = sub_df[feature_cols]
        y = sub_df[target_col]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        lr = LinearRegression()
        lr.fit(X_train, y_train)

        score = lr.score(X_test, y_test)
        coef_dict = {col: round(float(coef), 4) for col, coef in zip(feature_cols, lr.coef_)}

        return {
            "success": True,
            "target_column": target_col,
            "r2_score": round(float(score), 4),
            "intercept": round(float(lr.intercept_), 4),
            "coefficients": coef_dict
        }
    except Exception as e:
        logger.warning(f"Linear Regression error: {e}")
        return {"success": False, "message": f"Linear Regression failed: {e}"}