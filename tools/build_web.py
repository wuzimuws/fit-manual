#!/usr/bin/env python3
"""从 book/*.md + 前言/结语/附录 生成单文件网页（web/index.html）。

用法：  python3 tools/build_web.py
产物：  web/index.html   单文件、零依赖、可直接丢到 GitHub Pages
        web/data.json   中间数据，便于排查
"""
import os, re, json, sys, base64
from html import escape as _esc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refs  # noqa: E402  与 build_book.py 共用解析 / 镜像展开逻辑

# 顶栏「记食本」按钮指向的地址 —— 作者自己开发的饮食记录 App。
# 给了 App Store / 官网链接就改这一行（目前是 # 占位）。
JISHIBEN_URL = "https://nutridaily.cn/"

# 顶栏 GitHub 图标按钮指向的地址 —— 本指南的开源仓库。
GITHUB_URL = "https://github.com/wuzimuws/fit-manual"

# 百度统计站点 ID（tongji.baidu.com → 管理 → 站点管理 → 新增站点，代码里 hm.js? 后面那串 32 位十六进制）。
# 留空 = 不注入统计代码，页面保持"单文件零外部请求"；填上后重建即生效
# （代价：每个页面多一个到 hm.baidu.com 的外部请求 + 一个 cookie）。
BAIDU_ID = "37a50617991d766e2d06e498f09378a6"
BAIDU_SNIPPET = "" if not BAIDU_ID else (
    "<script>var _hmt=_hmt||[];(function(){"
    "var hm=document.createElement(\"script\");"
    "hm.async=true;"
    "hm.src=\"https://hm.baidu.com/hm.js?" + BAIDU_ID + "\";"
    "var s=document.getElementsByTagName(\"script\")[0];"
    "s.parentNode.insertBefore(hm,s);"
    "})();</script>"
)

# 顶栏「记食本」按钮的图标：与官网 nutridaily.cn 同源的品牌图标（三色饼图）。
# 和 FAVICON 一样内嵌成 data-URI，页面仍然只有一个文件。换图标就换 tools/assets/ 里那张图。
_ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "assets", "jishiben-icon.png")
try:
    with open(_ICON_PATH, "rb") as _f:
        JISHIBEN_ICON = "data:image/png;base64," + base64.b64encode(_f.read()).decode("ascii")
except OSError:
    # 兜底：1×1 透明像素，按钮退化成纯文字，不让 build 挂掉
    JISHIBEN_ICON = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
    print("⚠️ 未找到 tools/assets/jishiben-icon.png，图标留空", file=sys.stderr)

# 内嵌 SVG 图标：绿底圆角 + 白色「健」字。data-URI 内嵌，页面仍然只有一个文件。
FAVICON = ("data:image/svg+xml,"
           "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E"
           "%3Crect width='64' height='64' rx='14' fill='%231a6b4a'/%3E"
           "%3Ctext x='32' y='45' font-size='40' font-weight='700' fill='%23ffffff'"
           " font-family='PingFang SC,Microsoft YaHei,sans-serif'"
           " text-anchor='middle'%3E%E5%81%A5%3C/text%3E%3C/svg%3E")

ROOT = refs.ROOT
B = refs.B
FIELDS = refs.FIELDS
TODO = "〔待你补〕"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(s):
    s = esc(s)
    # markdown 链接 → <a>：来源里的书（豆瓣）和论文（PubMed/DOI）都靠这个变成可点
    def _a(m):
        txt = m.group(1).replace("\\[", "[").replace("\\]", "]")
        return f'<a href="{m.group(2)}" target="_blank" rel="noopener noreferrer">{txt}</a>'
    s = re.sub(r"\[((?:[^\[\]]|\\[\[\]])+)\]\((https?://[^)\s]+)\)", _a, s)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)


def md_block(txt, heads=True):
    """极简 markdown → HTML：标题 / 表格 / 列表 / 引用 / 段落 / 加粗"""
    out, lines, i = [], txt.split("\n"), 0
    while i < len(lines):
        ln = lines[i]
        st = ln.strip()
        if not st or st == "---":
            i += 1
            continue
        if heads and st.startswith("## "):
            out.append(f"<h4>{inline(st[3:])}</h4>")
            i += 1
            continue
        if st.startswith("# "):
            out.append(f"<h1>{inline(st[2:])}</h1>")
            i += 1
            continue
        # 表格
        if st.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            head = [c.strip() for c in st.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head)
                       + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows)
                       + "</tbody></table>")
            continue
        # 引用
        if st.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            out.append("<blockquote>" + inline(" ".join(buf)) + "</blockquote>")
            continue
        # 列表（保留层级缩进）
        if re.match(r"^\s*[-*] ", ln):
            buf = []
            while i < len(lines) and re.match(r"^\s*[-*] ", lines[i]):
                indent = len(lines[i]) - len(lines[i].lstrip())
                buf.append(f'<li data-i="{min(indent // 2, 3)}">'
                           + inline(re.sub(r"^\s*[-*] ", "", lines[i]).strip()) + "</li>")
                i += 1
            out.append("<ul>" + "".join(buf) + "</ul>")
            continue
        if re.match(r"^\s*\d+\. ", ln):
            buf = []
            while i < len(lines) and re.match(r"^\s*\d+\. ", lines[i]):
                buf.append("<li>" + inline(re.sub(r"^\s*\d+\. ", "", lines[i]).strip()) + "</li>")
                i += 1
            out.append("<ol>" + "".join(buf) + "</ol>")
            continue
        out.append("<p>" + inline(st) + "</p>")
        i += 1
    return "".join(out)


