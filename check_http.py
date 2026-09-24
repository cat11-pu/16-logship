"""check_http.py：起服务、按脚本走一圈，打印验收面。"""
import json
import sys
import threading
import urllib.error
import urllib.request

from server import serve


def call(method, url, body=None):
    request = urllib.request.Request(url, data=body, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def parse(text):
    try:
        return json.loads(text)
    except Exception:
        return {"_raw": (text or "")[:60]}


def main() -> int:
    spec = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "sample/ship.json", encoding="utf-8"))
    server = serve(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % server.server_port
    for item in spec["appends"]:
        call("POST", base + "/append", json.dumps(item).encode())
    first = parse(call("GET", base + "/sync?offset=0")[1])
    again = parse(call("GET", base + "/sync?offset=" + str(first.get("offset")))[1])
    stats = parse(call("GET", base + "/state")[1])
    recovered = parse(call("POST", base + "/recover", b"{}")[1])
    print("首轮拉取条数 =", len(first.get("entries") or []))
    print("首轮水位 =", first.get("offset"))
    print("重复拉取条数 =", len(again.get("entries") or []))
    print("重复判定条数 =", again.get("duplicates"))
    print("快照覆盖的 offset =", first.get("snapshot_offset"))
    print("追赶条数 =", again.get("catches"))
    print("重启恢复后 offset =", recovered.get("offset"))
    print("不变量（offset 单调） =", recovered.get("monotonic"))
    server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
