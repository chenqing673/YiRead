# 部署与使用

## Windows 启动

免安装发行版：将 `YiRead-Windows-x64.zip` 完整解压，双击 `YiRead.exe`。无需安装 Python、Node.js 或 PDF 依赖。程序自动打开系统浏览器，关闭服务窗口即停止。请解压到可写目录，保留 `_internal` 文件夹。用户数据存放在可执行文件旁的 `data` 目录，备份及升级时先关闭程序再迁移该目录。

重新打包：在 Windows x64 构建环境安装 `requirements-build.txt`，运行 `powershell -ExecutionPolicy Bypass -File build-portable.ps1`。输出为 `dist/YiRead` 和 `dist/YiRead-Windows-x64.zip`，不打包开发目录中的文献和密钥。

已有 `.venv` 环境时双击项目根目录的 `start.cmd`。也可在项目目录运行：

```powershell
.venv\Scripts\python.exe backend/server.py
```

首次安装：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

支持 Python 3.11+，服务地址为 http://127.0.0.1:8765。仅供本机使用。端口被占用时请先关闭此前的 YiRead 服务。

## 译文排版模式

阅读页顶部可选择「连续阅读」或「原版排版」，浏览器会记住选择。连续阅读可用 A− / A＋调字号；原版排版保留页面、栏位和图形背景，使用「版式缩放」放大。未译内容、公式、复杂表格、旋转文字和无法可靠定位的旧记录保留原文，对应完整译文可在页面下方展开。溢出段落可滚动，或点击「查看完整译文」切回连续阅读。选择段落后仍可修订、记笔记和保存书签。

切换只复用本机已有译文，不调用模型，不修改源 PDF。首次显示需计算本地排版。当前「导出译文」仍导出文字，不提供译文 PDF 导出。

## 配置翻译

打开网页的「翻译设置」。填写服务商提供的基础地址、准确的模型 ID、API 密钥及目标语言。远程地址需使用 HTTPS，本地 `localhost` 或 `127.0.0.1` 可使用 HTTP。地址填到 `/v1` 或服务商指定的 API 前缀，程序再拼接 `/chat/completions`。

密钥字段留空会保留已有密钥，勾选「清除已保存密钥」后保存才会删除。测试连接会先保存配置，再发送测试文本。改变配置不会自动翻译文献，需自行点击翻译。

配置、文献、译文、任务保存在 `data/`。备份时停止服务并复制整个 `data` 目录；其中 `translator.json` 含明文密钥，请妥善保管。恢复备份时将该目录放回项目根目录。

## 常见问题

双语阅读时，右侧滚动或点击译文会带动左侧原始 PDF，并高亮对应原文。左侧「跟随译文」可关闭联动；缩放菜单只改变 PDF，字号按钮只改变译文。已有文献无需重新导入或翻译。文字无法可靠匹配时只跳转页面；扫描件需先 OCR。

- **无法连接服务**：检查 API 基础地址、网络和服务是否启动。
- **HTTP 401/403**：核对密钥及服务商权限。
- **HTTP 404**：核对是否误填了完整 `/chat/completions` 地址，或模型不存在。
- **HTTP 429**：检查服务商额度和限流，稍后重试。
- **没有可提取文字**：扫描版 PDF 需在导入前进行 OCR。原始 PDF 仍可打开。
- **服务重启后翻译失败**：点击重试继续已保存段落。
- **部分译文存在但任务失败**：属于可恢复状态，任务状态优先于文件是否存在。

## 验证

```powershell
.venv\Scripts\python.exe tests/test_workflow.py
.venv\Scripts\python.exe tests/test_pdf_follow.py
node tests/test_frontend.cjs
```

测试采用隔离临时存储，不读取服务密钥，不调用外部模型服务。
