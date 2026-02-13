import markdown
from pathlib import Path

def convert():
    md_path = Path(r"d:\12.任務\HVAC-1\docs\feature_engineering\PRD_FEATURE_ENGINEER_V1.1.md")
    html_path = Path(r"d:\12.任務\HVAC-1\docs\feature_engineering\PRD_FEATURE_ENGINEER_V1.1.html")
    
    # Ensure output directory exists
    html_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not md_path.exists():
        print(f"Error: {md_path} not found")
        return
        
    text = md_path.read_text(encoding='utf-8')
    html_content = markdown.markdown(text, extensions=['tables', 'fenced_code', 'toc'])
    
    template = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Feature Engineering PRD v1.1</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 20px;
            background-color: #f8f9fa;
        }}
        .container {{
            background-color: #fff;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        h1, h2, h3 {{ border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }}
        h2 {{ margin-top: 2em; }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #dfe2e5;
            padding: 12px;
            text-align: left;
        }}
        th {{ background-color: #f6f8fa; font-weight: bold; }}
        tr:nth-child(even) {{ background-color: #fdfdfd; }}
        code {{
            background-color: #f3f3f3;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 85%;
        }}
        pre {{
            background-color: #f6f8fa;
            padding: 16px;
            overflow: auto;
            border-radius: 6px;
        }}
        blockquote {{
            margin: 0;
            padding: 0 1em;
            color: #6a737d;
            border-left: 0.25em solid #dfe2e5;
        }}
    </style>
</head>
<body>
    <div class="container">
        {html_content}
    </div>
</body>
</html>
"""
    html_path.write_text(template, encoding='utf-8')
    print(f"Successfully created: {html_path}")

if __name__ == "__main__":
    convert()
