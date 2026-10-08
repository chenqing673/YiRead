"""三页渲染验收（stage 9.3.1~9.3.7）：index / detail / reader 正常页与 404 页。

口径（9.3 修正15）：本脚本只覆盖**前端渲染**，不含删除与鉴权断言。
"""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8765"
results = []


def run(label, url, fn):
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-proxy-server"])
        page = browser.new_page()
        errs = []
        dialogs = []
        page.on("pageerror", lambda e: errs.append("pageerror:" + str(e)))
        page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(900)
        info = fn(page, dialogs)
        browser.close()
        print("[" + label + "]")
        for k, v in info.items():
            print("   ", k, "=", v)
        print("    ERRORS =", errs)
        results.append((label, errs))


def f_index(page, dialogs):
    out = {"cards": page.locator(".paper-item").count()}
    page.fill("#search-input", "Example")
    page.click("#search-btn")
    page.wait_for_timeout(600)
    out["search Example"] = page.locator(".paper-item").count()
    page.fill("#search-input", "")
    page.click("#search-btn")
    page.wait_for_timeout(600)
    out["search empty"] = page.locator(".paper-item").count()
    btn = page.locator(".paper-item .translate-btn").first
    if btn.count():
        btn.click()
        page.wait_for_timeout(1200)
    out["dialog"] = dialogs
    box = page.locator("#error-box")
    out["error-box count"] = box.count()
    if box.count():
        out["error-box display"] = box.evaluate("e => getComputedStyle(e).display")
    return out


def f_detail_ok(page, dialogs):
    return {
        "title": page.locator("#title").inner_text(),
        "info": page.locator("#info").inner_text().replace("\n", " | "),
        "has reader-btn": page.locator("#reader-btn").count(),
        "error-box count": page.locator("#error-box").count(),
    }


def f_detail_404(page, dialogs):
    page.wait_for_timeout(300)
    box = page.locator("#error-box")
    return {
        "error-box count": box.count(),
        "error-box text": box.inner_text() if box.count() else None,
        "error-box display": box.evaluate("e => getComputedStyle(e).display") if box.count() else None,
        "info": page.locator("#info").inner_text(),
    }


def f_reader(page, dialogs):
    return {
        "title": page.locator("#title").inner_text(),
        "trans-status": page.locator("#translation-status").inner_text(),
        "status": page.locator("#status").inner_text(),
        "source blocks": page.locator("#source .block").count(),
        "trans blocks": page.locator("#translation .block").count(),
        "error-box count": page.locator("#error-box").count(),
    }


def f_reader_404(page, dialogs):
    page.wait_for_timeout(300)
    box = page.locator("#error-box")
    return {
        "error-box text": box.inner_text() if box.count() else None,
        "status": page.locator("#status").inner_text(),
    }


run("index", BASE + "/", f_index)
run("detail ok", BASE + "/detail.html?id=demo001", f_detail_ok)
run("detail 404", BASE + "/detail.html?id=notexist", f_detail_404)
run("reader ok", BASE + "/reader.html?id=demo001", f_reader)
run("reader 404", BASE + "/reader.html?id=notexist", f_reader_404)

bad = [r for r in results if r[1]]
print()
print("TOTAL with errors:", len(bad))
