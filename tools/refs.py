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
FIELDS = ["总结性建议", "具体地", "为什么这样建议", "主观证据等级", "来源"]
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
    head_end = t.index("### ") if "### " in t else len(t)
    intro = t[m.end():head_end].strip().strip("-").strip()

    items = []
    for im in re.finditer(r"^### (\d+)\. ([^\n]+)\n(.*?)(?=^### \d+\. |\Z)", t, re.M | re.S):
        body = _split_body(im.group(3))
        it = {
            "no": int(im.group(1)),
            "title": im.group(2).strip(),
            "sec_no": sec_no,
            "sec": sec_name,
            "file": fn,
            "raw": body,
            "mirror": None,
        }
        ref = RE_REF.search(body)
        if ref:
            it["mirror"] = (int(ref.group(1)), int(ref.group(2)))
        for f in FIELDS:
            mm = re.search(r"^- \*\*" + f + r"\*\*：?(.*?)(?=\n- \*\*|\Z)", body, re.M | re.S)
            it[f] = mm.group(1).strip() if mm else ""
        items.append(it)

    return {"no": sec_no, "name": sec_name, "intro": intro, "items": items, "file": fn}


def load():
    """返回 (sections, index)。index 的键是 (节号, 条号)。镜像条已展开。"""
    secs = []
    for fn in sorted(f for f in os.listdir(B) if f.endswith(".md")):
        s = _parse_file(fn)
        if s:
            secs.append(s)
    index = {(s["no"], it["no"]): it for s in secs for it in s["items"]}

    problems = []
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
