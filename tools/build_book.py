#!/usr/bin/env python3
"""生成 全书-通读版.md（8 节拼合，镜像条自动展开）。

用法：  python3 tools/build_book.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refs  # noqa: E402

ROOT = refs.ROOT


def render_item(it, expanded=True):
    out = [f"### {it['no']}. {it['title']}", ""]
    if it["mirror"]:
        sn, ino = it["mirror"]
        out.append(
            f"> 本条与 {sn:02d} 节第 {ino} 条「{it.get('mirror_title','')}」是同一件事，"
            f"**正文以该条为准**（下面内容为自动展开，请勿在此处单独修改）。"
        )
        out.append("")
    for f in refs.FIELDS:
        val = it[f]
        # 值是「一行标签 + 若干子项」时，标签单独一行，子项整块接在后面
        if f == "具体地" and re.match(r"^\s*[-*] ", val.split("\n")[0]):
            out.append(f"- **{f}**：")
            out.append(val)
        else:
            out.append(f"- **{f}**：{val}")
    out.append("")
    return "\n".join(out)


def render_section(s):
    out = [f"# {s['no']}. {s['name']}", "", s["intro"], "", "---", ""]
    for it in s["items"]:
        out.append(render_item(it))
    out.append("---")
    out.append("")
    return "\n".join(out)


def main():
    secs, index, problems = refs.load()
    if problems:
        print("❌ 引用有问题：")
        for p in problems:
            print("  -", p)
        return 1

    parts = [
        open(os.path.join(ROOT, "README.md"), encoding="utf-8").read(),
        "\n\n---\n\n> **以下为正文全文**\n",
        "\n\n---\n\n",
        open(os.path.join(ROOT, "前言.md"), encoding="utf-8").read(),
    ]
    for s in secs:
        parts.append("\n\n---\n\n")
        parts.append(render_section(s))
    parts.append("\n\n---\n\n")
    parts.append(open(os.path.join(ROOT, "结语.md"), encoding="utf-8").read())
    parts.append("\n\n---\n\n")
    parts.append(open(os.path.join(ROOT, "附录-参考书目.md"), encoding="utf-8").read())

    outp = os.path.join(ROOT, "全书-通读版.md")
    open(outp, "w", encoding="utf-8").write("".join(parts))
    n_mirror = sum(1 for s in secs for it in s["items"] if it["mirror"])
    print(f"✅ 全书-通读版.md （{os.path.getsize(outp)//1024} KB）"
          f" · {sum(len(s['items']) for s in secs)} 条（镜像展开 {n_mirror} 条）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