# 正文里的手写引用 → 可点跳转。写了「NN 节」就用那个节号，没写就用当前节。
# 「第 8、9 条」这种多编号的，每一个数字各自成链接。
RE_CITE_HTML = re.compile(r"(?:(\d{1,2})\s*节\s*)?第\s*(\d+(?:\s*[、,，]\s*\d+)*)\s*条")


def link_cites(html, cur, index):
    """把一段 HTML 里的「第 N 条」包成 <a data-go>；目标不存在就原样留着。

    只替换数字那几个字符，其余一个字符都不动——和 citelock 改条号是同一套思路。
    """
    if cur is None and not re.search(r"\d{1,2}\s*节", html):
        return html

    def f(m):
        whole = m.group(0)
        sec = int(m.group(1)) if m.group(1) else cur
        if sec is None:
            return whole
        body = m.group(2)
        head = m.start(2) - m.start(0)          # 「第 」/「08 节第 」的宽度
        out, last = "", 0
        for nm in re.finditer(r"\d+", body):
            out += body[last:nm.start()]
            no = int(nm.group(0))
            tgt = index.get((sec, no))
            out += (f'<a data-go="c-{sec}-{no}" title="跳到 {sec}. {tgt["title"]}">'
                    f'{nm.group(0)}</a>') if tgt else nm.group(0)
            last = nm.end()
        out += body[last:]
        return whole[:head] + out + whole[head + len(body):]

    return RE_CITE_HTML.sub(f, html)


def parse_sections():
    secs_raw, index, problems = refs.load()
    if problems:
        for p in problems:
            print("❌", p)
        sys.exit(1)
    secs = []
    for s in secs_raw:
        items = []
        for it in s["items"]:
            # 整体拷贝 refs 解析出的字段，再加渲染用的——这样 refs.py 新增字段会自动流到前端，
            # 不会再出现「解析器有、前端拿不到」的哑 bug（theme 就这样丢过一次）
            d = {k: v for k, v in it.items() if k != "raw"}
            d["anchor"] = f"c-{s['no']}-{it['no']}"
            for f in FIELDS:
                val = it[f]
                # 多行字段必须走 md_block：inline() 会把换行压成空格，
                # 子项「  - 」就会原样输出成一整段（"没有自动换行"）
                multi = f in ("具体地", "为什么", "总结性建议") and "\n" in val
                if f == "来源":
                    d[f] = "<br>".join(inline(l.strip()) for l in val.split("\n") if l.strip())
                else:
                    d[f] = md_block(val) if multi else inline(val.replace("\n", " ").strip())
                d[f] = link_cites(d[f], s["no"], index)
            lv = re.sub(r"<[^>]+>", "", d["主观证据等级"]).strip()
            d["level"] = lv if lv in ("A", "B", "C") else "B"
            d["src_done"] = TODO not in d["来源"]
            if it["mirror"]:
                sn, ino = it["mirror"]
                d["mirror_label"] = f"{sn:02d} 节 · 第 {ino} 条"
                d["mirror_anchor"] = f"c-{sn}-{ino}"
                d["mirror_title"] = it.get("mirror_title", "")
            items.append(d)
        themes = [{"name": th["name"], "lead": inline(th["lead"]),
                   "n": len(th["nos"]), "id": f"t-{s['no']}-{k + 1}"}
                  for k, th in enumerate(s.get("themes", []))]
        secs.append({"no": s["no"], "name": s["name"], "intro": md_block(s["intro"]),
                     "themes": themes, "items": items})
    return secs


def standalone(fname, heading=None):
    t = open(os.path.join(ROOT, fname), encoding="utf-8").read()
    return md_block(t)


def front_matter():
    """书名和简介取自 README.md——网页和 markdown 只有一个源，改一处两边都变。

    README 的第 1 行是书名，书名到第一条分隔线之间是简介段。
    """
    t = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    m = re.search(r"^# (.+)$", t, re.M)
    if not m:
        return "高性价比新手小白健身指南", ""
    body = t[m.end():].split("\n---")[0]
    paras = [p.strip() for p in body.split("\n") if p.strip()]
    return m.group(1).strip(), "".join(f"<p>{inline(p)}</p>" for p in paras)


def disclaimer():
    t = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    b = t[t.index("## 免责声明"):t.index("## 怎么读")]
    paras = [p.strip() for p in b.replace("## 免责声明", "").split("\n")
             if p.strip() and p.strip() != "---"]
    return "".join(f"<p>{inline(p)}</p>" for p in paras)


