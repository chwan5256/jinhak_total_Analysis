#!/usr/bin/env python3
"""
선행학습 영향평가 보고서 → data/exams.json (학종 면접 기출 문항)

왜 이 자료인가
  선행학습 영향평가 보고서는 법정 공시 자료라 대학이 문항을 숨기지 않는다.
  가이드북이 학과당 한두 개를 예시로 보여주는 데 그치는 반면,
  이 보고서에는 실제 출제된 면접 문항 전문과 함께
    · 그 문항이 학생부의 어느 항목을 검증하는지 (<검증 : 학생부 …>)
    · 어떤 평가요소를 보는지 (전형취지적합성 / 전공적합성 / 발전가능성 / 인성)
  가 붙어 있다. 학생부의 어느 항목을 검증하는지가 명시되어 있으므로,
  생기부 분석 결과(세특·진로·동아리…)에서 곧바로 "이 학생에게 나올 수 있는
  문항"으로 넘어갈 수 있다. 문항을 생성하지 않으므로 LLM이 필요 없다.

  범위는 학생부종합전형으로 한정한다. 논술은 다루지 않는다.
"""
import json, os, re, sys, subprocess, glob

BASE = "/mnt/user-data/uploads/repos/context/jinhak_total_analysis/선행학습 영향평가 보고서"
OUT = "/home/claude/work/repo/data/exams.json"

# 대학군 — 상담에서 쓰는 실무 분류. 기출 표기는 "군 (대학)" 형태로 노출한다.
TIER = {}
for t, names in {
    1: ["연세대", "고려대", "서강대", "한양대", "성균관대", "중앙대", "경희대", "서울시립대", "건국대", "홍익대"],
    2: ["국민대", "서울과기대", "숭실대", "동국대", "세종대", "광운대", "한국항공대", "인하대", "아주대", "단국대", "인천대"],
    3: ["한성대", "삼육대", "서경대", "명지대", "상명대", "수원대", "가톨릭대", "경기대", "가천대", "한국공학대"],
}.items():
    for n in names:
        TIER[n] = t

# 학종은 서류100%와 서류+면접 두 갈래다. 면접 문항이 있으면 후자.
def track_type(track, has_q):
    if re.search(r"논술", track or ""):
        return None                      # 논술은 이 도구의 범위가 아니다
    return "서류+면접" if has_q else "서류100"

VERIFY = re.compile(r"<\s*검증\s*[:：]\s*([^>]+)>")
HEADHHINT = re.compile(r"<\s*(전형취지적합성|전공적합성|발전가능성|인성\s*및\s*사회성|인성)\s*>")
BRACKET = re.compile(r"^\[([^\]]{2,60})\]\s*(.+)$")
QEND = re.compile(r"(보세요|주세요|주십시오|말해\s*보|설명해|얘기해|소개해|알려주|"
                  r"무엇인가요|있나요|하였나요|했나요|인가요|나요|까요)\s*[.?]?\s*$")

# 학생부 항목 → 앱의 영역 코드
SECTION_MAP = [
    (r"세부능력|특기사항|교과학습발달", "세특"),
    (r"진로활동", "진로"),
    (r"동아리", "동아리"),
    (r"봉사", "봉사"),
    (r"자율|자치", "자율"),
    (r"행동특성|종합의견", "행특"),
    (r"독서", "독서"),
    (r"수상", "수상"),
]

# 평가요소 → 3역량 매핑 (대학 용어 ↔ 학종 공통 평가요소)
FOCUS_MAP = {
    "전공적합성": "ca", "발전가능성": "ac", "인성 및 사회성": "co",
    "인성": "co", "전형취지적합성": "",
}

KEYWORDS = re.compile(
    r"(회로|설계|반도체|알고리즘|프로그래밍|소프트웨어|데이터|인공지능|머신러닝|로봇|"
    r"산화|환원|촉매|반응|화학|분자|고분자|신소재|나노|배터리|이차전지|"
    r"역학|물리|전자기|파동|양자|에너지|열역학|유체|"
    r"세포|유전자|단백질|효소|미생물|생명|면역|약물|"
    r"기후|대기|해양|지질|천문|우주|위성|환경|탄소|"
    r"미적분|기하|벡터|확률|통계|함수|수열|극한|증명|모델링|시뮬레이션|"
    r"실험|탐구|가설|변인|오차|검증|관측|측정|분석|"
    r"경제|경영|마케팅|재무|무역|관세|ESG|금융|"
    r"교육|수업|학습|심리|사회|문화|미디어|여론|설문|"
    r"문학|언어|음운|방언|번역|역사|철학|윤리|불교)")


