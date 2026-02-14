import os
import markdown
from pathlib import Path
import sys

# Simple CSS for better readability
CSS_STYLE = """
<style>
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
    font-size: 16px;
    line-height: 1.5;
    word-wrap: break-word;
    color: #24292e;
    background-color: #fff;
    max-width: 900px;
    margin: 0 auto;
    padding: 2rem;
}
h1, h2, h3, h4, h5, h6 {
    margin-top: 24px;
    margin-bottom: 16px;
    font-weight: 600;
    line-height: 1.25;
}
h1 { font-size: 2em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }
h2 { font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }
h3 { font-size: 1.25em; }
code {
    padding: 0.2em 0.4em;
    margin: 0;
    font-size: 85%;
    background-color: #f6f8fa;
    border-radius: 6px;
    font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
}
pre {
    padding: 16px;
    overflow: auto;
    font-size: 85%;
    line-height: 1.45;
    background-color: #f6f8fa;
    border-radius: 6px;
}
pre code {
    display: inline;
    padding: 0;
    margin: 0;
    overflow: visible;
    line-height: inherit;
    word-wrap: normal;
    background-color: initial;
    border: 0;
}
blockquote {
    padding: 0 1em;
    color: #6a737d;
    border-left: 0.25em solid #dfe2e5;
    margin: 0;
}
table {
    display: block;
    width: 100%;
    margin-top: 0;
    margin-bottom: 16px;
    overflow: auto;
    border-spacing: 0;
    border-collapse: collapse;
}
table th, table td {
    padding: 6px 13px;
    border: 1px solid #dfe2e5;
}
table tr {
    background-color: #fff;
    border-top: 1px solid #c6cbd1;
}
table tr:nth-child(2n) {
    background-color: #f6f8fa;
}
a { color: #0366d6; text-decoration: none; }
a:hover { text-decoration: underline; }
hr {
    height: 0.25em;
    padding: 0;
    margin: 24px 0;
    background-color: #e1e4e8;
    border: 0;
}
</style>
"""

def convert_md_to_html(docs_dir: str):
    """Recursively convert all .md files in docs_dir to .html"""
    root_path = Path(docs_dir)
    if not root_path.exists():
        print(f"Error: Directory {docs_dir} not found.")
        sys.exit(1)

    print(f"Scanning {docs_dir} for Markdown files...")
    
    count = 0
    for md_file in root_path.rglob("*.md"):
        try:
            # Read Markdown
            with open(md_file, 'r', encoding='utf-8') as f:
                text = f.read()
            
            # Convert to HTML
            # Using extra extensions for tables, fenced code blocks, etc.
            html_body = markdown.markdown(text, extensions=['tables', 'fenced_code', 'toc', 'nl2br', 'sane_lists'])
            
            # Wrap in HTML template
            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{md_file.stem}</title>
{CSS_STYLE}
</head>
<body>
{html_body}
</body>
</html>"""
            
            # Write HTML
            html_file = md_file.with_suffix('.html')
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
            print(f"Converted: {md_file.name} -> {html_file.name}")
            count += 1
            
        except Exception as e:
            print(f"Failed to convert {md_file}: {e}")

    print(f"\nSuccessfully converted {count} files.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Convert docs Markdown to HTML")
    parser.add_argument("--dir", default="docs", help="Directory containing markdown files")
    args = parser.parse_args()
    
    convert_md_to_html(args.dir)
