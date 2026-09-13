import pandas as pd
import logging
from .bigdata_optimizer import optimize_dataframe_memory
from .semantic_service import classify_dataframe
from .cleaning_service import (
    normalize_missing_values,
    auto_convert_dtypes,
    normalize_categories,
    smart_clean_dataframe
)
from .quality_service import calculate_quality_score, evaluate_column_usefulness
from .outlier_service import detect_dataset_outliers
from .eda_service import dataset_numeric_summary, calculate_correlation, dataset_memory_summary
from .timeseries_service import time_series_analysis
from .kpi_service import generate_numeric_kpis, detect_business_metrics, top_bottom_categories
from .chart_service import generate_automatic_charts
from .insight_service import generate_ai_explanation
from .feature_service import (
    perform_kmeans_clustering,
    run_random_forest_analysis,
    run_linear_regression_analysis
)

logger = logging.getLogger(__name__)


def analyze_dataset(df, generate_ai=False):
    """
    Unified end-to-end automatic analytics pipeline runner:
    Upload → Validation → Profiling → Semantic Classification → Data Quality →
    Intelligent Cleaning → Descriptive EDA → Correlation → Outliers (IQR & Isolation Forest) →
    Time-Series (ARIMA) → ML Suite (K-Means, Random Forest, Linear Regression) →
    KPI Engine → Top/Bottom Analysis → Automatic Charts → AI Business Explanation

    Args:
        df (pd.DataFrame): Input dataset to analyze
        generate_ai (bool): Whether to generate AI-powered business explanations

    Returns:
        dict: Comprehensive analysis results including all pipeline outputs
    """
    logger.info("Starting end-to-end analytics pipeline...")

    # 0. Big Data Memory Optimization (Downcasts types to prevent RAM saturation on large datasets)
    try:
        df, mem_stats = optimize_dataframe_memory(df, verbose=True)
        logger.info(f"Big Data optimization complete: {mem_stats.get('reduction_pct', 0)}% memory saved.")
    except Exception as e:
        logger.warning(f"Memory optimization notice: {e}")

    # 1. Normalize missing tokens and dirty string entries
    try:
        raw_normalized = normalize_missing_values(df)
        logger.info("Missing value normalization completed.")
    except Exception as e:
        logger.error(f"Error during missing value normalization: {e}")
        raw_normalized = df.copy()

    # 2. Semantic column classification
    try:
        initial_semantics = classify_dataframe(raw_normalized)
        logger.info(f"Semantic classification completed. Found {len(initial_semantics)} columns.")
    except Exception as e:
        logger.error(f"Error during semantic classification: {e}")
        initial_semantics = {}

    # 3. Auto convert currencies, percentages, datetimes
    try:
        converted_df, semantics = auto_convert_dtypes(raw_normalized, initial_semantics)
        logger.info("Auto datatype conversion completed.")
    except Exception as e:
        logger.error(f"Error during datatype conversion: {e}")
        converted_df = raw_normalized
        semantics = initial_semantics

    # 4. Normalize categories
    try:
        converted_df = normalize_categories(converted_df, semantics)
        logger.info("Category normalization completed.")
    except Exception as e:
        logger.error(f"Error during category normalization: {e}")

    # 5. Intelligent Cleaning (skewness-aware, preserving IDs)
    cleaned_df = None
    try:
        cleaned_df = smart_clean_dataframe(converted_df, semantics)
        logger.info("Smart cleaning completed.")
    except Exception as e:
        logger.error(f"Error during smart cleaning: {e}")
        cleaned_df = converted_df

    # 6. Re-evaluate semantics post-cleaning & detect business domain
    try:
        final_semantics = classify_dataframe(cleaned_df)
        logger.info("Post-cleaning semantic classification completed.")
    except Exception as e:
        logger.error(f"Error during post-cleaning semantic classification: {e}")
        final_semantics = semantics

    try:
        from .semantic_service import detect_business_domain
        business_domain = detect_business_domain(cleaned_df, final_semantics)
        logger.info(f"Detected business domain: {business_domain}")
    except Exception as e:
        logger.error(f"Error detecting business domain: {e}")
        business_domain = "General Analytics"

    # 7. Outlier Engine (IQR & Isolation Forest)
    outliers_report = None
    try:
        outliers_report = detect_dataset_outliers(cleaned_df, final_semantics)
        total_outliers = outliers_report.get("total_outlier_count", 0)
        logger.info(f"Outlier detection completed. Found {total_outliers} outliers across {len(outliers_report.get('by_column', {}))} columns.")
    except Exception as e:
        logger.error(f"Error during outlier detection: {e}")
        outliers_report = {"by_column": {}, "total_outlier_count": 0}

    # 8. Data Quality Analysis (Run AFTER cleaning & outlier detection with actual outlier_count)
    quality_report = None
    try:
        actual_outliers = outliers_report.get("total_outlier_count", 0)
        quality_report = calculate_quality_score(cleaned_df, final_semantics, outlier_count=actual_outliers)
        logger.info(f"Data quality score: {quality_report.get('score', 0)}/100 (Grade {quality_report.get('grade', 'F')})")
    except Exception as e:
        logger.error(f"Error during quality scoring: {e}")
        quality_report = {"score": 0, "grade": "F", "recommendations": ["Quality scoring failed."]}

    # 9. Descriptive Statistics
    descriptive_stats = None
    try:
        descriptive_stats = dataset_numeric_summary(cleaned_df, final_semantics)
        logger.info(f"Descriptive statistics generated for {len(descriptive_stats)} numeric columns.")
    except Exception as e:
        logger.error(f"Error generating descriptive statistics: {e}")
        descriptive_stats = {}

    # 10. Correlation Analysis
    corr_dict = None
    try:
        corr_matrix = calculate_correlation(cleaned_df, final_semantics)
        corr_dict = corr_matrix if corr_matrix is not None else {}
        if corr_dict and corr_dict.get("matrix"):
            logger.info(f"Correlation analysis completed. Found {len(corr_dict.get('top_pairs', []))} top correlated pairs.")
        else:
            logger.info("Correlation analysis completed. No numeric columns found for correlation.")
    except Exception as e:
        logger.error(f"Error during correlation analysis: {e}")
        corr_dict = {}

    # 11. KPI Engine
    generic_kpis = None
    business_kpis = None
    try:
        generic_kpis = generate_numeric_kpis(cleaned_df, final_semantics)
        logger.info(f"Generated KPIs for {len(generic_kpis)} numeric columns.")
    except Exception as e:
        logger.error(f"Error generating generic KPIs: {e}")
        generic_kpis = {}

    try:
        business_kpis = detect_business_metrics(cleaned_df)
        logger.info(f"Business KPIs detected: {list(business_kpis.keys())}")
    except Exception as e:
        logger.error(f"Error detecting business KPIs: {e}")
        business_kpis = {}

    # 12. Time Series Engine (ARIMA)
    time_series_report = None
    try:
        date_cols = [c for c, t in final_semantics.items() if t == "datetime" and c in cleaned_df.columns]
        measure_cols = [c for c, t in final_semantics.items() if t in ["measure", "currency", "percentage"] and c in cleaned_df.columns]

        if date_cols and measure_cols and len(cleaned_df) >= 10:
            target_val = next((c for c in measure_cols if c.lower() in ['sales', 'revenue', 'profit', 'quantity', 'amount']), measure_cols[0])
            time_series_report = time_series_analysis(cleaned_df, date_cols[0], target_val)
            if time_series_report:
                logger.info(f"Time-series analysis (ARIMA) completed for '{target_val}' over '{date_cols[0]}'.")
            else:
                logger.warning("Time-series analysis returned no results.")
    except Exception as e:
        logger.error(f"Error during time-series analysis: {e}")
        time_series_report = None

    # 13. Advanced Machine Learning Suite (Run conditionally based on feature prerequisites)
    measure_cols_count = len([c for c, t in final_semantics.items() if t in ["measure", "currency", "percentage"] and c in cleaned_df.columns])

    kmeans_report = None
    if measure_cols_count >= 2 and len(cleaned_df) >= 10:
        try:
            kmeans_report = perform_kmeans_clustering(cleaned_df, final_semantics, n_clusters=3)
            if kmeans_report.get("success"):
                logger.info(f"K-Means Clustering completed with {kmeans_report.get('n_clusters')} clusters.")
        except Exception as e:
            logger.error(f"Error during K-Means Clustering: {e}")
            kmeans_report = {"success": False, "message": "K-Means execution failed."}
    else:
        kmeans_report = {"success": False, "message": "Requires at least 2 numeric columns and 10 rows."}

    rf_report = None
    if measure_cols_count >= 2 and len(cleaned_df) >= 15:
        try:
            rf_report = run_random_forest_analysis(cleaned_df, final_semantics)
            if rf_report.get("success"):
                logger.info(f"Random Forest analysis completed for target '{rf_report.get('target_column')}'. Top predictor: '{rf_report.get('top_predictor')}'.")
        except Exception as e:
            logger.error(f"Error during Random Forest analysis: {e}")
            rf_report = {"success": False, "message": "Random Forest execution failed."}
    else:
        rf_report = {"success": False, "message": "Requires at least 2 numeric columns and 15 rows."}

    lr_report = None
    if measure_cols_count >= 2 and len(cleaned_df) >= 10:
        try:
            lr_report = run_linear_regression_analysis(cleaned_df, final_semantics)
            if lr_report.get("success"):
                logger.info(f"Linear Regression analysis completed for target '{lr_report.get('target_column')}' (R2: {lr_report.get('r2_score')}).")
        except Exception as e:
            logger.error(f"Error during Linear Regression analysis: {e}")
            lr_report = {"success": False, "message": "Linear Regression execution failed."}
    else:
        lr_report = {"success": False, "message": "Requires at least 2 numeric columns and 10 rows."}

    # 14. Top/Bottom Category Analysis
    top_bottom_report = None
    try:
        cat_cols = [c for c, t in final_semantics.items() if t == "categorical" and c in cleaned_df.columns]
        measure_cols = [c for c, t in final_semantics.items() if t in ["measure", "currency", "percentage"] and c in cleaned_df.columns]

        if cat_cols and measure_cols:
            target_cat = cat_cols[0]
            target_val = next((c for c in measure_cols if c.lower() in ['sales', 'profit', 'revenue']), measure_cols[0])
            is_financial = any(k in target_val.lower() for k in ['sales', 'profit', 'revenue', 'qty', 'quantity'])
            agg_func = "sum" if is_financial else "mean"
            top_bottom_report = top_bottom_categories(cleaned_df, target_cat, target_val, n=5, agg_func=agg_func)
            if top_bottom_report:
                logger.info(f"Top/Bottom analysis completed for '{target_cat}' by '{target_val}'.")
            else:
                logger.warning("Top/Bottom analysis returned no results.")
    except Exception as e:
        logger.error(f"Error during top/bottom analysis: {e}")
        top_bottom_report = None

    # 15. Automatic Recommended Charts
    recommended_charts = None
    try:
        recommended_charts = generate_automatic_charts(cleaned_df, final_semantics)
        logger.info(f"Generated {len(recommended_charts)} automatic charts.")
    except Exception as e:
        logger.error(f"Error generating automatic charts: {e}")
        recommended_charts = []

    # 16. Memory Summary
    memory_sum = None
    try:
        memory_sum = dataset_memory_summary(cleaned_df)
        logger.info(f"Memory summary: {memory_sum.get('formatted_memory', 'N/A')}")
    except Exception as e:
        logger.error(f"Error generating memory summary: {e}")
        memory_sum = {"formatted_memory": "N/A", "total_cells": 0}

    # 17. Column Usefulness
    col_usefulness = None
    try:
        col_usefulness = evaluate_column_usefulness(cleaned_df, final_semantics)
        logger.info(f"Column usefulness evaluation completed for {len(col_usefulness)} columns.")
    except Exception as e:
        logger.error(f"Error evaluating column usefulness: {e}")
        col_usefulness = []

    # 18. Consolidated Analytics Pipeline Summary
    pipeline_result = {
        "dataset_overview": {
            "row_count": len(cleaned_df),
            "column_count": len(cleaned_df.columns),
            "columns": list(cleaned_df.columns)
        },
        "business_domain": business_domain,
        "semantic_types": final_semantics,
        "quality": quality_report,
        "descriptive_statistics": descriptive_stats,
        "outliers": outliers_report,
        "correlation_matrix": corr_dict,
        "generic_kpis": generic_kpis,
        "business_kpis": business_kpis,
        "time_series": time_series_report,
        "kmeans_clustering": kmeans_report,
        "random_forest_analysis": rf_report,
        "linear_regression_analysis": lr_report,
        "top_bottom_analysis": top_bottom_report,
        "recommended_charts": recommended_charts,
        "memory_summary": memory_sum,
        "column_usefulness": col_usefulness,
        "cleaned_df": cleaned_df
    }

    # 19. Optional AI Business Explanation Synthesis
    if generate_ai:
        try:
            summary_for_ai = {
                "row_count": len(cleaned_df),
                "quality_score": quality_report.get("score", 0) if quality_report else 0,
                "completeness": quality_report.get("completeness", 0) if quality_report else 0,
                "business_domain": business_domain,
                "business_kpis": business_kpis,
                "outliers_detected": {col: res.get("count", 0) for col, res in outliers_report.get("by_column", {}).items()} if outliers_report else {},
                "top_bottom_analysis": top_bottom_report
            }
            ai_result = generate_ai_explanation(summary_for_ai)
            pipeline_result["ai_explanation"] = ai_result.get("explanation", {})
            logger.info("AI explanation generated successfully.")
        except Exception as e:
            logger.error(f"Error generating AI explanation: {e}")
            pipeline_result["ai_explanation"] = {"fallback": "AI explanation is temporarily unavailable."}

    logger.info("Pipeline analysis completed successfully.")
    return pipeline_result