
import sys

from pathlib import Path
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import re

# --- 1. Font Setup for Traditional Chinese ---
def register_chinese_font():
    """Attempts to register a Traditional Chinese font."""
    font_path = None
    # Common Windows paths for Traditional Chinese fonts
    candidates = [
        r"C:\Windows\Fonts\msjh.ttc",      # Microsoft JhengHei (Win 7+)
        r"C:\Windows\Fonts\mingliu.ttc",    # PMingLiU
        r"C:\Windows\Fonts\simhei.ttf",     # SimHei (Fallback)
    ]
    
    font_name = "Helvetica" # Default fallback
    
    for path in candidates:
        if Path(path).exists():
            try:
                # For .ttc files, we usually want the first font
                pdfmetrics.registerFont(TTFont('ChineseFont', path, subfontIndex=0))
                font_name = 'ChineseFont'
                print(f"✅ Registered font: {path}")
                break
            except Exception as e:
                print(f"⚠️ Failed to load font {path}: {e}")
                
    return font_name

# --- 2. Markdown Parsing Helper ---
def parse_markdown_to_flowables(md_content, base_styles, font_name):
    """
    Rudimentary Markdown to ReportLab Flowables converter.
    Handles headers, paragraphs, and lists.
    Tables are tricky, basic implementation provided.
    """
    flowables = []
    
    # Styles
    title_style = ParagraphStyle(
        'CustomTitle', 
        parent=base_styles['Title'], 
        fontName=font_name, 
        fontSize=18, 
        spaceAfter=12,
        leading=22
    )
    h1_style = ParagraphStyle(
        'CustomH1', 
        parent=base_styles['Heading1'], 
        fontName=font_name, 
        fontSize=16, 
        spaceBefore=12, 
        spaceAfter=6,
        leading=20
    )
    h2_style = ParagraphStyle(
        'CustomH2', 
        parent=base_styles['Heading2'], 
        fontName=font_name, 
        fontSize=14, 
        spaceBefore=10, 
        spaceAfter=6,
        leading=18
    )
    normal_style = ParagraphStyle(
        'CustomNormal', 
        parent=base_styles['Normal'], 
        fontName=font_name, 
        fontSize=10, 
        leading=14,
        spaceAfter=6
    )
    code_style = ParagraphStyle(
        'Code',
        parent=base_styles['Code'],
        fontName='Courier',
        fontSize=8,
        leading=10,
        backColor=colors.lightgrey,
        borderPadding=2,
        spaceAfter=6
    )

    lines = md_content.split('\n')
    in_code_block = False
    code_buffer = []
    
    # Simple state machine
    for line in lines:
        line = line.strip()
        
        # Code Blocks
        if line.startswith("```"):
            if  in_code_block:
                # End of block
                in_code_block = False
                p = Paragraph("<br/>".join(code_buffer), code_style)
                flowables.append(p)
                code_buffer = []
            else:
                in_code_block = True
            continue
            
        if in_code_block:
            code_buffer.append(line.replace("<", "&lt;").replace(">", "&gt;"))
            continue

        # Headers
        if line.startswith("# "):
            flowables.append(Paragraph(line[2:], title_style))
        elif line.startswith("## "):
            flowables.append(Paragraph(line[3:], h1_style))
        elif line.startswith("### "):
            flowables.append(Paragraph(line[4:], h2_style))
        
        # Lists
        elif line.startswith("* ") or line.startswith("- "):
            # Bullet point
            text = line[2:]
            flowables.append(Paragraph(f"• {text}", normal_style))
        elif re.match(r"^\d+\.", line):
            # Numbered list
            text = line.split(".", 1)[1].strip()
            flowables.append(Paragraph(f"{line.split('.')[0]}. {text}", normal_style))
            
        # Tables (Very Basic Detection - assuming pipe tables)
        elif "|" in line and "-|-" in line:
            # Skip separator line
            continue
        elif "|" in line:
            # Determine if header or row (if it's bold/first row usually)
            # For simplicity, treat as row. ReportLab tables need list of lists.
            # We will just print as text for now to avoid complexity of layout
            # Or formatted text
            flowables.append(Paragraph(line, code_style)) 
            
        # Normal Text
        elif line:
            # Handle bold/italic markdown
            text = line
            text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text) # Bold
            text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", text)     # Italic
            text = re.sub(r"`(.*?)`", r"<font face='Courier'>\1</font>", text) # Inline Code
            
            flowables.append(Paragraph(text, normal_style))
        else:
            flowables.append(Spacer(1, 6))

    return flowables

def main():
    target_file = r"C:\Users\oscar.chang\.gemini\antigravity\brain\75cfcd29-e13f-48dd-9a8d-18ba2504b7a4\report_parser_evaluation_zh.md.resolved"
    output_pdf = r"C:\Users\oscar.chang\.gemini\antigravity\brain\75cfcd29-e13f-48dd-9a8d-18ba2504b7a4\report_parser_evaluation_zh.pdf"
    
    print(f"Reading: {target_file}")
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File {target_file} not found.")
        return

    # Create PDF
    doc = SimpleDocTemplate(output_pdf, pagesize=A4)
    styles = getSampleStyleSheet()
    
    # Font Logic
    font_name = register_chinese_font()
    
    # Parse Content
    story = parse_markdown_to_flowables(content, styles, font_name)
    
    # Build
    try:
        doc.build(story)
        print(f"✅ Successfully created PDF: {output_pdf}")
    except Exception as e:
        print(f"❌ PDF Generation Failed: {e}")

if __name__ == "__main__":
    main()
