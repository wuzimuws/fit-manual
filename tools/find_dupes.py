#!/usr/bin/env python3
"""查重复条目：跨节 + 同节，TF-IDF 余弦相似度。

用法：  python3 tools/find_dupes.py [阈值，默认 0.13]
说明：  镜像条自动跳过；问句套话（什么时候/要不要/怎么办…）不计入特征词，
        避免「什么时候可以脱离教练」和「什么时候不要练」这种假阳性。
"""
import os
import re
import sys
import math
import itertools
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refs  # noqa: E402

BOILER = re.compile(
    r"什么时候|要不要|怎么办|怎么|如何|哪些|什么|多少|可以|该不该|还是|到底|是不是|有没有|值得|吗|？|\?"
)


def toks(s):
    s = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", " ", s)
    out = []
    for w in s.split():
        if re.fullmatch(r"[A-Za-z0-9]+", w):
            out.append(w.lower())
            continue
        out += [w[i:i + 2] for i in range(len(w) - 1)]
        out += [w[i:i + 3] for i in range(len(w) - 2)]
    return out


def main():
    thresh = float(sys.argv[1]) if len(sys.argv) > 1 else 0.13
    secs, index, _ = refs.load()

    items = []
    for s in secs:
        for it in s["items"]:
            if it["mirror"]:
                continue
            items.append({
                "sec": s["no"], "secn": s["name"], "no": it["no"],
                "title": it["title"],
                "txt": BOILER.sub("", it["title"]) + " " + " ".join(it[f] for f in refs.FIELDS),
            })
    N = len(items)
    docs = [Counter(toks(x["txt"])) for x in items]
    df = defaultdict(int)
    for d in docs:
        for k in d:
            df[k] += 1
    idf = {k: math.log(N / max(v, 1)) + 1 for k, v in df.items()}
    vecs = []
    for d in docs:
        v = {k: c * idf[k] for k, c in d.items() if idf[k] > 1.4}
        n = math.sqrt(sum(x * x for x in v.values())) or 1
        vecs.append({k: x / n for k, x in v.items()})

    def cos(a, b):
        if len(a) > len(b):
            a, b = b, a
        return sum(x * b.get(k, 0) for k, x in a.items())

    hits = []
    for i, j in itertools.combinations(range(N), 2):
        s = cos(vecs[i], vecs[j])
        if s >= thresh:
            hits.append((s, i, j))
    hits.sort(reverse=True)

    if not hits:
        print(f"✅ 没找到相似度 ≥ {thresh} 的条目（共 {N} 条，镜像条已跳过）")
        return 0

    print(f"相似度 ≥ {thresh} 的条目：{len(hits)} 组（共 {N} 条，镜像条已跳过）\n")
    for s, i, j in hits:
        a, b = items[i], items[j]
        same = "同节" if a["sec"] == b["sec"] else "跨节"
        shared = sorted(((vecs[i][k] * vecs[j].get(k, 0), k) for k in vecs[i] if k in vecs[j]),
                        reverse=True)[:8]
        print(f"■ {s:.3f}  [{a['sec']}·{a['no']}] {a['title']}")
        print(f"         ⟷ [{b['sec']}·{b['no']}] {b['title']}   （{same}）")
        print(f"    共用特征：{'、'.join(k for _, k in shared)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
