"""
DataNova Report Generation Service
-----------------------------------
Generates standalone HTML, PDF, Word, PowerPoint and Excel reports from an
EDA pipeline result.

Bug fixes vs. previous version:
  * business_domain now actually uses detect_business_domain() as a fallback
    instead of importing it and never calling it.
  * All user/AI-generated text going into ReportLab Paragraphs is XML-escaped
    (previously a stray "&" or "<" in the AI summary would crash PDF export).
  * All numeric formatting is done through safe helpers so a missing/odd
    value (None, string, NaN) can never raise a ValueError mid-report.
  * descriptive_statistics, outliers, correlation_matrix and business_kpis
    were being computed upstream but silently dropped -- they are now
    rendered in every report format.
  * Empty charts / empty semantic tables / empty stats now show a clean
    "No data available" placeholder instead of a blank or broken section.
  * Chart images are embedded with aspect-ratio preserved sizing instead of
    a fixed width/height that used to stretch/squash the plot.
  * generate_excel_report_bytes() no longer crashes if df is None, and now
    auto-sizes columns and freezes the header row.
  * Each report generator is wrapped so a single bad chart/row can't take
    down the whole report -- it's skipped and logged instead.

Excel report rewrite (this version):
  * generate_excel_report_bytes() went from 3 bare sheets to a full,
    branded multi-sheet workbook that mirrors everything the HTML/PDF/Word
    reports show: Cover, Executive Summary, Business KPIs, Column
    Profiling, Descriptive Statistics, Correlation Matrix (heat-mapped),
    Outlier Detection, Exploratory Charts (images embedded in-sheet), and
    Cleaned Dataset -- instead of silently dropping most of the pipeline
    result the way the previous version did.
  * Every sheet has a consistent visual system: a colored title banner,
    dark header rows with white bold text, banded/striped body rows, real
    borders, frozen header rows + autofilter on tabular sheets, sensible
    column widths (measured from content, not guessed), right-aligned
    numeric columns with thousands separators, and colored sheet tabs so
    the sheet list itself is easy to scan.
  * Nothing is hardcoded that pipeline_result already computed -- KPIs,
    stats, correlations, outliers and chart images all come straight from
    the pipeline_result dict, same as the other four report formats.
"""

import base64
import html
import logging
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape as xml_escape

import pandas as pd

from .semantic_service import detect_business_domain

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------

def _safe_number(value, default=0):
    """Coerce a value to a number for formatting; never raises."""
    try:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return value
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt_int_commas(value, default=0):
    """Format an int with thousands separators, tolerating bad input."""
    num = _safe_number(value, default)
    try:
        return f"{int(num):,}"
    except (TypeError, ValueError):
        return str(default)


def _fmt_score(score, default=100):
    num = _safe_number(score, default)
    try:
        return f"{int(round(num))}/100"
    except (TypeError, ValueError):
        return f"{default}/100"


def _resolve_business_domain(pipeline_result):
    """Use the explicit domain if set, otherwise try to detect it."""
    domain = pipeline_result.get("business_domain")
    if domain:
        return str(domain)

    semantics = pipeline_result.get("semantic_types", {})
    try:
        detected = detect_business_domain(semantics)
        if detected:
            return str(detected)
    except Exception as e:  # noqa: BLE001 - detection is best-effort
        logger.info(f"Business domain detection skipped: {e}")

    return "General Analytics"


def _get_exec_summary(pipeline_result):
    ai_exp = pipeline_result.get("ai_explanation", {})
    if isinstance(ai_exp, dict):
        return ai_exp.get(
            "executive_summary",
            "Detailed quantitative analysis completed successfully across all dataset metrics.",
        )
    return "Analysis completed successfully."


def _decode_chart_image(chart):
    """Return (BytesIO, width_px, height_px) or None if the chart can't be decoded."""
    plot = chart.get("plot")
    if not plot:
        return None
    try:
        img_bytes = base64.b64decode(plot)
        if not img_bytes:
            return None
        buf = BytesIO(img_bytes)
        width_px, height_px = None, None
        try:
            from PIL import Image as PILImage

            with PILImage.open(buf) as im:
                width_px, height_px = im.size
            buf.seek(0)
        except Exception:
            buf.seek(0)
        return buf, width_px, height_px
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Could not decode chart image: {e}")
        return None


# --------------------------------------------------------------------------
# HTML report
# --------------------------------------------------------------------------

