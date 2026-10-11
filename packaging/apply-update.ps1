param([Parameter(Mandatory=$true)][string]$Manifest)
$ErrorActionPreference = 'Stop'
$info = Get-Content -LiteralPath $Manifest -Raw -Encoding UTF8 | ConvertFrom-Json
$target = [IO.Path]::GetFullPath($info.target)
$source = [IO.Path]::GetFullPath($info.source)
$stage = Split-Path -Parent $Manifest
$backup = Join-Path $stage 'backup'
$names = @('YiRead.exe', '_internal', '使用说明.txt', '用户使用说明书.html')
$moved = @()
$installed = @()
try {
    $oldProcess = Get-Process -Id $info.pid -ErrorAction SilentlyContinue
    if ($oldProcess -and !$oldProcess.WaitForExit(60000)) { throw '旧程序未退出，请关闭 YiRead 后重试。' }
    if (!(Test-Path -LiteralPath (Join-Path $target 'YiRead.exe'))) { throw '目标程序不存在。' }
    New-Item -ItemType Directory -Path $backup | Out-Null
    foreach ($name in $names) {
        $destination = [IO.Path]::GetFullPath((Join-Path $target $name))
        if ((Split-Path -Parent $destination) -ne $target) { throw '目标路径不合法。' }
        if (Test-Path -LiteralPath $destination) {
            Move-Item -LiteralPath $destination -Destination (Join-Path $backup $name)
            $moved += $name
        }
        $incoming = Join-Path $source $name
        if (Test-Path -LiteralPath $incoming) {
            $installed += $name
            Copy-Item -LiteralPath $incoming -Destination $destination -Recurse
        }
    }
    Start-Process -FilePath (Join-Path $target 'YiRead.exe') -WorkingDirectory $target -WindowStyle Hidden
    '更新成功。旧程序备份：' + $backup | Set-Content -LiteralPath (Join-Path $target 'update-result.txt') -Encoding UTF8
} catch {
    $failure = $_.Exception.Message
    foreach ($name in $installed) {
        $destination = [IO.Path]::GetFullPath((Join-Path $target $name))
        if ((Split-Path -Parent $destination) -eq $target -and (Test-Path -LiteralPath $destination)) {
            Remove-Item -LiteralPath $destination -Recurse -Force
        }
    }
    foreach ($name in $moved) {
        Move-Item -LiteralPath (Join-Path $backup $name) -Destination (Join-Path $target $name)
    }
    ('更新失败，已恢复旧程序：' + $failure) | Set-Content -LiteralPath (Join-Path $target 'update-result.txt') -Encoding UTF8
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show('更新失败，已恢复旧程序。' + $failure, 'YiRead') | Out-Null
}
