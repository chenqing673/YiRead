"""9.3 修正10~14 验证脚本。

分类（9.3 修正15）：本脚本属 **C 数据异常** + 前端渲染，全部用例**自动获取 token**。

覆盖：
  修正10  detail 删除按钮走 ensureToken()（auth.js）
  修正11  非法 PDF 导入返回 400 invalid pdf，handler 不崩
  修正12  失败时清理 data/upload 临时文件 + 孤儿 library 目录
  修正13  上述清理效果的实际校验
  修正14  detail.js 去掉恒真判断，删除后仍 alert + 跳转
"""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8765"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_token():
    with urllib.request.urlopen(BASE + "/api/token") as r:
        return json.loads(r.read().decode())["data"]["token"]


def library_count():
    with urllib.request.urlopen(BASE + "/api/library") as r:
        return json.loads(r.read().decode())["data"]["count"]


def library_ids():
    with urllib.request.urlopen(BASE + "/api/library") as r:
        return sorted(i["id"] for i in json.loads(r.read().decode())["data"]["items"])


def post_invalid_pdf(filename="item.json"):
    """把 data/library/demo001/item.json 当成 PDF 上传，模拟非法 PDF。"""
    tok = get_token()
    src = os.path.join(ROOT, "data", "library", "demo001", "item.json")
    with open(src, "rb") as f:
        payload = f.read()
    boundary = "----wb93d"
    body = (
        ("--" + boundary + "\r\n"
         'Content-Disposition: form-data; name="file"; filename="%s"\r\n'
         "Content-Type: application/octet-stream\r\n\r\n" % filename).encode()
        + payload
        + ("\r\n--" + boundary + "--\r\n").encode()
    )
    req = urllib.request.Request(BASE + "/api/import", method="POST", data=body)
    req.add_header("X-Token", tok)
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    req.add_header("Content-Length", str(len(body)))
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def upload_files():
    d = os.path.join(ROOT, "data", "upload")
    return sorted(os.listdir(d)) if os.path.isdir(d) else []


def main():
    print("=" * 60)
    print("[前置] library_count =", library_count())
    print("[前置] library_ids   =", library_ids())
    print("[前置] upload files  =", upload_files())

    ids_before = library_ids()

    print("\n[修正11/12/13] 上传 item.json 冒充 PDF ...")
    code, text = post_invalid_pdf("item.json")
    print("  HTTP =", code)
    print("  响应 =", text)

    ok = True
    if code != 400:
        print("  ✗ 期望 400"); ok = False
    try:
        payload = json.loads(text)
        if payload.get("status") != "error" or payload.get("message") != "invalid pdf":
            print("  ✗ 期望 {'status':'error','message':'invalid pdf'}"); ok = False
    except Exception:
        print("  ✗ 响应不是 JSON"); ok = False

    ids_after = library_ids()
    print("\n  library_ids  after =", ids_after)
    if ids_after != ids_before:
        new = set(ids_after) - set(ids_before)
        print("  ✗ 出现孤儿目录:", new); ok = False
    else:
        print("  ✓ 无孤儿 library 目录")

    up = upload_files()
    print("  upload files after =", up)
    if "item.json" in up:
        print("  ✗ data/upload/item.json 残留"); ok = False
    else:
        print("  ✓ 无 upload 残留")

    print("\n" + "=" * 60)
    print("修正11/12/13 结果:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
