#!/usr/bin/env python3
"""生成 A4 排版的 PDF 版（打印友好，静态无 JS）。

用法：  python3 tools/build_pdf.py
产物：  高性价比新手小白健身指南.pdf（项目根目录）

路线：先用 refs 解析出全书，拼一份「打印专用」HTML（没有侧栏、没有搜索、没有 JS，
分页由 CSS @page / break-before 控制），再调 Chrome headless 打印成 PDF。

为什么不用 pandoc：pandoc 出 PDF 需要 LaTeX 引擎（本机没有 xelatex，而且中文字体
配置麻烦）。Chrome headless 直接吃 CSS + 系统字体（PingFang / Songti），
中文和分页都稳。

注意：
· Chrome 打印时会自带页眉页脚（URL、日期、页码），用 --no-pdf-header-footer 关掉，
  换成自己排的页脚——但 CSS 的 @bottom-center 计数器 Chrome 不认，所以页码只能靠
  Chrome 自带的（难看）或者不要。这里选择不要页码，靠目录里的内部链接跳转。
· 目录里的条目和正文里的「第 N 条」都是 PDF 内部跳转链接，点得动。
"""
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refs  # noqa: E402
from build_web import (  # noqa: E402  复用网页版那套 markdown → HTML 渲染
    FIELDS, esc, md_block, inline, link_cites,
)

ROOT = refs.ROOT
OUT = os.path.join(ROOT, "高性价比新手小白健身指南.pdf")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = """
@page { size: A4; margin: 19mm 17mm 17mm; }

* { box-sizing: border-box; }
body {
  margin: 0;
  font: 10.5pt/1.78 "Songti SC", "STSong", "PingFang SC", serif;
  color: #1c1a17;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
h1, h2, h3, h4, .lv, .k, .cover-meta { font-family: "PingFang SC", "Hiragino Sans GB", sans-serif; }

/* ── 封面 ── */
.cover { height: 245mm; display: flex; flex-direction: column; justify-content: center;
         page-break-after: always; }
.cover h1 { font-size: 30pt; font-weight: 700; letter-spacing: -0.5pt; margin: 0 0 10mm;
            line-height: 1.28; }
.cover .sub { font-size: 11pt; color: #4a463f; line-height: 1.85; margin: 0 0 8mm;
              max-width: 145mm; }
.cover .sub p { margin: 0 0 3mm; }
.cover-meta { font-size: 9.5pt; color: #6f6a61; letter-spacing: 0.3pt; }
.cover .rule { width: 42mm; height: 2.6pt; background: #1a6b4a; margin: 0 0 9mm; }

/* ── 免责声明页 ── */
.disc { page-break-after: always; font-size: 9.8pt; color: #4a463f; line-height: 1.85; }
.disc .disc-h { font-family: "PingFang SC", sans-serif; font-size: 12pt; font-weight: 700;
                color: #1c1a17; margin: 0 0 5mm; }
.disc p { margin: 0 0 3.2mm; }
.disc b { color: #1c1a17; }

/* ── 目录 ── */
.toc { page-break-after: always; }
.toc h2 { font-size: 17pt; margin: 0 0 7mm; }
.toc .sec { margin: 0 0 5mm; }
.toc .sec-line { font-size: 11pt; font-weight: 700; margin: 0 0 1.6mm; }
.toc .sec-line a { color: #1c1a17; text-decoration: none; }
.toc .th { font-size: 9.6pt; color: #4a463f; margin: 0 0 1mm; line-height: 1.7; }
.toc .th b { color: #1a6b4a; font-weight: 700; }

/* ── 关注作者 / 版权页 ── */
.about { page-break-after: always; }
.about h2 { font-size: 17pt; margin: 0 0 6mm; }
.about .qr { float: right; width: 42mm; margin: 0 0 4mm 7mm; }
.about .qr img { width: 100%; border: 0.6pt solid #e6e2db; border-radius: 2mm; }
.about .qr figcaption { font-size: 8pt; color: #8b857a; text-align: center; margin-top: 1.5mm; }
.about p { font-size: 10pt; line-height: 1.85; margin: 0 0 3mm; }
.about .kv { font-size: 10pt; margin: 0 0 1.6mm; }
.about .kv b { font-family: "PingFang SC", sans-serif; color: #1a6b4a; }
.about a { color: #1a6b4a; text-decoration: none; }
.about .lic { margin-top: 7mm; padding-top: 4mm; border-top: 0.6pt solid #e6e2db; }
.about .lic ul { margin: 1mm 0 0; padding-left: 5mm; font-size: 9.4pt; line-height: 1.8; }
.about .copy { margin-top: 6mm; font-size: 9.6pt; color: #4a463f; }
.about .copy b { font-family: "PingFang SC", sans-serif; }

/* ── 正文 ── */
section.sec { page-break-before: always; }
section.sec:first-of-type { page-break-before: auto; }
h2.sec-h { font-size: 19pt; font-weight: 700; margin: 0 0 3mm; letter-spacing: -0.3pt; }
.sec-sub { font-size: 9pt; color: #6f6a61; margin: 0 0 6mm;
           padding-bottom: 3mm; border-bottom: 0.8pt solid #ddd8cf; }
.intro { font-size: 10.2pt; line-height: 1.85; color: #1c1a17; margin: 0 0 7mm; }
.intro p { margin: 0 0 3mm; }

h3.theme { font-size: 13pt; font-weight: 700; color: #1a6b4a; margin: 8mm 0 3mm;
           page-break-after: avoid; }

article.card { margin: 0 0 5mm; page-break-inside: auto; }
article.card h4 { font-size: 11.6pt; font-weight: 700; margin: 0 0 2.4mm; line-height: 1.5;
                  page-break-after: avoid; }
article.card h4 .lv { display: inline-block; min-width: 5mm; padding: 0 1mm; margin-right: 2mm;
                      font-size: 8pt; font-weight: 700; color: #fff; border-radius: 1.5mm;
                      text-align: center; vertical-align: 1pt; }
article.card h4 .lv.A { background: #1a6b4a; }
article.card h4 .lv.B { background: #9a6b1a; }
article.card h4 .lv.C { background: #7a5c8a; }

.f { display: flex; gap: 2.5mm; margin: 0 0 1.8mm; font-size: 9.9pt; line-height: 1.78; }
.f .k { flex: none; width: 18mm; font-size: 8.4pt; color: #8b857a; padding-top: 0.7mm; }
.f .v { flex: 1; min-width: 0; }
.f.hl .v { background: #f2f7f4; border-left: 1.4pt solid #1a6b4a; padding: 2mm 3mm; }
.f.src { font-size: 8.5pt; color: #9b968b; }
.f.src .v a { color: inherit; text-decoration: none; }
.f.src .v br { line-height: 0.4; }

.f ul { margin: 0.4mm 0 0; padding-left: 4.6mm; }
.f li { margin: 0 0 0.5mm; }
.f li::marker { color: #8b857a; }
.f strong { color: #1c1a17; }
.f a { color: #1a6b4a; text-decoration: none; }

table { width: 100%; border-collapse: collapse; font-size: 9.2pt; margin: 2mm 0; }
th, td { border: 0.6pt solid #ddd8cf; padding: 1.4mm 2mm; text-align: left; vertical-align: top; }
th { background: #f6f4f0; font-family: "PingFang SC", sans-serif; font-weight: 600; }

.foot { margin-top: 10mm; padding-top: 3mm; border-top: 0.6pt solid #e6e2db;
        font-size: 8.5pt; color: #9b968b; }
"""


