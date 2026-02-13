import os
import markdown
import codecs
from pathlib import Path

# Configuration
DOCS_ROOT = Path(r"D:\12.任務\HVAC-1\docs")
EXCLUDE_DIRS = {"_archive", ".git", ".idea", ".vscode", "__pycache__"}
CSS_STYLE = """
<style>
    body { 
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; 
        line-height: 1.6; 
        max-width: 900px; 
        margin: 0 auto; 
        padding: 40px 20px; 
        color: #24292e; 
        background-color: #ffffff;
    }
    h1, h2, h3, h4, h5, h6 { 
        margin-top: 24px; 
        margin-bottom: 16px; 
        font-weight: 600; 
        color: #24292e;
    }
    h1 { font-size: 2em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }
    h2 { font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }
    h3 { font-size: 1.25em; }
    p { margin-top: 0; margin-bottom: 16px; }
    a { color: #0366d6; text-decoration: none; }
    a:hover { text-decoration: underline; }
    table { 
        display: block; 
        width: 100%; 
        overflow: auto; 
        border-spacing: 0; 
        border-collapse: collapse; 
        margin-bottom: 16px; 
    }
    table th, table td { 
        padding: 6px 13px; 
        border: 1px solid #dfe2e5; 
    }
    table th { 
        font-weight: 600; 
        background-color: #f6f8fa; 
    }
    table tr:nth-child(2n) { 
        background-color: #f6f8fa; 
    }
    code { 
        font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace; 
        background-color: #f6f8fa; 
        padding: 0.2em 0.4em; 
        border-radius: 3px; 
        font-size: 85%; 
    }
    pre { 
        background-color: #f6f8fa; 
        padding: 16px; 
        overflow: auto; 
        border-radius: 3px; 
        line-height: 1.45; 
    }
    pre code { 
        background-color: transparent; 
        padding: 0; 
        border-radius: 0; 
    }
    blockquote { 
        border-left: 0.25em solid #dfe2e5; 
        color: #6a737d; 
        padding: 0 1em; 
        margin: 0 0 16px 0; 
    }
    hr {
        height: 0.25em;
        padding: 0;
        margin: 24px 0;
        background-color: #e1e4e8;
        border: 0;
    }
    .mermaid {
        display: flex;
        justify-content: center;
        margin: 20px 0;
    }
</style>
"""

MERMAID_SCRIPT = """
<script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    mermaid.initialize({ startOnLoad: true });
</script>
"""

def convert_to_html(md_path):
    try:
        with codecs.open(md_path, mode="r", encoding="utf-8") as f:
            text = f.read()
            
        # Convert Markdown to HTML
        html_content = markdown.markdown(
            text, 
            extensions=['extra', 'codehilite', 'toc', 'tables', 'fenced_code']
        )
        
        # Determine output path
        output_path = md_path.with_suffix('.html')
        
        # Wrap in HTML template
        full_html = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{md_path.stem}</title>
    {CSS_STYLE}
</head>
<body>
    {html_content}
    {MERMAID_SCRIPT}
</body>
</html>
"""
        
        with codecs.open(output_path, "w", encoding="utf-8", errors="xmlcharrefreplace") as f:
            f.write(full_html)
            
        print(f"Generated: {output_path}")
        return True
        
    except Exception as e:
        print(f"Failed to convert {md_path}: {e}")
        return False

def main():
    print(f"Scanning {DOCS_ROOT} for PRD markdown files...")
    
    count = 0
    for root, dirs, files in os.walk(DOCS_ROOT):
        # Filter directories in-place to skip _archive
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            if file.endswith(".md") and file.startswith("PRD_"):
                md_path = Path(root) / file
                if convert_to_html(md_path):
                    count += 1
                    
    print(f"Conversion complete. {count} files generated.")

if __name__ == "__main__":
    main()
