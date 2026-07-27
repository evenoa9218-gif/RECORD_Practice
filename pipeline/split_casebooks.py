# -*- coding: utf-8 -*-
"""추출한 해설서 페이지 → 회차별 블록으로 묶어 앱 데이터에 결합.

## 왜 목차가 아니라 머리글로 나누는가

사례형에서는 사례집 목차(편 > 사례)를 파싱해 매칭했다. 기록형 해설서는 그
방식이 통하지 않는다 — 다섯 권의 편집이 제각각이고, 김유향 책은 OCR본이라
목차 자체가 깨져 있다("재 2 편", "71 줄문제집").

대신 **페이지 머리글에 반복되는 회차 표기**를 쓴다. 어느 책이든 쪽마다
"2023년 제12회 변호사시험" 같은 머리글이 박혀 있고, OCR이 글자를 조금
흘려도 숫자와 '회/년/차'는 대체로 살아남는다. 머리글이 없는 쪽은 직전 회차를
물려받는다(장 안에서는 회차가 바뀌지 않는다).

공법 책으로 검증했을 때 364쪽 중 363쪽이 회차에 배정됐다.
"""
import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work' / 'casebook'
DATA = ROOT / 'data'

# OCR이라 글자 사이에 공백이 끼어든다 — 전부 유연하게 잡는다.
BAR = re.compile(r'제\s*(\d{1,2})\s*회\s*변호사\s*시험')
BAR2 = re.compile(r'(20\d{2})\s*년\s*제\s*(\d{1,2})\s*회')          # 연도 + 회차
MOCK = re.compile(r'(20\d{2})\s*년도?\s*제\s*(\d)\s*차')
SUBJ = re.compile(r'(공법|민사법|형사법)')

# 변시 회차 ↔ 연도. 1회=2012년. 연도만 있는 머리글을 회차로 되돌릴 때 쓴다.
YEAR_TO_BAR = {2011 + n: n for n in range(1, 16)}


def read_pages(book_dir):
    out = []
    for p in sorted(book_dir.glob('p*.txt')):
        out.append((p.name, io.open(p, encoding='utf-8').read()))
    return out


def detect_round(text):
    """이 쪽이 어느 회차인지. 못 찾으면 None."""
    head = text[:260]
    for blob in (head, text):
        m = BAR.search(blob)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 15:
                return ('변시', n, None)
        m = BAR2.search(blob)
        if m:
            n = int(m.group(2))
            if 1 <= n <= 15:
                return ('변시', n, None)
        m = MOCK.search(blob)
        if m:
            return ('모의', int(m.group(1)), int(m.group(2)))
    return None


def detect_subject(text):
    m = SUBJ.search(text[:400])
    return m.group(1) if m else None


def exam_id(subject, rnd):
    kind, a, b = rnd
    return f'{subject}_변시_{a}회_기록' if kind == '변시' else f'{subject}_모의_{a}_{b}차_기록'


# 회차 머리글이 이 비율 미만이면 회차 기반 매칭을 포기한다.
# 책마다 성격이 다르다 — 기출 해설서는 쪽마다 회차가 박혀 있지만(공법 43%),
# 실전연습서는 창작 기록 위주라 회차가 거의 없다(형사 6%). 후자에 상속 로직을
# 그대로 쓰면 어쩌다 한 번 나온 회차에 수백 쪽이 잘못 붙는다.
MIN_HEADER_RATIO = 0.20


def split_book(meta):
    d = WORK / meta['key']
    pages = read_pages(d)
    if not pages:
        return {}, {'key': meta['key'], 'skipped': 'no-pages'}

    # 1차: 머리글 밀도를 먼저 잰다.
    detected = [detect_round(t) for _, t in pages]
    ratio = sum(1 for r in detected if r) / len(pages)
    if ratio < MIN_HEADER_RATIO:
        print(f"  {meta['key']}: {len(pages)}쪽, 회차 머리글 {ratio:.0%} "
              f"→ 회차 매칭 안 함 (기출 회차별 책이 아님)")
        return {}, {'key': meta['key'], 'pages': len(pages),
                    'headerRatio': round(ratio, 3), 'skipped': 'low-header-ratio'}

    blocks = defaultdict(list)          # (subject, rnd) → [(page, text)]
    cur_rnd, cur_subj = None, meta.get('subject')
    unassigned = 0

    for (name, text), r in zip(pages, detected):
        if r:
            cur_rnd = r
        # 합본(과목이 정해지지 않은 책)은 쪽에서 과목을 읽는다.
        if meta.get('subject') is None:
            s = detect_subject(text)
            if s:
                cur_subj = s
        if cur_rnd and cur_subj:
            blocks[(cur_subj, cur_rnd)].append((name, text))
        else:
            unassigned += 1

    print(f"  {meta['key']}: {len(pages)}쪽, 머리글 {ratio:.0%} "
          f"→ {len(blocks)}개 회차블록 (미배정 {unassigned}쪽)")
    return blocks, {'key': meta['key'], 'pages': len(pages),
                    'headerRatio': round(ratio, 3), 'blocks': len(blocks)}


def main():
    books_file = WORK / 'books.json'
    if not books_file.exists():
        sys.exit(f'{books_file}가 없다. extract_casebooks.py를 먼저 돌릴 것.')
    metas = json.load(io.open(books_file, encoding='utf-8'))

    # (subject, examId) → [{author, title, pages, text}]
    merged = defaultdict(list)
    reports = []
    for meta in metas:
        blocks, rep = split_book(meta)
        reports.append(rep)
        for (subj, rnd), pages in blocks.items():
            eid = exam_id(subj, rnd)
            merged[(subj, eid)].append({
                'author': meta['author'],
                'title': meta['title'],
                'pageCount': len(pages),
                'firstPage': pages[0][0],
                'text': '\n'.join(t for _, t in pages).strip(),
            })

    # 실제 시험 데이터에 있는 회차에만 붙인다 — 없는 회차는 버린다.
    # 쪽수가 너무 적은 블록도 버린다. 회차 머리글만 스치고 지나간 목차·간지가
    # 한 회차로 잡힌 것이라, 해설 내용이 들어 있지 않다(교차검증에서 지문
    # 적중률 0~1/12로 걸린 것들이 전부 1~3쪽짜리였다).
    MIN_PAGES = 5
    out = defaultdict(dict)
    kept = dropped = thin = 0
    for (subj, eid), items in merged.items():
        if not (DATA / subj / 'exams' / f'{eid}.json').exists():
            dropped += 1
            continue
        solid = [it for it in items if it['pageCount'] >= MIN_PAGES]
        thin += len(items) - len(solid)
        if solid:
            out[subj][eid] = solid
            kept += 1

    (WORK).mkdir(parents=True, exist_ok=True)
    for subj, m in out.items():
        io.open(WORK / f'blocks_{subj}.json', 'w', encoding='utf-8', newline='').write(
            json.dumps(m, ensure_ascii=False, indent=1))
        chars = sum(len(x['text']) for v in m.values() for x in v)
        print(f'{subj}: {len(m)}개 시험에 해설 결합 ({chars//1000}천자)')
    io.open(WORK / 'split_report.json', 'w', encoding='utf-8', newline='').write(
        json.dumps(reports, ensure_ascii=False, indent=1))
    print(f'매칭 {kept}건, 앱에 없는 회차 {dropped}건, 쪽수 부족으로 버림 {thin}건')
    skipped = [r for r in reports if r.get('skipped')]
    if skipped:
        print('회차 매칭에서 제외된 책:',
              ', '.join(f"{r['key']}({r.get('headerRatio','?')})" for r in skipped))


if __name__ == '__main__':
    main()
