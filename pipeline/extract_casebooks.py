# -*- coding: utf-8 -*-
"""기록형 해설서·기출문제집 PDF → 페이지별 txt.

다섯 권 모두 텍스트층이 살아 있어 OCR 없이 뽑힌다. 다만 권마다 편집이 달라
사례 구분 마커가 제각각이라, 여기서는 **페이지 단위 원문만** 만들고
블록 나누기는 다음 단계(split_casebook_record.py)에서 한다.

원본은 저작권 자료라 저장소에 넣지 않는다. 산출물도 `work/`에 두고 커밋하지
않는다 — 커밋하는 건 최종 매칭 결과뿐이다.

    set RECORD_PDF=C:\\...\\모의고사 기출문제, 모범답안
    python -X utf8 extract_casebooks.py
"""
import io
import json
import os
import re
import sys
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    sys.exit('pypdf가 필요하다:  pip install pypdf')

RAW = Path(os.environ.get(
    'RECORD_PDF',
    r'C:\Users\82109\Desktop\2026\변시대비 자료 및 pdf\모의고사 기출문제, 모범답안',
))
WORK = Path(__file__).resolve().parents[1] / 'work' / 'casebook'

# 권마다 어느 과목을 다루는지. 매칭 단계에서 후보를 좁히는 데 쓴다.
BOOKS = [
    {'file': '기록형/(2027)[김유향] 공기록 해설OCR.pdf',
     'key': 'kim_public', 'author': '김유향', 'subject': '공법',
     'title': '공기록 해설'},
    {'file': '기록형/(25.03)[노수환] 핵심형사기록 실전연습 및 모범답안.pdf',
     'key': 'noh_criminal', 'author': '노수환', 'subject': '형사법',
     'title': '핵심형사기록 실전연습 및 모범답안'},
    {'file': '기록형/(25.05)[김기용] COMPACT 형사기록.pdf',
     'key': 'kim_criminal', 'author': '김기용', 'subject': '형사법',
     'title': 'COMPACT 형사기록'},
    {'file': '기록형/(26.06)[정연석] 로스쿨 기록형 기출문제집.pdf',
     'key': 'jung_all', 'author': '정연석', 'subject': None,   # 3과목 합본으로 보임
     'title': '로스쿨 기록형 기출문제집'},
    {'file': '사례집/기록형/15변시_기록형_정연석해설.pdf',
     'key': 'jung_15', 'author': '정연석', 'subject': None,
     'title': '15변시 기록형 해설'},
]


def extract(book):
    src = RAW / book['file']
    if not src.exists():
        print(f"  건너뜀 (없음): {book['file']}")
        return None
    out = WORK / book['key']
    out.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(src))
    n = len(reader.pages)
    empty = 0
    for i in range(n):
        try:
            t = reader.pages[i].extract_text() or ''
        except Exception:
            t = ''
        if not t.strip():
            empty += 1
        io.open(out / f'p{i+1:04d}.txt', 'w', encoding='utf-8', newline='').write(t)
        if (i + 1) % 100 == 0:
            print(f"    {book['key']}: {i+1}/{n}쪽")
    meta = {**book, 'pages': n, 'emptyPages': empty}
    io.open(out / '_meta.json', 'w', encoding='utf-8', newline='').write(
        json.dumps(meta, ensure_ascii=False, indent=1))
    print(f"  {book['key']}: {n}쪽 (빈 쪽 {empty})")
    return meta


def main():
    if not RAW.exists():
        sys.exit(f'원본 폴더를 찾지 못했다: {RAW}')
    WORK.mkdir(parents=True, exist_ok=True)
    metas = []
    for b in BOOKS:
        m = extract(b)
        if m:
            metas.append(m)
    io.open(WORK / 'books.json', 'w', encoding='utf-8', newline='').write(
        json.dumps(metas, ensure_ascii=False, indent=1))
    print('완료 →', WORK)


if __name__ == '__main__':
    main()
