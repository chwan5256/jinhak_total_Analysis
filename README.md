# 생활기록부 역량 흐름 분석기 (jinhak_total_analysis)

나이스 학교생활세부사항기록부를 **브라우저 안에서만** 분석하여, 학생부종합전형 평가요소(3역량 10항목)별 문장 분포와 전공 적합성을 진단하는 고3 담임 상담 도구입니다.

- 단일 HTML 파일 · 무빌드 · 서버 없음
- 업로드한 생기부는 외부로 전송되지 않으며, 새로고침하면 즉시 소멸합니다
- GitHub Pages로 배포되어 교실 PC·태블릿 어디서나 URL 하나로 열립니다

## 무엇을 하는가

| 단계 | 내용 |
|---|---|
| 입력 | 나이스 PDF 업로드 · 스캔본 브라우저 OCR · 텍스트 직접 붙여넣기 |
| 구조화 | 좌표 기반 줄 복원 → 학년·영역(세특/자율/동아리/진로/봉사/행특/독서)·교과 단위 분절 → 문장 분리 |
| 분류 | 가중 규칙 + 영역 사전확률로 3역량 10항목 자동 분류, 문장별 신뢰도 산출 |
| 교사 개입 | 드래그앤드롭 또는 키보드(1/2/3)로 재분류, Ctrl+Z 되돌리기, 교사수정 표시 |
| 산출 | 학년별 위계성 진단 · 전공 이수 점검표 · 예상 면접 질문 · CSV · 상담 요약 시트 · A4 인쇄 |

## 평가요소 체계

2022년 5개 대학 공동연구 기준 학생부종합전형 공통 평가요소를 그대로 따릅니다.

- **학업역량** — 학업성취도 / 학업태도(자기주도) / 탐구력
- **진로역량** — 전공 관련 교과 이수 노력 / 전공 관련 교과 성취도 / 진로 탐색 활동과 경험
- **공동체역량** — 협업과 소통능력 / 나눔과 배려 / 성실성과 규칙준수 / 리더십

## 신뢰도를 표시하는 이유

자동 분류는 보조 도구일 뿐이며, 학업역량과 진로역량의 경계에 놓인 문장(교과 개념을 전공 대상에 적용한 세특 등)은 원리적으로 한쪽으로 확정할 수 없습니다.
그래서 이 도구는 **판단을 숨기지 않고 신뢰도로 드러냅니다.** 신뢰도 60% 미만 문장은 노란 점선 테두리로 표시되며, 툴바의 "재검토 필요만 보기"로 모아 볼 수 있습니다. 최종 판단은 교사가 합니다.

## 개발

```bash
# 로컬에서 열기 (file:// 로 열어도 동작하지만, OCR·PDF 워커는 http 권장)
python3 -m http.server 8000
# http://localhost:8000
```

버전 올리고 배포까지 한 번에:

```powershell
# Windows (PowerShell)
.\scripts\release.ps1 "드래그 UX 개선"                # 패치 버전 +1
.\scripts\release.ps1 "분류 로직 전면 개편" -Minor      # 마이너 버전 +1
.\scripts\release.ps1 "오타 수정" -NoBump             # 버전 유지
```

```bash
# macOS / Linux / Git Bash
./scripts/release.sh "드래그 UX 개선"
./scripts/release.sh -m "분류 로직 전면 개편"
./scripts/release.sh -n "오타 수정"
```

`main`에 푸시되면 GitHub Actions가 인라인 스크립트 문법 검사 → 단일 파일 원칙 검사 → 버전 표기 일치 검사를 거쳐 Pages에 배포합니다.

## 코드 구조

단일 파일이지만 내부는 레이어로 나뉘어 있습니다. 기능을 추가할 때는 해당 레이어만 건드리면 됩니다.

```
CONST     TAXONOMY / RULES / SECTION_PRIOR / MAJORS
STATE     state 객체 하나로 단일화 (전역 변수 없음)
Parse     reflowTextContent · reflow · segment · splitSentences
Classify  run(text, section) → {cat, sub, conf}
Stats     compute() → byCat / bySub / byGrade / lowConf
Render    summary · gradeFlow · table · consulting · counselSheet · majorDiagnostic
Export    csv · sheetText · copySheet
UI        dialog · progress · handlePdf · runOcr · move/cycle/undo · init
```

전공을 추가하려면 `MAJORS`에 항목 하나를 넣으면 셀렉트 박스·점검표·면접 질문이 자동으로 따라옵니다.
분류 규칙을 조정하려면 `RULES`의 가중치(3.0 결정적 / 1.8 강함 / 1.0 보통)만 손보면 됩니다.

## 외부 의존성

CDN에서 스크립트로만 불러오며 번들링하지 않습니다. 학교망에서 CDN이 차단되어도 페이지 자체는 죽지 않도록 방어 코드가 들어 있습니다.

| 라이브러리 | 용도 |
|---|---|
| Tailwind CSS (play CDN) | 스타일 |
| pdf.js 3.11.174 | PDF 텍스트 레이어 추출, 한글 CMap |
| Tesseract.js 5 | 스캔본 OCR 폴백 |
| Font Awesome 6 | 아이콘 |

> pdf.js의 한글 CMap과 Tesseract의 언어 데이터는 런타임에 CDN에서 **fetch**로 받아옵니다. 스크립트 외 리소스 fetch를 막는 환경(예: 일부 샌드박스 호스팅)에서는 PDF 한글 추출과 OCR이 동작하지 않습니다. GitHub Pages에는 그런 제약이 없습니다.

## 라이선스

교육 목적 사용 자유. 학생 개인정보가 포함된 파일을 이 저장소에 커밋하지 마세요.
