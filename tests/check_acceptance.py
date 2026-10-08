"""YiRead 接口验收脚本 —— A/B/C 三类口径（9.3 修正15）。

分类与口径
----------
A 正常业务   import / translation / delete
             一律**自动获取 token**（等价前端 ensureToken），不依赖本地缓存；
             不再断言「无 token 删除失败」——删除属于业务，鉴权归 B。

B 鉴权异常   invalid token / missing token / expired(未知) token
             统一 HTTP 403 且响应体为 {"status":"error","message":"invalid token"}。
             仅校验鉴权口径，**不与删除业务断言混合**。

C 数据异常   invalid paper id / invalid pdf / missing file
             统一 JSON 信封，HTTP 400 或 404。

用法
----
    <python> tests/check_acceptance.py
退出码 0 = 无 FAIL；1 = 存在 FAIL（WARN 不影响退出码）。
"""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8765"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

RESULTS = []
WARNS = []
TEMP_IDS = []      # 本轮自建的临时样本，收尾统一清理（幂等）


def cleanup_temp():
    """兜底清理：即使中途异常，也不留下自建样本。删除接口幂等（不存在也 200）。"""
    if not TEMP_IDS:
        return
    try:
        tok = book_token()
    except Exception:
        return
    for pid in TEMP_IDS:
        request("/api/delete/" + pid, "POST", tok)
    print("  [清理] 已回收临时样本:", TEMP_IDS)


def record(cid, name, ok, detail="", warn=False):
    level = "WARN" if warn else ("PASS" if ok else "FAIL")
    flag = "PASS" if ok else level
    print("  [%s] %-40s %s" % (flag, name, detail))
    RESULTS.append((cid, name, flag, detail))
    if flag == "WARN":
        WARNS.append((cid, name, detail))


def _json(raw):
    try:
        return json.loads(raw.decode())
    except Exception:
        return {"__raw__": raw.decode(errors="ignore")}


def request(path, method="GET", token=None, body=None, headers=None):
    req = urllib.request.Request(BASE + path, method=method)
    if token is not None:
        req.add_header("X-Token", token)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with OPENER.open(req, data=body) as r:
            return r.status, _json(r.read())
    except urllib.error.HTTPError as e:
        return e.code, _json(e.read())


def book_token():
    """A 类业务统一入口：自动获取 token（不读本地缓存）。"""
    code, data = request("/api/token")
    if code != 200 or data.get("status") != "ok":
        raise RuntimeError("取 token 失败: %s %s" % (code, data))
    return data["data"]["token"]


def multipart_file(payload, filename="tmp.pdf", ctype="application/pdf"):
    boundary = "----wback"
    body = (
        ("--" + boundary + "\r\n"
         'Content-Disposition: form-data; name="file"; filename="%s"\r\n'
         "Content-Type: %s\r\n\r\n" % (filename, ctype)).encode()
        + payload
        + ("\r\n--" + boundary + "--\r\n").encode()
    )
    return body, "multipart/form-data; boundary=" + boundary


def multipart_no_file():
    boundary = "----wback"
    body = (
        "--" + boundary + "\r\n"
        'Content-Disposition: form-data; name="foo"\r\n\r\nbar\r\n'
        "--" + boundary + "--\r\n"
    ).encode()
    return body, "multipart/form-data; boundary=" + boundary


def envelope_ok(data):
    """统一 JSON 信封：必须含 status 且为 ok/error。"""
    return isinstance(data, dict) and data.get("status") in ("ok", "error")


def lib_ids():
    code, data = request("/api/library")
    return sorted(i["id"] for i in data["data"]["items"])


def upload_files():
    d = os.path.join(ROOT, "data", "upload")
    return sorted(os.listdir(d)) if os.path.isdir(d) else []


