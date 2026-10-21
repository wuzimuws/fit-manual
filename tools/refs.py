#!/usr/bin/env python3
"""解析 book/*.md，并展开「镜像条」。

镜像条 = 正文只存在源条里，此处由本模块从源条复制内容展开。
标记写法（在条目标题下第一行）：

    <!-- 引用：01 节第 3 条 -->

于是同一条内容只有一个真源（源条），但它可以在多个位置被显示。
build_web.py（网页版）与 build_book.py（通读版）都调用本模块，
保证两处展开结果一致。
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, "book")
# 版本号：网页、PDF 的封面/页脚都从这里取，改这一行两边同步
BOOK_VERSION = "20261021"

FIELDS = ["总结性建议", "具体地", "为什么", "主观证据等级", "来源"]
RE_REF = re.compile(r"<!-- 引用：(\d{1,2}) 节第 (\d+) 条 -->")


def _split_body(im_body):
    """切掉条末的 '---' 与页脚。"""
    return re.split(r"\n---\s*\n", im_body)[0].strip()


def _parse_file(fn):
    t = open(os.path.join(B, fn), encoding="utf-8").read()
    m = re.search(r"^# (\d+)\. ([^\n]+)", t, re.M)
    if not m:
        return None
    sec_no, sec_name = int(m.group(1)), m.group(2).strip()
    rest = t[m.end():]

    # 按二级标题（## 主题X）切块；没有二级标题的节就是整节一块。
    # 切块还顺带修了一个 bug：块边界让「## 主题二」不再落进上一条的「来源」里。
    parts = re.split(r"^## +(.+?)\s*$", rest, flags=re.M)
    if len(parts) == 1:
        blocks = [{"theme": None, "body": rest}]
        # 没有 ## 时，节头只到第一个条目为止——否则整节正文会被当成节头
        lead = rest[:rest.index("### ")] if "### " in rest else rest
    else:
        lead = parts[0]
        blocks = [{"theme": parts[k].strip(), "body": parts[k + 1]}
                  for k in range(1, len(parts), 2)]
    intro = re.sub(r"\n---\s*\n", "\n", lead).strip()
    if "### " in intro:                       # 兜底：节头里绝不允许出现条目
        intro = intro[:intro.index("### ")].strip()

    items, themes = [], []
    for b in blocks:
        body_all = b["body"]
        first = body_all.find("### ")
        tlead = (body_all[:first] if first >= 0 else body_all).strip()
        tlead = re.sub(r"\n---\s*\n", "\n", tlead).strip()
        got = []
        for im in re.finditer(r"^### (\d+)\. ([^\n]+)\n(.*?)(?=^### \d+\. |\Z)",
                              body_all, re.M | re.S):
            body = _split_body(im.group(3))
            it = {
                "no": int(im.group(1)),
                "title": im.group(2).strip(),
                "sec_no": sec_no,
                "sec": sec_name,
                "theme": b["theme"],
                "file": fn,
                "raw": body,
                "mirror": None,
            }
            ref = RE_REF.search(body)
            if ref:
                it["mirror"] = (int(ref.group(1)), int(ref.group(2)))
            for f in FIELDS:
                mm = re.search(r"^- \*\*" + f + r"\*\*：?(.*?)(?=\n- \*\*|\Z)", body, re.M | re.S)
                # 只去尾部空白 + 行首换行；不能 .strip()，否则第一个子项的缩进会被吃掉
                it[f] = mm.group(1).rstrip().lstrip("\n") if mm else ""
            items.append(it)
            got.append(it["no"])
        if b["theme"]:
            themes.append({"name": b["theme"], "lead": tlead, "nos": got})

    return {"no": sec_no, "name": sec_name, "intro": intro,
            "items": items, "themes": themes, "file": fn}


def _guard_orphan_items():
    """⚠️ 闸：一旦某节用了 `## 主题` 分块，第一个 `## ` 之前就不该再有条目——
    解析器把那段当节头，里面的 `### N.` 会被静默丢掉（实测：丢了整整一条，条数从 88 变 87，
    而 check.sh 的「条号连续」检查也看不出来）。宁可报错停下。
    """
    bad = []
    for fn in sorted(os.listdir(B)):
        if not fn.endswith(".md"):
            continue
        t = open(os.path.join(B, fn), encoding="utf-8").read()
        m = re.search(r"(?m)^# (\d+)\. ", t)
        if not m:
            continue
        rest = t[m.end():]
        first_h2 = rest.find("\n## ")
        if first_h2 < 0:
            continue                      # 没分块，整节一块，正常
        if "### " in rest[:first_h2]:
            sec = re.match(r"(\d+)", t[m.end():].strip()).group(1)
            title = re.search(r"(?m)^### (\d+)\. ([^\n]+)", rest[:first_h2])
            bad.append("节 %s 用了 ## 主题分块，但第一个 ## 之前还有条目「%s」——它会被静默丢掉。"
                       "把这一条挪进某个主题块里。" % (sec, title.group(2)[:40] if title else "?"))
    return bad


def load():
    """返回 (sections, index, problems)。index 的键是 (节号, 条号)。镜像条已展开。"""
    orphan = _guard_orphan_items()
    secs = []
    for fn in sorted(f for f in os.listdir(B) if f.endswith(".md")):
        s = _parse_file(fn)
        if s:
            secs.append(s)
    index = {(s["no"], it["no"]): it for s in secs for it in s["items"]}

    problems = list(orphan)
    for s in secs:
        for it in s["items"]:
            if not it["mirror"]:
                continue
            src = index.get(it["mirror"])
            if src is None:
                problems.append(
                    f"{it['file']} 第{it['no']}条：引用「{it['mirror'][0]} 节第 {it['mirror'][1]} 条」不存在"
                )
                continue
            for f in FIELDS:
                it[f] = src[f]
            it["mirror_title"] = src["title"]
            it["mirror_sec"] = src["sec"]
    return secs, index, problems


def real_count(sections):
    """不含镜像条的条数（栏位校验用）。"""
    return sum(1 for s in sections for it in s["items"] if not it["mirror"])


if __name__ == "__main__":
    secs, index, problems = load()
    n_mirror = sum(1 for s in secs for it in s["items"] if it["mirror"])
    print(f"{len(secs)} 节 · {sum(len(s['items']) for s in secs)} 条（其中镜像 {n_mirror} 条）")
    for s in secs:
        for it in s["items"]:
            if it["mirror"]:
                print(f"  {s['no']}节第{it['no']}条「{it['title']}」 ← {it['mirror'][0]} 节第 {it['mirror'][1]} 条「{it.get('mirror_title','')}」")
    if problems:
        print("\n❌", *problems, sep="\n  ")
