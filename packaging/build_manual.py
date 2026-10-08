"""Build a self-contained offline manual from the project's Markdown source."""
from pathlib import Path
import html
import re

ROOT = Path(__file__).resolve().parents[1]


def inline(text):
    parts = re.split(r'(`[^`]+`)', text)
    for i, part in enumerate(parts):
        if part.startswith('`') and part.endswith('`'):
            parts[i] = '<code>' + html.escape(part[1:-1]) + '</code>'
        else:
            parts[i] = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html.escape(part))
    return ''.join(parts)


def build():
    lines = (ROOT / 'docs' / '用户使用说明书.md').read_text(encoding='utf-8').splitlines()
    chapters = [line[3:] for line in lines if re.match(r'^## \d+\.', line)]
    anchors = {title: f'chapter-{index}' for index, title in enumerate(chapters, 1)}
    links = ''.join(f'<li><a href="#{anchors[title]}">{html.escape(title)}</a></li>' for title in chapters)
    body = []
    index = 0
    section_open = False
    while index < len(lines):
        line = lines[index]
        if line == '## 目录':
            index += 1
            while index < len(lines) and not lines[index].startswith('## '):
                index += 1
            continue
        if not line.strip():
            index += 1
            continue
        if line.startswith('```'):
            code = []
            index += 1
            while index < len(lines) and not lines[index].startswith('```'):
                code.append(lines[index])
                index += 1
            body.append('<pre><code>' + html.escape('\n'.join(code)) + '</code></pre>')
            index += 1
            continue
        if line.startswith('|'):
            rows = []
            while index < len(lines) and lines[index].startswith('|'):
                cells = [cell.strip() for cell in lines[index].strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?', cell) for cell in cells):
                    rows.append(cells)
                index += 1
            body.append('<div class="table-wrap"><table><thead><tr>' + ''.join('<th scope="col">' + inline(cell) + '</th>' for cell in rows[0]) + '</tr></thead><tbody>')
            for row in rows[1:]:
                body.append('<tr>' + ''.join('<td>' + inline(cell) + '</td>' for cell in row) + '</tr>')
            body.append('</tbody></table></div>')
            continue
        heading = re.match(r'^(#{1,3}) (.+)$', line)
        if heading:
            level, title = len(heading[1]), heading[2]
            if level == 2:
                if section_open:
                    body.append('<a class="back" href="#toc">↑ 返回目录</a></section>')
                body.append(f'<section id="{anchors[title]}">')
                section_open = True
            body.append(f'<h{level}>' + inline(title) + f'</h{level}>')
            index += 1
            continue
        if re.match(r'^(?:- |\d+\. )', line):
            ordered = not line.startswith('- ')
            tag = 'ol' if ordered else 'ul'
            body.append(f'<{tag}>')
            pattern = r'^\d+\. ' if ordered else r'^- '
            while index < len(lines) and re.match(pattern, lines[index]):
                body.append('<li>' + inline(re.sub(pattern, '', lines[index])) + '</li>')
                index += 1
            body.append(f'</{tag}>')
            continue
        paragraph = []
        while index < len(lines) and lines[index].strip() and not re.match(r'^(?:#|```|\||- |\d+\. )', lines[index]):
            paragraph.append(inline(lines[index].rstrip()))
            hard_break = lines[index].endswith('  ')
            index += 1
            if hard_break:
                paragraph.append('<br>')
        body.append('<p>' + '\n'.join(paragraph) + '</p>')
    if section_open:
        body.append('<a class="back" href="#toc">↑ 返回目录</a></section>')
    document = '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>YiRead · 译·读 用户使用说明书</title>
<style>
:root{color-scheme:light;--ink:#233044;--blue:#245a92;--line:#dce3eb}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}
body{margin:0;background:#f4f6f9;color:var(--ink);font:16px/1.85 "Segoe UI","Microsoft YaHei",sans-serif}
a{color:var(--blue);text-underline-offset:3px}a:focus-visible{outline:3px solid #e6a23c;outline-offset:4px}
.layout{max-width:1340px;margin:auto;display:grid;grid-template-columns:290px minmax(0,1fr);gap:28px;padding:28px}
nav{position:sticky;top:24px;align-self:start;max-height:calc(100vh - 48px);overflow:auto;background:white;border:1px solid var(--line);border-radius:12px;padding:20px}
nav h2{margin:0 0 10px;font-size:20px}nav ol{list-style:none;padding:0;margin:0}nav li{margin:0}nav a{display:block;text-decoration:none;padding:7px 9px;border-radius:6px;font-size:14px;line-height:1.6}nav a:hover{background:#edf3fa}
main{min-width:0;background:white;border:1px solid var(--line);border-radius:12px;padding:32px 40px}
h1{font-size:30px;line-height:1.5;margin-top:0}h2{font-size:24px;line-height:1.6;margin:0 0 18px}h3{font-size:19px;margin:26px 0 10px}p{margin:12px 0}
section{border-top:1px solid var(--line);margin-top:34px;padding-top:28px}li{margin:7px 0}
code{font-family:Consolas,monospace;background:#f0f3f7;border-radius:4px;padding:2px 5px;overflow-wrap:anywhere;font-size:.92em}pre{background:#f0f3f7;padding:16px;border-radius:8px;overflow:auto;line-height:1.6}pre code{padding:0;white-space:pre;overflow-wrap:normal}
.table-wrap{overflow:auto;margin:18px 0}table{border-collapse:collapse;width:100%;min-width:440px;font-size:14px}th,td{border:1px solid var(--line);padding:10px 12px;text-align:left;vertical-align:top}th{background:#edf3fa}tr:nth-child(even){background:#fafbfd}
.back{display:inline-block;margin-top:18px;font-size:14px}.floating{position:fixed;bottom:20px;right:20px;background:var(--blue);color:white;padding:9px 16px;border-radius:24px;text-decoration:none;box-shadow:0 2px 8px #0002}
@media(max-width:850px){.layout{grid-template-columns:1fr;padding:14px;gap:16px}nav{position:static;max-height:none}main{padding:24px 20px}h1{font-size:25px}.floating{bottom:12px;right:12px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
@media print{body{background:white}.layout{display:block;padding:0}nav{position:static;max-height:none;border:0;page-break-after:always}main{border:0;padding:0}.floating,.back{display:none}section{break-before:auto}h2,h3{break-after:avoid}pre{white-space:pre-wrap}a{color:inherit}}
</style></head><body><div class="layout"><nav id="toc" aria-label="使用说明书目录"><h2>使用说明书目录</h2><ol>''' + links + '''</ol></nav><main>''' + '\n'.join(body) + '''</main></div><a class="floating" href="#toc">↑ 目录</a></body></html>'''
    output = ROOT / 'docs' / '用户使用说明书.html'
    output.write_text(document, encoding='utf-8')
    print(output)


if __name__ == '__main__':
    build()
