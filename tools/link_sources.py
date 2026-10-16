#!/usr/bin/env python3
"""把「来源」里的书 / 论文引用套上链接（书 → 豆瓣，论文 → PubMed/DOI）。

映射表在 tools/source-links.json，形如：
    [{"match": "肌肉与力量全书", "url": "https://book.douban.com/subject/35140168/", "kind": "book"}]
`match` 是引用行里的一个足够独特的片段，用来认人。

整条引用套成一个链接（作者+标题+[M]+出版社…全在里面）。引用里带 `[M]` `[J]`
文献类型标识，而 markdown 链接是 `[文字](地址)`，方括号会打架——所以把引用正文里的
方括号**转义**成 `\[` `\]`。markdown 渲染出来仍然是 `[M]`，链接却不会断。

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


RE_PREFIX = re.compile(r"^(\s*- \*\*来源\*\*：)(.*)$")
RE_LINK = re.compile(r"\[((?:[^\[\]]|\\[\[\]])+)\]\((https?://[^)\s]+)\)")


def unwrap(line):
    """把已经套好的链接拆回纯文本，返回 (文本, 原URL)。"""
    m = RE_LINK.search(line)
    if not m:
        return line, None
    txt = m.group(1).replace("\\[", "[").replace("\\]", "]")
    return line[:m.start()] + txt + line[m.end():], m.group(2)


def wrap(line):
    """把一条引用行整条做成 markdown 链接；已有链接的返回 None。

    ⚠️ 两处坑：
    ①「  - **来源**：」这个栏位前缀必须留在链接外面，否则栏位标签被吞进链接文字，
       解析器认不出这一栏，check.sh 的「来源豁免半角标点」也跟着失效。
    ② 引用里的 `[M]`/`[J]` 要转义成 `\[M\]`/`\[J\]`，否则 markdown 链接的
       方括号语法会撞上，链接在 `[M]` 处就断了（只剩标题是可点的）。
    """
    if "](http" in line:
        return None
    m0 = RE_PREFIX.match(line)
    prefix, body = (m0.group(1), m0.group(2)) if m0 else ("", line)
    s = body.strip()
    if not s or s in ("无",) or "待你补" in s:
        return None
    esc = s.replace("[", "\\[").replace("]", "\\]")
    return f"{prefix}[{esc}]({{URL}})"


def main():
    dry = "--check" in sys.argv
    rewrap = "--rewrap" in sys.argv        # 先把旧链接拆掉再重包（改了包法之后用）
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
            if rewrap:                      # 拆旧链接，顺便校验原 URL 没变
                stripped, old = unwrap(line)
                if old and old != hit["url"]:
                    print("   ⚠️ URL 将变：%s\n       旧 %s\n       新 %s" % (hit["match"][:40], old, hit["url"]))
                line = stripped
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
