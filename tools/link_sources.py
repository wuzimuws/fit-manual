#!/usr/bin/env python3
"""把「来源」里的书 / 论文引用套上链接（书 → 豆瓣，论文 → PubMed/DOI）。

映射表在 tools/source-links.json，形如：
    [{"match": "肌肉与力量全书", "url": "https://book.douban.com/subject/35140168/", "kind": "book"}]
`match` 是引用行里的一个足够独特的片段，用来认人。

为什么只给「标题」套链接、不套整行：引用里有 `[M]` `[J]` 文献类型标识，
而 markdown 链接是 `[文字](地址)`——方括号会打架，整行套进去链接就断了。
所以：
    - 行里有 `[M]`/`[J]` → 只把「[M] 之前那段」（作者+标题）套成链接，其余原样
    - 行里没有 → 整行套成链接（APA 格式那种没有方括号的）

幂等：已经套过链接的行会跳过。用法：
    python3 tools/link_sources.py            # 应用映射表
    python3 tools/link_sources.py --check    # 只看会改哪些行，不写
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK = os.path.join(ROOT, "book")
MAP = os.path.join(ROOT, "tools", "source-links.json")
RE_MJ = re.compile(r"^(.*?)\s*(\[[MJ]\b.*)$")


def wrap(line):
    """把一条引用行变成 markdown 链接；已有链接的返回 None。"""
    if "](http" in line:
        return None
    s = line.strip()
    if not s or s in ("无",) or "待你补" in s:
        return None
    m = RE_MJ.match(s)
    if m:                                   # 有 [M]/[J]：只链作者+标题那一段
        head, tail = m.group(1).strip(), m.group(2).strip()
        # 「作者. 标题」——把标题单独拎出来链（作者也一起链进去更省事，读起来也顺）
        return f"[{head}]({{URL}}) {tail}"
    return f"[{s}]({{URL}})"                # 没方括号：整行链


def main():
    dry = "--check" in sys.argv
    table = json.load(open(MAP, encoding="utf-8"))
    hits = {t["match"]: t for t in table}
    changed_files, changed_lines, misses = [], 0, []

    for fn in sorted(f for f in os.listdir(BOOK) if f.endswith(".md")):
        path = os.path.join(BOOK, fn)
        src = open(path, encoding="utf-8").read()
        out_lines, touched = [], 0
        for line in src.split("\n"):
            hit = next((t for k, t in hits.items() if k in line), None)
            if not hit:
                out_lines.append(line)
                continue
            new = wrap(line)
            if not new:
                out_lines.append(line)      # 已经是链接 / 无值
                continue
            out_lines.append(new.replace("{URL}", hit["url"]))
            touched += 1
        if touched:
            changed_files.append(fn)
            changed_lines += touched
            if not dry:
                open(path, "w", encoding="utf-8").write("\n".join(out_lines))

    used = set()
    for fn in sorted(f for f in os.listdir(BOOK) if f.endswith(".md")):
        txt = open(os.path.join(BOOK, fn), encoding="utf-8").read()
        for k in hits:
            if k in txt:
                used.add(k)
    misses = sorted(set(hits) - used)
    print(("🔍 预演（未写入）" if dry else "✅ 已写入") + f"：{len(changed_files)} 个文件、{changed_lines} 行")
    for f in changed_files:
        print("   ", f)
    if misses:
        print(f"⚠️  映射表里这 {len(misses)} 条没在正文里找到（对不上，需要检查）：")
        for k in misses:
            print("   ", k[:70])
    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main())
