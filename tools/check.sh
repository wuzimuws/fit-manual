#!/usr/bin/env bash
# 全书质检：栏位齐全 / 条号连续 / 引用不越界 / 镜像引用有效 / 无过期条数声明 / 无软化词 / 无 AI 腔调
set -e
cd "$(dirname "$0")/.."
python3 - <<'PY'
import os, re, sys
import subprocess

B = "book"
files = sorted(f for f in os.listdir(B) if f.endswith(".md"))
fields = ["总结性建议", "具体地", "为什么", "主观证据等级", "来源"]
RE_MIRROR = re.compile(r"<!-- 引用：(\d{1,2}) 节第 (\d+) 条 -->")
err = []

# ---------- 第一遍：建索引（节号 → 条数、条标题） ----------
idx, titles = {}, {}
for fn in files:
    t = open(os.path.join(B, fn), encoding="utf-8").read()
    sec = fn.split("-")[0]
    idx[sec] = len(re.findall(r"^### \d+\. ", t, re.M))
    titles[sec] = re.findall(r"^### \d+\. ([^\n]+)", t, re.M)

# ---------- 第二遍：逐文件检查 ----------
for fn in files:
    t = open(os.path.join(B, fn), encoding="utf-8").read()
    sec = fn.split("-")[0]

    nums = [int(x) for x in re.findall(r"^### (\d+)\. ", t, re.M)]
    if nums != list(range(1, len(nums) + 1)):
        err.append(f"{fn}: 条号不连续 {nums}")

    # 镜像条：正文在源条，豁免栏位检查；但引用目标必须存在且不越界
    mirrors = RE_MIRROR.findall(t)
    for sn, ino in mirrors:
        tgt = sn.zfill(2)
        if tgt not in idx:
            err.append(f"{fn}: 引用目标「{tgt} 节」不存在")
        elif not (1 <= int(ino) <= idx[tgt]):
            err.append(f"{fn}: 引用「{tgt} 节第 {ino} 条」越界（该节只有 {idx[tgt]} 条）")

    n_mirror = len(mirrors)
    for f in fields:
        got = t.count("- **" + f + "**")
        want = idx[sec] - n_mirror
        if got != want:
            err.append(f"{fn}: 栏位「{f}」数量不符（{got}，应为 {want}）")

    # 半角标点不得夹在中文里。但「来源」整栏先摘掉——文献引用按 GB/T 7714 就是
    # 用半角「:」和「,」（北京: 科学出版社 / 张静, 译），那是规范，不是笔误。
    t_ = re.sub(r"^- \*\*来源\*\*：.*?(?=\n- \*\*|\Z)", "", t, flags=re.M | re.S)
    for m_ in re.finditer(r"[\u4e00-\u9fff][,;:!?]|[,;:!?][\u4e00-\u9fff]", t_):
        err.append(f"{fn}: 中文里混了半角标点「{m_.group(0)}」")

    # 行内 ①②③ 枚举（同一行 ≥2 个）应拆成子项
    for ln_ in t.split("\n"):
        if len(re.findall(r"[①-⑨]", ln_)) >= 2:
            err.append(f"{fn}: 行内枚举「{ln_.strip()[:34]}…」应拆成子项")

    # 不要用「（N）」行式枚举——统一用「  - 」子项，否则网页上没有项目符号
    for m_ in re.finditer(r"^\s*（\d+）", t, re.M):
        err.append(f"{fn}: 行首枚举「{m_.group(0).strip()}」应改成「  - 」子项")

    for w in ["我觉得", "其实", "我建议", "我发现"]:
        if w in t:
            err.append(f"{fn}: 残留软化词「{w}」")

    # 页脚重复
    for m_ in re.finditer(r"^> \*\*下一节[^\n]*", t, re.M):
        if m_.group(0).count("——") > 1:
            err.append(f"{fn}: 页脚重复")

    # 同节内重复句（≥14 字；跳过字段标签、表格线、引用行）
    body_only = "\n".join(l for l in t.split("\n")
                          if not l.lstrip().startswith(">")
                          and not l.lstrip().startswith("<!--"))
    sents = [s.strip() for s in re.split(r"[。！？\n]", body_only)]
    sents = [s for s in sents if len(s) >= 14
             and not s.startswith("- **") and not re.match(r"^[\s|:-]+$", s)]
    seen = {}
    for s in sents:
        if s in seen:
            err.append(f"{fn}: 重复句「{s[:30]}」")
        seen[s] = 1

    # AI 腔调：对偶式「不是 X，是 Y」等
    for p_ in [r"不是[^。！？\n]{1,40}?，是", r"不是[^。！？\n]{1,40}?，?而是",
               r"不是[^。！？\n]{1,30}?。\s*是", r"问题不在[^。！？\n]{1,30}?，?在",
               r"真正[^。！？\n]{0,20}?的不是"]:
        m_ = re.search(p_, t)
        if m_:
            err.append(f"{fn}: AI 腔调「{m_.group(0)}」")

