# -*- coding: utf-8 -*-
"""검증된 해설 블록을 앱 데이터(`../data/`)에 결합.

`split_casebooks.py` → `verify_match.py`를 먼저 돌린 뒤 실행한다.
**교차검증을 통과한 것만** 붙인다 — 지문 적중률이 낮은 블록은 다른 회차가
잘못 붙었을 가능성이 있어 넣지 않는다.

해설 원문은 저작권 자료다. 앱에는 **AI 채점의 근거로 쓸 만큼만** 담고
(회차당 최대 MAX_CHARS), 출처를 함께 적는다.
"""
import io
import json
import re
from collections import Counter
from pathlib import Path

# ── OCR 노이즈 제거 ────────────────────────────────────
# 스캔본(김유향 공기록 해설)은 표 괘선·로고·워터마크가 글자로 잘못 읽혀
# "‘> • ·,-.:-』;.: .. ·;,.-. -,·~.~'" 같은 줄이 섞인다. 사람이 읽을 수 없고
# AI 채점에 넣으면 근거를 흐린다.
HANGUL = re.compile(r'[가-힣]')
MEANINGFUL = re.compile(r'[가-힣A-Za-z0-9]')
# 쪽마다 반복되는 머리글(“2026년 제15회 변호사시험”)도 본문에서는 군더더기다.
PAGE_HEAD = re.compile(
    r'^[l|]?\s*\d{0,4}\s*년?\s*제\s*\d{1,2}\s*[회호]\s*\d?\s*변호사\s*시험.*$', re.M)


def denoise(text):
    """OCR 쓰레기 줄을 걷어낸다. 애매하면 남긴다 — 원문을 깎는 쪽이 더 나쁘다."""
    out = []
    for line in text.split('\n'):
        s = line.strip()
        if not s:
            out.append('')
            continue
        if PAGE_HEAD.match(s):
            continue
        # 의미 있는 글자가 너무 적은 줄은 괘선·장식이 잘못 읽힌 것이다.
        ratio = len(MEANINGFUL.findall(s)) / len(s)
        if len(s) >= 12 and ratio < 0.45:
            continue
        # 한글이 하나도 없고 특수문자만 늘어선 짧은 줄도 같은 부류.
        if len(s) >= 6 and not HANGUL.search(s) and ratio < 0.5:
            continue
        out.append(line.rstrip())
    # 빈 줄 3연속 이상은 둘로 줄인다.
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(out)).strip()

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work' / 'casebook'
DATA = ROOT / 'data'

# 지문 적중률이 이 미만이면 붙이지 않는다.
#
# 처음엔 0.25로 뒀다가 0.5로 올렸다. 정확히 0.25로 통과한 한 건
# (공법 2016-2차, 김유향 11쪽)을 열어 보니, 문제는 건축·용도변경허가 사건인데
# 붙은 해설은 재외동포법·환경영향평가법이었고 "[16 변호사 기록]" 같은 다른
# 회차 표기가 섞여 있었다 — 회차별 해설이 아니라 **유형별 청구취지 예시를
# 모아 둔 정리 페이지**가 회차 하나로 잡힌 것이다. 쪽수(11쪽)만으로는
# 걸러지지 않아 적중률 기준을 ok 판정과 같은 선으로 맞췄다.
MIN_RATIO = 0.5
# 회차당 해설 분량 상한. 형사 기록 해설은 문제·기록이 두 번 다시 실려 한 회차가 7만 자를
# 넘기도 한다(변시 10·11회). 예전 상한 6만 자로는 정작 뒤에 오는 모범답안이 잘려 나갔다.
# 채점에 쓰는 구간은 mark_answer_span.js 가 따로 표시하므로 여기서는 원문을 살려 둔다.
MAX_CHARS = 100000


def main():
    report = json.load(io.open(WORK / 'match_report.json', encoding='utf-8'))
    # (subject, examId, author) → verdict
    ok = {(r['subject'], r['examId'], r['author']): r
          for r in report if r['ratio'] >= MIN_RATIO}

    stat = Counter()
    for subj in ['공법', '민사법', '형사법']:
        bf = WORK / f'blocks_{subj}.json'
        if not bf.exists():
            continue
        blocks = json.load(io.open(bf, encoding='utf-8'))
        idx_file = DATA / subj / 'index.json'
        index = json.load(io.open(idx_file, encoding='utf-8'))
        by_id = {e['id']: e for e in index['exams']}

        for eid, items in blocks.items():
            keep = []
            for it in items:
                r = ok.get((subj, eid, it['author']))
                if not r:
                    stat['제외(검증미달)'] += 1
                    continue
                text = denoise(it['text'])
                truncated = len(text) > MAX_CHARS
                keep.append({
                    'author': it['author'],
                    'title': it['title'],
                    'pageCount': it['pageCount'],
                    'matchRatio': r['ratio'],
                    'truncated': truncated,
                    'text': text[:MAX_CHARS],
                })
                stat['결합'] += 1

            ef = DATA / subj / 'exams' / f'{eid}.json'
            exam = json.load(io.open(ef, encoding='utf-8'))
            exam['commentaries'] = keep
            io.open(ef, 'w', encoding='utf-8', newline='').write(
                json.dumps(exam, ensure_ascii=False, indent=1))
            if eid in by_id:
                by_id[eid]['hasCommentary'] = bool(keep)
                by_id[eid]['commentaryAuthors'] = [k['author'] for k in keep]

        # 해설이 없는 회차도 필드를 채워 화면에서 분기가 단순해지게 한다.
        for e in index['exams']:
            e.setdefault('hasCommentary', False)
            e.setdefault('commentaryAuthors', [])
        io.open(idx_file, 'w', encoding='utf-8', newline='').write(
            json.dumps(index, ensure_ascii=False, indent=1))

        n = sum(1 for e in index['exams'] if e['hasCommentary'])
        print(f'{subj}: {n}/{len(index["exams"])}회차에 해설 결합')

    print('블록:', dict(stat))


if __name__ == '__main__':
    main()
