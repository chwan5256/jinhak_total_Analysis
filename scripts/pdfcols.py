#!/usr/bin/env python3
"""
다단 레이아웃 PDF에서 열을 복원해 읽는 순서대로 텍스트를 뽑는다.

pdftotext -layout 은 3단 그리드를 줄 단위로 섞어버린다. 서로 다른 학과의
면접 문항이 한 줄에 붙어 나오면 문항을 분리할 수 없다.
그래서 단어 좌표(-bbox-layout)를 받아 x좌표로 열을 나눈 뒤 열 안에서 y순으로 읽는다.
"""
import re, subprocess, sys
from xml.etree import ElementTree as ET

NS = {"x": "http://www.w3.org/1999/xhtml"}


def words(pdf, first, last):
    """페이지별 단어 목록 [(page, xmin, ymin, xmax, ymax, text)]"""
    out = subprocess.run(
        ["pdftotext", "-bbox-layout", "-f", str(first), "-l", str(last), pdf, "-"],
        capture_output=True, text=True, timeout=180)
    if out.returncode != 0:
        raise RuntimeError(out.stderr[:300])
    # pdftotext 출력에 XML로 허용되지 않는 제어문자가 섞이는 PDF가 있다. 걸러낸다.
    xml = "".join(ch for ch in out.stdout
                  if ch in "\t\n\r" or 0x20 <= ord(ch) < 0xD800 or 0xE000 <= ord(ch) <= 0xFFFD)
    xml = xml.replace("&#0;", "").replace("\x00", "")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        # 앰퍼샌드 등 미이스케이프 문자 방어
        xml2 = re.sub(r"&(?!(amp|lt|gt|quot|apos|#\d+|#x[0-9A-Fa-f]+);)", "&amp;", xml)
        root = ET.fromstring(xml2)
    res = []
    for pi, page in enumerate(root.iter("{http://www.w3.org/1999/xhtml}page"), first):
        for w in page.iter("{http://www.w3.org/1999/xhtml}word"):
            t = (w.text or "").strip()
            if not t:
                continue
            res.append((pi, float(w.get("xMin")), float(w.get("yMin")),
                        float(w.get("xMax")), float(w.get("yMax")), t))
    return res


def columns(ws, page_w=None, gap=40.0):
    """
    한 페이지의 단어를 x좌표 기준으로 열로 나눈다.
    단어 x구간을 히스토그램으로 훑어 빈 골짜기(gap 이상)를 열 경계로 삼는다.
    """
    if not ws:
        return []
    xs = sorted((w[1], w[3]) for w in ws)
    merged = []
    for a, b in xs:
        if merged and a <= merged[-1][1] + gap:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged


def read_page(ws, gap=40.0, line_tol=4.0):
    """열 → 줄 순서로 텍스트를 조립한다."""
    cols = columns(ws, gap=gap)
    chunks = []
    for lo, hi in cols:
        sel = [w for w in ws if w[1] >= lo - 0.5 and w[3] <= hi + 0.5]
        if not sel:
            continue
        rows = {}
        for w in sel:
            key = round(w[2] / line_tol)
            rows.setdefault(key, []).append(w)
        lines = []
        for key in sorted(rows):
            line = " ".join(t for *_ , t in sorted(rows[key], key=lambda w: w[1]))
            line = re.sub(r"\s+", " ", line).strip()
            if line:
                lines.append(line)
        if lines:
            chunks.append("\n".join(lines))
    return chunks


def extract(pdf, first, last, gap=40.0):
    ws = words(pdf, first, last)
    pages = {}
    for w in ws:
        pages.setdefault(w[0], []).append(w)
    out = []
    for p in sorted(pages):
        for c in read_page(pages[p], gap=gap):
            out.append((p, c))
    return out


if __name__ == "__main__":
    pdf, f, l = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    gap = float(sys.argv[4]) if len(sys.argv) > 4 else 40.0
    for p, c in extract(pdf, f, l, gap):
        print(f"\n----- p{p} 열 -----")
        print(c)
