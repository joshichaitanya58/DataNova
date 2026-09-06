import pandas as pd
import logging
from .cleaning_service import convert_currency, convert_percentage

logger = logging.getLogger(__name__)


def generate_numeric_kpis(df, semantic_types):
    """
    Generates summary KPIs (Total, Average, Min, Max, Median) for all numeric measure, currency, percentage columns.

    Args:
        df (pd.DataFrame): Input dataset
        semantic_types (dict): Column semantic type mapping

    Returns:
        dict: KPIs per column
    """
    kpis = {}
    valid_types = ["measure", "currency", "percentage"]
    measures = [
        col for col, sem_type in semantic_types.items()
        if sem_type in valid_types and col in df.columns
    ]

    for column in measures:
        series = convert_currency(df[column])
        series = convert_percentage(series)
        series = pd.to_numeric(series, errors="coerce").dropna()
        if series.empty:
            continue

        kpis[column] = {
            "total": round(float(series.sum()), 2),
            "average": round(float(series.mean()), 2),
            "median": round(float(series.median()), 2),
            "minimum": round(float(series.min()), 2),
            "maximum": round(float(series.max()), 2)
        }

    return kpis


def detect_business_metrics(df, business_domain="General Analytics"):
    """
    Detects business-specific Key Performance Indicators (KPIs) tailored by domain.

    Args:
        df (pd.DataFrame): Input dataset
        business_domain (str): Domain name (used for labeling)

    Returns:
        dict: Business KPIs including total sales, profit, margin, order count, etc.
    """
    lower_map = {str(col).lower(): col for col in df.columns}
    metrics = {
        "domain": business_domain
    }

    sales_col = lower_map.get("sales") or lower_map.get("revenue") or lower_map.get("amount") or lower_map.get("total_sales")
    profit_col = lower_map.get("profit") or lower_map.get("net_profit") or lower_map.get("margin")
    qty_col = lower_map.get("quantity") or lower_map.get("qty") or lower_map.get("volume") or lower_map.get("units")
    disc_col = lower_map.get("discount") or lower_map.get("discount_pct") or lower_map.get("disc")
    order_col = lower_map.get("order_id") or lower_map.get("order_num") or lower_map.get("invoice_no") or lower_map.get("id")

    sales_val = 0.0
    profit_val = 0.0
    total_orders = len(df)

    if order_col:
        total_orders = int(df[order_col].nunique(dropna=True))

    metrics["total_records"] = int(len(df))
    metrics["total_orders_or_keys"] = total_orders

    if sales_col:
        s_series = convert_currency(df[sales_col])
        sales_val = float(pd.to_numeric(s_series, errors="coerce").sum())
        metrics["total_sales"] = round(sales_val, 2)
        metrics["average_sales_per_record"] = round(sales_val / max(len(df), 1), 2)

        if total_orders > 0:
            metrics["average_order_value_aov"] = round(sales_val / total_orders, 2)

    if profit_col:
        p_series = convert_currency(df[profit_col])
        profit_val = float(pd.to_numeric(p_series, errors="coerce").sum())
        metrics["total_profit"] = round(profit_val, 2)

    if sales_col and profit_col:
        if sales_val != 0:
            margin = (profit_val / sales_val) * 100.0
            metrics["profit_margin_pct"] = round(float(margin), 2)

    if qty_col:
        q_series = convert_currency(df[qty_col])
        qty_val = float(pd.to_numeric(q_series, errors="coerce").sum())
        metrics["total_quantity"] = round(qty_val, 2)

    if disc_col:
        d_series = convert_percentage(df[disc_col])
        d_series = pd.to_numeric(d_series, errors="coerce")
        mean_disc = d_series.mean()
        if not pd.isna(mean_disc):
            avg_disc = float(mean_disc) * 100.0 if mean_disc <= 1.0 else float(mean_disc)
            metrics["average_discount_pct"] = round(avg_disc, 2)

    return metrics


def top_bottom_categories(df, category_col, measure_col, n=5, agg_func="sum"):
    """
    Calculates Top-N and Bottom-N categories aggregated by a measure.

    Args:
        df (pd.DataFrame): Input dataset
        category_col (str): Column name for categories
        measure_col (str): Column name for numeric measure
        n (int): Number of top/bottom categories to return
        agg_func (str): Aggregation function ('sum', 'mean', 'count', 'median', 'min', 'max')

    Returns:
        dict or None: Contains top_n, bottom_n, and metadata
    """
    if category_col not in df.columns or measure_col not in df.columns:
        return None

    temp = df[[category_col, measure_col]].copy()
    temp[category_col] = temp[category_col].fillna("Unknown").astype(str)
    temp[measure_col] = convert_currency(temp[measure_col])
    temp[measure_col] = pd.to_numeric(temp[measure_col], errors="coerce")
    temp.dropna(subset=[measure_col], inplace=True)

    if temp.empty:
        return None

    grouped = temp.groupby(category_col)[measure_col].agg(agg_func).round(2)
    top_n = grouped.sort_values(ascending=False).head(n).to_dict()
    bottom_n = grouped.sort_values(ascending=True).head(n).to_dict()

    return {
        "category": category_col,
        "measure": measure_col,
        "aggregation": agg_func,
        "top_n": top_n,
        "bottom_n": bottom_n
    }