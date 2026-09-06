import os
import json
import logging
from . import ai_helper

logger = logging.getLogger(__name__)


def generate_rule_based_insights(analytics_summary):
    """
    Generates rule-based business insights and recommendations when AI key is unavailable.
    """
    domain = analytics_summary.get("domain", "General Analytics")
    row_count = analytics_summary.get("row_count", 0)
    quality_score = analytics_summary.get("quality_score", 100.0)
    grade = analytics_summary.get("grade", "A+")
    biz_kpis = analytics_summary.get("business_kpis", {})
    top_bottom = analytics_summary.get("top_bottom_analysis", {})
    outliers = analytics_summary.get("outliers_detected", {})
    top_corr = analytics_summary.get("top_correlations", [])

    # 1. Executive Summary
    total_sales = biz_kpis.get("total_sales")
    total_profit = biz_kpis.get("total_profit")
    margin_pct = biz_kpis.get("profit_margin_pct")

    exec_summary = f"The dataset contains {row_count} records evaluated under the '{domain}' domain with a Data Quality Score of {quality_score}/100 (Grade {grade})."
    if total_sales:
        exec_summary += f" Total Revenue is ₹{total_sales:,.2f}."
    if total_profit:
        exec_summary += f" Total Profit generated is ₹{total_profit:,.2f} (Margin: {margin_pct}%)."

    # 2. Positive Highlights
    highlights = []
    if quality_score >= 80:
        highlights.append(f"High data quality rating of {quality_score}/100 ({grade} Grade).")
    if margin_pct and margin_pct > 15.0:
        highlights.append(f"Strong overall profit margin of {margin_pct}%.")
    if top_bottom and "top_n" in top_bottom:
        top_cat = list(top_bottom["top_n"].keys())[0] if top_bottom["top_n"] else "N/A"
        highlights.append(f"Category '{top_cat}' is the highest revenue/value driver.")
    if top_corr:
        c_item = top_corr[0]
        highlights.append(f"Strong correlation found between '{c_item.get('col1')}' and '{c_item.get('col2')}' (r = {c_item.get('correlation')}).")
    if not highlights:
        highlights.append("Dataset structure is intact and ready for deeper segment profiling.")

    # 3. Anomalies & Risks
    risks = []
    total_outliers = sum(outliers.values()) if isinstance(outliers, dict) else 0
    if total_outliers > 0:
        risks.append(f"Detected {total_outliers} numerical outliers across measure columns.")
    if quality_score < 70:
        risks.append(f"Data quality is low ({quality_score}/100) due to missing or duplicate entries.")
    if margin_pct and margin_pct < 5.0:
        risks.append(f"Low profit margin detected ({margin_pct}%). Review discount strategies.")
    if not risks:
        risks.append("No critical anomalies or severe risk patterns detected.")

    # 4. Strategic Recommendations
    recommendations = []
    if total_outliers > 0:
        recommendations.append("Apply IQR capping or Isolation Forest cleaning to normalize extreme measure values.")
    if top_bottom and "bottom_n" in top_bottom:
        bot_cat = list(top_bottom["bottom_n"].keys())[0] if top_bottom["bottom_n"] else "N/A"
        recommendations.append(f"Evaluate low-performing category '{bot_cat}' for pricing optimization or phase-out.")
    recommendations.append("Generate automated feature columns (Year, Month, Quarter, Profit Margin) to power predictive dashboards.")
    recommendations.append("Export the full EDA report (PDF/Excel) for business stakeholder review.")

    return {
        "executive_summary": exec_summary,
        "positive_highlights": highlights,
        "anomalies_and_risks": risks,
        "strategic_recommendations": recommendations
    }


