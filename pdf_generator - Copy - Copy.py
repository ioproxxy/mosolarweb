"""
PDF Generation for Invoices and Orders
"""
import os
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas


def generate_invoice_pdf(order, template=None):
    """
    Generate PDF invoice for an order using the specified template
    
    Args:
        order: Order object
        template: InvoiceTemplate object (optional, uses default if None)
    
    Returns:
        BytesIO: PDF content as bytes
    """
    if not template:
        # Use default template if none specified
        template = get_default_template()
    
    # Create PDF buffer
    pdf_buffer = BytesIO()
    
    # Create the PDF document
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
    story = []
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=colors.HexColor('#22c55e'),
        alignment=1  # Center alignment
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        textColor=colors.HexColor('#333333')
    )
    
    normal_style = styles['Normal']
    
    # Company header
    company_name = template.company_name or 'Mo Solar Technologies'
    story.append(Paragraph(company_name, title_style))
    
    company_info = f"""
    {template.company_address or 'P.O. Box 12345, Nairobi, Kenya'}<br/>
    Phone: {template.company_phone or '+254727811269'}<br/>
    Email: {template.company_email or 'info@mo-solar.co.ke'}
    """
    story.append(Paragraph(company_info, normal_style))
    story.append(Spacer(1, 20))
    
    # Invoice details
    invoice_number = f'INV-{order.id:06d}'
    invoice_date = datetime.now().strftime('%B %d, %Y')
    
    invoice_info = f"""
    <b>INVOICE</b><br/>
    Invoice #: {invoice_number}<br/>
    Date: {invoice_date}<br/>
    Due Date: {invoice_date}
    """
    story.append(Paragraph(invoice_info, heading_style))
    story.append(Spacer(1, 20))
    
    # Customer information
    customer_info = f"""
    <b>Bill To:</b><br/>
    {order.user.first_name} {order.user.last_name}<br/>
    {order.shipping_address}<br/>
    {order.shipping_city}, {order.shipping_country}<br/>
    {order.shipping_postal_code}<br/>
    Phone: {order.contact_phone}<br/>
    Email: {order.contact_email}
    """
    story.append(Paragraph(customer_info, normal_style))
    story.append(Spacer(1, 30))
    
    # Order items table
    table_data = [['Product', 'Quantity', 'Unit Price', 'Total']]
    
    for item in order.items:
        table_data.append([
            item.product.name,
            str(item.quantity),
            f'KES {item.price:,.2f}',
            f'KES {item.subtotal():,.2f}'
        ])
    
    # Create table
    table = Table(table_data, colWidths=[3*inch, 1*inch, 1.5*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#22c55e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))
    
    story.append(table)
    story.append(Spacer(1, 30))
    
    # Totals
    subtotal = sum(item.subtotal() for item in order.items)
    tax_amount = Decimal('0.00')
    
    totals_data = [
        ['Subtotal:', f'KES {subtotal:,.2f}'],
        ['Tax:', f'KES {tax_amount:,.2f}'],
        ['Total:', f'KES {order.total_amount:,.2f}']
    ]
    
    totals_table = Table(totals_data, colWidths=[2*inch, 1.5*inch])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 14),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#22c55e')),
        ('LINEBELOW', (0, -1), (-1, -1), 2, colors.HexColor('#22c55e')),
        ('TOPPADDING', (0, -1), (-1, -1), 12)
    ]))
    
    story.append(totals_table)
    story.append(Spacer(1, 30))
    
    # Terms and conditions
    if template.terms_conditions:
        story.append(Paragraph('<b>Terms & Conditions:</b>', heading_style))
        story.append(Paragraph(template.terms_conditions, normal_style))
        story.append(Spacer(1, 15))
    
    # Payment instructions
    if template.payment_instructions:
        story.append(Paragraph('<b>Payment Instructions:</b>', heading_style))
        story.append(Paragraph(template.payment_instructions, normal_style))
        story.append(Spacer(1, 15))
    
    # Footer
    footer_text = template.footer_text or 'Thank you for choosing Mo Solar Technologies - We brighten your world one panel at a time!'
    story.append(Paragraph(footer_text, normal_style))
    
    # Build PDF
    doc.build(story)
    pdf_buffer.seek(0)
    
    return pdf_buffer





def get_default_template():
    """
    Get or create default invoice template
    """
    from models import InvoiceTemplate, db
    
    default_template = InvoiceTemplate.query.filter_by(
        template_type='invoice', is_active=True
    ).first()
    
    if not default_template:
        # Create default template
        default_template = InvoiceTemplate(
            name='Default Invoice Template',
            template_type='invoice',
            company_name='Mo Solar Technologies',
            company_address='P.O. Box 12345, Nairobi, Kenya',
            company_phone='+254727811269',
            company_email='info@mo-solar.co.ke',
            header_text='Professional Solar Solutions for Kenya',
            footer_text='Thank you for choosing Mo Solar Technologies - We brighten your world one panel at a time!',
            terms_conditions='Payment is due within 30 days. Late payments may incur additional charges.',
            payment_instructions='Payments can be made via M-Pesa or Bank Transfer. Please reference your invoice number.',
            is_active=True
        )
        db.session.add(default_template)
        db.session.commit()
    
    return default_template