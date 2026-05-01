import io
import os
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
import arabic_reshaper
from bidi.algorithm import get_display

from purchases.models import PurchaseProposal

# Register Arabic Font
FONT_DIR = os.path.join(settings.BASE_DIR, "purchases", "services", "fonts")
FONT_PATH = os.path.join(FONT_DIR, "Amiri-Regular.ttf")

try:
    pdfmetrics.registerFont(TTFont("Amiri", FONT_PATH))
    FONT_NAME = "Amiri"
except Exception as e:
    # Fallback to default if font fails to load for some reason
    FONT_NAME = "Helvetica"

def process_arabic(text: str) -> str:
    """Reshape and apply bidi to Arabic text for proper rendering."""
    if not text:
        return ""
    reshaped_text = arabic_reshaper.reshape(str(text))
    bidi_text = get_display(reshaped_text)
    return bidi_text

def generate_proposal_pdf(proposal: PurchaseProposal) -> bytes:
    """
    Generates a PDF for a given PurchaseProposal.
    Includes pharmacy name, date, supplier name, and a table of items.
    Returns the PDF as bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4, 
        rightMargin=30, 
        leftMargin=30, 
        topMargin=50, 
        bottomMargin=30
    )

    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'ArabicTitle',
        parent=styles['Heading1'],
        fontName=FONT_NAME,
        fontSize=20,
        alignment=TA_CENTER,
        spaceAfter=20
    )
    
    text_style = ParagraphStyle(
        'ArabicText',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=12,
        alignment=TA_RIGHT,
        spaceAfter=10
    )
    
    # Header Information
    pharmacy_name = getattr(settings, "PHARMACY_NAME", "Pharmacio")
    # All items in a proposal are grouped by warehouse_name
    first_item = proposal.items.first()
    supplier_name = first_item.ware_house_name if first_item and first_item.ware_house_name else "مورد غير معروف"
    
    date_str = proposal.created_at.strftime("%Y-%m-%d %H:%M")
    
    # Titles
    title_text = process_arabic(f"طلب شراء - {pharmacy_name}")
    elements.append(Paragraph(title_text, title_style))
    
    intro_text = process_arabic(
        f"هذا طلب شراء من صيدلية {pharmacy_name} إلى المورد/المخزن {supplier_name}."
    )
    elements.append(Paragraph(intro_text, text_style))
    
    date_text = process_arabic(f"التاريخ: {date_str}")
    elements.append(Paragraph(date_text, text_style))
    
    elements.append(Spacer(1, 20))
    
    # Table Data
    # Columns from right to left (since Arabic is RTL)
    headers = [
        process_arabic("الإجمالي"),
        process_arabic("سعر الوحدة"),
        process_arabic("الكمية"),
        process_arabic("اسم المنتج")
    ]
    data = [headers]
    
    for item in proposal.items.all():
        name = process_arabic(item.product_name)
        if item.strength:
            name += " " + process_arabic(item.strength)
        
        row = [
            f"{item.line_total:.2f}",
            f"{item.unit_price:.2f}",
            str(item.proposed_quantity),
            name
        ]
        data.append(row)
        
    # Add Total Cost Row
    data.append([
        f"{proposal.total_cost:.2f}",
        "",
        "",
        process_arabic("المجموع الكلي")
    ])

    # Table formatting
    table = Table(data, colWidths=[80, 80, 60, 260])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('GRID', (0, 0), (-1, -2), 1, colors.black),
        # Total Row Styling
        ('FONTNAME', (0, -1), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('GRID', (0, -1), (-1, -1), 1, colors.black),
        ('SPAN', (1, -1), (3, -1)), # Span the last 3 columns for "Total Cost"
        ('ALIGN', (0, -1), (-1, -1), 'CENTER'),
    ]))
    
    elements.append(table)
    
    # Build PDF
    doc.build(elements)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
