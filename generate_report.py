#!/usr/bin/env python3
"""
Generate HTML and PDF reports from Markdown progress report
"""

import markdown
from pathlib import Path

# Read the markdown file
md_file = Path('/Users/chanoscar/.gemini/antigravity/brain/cf0a4553-5d4d-47d7-a4ff-a54dacc96004/phase1_progress_report.md')
with open(md_file, 'r', encoding='utf-8') as f:
    md_content = f.read()

# Convert markdown to HTML
md = markdown.Markdown(extensions=['tables', 'fenced_code', 'toc'])
html_body = md.convert(md_content)

# Create professional HTML with CSS styling
html_template = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HVAC Analytics ETL Pipeline - Phase 1 進度報告</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700&display=swap');
        
        body {{
            font-family: 'Noto Sans TC', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            line-height: 1.8;
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 20px;
            background: #f5f7fa;
            color: #2c3e50;
        }}
        
        .container {{
            background: white;
            padding: 60px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        
        h1 {{
            color: #1a202c;
            border-bottom: 4px solid #3182ce;
            padding-bottom: 20px;
            margin-bottom: 30px;
            font-size: 2.5em;
            font-weight: 700;
        }}
        
        h2 {{
            color: #2d3748;
            margin-top: 50px;
            margin-bottom: 20px;
            font-size: 1.8em;
            font-weight: 600;
            border-left: 5px solid #3182ce;
            padding-left: 15px;
        }}
        
        h3 {{
            color: #4a5568;
            margin-top: 30px;
            margin-bottom: 15px;
            font-size: 1.3em;
            font-weight: 500;
        }}
        
        h4 {{
            color: #718096;
            margin-top: 20px;
            margin-bottom: 10px;
            font-size: 1.1em;
        }}
        
        p {{
            margin-bottom: 15px;
            color: #4a5568;
        }}
        
        strong {{
            color: #2d3748;
            font-weight: 600;
        }}
        
        ul, ol {{
            margin-bottom: 20px;
            padding-left: 30px;
        }}
        
        li {{
            margin-bottom: 8px;
            color: #4a5568;
        }}
        
        code {{
            background: #f7fafc;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            color: #c7254e;
        }}
        
        pre {{
            background: #2d3748;
            color: #e2e8f0;
            padding: 20px;
            border-radius: 8px;
            overflow-x: auto;
            margin: 20px 0;
        }}
        
        pre code {{
            background: none;
            color: #e2e8f0;
            padding: 0;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }}
        
        th {{
            background: #edf2f7;
            color: #2d3748;
            font-weight: 600;
        }}
        
        hr {{
            border: none;
            border-top: 2px solid #e2e8f0;
            margin: 40px 0;
        }}
        
        .meta {{
            color: #718096;
            font-size: 0.95em;
            margin-bottom: 30px;
            padding: 15px;
            background: #f7fafc;
            border-radius: 6px;
        }}
        
        .status-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 500;
            margin-left: 10px;
        }}
        
        .status-success {{
            background: #c6f6d5;
            color: #22543d;
        }}
        
        .status-warning {{
            background: #feebc8;
            color: #7c2d12;
        }}
        
        @media print {{
            body {{
                background: white;
            }}
            .container {{
                box-shadow: none;
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        {html_body}
    </div>
</body>
</html>
"""

# Save HTML file
html_file = Path('/Users/chanoscar/antigravity/HVAC_Analytics/phase1_progress_report.html')
with open(html_file, 'w', encoding='utf-8') as f:
    f.write(html_template)

print(f"✅ HTML 報告已生成: {html_file}")
print(f"   可在瀏覽器中打開，或列印為 PDF")

# Try to generate PDF using weasyprint
try:
    from weasyprint import HTML
    pdf_file = Path('/Users/chanoscar/antigravity/HVAC_Analytics/phase1_progress_report.pdf')
    HTML(string=html_template).write_pdf(pdf_file)
    print(f"✅ PDF 報告已生成: {pdf_file}")
except ImportError:
    print("⚠️  未安裝 weasyprint，無法生成 PDF")
    print("   但您可以在瀏覽器打開 HTML 後，使用「列印」功能儲存為 PDF")
except Exception as e:
    print(f"⚠️  PDF 生成錯誤: {e}")
    print("   但您可以在瀏覽器打開 HTML 後，使用「列印」功能儲存為 PDF")
