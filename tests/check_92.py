"""首页验收（stage 9.2）：卡片/搜索/翻译按钮 + token 写入 localStorage。

口径（9.3 修正15）：本脚本只覆盖**前端渲染与正常业务**，不含删除鉴权断言。
"""
import json
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8765"
errors = []
dialogs = []

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-proxy-server"])
    page = browser.new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console:" + m.type + ":" + m.text) if m.type == "error" else None)
    page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))

    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_timeout(800)
    cards_all = page.locator(".paper-item").count()
    titles_all = page.locator(".paper-item h3").all_inner_texts()
    print("ALL cards =", cards_all, titles_all)

    # 搜索
    page.fill("#search-input", "Example")
    page.click("#search-btn")
    page.wait_for_timeout(700)
    print("SEARCH Example =", page.locator(".paper-item").count(),
          page.locator(".paper-item h3").all_inner_texts())

    page.fill("#search-input", "")
    page.click("#search-btn")
    page.wait_for_timeout(700)
    print("SEARCH empty =", page.locator(".paper-item").count())

    # token 是否成功拿到（localStorage）
    tok = page.evaluate("localStorage.getItem('token')")
    print("TOKEN =", (tok[:12] + "...") if tok else None)

    # 开始翻译按钮
    btn = page.locator(".paper-item .translate-btn").first
    if btn.count() > 0:
        btn.click()
        page.wait_for_timeout(1200)
    print("DIALOGS =", dialogs)
    page.wait_for_timeout(1500)
    tok2 = page.evaluate("localStorage.getItem('token')")
    print("TOKEN after translate =", (tok2[:12] + "...") if tok2 else None)
    print("AFTER translate cards =", page.locator(".paper-item").count())

    browser.close()

print("PAGEERRORS =", errors)