def readme_block(title):
    """从 README.md 里取某节（## 标题 到下一个 ## 之间）的内容。"""
    path = os.path.join(ROOT, "README.md")
    if not os.path.exists(path):
        return ""
    t = open(path, encoding="utf-8").read()
    m = re.search(r"(?m)^## " + re.escape(title) + r"\s*$(.*?)(?=^## |\Z)", t, re.S)
    return m.group(1).strip() if m else ""


def about_page():
    """「关注作者 / 版权」页。内容全部取自 README，改 README 就跟着变。"""
    follow = readme_block("关注作者")
    lic = readme_block("许可")
    if not follow and not lic:
        return ""

    # 二维码：README 里写的是 <img src="assets/douyin-card.jpg">，
    # 打印时换成 file:// 绝对路径，Chrome 才读得到本地图。
    qr_html = ""
    for m in re.finditer(r'<img[^>]*src="([^"]+)"[^>]*>', follow):
        src = m.group(1)
        abs_path = os.path.join(ROOT, src)
        cap = "抖音号 DoufuQS"
        if os.path.exists(abs_path):
            qr_html = (f'<figure class="qr"><img src="file://{abs_path}" alt="抖音账号名片">'
                       f'<figcaption>{cap}</figcaption></figure>')
        follow = follow.replace(m.group(0), "")

    def para(s):
        s = s.strip()
        if not s or s == "---" or s.startswith("<"):
            return ""
        if s.startswith(("- ", "* ")):
            s2 = re.sub(r"^[-*]\s+", "", s)
            return f'<div class="kv">· {inline(s2)}</div>'
        if s.startswith(">"):
            return f'<p style="color:#6f6a61">{inline(s.lstrip("> ").strip())}</p>'
        return f"<p>{inline(s)}</p>"

    follow_html = "".join(para(l) for l in follow.split("\n"))
    lic_html = "".join(para(l) for l in lic.split("\n"))

    return (f'<div class="about"><h2>关注作者 · 版权</h2>{qr_html}'
            f'{follow_html}'
            f'<div class="lic">{lic_html}</div></div>')


