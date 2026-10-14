#!/usr/bin/env bash
# 全书质检：栏位齐全 / 条号引用不越界 / 无过期条数声明
set -e
cd "$(dirname "$0")/.."
python3 - <<'PY'
import os, re, sys
B = "book"
files = sorted(f for f in os.listdir(B) if f.endswith(".md"))
fields = ["总结性建议","具体地","为什么这样建议","主观证据等级","来源"]
idx, err = {}, []
for fn in files:
    t = open(os.path.join(B,fn), encoding="utf-8").read()
    sec = fn.split("-")[0]
    idx[sec] = len(re.findall(r"^### \d+\. ", t, re.M))
    nums = [int(x) for x in re.findall(r"^### (\d+)\. ", t, re.M)]
    if nums != list(range(1, len(nums)+1)):
        err.append(f"{fn}: 条号不连续 {nums}")
    for f in fields:
        if t.count("- **"+f+"**") != idx[sec]:
            err.append(f"{fn}: 栏位「{f}」数量不符")
    for w in ["我觉得","其实","我建议","我发现"]:
        if w in t: err.append(f"{fn}: 残留软化词「{w}」")

# 条号引用越界
pat = re.compile(r"(?:(\d{2}) 节)?第 ([\d、,，]+) 条")
for p in files + ["../前言.md","../结语.md","../README.md"]:
    path = os.path.join(B, p) if not p.startswith("..") else p[3:]
    if not os.path.exists(path): continue
    sec_default = os.path.basename(path).split("-")[0]
    t = open(path, encoding="utf-8").read()
    for m in pat.finditer(t):
        target = m.group(1) or sec_default
        for n in [int(x) for x in re.findall(r"\d+", m.group(2))]:
            if target in idx and not (1 <= n <= idx[target]):
                err.append(f"{os.path.basename(path)}: 引用「{target}节第{n}条」越界")

# 过期条数声明
total = sum(idx.values())
for p in files + ["../前言.md","../结语.md","../README.md"]:
    path = os.path.join(B, p) if not p.startswith("..") else p[3:]
    if not os.path.exists(path): continue
    t = open(path, encoding="utf-8").read()
    for m in re.finditer(r"(\d+) 条", t):
        if int(m.group(1)) > 20:
            err.append(f"{os.path.basename(path)}: 过期条数声明「{m.group(0)}」")

print(f"条数：{ {k:v for k,v in idx.items()} }  合计 {total}")
if err:
    print("\n❌ 发现问题：")
    for e in err: print("  -", e)
    sys.exit(1)
print("✅ 全部通过")
PY