TPL = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">__BAIDU_TONGJI__
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<meta name="author" content="__AUTHOR__">
<meta property="og:type" content="article">
<meta property="og:title" content="__TITLE__">
<meta property="og:description" content="__DESC__">
<meta property="og:site_name" content="__TITLE__">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="__TITLE__">
<meta name="twitter:description" content="__DESC__">
<link rel="icon" href="__FAVICON__">
<style>
*{box-sizing:border-box}
:root{--bg:#fbfaf8;--card:#fff;--line:#e6e2db;--ink:#1c1a17;--dim:#6f6a61;--acc:#1a6b4a;
--A:#1a6b4a;--B:#9a6b1a;--C:#7a5c8a}
html{scrollbar-gutter:stable}          /* 正文高矮变化时不再挤动整页宽度 */
body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.75 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
header.topbar{position:sticky;top:0;z-index:20;background:var(--card);
border-bottom:1px solid var(--line)}
.logo{font-size:12px;font-weight:700;color:var(--acc);border:1px solid var(--acc);
border-radius:6px;padding:2px 7px;white-space:nowrap}
.top-title{font-size:15px;font-weight:600;white-space:nowrap;color:var(--dim);
text-decoration:none}
.top-title:hover{color:var(--ink)}
/* 窄屏（<560px）：顶栏固定项 logo40+标题180+GitHub37+记食本87+间隙52+内边距48=446px，
   在真机 390px 下会横向溢出 56px。这里收掉手机上没用的搜索框、书名缩成简称；
   桌面端一点不变。（实测数据来自 iframe 探针 —— --window-size 在 macOS 会被钳到 500px，测不准） */
.top-title .t-short{display:none}
@media(max-width:560px){
.top-title .t-full{display:none}
.top-title .t-short{display:inline}
.top-in input[type=search]{display:none}
}
.top-in input[type=search]{width:auto;flex:1;min-width:0;max-width:330px;margin-left:auto}
.doc{padding:4px 0 22px;border-bottom:1px solid var(--line);margin-bottom:24px}
h1{margin:0 0 10px;font-size:27px;letter-spacing:-.5px}
.lede{color:var(--dim);font-size:15px;margin:0 0 14px;line-height:1.75}
.lede p{margin:0 0 7px}.lede p:last-child{margin:0}
.stats{font-size:13px;color:var(--dim);margin:0 0 20px}
.stats b{font-weight:600}
.stats .A{color:var(--A)}.stats .B{color:var(--B)}.stats .C{color:var(--C)}
.disc{font-size:14px;color:var(--dim);background:#f6f4f0;border-radius:10px;padding:14px 16px}
.disc .disc-h{color:var(--ink);margin-bottom:7px}
.disc p{margin:0 0 7px}.disc p:last-child{margin:0}
.disc b{color:var(--ink)}
.sec-h{font-size:15px;margin:30px 0 12px;padding-bottom:7px;
border-bottom:1px solid var(--line);display:flex;align-items:baseline;gap:9px}
.sec-h .sec-n{font-size:12px;color:var(--dim);font-weight:400}
.sec-h:first-child{margin-top:0}
/* 来源栏：字号更小、整栏灰色；每条引用各自成行，整条都是一个链接 */
.f.src .v{font-size:12.5px;color:#9b968b;line-height:1.95}
.f.src .v a{color:inherit;text-decoration:none;border-bottom:1px solid #e2dcd2}
.f.src .v a:hover{color:var(--acc);border-color:var(--acc)}
/* 顶栏「记食本」入口（原「审核模式」按钮的位置）。
   样式照官网 nutridaily.cn 的次要按钮：品牌绿 #3E8C57，软底 + 同色描边 + 绿字，
   悬停翻成实心绿白字。底色比官网深一档（20% vs 12%）——本站卡片是纯白，
   12% 铺上去像没上色。 */
.top-link{flex:none;display:inline-flex;align-items:center;gap:6px;
border:1px solid rgba(62,140,87,.34);background:rgba(62,140,87,.2);color:#3E8C57;
font-size:12.5px;font-weight:500;padding:5px 12px;border-radius:999px;text-decoration:none;
font-family:inherit;white-space:nowrap;
transition:background .2s,color .2s,border-color .2s}
.top-link:hover{background:#3E8C57;border-color:#3E8C57;color:#fff}
.top-link img{width:17px;height:17px;display:block;flex:none}
.top-link svg{width:17px;height:17px;display:block;flex:none;fill:currentColor}
/* 顶栏纯图标按钮（GitHub）：左右内边距收窄，视觉上接近方形 */
.top-gh{padding:5px 9px;gap:0}
/* 回到顶部：滚过一屏才出现，右下角固定 */
#toTop{position:fixed;right:24px;bottom:24px;width:44px;height:44px;border-radius:50%;
background:var(--acc);border:1px solid var(--acc);color:#fff;font-size:19px;font-weight:700;
line-height:1;cursor:pointer;box-shadow:0 4px 16px rgba(26,107,74,.38);
opacity:0;pointer-events:none;transform:translateY(8px);
transition:opacity .18s,transform .18s,background .18s,box-shadow .18s;z-index:25}
#toTop.show{opacity:1;pointer-events:auto;transform:none}
#toTop:hover{background:#155c3f;border-color:#155c3f;box-shadow:0 6px 20px rgba(26,107,74,.5)}
@media(max-width:860px){#toTop{right:14px;bottom:14px;width:38px;height:38px}}

/* 节标题（照参考站 .sec-h：h2 + 条数） */
.sec-head{display:flex;align-items:baseline;gap:12px;margin:0 0 14px;
padding-bottom:10px;border-bottom:1px solid var(--line)}
.sec-head h2{font-size:24px;margin:0;letter-spacing:-.3px}
.sec-head .shown{font-size:13px;color:var(--dim)}
/* 章节简介区的「内置主题分类 + 快速索引」——照参考站写法：
   「日常开销：关掉自动续费（第 1 条），重算手机和宽带套餐（第 4 条）……」 */
.idx{margin:15px 0 26px}
.idx-lead{font-size:13.5px;color:var(--dim);margin:0 0 9px}
.idx-g{font-size:13.5px;line-height:1.95;margin:0 0 7px}
.idx-g:last-child{margin-bottom:0}
.idx-g b{font-weight:700}
.idx-g a{color:var(--acc);text-decoration:none;cursor:pointer;
border-bottom:1px dashed rgba(26,107,74,.45)}
.idx-g a:hover{border-bottom-style:solid}
.top-in{display:flex;align-items:center;gap:13px;height:56px;padding:0 24px}
.side{position:fixed;top:57px;left:0;bottom:0;width:272px;z-index:15;
display:flex;flex-direction:column;background:var(--card);border-right:1px solid var(--line);
padding:22px 30px 46px;overflow-y:auto;overflow-x:hidden;
scrollbar-gutter:stable}                /* 常驻预留滚动条槽位：展开/收起不再改宽度 */
.side::-webkit-scrollbar{width:16px}
main{margin-left:272px}
.main-in{max-width:900px;margin:0 auto;padding:26px 46px 96px}
.grp{margin-top:18px}
.grp:first-of-type{margin-top:13px}
.gt{font-size:14px;font-weight:700;margin:0 0 4px}
.gd{font-size:12px;color:var(--dim);line-height:1.6;margin:0 0 8px}
.hint{font-size:12px;color:var(--dim);line-height:1.65;margin:18px 0 0}
nav{display:flex;flex-direction:column;gap:2px}
nav button{text-align:left;border:1px solid transparent;background:none;color:var(--ink);
padding:7px 10px;border-radius:8px;font-size:14px;cursor:pointer;font-family:inherit;line-height:1.35}
nav button:hover{background:#f1efe9}
nav button.on{background:#eaf3ee;color:var(--acc);font-weight:600}
nav button.on .sn,nav button.on i,nav button.on .fold{color:var(--acc);opacity:.75}
.ch-b{display:flex;align-items:center;gap:7px;width:100%}
.ch-b .sn{color:var(--dim);flex:none}
.ch-b .st{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ch-b i{font-style:normal;font-size:11px;color:var(--dim);flex:none}
.ch-b .fold{flex:none;width:18px;height:18px;display:inline-flex;align-items:center;
justify-content:center;font-size:9px;color:var(--dim);font-style:normal;
transition:transform .18s;cursor:pointer;border-radius:4px}
.ch-b .fold::before{content:"\25BE"}
.ch-b .fold:hover{background:rgba(0,0,0,.06)}
.ch.open .ch-b .fold{transform:rotate(180deg)}
.toc-sub{display:flex;flex-direction:column;padding:1px 0 7px}
.toc-sub[hidden]{display:none}
.toc-sub a{display:flex;gap:6px;align-items:flex-start;font-size:13px;color:var(--dim);
text-decoration:none;padding:3px 6px 3px 12px;line-height:20px;
border-left:2px solid transparent;border-radius:0 6px 6px 0}
.toc-sub a:hover{color:var(--acc);background:#f2f6f3}
.toc-sub a.on{color:var(--acc);border-left-color:var(--acc);font-weight:600}
.toc-sub a.on i{opacity:1}
.toc-sub a i{font-style:normal;flex:none;width:20px;text-align:right;opacity:.65}
.toc-sub a span{flex:1;min-width:0;display:-webkit-box;-webkit-box-orient:vertical;
-webkit-line-clamp:2;overflow:hidden}       /* 最多两行，超出省略；短标题仍是一行 */
input[type=search]{width:100%;padding:8px 12px;border:1px solid var(--line);
border-radius:9px;font-size:14px;font-family:inherit;background:var(--card)}
.levels{display:flex;gap:6px}
.chip{display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--line);
background:var(--card);padding:3px 11px;border-radius:999px;font-size:12px;cursor:pointer;user-select:none}
.chip:hover{border-color:#c9c3b8}
.chip.on{background:#eef5f1;border-color:var(--acc);color:var(--acc)}
.count{color:var(--dim);font-size:12px;margin-top:14px;line-height:1.55}
@media(max-width:860px){
.side{position:static;width:auto;border-right:0;border-bottom:1px solid var(--line);
max-height:none;padding:14px 18px 18px}
main{margin-left:0}
.main-in{padding:18px 18px 64px}
nav{flex-direction:row;flex-wrap:wrap}
nav button{border:1px solid var(--line);border-radius:999px;padding:6px 12px}
.ch{display:contents}                    /* 章节直接作为胶囊横排 */
.ch-b{width:auto}
.ch-b .st{flex:none}
.ch-b .fold{display:none}                /* 窄屏收起逐条目录，交给搜索/全部 */
.toc-sub{display:none !important}
.levels{flex-wrap:wrap}
}
/* 节简介：普通段落，不套卡片——它就是「本节条目按主题分成下面几块」前面那一段 */
.intro{margin:0 0 22px;font-size:14px;line-height:1.85;color:var(--ink)}
.intro p{margin:0 0 12px}
.intro p:last-child{margin:0}
.intro p{margin:0 0 8px}.intro p:last-child{margin:0}
.intro h4{color:var(--ink);font-size:15px;margin:14px 0 6px}
.intro h4:first-child{margin-top:0}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:22px 24px 18px;margin-bottom:16px;
font-size:14px;line-height:1.75}      /* 卡内基准 14px：正文比标题低一级，层级才分得开 */
.card h4{margin:0 0 14px;font-size:18px;font-weight:600;line-height:28px;
display:flex;gap:10px;align-items:flex-start}
.num{color:#b9b3a8;font-size:14px;font-variant-numeric:tabular-nums;
flex:none;width:23px;height:23px;display:grid;place-items:center;
line-height:1;margin-top:2px}
.lv{flex:none;width:23px;height:23px;border-radius:6px;display:grid;place-items:center;
font-size:12px;font-weight:700;color:#fff;margin-top:2px;line-height:1;text-align:center}
.lv.A{background:var(--A)}.lv.B{background:var(--B)}.lv.C{background:var(--C)}
.sec-tag{display:inline-block;background:#f1efe9;color:var(--dim);border-radius:5px;
padding:1px 7px;font-size:12px;margin-left:auto;flex:none}
.f{margin:0 0 11px;display:flex;gap:10px;align-items:baseline}
.f:last-child{margin:0}
/* 总结性建议：强调底色（参考 How-to-Train-Better 的 .human 盒） */
.f.hl{background:rgba(26,107,74,.09);border-left:2px solid var(--acc);
border-radius:0 6px 6px 0;padding:10px 14px;margin:0 0 11px;
font-size:15px;line-height:1.75}       /* 照模板 .human：比正文大一级 */
.f.hl .k{color:var(--acc);font-weight:600}
.f.hl .v{width:100%}
.k{flex:none;width:96px;color:var(--dim);font-size:13px;font-weight:500;line-height:1.75}
.v{flex:1;min-width:0}
.v p{margin:0 0 6px}.v p:last-child{margin:0}
.v ul,.v ol{margin:0 0 6px;padding-left:20px}.v li{margin:2px 0}
.v li[data-i="1"]{margin-left:18px}.v li[data-i="2"]{margin-left:36px}.v li[data-i="3"]{margin-left:54px}
.v table{border-collapse:collapse;margin:8px 0;font-size:13px;width:100%}
.v th,.v td{border:1px solid var(--line);padding:6px 9px;text-align:left}
.v th{background:#f6f4f0;font-weight:600}
.v blockquote{margin:6px 0;padding:8px 13px;border-left:3px solid var(--line);color:var(--dim)}
.todo{color:#c0392b;font-size:13px;font-style:italic}
.mirror{background:#f4f8f6;border:1px solid #d8e8e0;border-radius:8px;padding:8px 12px;
margin:0 0 12px;font-size:13px;color:var(--dim);line-height:1.6}
.mirror a{color:var(--acc);font-weight:600;text-decoration:none}
.mirror a:hover{text-decoration:underline}
.card,.page{scroll-margin-top:24px}
.page{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:30px 34px;margin-top:34px}
.page h1{font-size:24px;margin:0 0 18px}
.page h2,.page h4{font-size:18px;margin:26px 0 10px}
.page table{border-collapse:collapse;margin:12px 0;font-size:15px;width:100%}
.page th,.page td{border:1px solid var(--line);padding:7px 10px;text-align:left}
.page th{background:#f6f4f0}
.page blockquote{margin:12px 0;padding:10px 16px;border-left:3px solid var(--acc);background:#f4f8f6;color:var(--dim)}
footer{color:var(--dim);font-size:13px;padding:30px 0 50px;text-align:center}
</style></head><body>
<header class="topbar"><div class="top-in">
  <span class="logo">健身</span>
  <a class="top-title" href="#" title="回到全书"><span class="t-full">高性价比新手小白健身指南</span><span class="t-short">健身指南</span></a>
  <input type="search" id="q" placeholder="搜索条目（可跨章）">
  <a class="top-link top-gh" href="__GITHUB__" target="_blank" rel="noopener noreferrer"
     title="本指南的 GitHub 仓库" aria-label="本指南的 GitHub 仓库"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="17" height="17" aria-hidden="true" focusable="false"><path d="M10.226 17.284c-2.965-.36-5.054-2.493-5.054-5.256 0-1.123.404-2.336 1.078-3.144-.292-.741-.247-2.314.09-2.965.898-.112 2.111.36 2.83 1.01.853-.269 1.752-.404 2.853-.404 1.1 0 1.999.135 2.807.382.696-.629 1.932-1.1 2.83-.988.315.606.36 2.179.067 2.942.72.854 1.101 2 1.101 3.167 0 2.763-2.089 4.852-5.098 5.234.763.494 1.28 1.572 1.28 2.807v2.336c0 .674.561 1.056 1.235.786 4.066-1.55 7.255-5.615 7.255-10.646C23.5 6.188 18.334 1 11.978 1 5.62 1 .5 6.188.5 12.545c0 4.986 3.167 9.12 7.435 10.669.606.225 1.19-.18 1.19-.786V20.63a2.9 2.9 0 0 1-1.078.224c-1.483 0-2.359-.808-2.987-2.313-.247-.607-.517-.966-1.034-1.033-.27-.023-.359-.135-.359-.27 0-.27.45-.471.898-.471.652 0 1.213.404 1.797 1.235.45.651.921.943 1.483.943.561 0 .92-.202 1.437-.719.382-.381.674-.718.944-.943"/></svg></a>
  <a class="top-link" href="__JISHIBEN__" target="_blank" rel="noopener noreferrer"
     title="作者自己开发的饮食记录 App"><img src="__JISHIBEN_ICON__" alt="" width="17" height="17">记食本</a>
</div></header>
<aside class="side" id="side">
    <div class="grp">
      <div class="gt">证据等级</div>
      <div class="gd">A 机制或共识 · B 有一定的相关性 · C 个人体感</div>
      <div class="levels">
        <span class="chip on" data-lv="A">A 级</span>
        <span class="chip on" data-lv="B">B 级</span>
        <span class="chip on" data-lv="C">C 级</span>
      </div>
    </div>
    <div class="grp">
      <div class="gt">章节</div>
      <nav id="nav"></nav>
    </div>
    <div class="hint">章节一次看一个；等级可多选，多选之间是「或」。</div>
    <span class="count" id="cnt"></span>
  </aside>
<main><div class="main-in">
    <div class="doc" id="doc">
      <h1>__TITLE__</h1>
      <div class="lede">__LEDE__</div>
      <div class="stats">__SECTIONS__ 节 · __TOTAL__ 条 · <b class="A">A __NA__</b>
      · <b class="B">B __NB__</b> · <b class="C">C __NC__</b></div>
      <div class="disc"><div class="disc-h">免责声明</div>__DISCLAIMER__</div>
    </div>
    <div id="body"></div>
    <footer>共 __TOTAL__ 条 · __SECTIONS__ 节 · 作者个人经验，仅供参考 · <a href="https://fit.nutridaily.cn/" target="_blank" rel="noopener">在线版</a></footer>
    <button id="toTop" type="button" aria-label="回到顶部" title="回到顶部">↑</button>
</div></main>
<script>
const DATA=__DATA__, PAGES=__PAGES__, TOTAL=__TOTAL__;
let cur="1", q="", lv={A:1,B:1,C:1}, selAnchor=null, tocClosed=false;
const $=s=>document.querySelector(s), nav=$("#nav");
const esc=s=>String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
const tabs=[{k:"all",t:"全部 · "+TOTAL+" 条"},{k:"pre",t:"前言"},
  ...DATA.map(s=>({k:String(s.no),t:s.no+". "+s.name,sub:s.items,themes:s.themes})),
  {k:"end",t:"结语"},{k:"app",t:"附录"}];
const tocLink=it=>`<a href="#${it.anchor}" data-go="${it.anchor}" `
  +`title="${esc(it.title)}"><i>${it.no}</i><span>${esc(it.title)}</span></a>`;
nav.innerHTML=tabs.map(t=>{
  if(!t.sub) return `<button data-k="${t.k}">${t.t}</button>`;
  const inner=t.sub.map(tocLink).join("");
  return `<div class="ch"><button class="ch-b" data-k="${t.k}">`
    +`<span class="sn">${t.k}.</span><span class="st">${esc(t.t.replace(/^\d+\. /,""))}</span>`
    +`<i>${t.sub.length}</i>`
    +`<b class="fold" title="展开/收起本章目录"></b></button>`
    +`<div class="toc-sub" hidden>${inner}</div></div>`;
}).join("");
nav.onclick=e=>{
  const fold=e.target.closest(".fold");                 /* 小箭头 → 单独收起 */
  if(fold){const ch=fold.closest(".ch");const sub=ch.querySelector(".toc-sub");
    const open=ch.classList.toggle("open");sub.hidden=!open;
    if(ch.querySelector("button").dataset.k===cur)tocClosed=!open;
    return;}
  const b=e.target.closest("button");if(!b)return;
  const k=b.dataset.k;
  if(k===cur && b.closest(".ch")){                     /* 再点当前章 → 收起目录 */
    tocClosed=!tocClosed;syncToc();return;}
  cur=k;tocClosed=false;                               /* 换章 = 选中 + 展开 */
  /* 先把选中态画上，再重建正文：否则高亮要等 94 张卡片重建完才上色，看着就是「点慢了」 */
  document.querySelectorAll("nav button")
    .forEach(x=>x.classList.toggle("on",x.dataset.k===cur));
  window.scrollTo({top:0});                            /* 切换视图直接回顶，不用平滑滚动 */
  requestAnimationFrame(()=>draw());};

/* 侧栏目录与正文联动：当前章展开（手风琴），当前条目加选中竖线 */
function syncToc(){
  const secNo=/^\d+$/.test(cur)?cur:null;
  document.querySelectorAll(".ch").forEach(ch=>{
    const open=(ch.querySelector("button").dataset.k===secNo)&&!tocClosed;
    ch.classList.toggle("open",open);
    const sub=ch.querySelector(".toc-sub");if(sub)sub.hidden=!open;
  });
  document.querySelectorAll(".toc-sub a").forEach(a=>
    a.classList.toggle("on",a.dataset.go===selAnchor));
}
let raf=0;
addEventListener("scroll",()=>{if(raf)return;
  raf=requestAnimationFrame(()=>{raf=0;spy();toTopSync();});}, {passive:true});
const toTop=$("#toTop");
function toTopSync(){toTop.classList.toggle("show",scrollY>500);}
toTop.onclick=()=>window.scrollTo({top:0,behavior:"smooth"});
function spy(){                                        /* 滚动时把选中标志挪到当前读到的条目 */
  const cards=[...document.querySelectorAll(".card")];
  if(!cards.length)return;
  const mark=innerHeight*0.34;let best=null;
  for(const c of cards){if(c.getBoundingClientRect().top<=mark)best=c;else break;}
  const id=(best||cards[0]).id;
  if(id===selAnchor)return;
  selAnchor=id;
  document.querySelectorAll(".toc-sub a").forEach(a=>
    a.classList.toggle("on",a.dataset.go===id));
}
document.querySelectorAll(".chip").forEach(c=>c.onclick=()=>{
  lv[c.dataset.lv]=!lv[c.dataset.lv];c.classList.toggle("on");draw();});
$("#q").oninput=e=>{q=e.target.value.trim().toLowerCase();draw();};
document.querySelector(".top-title").onclick=e=>{e.preventDefault();
  cur="all";draw();window.scrollTo({top:0,behavior:"smooth"});};
function renderItems(sec,items,compact){ return items.map(it=>card(it,false,compact)).join(""); }

/* 简介区的「内置主题分类 + 快速索引」：主题名 + 一句说明 + 该主题全部条目的跳转。
   主题不再是正文里的一层，只是简介区的一部分。 */
function idxBlock(sec,items){
  if(!sec.themes||!sec.themes.length) return "";
  const by=new Map();
  items.forEach(it=>{const k=it.theme||"";if(!by.has(k))by.set(k,[]);by.get(k).push(it);});
  const parts=sec.themes.map(th=>{
    const arr=by.get(th.name)||[];if(!arr.length)return "";
    return `<p class="idx-g" id="${th.id}"><b>${esc(th.name)}</b>：`
      +arr.map(it=>`${esc(it.title)}（<a data-go="${it.anchor}" title="跳到这一条">第 ${
        it.no} 条</a>）`).join("，")+`</p>`;
  }).join("");
  return parts?`<div class="idx"><p class="idx-lead">本节条目按主题分成下面几块，括号里是条号。</p>${
    parts}</div>`:"";
}
const hay=it=>[it.title,it["总结性建议"],it["具体地"],it["为什么"]].join(" ").replace(/<[^>]+>/g,"").toLowerCase();
function card(it,showSec,compact){
  const mir=it.mirror?`<div class="mirror">本条正文与 <a href="#${it.mirror_anchor}" data-go="${it.mirror_anchor}">${it.mirror_label}</a>「${it.mirror_title}」相同，<b>正文以该条为准</b></div>`:"";
  if(compact&&it.mirror)                      /* 全书视图：镜像条不重复展开 */
    return `<div class="card compact" id="${it.anchor}"><h4><span class="num">${it.no}</span>
      <span class="lv ${it.level}">${it.level}</span><span>${it.title}</span>
      <span class="sec-tag">${it.sec}</span></h4>${mir}</div>`;
  return `<div class="card" id="${it.anchor}"><h4><span class="num">${it.no}</span>
    <span class="lv ${it.level}">${it.level}</span><span>${it.title}</span>
    ${showSec?`<span class="sec-tag">${it.sec}</span>`:""}</h4>
    ${mir}${["总结性建议","具体地","为什么","来源"].map(f=>{
      let v=it[f];
      if(f==="来源"&&!it.src_done) v=`<span class="todo">〔待补〕</span>`;
      if (f === "总结性建议")                 /* 高亮框本身就是"答案"，不再重复标签 */
        return `<div class="f hl"><div class="v">${v}</div></div>`;
      return `<div class="f${f === "来源" ? " src" : ""}"><div class="k">${f}</div><div class="v">${v}</div></div>`;
    }).join("")}</div>`;
}
function goTo(anchor){                       /* 跳到镜像条的源条 */
  const m=anchor.match(/^c-(\d+)-(\d+)$/); if(!m) return;
  lv={A:1,B:1,C:1};
  document.querySelectorAll(".chip").forEach(c=>c.classList.add("on"));
  q=""; $("#q").value="";
  cur=m[1]; tocClosed=false; draw();
  const el=document.getElementById(anchor);
  if(el) el.scrollIntoView({block:"center",behavior:"smooth"});
}
document.addEventListener("click",e=>{
  const a=e.target.closest("a[data-go]"); if(!a) return;
  e.preventDefault(); goTo(a.dataset.go);
});
function draw(){
  document.querySelectorAll("nav button").forEach(b=>b.classList.toggle("on",b.dataset.k===cur));
  const isList=!("pre end app".split(" ").includes(cur));
  $("#side").style.display="flex";        /* 侧栏就是导航，任何视图都留着 */
  $("#doc").style.display=isList?"block":"none";
  if(!isList){$("#body").innerHTML=`<div class="page">${PAGES[cur].html}</div>`;return;}
  if(cur==="all"){                          /* 全部：按章分组，等级筛选跨全书 */
    let n=0,html="";
    DATA.forEach(s=>{
      const arr=s.items.filter(it=>lv[it.level]&&(!q||hay(it).includes(q)));
      if(!arr.length)return;
      n+=arr.length;
      html+=`<h2 class="sec-h"><span>${s.no}. ${s.name}</span>`
          + `<span class="sec-n">${arr.length} 条</span></h2>`
          + renderItems(s,arr,true);
    });
    $("#cnt").textContent=q?`全书命中 ${n} 条`:`${n} / ${TOTAL} 条（全书）`;
    $("#body").innerHTML=html||'<div class="card">没有符合条件的条目。</div>';
    syncToc();
    return;
  }
  if(q){                                   /* 有搜索词 → 全书跨节搜 */
    const hits=[];
    DATA.forEach(s=>s.items.forEach(it=>{if(lv[it.level]&&hay(it).includes(q))hits.push(it)}));
    $("#cnt").textContent=`全书命中 ${hits.length} 条`;
    $("#body").innerHTML=hits.length
      ? hits.map(it=>card(it,true)).join("")
      : '<div class="card">没找到。换个词试试，或者清空搜索框。</div>';
    return;
  }
  const s=DATA.find(x=>String(x.no)===cur);   /* 无搜索词 → 只看当前节 */
  const items=s.items.filter(it=>lv[it.level]);
  $("#cnt").textContent=`${items.length} / ${s.items.length} 条`;
  $("#body").innerHTML=`<div class="sec-head"><h2>${s.no}. ${esc(s.name)}</h2>`
    +`<span class="shown">${items.length} / ${s.items.length} 条</span></div>`
    +`<div class="intro">${s.intro}</div>`+idxBlock(s,items)
    +renderItems(s,items,false);
  syncToc(); spy(); toTopSync();
}
draw();
</script></body></html>"""


def _js_check(html):
    """抽出 <script> 跑 node --check —— 防止手改模板时打错符号却只在线上下线才炸。"""
    import shutil, subprocess, tempfile
    if not shutil.which("node"):
        print("   （未装 node，跳过 JS 语法检查）"); return
    # 逐个 <script> 块单独检查 —— 不能从第一个 <script> 切到最后一个 </script>：
    # 页面上有多块 inline JS 时，中间夹的 </script><script> 会被当成同一个 js 文件，报 Unexpected token '<'。
    blocks = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
    if not blocks:
        print("   （没有内联 script 块，跳过 JS 语法检查）"); return
    for i, js in enumerate(blocks, 1):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(js); path = f.name
        try:
            r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
            if r.returncode:
                print(f"❌ JS 语法错误（第 {i} 个 script 块）："); print(r.stderr.strip()[:600]); raise SystemExit(1)
        finally:
            os.unlink(path)
    print(f"   JS 语法 ✅（{len(blocks)} 个内联块）")


def main():
    secs = parse_sections()
    _, index, _ = refs.load()          # 非正文页面里的「NN 节第 N 条」要按节号找目标
    total = sum(len(s["items"]) for s in secs)
    pages = {
        "pre": {"html": link_cites(standalone("前言.md"), None, index)},
        "end": {"html": link_cites(standalone("结语.md"), None, index)},
        "app": {"html": link_cites(standalone("附录-参考书目.md"), None, index)},
    }
    title, lede = front_matter()
    html = (TPL.replace("__DATA__", json.dumps(secs, ensure_ascii=False))
               .replace("__PAGES__", json.dumps(pages, ensure_ascii=False))
               .replace("__TITLE__", title)
               .replace("__LEDE__", lede)
               .replace("__DISCLAIMER__", disclaimer())
               .replace("__NA__", str(sum(1 for s in secs for i in s["items"] if i["level"]=="A")))
               .replace("__NB__", str(sum(1 for s in secs for i in s["items"] if i["level"]=="B")))
               .replace("__NC__", str(sum(1 for s in secs for i in s["items"] if i["level"]=="C")))
               .replace("__TOTAL__", str(total))
               .replace("__SECTIONS__", str(len(secs)))
               .replace("__JISHIBEN__", JISHIBEN_URL)
               .replace("__JISHIBEN_ICON__", JISHIBEN_ICON)
               .replace("__GITHUB__", GITHUB_URL)
               .replace("__BAIDU_TONGJI__", BAIDU_SNIPPET)
               .replace("__DESC__", _esc(re.sub(r"<[^>]+>", "", lede).replace("&nbsp;", " ").strip()[:120]))
               .replace("__AUTHOR__", "指南作者")
               .replace("__FAVICON__", FAVICON))
    os.makedirs(os.path.join(ROOT, "web"), exist_ok=True)
    json.dump(secs, open(os.path.join(ROOT, "web", "data.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    outp = os.path.join(ROOT, "web", "index.html")
    open(outp, "w", encoding="utf-8").write(html)
    _js_check(html)
    todo = sum(1 for s in secs for i in s["items"] if not i["src_done"])
    print(f"✅ {len(secs)} 节 / {total} 条 → web/index.html ({os.path.getsize(outp)//1024} KB)")
    print(f"   来源待补：{todo} / {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
