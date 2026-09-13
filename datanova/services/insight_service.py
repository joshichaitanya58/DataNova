import os
import json
import logging
from typing import Dict, Any, List
from . import ai_helper

logger = logging.getLogger(__name__)


def _extract_outlier_count(outliers) -> int:
    if isinstance(outliers, int):
        return outliers
    if isinstance(outliers, dict):
        if "summary" in outliers and isinstance(outliers["summary"], dict):
            return int(outliers["summary"].get("total_unique_outliers", 0))
        if "by_column" in outliers and isinstance(outliers["by_column"], dict):
            total = 0
            for v in outliers["by_column"].values():
                if isinstance(v, dict):
                    total += int(v.get("count", 0))
                elif isinstance(v, (int, float)):
                    total += int(v)
            return total
        total = 0
        for v in outliers.values():
            if isinstance(v, (int, float)):
                total += int(v)
            elif isinstance(v, dict):
                total += int(v.get("count", 0))
        return total
    return 0


def generate_automl_recommendations(analytics_summary: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Analyzes dataset metadata and generates automated Machine Learning & statistical model recommendations.
    """
    recommendations = []
    numeric_summary = analytics_summary.get("numeric_summary", {})
    semantic_types = analytics_summary.get("semantic_types", {})
    row_count = analytics_summary.get("row_count", 0)

    has_datetime = any(t == "datetime" for t in semantic_types.values())
    numeric_cols = [c for c, t in semantic_types.items() if t in ["measure", "currency", "percentage", "numeric"]]
    categorical_cols = [c for c, t in semantic_types.items() if t in ["categorical", "category"]]

    # 1. Time Series Forecasting Recommender
    if has_datetime and numeric_cols:
        primary_measure = numeric_cols[0]
        recommendations.append({
            "model_type": "Time Series Forecasting",
            "recommended_algorithms": "Prophet / ARIMA / Exponential Smoothing",
            "target": primary_measure,
            "objective": f"Forecast future growth trends and seasonality for '{primary_measure}'.",
            "confidence": "High"
        })

    # 2. Supervised Regression Recommender
    if len(numeric_cols) >= 2:
        target_measure = numeric_cols[0]
        features = numeric_cols[1:5]
        recommendations.append({
            "model_type": "Predictive Regression",
            "recommended_algorithms": "Random Forest Regressor / XGBoost / Ridge Regression",
            "target": target_measure,
            "objective": f"Predict '{target_measure}' based on features ({', '.join(features)}).",
            "confidence": "Very High" if row_count >= 50 else "Moderate"
        })

    # 3. Customer / Entity Segmentation (Clustering)
    if len(numeric_cols) >= 3:
        recommendations.append({
            "model_type": "Unsupervised Clustering",
            "recommended_algorithms": "K-Means / HDBSCAN / Gaussian Mixture",
            "target": "N/A (Unsupervised)",
            "objective": "Segment high-value clusters, customer cohorts, and performance tiers.",
            "confidence": "High"
        })

    # 4. Classification Recommender
    if categorical_cols and numeric_cols:
        cat_target = categorical_cols[0]
        recommendations.append({
            "model_type": "Classification & Churn/Risk Modeling",
            "recommended_algorithms": "LightGBM / Random Forest / Logistic Regression",
            "target": cat_target,
            "objective": f"Classify and predict '{cat_target}' categories automatically.",
            "confidence": "High"
        })

    return recommendations


def generate_rule_based_insights(analytics_summary: Dict[str, Any], language: str = "en") -> Dict[str, Any]:
    """
    Generates rich, prescriptive business insights, Pareto risk analysis, and actionable next steps.
    """
    domain = analytics_summary.get("domain", "General Analytics")
    row_count = analytics_summary.get("row_count", 0)
    col_count = analytics_summary.get("column_count", 0)
    quality_score = analytics_summary.get("quality_score", 100.0)
    grade = analytics_summary.get("grade", "A+")
    biz_kpis = analytics_summary.get("business_kpis", {})
    top_bottom = analytics_summary.get("top_bottom_analysis", {})
    outliers = analytics_summary.get("outliers_detected", {})
    top_corr = analytics_summary.get("top_correlations", [])
    ml_recs = generate_automl_recommendations(analytics_summary)

    total_sales = biz_kpis.get("total_sales")
    total_profit = biz_kpis.get("total_profit")
    margin_pct = biz_kpis.get("profit_margin_pct")
    total_outliers = _extract_outlier_count(outliers)

    if language == "hi":
        exec_summary = (
            f"डेटासेट में '{domain}' डोमेन के तहत कुल {row_count:,} रिकॉर्ड्स और {col_count} कॉलम्स शामिल हैं। "
            f"डेटा हेल्थ और क्वालिटी स्कोर {quality_score}/100 (ग्रेड {grade}) है।"
        )
        if total_sales:
            exec_summary += f" कुल दर्ज राजस्व ₹{total_sales:,.2f} है।"
        if total_profit:
            exec_summary += f" कुल दर्ज लाभ ₹{total_profit:,.2f} (लाभ मार्जिन: {margin_pct}%) रहा।"

        highlights = []
        if quality_score >= 80:
            highlights.append(f"डेटा स्वच्छता और गुणवत्ता रेटिंग उत्कृष्ट ({quality_score}/100) है।")
        if margin_pct and margin_pct > 15.0:
            highlights.append(f"मजबूत लाभप्रदता मार्जिन ({margin_pct}%) दर्ज किया गया है।")
        if top_bottom and "top_n" in top_bottom:
            top_cat = list(top_bottom["top_n"].keys())[0] if top_bottom["top_n"] else "N/A"
            highlights.append(f"शीर्ष श्रेणी '{top_cat}' सबसे बड़ा रेवेन्यू ड्राइवर सिद्ध हुआ।")
        if not highlights:
            highlights.append("डेटा संरचना सुसंगत है और त्वरित निर्णय लेने के लिए तैयार है।")

        risks = []
        if total_outliers > 0:
            risks.append(f"{total_outliers:,} सांख्यिकीय आउटलायर्स का पता चला है, जिन्हें कैपिंग/क्लीनिंग की आवश्यकता है।")
        if quality_score < 75:
            risks.append("मिसिंग वैल्यूज या इनकंसिस्टेंसी के कारण डेटा गुणवत्ता स्कोर कम है।")
        if not risks:
            risks.append("डेटासेट में कोई गंभीर असामान्यता या गंभीर जोखिम पैटर्न नहीं पाया गया।")

        recommendations = [
            "Pareto 80/20 सिद्धांत लागू करके शीर्ष 20% राजस्व प्रदाताओं पर रणनीतिक फोकस बढ़ाएं।",
            "संभावित जोखिम और अप्रत्याशित उतार-चढ़ाव रोकने के लिए आउटलायर नॉर्मलाइजेशन लागू करें।",
            "भविष्य के सटीक पूर्वानुमानों के लिए ऑटोमेटेड ML मॉडल्स (XGBoost / Time Series) को सक्रिय करें।"
        ]

    elif language == "mr":
        exec_summary = (
            f"डेटासेटमध्ये '{domain}' क्षेत्राअंतर्गत एकूण {row_count:,} नोंदी व {col_count} स्तंभ आढळले आहेत. "
            f"डेटा गुणवत्ता गुण {quality_score}/100 (श्रेणी {grade}) आहे."
        )
        if total_sales:
            exec_summary += f" एकूण महसूल ₹{total_sales:,.2f} नोंदवला गेला."
        if total_profit:
            exec_summary += f" एकूण नफा ₹{total_profit:,.2f} (नफा मार्जिन: {margin_pct}%) मिळाला."

        highlights = [f"डेटा गुणवत्ता गुण {quality_score}/100 (ग्रेड {grade}) सह उच्च दर्जाचा आहे."]
        risks = [f"{total_outliers:,} सांख्यिकीय आउटलायर्स आढळले आहेत."] if total_outliers > 0 else ["डेटासेटमध्ये कोणतेही गंभीर धोके आढळले नाहीत."]
        recommendations = [
            "८०/२० पारेटो नियमानुसार सर्वाधिक उत्पन्न देणाऱ्या घटकांवर विशेष लक्ष केंद्रित करा.",
            "अचूक व्यवसाय अंदाजासाठी स्वयंचलित टाइम-सिरीज व एमएल मॉडेल्स वापरा.",
            "कार्यकारी मंडळासाठी सर्वसमावेशक विश्लेषणात्मक अहवाल निर्यात करा."
        ]

    else:
        exec_summary = (
            f"The dataset encapsulates {row_count:,} records across {col_count} attributes within the '{domain}' domain, "
            f"maintaining a Data Quality Index of {quality_score}/100 (Grade {grade})."
        )
        if total_sales:
            exec_summary += f" Aggregate Revenue is ₹{total_sales:,.2f}."
        if total_profit:
            exec_summary += f" Total Profit stands at ₹{total_profit:,.2f} with an operating margin of {margin_pct}%."

        highlights = []
        if quality_score >= 80:
            highlights.append(f"Exceptional data reliability with a Quality Score of {quality_score}/100 ({grade} Grade).")
        if margin_pct and margin_pct > 15.0:
            highlights.append(f"Robust operational profit margin of {margin_pct}%.")
        if top_bottom and "top_n" in top_bottom:
            top_cat = list(top_bottom["top_n"].keys())[0] if top_bottom["top_n"] else "N/A"
            highlights.append(f"Dominant segment '{top_cat}' is the primary value & volume generator.")
        if top_corr:
            strongest = top_corr[0]
            highlights.append(f"Strong correlation ({strongest.get('correlation')}) discovered between '{strongest.get('col1')}' and '{strongest.get('col2')}'.")
        if not highlights:
            highlights.append("Dataset structure is intact and optimized for multidimensional intelligence extraction.")

        risks = []
        if total_outliers > 0:
            risks.append(f"Detected {total_outliers:,} numerical anomalies/outliers that may distort mean indicators.")
        if quality_score < 75:
            risks.append("Sub-optimal data hygiene detected due to missing attributes or text inconsistencies.")
        if not risks:
            risks.append("Zero critical structural risks or disruptive variance anomalies detected.")

        recommendations = [
            "Leverage Pareto 80/20 optimization: allocate 80% of retention efforts to the top 20% revenue-generating contributors.",
            "Apply IQR capping or Isolation Forest cleaning to normalize high-leverage numeric outliers.",
            "Deploy recommended predictive ML pipelines (Random Forest / XGBoost / Time Series) for forward-looking demand forecasting.",
            "Export the multi-dimensional analytical executive summary (PDF/Word/PPT/Excel) for stakeholder review."
        ]

    return {
        "executive_summary": exec_summary,
        "positive_highlights": highlights,
        "anomalies_and_risks": risks,
        "strategic_recommendations": recommendations,
        "automl_recommendations": ml_recs
    }


def generate_ai_explanation(analytics_summary: Dict[str, Any], language: str = "en") -> Dict[str, Any]:
    """
    Sends pre-calculated analytical facts to the AI Engine and returns
    a professional, executive-ready explanation in the requested language.
    """
    language_guidance = {
        "en": "Respond entirely in clear, natural, professional English like a Principal Data Scientist advising an Executive.",
        "hi": "पूरा उत्तर सरल, स्वाभाविक और प्रभावशाली व्यावसायिक हिंदी में दें जैसे एक सीनियर एनालिस्ट बिज़नेस लीडर को समझा रहा हो।",
        "mr": "संपूर्ण उत्तर सोप्या, अस्खलित आणि व्यावसायिक मराठीत द्या जणू एक वरिष्ठ डेटा सायंटिस्ट व्यवस्थापनाला मार्गदर्शन करत आहे."
    }
    lang_instruction = language_guidance.get(language, language_guidance["en"])

    prompt = f"""
You are a Principal Data Scientist and Executive Business Advisor.
Your job is to translate the raw analytical data below into clear, persuasive, strategic executive insights.

LANGUAGE REQUIREMENTS:
{lang_instruction}

TONE & STYLE:
- Authoritative, professional, concise, and focused on business value creation.
- Avoid technical jargon (translate p-values and distributions into concrete business outcomes).
- Highlight key revenue drivers, risk areas, and actionable prescriptive decisions.

RAW ANALYTICS DATA:
{json.dumps(analytics_summary, indent=2, default=str)}

Provide four concise, high-impact sections:
1. "executive_summary": Clear high-level takeaway with core volume and revenue impact.
2. "positive_highlights": What is working exceptionally well and driving value.
3. "anomalies_and_risks": What operational or statistical risks need immediate mitigation.
4. "strategic_recommendations": 3 concrete, prioritized business action items.

OUTPUT FORMAT:
Return ONLY a valid JSON object with the exact keys above.
"""

    try:
        ai_response = ai_helper.generate_ai_completion(prompt, expect_json=True)
        logger.info(f"AI strategic explanation generated in language: {language}")
        return {
            "success": True,
            "mode": "ai",
            "language": language,
            "explanation": ai_response,
        }
    except Exception as e:
        logger.warning(f"Error calling AI Service: {e}. Falling back to rule-based intelligence engine.")
        return {
            "success": True,
            "mode": "rule_based_fallback",
            "language": language,
            "message": f"Rule-based intelligence engine executed for language '{language}'.",
            "explanation": generate_rule_based_insights(analytics_summary, language=language),
        }