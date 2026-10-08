"""前端页面行为验收（9.3 修正15 口径统一）。

分类对照：
  [B 类·独立]  token 失效 —— stale token → 403 → 清 localStorage → 重新获取新 token。
               注意：**不与删除业务断言混合**（删除鉴权归 B 的接口层用例，见 check_acceptance.py）。
  [A 类]       delete 业务 —— 删除接口一律**自动获取 token**（走 auth.js 的 ensureToken），
               **不再断言「无 token 删除失败」**。破坏性用例必须用临时样本，禁止拿 demo001 当靶子。
"""
from playwright.sync_api import sync_playwright
import json
import urllib.request

BASE = "http://127.0.0.1:8765"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
TEMP_IDS = []      # 本轮自建的临时样本，收尾统一清理（幂等，缺 token 也不会留残留）


def api(path, method="GET", token=None, body=None, headers=None):
    req = urllib.request.Request(BASE + path, method=method)
    if token:
        req.add_header("X-Token", token)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    data = body
    return OPENER.open(req, data)


def get_token():
    with OPENER.open(BASE + "/api/token") as r:
        return json.loads(r.read().decode())["data"]["token"]


with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-proxy-server"])

    # ---- [B 类·独立] token 失效：stale → 403 → 清 localStorage → 重新获取（不与删除混合）----
    pg = b.new_page()
    errs = []
    dialogs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
    pg.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    pg.goto(BASE + "/", wait_until="networkidle")
    pg.wait_for_timeout(700)
    pg.evaluate("localStorage.setItem('token','stale-xxx')")
    pg.locator(".paper-item .translate-btn").first.click()
    pg.wait_for_timeout(1500)
    box = pg.locator("#error-box")
    print("[B token失效] error-box =", repr(box.inner_text()) if box.count() else None)
    print("[B token失效] token after =", repr(pg.evaluate("localStorage.getItem('token')")))
    pg.locator(".paper-item .translate-btn").first.click()
    pg.wait_for_timeout(1800)
    print("[B token失效] dialogs =", dialogs)
    t = pg.evaluate("localStorage.getItem('token')")
    print("[B token失效] token renewed =", (t[:12] + "...") if t else None)
    pg.close()

    # ---- 修正8：reader 渲染 ----
    pg = b.new_page()
    errs8 = []
    pg.on("pageerror", lambda e: errs8.append(str(e)))
    pg.goto(BASE + "/reader.html?id=demo001", wait_until="networkidle")
    pg.wait_for_timeout(900)
    print("[reader ok] title =", pg.locator("#title").inner_text())
    print("[reader ok] meta =", repr(pg.locator("#meta").inner_text()))
    print("[reader ok] trans-status =", pg.locator("#translation-status").inner_text())
    print("[reader ok] blocks =", pg.locator("#source .block").count(),
          "/", pg.locator("#translation .block").count())
    print("[reader ok] PAGEERRORS =", errs8)
    pg.close()

    # ---- [A 类] delete：本地**无** token → 自动获取 → 删除成功（临时样本）----
    tok_tmp = get_token()
    with open("data/library/20261004_b44d959c/source.pdf", "rb") as f:
        payload = f.read()
    boundary = "----wb"
    body = (
        ("--" + boundary + "\r\n"
         'Content-Disposition: form-data; name="file"; filename="tmp.pdf"\r\n'
         "Content-Type: application/pdf\r\n\r\n").encode() + payload
        + ("\r\n--" + boundary + "--\r\n").encode()
    )
    r = api("/api/import", "POST", tok_tmp, body,
            {"Content-Type": "multipart/form-data; boundary=" + boundary})
    tmp_id = json.loads(r.read().decode())["data"]["id"]
    TEMP_IDS.append(tmp_id)
    print("[A delete 自动token] tmp id =", tmp_id)

    pg = b.new_page()
    dialogs = []
    errs9a = []
    pg.on("pageerror", lambda e: errs9a.append(str(e)))
    pg.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    pg.goto(BASE + "/detail.html?id=" + tmp_id, wait_until="networkidle")
    pg.wait_for_timeout(600)
    pg.evaluate("localStorage.removeItem('token')")
    pg.click("#delete-btn")
    pg.wait_for_timeout(2000)
    print("[A delete 自动token] dialogs =", dialogs)
    print("[A delete 自动token] url =", pg.url)
    print("[A delete 自动token] PAGEERRORS =", errs9a)
    pg.close()

    # ---- [A 类] delete：本地**已有**有效 token → 直接删除成功（临时样本）----
    tok = get_token()
    with open("data/library/20261004_b44d959c/source.pdf", "rb") as f:
        payload = f.read()
    boundary = "----wb"
    body = (
        ("--" + boundary + "\r\n"
         'Content-Disposition: form-data; name="file"; filename="tmp.pdf"\r\n'
         "Content-Type: application/pdf\r\n\r\n").encode() + payload
        + ("\r\n--" + boundary + "--\r\n").encode()
    )
    r = api("/api/import", "POST", tok, body,
            {"Content-Type": "multipart/form-data; boundary=" + boundary})
    new_id = json.loads(r.read().decode())["data"]["id"]
    TEMP_IDS.append(new_id)
    print("[A delete 已有token] new id =", new_id)

    pg = b.new_page()
    dialogs = []
    errs9 = []
    pg.on("pageerror", lambda e: errs9.append(str(e)))
    pg.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    pg.goto(BASE + "/detail.html?id=" + new_id, wait_until="networkidle")
    pg.wait_for_timeout(600)
    pg.evaluate("(t) => localStorage.setItem('token', t)", tok)
    pg.click("#delete-btn")
    pg.wait_for_timeout(1800)
    print("[A delete 已有token] dialogs =", dialogs)
    print("[A delete 已有token] url =", pg.url)
    print("[A delete 已有token] cards =", pg.locator(".paper-item").count())
    print("[A delete 已有token] PAGEERRORS =", errs9)
    pg.close()

    b.close()

# 兜底清理：前端删除若未生效（如中断），这里用接口幂等回收，避免留下临时样本
_tok = get_token()
for _pid in TEMP_IDS:
    api("/api/delete/" + _pid, "POST", _tok)
print("[清理] 已回收临时样本:", TEMP_IDS)

with OPENER.open(BASE + "/api/library") as r:
    print("[library count] =", json.loads(r.read().decode())["data"]["count"])
