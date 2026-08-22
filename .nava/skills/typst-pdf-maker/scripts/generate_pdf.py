#!/usr/bin/env python3
"""
High-End PDF Generation Script for Typst PDF Maker Skill
Generates publication-quality executive reports and technical documents.
"""

import os
import sys
import argparse
import json
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        if self._pageNumber == 1:
            return  # First page / cover title block

        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Running Header
        self.drawString(54, 842 - 36, "Executive Technical Report")
        self.drawRightString(595 - 54, 842 - 36, "Confidential Document")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 842 - 42, 595 - 54, 842 - 42)

        # Running Footer
        self.line(54, 48, 595 - 54, 48)
        self.setFont("Helvetica", 8)
        self.drawString(54, 34, "CONFIDENTIAL — INTERNAL DISTRIBUTION ONLY")
        self.setFont("Helvetica-Bold", 8)
        self.drawRightString(595 - 54, 34, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


def create_pdf(output_path, title, subtitle, author, date, sections, metrics=None, callout_text=None):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    c_brand = colors.HexColor("#0F172A")    # Slate 900
    c_blue = colors.HexColor("#1E40AF")     # Blue 800
    c_teal = colors.HexColor("#0D9488")     # Teal 600
    c_bg_soft = colors.HexColor("#F8FAFC")  # Slate 50
    c_border = colors.HexColor("#E2E8F0")   # Slate 200
    c_text = colors.HexColor("#334155")     # Slate 700

    style_title = ParagraphStyle('DocTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=22, leading=26, textColor=c_brand, alignment=1, spaceAfter=10)
    style_subtitle = ParagraphStyle('DocSubtitle', parent=styles['Normal'], fontName='Helvetica', fontSize=11, leading=15, textColor=colors.HexColor("#475569"), alignment=1, spaceAfter=12)
    style_meta = ParagraphStyle('DocMeta', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=12, textColor=colors.HexColor("#64748B"), alignment=1, spaceAfter=16)
    style_h1 = ParagraphStyle('SectionH1', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=13, leading=17, textColor=c_blue, spaceBefore=14, spaceAfter=8, keepWithNext=True)
    style_body = ParagraphStyle('BodyDark', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.5, leading=14, textColor=c_text, spaceAfter=8)
    style_code = ParagraphStyle('CodeSnippet', parent=styles['Normal'], fontName='Courier', fontSize=8.5, leading=12, textColor=colors.HexColor("#E2E8F0"))

    story = []

    # Title Badge
    badge_data = [[Paragraph("<font color='white'><b>EXECUTIVE TECHNICAL REPORT</b></font>", ParagraphStyle('B', fontName='Helvetica-Bold', fontSize=8, alignment=1))]]
    t_badge = Table(badge_data, colWidths=[180])
    t_badge.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_brand),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_badge)
    story.append(Spacer(1, 12))

    story.append(Paragraph(title, style_title))
    if subtitle:
        story.append(Paragraph(subtitle, style_subtitle))
    story.append(HRFlowable(width="40%", thickness=1.5, color=c_blue, spaceBefore=0, spaceAfter=10))
    story.append(Paragraph(f"<b>Author:</b> {author} &nbsp;|&nbsp; <b>Date:</b> {date} &nbsp;|&nbsp; <b>Version:</b> 1.0.0", style_meta))

    # Metrics Section
    if metrics:
        cards = []
        for m in metrics:
            card_data = [
                [Paragraph(f"<font color='#64748B' size=7.5><b>{m['label'].upper()}</b></font>", styles['Normal'])],
                [Paragraph(f"<font color='#0F172A' size=14><b>{m['value']}</b></font>", styles['Normal'])],
                [Paragraph(f"<font color='#16A34A' size=7.5><b>{m['delta']}</b></font>", styles['Normal'])]
            ]
            t = Table(card_data, colWidths=[150])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), c_bg_soft),
                ('BOX', (0,0), (-1,-1), 1, c_border),
                ('TOPPADDING', (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ('LEFTPADDING', (0,0), (-1,-1), 10),
                ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ]))
            cards.append(t)
        
        m_table = Table([cards], colWidths=[162] * len(cards))
        m_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(m_table)
        story.append(Spacer(1, 10))

    # Callout Box
    if callout_text:
        callout_content = [
            [Paragraph("<font color='#0D9488'><b>KEY HIGHLIGHT</b></font>", styles['Normal'])],
            [Spacer(1, 2)],
            [Paragraph(callout_text, style_body)]
        ]
        t_callout = Table(callout_content, colWidths=[475])
        t_callout.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
            ('LINELEFT', (0,0), (0,-1), 4, c_teal),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
            ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ]))
        story.append(t_callout)
        story.append(Spacer(1, 12))

    # Render Sections
    for sec in sections:
        story.append(Paragraph(sec.get('heading', ''), style_h1))
        for p in sec.get('content', []):
            if isinstance(p, str):
                story.append(Paragraph(p, style_body))
            elif isinstance(p, dict) and p.get('type') == 'code':
                code_lines = [[Paragraph(line.replace(' ', '&nbsp;'), style_code)] for line in p['code'].split('\n')]
                t_code = Table(code_lines, colWidths=[475])
                t_code.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#0F172A")),
                    ('TOPPADDING', (0,0), (-1,-1), 1),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 1),
                    ('LEFTPADDING', (0,0), (-1,-1), 12),
                    ('RIGHTPADDING', (0,0), (-1,-1), 12),
                ]))
                story.append(t_code)
                story.append(Spacer(1, 10))
            elif isinstance(p, dict) and p.get('type') == 'table':
                table_cells = []
                for row_idx, row in enumerate(p['data']):
                    row_cells = []
                    for col in row:
                        if row_idx == 0:
                            row_cells.append(Paragraph(f"<b>{col}</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white)))
                        else:
                            row_cells.append(Paragraph(str(col), style_body))
                    table_cells.append(row_cells)
                
                col_widths = p.get('widths', [475 // len(p['data'][0])] * len(p['data'][0]))
                t_data = Table(table_cells, colWidths=col_widths)
                t_data.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), c_blue),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                    ('TOPPADDING', (0,0), (-1,-1), 6),
                    ('GRID', (0,0), (-1,-1), 0.5, c_border),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [c_bg_soft, colors.white])
                ]))
                story.append(t_data)
                story.append(Spacer(1, 10))

    story.append(Spacer(1, 16))
    story.append(Paragraph("<font color='#94A3B8'>--- End of Document ---</font>", ParagraphStyle('End', fontName='Helvetica', fontSize=8.5, alignment=1)))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[SUCCESS] PDF generated at: {output_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate PDF report.")
    parser.add_argument('--output', default='sample.pdf', help='Output PDF path')
    parser.add_argument('--title', default='Next-Generation Systems Report', help='Document Title')
    parser.add_argument('--subtitle', default='Technical Architecture & Operational Blueprints', help='Subtitle')
    parser.add_argument('--author', default='Engineering & AI Architecture Group', help='Author')
    parser.add_argument('--date', default='August 2026', help='Date')
    parser.add_argument('--data_file', help='JSON file containing sections, metrics, and callout_text')
    args = parser.parse_args()

    sample_sections = [
        {
            "heading": "1. Executive Overview",
            "content": [
                "This document outlines the operational blueprints and architectural standards for high-performance agentic workflows.",
                "Key priorities include sub-200ms latency SLAs, deterministic verification, and transactional state persistence."
            ]
        },
        {
            "heading": "2. Component Matrix",
            "content": [
                {
                    "type": "table",
                    "data": [
                        ["Layer", "Description", "Status"],
                        ["Core Loop", "Plan execution and sub-agent task decomposition.", "Active"],
                        ["Context Engine", "Sliding window semantic graph memory index.", "Optimized"],
                        ["Safety Gate", "Real-time PII masking and policy verification.", "Active"]
                    ],
                    "widths": [120, 260, 95]
                }
            ]
        },
        {
            "heading": "3. Implementation Snippet",
            "content": [
                {
                    "type": "code",
                    "code": "async fn process_pipeline(input: TaskInput) -> Result<Summary, Error> {\n    let ctx = ContextEngine::load(&input.id).await?;\n    let plan = Planner::decompose(&input.query, &ctx)?;\n    Ok(plan.execute().await?)\n}"
                }
            ]
        }
    ]

    sample_metrics = [
        {"label": "Throughput", "value": "1,420 tps", "delta": "+38% YoY"},
        {"label": "Task Latency", "value": "184 ms", "delta": "-42% Reduction"},
        {"label": "Precision", "value": "99.4%", "delta": "+2.1% Improvement"}
    ]

    callout = "By decoupling state graph compaction from real-time inference, the system reduces cross-agent synchronization overhead by 64%."

    if args.data_file and os.path.exists(args.data_file):
        with open(args.data_file, 'r', encoding='utf-8') as f:
            dynamic_data = json.load(f)
            # Use empty lists/strings if the agent forgets a key, do NOT fall back to dummy data
            sections_data = dynamic_data.get('sections', [])
            metrics_data = dynamic_data.get('metrics', [])
            callout_data = dynamic_data.get('callout_text', "")
    else:
        # Only use dummy data if the script is run manually without a data file
        sections_data = sample_sections
        metrics_data = sample_metrics
        callout_data = callout

    create_pdf(args.output, args.title, args.subtitle, args.author, args.date, sections_data, metrics=metrics_data, callout_text=callout_data)
