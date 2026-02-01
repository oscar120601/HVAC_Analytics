from xhtml2pdf import pisa
from pathlib import Path

def convert_html_to_pdf(source_html, output_filename):
    # open output file for writing (truncated binary)
    with open(output_filename, "wb") as result_file:
        # convert HTML to PDF
        with open(source_html, "r", encoding='utf-8') as f:
            source_html_content = f.read()
            
        # Add support for Chinese fonts (using a system font if possible, or fallback)
        # xhtml2pdf needs explicit font definition for non-latin characters.
        # This is a basic attempt. If it fails to render Chinese specific fonts, 
        # it might show squares.
        # For Mac, we can try to point to a font.
        
        style = """
        <style>
            @page { size: A4; margin: 1cm; }
            body { font-family: "Heiti TC", "PingFang TC", sans-serif; }
        </style>
        """
        # Inject style
        source_html_content = source_html_content.replace('</head>', f'{style}</head>')

        pisa_status = pisa.CreatePDF(
            source_html_content,                # the HTML to convert
            dest=result_file)           # file handle to recieve result

    # return True on success and False on errors
    return pisa_status.err

html_file = '/Users/chanoscar/antigravity/HVAC_Analytics/phase1_progress_report.html'
pdf_file = '/Users/chanoscar/antigravity/HVAC_Analytics/phase1_progress_report.pdf'

if convert_html_to_pdf(html_file, pdf_file) == 0:
    print(f"Successfully created PDF at {pdf_file}")
else:
    print("Failed to create PDF")
