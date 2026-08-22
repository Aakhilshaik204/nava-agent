import os
import sys
import subprocess

try:
    import reportlab
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"])

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def create_invoice(filename="invoice.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor('#1E3A8A'),
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'InvoiceSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#4B5563')
    )
    
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=10,
        spaceAfter=6
    )
    
    body_style = ParagraphStyle(
        'InvoiceBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#1F2937')
    )
    
    body_bold = ParagraphStyle(
        'InvoiceBodyBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    right_align_body = ParagraphStyle(
        'RightAlignBody',
        parent=body_style,
        alignment=2
    )

    right_align_bold = ParagraphStyle(
        'RightAlignBold',
        parent=body_bold,
        alignment=2
    )

    # Header Table
    header_data = [
        [
            Paragraph("NAVA OS SERVICES", title_style),
            Paragraph("<b>INVOICE</b>", ParagraphStyle('InvText', parent=title_style, alignment=2, fontSize=28, leading=32))
        ],
        [
            Paragraph("100 Innovation Way, Suite 400<br/>San Francisco, CA 94105<br/>support@navaos.com", subtitle_style),
            Paragraph("<b>Invoice #:</b> INV-2023-001<br/><b>Date:</b> October 24, 2023<br/><b>Due Date:</b> November 24, 2023", ParagraphStyle('MetaText', parent=subtitle_style, alignment=2))
        ]
    ]
    
    header_table = Table(header_data, colWidths=[3.5*inch, 3.5*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 25))
    
    # Bill To / Ship To Section
    bill_data = [
        [
            Paragraph("<b>BILL TO:</b>", section_heading),
            Paragraph("<b>SHIP TO:</b>", section_heading)
        ],
        [
            Paragraph("Acme Corporation<br/>Attn: Accounts Payable<br/>123 Enterprise Blvd<br/>Austin, TX 78701", body_style),
            Paragraph("Acme Corporation<br/>HQ Warehouse Dept<br/>123 Enterprise Blvd<br/>Austin, TX 78701", body_style)
        ]
    ]
    bill_table = Table(bill_data, colWidths=[3.5*inch, 3.5*inch])
    bill_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(bill_table)
    story.append(Spacer(1, 30))
    
    # Line Items Table
    items_data = [
        [
            Paragraph("<b>Description</b>", body_bold),
            Paragraph("<b>Qty</b>", right_align_bold),
            Paragraph("<b>Unit Price</b>", right_align_bold),
            Paragraph("<b>Total</b>", right_align_bold)
        ]
    ]
    
    items = [
        ("Nava OS Enterprise License - Tier 1", 5, 1200.00),
        ("Cloud Infrastructure Migration Consulting", 12, 150.00),
        ("Premium Support SLA (Annual)", 1, 1500.00),
        ("Custom API Integration Services", 8, 175.00),
    ]
    
    subtotal = 0.0
    for desc, qty, price in items:
        tot = qty * price
        subtotal += tot
        items_data.append([
            Paragraph(desc, body_style),
            Paragraph(str(qty), right_align_body),
            Paragraph(f"${price:,.2f}", right_align_body),
            Paragraph(f"${tot:,.2f}", right_align_body)
        ])
    
    tax_rate = 0.0825
    tax = subtotal * tax_rate
    grand_total = subtotal + tax
    
    items_data.append([
        Paragraph("", body_style),
        Paragraph("", body_style),
        Paragraph("<b>Subtotal:</b>", right_align_body),
        Paragraph(f"${subtotal:,.2f}", right_align_body)
    ])
    items_data.append([
        Paragraph("", body_style),
        Paragraph("", body_style),
        Paragraph("<b>Tax (8.25%):</b>", right_align_body),
        Paragraph(f"${tax:,.2f}", right_align_body)
    ])
    items_data.append([
        Paragraph("", body_style),
        Paragraph("", body_style),
        Paragraph("<b>Grand Total:</b>", right_align_bold),
        Paragraph(f"${grand_total:,.2f}", right_align_bold)
    ])
    
    items_table = Table(items_data, colWidths=[3.8*inch, 0.8*inch, 1.2*inch, 1.2*inch])
    
    t_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,0), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('LINEBELOW', (0,0), (-1,0), 1.5, colors.HexColor('#1E3A8A')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,1), (-1,-1), 6),
        ('TOPPADDING', (0,1), (-1,-1), 6),
    ])
    
    header_text_style = ParagraphStyle(
        'HeaderText',
        parent=body_bold,
        textColor=colors.white
    )
    header_text_right = ParagraphStyle(
        'HeaderTextRight',
        parent=right_align_bold,
        textColor=colors.white
    )
    items_data[0][0] = Paragraph("<b>Description</b>", header_text_style)
    items_data[0][1] = Paragraph("<b>Qty</b>", header_text_right)
    items_data[0][2] = Paragraph("<b>Unit Price</b>", header_text_right)
    items_data[0][3] = Paragraph("<b>Total</b>", header_text_right)
    
    num_items = len(items)
    for i in range(1, num_items + 1):
        bg_color = colors.HexColor('#F9FAFB') if i % 2 == 0 else colors.white
        t_style.add('BACKGROUND', (0, i), (-1, i), bg_color)
        t_style.add('LINEBELOW', (0, i), (-1, i), 0.5, colors.HexColor('#E5E7EB'))
        
    t_style.add('LINEABOVE', (2, num_items + 1), (3, num_items + 1), 1, colors.HexColor('#9CA3AF'))
    t_style.add('BOTTOMPADDING', (2, num_items + 1), (3, -1), 4)
    t_style.add('TOPPADDING', (2, num_items + 1), (3, -1), 4)
    
    t_style.add('BACKGROUND', (2, num_items + 3), (3, num_items + 3), colors.HexColor('#EFF6FF'))
    t_style.add('LINEABOVE', (2, num_items + 3), (3, num_items + 3), 1.5, colors.HexColor('#1E3A8A'))
    t_style.add('LINEBELOW', (2, num_items + 3), (3, num_items + 3), 1.5, colors.HexColor('#1E3A8A'))

    items_table.setStyle(t_style)
    story.append(items_table)
    story.append(Spacer(1, 40))
    
    terms_data = [
        [
            Paragraph("<b>Terms & Conditions:</b><br/>Payment is due within 30 days from the invoice date. Please make checks payable to <b>Nava OS Services</b> or use our electronic payment gateway at pay.navaos.com. Late payments are subject to a 1.5% fee per month.", subtitle_style)
        ]
    ]
    terms_table = Table(terms_data, colWidths=[7.0*inch])
    terms_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F3F4F6')),
        ('PADDING', (0,0), (-1,-1), 12),
        ('LINELEFT', (0,0), (-1,-1), 3, colors.HexColor('#1E3A8A')),
    ]))
    story.append(terms_table)
    
    doc.build(story)
    print("invoice.pdf created successfully.")

if __name__ == "__main__":
    create_invoice()