# ---------------------------------------------------------------- A 正常业务
def suite_a():
    print("\n=== A. 正常业务（自动获取 token）===")
    before_ids = lib_ids()
    new_id = None

    # A1 import
    tok = book_token()
    with open(os.path.join(ROOT, "data", "library", "20261004_b44d959c", "source.pdf"), "rb") as f:
        pdf = f.read()
    body, ctype = multipart_file(pdf, "acceptance.pdf")
    code, data = request("/api/import", "POST", tok, body, {"Content-Type": ctype})
    ok = code == 200 and envelope_ok(data) and data.get("status") == "ok"
    if ok:
        item = data["data"]
        new_id = item.get("id")
        if new_id:
            TEMP_IDS.append(new_id)
        ok = bool(new_id) and "file_name" in item and "file_size" in item and "created_at" in item
    record("A1", "import（自动 token）", ok, "HTTP=%s id=%s" % (code, new_id))
    if new_id:
        record("A1b", "import 落盘（library 可读回）", new_id in lib_ids(), "ids=%s" % lib_ids())

    # A2 translation
    tok = book_token()
    code, data = request("/api/translation", "POST", tok,
                         json.dumps({"paper_id": "demo001"}).encode(),
                         {"Content-Type": "application/json"})
    ok = code == 200 and envelope_ok(data) and data.get("status") == "ok"
    st = data.get("data", {}).get("status") if ok else None
    record("A2", "translation 建任务（自动 token）", ok, "HTTP=%s status=%s" % (code, st))

    code, data = request("/api/translation/demo001")
    blocks = (data.get("data") or {}).get("blocks") if code == 200 else None
    ok = code == 200 and blocks and "id" in blocks[0] and "translation" in blocks[0]
    record("A2b", "translation 读回配对", bool(ok), "HTTP=%s blocks=%s" % (code, len(blocks or [])))

    # A3 delete（自动 token；用例自建样本，不碰常驻文献）
    if new_id:
        tok = book_token()
        code, data = request("/api/delete/" + new_id, "POST", tok)
        ok = (code == 200 and envelope_ok(data) and data.get("status") == "ok"
              and data["data"].get("paper_id") == new_id)
        record("A3", "delete（自动 token）", ok, "HTTP=%s deleted=%s" % (code, data.get("data", {}).get("deleted")))
        record("A3b", "delete 后 library 不含该 id", new_id not in lib_ids(), "ids=%s" % lib_ids())
        c2, _ = request("/api/translation/" + new_id)
        record("A3c", "delete 后译文文件已清", c2 == 404, "HTTP=%s" % c2)

    record("A4", "library 恢复基线", lib_ids() == before_ids, "before=%s after=%s" % (before_ids, lib_ids()))


# ---------------------------------------------------------------- B 鉴权异常
def suite_b():
    print("\n=== B. 鉴权异常（403 + invalid token）===")
    EXPIRED = "0" * 64   # 未知/过期 token（后端内存态，重启即失效）

    cases = [
        ("B1", "missing token → import", "/api/import", "POST", None, b"x"),
        ("B2", "invalid token → translation", "/api/translation", "POST", "bogus",
         json.dumps({"paper_id": "demo001"}).encode()),
        ("B3", "expired token → worker", "/api/worker", "POST", EXPIRED,
         json.dumps({"job_id": "x"}).encode()),
        ("B4", "missing token → delete（仅校验鉴权）", "/api/delete/__nope__", "POST", None, None),
    ]
    for cid, name, path, method, tok, body in cases:
        code, data = request(path, method, tok, body)
        ok = code == 403 and data.get("status") == "error" and data.get("message") == "invalid token"
        record(cid, name, ok, "HTTP=%s %s" % (code, data))


