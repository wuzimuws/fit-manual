#!/usr/bin/env python3
"""从 book/*.md + 前言/结语/附录 生成单文件网页（web/index.html）。

用法：  python3 tools/build_web.py
产物：  web/index.html   单文件、零依赖、可直接丢到 GitHub Pages
        web/data.json   中间数据，便于排查
"""
import os, re, json, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refs  # noqa: E402  与 build_book.py 共用解析 / 镜像展开逻辑

ROOT = refs.ROOT
B = refs.B
FIELDS = refs.FIELDS
TODO = "〔待你补〕"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(s):
    s = esc(s)
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
            d = {"no": it["no"], "title": it["title"], "sec": s["name"], "sec_no": s["no"],
                 "anchor": f"c-{s['no']}-{it['no']}", "mirror": it["mirror"]}
            for f in FIELDS:
                val = it[f]
                # 多行字段必须走 md_block：inline() 会把换行压成空格，
                # 子项「  - 」就会原样输出成一整段（"没有自动换行"）
                multi = f in ("具体地", "为什么这样建议", "总结性建议") and "\n" in val
                d[f] = md_block(val) if multi else inline(val.replace("\n", " ").strip())
            lv = re.sub(r"<[^>]+>", "", d["主观证据等级"]).strip()
            d["level"] = lv if lv in ("A", "B", "C") else "B"
            d["src_done"] = TODO not in d["来源"]
            if it["mirror"]:
                sn, ino = it["mirror"]
                d["mirror_label"] = f"{sn:02d} 节 · 第 {ino} 条"
                d["mirror_anchor"] = f"c-{sn}-{ino}"
                d["mirror_title"] = it.get("mirror_title", "")
            items.append(d)
        secs.append({"no": s["no"], "name": s["name"], "intro": md_block(s["intro"]), "items": items})
    return secs


def standalone(fname, heading=None):
    t = open(os.path.join(ROOT, fname), encoding="utf-8").read()
    return md_block(t)


def disclaimer():
    t = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    b = t[t.index("## 免责声明"):t.index("## 怎么读")]
    paras = [p.strip() for p in b.replace("## 免责声明", "").split("\n")
             if p.strip() and p.strip() != "---"]
    return "".join(f"<p>{inline(p)}</p>" for p in paras)


