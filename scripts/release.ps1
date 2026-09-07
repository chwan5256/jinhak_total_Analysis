# ---------------------------------------------------------------------------
# 생활기록부 역량 흐름 분석기 — 버전 올리고 커밋·푸시까지 한 번에 (Windows PowerShell)
#
#   .\scripts\release.ps1 "드래그 UX 개선"              # 패치 (2026.4 -> 2026.5)
#   .\scripts\release.ps1 "분류 로직 전면 개편" -Minor   # 마이너 (2026.4 -> 2027.0)
#   .\scripts\release.ps1 "오타 수정" -NoBump           # 버전 유지, 커밋만
#
# 처음 한 번만: PowerShell에서 스크립트 실행이 막혀 있다면
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
# ---------------------------------------------------------------------------
param(
  [Parameter(Mandatory = $true, Position = 0)][string]$Message,
  [switch]$Minor,
  [switch]$NoBump
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$html = Get-Content index.html -Raw -Encoding UTF8
if ($html -notmatch 'const VERSION = "([0-9.]+)";') { throw "index.html에서 VERSION 상수를 찾지 못했습니다." }
$cur = $Matches[1]
$parts = $cur.Split(".")

if     ($NoBump) { $new = $cur }
elseif ($Minor)  { $new = "$([int]$parts[0] + 1).0" }
else             { $new = "$($parts[0]).$([int]$parts[1] + 1)" }

if ($new -ne $cur) {
  Write-Host "버전 $cur -> $new"
  $html = $html.Replace("const VERSION = `"$cur`";", "const VERSION = `"$new`";")
  $html = $html.Replace("ver.$cur", "ver.$new")
  [System.IO.File]::WriteAllText((Resolve-Path index.html), $html, (New-Object System.Text.UTF8Encoding $false))

  $today = Get-Date -Format "yyyy-MM-dd"
  $log = Get-Content CHANGELOG.md -Encoding UTF8
  $entry = @("", "## ver.$new — $today", "", "- $Message")
  $merged = $log[0..3] + $entry + $log[4..($log.Length - 1)]
  [System.IO.File]::WriteAllLines((Resolve-Path CHANGELOG.md), $merged, (New-Object System.Text.UTF8Encoding $false))
} else {
  Write-Host "버전 유지: $cur"
}

# 로컬 사전 검사 — GitHub Actions에서 도는 것과 같은 문법 검사
$check = @'
const fs = require('fs');
const html = fs.readFileSync('index.html', 'utf8');
const i = html.lastIndexOf('<script>\n"use strict";');
const j = html.lastIndexOf('</script>');
if (i < 0 || j < 0) { console.error('앱 스크립트 블록을 찾지 못했습니다.'); process.exit(1); }
fs.writeFileSync('.check.tmp.js', html.slice(i + 8, j));
'@
if (Get-Command node -ErrorAction SilentlyContinue) {
  $check | Out-File -Encoding UTF8 .extract.tmp.js
  node .extract.tmp.js
  node --check .check.tmp.js
  Remove-Item .extract.tmp.js, .check.tmp.js -ErrorAction SilentlyContinue
  Write-Host "문법 검사 통과"
} else {
  Write-Host "node가 없어 로컬 문법 검사를 건너뜁니다. GitHub Actions에서 검사됩니다." -ForegroundColor Yellow
}

git add -A
git commit -m "$Message`n`nver.$new"
git push origin main

$remote = (git remote get-url origin) -replace '^git@github\.com:', 'https://github.com/' -replace '\.git$', ''
Write-Host ""
Write-Host "푸시 완료. GitHub Actions가 Pages에 배포합니다."
Write-Host "  Actions: $remote/actions"
