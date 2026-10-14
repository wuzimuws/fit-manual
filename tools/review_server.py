#!/usr/bin/env python3
"""审核模式的本地写回服务。只在你自己的机器上跑，不对外。

    python3 tools/review_server.py           # 然后打开 http://127.0.0.1:8787

页面里在「审核模式」下点「编辑原文」，直接改这一条的 markdown（就是 book/*.md 里的原文，
一字不差），点保存 → 写回源文件 → 自动重建通读版和网页 → 返回校验结果。

为什么要有这个服务：网页是 file:// 打开的，浏览器不让它写本地文件。
走 http://127.0.0.1 才能 POST 回来。

安全：
  · 只监听 127.0.0.1，只有本机能连
  · 只改 book/ 下的 .md，且只替换「### N. 」开头的那一条，其余一字不动
  · 改完立刻跑 tools/check.sh，有问题把报错一起返回给你
  · 源文件由 git 兜底：改坏了 git checkout -- book/ 就回来了
"""
import http.server
import json
import os
import re
import subprocess
import sys
import urllib.parse
from typing import Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
BOOK = os.path.join(ROOT, "book")
PORT = 8787

RE_ENTRY = re.compile(r"^### (\d+)\. .*?(?=^### \d+\. |\Z)", re.M | re.S)


def sec_file(sec_no):
    for fn in sorted(os.listdir(BOOK)):
        if fn.endswith(".md") and fn.startswith(f"{sec_no:02d}-"):
            return os.path.join(BOOK, fn)
    return None


def read_entry(sec_no: int, item_no: int
               ) -> Tuple[Optional[str], Optional[str], Optional[re.Match]]:
    """→ (文件路径, 全文, 该条的正则匹配)；找不到就返回 None"""
    path = sec_file(sec_no)
    if not path:
        return None, None, None
    text = open(path, encoding="utf-8").read()
    for m in RE_ENTRY.finditer(text):
        if int(m.group(1)) == item_no:
            return path, text, m
    return path, text, None


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=WEB, **kw)

    def log_message(self, *args):             # 静音，别刷屏
        pass

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/api/raw":
            q = urllib.parse.parse_qs(u.query)
            try:
                sec_no, item_no = int(q["sec"][0]), int(q["no"][0])
            except (KeyError, ValueError):
                return self._json(400, {"error": "缺少 sec / no 参数"})
            path, _, m = read_entry(sec_no, item_no)
            if not (path and m):
                return self._json(404, {"error": f"{sec_no} 节没有第 {item_no} 条"})
            return self._json(200, {"file": os.path.basename(path), "text": m.group(0)})
        return super().do_GET()

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != "/api/save":
            return self._json(404, {"error": "没有这个接口"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            sec_no, item_no, newtext = int(body["sec"]), int(body["no"]), body["text"]
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            return self._json(400, {"error": f"请求不对：{e}"})

        path, text, m = read_entry(sec_no, item_no)
        if not (path and text and m):
            return self._json(404, {"error": f"{sec_no} 节没有第 {item_no} 条"})
        if not re.match(rf"^### {item_no}\. ", newtext):
            return self._json(400, {"error": f"新内容必须以「### {item_no}. 」开头——条号不能改"})

        # 只替换这一条，其余一字不动。尾部空白沿用原文的——否则改文件里最后一条会凭空多个空行
        old = m.group(0)
        tail = old[len(old.rstrip()):] or "\n\n"
        out = text[:m.start()] + newtext.rstrip() + tail + text[m.end():]
        open(path, "w", encoding="utf-8").write(out)

        # 重建 + 体检
        build, check = "", ""
        for cmd, key in ((["python3", "tools/build_book.py"], "build"),
                         (["python3", "tools/build_web.py"], "build"),
                         (["bash", "tools/check.sh"], "check")):
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            out_ = (r.stdout + r.stderr).strip()
            if key == "check":
                check = out_
            else:
                build += out_ + "\n"
        ok = "✅ 全部通过" in check
        return self._json(200, {"ok": ok, "file": os.path.basename(path) if path else "",
                                "build": build.strip(), "check": check.strip()})


def main():
    if not os.path.isdir(WEB):
        print("❌ 先跑 python3 tools/build_web.py 生成 web/")
        return 1
    os.chdir(ROOT)
    with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as s:
        print(f"审核服务已启动 →  http://127.0.0.1:{PORT}/")
        print("（只有本机能连；Ctrl-C 停）")
        try:
            s.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