def generate_rule_based_insights(analytics_summary, language="en"):
    """
    Generates rule-based business insights and recommendations in English, Hindi, or Marathi.
    """
    domain = analytics_summary.get("domain", "General Analytics")
    row_count = analytics_summary.get("row_count", 0)
    quality_score = analytics_summary.get("quality_score", 100.0)
    grade = analytics_summary.get("grade", "A+")
    biz_kpis = analytics_summary.get("business_kpis", {})
    top_bottom = analytics_summary.get("top_bottom_analysis", {})
    outliers = analytics_summary.get("outliers_detected", {})
    top_corr = analytics_summary.get("top_correlations", [])

    total_sales = biz_kpis.get("total_sales")
    total_profit = biz_kpis.get("total_profit")
    margin_pct = biz_kpis.get("profit_margin_pct")

    if language == "hi":
        exec_summary = f"डेटासेट में '{domain}' डोमेन के तहत {row_count} रिकॉर्ड हैं। डेटा गुणवत्ता स्कोर {quality_score}/100 (ग्रेड {grade}) है।"
        if total_sales:
            exec_summary += f" कुल राजस्व ₹{total_sales:,.2f} है।"
        if total_profit:
            exec_summary += f" कुल लाभ ₹{total_profit:,.2f} (मार्जिन: {margin_pct}%) प्राप्त हुआ।"

        highlights = [f"डेटा गुणवत्ता रेटिंग उच्च ({quality_score}/100) है।"]
        outlier_count_val = sum(outliers.values()) if isinstance(outliers, dict) else 0
        risks = [f"{outlier_count_val} संख्यात्मक आउटलायर्स का पता चला।"] if outlier_count_val > 0 else ["कोई गंभीर जोखिम नहीं पाया गया।"]
        recommendations = ["भविष्य के रुझानों का विश्लेषण करने के लिए समय-श्रृंखला और ML पूर्वानुमान मॉडल का उपयोग करें।"]

    elif language == "mr":
        exec_summary = f"डेटासेटमध्ये '{domain}' क्षेत्राअंतर्गत {row_count} नोंदी आढळल्या आहेत. डेटा गुणवत्ता गुण {quality_score}/100 (श्रेणी {grade}) आहे."
        if total_sales:
            exec_summary += f" एकूण महसूल ₹{total_sales:,.2f} आहे."
        if total_profit:
            exec_summary += f" एकूण नफा ₹{total_profit:,.2f} (मार्जिन: {margin_pct}%) मिळाला."

        highlights = [f"उत्कृष्ट डेटा गुणवत्ता गुण {quality_score}/100 आहे."]
        risks = ["डेटासेट विश्लेषण प्रक्रियेत कोणतेही गंभीर धोके आढळले नाहीत."]
        recommendations = ["उत्पादक निर्णय घेण्यासाठी स्वयंचलित अंदाज आणि अहवाल वापरा."]

    else:
        exec_summary = f"The dataset contains {row_count} records evaluated under the '{domain}' domain with a Data Quality Score of {quality_score}/100 (Grade {grade})."
        if total_sales:
            exec_summary += f" Total Revenue is ₹{total_sales:,.2f}."
        if total_profit:
            exec_summary += f" Total Profit generated is ₹{total_profit:,.2f} (Margin: {margin_pct}%)."

        highlights = []
        if quality_score >= 80:
            highlights.append(f"High data quality rating of {quality_score}/100 ({grade} Grade).")
        if margin_pct and margin_pct > 15.0:
            highlights.append(f"Strong overall profit margin of {margin_pct}%.")
        if top_bottom and "top_n" in top_bottom:
            top_cat = list(top_bottom["top_n"].keys())[0] if top_bottom["top_n"] else "N/A"
            highlights.append(f"Category '{top_cat}' is the highest revenue/value driver.")
        if not highlights:
            highlights.append("Dataset structure is intact and ready for deeper segment profiling.")

        risks = []
        total_outliers = sum(outliers.values()) if isinstance(outliers, dict) else 0
        if total_outliers > 0:
            risks.append(f"Detected {total_outliers} numerical outliers across measure columns.")
        if not risks:
            risks.append("No critical anomalies or severe risk patterns detected.")

        recommendations = [
            "Apply IQR capping or Isolation Forest cleaning to normalize extreme measure values.",
            "Generate automated feature columns to power predictive dashboards.",
            "Export the full EDA report (PDF/Word/PPT/Excel) for business review."
        ]

    return {
        "executive_summary": exec_summary,
        "positive_highlights": highlights,
        "anomalies_and_risks": risks,
        "strategic_recommendations": recommendations
    }


def generate_ai_explanation(analytics_summary, language="en"):
    """
    Sends pre-calculated Python analytical facts to AI Engine for clear business explanation
    in the requested language ('en', 'hi', 'mr').
    """
    lang_instruction = "Respond in clear, professional English."
    if language == "hi":
        lang_instruction = "Respond completely in clear, natural Hindi (हिंदी भाषा)."
    elif language == "mr":
        lang_instruction = "Respond completely in clear, natural Marathi (मराठी भाषा)."

    prompt = f"""
You are an expert senior data analyst.
Language Requirement: {lang_instruction}

Pre-Calculated Analytics Data:
{json.dumps(analytics_summary, indent=2, default=str)}

Please provide a structured business interpretation covering:
1. Executive Summary & Overview
2. Key Positive Highlights
3. Anomaly & Risk Detection
4. Strategic Business Recommendations

Return your response as a valid JSON object with keys:
"executive_summary", "positive_highlights", "anomalies_and_risks", "strategic_recommendations".
"""

    try:
        ai_response = ai_helper.generate_ai_completion(prompt, expect_json=True)
        logger.info(f"AI explanation generated in language: {language}")
        return {
            "success": True,
            "mode": "ai",
            "language": language,
            "explanation": ai_response
        }
    except Exception as e:
        logger.warning(f"Error calling AI Service: {e}. Falling back to rule-based engine.")
        return {
            "success": True,
            "mode": "rule_based_fallback",
            "language": language,
            "message": f"AI service fallback executed for language '{language}'.",
            "explanation": generate_rule_based_insights(analytics_summary, language=language)
        }