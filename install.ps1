#Requires -Version 5.1
<#
.SYNOPSIS
    把 skills/ 下的科研技能安装到 DSH 技能目录，并做本机适配。

.DESCRIPTION
    只复制技能文件和做环境适配，不修改任何技能的检索逻辑。
    每一步都可重复执行；已存在且内容一致的文件会跳过。

.PARAMETER Destination
    技能目标目录，默认 %USERPROFILE%\.dsh\skills

.PARAMETER Skills
    要安装的技能名；省略则安装 skills/ 下全部

.PARAMETER SkipMCP
    不写入 MCP 配置

.PARAMETER SkipRequirements
    不安装 Python 依赖（只复制文件）

.EXAMPLE
    .\install.ps1
    .\install.ps1 -Skills design-study,search-lit -Verbose

.NOTES
    详见 RESEARCH-SKILLS-ENV.md。需要以普通用户权限运行，不需要管理员。
#>
[CmdletBinding()]
param(
    [string]$Destination = (Join-Path $env:USERPROFILE '.dsh\skills'),
    [string[]]$Skills,
    [switch]$SkipMCP,
    [switch]$SkipRequirements
)

$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'skills'

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn2($msg){ Write-Host "    $msg" -ForegroundColor Yellow }

if (-not (Test-Path $source)) { throw "找不到 skills 目录：$source（请在仓库根目录运行脚本）" }

$all = Get-ChildItem $source -Directory | Select-Object -ExpandProperty Name
# `powershell -File` 传参时 "a,b" 会作为一个字符串传进来，这里拆开；
# 同时也接受重复参数 -Skills a -Skills b 与空格分隔的写法。
$Skills = $Skills | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ }
$targets = if ($Skills) {
    $missing = $Skills | Where-Object { $_ -notin $all }
    if ($missing) { throw "仓库中没有这些技能：$($missing -join ', ')" }
    $Skills | Select-Object -Unique
} else { $all }

Write-Step "安装 $($targets.Count) 个技能到 $Destination"
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
foreach ($name in $targets) {
    $dst = Join-Path $Destination $name
    if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
    Copy-Item (Join-Path $source $name) $dst -Recurse -Force
    Write-Ok "$name"
}

# ---------------------------------------------------------------- python3 垫片
Write-Step '检查 python3'
$python3 = Get-Command python3 -ErrorAction SilentlyContinue
$probe = $null
if ($python3) { $probe = & python3 --version 2>&1 }
if ($LASTEXITCODE -ne 0 -or -not $python3) {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) {
        Write-Warn2 'python 和 python3 都不可用，请先安装 Python 3.9+'
    } else {
        $pyDir = Split-Path $py.Source -Parent
        $shim = Join-Path $pyDir 'python3.exe'
        if (-not (Test-Path $shim)) {
            Copy-Item (Join-Path $pyDir 'python.exe') $shim
            Write-Ok "已创建 $shim"
        } else { Write-Ok "已存在 $shim" }
    }
} else { Write-Ok "python3 可用：$probe" }

# ---------------------------------------------------------------- Python 依赖
if (-not $SkipRequirements) {
    Write-Step '安装 Python 依赖（mcp<2、pybliometrics 等）'
    Write-Warn2 '本机 pip 可能因网络受限而挂起；见 RESEARCH-SKILLS-ENV.md 第四节'
    $needMCP = $targets -contains 'nature-academic-search'
    if ($needMCP) {
        $pkgs = @('mcp<2', 'pybliometrics', 'lxml', 'requests', 'toml')
        Write-Host "    pip install $($pkgs -join ' ')"
        try {
            & python -m pip install --no-input --disable-pip-version-check --timeout 30 @pkgs
            Write-Ok '依赖安装完成'
        } catch { Write-Warn2 "pip 失败：$_" }
        $ok = & python -c "from mcp.server.fastmcp import FastMCP; print('ok')" 2>&1
        if ($ok -match 'ok') { Write-Ok 'FastMCP 可导入' }
        else { Write-Warn2 'FastMCP 仍不可导入，检查是否误装了 mcp 2.x（必须 mcp<2）' }
    }
}

# ---------------------------------------------------------------- MCP 配置
if (-not $SkipMCP -and ($targets -contains 'nature-academic-search')) {
    Write-Step '写入 academic-search MCP 配置'
    $profileDir = Join-Path $env:USERPROFILE '.dsh\profiles\desktop'
    $patch = Join-Path $profileDir 'cordis.patch.yml'
    if (-not (Test-Path $patch)) {
        Write-Warn2 "未找到 $patch，跳过（请按 RESEARCH-SKILLS-ENV.md 手动添加）"
    } else {
        $text = Get-Content $patch -Raw -Encoding UTF8
        if ($text -match 'mcp-academic-search') {
            Write-Ok '配置已存在，跳过'
        } else {
            Copy-Item $patch "$patch.bak-before-mcp" -Force
            $serverPy = Join-Path $Destination 'nature-academic-search\mcp-server\academic_search_server.py'
            $pythonExe = (Get-Command python).Source
            $block = @"

- id: mcp-academic-search
  name: "@deepseek-ai/dsh-mcp-client"
  config:
    serverName: academic-search
    transport: stdio
    command: $pythonExe
    args:
      - $serverPy
    cwd: $(Split-Path $serverPy -Parent)
    env:
      PYTHONIOENCODING: utf-8
    toolCallTimeoutMs: 120000
"@
            Add-Content -Path $patch -Value $block -Encoding UTF8
            Write-Ok "已追加到 $patch"
            Write-Warn2 '备份：cordis.patch.yml.bak-before-mcp'
            Write-Warn2 '需要重启 DSH 才会加载 MCP 工具'
        }
    }
}

# ---------------------------------------------------------------- 验证
Write-Step '验证'
$checks = @(
    @{ Name = 'python3'; Cmd = 'python3 --version' },
    @{ Name = 'pandoc（可选，用于 docx/html 导出）'; Cmd = 'pandoc --version' }
)
foreach ($c in $checks) {
    try {
        $out = Invoke-Expression $c.Cmd 2>&1 | Select-Object -First 1
        Write-Ok "$($c.Name): $out"
    } catch { Write-Warn2 "$($c.Name): 不可用" }
}

$pf = Join-Path $Destination 'pubmed-paper-finder\scripts\pubmed_paper_finder.py'
if (Test-Path $pf) {
    Write-Host '    抽查 PubMed 检索...'
    Push-Location $env:TEMP
    try {
        $r = & python $pf 'Mendelian randomization lipid' --max-per-query 2 --show 1 2>&1 | Select-Object -Last 1
        Write-Ok $r
    } catch { Write-Warn2 "检索失败：$_" }
    finally { Pop-Location }
}

Write-Host ''
Write-Host '完成。' -ForegroundColor Cyan
Write-Host '  - 新装/更新的技能会在下次会话生效'
Write-Host '  - 若写了 MCP 配置，请重启 DSH'
Write-Host '  - 详细排查见 RESEARCH-SKILLS-ENV.md'
