"""
Generate professional HTML from the project scheduling markdown document.
Usage: python tools/docs/generate_schedule_html.py
"""
import markdown
from pathlib import Path

MD_PATH = Path(__file__).resolve().parents[2] / "docs" / "專案任務排程" / "專案任務排程文件.md"
OUT_PATH = MD_PATH.with_suffix(".html")

CSS_STYLE = """
<style>
:root { --primary: #1a73e8; --bg: #f8f9fa; --card: #fff; --text: #24292e; --border: #e1e4e8; --accent: #0d6efd; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Microsoft JhengHei", "Segoe UI", sans-serif; font-size: 15px; line-height: 1.65; color: var(--text); background: var(--bg); }
.container { max-width: 1100px; margin: 0 auto; padding: 2rem; }
.header { background: linear-gradient(135deg, #1a73e8, #0d47a1); color: white; padding: 2.5rem 2rem; margin-bottom: 2rem; border-radius: 12px; box-shadow: 0 4px 12px rgba(26,115,232,0.3); }
.header h1 { font-size: 2em; margin-bottom: 0.5rem; border: none; color: white; padding: 0; }
.header .meta { opacity: 0.85; font-size: 0.9em; }
h1 { font-size: 1.8em; color: var(--primary); border-bottom: 2px solid var(--primary); padding-bottom: 0.4em; margin: 2rem 0 1rem; }
h2 { font-size: 1.4em; color: #333; border-bottom: 1px solid var(--border); padding-bottom: 0.3em; margin: 1.8rem 0 1rem; }
h3 { font-size: 1.2em; color: #444; margin: 1.5rem 0 0.8rem; }
h4 { font-size: 1.05em; color: #555; margin: 1.2rem 0 0.6rem; }
p { margin: 0.5rem 0; }
table { width: 100%; border-collapse: collapse; margin: 1rem 0 1.5rem; background: var(--card); border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); display: table; }
th { background: #e8f0fe; color: #1a56a0; font-weight: 600; text-align: center; padding: 10px 12px; border: 1px solid #d0d7de; font-size: 0.9em; }
td { padding: 8px 12px; border: 1px solid #d0d7de; font-size: 0.88em; vertical-align: top; }
tr:nth-child(2n) { background: #f6f8fa; }
tr:hover { background: #e8f0fe; transition: background 0.2s; }
code { padding: 0.2em 0.4em; font-size: 85%; background: #eff1f3; border-radius: 4px; font-family: Consolas, "Courier New", monospace; color: #d63384; }
pre { padding: 16px; background: #1e1e1e; color: #d4d4d4; border-radius: 8px; overflow-x: auto; margin: 1rem 0; line-height: 1.45; }
pre code { background: none; color: inherit; padding: 0; font-size: 90%; }
blockquote { border-left: 4px solid var(--primary); padding: 0.8rem 1.2rem; margin: 1rem 0; background: #e8f0fe; border-radius: 0 6px 6px 0; }
hr { border: none; height: 1px; background: var(--border); margin: 2rem 0; }
ul, ol { padding-left: 2em; margin: 0.5rem 0; }
li { margin: 0.3rem 0; }
strong { color: #1a56a0; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.mermaid { background: white; padding: 1.5rem; border-radius: 8px; margin: 1rem 0; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.footer { text-align: center; padding: 2rem; color: #6c757d; font-size: 0.85em; border-top: 1px solid var(--border); margin-top: 3rem; }
@media print {
    body { background: white; font-size: 12px; }
    .container { max-width: 100%; padding: 1rem; }
    .header { box-shadow: none; }
    table { box-shadow: none; }
    pre { background: #f6f8fa; color: #24292e; }
}
</style>
"""


def convert():
    text = MD_PATH.read_text(encoding="utf-8")

    # Convert markdown to HTML
    html_body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "toc", "sane_lists"],
    )

    # Enable Mermaid rendering for mermaid code blocks
    html_body = html_body.replace(
        '<code class="language-mermaid">',
        '</code></pre><div class="mermaid">',
    )
    # Close the mermaid divs properly
    import re
    html_body = re.sub(
        r'</code></pre><div class="mermaid">(.*?)</code>\s*</pre>',
        r'<div class="mermaid">\1</div>',
        html_body,
        flags=re.DOTALL,
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HVAC-1 專案任務排程文件 v1.3</title>
{CSS_STYLE}
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({{startOnLoad:true, theme:"default"}});</script>
</head>
<body>
<div class="container">
<div class="header">
<h1>HVAC-1 專案任務排程文件</h1>
<div class="meta">📋 版本 v1.3 | 📅 最後更新: 2026-02-23 | ✅ Sprint 1 已完成 (3/3) | 🆕 新增 Demo 展示任務</div>
</div>
{html_body}
<div class="footer">
HVAC-1 專案任務排程文件 v1.3 &copy; 2026 | 自動產生於 2026-02-23
</div>
</div>
</body>
</html>"""

    OUT_PATH.write_text(html, encoding="utf-8")
    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"✅ HTML generated: {OUT_PATH}")
    print(f"   Size: {size_kb:.1f} KB")


if __name__ == "__main__":
    convert()