def cite_links(html, cur):
    """把正文里的「第 N 条」变成 PDF 内部跳转链接（href="#c-节-条"）。"""
    def f(m):
        sec = int(m.group(1)) if m.group(1) else cur
        no = m.group(2)
        return f'<a href="#c-{sec}-{no}">{m.group(0)}</a>'
    return RE_CITE.sub(f, html)


RE_CITE = re.compile(r"(?:(\d{1,2})\s*节\s*)?第\s*(\d+\s*(?:[、,，]\s*\d+\s*)*)条")


def render_field(it, f, idx):
    val = str(it.get(f, "") or "")
    if f == "来源":
        if not val.strip() or val.strip() == "无":
            return ""
        body = "<br>".join(inline(l.strip()) for l in val.split("\n") if l.strip())
        return f'<div class="f src"><div class="k">来源</div><div class="v">{body}</div></div>'
    multi = f in ("具体地", "为什么", "总结性建议") and "\n" in val
    body = md_block(val) if multi else inline(val.replace("\n", " ").strip())
    body = cite_links(body, it["sec_no"])
    if f == "总结性建议":
        return f'<div class="f hl"><div class="v">{body}</div></div>'
    return f'<div class="f"><div class="k">{f}</div><div class="v">{body}</div></div>'


def _need_pymupdf():
    """页码靠 pymupdf 盖章。当前解释器没装的话，自动切到项目里的 .venv 重跑一遍。"""
    try:
        import pymupdf  # noqa: F401
        return
    except ImportError:
        venv = os.path.join(ROOT, ".venv", "bin", "python")
        if os.path.exists(venv) and not os.environ.get("_PDF_VENV"):
            os.environ["_PDF_VENV"] = "1"
            os.execv(venv, [venv, os.path.abspath(__file__)] + sys.argv[1:])
        raise


def stamp_pages(pdf_path):
    """给每页盖页码。封面不盖。页脚居中「3 / 52」，浅灰 8pt。"""
    import pymupdf
    doc = pymupdf.open(pdf_path)
    n = doc.page_count
    for i, page in enumerate(doc):
        if i == 0:                      # 封面不盖
            continue
        label = f"{i + 1} / {n}"
        w = pymupdf.get_text_length(label, fontname="helv", fontsize=8)
        page.insert_text(((page.rect.width - w) / 2, page.rect.height - 22),
                         label, fontname="helv", fontsize=8,
                         color=(0.66, 0.64, 0.60))
    tmp = pdf_path + ".tmp"
    doc.save(tmp, garbage=3, deflate=True)
    doc.close()
    os.replace(tmp, pdf_path)
    return n