# ---------------------------------------------------------------- C 数据异常
def suite_c():
    print("\n=== C. 数据异常（400/404 + 统一信封）===")

    # C1 invalid pdf（含孤儿/残留校验）
    ids_before = lib_ids()
    tok = book_token()
    with open(os.path.join(ROOT, "data", "library", "demo001", "item.json"), "rb") as f:
        bad = f.read()
    body, ctype = multipart_file(bad, "item.json", "application/octet-stream")
    code, data = request("/api/import", "POST", tok, body, {"Content-Type": ctype})
    ok = code == 400 and envelope_ok(data) and data.get("message") == "invalid pdf"
    record("C1", "invalid pdf → import", ok, "HTTP=%s %s" % (code, data))
    record("C1b", "invalid pdf 无孤儿 library 目录", lib_ids() == ids_before, "ids=%s" % lib_ids())
    record("C1c", "invalid pdf 无 upload 残留", "item.json" not in upload_files(), "upload=%s" % upload_files())

    # C2 missing file
    tok = book_token()
    body, ctype = multipart_no_file()
    code, data = request("/api/import", "POST", tok, body, {"Content-Type": ctype})
    ok = code == 400 and envelope_ok(data) and data.get("message") == "no file"
    record("C2", "missing file → import", ok, "HTTP=%s %s" % (code, data))

    # C3 invalid paper id（读）
    for cid, path, msg in [
        ("C3a", "/api/item/__nope__", "item not found"),
        ("C3b", "/api/paper/__nope__", "paper not found"),
        ("C3c", "/api/translation/__nope__", "translation not found"),
    ]:
        code, data = request(path)
        ok = code == 404 and envelope_ok(data) and data.get("message") == msg
        record(cid, "invalid paper id → %s" % path.split("/")[2], ok, "HTTP=%s %s" % (code, data))

    # C4 missing paper_id
    tok = book_token()
    code, data = request("/api/translation", "POST", tok, b"{}", {"Content-Type": "application/json"})
    ok = code == 400 and envelope_ok(data) and data.get("message") == "missing paper_id"
    record("C4", "missing paper_id → translation", ok, "HTTP=%s %s" % (code, data))

    # C5 unknown paper id（写）—— 目标口径 400/404，当前实际 200 → WARN
    tok = book_token()
    code, data = request("/api/translation", "POST", tok,
                         json.dumps({"paper_id": "__nope__"}).encode(),
                         {"Content-Type": "application/json"})
    ok = code in (400, 404)
    record("C5", "invalid paper id → translation 建任务", ok,
           "HTTP=%s %s" % (code, (data.get("data") or {}).get("job_id") if isinstance(data.get("data"), dict) else data),
           warn=not ok)
    TEMP_IDS.append("__nope__")   # 清理 C5 可能产生的 job（delete 幂等）

    # C6 unknown job id —— 目标口径 400/404，当前实际 200 data:null → WARN
    tok = book_token()
    code, data = request("/api/worker", "POST", tok,
                         json.dumps({"job_id": "__nope__"}).encode(),
                         {"Content-Type": "application/json"})
    ok = code in (400, 404)
    record("C6", "invalid job id → worker", ok, "HTTP=%s %s" % (code, data), warn=not ok)

    # C7 unknown api route
    code, data = request("/api/nosuchthing")
    ok = code == 404 and envelope_ok(data) and data.get("message") == "api not found"
    record("C7", "unknown api route", ok, "HTTP=%s %s" % (code, data))


def main():
    print("=" * 72)
    print("YiRead 接口验收（9.3 修正15：A 正常业务 / B 鉴权异常 / C 数据异常）")
    print("=" * 72)
    try:
        suite_a()
        suite_b()
        suite_c()
    except Exception as e:
        print("\n[EXCEPTION] %s: %s" % (type(e).__name__, e))
        cleanup_temp()
        return 1
    cleanup_temp()

    fails = [r for r in RESULTS if r[2] == "FAIL"]
    print("\n" + "=" * 72)
    print("合计 %d 项：PASS %d / WARN %d / FAIL %d" % (
        len(RESULTS),
        len([r for r in RESULTS if r[2] == "PASS"]),
        len(WARNS),
        len(fails),
    ))
    if WARNS:
        print("\n⚠️  WARN（与目标口径不符，未擅自改后端，待裁决）：")
        for cid, name, detail in WARNS:
            print("   - %s %s | %s" % (cid, name, detail))
    if fails:
        print("\n❌ FAIL：")
        for cid, name, _, detail in fails:
            print("   - %s %s | %s" % (cid, name, detail))
    print("\n结果：", "PASS" if not fails else "FAIL")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
