$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$pythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $pythonExe)) { throw '请先创建 .venv 并安装 requirements-build.txt。' }
& $pythonExe packaging\build_manual.py
if ($LASTEXITCODE -ne 0) { throw '生成使用说明书失败。' }
& $pythonExe -m PyInstaller --noconfirm packaging\YiRead.spec
if ($LASTEXITCODE -ne 0) { throw '打包失败。' }
Copy-Item -LiteralPath 'packaging\使用说明.txt' -Destination 'dist\YiRead\使用说明.txt'
$oldMarkdownManual = Join-Path $PSScriptRoot 'dist\YiRead\用户使用说明书.md'
if (Test-Path -LiteralPath $oldMarkdownManual) { Remove-Item -LiteralPath $oldMarkdownManual }
Copy-Item -LiteralPath 'docs\用户使用说明书.html' -Destination 'dist\YiRead\用户使用说明书.html'
$archive = Join-Path $PSScriptRoot 'dist\YiRead-Windows-x64.zip'
Compress-Archive -Path 'dist\YiRead' -DestinationPath $archive -Force
Get-FileHash -LiteralPath $archive -Algorithm SHA256 | Format-List