def main():
    try:
        _need_pymupdf()
    except ImportError:
        print("⚠️ 没有 pymupdf，页码会跳过。装一下：")
        print("   python3 -m venv .venv && .venv/bin/pip install pymupdf")
    secs, index, problems = refs.load()
    # 调试用：--only 4 只印第 4 节，--out /tmp/x.pdf 换输出路径
    only = None
    out = OUT
    argv = sys.argv[1:]
    if "--only" in argv:
        only = int(argv[argv.index("--only") + 1])
        secs = [s for s in secs if s["no"] == only]
    if "--out" in argv:
        out = argv[argv.index("--out") + 1]
    if problems:
        for p in problems:
            print("❌", p)
        return 1

    title, lede = "高性价比新手小白健身指南", ""
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read().split("\n")
    if readme and readme[0].startswith("# "):
        title = readme[0][2:].strip()
    # 简介：README 里第一段长文本
    for line in readme[1:]:
        s = line.strip()
        if len(s) > 30 and not s.startswith(("#", "-", ">", "|")):
            lede = md_block(s)
            break
    disc = ""
    d0 = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    m = re.search(r"(?m)^## 免责声明\s*$(.*?)(?=^## |\Z)", d0, re.S)
    if m:
        disc = md_block(m.group(1).strip())

    total = sum(len(s["items"]) for s in secs)
    def _lv(it):
        v = re.sub(r"<[^>]+>", "", str(it.get("主观证据等级", ""))).strip()
        return v if v in ("A", "B", "C") else "B"
    nA = sum(1 for s in secs for i in s["items"] if _lv(i) == "A")
    nB = sum(1 for s in secs for i in s["items"] if _lv(i) == "B")
    nC = sum(1 for s in secs for i in s["items"] if _lv(i) == "C")

    parts = [f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>{esc(title)}</title><style>{CSS}</style></head><body>"""]

    if only:
        pass                       # --only 调试模式：跳过封面 / 免责 / 目录，直接看正文
    else:
        # 封面
        parts.append(f"""<div class="cover">
  <div class="rule"></div>
  <h1>{esc(title)}</h1>
  <div class="sub">{lede}</div>
  <div class="cover-meta">{len(secs)} 节 · {total} 条 · A {nA} / B {nB} / C {nC}</div>
</div>""")

        # 免责声明
        if disc:
            parts.append(f'<div class="disc"><div class="disc-h">免责声明</div>{disc}</div>')

        # 关注作者 / 版权
        ap = about_page()
        if ap:
            parts.append(ap)

        # 目录
        parts.append('<div class="toc"><h2>目录</h2>')
        for s in secs:
            parts.append(f'<div class="sec"><div class="sec-line">'
                         f'<a href="#s{s["no"]}">{s["no"]}. {esc(s["name"])}</a>'
                         f'　<span style="font-weight:400;font-size:9pt;color:#8b857a">'
                         f'{len(s["items"])} 条</span></div>')
            for th in (s.get("themes") or []):
                nos = "、".join(f'<a href="#c-{s["no"]}-{n}" style="color:#4a463f;'
                                f'text-decoration:none">{n}</a>' for n in th["nos"])
                parts.append(f'<div class="th"><b>{esc(th["name"])}</b>　{nos}</div>')
            if not s.get("themes"):
                nos = "、".join(f'<a href="#c-{s["no"]}-{it["no"]}" style="color:#4a463f;'
                                f'text-decoration:none">{it["no"]}</a>' for it in s["items"])
                parts.append(f'<div class="th">　{nos}</div>')
            parts.append("</div>")
        parts.append("</div>")

    # 正文
    for s in secs:
        parts.append(f'<section class="sec" id="s{s["no"]}">')
        parts.append(f'<h2 class="sec-h">{s["no"]}. {esc(s["name"])}</h2>')
        parts.append(f'<div class="sec-sub">{len(s["items"])} 条</div>')
        if s.get("intro"):
            parts.append(f'<div class="intro">{md_block(s["intro"])}</div>')

        # 按主题分块输出（主题名做 h3；没有主题就平铺）
        themes = s.get("themes") or []
        if themes:
            by_no = {it["no"]: it for it in s["items"]}
            for th in themes:
                parts.append(f'<h3 class="theme">{esc(th["name"])}</h3>')
                for n in th["nos"]:
                    it = by_no.get(n)
                    if it:
                        parts.append(render_card(it, index))
        else:
            for it in s["items"]:
                parts.append(render_card(it, index))
        parts.append("</section>")

    parts.append('<div class="foot">本 PDF 由原稿自动生成；站内「第 N 条」和目录都是内部跳转链接，点得动。</div>')
    parts.append("</body></html>")
    html = "\n".join(parts)

    tmp = os.path.join(ROOT, ".print.html")
    open(tmp, "w", encoding="utf-8").write(html)

    if "--html-only" in argv:          # 调试：只生成打印用 HTML，不打印
        print("打印用 HTML →", tmp)
        return 0

    if not os.path.exists(CHROME):
        print("❌ 找不到 Chrome：" + CHROME)
        return 1
    cmd = [CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
           "--virtual-time-budget=8000",
           f"--print-to-pdf={out}", "file://" + tmp]
    r = subprocess.run(cmd, capture_output=True, text=True)
    os.unlink(tmp)
    if r.returncode != 0 or not os.path.exists(out):
        print("❌ Chrome 打印失败：\n" + (r.stderr or "")[:800])
        return 1
    try:
        pages = stamp_pages(out)
    except Exception as e:
        pages = 0
        print(f"⚠️ 页码没盖上：{e}")
    sz = os.path.getsize(out) / 1024 / 1024
    print(f"✅ {title}.pdf  ({sz:.1f} MB, {pages or '?'} 页，页码已盖)")
    print(f"   {len(secs)} 节 / {total} 条 → {out}")
    return 0


def render_card(it, index):
    lv = re.sub(r"<[^>]+>", "", str(it.get("主观证据等级", ""))).strip()
    lv = lv if lv in ("A", "B", "C") else "B"
    fields = "".join(render_field(it, f, index) for f in FIELDS)
    return (f'<article class="card" id="c-{it["sec_no"]}-{it["no"]}">'
            f'<h4><span class="lv {lv}">{lv}</span>{esc(it["title"])}</h4>{fields}</article>')


if __name__ == "__main__":
    sys.exit(main())
