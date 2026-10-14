#!/usr/bin/env python3
"""列出全书每一处「第 N 条」引用，并打印它实际指向的条目标题。

check.sh 只能查出「条号越界」，查不出「条号存在但不是想说那条」。
插条 / 删条 / 移动条 / 换节序 之后，**必须跑这个脚本，逐行核对语义**。

用法：  python3 tools/verify_refs.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refs  # noqa: E402

ROOT = refs.ROOT
PAT = re.compile(r"(?:(\d{1,2})\s*节)?第\s*([\d、,，\s]+?)\s*条")


def main():
    secs, index, problems = refs.load()
    if problems:
        for p in problems:
            print("❌", p)
        return 1

    titles = {s["no"]: [it["title"] for it in s["items"]] for s in secs}

    docs = [os.path.join(refs.B, s["file"]) for s in secs]
    for f in ["前言.md", "结语.md", "附录-参考书目.md", "README.md"]:
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            docs.append(p)

    n = 0
    for path in docs:
        t = open(path, encoding="utf-8").read()
        base = os.path.basename(path)
        own = base.split("-")[0] if base[0].isdigit() else None
        for line_no, line in enumerate(t.split("\n"), 1):
            for m in PAT.finditer(line):
                # 排除镜像标记行与字段标签行
                if line.lstrip().startswith("<!--"):
                    continue
                if m.group(1):
                    target = int(m.group(1))
                elif own and int(own) in titles:
                    target = int(own)
                else:
                    continue
                if target not in titles:
                    continue
                nums = [int(x) for x in re.findall(r"\d+", m.group(2))]
                got = []
                for x in nums:
                    got.append(titles[target][x - 1] if 1 <= x <= len(titles[target])
                               else f"❌越界({len(titles[target])}条)")
                ctx = line.strip()
                ctx = ctx[max(0, m.start() - 26):m.end() + 18]
                print(f"{base}:{line_no}  [{target} 节第 {m.group(2).strip()} 条]")
                print(f"    → {'、'.join(got)}")
                print(f"    …{ctx}…")
                n += 1
    print(f"\n共 {n} 处引用。逐行确认「→ 后面那条」是不是正文想说的那条。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
