#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 생활기록부 역량 흐름 분석기 — 버전 올리고 커밋·푸시까지 한 번에.
#
#   ./scripts/release.sh "드래그 UX 개선"          # 패치 (2026.4 -> 2026.5)
#   ./scripts/release.sh -m "분류 로직 전면 개편"   # 마이너 (2026.4 -> 2027.0)
#   ./scripts/release.sh -n "오타 수정"            # 버전 유지, 커밋만
#
# index.html 안의 VERSION 상수와 <title>, CHANGELOG.md를 함께 갱신한다.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."

BUMP="patch"
while getopts ":mnp" opt; do
  case $opt in
    m) BUMP="minor" ;;
    n) BUMP="none" ;;
    p) BUMP="patch" ;;
    *) echo "알 수 없는 옵션: -$OPTARG" >&2; exit 1 ;;
  esac
done
shift $((OPTIND - 1))

MSG="${1:-}"
if [ -z "$MSG" ]; then
  echo "커밋 메시지를 인자로 넘겨주세요.  예) ./scripts/release.sh \"분류 규칙 보강\"" >&2
  exit 1
fi

CUR=$(grep -oP 'const VERSION = "\K[0-9.]+' index.html | head -1)
MAJOR="${CUR%%.*}"
MINOR="${CUR##*.}"

case "$BUMP" in
  patch) NEW="${MAJOR}.$((MINOR + 1))" ;;
  minor) NEW="$((MAJOR + 1)).0" ;;
  none)  NEW="$CUR" ;;
esac

if [ "$NEW" != "$CUR" ]; then
  echo "버전 $CUR -> $NEW"
  sed -i "s/const VERSION = \"$CUR\";/const VERSION = \"$NEW\";/" index.html
  sed -i "s/ver\.$CUR/ver.$NEW/g" index.html

  TODAY=$(date +%Y-%m-%d)
  TMP=$(mktemp)
  {
    head -n 4 CHANGELOG.md
    printf '\n## ver.%s — %s\n\n- %s\n' "$NEW" "$TODAY" "$MSG"
    tail -n +5 CHANGELOG.md
  } > "$TMP"
  mv "$TMP" CHANGELOG.md
else
  echo "버전 유지: $CUR"
fi

# 로컬 사전 검사 — Actions에서 도는 것과 같은 문법 검사
node - <<'JS'
const fs = require('fs');
const html = fs.readFileSync('index.html', 'utf8');
const i = html.lastIndexOf('<script>\n"use strict";');
const j = html.lastIndexOf('</script>');
if (i < 0 || j < 0) { console.error('앱 스크립트 블록을 찾지 못했습니다.'); process.exit(1); }
fs.writeFileSync('/tmp/app.js', html.slice(i + 8, j));
JS
node --check /tmp/app.js
echo "문법 검사 통과"

git add -A
git commit -m "$(printf '%s\n\nver.%s' "$MSG" "$NEW")"
git push origin main

echo ""
echo "푸시 완료. GitHub Actions가 Pages에 배포합니다."
echo "  Actions: $(git remote get-url origin | sed 's#git@github.com:#https://github.com/#; s#\.git$##')/actions"