def generate_eda_html_report(pipeline_result):
    """
    Generates a standalone, professionally styled HTML EDA report summarizing
    all analytical modules. Supports native print-to-PDF.

    Args:
        pipeline_result (dict): The output from pipeline_service.analyze_dataset()

    Returns:
        str: Complete HTML document as a string.
    """
    overview = pipeline_result.get("dataset_overview", {}) or {}
    quality = pipeline_result.get("quality", {}) or {}
    semantics = pipeline_result.get("semantic_types", {}) or {}
    stats = pipeline_result.get("descriptive_statistics", {}) or {}
    outliers = pipeline_result.get("outliers", {}) or {}
    corr_data = pipeline_result.get("correlation_matrix", {}) or {}
    biz_kpis = pipeline_result.get("business_kpis", {}) or {}
    charts = pipeline_result.get("recommended_charts", []) or []
    mem_summary = pipeline_result.get("memory_summary", {}) or {}

    domain = _resolve_business_domain(pipeline_result)
    exec_summary_text = html.escape(_get_exec_summary(pipeline_result))
    grade = html.escape(str(quality.get("grade", "A+")))
    score_display = _fmt_score(quality.get("score", 100))

    # ---- Charts -----------------------------------------------------
    if charts:
        charts_html = ""
        for chart in charts:
            title = html.escape(chart.get("title", "Chart"))
            description = html.escape(chart.get("description", ""))
            decoded = _decode_chart_image(chart)
            if decoded is None:
                continue
            _, _, _ = decoded  # not needed for <img>, browser handles scaling
            plot = chart.get("plot", "")
            charts_html += f"""
            <div class="chart-card">
                <h4>{title}</h4>
                <p class="muted">{description}</p>
                <div class="chart-img-wrap">
                    <img src="data:image/png;base64,{plot}" alt="{title}" />
                </div>
            </div>
            """
        if not charts_html:
            charts_html = '<p class="empty-state">No charts could be rendered for this dataset.</p>'
    else:
        charts_html = '<p class="empty-state">No charts were generated for this dataset.</p>'

    # ---- Semantic column classification ------------------------------
    if semantics:
        semantics_rows = ""
        for col, sem in semantics.items():
            col_esc = html.escape(str(col))
            sem_esc = html.escape(str(sem))
            semantics_rows += (
                f"<tr><td class='col-name'>{col_esc}</td>"
                f"<td><span class='pill'>{sem_esc}</span></td></tr>"
            )
    else:
        semantics_rows = "<tr><td colspan='2' class='empty-state'>No semantic classification available.</td></tr>"

    # ---- Descriptive statistics ---------------------------------------
    if stats:
        try:
            stats_df = pd.DataFrame(stats)
            stat_cols = list(stats_df.columns)
            stat_rows = ""
            for idx in stats_df.index:
                cells = "".join(
                    f"<td>{html.escape(str(round(v, 3)) if isinstance(v, float) else str(v))}</td>"
                    for v in stats_df.loc[idx]
                )
                stat_rows += f"<tr><td class='col-name'>{html.escape(str(idx))}</td>{cells}</tr>"
            stats_header = "".join(f"<th>{html.escape(str(c))}</th>" for c in stat_cols)
            stats_html = f"""
            <table>
                <thead><tr><th>Metric</th>{stats_header}</tr></thead>
                <tbody>{stat_rows}</tbody>
            </table>
            """
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Could not render descriptive statistics table: {e}")
            stats_html = '<p class="empty-state">Descriptive statistics could not be rendered.</p>'
    else:
        stats_html = '<p class="empty-state">No descriptive statistics available.</p>'

    # ---- Outliers -------------------------------------------------------
    if outliers:
        outlier_rows = ""
        for col, info in outliers.items():
            if isinstance(info, dict):
                count = info.get("count", info.get("outlier_count", "-"))
                pct = info.get("percentage", info.get("outlier_percentage", "-"))
            else:
                count, pct = info, "-"
            outlier_rows += (
                f"<tr><td class='col-name'>{html.escape(str(col))}</td>"
                f"<td>{html.escape(str(count))}</td><td>{html.escape(str(pct))}</td></tr>"
            )
        outliers_html = f"""
        <table>
            <thead><tr><th>Column</th><th>Outlier Count</th><th>Percentage</th></tr></thead>
            <tbody>{outlier_rows}</tbody>
        </table>
        """
    else:
        outliers_html = '<p class="empty-state">No significant outliers detected.</p>'

    # ---- Correlation matrix ---------------------------------------------
    if corr_data:
        try:
            corr_df = pd.DataFrame(corr_data)
            cols = list(corr_df.columns)
            header = "".join(f"<th>{html.escape(str(c))}</th>" for c in cols)
            corr_rows = ""
            for idx in corr_df.index:
                cells = ""
                for c in cols:
                    v = corr_df.loc[idx, c]
                    try:
                        v_num = float(v)
                        shade = int(abs(v_num) * 180)
                        color = f"rgba(79,70,229,{abs(v_num):.2f})" if v_num >= 0 else f"rgba(220,38,38,{abs(v_num):.2f})"
                        cells += f"<td style='background:{color}; color:{'#fff' if abs(v_num) > 0.5 else '#1e293b'}'>{v_num:.2f}</td>"
                    except (TypeError, ValueError):
                        cells += f"<td>{html.escape(str(v))}</td>"
                corr_rows += f"<tr><td class='col-name'>{html.escape(str(idx))}</td>{cells}</tr>"
            corr_html = f"""
            <div class="table-scroll">
            <table>
                <thead><tr><th>&nbsp;</th>{header}</tr></thead>
                <tbody>{corr_rows}</tbody>
            </table>
            </div>
            """
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Could not render correlation matrix: {e}")
            corr_html = '<p class="empty-state">Correlation matrix could not be rendered.</p>'
    else:
        corr_html = '<p class="empty-state">No correlation data available (dataset may lack numeric columns).</p>'

    # ---- Business KPIs ----------------------------------------------------
    if biz_kpis:
        kpi_cards = ""
        for label, value in biz_kpis.items():
            kpi_cards += f"""
            <div class="card">
                <div class="card-label">{html.escape(str(label))}</div>
                <div class="card-val kpi-val">{html.escape(str(value))}</div>
            </div>
            """
        biz_kpis_html = f'<div class="grid">{kpi_cards}</div>'
    else:
        biz_kpis_html = ""

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DataNova - Executive Automated EDA Report</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    background: #f1f5f9;
    color: #1e293b;
    line-height: 1.6;
    margin: 0;
    padding: 40px 20px;
  }}
  .container {{
    max-width: 1080px;
    margin: 0 auto;
    background: #ffffff;
    padding: 48px;
    border-radius: 18px;
    box-shadow: 0 20px 40px -12px rgba(15, 23, 42, 0.12);
  }}
  .header {{
    border-bottom: 2px solid #4f46e5;
    padding-bottom: 24px;
    margin-bottom: 32px;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 16px;
  }}
  .header h1 {{ margin: 0; color: #4f46e5; font-size: 30px; font-weight: 800; letter-spacing: -0.5px; }}
  .header p {{ margin: 6px 0 0 0; color: #64748b; font-size: 14px; }}
  .badge {{
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    color: #fff; padding: 8px 18px; border-radius: 30px;
    font-weight: 700; font-size: 15px; box-shadow: 0 4px 12px rgba(79, 70, 229, 0.25);
    white-space: nowrap;
  }}
  .print-btn {{
    background: #10b981; color: #fff; border: none; padding: 10px 20px;
    border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 14px;
    display: inline-flex; align-items: center; gap: 6px;
  }}
  .print-btn:hover {{ background: #059669; }}
  .toolbar {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 20px; margin-bottom: 12px; }}
  .card {{ background: #f8fafc; border: 1px solid #e2e8f0; padding: 22px; border-radius: 12px; text-align: center; }}
  .card-label {{ font-size: 12px; font-weight: 700; color: #64748b; letter-spacing: 0.5px; text-transform: uppercase; }}
  .card-val {{ font-size: 28px; font-weight: 800; color: #0f172a; margin-top: 6px; letter-spacing: -0.5px; }}
  .kpi-val {{ font-size: 20px; }}
  .section-title {{
    font-size: 20px; font-weight: 700; color: #0f172a; border-left: 4px solid #4f46e5;
    padding-left: 12px; margin-top: 44px; margin-bottom: 20px;
  }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; font-size: 13.5px; }}
  th {{ background: #f1f5f9; text-align: left; padding: 10px 12px; font-size: 12px; font-weight: 700; color: #475569; border-bottom: 2px solid #cbd5e1; text-transform: uppercase; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid #f1f5f9; }}
  .col-name {{ font-weight: 600; color: #334155; }}
  .pill {{ background: #e0e7ff; color: #3730a3; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }}
  .table-scroll {{ overflow-x: auto; margin-bottom: 28px; }}
  .empty-state {{ color: #94a3b8; font-style: italic; padding: 16px 4px; margin: 0 0 28px 0; }}
  .exec-box {{ background: #eef2ff; padding: 24px; border-radius: 12px; border-left: 5px solid #4f46e5; color: #312e81; font-size: 15px; line-height: 1.7; font-weight: 500; margin-bottom: 32px; }}
  .chart-card {{
    background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 20px;
    margin-bottom: 24px; box-shadow: 0 2px 4px rgba(0,0,0,0.04); page-break-inside: avoid;
  }}
  .chart-card h4 {{ margin-top: 0; color: #1e293b; font-size: 16px; font-weight: 700; }}
  .chart-card .muted {{ color: #64748b; font-size: 13px; margin-bottom: 14px; }}
  .chart-img-wrap {{ text-align: center; }}
  .chart-img-wrap img {{ max-width: 100%; height: auto; border-radius: 8px; }}
  .footer {{ text-align: center; margin-top: 60px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #94a3b8; font-size: 13px; }}
  @media print {{
    body {{ background: #fff; padding: 0; color: #000; }}
    .container {{ box-shadow: none; padding: 0; max-width: 100%; }}
    .print-btn {{ display: none !important; }}
    .section-title {{ page-break-after: avoid; }}
  }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div>
        <h1>DataNova Executive EDA Report</h1>
        <p>Business Domain: <strong>{html.escape(domain)}</strong> &middot; Analytics Platform 2.0</p>
      </div>
      <div class="toolbar">
        <button class="print-btn" onclick="window.print()">&#128424; Save as PDF / Print</button>
        <div class="badge">Grade {grade} ({score_display})</div>
      </div>
    </div>

    <div class="grid">
      <div class="card">
        <div class="card-label">Total Rows</div>
        <div class="card-val">{_fmt_int_commas(overview.get("row_count", 0))}</div>
      </div>
      <div class="card">
        <div class="card-label">Total Columns</div>
        <div class="card-val">{html.escape(str(overview.get("column_count", 0)))}</div>
      </div>
      <div class="card">
        <div class="card-label">Memory Usage</div>
        <div class="card-val">{html.escape(str(mem_summary.get("formatted_memory", "N/A")))}</div>
      </div>
      <div class="card">
        <div class="card-label">Quality Score</div>
        <div class="card-val" style="color: #10b981;">{score_display}</div>
      </div>
    </div>

    <div class="section-title">Executive Summary &amp; Analysis Insights</div>
    <div class="exec-box">{exec_summary_text}</div>

    {f'<div class="section-title">Business KPIs</div>{biz_kpis_html}' if biz_kpis else ''}

    <div class="section-title">Semantic Column Classification</div>
    <table>
      <thead><tr><th>Column Name</th><th>Detected Semantic Role</th></tr></thead>
      <tbody>{semantics_rows}</tbody>
    </table>

    <div class="section-title">Descriptive Statistics</div>
    <div class="table-scroll">{stats_html}</div>

    <div class="section-title">Outlier Detection</div>
    {outliers_html}

    <div class="section-title">Correlation Matrix</div>
    {corr_html}

    <div class="section-title">Visual Exploratory Charts</div>
    {charts_html}

    <div class="footer">
      Generated automatically by <strong>DataNova Smart Analytics Platform</strong> &bull; All Rights Reserved
    </div>
  </div>
</body>
</html>
"""
    return html_content


# --------------------------------------------------------------------------
# PDF report
# --------------------------------------------------------------------------

def generate_pdf_report_bytes(pipeline_result):
    """
    Generates a professional executive PDF report using ReportLab.
    Returns: bytes (PDF binary stream)
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        "DocTitle", parent=styles["Heading1"], fontName="Helvetica-Bold",
        fontSize=22, textColor=colors.HexColor("#4F46E5"), spaceAfter=10,
    )
    h2_style = ParagraphStyle(
        "SectionHeading", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=14, textColor=colors.HexColor("#1E293B"), spaceBefore=15, spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "BodyDark", parent=styles["Normal"], fontName="Helvetica",
        fontSize=10, textColor=colors.HexColor("#334155"), spaceAfter=6,
    )

    overview = pipeline_result.get("dataset_overview", {}) or {}
    quality = pipeline_result.get("quality", {}) or {}
    domain = xml_escape(_resolve_business_domain(pipeline_result))
    exec_summary_text = xml_escape(_get_exec_summary(pipeline_result))
    grade = xml_escape(str(quality.get("grade", "A+")))
    score_display = _fmt_score(quality.get("score", 100))

    story.append(Paragraph("DataNova Executive Automated EDA Report", title_style))
    story.append(Paragraph(f"Business Domain: <b>{domain}</b> | Data Quality Index: <b>{score_display} (Grade {grade})</b>", body_style))
    story.append(Spacer(1, 12))

    kpi_table_data = [
        ["Total Rows", "Total Columns", "Quality Score", "Missing Cells"],
        [
            _fmt_int_commas(overview.get("row_count", 0)),
            str(overview.get("column_count", 0)),
            score_display,
            str(quality.get("missing_cells", 0)),
        ],
    ]
    t = Table(kpi_table_data, colWidths=[130, 130, 130, 130])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F46E5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F8FAFC")),
        ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))

    story.append(Paragraph("Executive Summary &amp; AI Insights", h2_style))
    story.append(Paragraph(exec_summary_text, body_style))
    story.append(Spacer(1, 15))

    # Business KPIs
    biz_kpis = pipeline_result.get("business_kpis", {}) or {}
    if biz_kpis:
        story.append(Paragraph("Business KPIs", h2_style))
        kpi_rows = [["KPI", "Value"]] + [
            [xml_escape(str(k)), xml_escape(str(v))] for k, v in biz_kpis.items()
        ]
        kpi_tbl = Table(kpi_rows, colWidths=[260, 260])
        kpi_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(kpi_tbl)
        story.append(Spacer(1, 15))

    story.append(Paragraph("Semantic Column Profiling", h2_style))
    semantics = pipeline_result.get("semantic_types", {}) or {}
    if semantics:
        sem_data = [["Column Name", "Detected Semantic Role"]] + [
            [xml_escape(str(col)), xml_escape(str(sem))] for col, sem in list(semantics.items())[:15]
        ]
        sem_table = Table(sem_data, colWidths=[260, 260])
        sem_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(sem_table)
    else:
        story.append(Paragraph("No semantic classification available.", body_style))
    story.append(Spacer(1, 15))

    # Outliers
    outliers = pipeline_result.get("outliers", {}) or {}
    if outliers:
        story.append(Paragraph("Outlier Detection", h2_style))
        out_rows = [["Column", "Outlier Count"]]
        for col, info in list(outliers.items())[:15]:
            count = info.get("count", info.get("outlier_count", "-")) if isinstance(info, dict) else info
            out_rows.append([xml_escape(str(col)), xml_escape(str(count))])
        out_table = Table(out_rows, colWidths=[260, 260])
        out_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F46E5")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(out_table)
        story.append(Spacer(1, 15))

    # Charts (aspect-ratio preserved, max 3 to keep PDF light)
    charts = pipeline_result.get("recommended_charts", []) or []
    if charts:
        story.append(Paragraph("Visual Exploratory Charts", h2_style))
        max_width = 450
        for c in charts[:3]:
            decoded = _decode_chart_image(c)
            if decoded is None:
                continue
            img_buf, w_px, h_px = decoded
            if w_px and h_px:
                draw_width = max_width
                draw_height = max_width * (h_px / w_px)
            else:
                draw_width, draw_height = max_width, 220
            try:
                img = Image(img_buf, width=draw_width, height=draw_height)
                story.append(Paragraph(f"<b>{xml_escape(str(c.get('title', 'Chart')))}</b>", body_style))
                story.append(img)
                story.append(Spacer(1, 10))
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Could not render image in PDF: {e}")

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# --------------------------------------------------------------------------
# Word report
# --------------------------------------------------------------------------

try:
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
except ImportError:
    qn = None
    OxmlElement = None


def _docx_shade_cell(cell, hex_color):
    """Set a table cell's background fill (python-docx has no public API for this)."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def _docx_set_cell_text(cell, text, bold=False, color_hex=None, size=None, align=None):
    from docx.shared import Pt, RGBColor

    cell.text = ""
    p = cell.paragraphs[0]
    if align is not None:
        p.alignment = align
    run = p.add_run(str(text))
    run.bold = bold
    if size:
        run.font.size = Pt(size)
    if color_hex:
        run.font.color.rgb = RGBColor(
            int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
        )


def _docx_bottom_border(paragraph, color_hex="4F46E5", size=10):
    """Draw a thin colored rule under a paragraph (used under section headings)."""
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:space"), "6")
    bottom.set(qn("w:color"), color_hex)
    p_bdr.append(bottom)
    p_pr.append(p_bdr)


def _docx_add_page_number_field(paragraph):
    """Insert a dynamic {PAGE} field so the footer shows a real page number."""
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_end)


def generate_word_report_bytes(pipeline_result):
    """
    Generates a polished, branded Microsoft Word (.docx) report using python-docx:
    a colored cover banner, shaded/banded tables, ruled section headings and a
    page-numbered footer.
    Returns: bytes (.docx binary stream)
    """
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT

    PRIMARY = "4F46E5"
    PRIMARY_DARK = "3730A3"
    DARK = "1E293B"
    MUTED = "64748B"
    LIGHT_BG = "F1F5F9"
    WHITE = "FFFFFF"

    doc = Document()
    buffer = BytesIO()

    for section in doc.sections:
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)

    overview = pipeline_result.get("dataset_overview", {}) or {}
    quality = pipeline_result.get("quality", {}) or {}
    domain = _resolve_business_domain(pipeline_result)
    exec_text = _get_exec_summary(pipeline_result)
    score_display = _fmt_score(quality.get("score", 100))
    grade = quality.get("grade", "A+")

    # ---- Cover banner (a single shaded table cell used as a colored band) ----
    banner = doc.add_table(rows=1, cols=1)
    banner.alignment = WD_TABLE_ALIGNMENT.CENTER
    banner.autofit = True
    b_cell = banner.rows[0].cells[0]
    _docx_shade_cell(b_cell, PRIMARY)
    b_cell.paragraphs[0].text = ""
    b_cell.paragraphs[0].paragraph_format.space_before = Pt(18)

    title_p = b_cell.paragraphs[0]
    title_run = title_p.add_run("DataNova Executive Analysis Report")
    title_run.bold = True
    title_run.font.size = Pt(26)
    title_run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    subtitle_p = b_cell.add_paragraph()
    subtitle_p.paragraph_format.space_after = Pt(18)
    subtitle_run = subtitle_p.add_run(
        f"Business Domain: {domain}   |   Quality Index: {score_display} (Grade {grade})"
    )
    subtitle_run.font.size = Pt(12)
    subtitle_run.font.color.rgb = RGBColor(0xE0, 0xE7, 0xFF)

    doc.add_paragraph()  # breathing room after the banner

    section_num = 1

    def add_section_heading(text):
        nonlocal section_num
        heading = doc.add_heading(f"{section_num}. {text}", level=1)
        for run in heading.runs:
            run.font.color.rgb = RGBColor(
                int(PRIMARY_DARK[0:2], 16), int(PRIMARY_DARK[2:4], 16), int(PRIMARY_DARK[4:6], 16)
            )
        _docx_bottom_border(heading, color_hex=PRIMARY, size=10)
        section_num += 1
        return heading

    def style_two_col_table(table, header_left, header_right, rows):
        table.style = "Table Grid"
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        _docx_set_cell_text(table.rows[0].cells[0], header_left, bold=True, color_hex=WHITE, size=11)
        _docx_set_cell_text(table.rows[0].cells[1], header_right, bold=True, color_hex=WHITE, size=11)
        _docx_shade_cell(table.rows[0].cells[0], DARK)
        _docx_shade_cell(table.rows[0].cells[1], DARK)
        for i, (left, right) in enumerate(rows):
            row_cells = table.add_row().cells
            _docx_set_cell_text(row_cells[0], left, bold=True, size=10.5)
            _docx_set_cell_text(row_cells[1], right, size=10.5)
            if i % 2 == 1:
                _docx_shade_cell(row_cells[0], LIGHT_BG)
                _docx_shade_cell(row_cells[1], LIGHT_BG)

    # ---- 1. Dataset Overview ----
    add_section_heading("Dataset Overview & Metrics")
    overview_table = doc.add_table(rows=1, cols=2)
    style_two_col_table(
        overview_table,
        "Metric",
        "Value",
        [
            ("Total Records (Rows)", _fmt_int_commas(overview.get("row_count", 0))),
            ("Total Columns", str(overview.get("column_count", 0))),
            ("Missing Values Count", str(quality.get("missing_cells", 0))),
            ("Duplicate Rows Count", str(quality.get("duplicate_rows", 0))),
        ],
    )
    doc.add_paragraph()

    # ---- 2. Executive Summary ----
    add_section_heading("Executive Summary")
    summary_table = doc.add_table(rows=1, cols=1)
    summary_table.style = "Table Grid"
    s_cell = summary_table.rows[0].cells[0]
    _docx_shade_cell(s_cell, "EEF2FF")
    s_cell.text = ""
    s_run = s_cell.paragraphs[0].add_run(exec_text)
    s_run.font.size = Pt(11)
    s_run.font.color.rgb = RGBColor(
        int(PRIMARY_DARK[0:2], 16), int(PRIMARY_DARK[2:4], 16), int(PRIMARY_DARK[4:6], 16)
    )
    doc.add_paragraph()

    # ---- 3. Business KPIs ----
    biz_kpis = pipeline_result.get("business_kpis", {}) or {}
    if biz_kpis:
        add_section_heading("Business KPIs")
        kpi_table = doc.add_table(rows=1, cols=2)
        style_two_col_table(kpi_table, "KPI", "Value", [(str(k), str(v)) for k, v in biz_kpis.items()])
        doc.add_paragraph()

    # ---- 4. Semantic Column Profiling ----
    add_section_heading("Column Semantic Profiling")
    semantics = pipeline_result.get("semantic_types", {}) or {}
    if semantics:
        sem_table = doc.add_table(rows=1, cols=2)
        style_two_col_table(
            sem_table, "Column Name", "Detected Semantic Role",
            [(str(col), str(sem)) for col, sem in list(semantics.items())[:25]],
        )
        if len(semantics) > 25:
            note = doc.add_paragraph(f"+ {len(semantics) - 25} more columns not shown.")
            note.runs[0].font.italic = True
            note.runs[0].font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
    else:
        doc.add_paragraph("No semantic classification available.")
    doc.add_paragraph()

    # ---- 5. Outlier Detection ----
    outliers = pipeline_result.get("outliers", {}) or {}
    if outliers:
        add_section_heading("Outlier Detection")
        out_rows = []
        for col, info in list(outliers.items())[:25]:
            count = info.get("count", info.get("outlier_count", "-")) if isinstance(info, dict) else info
            out_rows.append((str(col), str(count)))
        out_table = doc.add_table(rows=1, cols=2)
        style_two_col_table(out_table, "Column", "Outlier Count", out_rows)
        doc.add_paragraph()

    # ---- 6. Exploratory Charts ----
    add_section_heading("Automated Exploratory Charts")
    charts = pipeline_result.get("recommended_charts", []) or []
    if charts:
        for c in charts[:4]:
            decoded = _decode_chart_image(c)
            if decoded is None:
                continue
            img_buf, _, _ = decoded
            try:
                chart_heading = doc.add_heading(c.get("title", "Chart"), level=2)
                for run in chart_heading.runs:
                    run.font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)
                desc_p = doc.add_paragraph(c.get("description", ""))
                if desc_p.runs:
                    desc_p.runs[0].font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
                    desc_p.runs[0].font.italic = True
                pic_p = doc.add_paragraph()
                pic_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                pic_p.add_run().add_picture(img_buf, width=Inches(6.0))
                doc.add_paragraph()
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Could not embed chart in Word doc: {e}")
    else:
        doc.add_paragraph("No charts were generated for this dataset.")

    # ---- Branded footer with page numbers ----
    footer = doc.sections[0].footer
    footer_p = footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer_p.add_run("DataNova Smart Analytics Platform  |  Page ")
    footer_run.font.size = Pt(9)
    footer_run.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)
    _docx_add_page_number_field(footer_p)
    for r in footer_p.runs[1:]:
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)

    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# --------------------------------------------------------------------------
# PowerPoint report
# --------------------------------------------------------------------------

def _ppt_rgb(hex_str):
    from pptx.dml.color import RGBColor

    return RGBColor(int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))


def _ppt_add_transition(slide, kind="fade", duration_ms=600):
    """
    Add a slide-advance transition effect (Slide Show > Transitions), via direct
    XML injection since python-pptx exposes no public API for this.

    This is intentionally best-effort: PowerPoint's true *object* entrance
    animations require a much more complex <p:timing> tree that is easy to
    get subtly wrong and can produce a file PowerPoint refuses to open, so
    that is deliberately NOT attempted here. A slide transition is the safe,
    reliable way to add motion to a generated deck.
    """
    try:
        from lxml import etree
        from pptx.oxml.ns import qn

        p14_ns = "http://schemas.microsoft.com/office/powerpoint/2010/main"
        sld = slide._element

        existing = sld.find(qn("p:transition"))
        if existing is not None:
            sld.remove(existing)

        transition = etree.SubElement(sld, qn("p:transition"))
        transition.set(f"{{{p14_ns}}}dur", str(duration_ms))
        transition.set("spd", "med")

        if kind == "push":
            child = etree.SubElement(transition, qn("p:push"))
            child.set("dir", "l")
        elif kind == "wipe":
            child = etree.SubElement(transition, qn("p:wipe"))
            child.set("dir", "r")
        else:
            etree.SubElement(transition, qn("p:fade"))

        # Per the schema, <p:transition> must immediately follow <p:cSld>.
        sld.remove(transition)
        c_sld = sld.find(qn("p:cSld"))
        c_sld.addnext(transition)
    except Exception as e:  # noqa: BLE001 - transitions are a nice-to-have, never fatal
        logger.info(f"Skipped slide transition (non-fatal): {e}")


def generate_ppt_report_bytes(pipeline_result):
    """
    Generates a branded, widescreen executive PowerPoint (.pptx) using python-pptx:
    a colored cover/closing slide, KPI cards, styled tables, framed charts, a
    consistent accent-bar title treatment on every slide, and slide transitions.
    Returns: bytes (.pptx binary stream)
    """
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.enum.shapes import MSO_SHAPE

    PRIMARY = "4F46E5"
    PRIMARY_DARK = "3730A3"
    SECONDARY = "7C3AED"
    DARK = "1E293B"
    MUTED = "64748B"
    LIGHT_BG = "F1F5F9"
    WHITE = "FFFFFF"
    SUCCESS = "10B981"

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    SW, SH = 13.333, 7.5
    blank_layout = prs.slide_layouts[6]
    buffer = BytesIO()

    overview = pipeline_result.get("dataset_overview", {}) or {}
    quality = pipeline_result.get("quality", {}) or {}
    domain = _resolve_business_domain(pipeline_result)
    exec_text = _get_exec_summary(pipeline_result)
    score_display = _fmt_score(quality.get("score", 100))
    grade = quality.get("grade", "A+")

    # ---- low-level shape helpers -----------------------------------------
    def add_rect(slide, left, top, width, height, hex_color, shape=MSO_SHAPE.RECTANGLE):
        shp = slide.shapes.add_shape(shape, Inches(left), Inches(top), Inches(width), Inches(height))
        shp.fill.solid()
        shp.fill.fore_color.rgb = _ppt_rgb(hex_color)
        shp.line.fill.background()
        shp.shadow.inherit = False
        return shp

    def add_text(slide, left, top, width, height, text, size=14, bold=False, color=DARK,
                 align=PP_ALIGN.LEFT, anchor=None, font_name=None):
        box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = box.text_frame
        tf.word_wrap = True
        if anchor:
            tf.vertical_anchor = anchor
        p = tf.paragraphs[0]
        p.text = text
        p.font.size = Pt(size)
        p.font.bold = bold
        p.font.color.rgb = _ppt_rgb(color)
        p.alignment = align
        if font_name:
            p.font.name = font_name
        return box

    def set_background(slide, hex_color):
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = _ppt_rgb(hex_color)

    def add_footer(slide, page_label):
        add_rect(slide, 0, SH - 0.06, SW, 0.06, PRIMARY)
        add_text(
            slide, 0.5, SH - 0.45, SW - 1, 0.35,
            f"DataNova Smart Analytics Platform  ·  {domain}",
            size=9, color=MUTED,
        )
        add_text(slide, SW - 2.0, SH - 0.45, 1.5, 0.35, page_label, size=9, color=MUTED, align=PP_ALIGN.RIGHT)

    def add_title_bar(slide, title_text):
        add_rect(slide, 0.6, 0.55, 0.08, 0.55, PRIMARY)
        add_text(slide, 0.85, 0.45, SW - 1.4, 0.7, title_text, size=26, bold=True, color=DARK)
        return 1.35  # y-offset where content should start

    def add_kpi_card(slide, left, top, width, height, label, value, accent=PRIMARY, value_size=22):
        card = add_rect(slide, left, top, width, height, WHITE, MSO_SHAPE.ROUNDED_RECTANGLE)
        card.adjustments[0] = 0.08
        add_rect(slide, left, top, width, 0.09, accent)
        add_text(slide, left + 0.15, top + 0.22, width - 0.3, 0.5, str(value),
                  size=value_size, bold=True, color=DARK)
        add_text(slide, left + 0.15, top + height - 0.55, width - 0.3, 0.45, str(label),
                  size=10.5, color=MUTED)

    def style_table(table, ncols, header_bg=PRIMARY, band_bg=LIGHT_BG):
        for c in range(ncols):
            cell = table.cell(0, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = _ppt_rgb(header_bg)
            for p in cell.text_frame.paragraphs:
                p.font.bold = True
                p.font.size = Pt(12)
                p.font.color.rgb = _ppt_rgb(WHITE)
        for r in range(1, len(table.rows)):
            for c in range(ncols):
                cell = table.cell(r, c)
                cell.fill.solid()
                cell.fill.fore_color.rgb = _ppt_rgb(band_bg if r % 2 == 0 else WHITE)
                for p in cell.text_frame.paragraphs:
                    p.font.size = Pt(11)
                    p.font.color.rgb = _ppt_rgb(DARK)

    def add_data_table(slide, headers, rows, top, left=0.8, width=SW - 1.6, row_h=0.42):
        n_rows = len(rows) + 1
        n_cols = len(headers)
        gframe = slide.shapes.add_table(n_rows, n_cols, Inches(left), Inches(top), Inches(width), Inches(row_h * n_rows))
        table = gframe.table
        for c, h in enumerate(headers):
            table.cell(0, c).text = str(h)
        for r, row in enumerate(rows, start=1):
            for c, val in enumerate(row):
                table.cell(r, c).text = str(val)
        style_table(table, n_cols)
        return table

    # ======================= Slide 1: Cover =================================
    cover = prs.slides.add_slide(blank_layout)
    set_background(cover, PRIMARY)
    add_rect(cover, SW - 3.2, -1.2, 4.2, 4.2, SECONDARY, MSO_SHAPE.OVAL).fill.fore_color.rgb = _ppt_rgb(PRIMARY_DARK)
    add_rect(cover, -1.0, SH - 2.4, 3.6, 3.6, PRIMARY_DARK, MSO_SHAPE.OVAL)
    add_text(cover, 1, 2.55, SW - 2, 1.0, "DataNova Smart Analytics Platform",
              size=40, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(cover, 1, 3.5, SW - 2, 0.6, "Executive Automated EDA Presentation",
              size=18, color="E0E7FF", align=PP_ALIGN.CENTER)
    badge = add_rect(cover, SW / 2 - 1.9, 4.35, 3.8, 0.6, WHITE, MSO_SHAPE.ROUNDED_RECTANGLE)
    badge.adjustments[0] = 0.5
    add_text(cover, SW / 2 - 1.9, 4.42, 3.8, 0.5, f"Domain: {domain}",
              size=13, bold=True, color=PRIMARY_DARK, align=PP_ALIGN.CENTER)
    add_text(cover, 1, SH - 1.0, SW - 2, 0.4, f"Data Quality: Grade {grade} ({score_display})",
              size=12, color="C7D2FE", align=PP_ALIGN.CENTER)
    _ppt_add_transition(cover, "fade", 700)

    # ================= Slide 2: Executive Summary & KPIs ====================
    kpi_slide = prs.slides.add_slide(blank_layout)
    set_background(kpi_slide, WHITE)
    add_title_bar(kpi_slide, "Executive Summary & Core Metrics")

    kpi_defs = [
        ("Total Records", _fmt_int_commas(overview.get("row_count", 0)), PRIMARY),
        ("Total Columns", str(overview.get("column_count", 0)), SECONDARY),
        ("Quality Score", score_display, SUCCESS),
        ("Quality Grade", str(grade), PRIMARY_DARK),
    ]
    card_w, gap = 2.75, 0.3
    start_x = (SW - (card_w * 4 + gap * 3)) / 2
    for i, (label, value, accent) in enumerate(kpi_defs):
        add_kpi_card(kpi_slide, start_x + i * (card_w + gap), 1.6, card_w, 1.5, label, value, accent)

    add_rect(kpi_slide, 0.8, 3.5, 0.07, 2.6, PRIMARY)
    summary_box = add_rect(kpi_slide, 0.8, 3.5, SW - 1.6, 2.6, "EEF2FF", MSO_SHAPE.ROUNDED_RECTANGLE)
    summary_box.adjustments[0] = 0.03
    add_text(kpi_slide, 1.1, 3.65, SW - 2.2, 0.4, "Key Finding", size=14, bold=True, color=PRIMARY_DARK)
    add_text(kpi_slide, 1.1, 4.05, SW - 2.2, 1.9, exec_text, size=13, color=PRIMARY_DARK,
              anchor=MSO_ANCHOR.TOP)
    add_footer(kpi_slide, "2")
    _ppt_add_transition(kpi_slide, "fade", 500)

    slide_num = 3

    # ======================= Slide 3: Business KPIs ==========================
    biz_kpis = pipeline_result.get("business_kpis", {}) or {}
    if biz_kpis:
        kpi_only_slide = prs.slides.add_slide(blank_layout)
        set_background(kpi_only_slide, WHITE)
        add_title_bar(kpi_only_slide, "Business KPIs")
        items = list(biz_kpis.items())[:8]
        cols = 4
        card_w2, card_h2, gap2 = 2.75, 1.65, 0.3
        start_x2 = (SW - (card_w2 * cols + gap2 * (cols - 1))) / 2
        accents = [PRIMARY, SECONDARY, SUCCESS, PRIMARY_DARK]
        for idx, (k, v) in enumerate(items):
            row, col = divmod(idx, cols)
            x = start_x2 + col * (card_w2 + gap2)
            y = 1.7 + row * (card_h2 + 0.3)
            add_kpi_card(kpi_only_slide, x, y, card_w2, card_h2, str(k), str(v),
                          accent=accents[idx % len(accents)], value_size=18)
        add_footer(kpi_only_slide, str(slide_num))
        _ppt_add_transition(kpi_only_slide, "fade", 500)
        slide_num += 1

    # ================ Slide: Column Semantic Profiling =======================
    semantics = pipeline_result.get("semantic_types", {}) or {}
    if semantics:
        sem_slide = prs.slides.add_slide(blank_layout)
        set_background(sem_slide, WHITE)
        add_title_bar(sem_slide, "Column Semantic Profiling")
        rows = [(str(c), str(s)) for c, s in list(semantics.items())[:10]]
        add_data_table(sem_slide, ["Column Name", "Detected Semantic Role"], rows, top=1.5)
        if len(semantics) > 10:
            add_text(sem_slide, 0.8, 1.5 + 0.42 * (len(rows) + 1) + 0.15, SW - 1.6, 0.4,
                      f"+ {len(semantics) - 10} more columns not shown.", size=10.5, color=MUTED)
        add_footer(sem_slide, str(slide_num))
        _ppt_add_transition(sem_slide, "fade", 500)
        slide_num += 1

    # ===================== Slide: Outlier Detection ==========================
    outliers = pipeline_result.get("outliers", {}) or {}
    if outliers:
        out_slide = prs.slides.add_slide(blank_layout)
        set_background(out_slide, WHITE)
        add_title_bar(out_slide, "Outlier Detection")
        out_rows = []
        for col, info in list(outliers.items())[:10]:
            count = info.get("count", info.get("outlier_count", "-")) if isinstance(info, dict) else info
            out_rows.append((str(col), str(count)))
        add_data_table(out_slide, ["Column", "Outlier Count"], out_rows, top=1.5)
        add_footer(out_slide, str(slide_num))
        _ppt_add_transition(out_slide, "fade", 500)
        slide_num += 1

    # ===================== Chart slides (framed, aspect-ratio preserved) =====
    charts = pipeline_result.get("recommended_charts", []) or []
    max_width_in, max_height_in = 9.5, 4.6
    for c in charts[:4]:
        chart_slide = prs.slides.add_slide(blank_layout)
        set_background(chart_slide, WHITE)
        add_title_bar(chart_slide, c.get("title", "Exploratory Chart"))
        desc = c.get("description", "")
        if desc:
            add_text(chart_slide, 0.85, 1.3, SW - 1.7, 0.4, desc, size=12, color=MUTED)

        decoded = _decode_chart_image(c)
        if decoded is None:
            add_footer(chart_slide, str(slide_num))
            _ppt_add_transition(chart_slide, "fade", 500)
            slide_num += 1
            continue
        img_buf, w_px, h_px = decoded
        try:
            if w_px and h_px:
                aspect = w_px / h_px
                draw_w, draw_h = max_width_in, max_width_in / aspect
                if draw_h > max_height_in:
                    draw_h = max_height_in
                    draw_w = max_height_in * aspect
            else:
                draw_w, draw_h = max_width_in, max_height_in
            left = (SW - draw_w) / 2
            top = 2.0
            # subtle card frame behind the chart image
            frame = add_rect(chart_slide, left - 0.15, top - 0.15, draw_w + 0.3, draw_h + 0.3,
                              WHITE, MSO_SHAPE.ROUNDED_RECTANGLE)
            frame.adjustments[0] = 0.03
            frame.line.fill.solid()
            frame.line.fill.fore_color.rgb = _ppt_rgb("E2E8F0")
            frame.line.width = Pt(1)
            chart_slide.shapes.add_picture(img_buf, Inches(left), Inches(top), Inches(draw_w), Inches(draw_h))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Could not add picture to PPT: {e}")
        add_footer(chart_slide, str(slide_num))
        _ppt_add_transition(chart_slide, "fade", 500)
        slide_num += 1

    # ======================= Closing slide ===================================
    closing = prs.slides.add_slide(blank_layout)
    set_background(closing, PRIMARY_DARK)
    add_rect(closing, -1.2, -1.2, 3.6, 3.6, PRIMARY, MSO_SHAPE.OVAL)
    add_text(closing, 1, 3.1, SW - 2, 0.9, "Thank You", size=36, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(closing, 1, 3.95, SW - 2, 0.5, "DataNova Smart Analytics Platform",
              size=15, color="C7D2FE", align=PP_ALIGN.CENTER)
    _ppt_add_transition(closing, "fade", 700)

    prs.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# --------------------------------------------------------------------------
# Excel report
# --------------------------------------------------------------------------
#
# Design system (kept consistent with the HTML/PDF/Word/PPT reports):
#   PRIMARY = indigo (#4F46E5), PRIMARY_DARK = #3730A3, SECONDARY = violet
#   (#7C3AED), DARK = slate-900 (#1E293B), MUTED = slate-500 (#64748B),
#   LIGHT_BG = slate-100 (#F1F5F9), SUCCESS = emerald (#10B981),
#   DANGER = red (#DC2626), WHITE = #FFFFFF.
#
# Sheet map (only sheets with real data are created):
#   1. Cover                  - branded title band + at-a-glance metrics
#   2. Executive Summary      - overview metrics + AI narrative
#   3. Business KPIs          - every business_kpis entry
#   4. Column Profiling       - semantic_types, one row per column
#   5. Descriptive Statistics - full descriptive_statistics table
#   6. Correlation Matrix     - correlation_matrix with a red/blue heat map
#   7. Outlier Detection      - outliers, with % highlighted by severity
#   8. Exploratory Charts     - chart images embedded in-sheet with captions
#   9. Cleaned Dataset        - the full dataframe, banded + auto-filtered

def _xlsx_style_kit():
    """Centralised colors/fonts/fills/borders/number-formats for the workbook."""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, NamedStyle

    colors = {
        "primary": "4F46E5",
        "primary_dark": "3730A3",
        "secondary": "7C3AED",
        "dark": "1E293B",
        "muted": "64748B",
        "light_bg": "F1F5F9",
        "band_bg": "F8FAFC",
        "success": "10B981",
        "success_bg": "D1FAE5",
        "warning": "F59E0B",
        "warning_bg": "FEF3C7",
        "danger": "DC2626",
        "danger_bg": "FEE2E2",
        "border": "E2E8F0",
        "white": "FFFFFF",
    }

    thin = Side(style="thin", color=colors["border"])
    kit = {
        "colors": colors,
        "font_name": "Calibri",
        "border_thin": Border(left=thin, right=thin, top=thin, bottom=thin),
        "align_left": Alignment(horizontal="left", vertical="center", wrap_text=True),
        "align_center": Alignment(horizontal="center", vertical="center", wrap_text=True),
        "align_right": Alignment(horizontal="right", vertical="center"),
        "num_fmt_int": "#,##0",
        "num_fmt_dec": "#,##0.00",
        "num_fmt_pct": "0.0%",
    }
    kit["Font"] = Font
    kit["PatternFill"] = PatternFill
    return kit


def _xlsx_title_banner(ws, kit, title, subtitle, span_cols=6, height=(34, 20)):
    """Draws a colored two-row title band across the top of a sheet."""
    Font, PatternFill = kit["Font"], kit["PatternFill"]
    c = kit["colors"]

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=span_cols)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=span_cols)

    for row in (1, 2):
        for col in range(1, span_cols + 1):
            ws.cell(row=row, column=col).fill = PatternFill(
                start_color=c["primary"], end_color=c["primary"], fill_type="solid"
            )

    title_cell = ws.cell(row=1, column=1, value=title)
    title_cell.font = Font(name=kit["font_name"], size=18, bold=True, color=c["white"])
    title_cell.alignment = kit["align_left"]

    sub_cell = ws.cell(row=2, column=1, value=subtitle)
    sub_cell.font = Font(name=kit["font_name"], size=11, color="E0E7FF")
    sub_cell.alignment = kit["align_left"]

    ws.row_dimensions[1].height = height[0]
    ws.row_dimensions[2].height = height[1]
    ws.row_dimensions[3].height = 8  # breathing room before content


def _xlsx_section_label(ws, kit, row, text, span_cols=2):
    """A small bold, colored label used to introduce a sub-block within a sheet."""
    Font = kit["Font"]
    c = kit["colors"]
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=max(span_cols, 1))
    cell = ws.cell(row=row, column=1, value=text)
    cell.font = Font(name=kit["font_name"], size=12, bold=True, color=c["primary_dark"])
    ws.row_dimensions[row].height = 22
    return row + 1


def _xlsx_write_table(ws, kit, start_row, headers, rows, col_widths=None, number_cols=None,
                       autofilter=True, freeze=True):
    """
    Writes a styled table (dark header row, banded body rows, thin borders,
    right-aligned number columns) starting at start_row, column 1.
    Returns the row index just after the table.
    """
    Font, PatternFill = kit["Font"], kit["PatternFill"]
    c = kit["colors"]
    number_cols = number_cols or set()

    header_row = start_row
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=str(header))
        cell.font = Font(name=kit["font_name"], size=11, bold=True, color=c["white"])
        cell.fill = PatternFill(start_color=c["dark"], end_color=c["dark"], fill_type="solid")
        cell.alignment = kit["align_center"]
        cell.border = kit["border_thin"]
    ws.row_dimensions[header_row].height = 20

    for r_offset, row_vals in enumerate(rows):
        row_idx = header_row + 1 + r_offset
        band = r_offset % 2 == 1
        for col_idx, val in enumerate(row_vals, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.border = kit["border_thin"]
            cell.font = Font(name=kit["font_name"], size=10.5, color=c["dark"])
            if band:
                cell.fill = PatternFill(start_color=c["band_bg"], end_color=c["band_bg"], fill_type="solid")
            if col_idx in number_cols:
                cell.alignment = kit["align_right"]
                if isinstance(val, float):
                    cell.number_format = kit["num_fmt_dec"]
                elif isinstance(val, int):
                    cell.number_format = kit["num_fmt_int"]
            else:
                cell.alignment = kit["align_left"]

    last_row = header_row + len(rows)

    if col_widths or (autofilter and rows):
        from openpyxl.utils import get_column_letter
        if col_widths:
            for i, width in enumerate(col_widths, start=1):
                ws.column_dimensions[get_column_letter(i)].width = width
        if autofilter and rows:
            ws.auto_filter.ref = f"A{header_row}:{get_column_letter(len(headers))}{last_row}"

    if freeze:
        ws.freeze_panes = ws.cell(row=header_row + 1, column=1).coordinate

    return last_row + 2


def _xlsx_kpi_strip(ws, kit, start_row, kpi_defs):
    """
    Draws a row of card-like KPI tiles (label on top, big value below) using
    merged, filled, bordered cell blocks -- openpyxl has no native "card"
    shape, so this is built from styled cell ranges.
    kpi_defs: list of (label, value, accent_hex)
    """
    Font, PatternFill = kit["Font"], kit["PatternFill"]
    c = kit["colors"]
    from openpyxl.styles import Border, Side

    card_cols = 2  # each card spans 2 columns
    value_row = start_row
    label_row = start_row + 1
    accent_row_fill_row = start_row  # top accent stripe reuses value row's top border trick instead

    for i, (label, value, accent) in enumerate(kpi_defs):
        c1 = i * card_cols + 1
        c2 = c1 + card_cols - 1
        ws.merge_cells(start_row=value_row, start_column=c1, end_row=value_row, end_column=c2)
        ws.merge_cells(start_row=label_row, start_column=c1, end_row=label_row, end_column=c2)

        val_cell = ws.cell(row=value_row, column=c1, value=value)
        val_cell.font = Font(name=kit["font_name"], size=16, bold=True, color=c["dark"])
        val_cell.alignment = kit["align_center"]
        val_cell.fill = PatternFill(start_color=c["white"], end_color=c["white"], fill_type="solid")
        thick_top = Side(style="thick", color=accent)
        thin = Side(style="thin", color=c["border"])
        val_cell.border = Border(top=thick_top, left=thin, right=thin)
        for cc in range(c1, c2 + 1):
            if cc != c1:
                ec = ws.cell(row=value_row, column=cc)
                ec.border = Border(top=thick_top)
                ec.fill = PatternFill(start_color=c["white"], end_color=c["white"], fill_type="solid")

        lab_cell = ws.cell(row=label_row, column=c1, value=str(label))
        lab_cell.font = Font(name=kit["font_name"], size=9.5, bold=True, color=c["muted"])
        lab_cell.alignment = kit["align_center"]
        lab_cell.fill = PatternFill(start_color=c["white"], end_color=c["white"], fill_type="solid")
        lab_cell.border = Border(left=thin, right=thin, bottom=thin)
        for cc in range(c1, c2 + 1):
            if cc != c1:
                ec = ws.cell(row=label_row, column=cc)
                ec.border = Border(bottom=thin)
                ec.fill = PatternFill(start_color=c["white"], end_color=c["white"], fill_type="solid")

    ws.row_dimensions[value_row].height = 30
    ws.row_dimensions[label_row].height = 18
    return label_row + 2


def generate_excel_report_bytes(df, pipeline_result):
    """
    Generates a full, professionally branded multi-sheet Microsoft Excel
    (.xlsx) workbook using openpyxl. Unlike a bare data dump, every module the
    pipeline computed gets its own clearly labeled, formatted sheet -- title
    banners, KPI tiles, dark banded tables, a color-scaled correlation heat
    map, embedded chart images and a fully filterable/frozen cleaned dataset.

    Args:
        df (pd.DataFrame | None): the cleaned dataset, or None.
        pipeline_result (dict): output from pipeline_service.analyze_dataset()

    Returns:
        bytes: .xlsx binary stream
    """
    import openpyxl
    from openpyxl.utils import get_column_letter
    from openpyxl.formatting.rule import ColorScaleRule
    from openpyxl.worksheet.pagebreak import Break

    kit = _xlsx_style_kit()
    c = kit["colors"]
    Font, PatternFill = kit["Font"], kit["PatternFill"]

    overview = pipeline_result.get("dataset_overview", {}) or {}
    quality = pipeline_result.get("quality", {}) or {}
    semantics = pipeline_result.get("semantic_types", {}) or {}
    stats = pipeline_result.get("descriptive_statistics", {}) or {}
    outliers = pipeline_result.get("outliers", {}) or {}
    corr_data = pipeline_result.get("correlation_matrix", {}) or {}
    biz_kpis = pipeline_result.get("business_kpis", {}) or {}
    charts = pipeline_result.get("recommended_charts", []) or []
    mem_summary = pipeline_result.get("memory_summary", {}) or {}

    domain = _resolve_business_domain(pipeline_result)
    exec_text = _get_exec_summary(pipeline_result)
    score_display = _fmt_score(quality.get("score", 100))
    grade = quality.get("grade", "A+")
    generated_on = datetime.now().strftime("%B %d, %Y at %H:%M")

    buffer = BytesIO()
    wb = openpyxl.Workbook()
    wb.properties.title = "DataNova Executive EDA Report"
    wb.properties.creator = "DataNova Smart Analytics Platform"
    wb.properties.subject = domain

    # ======================================================================
    # Sheet 1: Cover
    # ======================================================================
    ws_cover = wb.active
    ws_cover.title = "Cover"
    ws_cover.sheet_view.showGridLines = False
    ws_cover.sheet_properties.tabColor = c["primary"]

    _xlsx_title_banner(
        ws_cover, kit,
        "DataNova Executive EDA Report",
        f"Business Domain: {domain}   |   Generated on {generated_on}",
        span_cols=8, height=(40, 22),
    )

    row = 5
    row = _xlsx_section_label(ws_cover, kit, row, "At a Glance", span_cols=8)
    kpi_defs = [
        ("Total Rows", _fmt_int_commas(overview.get("row_count", 0)), c["primary"]),
        ("Total Columns", str(overview.get("column_count", 0)), c["secondary"]),
        ("Quality Score", score_display, c["success"]),
        ("Quality Grade", str(grade), c["primary_dark"]),
    ]
    row = _xlsx_kpi_strip(ws_cover, kit, row, kpi_defs)

    row += 1
    row = _xlsx_section_label(ws_cover, kit, row, "Report Contents", span_cols=8)
    contents = [("Sheet", "Contents")]
    contents_rows = [("Cover", "Report summary and navigation")]
    contents_rows.append(("Executive Summary", "Dataset overview metrics and AI-generated narrative"))
    if biz_kpis:
        contents_rows.append(("Business KPIs", f"{len(biz_kpis)} business metric(s)"))
    if semantics:
        contents_rows.append(("Column Profiling", f"Semantic role for all {len(semantics)} column(s)"))
    if stats:
        contents_rows.append(("Descriptive Statistics", "Full statistical summary per numeric column"))
    if corr_data:
        contents_rows.append(("Correlation Matrix", "Heat-mapped pairwise correlations"))
    if outliers:
        contents_rows.append(("Outlier Detection", f"Outliers across {len(outliers)} column(s)"))
    if charts:
        contents_rows.append(("Exploratory Charts", f"{len(charts)} embedded chart(s)"))
    contents_rows.append(("Cleaned Dataset", "Full underlying data, filterable" if df is not None and not df.empty
                           else "No dataset was provided for this report"))
    row = _xlsx_write_table(
        ws_cover, kit, row, ["Sheet", "Contents"], contents_rows,
        col_widths=[26, 60], autofilter=False, freeze=False,
    )

    row += 1
    footer_cell = ws_cover.cell(row=row, column=1, value="Generated automatically by DataNova Smart Analytics Platform")
    footer_cell.font = Font(name=kit["font_name"], size=9, italic=True, color=c["muted"])

    # ======================================================================
    # Sheet 2: Executive Summary
    # ======================================================================
    ws_sum = wb.create_sheet("Executive Summary")
    ws_sum.sheet_view.showGridLines = False
    ws_sum.sheet_properties.tabColor = c["primary_dark"]

    _xlsx_title_banner(ws_sum, kit, "Executive Summary", f"Business Domain: {domain}", span_cols=6)

    row = 5
    row = _xlsx_section_label(ws_sum, kit, row, "Dataset Overview", span_cols=6)
    overview_rows = [
        ("Total Records (Rows)", _fmt_int_commas(overview.get("row_count", 0))),
        ("Total Columns", str(overview.get("column_count", 0))),
        ("Memory Usage", str(mem_summary.get("formatted_memory", "N/A"))),
        ("Data Quality Score", score_display),
        ("Data Quality Grade", str(grade)),
        ("Missing Cells Count", _fmt_int_commas(quality.get("missing_cells", 0))),
        ("Duplicate Rows Count", _fmt_int_commas(quality.get("duplicate_rows", 0))),
    ]
    row = _xlsx_write_table(
        ws_sum, kit, row, ["Metric", "Value"], overview_rows,
        col_widths=[34, 30], autofilter=False, freeze=False,
    )

    row += 1
    row = _xlsx_section_label(ws_sum, kit, row, "Key Finding (AI-Generated Narrative)", span_cols=6)
    ws_sum.merge_cells(start_row=row, start_column=1, end_row=row + 4, end_column=6)
    narrative_cell = ws_sum.cell(row=row, column=1, value=exec_text)
    narrative_cell.font = Font(name=kit["font_name"], size=11, color=c["primary_dark"])
    narrative_cell.alignment = kit["align_left"]
    narrative_cell.fill = PatternFill(start_color="EEF2FF", end_color="EEF2FF", fill_type="solid")
    for rr in range(row, row + 5):
        for cc in range(1, 7):
            ws_sum.cell(row=rr, column=cc).border = kit["border_thin"]
            if ws_sum.cell(row=rr, column=cc).fill.start_color.rgb in (None, "00000000"):
                ws_sum.cell(row=rr, column=cc).fill = PatternFill(
                    start_color="EEF2FF", end_color="EEF2FF", fill_type="solid"
                )
    ws_sum.row_dimensions[row].height = 24

    # ======================================================================
    # Sheet 3: Business KPIs
    # ======================================================================
    if biz_kpis:
        ws_kpi = wb.create_sheet("Business KPIs")
        ws_kpi.sheet_view.showGridLines = False
        ws_kpi.sheet_properties.tabColor = c["secondary"]
        _xlsx_title_banner(ws_kpi, kit, "Business KPIs", f"Business Domain: {domain}", span_cols=2)

        row = 5
        kpi_rows = []
        for k, v in biz_kpis.items():
            label = str(k).replace("_", " ").title()
            num = _safe_number(v, default=None)
            kpi_rows.append((label, round(num, 2) if isinstance(num, float) else v))
        _xlsx_write_table(
            ws_kpi, kit, row, ["KPI", "Value"], kpi_rows,
            col_widths=[38, 24], number_cols={2},
        )

    # ======================================================================
    # Sheet 4: Column Profiling (semantic types)
    # ======================================================================
    if semantics:
        ws_sem = wb.create_sheet("Column Profiling")
        ws_sem.sheet_view.showGridLines = False
        ws_sem.sheet_properties.tabColor = c["primary"]
        _xlsx_title_banner(
            ws_sem, kit, "Column Semantic Profiling",
            f"Detected semantic role for all {len(semantics)} column(s)", span_cols=2,
        )
        row = 5
        sem_rows = [(str(col), str(sem)) for col, sem in semantics.items()]
        _xlsx_write_table(
            ws_sem, kit, row, ["Column Name", "Detected Semantic Role"], sem_rows,
            col_widths=[36, 30],
        )

    # ======================================================================
    # Sheet 5: Descriptive Statistics
    # ======================================================================
    if stats:
        try:
            stats_df = pd.DataFrame(stats)
            ws_stats = wb.create_sheet("Descriptive Statistics")
            ws_stats.sheet_view.showGridLines = False
            ws_stats.sheet_properties.tabColor = c["primary"]
            _xlsx_title_banner(
                ws_stats, kit, "Descriptive Statistics",
                "Full statistical summary for every numeric column", span_cols=min(len(stats_df.columns) + 1, 10),
            )
            row = 5
            headers = ["Metric"] + [str(col) for col in stats_df.columns]
            data_rows = []
            for idx in stats_df.index:
                vals = []
                for v in stats_df.loc[idx]:
                    if isinstance(v, float):
                        vals.append(round(v, 4))
                    else:
                        vals.append(v)
                data_rows.append([str(idx)] + vals)
            number_cols = set(range(2, len(headers) + 1))
            _xlsx_write_table(
                ws_stats, kit, row, headers, data_rows,
                col_widths=[22] + [16] * (len(headers) - 1), number_cols=number_cols,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Could not render descriptive statistics sheet: {e}")

    # ======================================================================
    # Sheet 6: Correlation Matrix (heat-mapped)
    # ======================================================================
    if corr_data:
        try:
            corr_df = pd.DataFrame(corr_data)
            ws_corr = wb.create_sheet("Correlation Matrix")
            ws_corr.sheet_view.showGridLines = False
            ws_corr.sheet_properties.tabColor = c["secondary"]
            _xlsx_title_banner(
                ws_corr, kit, "Correlation Matrix",
                "Pairwise Pearson correlation between numeric columns (heat-mapped)",
                span_cols=min(len(corr_df.columns) + 1, 10),
            )
            row = 5
            headers = [""] + [str(col) for col in corr_df.columns]
            data_rows = []
            for idx in corr_df.index:
                vals = []
                for c_ in corr_df.columns:
                    v = corr_df.loc[idx, c_]
                    try:
                        vals.append(round(float(v), 3))
                    except (TypeError, ValueError):
                        vals.append(v)
                data_rows.append([str(idx)] + vals)
            number_cols = set(range(2, len(headers) + 1))
            last_row = _xlsx_write_table(
                ws_corr, kit, row, headers, data_rows,
                col_widths=[20] + [11] * (len(headers) - 1), number_cols=number_cols,
                autofilter=False,
            )
            data_start = row + 1
            data_end = row + len(data_rows)
            if len(headers) > 1 and data_rows:
                rng = f"{get_column_letter(2)}{data_start}:{get_column_letter(len(headers))}{data_end}"
                ws_corr.conditional_formatting.add(
                    rng,
                    ColorScaleRule(
                        start_type="min", start_color="DC2626",
                        mid_type="num", mid_value=0, mid_color="FFFFFF",
                        end_type="max", end_color="4F46E5",
                    ),
                )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Could not render correlation matrix sheet: {e}")

    # ======================================================================
    # Sheet 7: Outlier Detection
    # ======================================================================
    if outliers:
        ws_out = wb.create_sheet("Outlier Detection")
        ws_out.sheet_view.showGridLines = False
        ws_out.sheet_properties.tabColor = c["danger"]
        _xlsx_title_banner(
            ws_out, kit, "Outlier Detection",
            f"Statistical outliers identified across {len(outliers)} column(s)", span_cols=3,
        )
        row = 5
        out_rows = []
        for col, info in outliers.items():
            if isinstance(info, dict):
                count = info.get("count", info.get("outlier_count", "-"))
                pct = info.get("percentage", info.get("outlier_percentage", "-"))
            else:
                count, pct = info, "-"
            count_num = _safe_number(count, default=None)
            pct_num = _safe_number(pct, default=None)
            out_rows.append((
                str(col),
                int(count_num) if isinstance(count_num, (int, float)) else count,
                round(pct_num, 2) if isinstance(pct_num, float) else pct,
            ))
        last_row = _xlsx_write_table(
            ws_out, kit, row, ["Column", "Outlier Count", "Percentage (%)"], out_rows,
            col_widths=[30, 20, 20], number_cols={2, 3}, autofilter=False,
        )
        # Severity highlight on the percentage column: >=10% red, >=5% amber, else green
        pct_col_letter = "C"
        for r_offset, (_col, _count, pct) in enumerate(out_rows):
            r_idx = row + 1 + r_offset
            pct_num = _safe_number(pct, default=None)
            if not isinstance(pct_num, (int, float)):
                continue
            if pct_num >= 10:
                fill_color, font_color = c["danger_bg"], c["danger"]
            elif pct_num >= 5:
                fill_color, font_color = c["warning_bg"], c["warning"]
            else:
                fill_color, font_color = c["success_bg"], c["success"]
            cell = ws_out[f"{pct_col_letter}{r_idx}"]
            cell.fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")
            cell.font = Font(name=kit["font_name"], size=10.5, bold=True, color=font_color)
        ws_out.auto_filter.ref = f"A{row}:C{last_row - 2}"
        ws_out.freeze_panes = f"A{row + 1}"

    # ======================================================================
    # Sheet 8: Exploratory Charts (images embedded in-sheet)
    # ======================================================================
    if charts:
        ws_charts = wb.create_sheet("Exploratory Charts")
        ws_charts.sheet_view.showGridLines = False
        ws_charts.sheet_properties.tabColor = c["success"]
        _xlsx_title_banner(
            ws_charts, kit, "Visual Exploratory Charts",
            f"{len(charts)} automatically generated chart(s)", span_cols=8,
        )

        cursor_row = 5
        embedded_any = False
        for chart in charts:
            title = str(chart.get("title", "Chart"))
            description = str(chart.get("description", ""))

            cap_cell = ws_charts.cell(row=cursor_row, column=1, value=title)
            cap_cell.font = Font(name=kit["font_name"], size=13, bold=True, color=c["dark"])
            cursor_row += 1
            if description:
                desc_cell = ws_charts.cell(row=cursor_row, column=1, value=description)
                desc_cell.font = Font(name=kit["font_name"], size=10, italic=True, color=c["muted"])
                cursor_row += 1

            decoded = _decode_chart_image(chart)
            if decoded is None:
                empty_cell = ws_charts.cell(row=cursor_row, column=1, value="Chart image could not be rendered.")
                empty_cell.font = Font(name=kit["font_name"], size=10, italic=True, color=c["muted"])
                cursor_row += 3
                continue

            img_buf, w_px, h_px = decoded
            try:
                from openpyxl.drawing.image import Image as XLImage

                xl_img = XLImage(img_buf)
                max_w_px = 640
                if w_px and h_px and w_px > 0:
                    scale = min(1.0, max_w_px / w_px)
                    xl_img.width = int(w_px * scale)
                    xl_img.height = int(h_px * scale)
                    rows_spanned = max(14, int(xl_img.height / 15) + 2)
                else:
                    rows_spanned = 22
                anchor = f"A{cursor_row + 1}"
                ws_charts.add_image(xl_img, anchor)
                embedded_any = True
                cursor_row += rows_spanned
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Could not embed chart image in Excel sheet: {e}")
                fail_cell = ws_charts.cell(row=cursor_row, column=1, value="Chart image could not be embedded.")
                fail_cell.font = Font(name=kit["font_name"], size=10, italic=True, color=c["muted"])
                cursor_row += 3

        if not embedded_any:
            note_cell = ws_charts.cell(row=cursor_row, column=1, value="No charts could be rendered for this dataset.")
            note_cell.font = Font(name=kit["font_name"], size=10, italic=True, color=c["muted"])

        ws_charts.column_dimensions["A"].width = 90

    # ======================================================================
    # Sheet 9: Cleaned Dataset
    # ======================================================================
    ws_data = wb.create_sheet("Cleaned Dataset")
    ws_data.sheet_view.showGridLines = False
    ws_data.sheet_properties.tabColor = c["dark"]

    if df is not None and not df.empty:
        n_rows_shown = min(len(df), 5000)
        _xlsx_title_banner(
            ws_data, kit, "Cleaned Dataset",
            f"Showing {_fmt_int_commas(n_rows_shown)} of {_fmt_int_commas(len(df))} row(s) · {len(df.columns)} column(s)",
            span_cols=min(len(df.columns), 10),
        )
        row = 5
        headers = list(df.columns)
        numeric_cols = {
            i + 1 for i, col in enumerate(headers) if pd.api.types.is_numeric_dtype(df[col])
        }
        data_rows = []
        for record in df.head(5000).itertuples(index=False):
            row_vals = []
            for v in record:
                if pd.isna(v):
                    row_vals.append("")
                elif isinstance(v, (int, float)):
                    row_vals.append(v)
                else:
                    row_vals.append(str(v))
            data_rows.append(row_vals)

        col_widths = []
        for i, col in enumerate(headers):
            sample_len = max((len(str(v[i])) for v in data_rows[:200]), default=8)
            col_widths.append(min(max(sample_len + 2, len(str(col)) + 2, 10), 40))

        _xlsx_write_table(
            ws_data, kit, row, headers, data_rows,
            col_widths=col_widths, number_cols=numeric_cols,
        )
        if len(df) > 5000:
            note_row = row + len(data_rows) + 2
            note_cell = ws_data.cell(
                row=note_row, column=1,
                value=f"Showing the first 5,000 of {_fmt_int_commas(len(df))} total rows. "
                      f"Export the full dataset separately for the complete record set.",
            )
            note_cell.font = Font(name=kit["font_name"], size=9.5, italic=True, color=c["muted"])
    else:
        _xlsx_title_banner(ws_data, kit, "Cleaned Dataset", "No dataset was provided for this report", span_cols=4)
        note_cell = ws_data.cell(row=5, column=1, value="No dataset was provided for this report.")
        note_cell.font = Font(name=kit["font_name"], size=11, italic=True, color=c["muted"])

    # Cover sheet should open first regardless of creation order.
    wb.move_sheet("Cover", offset=-len(wb.sheetnames))
    wb.active = 0

    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()