"""前端行为验收（stage 9.3 修正1~6）。

口径（9.3 修正15）：
  - 本脚本**不含删除业务断言**（删除走自动 token，见 check_93c.py / check_acceptance.py）。
  - 第 4) 段为 [B 类·独立] token 失效用例：stale token → 403 → 清 localStorage，
    **不与删除功能混合**。
"""
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8765"


def newpage(p):
    b = p.chromium.launch(args=["--no-proxy-server"])
    pg = b.new_page()
    errs = []
    dialogs = []
    pg.on("pageerror", lambda e: errs.append("pageerror:" + str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
    pg.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    return b, pg, errs, dialogs


with sync_playwright() as p:
    # ---- 1) 首页：空列表提示 + 搜索 + 翻译 ----
    b, pg, errs, dialogs = newpage(p)
    pg.goto(BASE + "/", wait_until="networkidle")
    pg.wait_for_timeout(700)
    print("[index] cards =", pg.locator(".paper-item").count())
    pg.fill("#search-input", "zzz_no_match")
    pg.click("#search-btn")
    pg.wait_for_timeout(700)
    print("[index] search zzz -> library text =", repr(pg.locator("#library").inner_text()),
          "| cards =", pg.locator(".paper-item").count())
    pg.fill("#search-input", "")
    pg.click("#search-btn")
    pg.wait_for_timeout(700)
    print("[index] search empty cards =", pg.locator(".paper-item").count())
    pg.locator(".paper-item .translate-btn").first.click()
    pg.wait_for_timeout(1200)
    print("[index] dialog =", dialogs)
    print("[index] error-box count =", pg.locator("#error-box").count())
    b.close()
    print("[index] ERRORS =", errs)
    print()

    # ---- 2) 详情页 ok / 404 ----
    b, pg, errs, dialogs = newpage(p)
    pg.goto(BASE + "/detail.html?id=demo001", wait_until="networkidle")
    pg.wait_for_timeout(700)
    print("[detail ok] title =", pg.locator("#title").inner_text())
    print("[detail ok] info =", repr(pg.locator("#info").inner_text()))
    b.close()
    print("[detail ok] ERRORS =", errs)
    print()

    b, pg, errs, dialogs = newpage(p)
    pg.goto(BASE + "/detail.html?id=notexist", wait_until="networkidle")
    pg.wait_for_timeout(700)
    print("[detail 404] info =", repr(pg.locator("#info").inner_text()))
    box = pg.locator("#error-box")
    print("[detail 404] error-box =", repr(box.inner_text()) if box.count() else None)
    b.close()
    print("[detail 404] ERRORS =", errs)
    print()

    # ---- 3) 阅读页 ok / 404 ----
    b, pg, errs, dialogs = newpage(p)
    pg.goto(BASE + "/reader.html?id=demo001", wait_until="networkidle")
    pg.wait_for_timeout(900)
    print("[reader ok] title =", pg.locator("#title").inner_text())
    print("[reader ok] trans-status =", pg.locator("#translation-status").inner_text())
    print("[reader ok] source/trans blocks =", pg.locator("#source .block").count(),
          "/", pg.locator("#translation .block").count())
    b.close()
    print("[reader ok] ERRORS =", errs)
    print()

    b, pg, errs, dialogs = newpage(p)
    pg.goto(BASE + "/reader.html?id=notexist", wait_until="networkidle")
    pg.wait_for_timeout(900)
    print("[reader 404] status =", repr(pg.locator("#status").inner_text()))
    box = pg.locator("#error-box")
    print("[reader 404] error-box =", repr(box.inner_text()) if box.count() else None)
    b.close()
    print("[reader 404] ERRORS =", errs)
    print()

    # ---- 4) [B 类·独立] 失效 token：stale → 403 → 清 localStorage（不与删除混合）----
    b, pg, errs, dialogs = newpage(p)
    pg.goto(BASE + "/", wait_until="networkidle")
    pg.wait_for_timeout(700)
    pg.evaluate("localStorage.setItem('token','stale-token-xxx')")
    pg.locator(".paper-item .translate-btn").first.click()
    pg.wait_for_timeout(1500)
    box = pg.locator("#error-box")
    print("[stale token] error-box =", repr(box.inner_text()) if box.count() else None)
    print("[stale token] dialog =", dialogs)
    print("[stale token] localStorage.token after =", repr(pg.evaluate("localStorage.getItem('token')")))
    b.close()
    print("[stale token] ERRORS =", errs)