TPL = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>高性价比新手小白健身指南</title>
<style>
*{box-sizing:border-box}
:root{--bg:#fbfaf8;--card:#fff;--line:#e6e2db;--ink:#1c1a17;--dim:#6f6a61;--acc:#1a6b4a;
--A:#1a6b4a;--B:#9a6b1a;--C:#7a5c8a}
body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.75 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
header{padding:34px 22px 20px;border-bottom:1px solid var(--line);background:var(--card)}
h1{margin:0 0 10px;font-size:27px;letter-spacing:-.5px}
.sub{color:var(--dim);font-size:14px;max-width:800px}
.sub b{color:var(--ink)}
.sub p{margin:0 0 7px}.sub p:last-child{margin:0}
.disc-h{font-weight:600;color:var(--ink);margin-bottom:8px}
.wrap{max-width:1120px;margin:0 auto;padding:0 22px}
.layout{display:grid;grid-template-columns:208px minmax(0,1fr);gap:30px;align-items:start;padding-top:22px}
.side{position:sticky;top:16px;display:flex;flex-direction:column;
max-height:calc(100vh - 32px);overflow-y:auto}
.grp{margin-top:18px}
.grp:first-of-type{margin-top:13px}
.gt{font-size:14px;font-weight:700;margin:0 0 4px}
.gd{font-size:11px;color:var(--dim);line-height:1.55;margin:0 0 8px}
.hint{font-size:11px;color:var(--dim);line-height:1.6;margin:18px 0 0}
nav{display:flex;flex-direction:column;gap:2px}
nav button{text-align:left;border:1px solid transparent;background:none;color:var(--ink);
padding:7px 10px;border-radius:8px;font-size:14px;cursor:pointer;font-family:inherit;line-height:1.35}
nav button:hover{background:#f1efe9}
nav button.on{background:var(--ink);color:#fff}
input[type=search]{width:100%;padding:8px 12px;border:1px solid var(--line);
border-radius:9px;font-size:14px;font-family:inherit;background:var(--card)}
.levels{display:flex;gap:6px}
.chip{display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--line);
background:var(--card);padding:3px 11px;border-radius:999px;font-size:12px;cursor:pointer;user-select:none}
.chip:hover{border-color:#c9c3b8}
.chip.on{background:#eef5f1;border-color:var(--acc);color:var(--acc)}
.count{color:var(--dim);font-size:12px;margin-top:14px;line-height:1.55}
@media(max-width:860px){
.layout{grid-template-columns:1fr;gap:0}
.side{position:static;margin-bottom:18px}
nav{flex-direction:row;flex-wrap:wrap}
nav button{border:1px solid var(--line);border-radius:999px;padding:6px 12px}
.levels{flex-wrap:wrap}
}
.intro{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 20px;
margin-bottom:20px;color:var(--dim);font-size:15px}
.intro p{margin:0 0 8px}.intro p:last-child{margin:0}
.intro h4{color:var(--ink);font-size:15px;margin:14px 0 6px}
.intro h4:first-child{margin-top:0}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin-bottom:14px}
.card h3{margin:0 0 14px;font-size:18px;line-height:1.5;display:flex;gap:10px;align-items:flex-start}
.num{color:#b9b3a8;font-size:14px;font-variant-numeric:tabular-nums;padding-top:3px;min-width:22px}
.lv{flex:none;width:23px;height:23px;border-radius:6px;display:grid;place-items:center;
font-size:12px;font-weight:700;color:#fff;margin-top:2px}
.lv.A{background:var(--A)}.lv.B{background:var(--B)}.lv.C{background:var(--C)}
.sec-tag{display:inline-block;background:#f1efe9;color:var(--dim);border-radius:5px;
padding:1px 7px;font-size:12px;margin-left:auto;flex:none}
.f{margin:0 0 11px;display:flex;gap:10px;align-items:baseline}
.f:last-child{margin:0}
/* 总结性建议：强调底色（参考 How-to-Train-Better 的 .human 盒） */
.f.hl{background:rgba(26,107,74,.09);border-left:2px solid var(--acc);
border-radius:0 6px 6px 0;padding:10px 14px;margin:0 0 11px}
.f.hl .k{color:var(--acc);font-weight:600}
.f.hl .v{width:100%}
.k{flex:none;width:96px;color:var(--dim);font-size:13px}
.v{flex:1;min-width:0}
.v p{margin:0 0 6px}.v p:last-child{margin:0}
.v ul,.v ol{margin:0 0 6px;padding-left:20px}.v li{margin:2px 0}
.v li[data-i="1"]{margin-left:18px}.v li[data-i="2"]{margin-left:36px}.v li[data-i="3"]{margin-left:54px}
.v table{border-collapse:collapse;margin:8px 0;font-size:14px;width:100%}
.v th,.v td{border:1px solid var(--line);padding:6px 9px;text-align:left}
.v th{background:#f6f4f0;font-weight:600}
.v blockquote{margin:6px 0;padding:8px 13px;border-left:3px solid var(--line);color:var(--dim)}
.todo{color:#c0392b;font-size:13px;font-style:italic}
.mirror{background:#f4f8f6;border:1px solid #d8e8e0;border-radius:8px;padding:8px 12px;
margin:0 0 12px;font-size:13px;color:var(--dim);line-height:1.6}
.mirror a{color:var(--acc);font-weight:600;text-decoration:none}
.mirror a:hover{text-decoration:underline}
.card,.page{scroll-margin-top:24px}
.page{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:26px 30px}
.page h1{font-size:24px;margin:0 0 18px}
.page h2,.page h4{font-size:18px;margin:26px 0 10px}
.page table{border-collapse:collapse;margin:12px 0;font-size:15px;width:100%}
.page th,.page td{border:1px solid var(--line);padding:7px 10px;text-align:left}
.page th{background:#f6f4f0}
.page blockquote{margin:12px 0;padding:10px 16px;border-left:3px solid var(--acc);background:#f4f8f6;color:var(--dim)}
footer{color:var(--dim);font-size:13px;padding:30px 0 50px;text-align:center}
</style></head><body>
<header><div class="wrap">
<h1>高性价比新手小白健身指南</h1>
<div class="sub"><div class="disc-h">免责声明</div>__DISCLAIMER__</div>
</div></header>
<div class="wrap layout">
  <aside class="side" id="side">
    <input type="search" id="q" placeholder="搜索（可跨章）">
    <div class="grp">
      <div class="gt">证据等级</div>
      <div class="gd">A 机制或共识 ＋ 我验证过 · B 道理站得住但靠经验 · C 只有我的体感</div>
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
  <main>
    <div id="body"></div>
    <footer>共 __TOTAL__ 条 · __SECTIONS__ 节 · 作者个人经验，仅供参考</footer>
  </main>
</div>
<script>
const DATA=__DATA__, PAGES=__PAGES__;
let cur="1", q="", lv={A:1,B:1,C:1};
const $=s=>document.querySelector(s), nav=$("#nav");
const tabs=[{k:"pre",t:"前言"},...DATA.map(s=>({k:String(s.no),t:s.no+". "+s.name})),{k:"end",t:"结语"},{k:"app",t:"附录"}];
nav.innerHTML=tabs.map(t=>`<button data-k="${t.k}">${t.t}</button>`).join("");
nav.onclick=e=>{const b=e.target.closest("button");if(!b)return;cur=b.dataset.k;draw();
  window.scrollTo({top:0,behavior:"smooth"});};
document.querySelectorAll(".chip").forEach(c=>c.onclick=()=>{
  lv[c.dataset.lv]=!lv[c.dataset.lv];c.classList.toggle("on");draw();});
$("#q").oninput=e=>{q=e.target.value.trim().toLowerCase();draw();};
const hay=it=>[it.title,it["总结性建议"],it["具体地"],it["为什么这样建议"]].join(" ").replace(/<[^>]+>/g,"").toLowerCase();
function card(it,showSec){
  const mir=it.mirror?`<div class="mirror">本条正文与 <a href="#${it.mirror_anchor}" data-go="${it.mirror_anchor}">${it.mirror_label}</a>「${it.mirror_title}」相同，<b>正文以该条为准</b></div>`:"";
  return `<div class="card" id="${it.anchor}"><h3><span class="num">${it.no}</span>
    <span class="lv ${it.level}">${it.level}</span><span>${it.title}</span>
    ${showSec?`<span class="sec-tag">${it.sec}</span>`:""}</h3>
    ${mir}${["总结性建议","具体地","为什么这样建议","来源"].map(f=>{
      let v=it[f];
      if(f==="来源"&&!it.src_done) v=`<span class="todo">〔待补〕</span>`;
      if (f === "总结性建议")                 /* 高亮框本身就是"答案"，不再重复标签 */
        return `<div class="f hl"><div class="v">${v}</div></div>`;
      return `<div class="f"><div class="k">${f}</div><div class="v">${v}</div></div>`;
    }).join("")}</div>`;
}
function goTo(anchor){                       /* 跳到镜像条的源条 */
  const m=anchor.match(/^c-(\d+)-(\d+)$/); if(!m) return;
  lv={A:1,B:1,C:1};
  document.querySelectorAll(".chip").forEach(c=>c.classList.add("on"));
  q=""; $("#q").value="";
  cur=m[1]; draw();
  const el=document.getElementById(anchor);
  if(el) el.scrollIntoView({block:"center",behavior:"smooth"});
}
document.addEventListener("click",e=>{
  const a=e.target.closest("a[data-go]"); if(!a) return;
  e.preventDefault(); goTo(a.dataset.go);
});
function draw(){
  nav.querySelectorAll("button").forEach(b=>b.classList.toggle("on",b.dataset.k===cur));
  const isList=!("pre end app".split(" ").includes(cur));
  $("#side").style.display=isList?"flex":"none";
  if(!isList){$("#body").innerHTML=`<div class="page">${PAGES[cur].html}</div>`;return;}
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
  $("#body").innerHTML=`<div class="intro">${s.intro}</div>`+items.map(it=>card(it,false)).join("");
}
draw();
</script></body></html>"""


def main():
    secs = parse_sections()
    total = sum(len(s["items"]) for s in secs)
    pages = {
        "pre": {"html": standalone("前言.md")},
        "end": {"html": standalone("结语.md")},
        "app": {"html": standalone("附录-参考书目.md")},
    }
    html = (TPL.replace("__DATA__", json.dumps(secs, ensure_ascii=False))
               .replace("__PAGES__", json.dumps(pages, ensure_ascii=False))
               .replace("__DISCLAIMER__", disclaimer())
               .replace("__TOTAL__", str(total))
               .replace("__SECTIONS__", str(len(secs))))
    os.makedirs(os.path.join(ROOT, "web"), exist_ok=True)
    json.dump(secs, open(os.path.join(ROOT, "web", "data.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    outp = os.path.join(ROOT, "web", "index.html")
    open(outp, "w", encoding="utf-8").write(html)
    todo = sum(1 for s in secs for i in s["items"] if not i["src_done"])
    print(f"✅ {len(secs)} 节 / {total} 条 → web/index.html ({os.path.getsize(outp)//1024} KB)")
    print(f"   来源待补：{todo} / {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
