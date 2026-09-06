import html
import logging
import pandas as pd
from .semantic_service import detect_business_domain

logger = logging.getLogger(__name__)


def generate_eda_html_report(pipeline_result):
    """
    Generates a standalone, beautifully styled HTML EDA Report summarizing all analytical modules.
    Supports native print to PDF with print-friendly layout.

    Args:
        pipeline_result (dict): The output from pipeline_service.analyze_dataset()

    Returns:
        str: Complete HTML document as a string.
    """
    overview = pipeline_result.get("dataset_overview", {})
    quality = pipeline_result.get("quality", {})
    semantics = pipeline_result.get("semantic_types", {})
    stats = pipeline_result.get("descriptive_statistics", {})
    outliers = pipeline_result.get("outliers", {})
    corr_data = pipeline_result.get("correlation_matrix", {})
    biz_kpis = pipeline_result.get("business_kpis", {})
    charts = pipeline_result.get("recommended_charts", [])
    ai_exp = pipeline_result.get("ai_explanation", {})
    domain = pipeline_result.get("business_domain", "General Analytics")
    mem_summary = pipeline_result.get("memory_summary", {})

    # If business_domain not explicitly set, we could try to infer from semantic types,
    # but we don't have df here. So we keep fallback.

    charts_html = ""
    for chart in charts:
        title = html.escape(chart.get('title', 'Chart'))
        description = html.escape(chart.get('description', ''))
        plot = chart.get('plot', '')
        charts_html += f"""
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 20px; margin-bottom: 24px; box-shadow: 0 2px 4px rgba(0,0,0,0.04); page-break-inside: avoid;">
            <h4 style="margin-top:0; color:#1e293b; font-size:16px; font-weight:700;">{title}</h4>
            <p style="color:#64748b; font-size:13px; margin-bottom:14px;">{description}</p>
            <div style="text-align:center;">
                <img src="data:image/png;base64,{plot}" style="max-width:100%; height:auto; border-radius:8px;" alt="{title}" />
            </div>
        </div>
        """

    semantics_rows = ""
    for col, sem in semantics.items():
        col_esc = html.escape(str(col))
        sem_esc = html.escape(str(sem))
        semantics_rows += f"<tr><td style='padding:10px 12px; border-bottom:1px solid #f1f5f9; font-weight:500;'>{col_esc}</td><td style='padding:10px 12px; border-bottom:1px solid #f1f5f9;'><span style='background:#e0e7ff; color:#3730a3; padding:4px 10px; border-radius:12px; font-size:12px; font-weight:600;'>{sem_esc}</span></td></tr>"

    exec_summary_text = ai_exp.get("executive_summary", "Detailed quantitative analysis completed successfully across all dataset metrics.") if isinstance(ai_exp, dict) else "Analysis completed successfully."
    exec_summary_text = html.escape(exec_summary_text)

    # Fallback if quality grade missing
    grade = html.escape(str(quality.get('grade', 'A+')))
    score = quality.get('score', 100)

    # Ensure score is a number
    try:
        score_display = f"{int(score)}/100" if isinstance(score, (int, float)) else f"{score}/100"
    except:
        score_display = "100/100"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DataNova - Executive Automated EDA Report</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        <style>
            * {{ box-sizing: border-box; }}
            body {{ font-family: 'Inter', system-ui, -apple-system, sans-serif; background-color: #f8fafc; color: #1e293b; line-height: 1.6; margin: 0; padding: 40px 20px; }}
            .container {{ max-width: 1040px; margin: 0 auto; background: #ffffff; padding: 48px; border-radius: 16px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05); }}
            .header {{ border-bottom: 2px solid #4f46e5; padding-bottom: 24px; margin-bottom: 32px; display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px; }}
            .header h1 {{ margin: 0; color: #4f46e5; font-size: 30px; font-weight: 800; letter-spacing: -0.5px; }}
            .header p {{ margin: 6px 0 0 0; color: #64748b; font-size: 14px; }}
            .badge {{ background: linear-gradient(135deg, #4f46e5, #7c3aed); color: #fff; padding: 8px 18px; border-radius: 30px; font-weight: 700; font-size: 15px; box-shadow: 0 4px 12px rgba(79, 70, 229, 0.25); }}
            .print-btn {{ background: #10b981; color: #fff; border: none; padding: 10px 20px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 14px; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; }}
            .print-btn:hover {{ background: #059669; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 20px; margin-bottom: 36px; }}
            .card {{ background: #f8fafc; border: 1px solid #e2e8f0; padding: 22px; border-radius: 12px; text-align: center; }}
            .card-label {{ font-size: 12px; font-weight: 700; color: #64748b; letter-spacing: 0.5px; text-transform: uppercase; }}
            .card-val {{ font-size: 28px; font-weight: 800; color: #0f172a; margin-top: 6px; letter-spacing: -0.5px; }}
            .section-title {{ font-size: 20px; font-weight: 700; color: #0f172a; border-left: 4px solid #4f46e5; padding-left: 12px; margin-top: 40px; margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 28px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }}
            th {{ background: #f1f5f9; text-align: left; padding: 12px; font-size: 13px; font-weight: 700; color: #475569; border-bottom: 2px solid #cbd5e1; text-transform: uppercase; }}
            .exec-box {{ background: #eef2ff; padding: 24px; border-radius: 12px; border-left: 5px solid #4f46e5; color: #312e81; font-size: 15px; line-height: 1.7; font-weight: 500; margin-bottom: 32px; }}
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
                    <p>Business Domain: <strong>{html.escape(domain)}</strong> | Analytics Platform 2.0</p>
                </div>
                <div style="display: flex; gap: 12px; align-items: center;">
                    <button class="print-btn" onclick="window.print()">🖨️ Save as PDF / Print</button>
                    <div class="badge">Grade {grade} ({score_display})</div>
                </div>
            </div>

            <div class="grid">
                <div class="card">
                    <div class="card-label">Total Rows</div>
                    <div class="card-val">{overview.get('row_count', 0):,}</div>
                </div>
                <div class="card">
                    <div class="card-label">Total Columns</div>
                    <div class="card-val">{overview.get('column_count', 0)}</div>
                </div>
                <div class="card">
                    <div class="card-label">Memory Usage</div>
                    <div class="card-val">{html.escape(mem_summary.get('formatted_memory', 'N/A'))}</div>
                </div>
                <div class="card">
                    <div class="card-label">Quality Score</div>
                    <div class="card-val" style="color: #10b981;">{score_display}</div>
                </div>
            </div>

            <div class="section-title">Executive Summary & Analysis Insights</div>
            <div class="exec-box">
                {exec_summary_text}
            </div>

            <div class="section-title">Semantic Column Classification</div>
            <table>
                <thead>
                    <tr><th>Column Name</th><th>Detected Semantic Role</th></tr>
                </thead>
                <tbody>
                    {semantics_rows}
                </tbody>
            </table>

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


def generate_pdf_report_bytes(pipeline_result):
    """
    Generates a professional executive PDF report using ReportLab.
    Returns: bytes (PDF binary stream)
    """
    from io import BytesIO
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import base64

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        textColor=colors.HexColor('#4F46E5'),
        spaceAfter=10
    )

    h2_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=colors.HexColor('#1E293B'),
        spaceBefore=15,
        spaceAfter=8
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#334155'),
        spaceAfter=6
    )

    overview = pipeline_result.get("dataset_overview", {})
    quality = pipeline_result.get("quality", {})
    domain = pipeline_result.get("business_domain", "General Analytics")
    ai_exp = pipeline_result.get("ai_explanation", {})

    story.append(Paragraph("DataNova Executive Automated EDA Report", title_style))
    story.append(Paragraph(f"Business Domain: <b>{domain}</b> | Data Quality Index: <b>{quality.get('score', 100)}/100 (Grade {quality.get('grade', 'A+')})</b>", body_style))
    story.append(Spacer(1, 12))

    # Overview Table
    kpi_table_data = [
        ["Total Rows", "Total Columns", "Quality Score", "Missing Cells"],
        [f"{overview.get('row_count', 0):,}", str(overview.get('column_count', 0)), f"{quality.get('score', 100)}%", str(quality.get('missing_cells', 0))]
    ]
    t = Table(kpi_table_data, colWidths=[130, 130, 130, 130])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F46E5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E2E8F0'))
    ]))
    story.append(t)
    story.append(Spacer(1, 15))

    # Executive Summary Box
    story.append(Paragraph("Executive Summary & AI Insights", h2_style))
    exec_summary_text = ai_exp.get("executive_summary", "Detailed quantitative analysis completed successfully across all dataset metrics.") if isinstance(ai_exp, dict) else "Analysis completed successfully."
    story.append(Paragraph(exec_summary_text, body_style))
    story.append(Spacer(1, 15))

    # Semantic Roles Table
    story.append(Paragraph("Semantic Column Profiling", h2_style))
    semantics = pipeline_result.get("semantic_types", {})
    sem_data = [["Column Name", "Detected Semantic Role"]]
    for col, sem in list(semantics.items())[:15]:
        sem_data.append([str(col), str(sem)])

    sem_table = Table(sem_data, colWidths=[260, 260])
    sem_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0, 0), (-1, -1), 6)
    ]))
    story.append(sem_table)
    story.append(Spacer(1, 15))

    # Charts
    charts = pipeline_result.get("recommended_charts", [])
    if charts:
        story.append(Paragraph("Visual Exploratory Charts", h2_style))
        for c in charts[:3]:
            try:
                img_data = base64.b64decode(c.get('plot', ''))
                img_buf = BytesIO(img_data)
                img = Image(img_buf, width=450, height=220)
                story.append(Paragraph(f"<b>{c.get('title')}</b>", body_style))
                story.append(img)
                story.append(Spacer(1, 10))
            except Exception as e:
                logger.warning(f"Could not render image in PDF: {e}")

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_word_report_bytes(pipeline_result):
    """
    Generates a structured Microsoft Word (.docx) report using python-docx.
    Returns: bytes (.docx binary stream)
    """
    from io import BytesIO
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    import base64

    doc = Document()
    buffer = BytesIO()

    overview = pipeline_result.get("dataset_overview", {})
    quality = pipeline_result.get("quality", {})
    domain = pipeline_result.get("business_domain", "General Analytics")
    ai_exp = pipeline_result.get("ai_explanation", {})

    # Document Title
    h1 = doc.add_heading('DataNova Executive Analysis Report', level=0)
    h1.runs[0].font.color.rgb = RGBColor(79, 70, 229)

    doc.add_paragraph(f"Business Domain: {domain} | Quality Index: {quality.get('score', 100)}/100 (Grade {quality.get('grade', 'A+')})")

    # Overview Section
    doc.add_heading('1. Dataset Overview & Metrics', level=1)
    p_overview = doc.add_paragraph()
    p_overview.add_run(f"Total Records (Rows): {overview.get('row_count', 0):,}\n").bold = True
    p_overview.add_run(f"Total Columns: {overview.get('column_count', 0)}\n")
    p_overview.add_run(f"Missing Values Count: {quality.get('missing_cells', 0)}\n")
    p_overview.add_run(f"Duplicate Rows Count: {quality.get('duplicate_rows', 0)}\n")

    # Executive Summary
    doc.add_heading('2. Executive Summary', level=1)
    exec_text = ai_exp.get("executive_summary", "Automated analysis completed successfully across all feature columns.") if isinstance(ai_exp, dict) else "Analysis completed."
    doc.add_paragraph(exec_text)

    # Semantic Column Roles Table
    doc.add_heading('3. Column Semantic Profiling', level=1)
    semantics = pipeline_result.get("semantic_types", {})
    table = doc.add_table(rows=1, cols=2)
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Column Name'
    hdr_cells[1].text = 'Detected Semantic Role'

    for col, sem in list(semantics.items())[:20]:
        row_cells = table.add_row().cells
        row_cells[0].text = str(col)
        row_cells[1].text = str(sem)

    # Embedded Chart Images
    doc.add_heading('4. Automated Exploratory Charts', level=1)
    charts = pipeline_result.get("recommended_charts", [])
    for c in charts[:4]:
        try:
            doc.add_heading(c.get('title', 'Chart'), level=2)
            doc.add_paragraph(c.get('description', ''))
            img_data = base64.b64decode(c.get('plot', ''))
            img_buf = BytesIO(img_data)
            doc.add_picture(img_buf, width=Inches(6.0))
        except Exception as e:
            logger.warning(f"Could not embed chart in Word doc: {e}")

    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def generate_ppt_report_bytes(pipeline_result):
    """
    Generates an executive PowerPoint presentation (.pptx) using python-pptx.
    Returns: bytes (.pptx binary stream)
    """
    from io import BytesIO
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN
    import base64

    prs = Presentation()
    buffer = BytesIO()

    overview = pipeline_result.get("dataset_overview", {})
    quality = pipeline_result.get("quality", {})
    domain = pipeline_result.get("business_domain", "General Analytics")
    ai_exp = pipeline_result.get("ai_explanation", {})

    # Slide 1: Title Slide
    blank_slide_layout = prs.slide_layouts[6]
    title_slide = prs.slides.add_slide(blank_slide_layout)
    tx_box = title_slide.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(2))
    tf = tx_box.text_frame
    p1 = tf.paragraphs[0]
    p1.text = "DataNova Smart Analytics Platform"
    p1.font.bold = True
    p1.font.size = Pt(36)
    p1.alignment = PP_ALIGN.CENTER
    p2 = tf.add_paragraph()
    p2.text = f"Executive Presentation | Domain: {domain}"
    p2.font.size = Pt(20)
    p2.alignment = PP_ALIGN.CENTER

    # Slide 2: Executive Summary & KPIs
    kpi_slide = prs.slides.add_slide(prs.slide_layouts[5])
    kpi_slide.shapes.title.text = "Executive Summary & Core Metrics"
    body_box = kpi_slide.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(8.5), Inches(5))
    btf = body_box.text_frame
    btf.word_wrap = True
    p_kpi = btf.paragraphs[0]
    p_kpi.text = f"Total Records: {overview.get('row_count', 0):,} | Total Columns: {overview.get('column_count', 0)}"
    p_kpi.font.bold = True
    p_kpi.font.size = Pt(18)

    p_q = btf.add_paragraph()
    p_q.text = f"Data Quality Score: {quality.get('score', 100)}/100 (Grade {quality.get('grade', 'A+')})"
    p_q.font.size = Pt(16)

    p_sum = btf.add_paragraph()
    exec_text = ai_exp.get("executive_summary", "Automated analysis completed successfully across all dataset metrics.") if isinstance(ai_exp, dict) else "Analysis completed."
    p_sum.text = f"\nKey Finding:\n{exec_text}"
    p_sum.font.size = Pt(14)

    # Slide 3 & 4: Visual Chart Slides
    charts = pipeline_result.get("recommended_charts", [])
    for c in charts[:3]:
        chart_slide = prs.slides.add_slide(prs.slide_layouts[5])
        chart_slide.shapes.title.text = c.get('title', 'Exploratory Chart')
        try:
            img_data = base64.b64decode(c.get('plot', ''))
            img_buf = BytesIO(img_data)
            chart_slide.shapes.add_picture(img_buf, Inches(1), Inches(1.8), Inches(8), Inches(4.8))
        except Exception as e:
            logger.warning(f"Could not add picture to PPT: {e}")

    prs.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def generate_excel_report_bytes(df, pipeline_result):
    """
    Generates a multi-sheet Microsoft Excel (.xlsx) report workbook using openpyxl.
    Returns: bytes (.xlsx binary stream)
    """
    from io import BytesIO
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    buffer = BytesIO()
    wb = openpyxl.Workbook()

    # Sheet 1: Executive Summary
    ws_sum = wb.active
    ws_sum.title = "Executive Summary"

    ws_sum['A1'] = "DataNova Smart Analytics - Executive Workbook"
    ws_sum['A1'].font = Font(name="Calibri", size=16, bold=True, color="4F46E5")

    overview = pipeline_result.get("dataset_overview", {})
    quality = pipeline_result.get("quality", {})

    ws_sum['A3'] = "Metric"
    ws_sum['B3'] = "Value"
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

    for col_cell in ['A3', 'B3']:
        ws_sum[col_cell].fill = header_fill
        ws_sum[col_cell].font = header_font

    metrics_rows = [
        ("Total Rows", overview.get("row_count", 0)),
        ("Total Columns", overview.get("column_count", 0)),
        ("Data Quality Score", f"{quality.get('score', 100)}/100"),
        ("Quality Grade", quality.get('grade', 'A+')),
        ("Missing Cells Count", quality.get('missing_cells', 0)),
        ("Duplicate Rows Count", quality.get('duplicate_rows', 0)),
    ]

    for idx, (m, v) in enumerate(metrics_rows, start=4):
        ws_sum[f'A{idx}'] = m
        ws_sum[f'B{idx}'] = str(v)

    # Sheet 2: Raw Cleaned Dataset
    ws_data = wb.create_sheet(title="Cleaned Dataset")
    ws_data.append(list(df.columns))

    for cell in ws_data[1]:
        cell.fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
        cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

    for row in df.head(5000).itertuples(index=False):
        ws_data.append([str(v) if pd.notna(v) else "" for v in row])

    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()