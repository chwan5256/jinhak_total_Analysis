#!/usr/bin/env python3
"""
학종 가이드북 PDF → data/interviews.json (면접 기출 문항 은행)

왜 이렇게 하는가
  학생 맞춤 면접 질문을 "생성"하려면 LLM이 필요하고, 그러면 학생 생기부가
  외부 API로 나가야 한다. 이 프로젝트의 제1원칙이 무너진다.
  그래서 생성하지 않고, 대학이 실제로 공개한 기출 문항을 색인해 두고
  학생 생기부의 키워드와 매칭해 "골라 쓴다". API가 필요 없고,
  대학이 낸 실제 문항이라 신뢰도도 더 높다.

레이아웃
  가이드북은 2~3단 그리드다. pdftotext -layout 은 열을 줄 단위로 섞어
  서로 다른 학과의 문항을 한 줄에 붙여버린다. 그래서 단어 좌표로 열을
  복원한 뒤(pdfcols) 열 안에서 읽는다.
"""
import json, os, re, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdfcols import extract, words

BASE = r"C:\repos\context\jinhak_total_analysis\학생부종합전형 가이드북"
OUT = "data/interviews.json"

# 면접 문항의 종결형. 이걸로 문항의 끝을 판정한다.
END = re.compile(r"(보세요|주세요|주십시오|말해\s*보십시오|설명하세요|해\s*보시오|"
                 r"이야기해\s*보세요|말씀해\s*주세요|알려주세요|무엇인가요|어떤가요|"
                 r"있나요|하였나요|했나요|인가요|나요|까요)\s*[.?]?\s*$")
COLLEGE = re.compile(r"^[가-힣A-Za-z·\s]{2,18}(대학|대학원|학부대학)$")
DEPT = re.compile(r"^[가-힣A-Za-z·()\s]{2,26}(학과|학부|전공|계열|과)$")
NOISE = re.compile(r"^(\d+|.{0,3}대학교|20\d\d학년도.*|SOONGSIL.*|[A-Z:]{3,}.*|"
                   r"서류기반|면접|기출\s*질문|학생부종합전형.*|가이드북.*)$")

# 문항에서 뽑을 학문 키워드 — 학생 생기부 매칭용
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
    r"문학|언어|음운|방언|번역|역사|철학|윤리)")


def clean(s):
    return re.sub(r"\s+", " ", s).strip()


def parse_column(text, uni, src, page):
    """한 열의 텍스트에서 (단과대학, 학과, 문항) 묶음을 뽑는다."""
    rows, col, dept, buf = [], "", "", []

    def flush():
        nonlocal buf
        q = clean(" ".join(buf))
        # 진짜 기출 문항만 남긴다. 가이드북에는 합격자 인터뷰 답변과
        # 면접 준비 안내문이 같은 종결형으로 섞여 있어 그대로 두면 오염된다.
        ok = (
            len(q) >= 18 and len(q) <= 200          # 문항 길이대
            and END.search(q)
            and bool(dept)                           # 학과가 붙은 것만 (기출 문항의 형식)
            and not q.startswith(("·", "•", "○", "-", "저는", "제가", "체크포인트"))
            and not re.search(r"(저는|제가|했습니다|싶습니다|입니다\.|합니다\.)", q)
        )
        if ok:
            rows.append({"u": uni, "col": col, "dept": dept, "q": q,
                         "tags": sorted(set(KEYWORDS.findall(q))),
                         "src": src, "page": page})
        buf = []

    for raw in text.split("\n"):
        line = clean(raw)
        if not line or NOISE.match(line):
            continue
        if COLLEGE.match(line) and len(line) <= 12:
            flush(); col = line; dept = ""; continue
        if DEPT.match(line) and len(line) <= 20 and not END.search(line):
            flush(); dept = line; continue
        buf.append(line)
        if END.search(line):
            flush()
    flush()
    return rows


def find_pages(pdf, max_pages=200):
    """면접 문항이 몰려 있는 페이지를 종결형 밀도로 찾는다."""
    import subprocess
    out = subprocess.run(["pdftotext", "-layout", pdf, "-"],
                         capture_output=True, text=True, timeout=240)
    pages = out.stdout.split("\f")
    hits = []
    for i, p in enumerate(pages, 1):
        n = len(re.findall(r"(보세요|주세요|말씀해|알려주세요)", p))
        if n >= 3:
            hits.append((i, n))
    return hits


def run(pdf, uni):
    src = os.path.basename(pdf)
    hits = find_pages(pdf)
    if not hits:
        return []
    rows = []
    for page, _ in hits:
        try:
            for _, chunk in extract(pdf, page, page, gap=12.0):
                rows.extend(parse_column(chunk, uni, src, page))
        except Exception as e:
            print(f"    p{page} 실패: {e}")
    # 중복 제거
    seen, uniq = set(), []
    for r in rows:
        k = r["q"][:60]
        if k in seen:
            continue
        seen.add(k); uniq.append(r)
    return uniq


UNIS = {
    "숭실대": "2027 숭실대 학종가이드북.pdf",
    "경희대": "2027 경희대 학생부종합 가이드북.pdf",
    "서울시립대": "2027 서울시립대 학생부종합전형 가이드북.pdf",
    "연세대": "2027 연세대 학생부종합전형 안내서.pdf",
}

if __name__ == "__main__":
    allrows = []
    for uni, fname in UNIS.items():
        path = os.path.join(BASE, fname)
        if not os.path.exists(path):
            print(f"  건너뜀: {fname}")
            continue
        r = run(path, uni)
        print(f"  {uni:10s} → 문항 {len(r):3d}건")
        allrows.extend(r)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    doc = {"meta": {"schema": 1, "count": len(allrows),
                    "universities": sorted({r["u"] for r in allrows}),
                    "note": "대학이 공개한 학생부 기반 면접 기출 문항. 생성물이 아니다."},
           "rows": allrows}
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"\n총 {len(allrows)}건 → {OUT} ({os.path.getsize(OUT):,} bytes)")
