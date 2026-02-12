
import sys
import os
import markdown
from pathlib import Path

def convert_md_to_html(md_path, html_path):
    print(f"Reading: {md_path}")
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except FileNotFoundError:
        print(f"Error: File {md_path} not found.")
        return

    # Convert to HTML
    html_content = markdown.markdown(text, extensions=['tables', 'fenced_code', 'toc'])

    # Wrap in a clean template with CSS
    template = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HVAC Analytics PRD</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";
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
        table {{
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 20px;
        }}
        th, td {{
            border: 1px solid #dfe2e5;
            padding: 12px;
            text-align: left;
        }}
        th {{ background-color: #f6f8fa; }}
        tr:nth-child(even) {{ background-color: #fdfdfd; }}
        code {{
            background-color: #f3f3f3;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
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
        .important {{
            background-color: #fff9db;
            padding: 10px;
            border-left: 5px solid #fcc419;
            margin: 10px 0;
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
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(template)
    print(f"✅ Successfully created HTML: {html_path}")

def main():
    target_file = r"d:\12.任務\HVAC-1\docs\evaluation\PRD.md"
    output_html = r"d:\12.任務\HVAC-1\docs\evaluation\PRD.html"
    
    convert_md_to_html(target_file, output_html)

if __name__ == "__main__":
    main()