# ---------- 非正文文档：只查软化词 / AI 腔 / 陈旧节名 ----------
EXTRA = ["前言.md", "结语.md", "附录-参考书目.md", "README.md"]
for path in EXTRA:
    if not os.path.exists(path):
        continue
    t = open(path, encoding="utf-8").read()
    # 半角标点不得夹在中文里
    for m_ in re.finditer(r"[\u4e00-\u9fff][,;:!?]|[,;:!?][\u4e00-\u9fff]", t):
        err.append(f"{fn}: 中文里混了半角标点「{m_.group(0)}」")

    # 行内 ①②③ 枚举（同一行 ≥2 个）应拆成子项
    for ln_ in t.split("\n"):
        if len(re.findall(r"[①-⑨]", ln_)) >= 2:
            err.append(f"{fn}: 行内枚举「{ln_.strip()[:34]}…」应拆成子项")

    # 不要用「（N）」行式枚举——统一用「  - 」子项，否则网页上没有项目符号
    for m_ in re.finditer(r"^\s*（\d+）", t, re.M):
        err.append(f"{fn}: 行首枚举「{m_.group(0).strip()}」应改成「  - 」子项")

    for w in ["我觉得", "其实", "我建议", "我发现"]:
        if w in t:
            err.append(f"{path}: 残留软化词「{w}」")
    for p_ in [r"不是[^。！？\n]{1,40}?，?[是而]", r"问题不在[^。！？\n]{1,30}?，?在"]:
        m_ = re.search(p_, t)
        if m_:
            err.append(f"{path}: AI 腔调「{m_.group(0)}」")
    for stale in ["「地基」", "02 节地基", "「先说清楚」"]:
        if stale in t:
            err.append(f"{path}: 陈旧表述「{stale}」")

# ---------- 解析后检查：「具体地」子项缩进必须一致 ----------
# 这类 bug 只发生在解析层（天真的 .strip() 会吃掉第一个子项的缩进），
# 源 markdown 里缩进是对的，所以必须查解析结果。
sys.path.insert(0, os.path.join("tools"))
import refs  # noqa: E402
secs_, _, probs_ = refs.load()
# ---------- 解析后检查：节头不得吞进条目 ----------
for s_ in secs_:
    if "- **" in s_["intro"] or "### " in s_["intro"]:
        err.append(f"{s_['no']:02d} 节（{s_['name']}）：节头里混进了条目正文")
    if len(s_["intro"]) > 900:
        err.append(f"{s_['no']:02d} 节：节头异常长（{len(s_['intro'])} 字），疑似吞进了正文")

for p_ in probs_:
    err.append(p_)

# ---------- 手写引用的条号是否漂移 ----------
# 插删移动条目会让后面的条号整体位移，正文里手写的「第 N 条」不会自己变。
# citelock.py 按【标题】锁定目标，能查出漂移；跑 --fix 自动改数字。
_r_ = subprocess.run([sys.executable, os.path.join("tools", "citelock.py")],
                     capture_output=True, text=True)
if _r_.returncode != 0:
    for _l in _r_.stdout.strip().split("\n"):
        if _l.strip().startswith(("❗", "❌", "⚠️")) or "→ 应为" in _l:
            err.append("引用锁定：" + _l.strip())
for s_ in secs_:
    for it_ in s_["items"]:
        if it_["mirror"]:
            continue
        val_ = it_["具体地"]
        ind = [len(x) - len(x.lstrip()) for x in val_.split("\n")
               if re.match(r"^\s*[-*] ", x)]
        if ind and min(ind) == 0 and max(ind) > 0:
            err.append(f"{s_['no']:02d} 节第 {it_['no']} 条："
                       f"「具体地」子项缩进不一致（{ind}）——网页上会第一个顶格、后面缩进")

# ---------- 引用不得指向镜像条（应指向源条） ----------
mirror_targets = set()          # 镜像条自身的位置，例如 (08, 1)
for fn in files:
    t = open(os.path.join(B, fn), encoding="utf-8").read()
    sec = fn.split("-")[0]
    for im in re.finditer(r"^### (\d+)\. [^\n]+\n(.*?)(?=^### \d+\. |\Z)", t, re.M | re.S):
        if RE_MIRROR.search(im.group(2)):
            mirror_targets.add((sec, int(im.group(1))))

# ---------- 条号引用越界（正文 + 非正文文档） ----------
pat = re.compile(r"(?:(\d{1,2}) 节)?第 ([\d、,，]+) 条")
for fn in files + EXTRA:
    path = os.path.join(B, fn) if fn in files else fn
    if not os.path.exists(path):
        continue
    sec_default = fn.split("-")[0] if fn in files else None
    t = open(path, encoding="utf-8").read()
    for m in pat.finditer(t):
        target = (m.group(1) or sec_default or "").zfill(2)
        if target not in idx:
            continue
        for n in [int(x) for x in re.findall(r"\d+", m.group(2))]:
            if not (1 <= n <= idx[target]):
                err.append(f"{path}: 引用「{target}节第{n}条」越界（该节只有 {idx[target]} 条）")
            elif (target, n) in mirror_targets:
                err.append(f"{path}: 引用「{target}节第{n}条」指向的是镜像条，应改指其源条")

# ---------- 过期条数声明 ----------
total = sum(idx.values())
for fn in files + EXTRA:
    path = os.path.join(B, fn) if fn in files else fn
    if not os.path.exists(path):
        continue
    t = open(path, encoding="utf-8").read()
    for m in re.finditer(r"(\d+) 条", t):
        if int(m.group(1)) > 20:
            err.append(f"{path}: 过期条数声明「{m.group(0)}」")

mir = sum(len(RE_MIRROR.findall(open(os.path.join(B, f), encoding="utf-8").read())) for f in files)
print(f"条数：{idx}  合计 {total}（其中镜像条 {mir}）")
if err:
    print("\n❌ 发现问题：")
    for e in err:
        print("  -", e)
    sys.exit(1)
print("✅ 全部通过")
PY