def clean(s):
    return re.sub(r"\s+", " ", s).strip()


def section_of(verify):
    hits = []
    for pat, code in SECTION_MAP:
        if re.search(pat, verify):
            hits.append(code)
    return hits


def parse(text, uni, src):
    """
    <검증 : …> 를 문항의 끝 마커로 삼는다.
    그 바로 앞에서 거꾸로 올라가며 '[전형 학과]'로 시작하는 줄까지 모으면 문항 전문이 된다.
    """
    lines = [clean(l) for l in text.split("\n")]
    rows, focus = [], ""

    for i, line in enumerate(lines):
        h = HEADHHINT.search(line)
        if h:
            focus = clean(h.group(1))

        m = VERIFY.search(line)
        if not m:
            continue
        verify = clean(m.group(1))

        # 위로 최대 12줄 거슬러 올라가 '[' 로 시작하는 문항 머리를 찾는다
        buf, head = [], None
        for j in range(i - 1, max(i - 13, -1), -1):
            cur = lines[j]
            if not cur or VERIFY.search(cur):
                break
            cur = re.sub(r"^(평가|위원|\d+)\s+", "", cur)
            cur = re.sub(r"^문항\s*\d+\s*", "", cur)
            cur = re.sub(r"\s*문항\s*\d+\s*$", "", cur)
            if not cur:
                continue
            buf.insert(0, cur)
            if cur.startswith("["):
                head = j
                break
        if head is None or not buf:
            continue

        whole = clean(" ".join(buf))
        bm = BRACKET.match(whole)
        if not bm:
            continue
        track_dept, q = clean(bm.group(1)), clean(bm.group(2))
        if len(q) < 20 or not QEND.search(q):
            continue

        # "Do Dream 화학과" → 전형 + 학과
        parts = track_dept.rsplit(" ", 1)
        track = parts[0] if len(parts) == 2 else ""
        dept = parts[-1]

        if re.search(r"논술", track + " " + dept):
            continue
        rows.append({
            "u": uni, "tier": TIER.get(uni, 0), "type": "서류+면접",
            "track": track, "dept": dept, "q": q,
            "verify": verify, "sections": section_of(verify),
            "focus": FOCUS_MAP.get(focus, ""), "focusRaw": focus,
            "tags": sorted(set(KEYWORDS.findall(q))),
            "src": src,
        })
    return rows


def uni_of(fname):
    m = re.search(r"([가-힣]+대학교)", fname)
    return m.group(1).replace("대학교", "대") if m else fname[:10]


def run(pdf):
    out = subprocess.run(["pdftotext", "-layout", pdf, "-"],
                         capture_output=True, text=True, timeout=300)
    if out.returncode != 0:
        return []
    src = os.path.basename(pdf)
    rows = parse(out.stdout, uni_of(src), src)
    seen, uniq = set(), []
    for r in rows:
        k = r["q"][:70]
        if k in seen:
            continue
        seen.add(k); uniq.append(r)
    return uniq


if __name__ == "__main__":
    allrows = []
    for pdf in sorted(glob.glob(os.path.join(BASE, "*.pdf"))):
        try:
            r = run(pdf)
        except Exception as e:
            print(f"  {uni_of(os.path.basename(pdf)):10s} 실패: {e}")
            continue
        if r:
            print(f"  {uni_of(os.path.basename(pdf)):10s} [{r[0]['tier'] or '기타'}군] → 문항 {len(r):3d}건")
        allrows.extend(r)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tiers = {}
    for r in allrows:
        tiers.setdefault(str(r["tier"]), set()).add(r["u"])
    doc = {"meta": {"schema": 2, "year": 2026, "count": len(allrows),
                    "scope": "학생부종합전형(서류+면접)만. 논술은 제외한다.",
                    "tiers": {k: sorted(v) for k, v in sorted(tiers.items())},
                    "tierNames": {"1": "1군", "2": "2군", "3": "3군", "0": "그 외"},
                    "universities": sorted({r["u"] for r in allrows}),
                    "note": "선행학습 영향평가 보고서(법정 공시)에 실린 실제 면접 기출 문항. 생성물이 아니다."},
           "rows": allrows}
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"\n총 {len(allrows)}건 → {OUT} ({os.path.getsize(OUT):,} bytes)")
