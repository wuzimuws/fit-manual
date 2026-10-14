#!/usr/bin/env python3
"""引用条号锁定：让正文里手写的「第 N 条」在插删移动后自动跟着变。

问题：正文里人写的「见 02 节第 15 条」，一旦在 02 节中间插入或删除条目，
后面的条号整体位移，引用就静默指错——而越界校验仍然全绿（它只查条号存不存在）。
之前已经踩过一次：「心理障碍」提到第 1 条后，结语和条内 2 处引用错位。

做法：锁文件记的不是条号，是「这条引用当时指向哪一条（按标题）」。
校验/重建时按标题找回该条【当前】的条号：
  · 条号变了        → 自动改源文件里的数字（--fix）
  · 标题找不到了    → 报错停下（那条被删或改名了，必须人来决定）
  · 出现没锁过的新引用 → 报错停下（需要人确认它指向哪一条，再 --update）

用法：
  python3 tools/citelock.py            # 只读校验（check.sh 调这个）
  python3 tools/citelock.py --fix      # 校验 + 自动改条号
  python3 tools/citelock.py --update   # 把新引用按当前条号登记进锁文件
  python3 tools/citelock.py --list     # 列出每条引用当前指向哪一条
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refs  # noqa: E402

ROOT = refs.ROOT
LOCK = os.path.join(ROOT, "tools", "cite-lock.json")

RE_SEC = re.compile(r"^# (\d+)\. ")
RE_ITEM = re.compile(r"^### (\d+)\. (.+?)\s*$")
RE_FIELD = re.compile(r"^- \*\*(.+?)\*\*")
# 「第 15 条」/「02 节第 15 条」；节号缺省 = 本条所在节
RE_CITE = re.compile(r"(?:(\d{1,2})\s*节\s*)?第\s*(\d+)\s*条")


def scan_file(fn):
    """按文件顺序扫出所有手写引用，带回精确偏移，便于原地改数字。"""
    path = os.path.join(refs.B, fn)
    text = open(path, encoding="utf-8").read()
    out, sec, item, title, field, k = [], None, None, None, None, {}
    pos = 0
    for line in text.splitlines(keepends=True):
        m = RE_SEC.match(line)
        if m:
            sec, item, title, field, k = int(m.group(1)), None, None, None, {}
        else:
            m = RE_ITEM.match(line)
            if m:
                item, title, field, k = int(m.group(1)), m.group(2).strip(), None, {}
            else:
                m = RE_FIELD.match(line)
                if m and m.group(1) in refs.FIELDS:
                    field = m.group(1)
        if sec and item and field:
            for c in RE_CITE.finditer(line):
                # 键用「节号·源条目标题[栏位]#序号」——不用源条目的条号，
                # 因为源条目自己也会被重新编号，用条号当键一插删就全部失配
                grp = f"{sec}\N{MIDDLE DOT}{title}[{field}]"
                k[grp] = k.get(grp, -1) + 1
                out.append({
                    "key": f"{grp}#{k[grp]}",
                    "file": fn,
                    "src_sec": sec,
                    "src_no": item,
                    "src_title": title,
                    "field": field,
                    "text": c.group(0),
                    "sec": int(c.group(1)) if c.group(1) else sec,
                    "no": int(c.group(2)),
                    # 数字在文件里的绝对偏移，改的时候只替换这一段
                    "start": pos + c.start(2),
                    "end": pos + c.end(2),
                })
        pos += len(line)
    return text, out


def load_lock():
    if not os.path.exists(LOCK):
        return {}
    return json.load(open(LOCK, encoding="utf-8"))


def save_lock(lock):
    json.dump(lock, open(LOCK, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, sort_keys=True)


def main():
    fix = "--fix" in sys.argv
    update = "--update" in sys.argv
    listing = "--list" in sys.argv

    secs, index, problems = refs.load()
    if problems:
        print("❌ 引用本身有问题，先修：")
        for p in problems:
            print("  -", p)
        return 1

    # 标题 → 该条当前的 (节号, 条号)；重名时以第一条为准并被标记
    by_title = {}
    for (s_no, i_no), it in sorted(index.items()):
        by_title.setdefault(it["title"], (s_no, i_no))

    lock = load_lock()
    drift, missing, fresh, seen = [], [], [], set()

    for fn in sorted(f for f in os.listdir(refs.B) if f.endswith(".md")):
        text, cites = scan_file(fn)
        for c in cites:
            seen.add(c["key"])
            ent = lock.get(c["key"])
            if not ent:
                fresh.append(c)
                continue
            hit = by_title.get(ent["title"])
            if not hit:
                missing.append((c, ent))
                continue
            real_sec, real_no = hit
            if (real_sec, real_no) != (c["sec"], c["no"]):
                drift.append((c, ent, real_sec, real_no))

    # 锁里指向的引用在源里找不到了（条被删 / 源条目被重新编号）
    orphan = [k for k in lock if k not in seen]

    if listing:
        for fn in sorted(f for f in os.listdir(refs.B) if f.endswith(".md")):
            _, cites = scan_file(fn)
            for c in cites:
                locked = lock.get(c["key"])
                cur = index.get((c["sec"], c["no"]))
                cur_title = cur["title"] if cur else "❗不存在"
                note = ""
                if locked:
                    note = (f"   〔锁定：{locked['title']}〕"
                            if locked["title"] != cur_title else "   〔锁定 ✓〕")
                print(f"  [{'锁' if locked else '新'}] {c['key']:<22} 「{c['text']}」 → "
                      f"{c['sec']:02d} 节「{cur_title}」{note}")

    if drift:
        print(f"\n{'已自动修正' if fix else '❗条号漂移'} {len(drift)} 处：")
        for c, ent, rs, rn in drift:
            print(f"  {c['key']:<22} 「{c['text']}」 → 应为 {rs:02d} 节第 {rn} 条"
                  f"（「{ent['title']}」）")
        if fix:
            by_file = {}
            for c, ent, rs, rn in drift:
                by_file.setdefault(c["file"], []).append((c, ent, rs, rn))
            for fn, lst in by_file.items():
                path = os.path.join(refs.B, fn)
                src = open(path, encoding="utf-8").read()
                out = src
                # 从后往前替换，偏移才不会互相影响；只动数字那几个字符
                for c, ent, rs, rn in sorted(lst, key=lambda x: -x[0]["start"]):
                    out = out[:c["start"]] + str(rn) + out[c["end"]:]
                    lock[c["key"]] = {"sec": rs, "no": rn, "title": ent["title"]}
                # 保险：确认除数字外一个字符都没动
                a = re.sub(r"\d+", "#", src)
                b = re.sub(r"\d+", "#", out)
                if a != b:
                    print(f"❌ {fn}: 替换影响了非数字内容，已放弃写入")
                    return 1
                open(path, "w", encoding="utf-8").write(out)
                print(f"  ✅ 已改 {fn}（{len(lst)} 处，仅替换数字）")

    if update and fresh:
        for c in fresh:
            tgt = index.get((c["sec"], c["no"]))
            if not tgt:
                print(f"  ❌ {c['key']}「{c['text']}」指向不存在的条目，不能登记")
                continue
            lock[c["key"]] = {"sec": c["sec"], "no": c["no"], "title": tgt["title"]}
        print(f"  ✅ 新登记 {len(fresh)} 条引用（按当前条号）")

    if fix:
        # 自检：改完重新扫一遍。这类「改是改了、改错了」的 bug 必须当场撞出来
        _, _, _ = refs.load()
        bad2 = []
        for fn in sorted(f for f in os.listdir(refs.B) if f.endswith(".md")):
            _, cites = scan_file(fn)
            for c in cites:
                ent = lock.get(c["key"])
                if not ent:
                    continue
                hit = by_title.get(ent["title"])
                if hit and hit != (c["sec"], c["no"]):
                    bad2.append((c["key"], c["text"], hit, c["sec"], c["no"]))
        if bad2:
            print(f"\n❌ 修正后自检不通过，还有 {len(bad2)} 处不对（锁文件已写，请手动处理）：")
            for k, txt, hit, cs, cn in bad2:
                print(f"  {k:<22} 「{txt}」 锁定目标现在在第 {hit[1]} 条，正文写的是第 {cn} 条")
            save_lock(lock)
            return 1
        print(f"  ✅ 修正后自检通过")

    if fix or update:
        save_lock(lock)

    err = 0
    if drift and not fix:          # 只有漂移也必须算失败，否则 check.sh 会漏过
        err = 1
    if missing:
        err = 1
        print(f"\n❌ 锁定的引用，目标条目找不到了 {len(missing)} 处"
              f"（被删了或改了标题，必须人来定）：")
        for c, ent in missing:
            print(f"  {c['key']:<22} 「{c['text']}」 原本指向「{ent['title']}」")
    if fresh and not update:
        err = 1
        print(f"\n❌ 出现未登记的手写引用 {len(fresh)} 处（确认指向后跑 --update）：")
        for c in fresh:
            tgt = index.get((c["sec"], c["no"]))
            print(f"  {c['key']:<22} 「{c['text']}」 → 当前指向"
                  f"{c['sec']:02d} 节「{tgt['title'] if tgt else '❗不存在'}」")
    if orphan and not fix:
        print(f"\n⚠️  锁里有 {len(orphan)} 条记录在源里对不上（源条目被重新编号或删除）：")
        for k in sorted(orphan)[:12]:
            print(f"  {k:<22} 锁定「{lock[k]['title']}」")
        if len(orphan) > 12:
            print(f"  …… 还有 {len(orphan) - 12} 条")

    if err == 0 and not drift:
        print(f"\n✅ 手写引用 {len(seen)} 处全部对齐（锁文件 {len(lock)} 条）")
    elif drift and not fix:
        print("\n   修法：python3 tools/citelock.py --fix")
    return err


if __name__ == "__main__":
    sys.exit(main())
