import pandas as pd
import logging
from .cleaning_service import convert_currency, convert_percentage

logger = logging.getLogger(__name__)


def detect_time_series_columns(df, semantic_types):
    """
    Identifies primary datetime column and primary numerical measure columns for time-series analysis.

    Args:
        df (pd.DataFrame): Input dataset
        semantic_types (dict): Column semantic type mapping

    Returns:
        tuple: (date_cols, measure_cols) lists of column names
    """
    date_cols = [
        col for col, sem_type in semantic_types.items()
        if sem_type == "datetime" and col in df.columns
    ]

    valid_types = ["measure", "currency", "percentage"]
    measure_cols = [
        col for col, sem_type in semantic_types.items()
        if sem_type in valid_types and col in df.columns
    ]

    return date_cols, measure_cols


def time_series_analysis(df, date_column, value_column):
    """
    Performs comprehensive time-series analysis across Daily, Monthly, Quarterly, and Yearly frequencies,
    including Period-over-Period (PoP), Year-over-Year (YoY) growth, and Seasonality breakdown.

    Args:
        df (pd.DataFrame): Input dataset
        date_column (str): Name of the datetime column
        value_column (str): Name of the numeric value column

    Returns:
        dict or None: Time series analysis results with monthly/quarterly/yearly trends,
                     seasonality breakdown, and growth metrics.
    """
    if date_column not in df.columns or value_column not in df.columns:
        logger.warning(f"Columns '{date_column}' or '{value_column}' not found in dataframe.")
        return None

    temp = df[[date_column, value_column]].copy()

    # Convert date column
    try:
        temp[date_column] = pd.to_datetime(temp[date_column], errors="coerce", format="mixed")
    except Exception as e:
        logger.warning(f"Date conversion failed for column '{date_column}': {e}. Trying fallback.")
        temp[date_column] = pd.to_datetime(temp[date_column], errors="coerce")

    # Convert value column
    temp[value_column] = pd.to_numeric(
        convert_percentage(convert_currency(temp[value_column])),
        errors="coerce"
    )
    temp.dropna(inplace=True)

    if temp.empty:
        logger.warning(f"No valid data points after cleaning for time series analysis.")
        return None

    temp.set_index(date_column, inplace=True)
    temp.sort_index(inplace=True)

    # 1. Monthly Aggregation & Growth
    monthly = temp[value_column].resample('ME').sum().round(2)

    # If monthly is empty or all zeros, return early
    if monthly.empty or monthly.sum() == 0:
        logger.warning("Monthly aggregation resulted in empty or all-zero data.")
        return {
            "date_column": date_column,
            "value_column": value_column,
            "data_points": 0,
            "total_value": 0.0,
            "overall_growth_pct": 0.0,
            "monthly_trend": [],
            "quarterly_trend": [],
            "yearly_trend": [],
            "seasonality": {"by_month": {}, "by_day": {}}
        }

    pop_growth = (monthly.pct_change() * 100.0).round(2)
    yoy_growth = (monthly.pct_change(12) * 100.0).round(2)

    monthly_records = []
    for dt, val in monthly.items():
        monthly_records.append({
            "date": dt.strftime("%Y-%m"),
            "value": float(val),
            "pop_growth_pct": float(pop_growth.loc[dt]) if not pd.isna(pop_growth.loc[dt]) else 0.0,
            "yoy_growth_pct": float(yoy_growth.loc[dt]) if not pd.isna(yoy_growth.loc[dt]) else 0.0
        })

    # 2. Quarterly Aggregation
    quarterly = temp[value_column].resample('QE').sum().round(2)
    quarterly_records = [{"quarter": f"{dt.year}-Q{dt.quarter}", "value": float(val)} for dt, val in quarterly.items()]

    # 3. Yearly Aggregation
    yearly = temp[value_column].resample('YE').sum().round(2)
    yearly_records = [{"year": dt.strftime("%Y"), "value": float(val)} for dt, val in yearly.items()]

    # 4. Seasonality Breakdown (Month-of-Year & Day-of-Week)
    temp['month_name'] = temp.index.strftime('%B')
    temp['day_name'] = temp.index.strftime('%A')

    month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    month_agg = temp.groupby('month_name')[value_column].sum().reindex(month_order).dropna().round(2).to_dict()
    day_agg = temp.groupby('day_name')[value_column].sum().reindex(day_order).dropna().round(2).to_dict()

    # Overall growth
    overall_growth = 0.0
    if len(monthly) > 1 and monthly.iloc[0] != 0:
        overall_growth = round(((monthly.iloc[-1] - monthly.iloc[0]) / abs(monthly.iloc[0])) * 100.0, 2)

    logger.info(f"Time series analysis completed for '{value_column}' over '{date_column}'. "
                f"Found {len(monthly)} monthly data points. Overall growth: {overall_growth}%")

    # 5. Statsmodels Future Trend Forecasting
    forecast_records = generate_statsmodels_forecast(monthly, periods=6)

    return {
        "date_column": date_column,
        "value_column": value_column,
        "data_points": len(monthly),
        "total_value": float(monthly.sum()),
        "overall_growth_pct": overall_growth,
        "monthly_trend": monthly_records,
        "quarterly_trend": quarterly_records,
        "yearly_trend": yearly_records,
        "seasonality": {
            "by_month": month_agg,
            "by_day": day_agg
        },
        "forecast": forecast_records
    }


def generate_statsmodels_forecast(monthly_series, periods=6):
    """
    Uses Statsmodels ExponentialSmoothing to compute future trend forecast.
    Falls back gracefully to linear trend extrapolation if series is short.
    """
    if len(monthly_series) < 2:
        return []

    forecast_values = []
    try:
        from statsmodels.tsa.api import ExponentialSmoothing
        model = ExponentialSmoothing(monthly_series.values, trend="add", initialization_method="estimated")
        fit_model = model.fit()
        pred = fit_model.forecast(periods)

        last_dt = monthly_series.index[-1]
        for i in range(1, periods + 1):
            future_dt = last_dt + pd.DateOffset(months=i)
            val = max(0.0, float(pred[i - 1]))
            forecast_values.append({
                "date": future_dt.strftime("%Y-%m"),
                "predicted_value": round(val, 2)
            })
        logger.info(f"Generated {periods}-period statsmodels forecast successfully.")

    except Exception as e:
        logger.debug(f"Statsmodels fit warning: {e}. Using linear trend fallback.")
        y = monthly_series.values
        x = np.arange(len(y))
        slope, intercept = np.polyfit(x, y, 1)
        last_dt = monthly_series.index[-1]

        for i in range(1, periods + 1):
            future_dt = last_dt + pd.DateOffset(months=i)
            val = max(0.0, float(slope * (len(y) + i - 1) + intercept))
            forecast_values.append({
                "date": future_dt.strftime("%Y-%m"),
                "predicted_value": round(val, 2)
            })

    return forecast_values