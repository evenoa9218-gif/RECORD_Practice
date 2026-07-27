# -*- coding: utf-8 -*-
"""기록형 원본 txt → 앱 데이터(`../data/`).

사례형 파이프라인과 같은 자리에 서지만 훨씬 짧다. 기록형은 쟁점 태깅을 아직
하지 않았기 때문에, 여기서는 **문제와 채점기준표를 회차로 짝지어 정제**하는
데까지만 한다(쟁점별 풀기는 태깅이 생긴 뒤에).

원본은 저작권 자료라 저장소 밖에 있다. 경로는 환경변수로 준다:

    set RECORD_RAW=C:\\...\\모의고사 기출문제, 모범답안
    python -X utf8 build_record_data.py
"""
import io
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clean_text import clean_hwp  # noqa: E402

RAW = Path(os.environ.get(
    'RECORD_RAW',
    r'C:\Users\82109\Desktop\2026\변시대비 자료 및 pdf\모의고사 기출문제, 모범답안',
))
OUT = Path(__file__).resolve().parents[1] / 'data'
SUBJECTS = ['공법', '민사법', '형사법']

# 파일명에서 회차를 읽는다. 일부 파일은 공백이 밑줄로 바뀌어 있어 먼저 편다.
MOCK = re.compile(r'(20\d{2})년도\s*제(\d)차')
BAR = re.compile(r'제(\d+)회\s*변호사시험')

# 문제 블록. 【 문 제 】 뒤부터 작성요령 전까지.
PROBLEM_HEAD = re.compile(r'【\s*문\s*제\s*】')
NEXT_HEAD = re.compile(r'^\s*(?:【|Ⅱ\.|II\.|2\.)\s*(?:작성요령|작성 요령)', re.M)

# 과제 표기는 과목마다 근본적으로 다르다. 번호·배점으로는 공법만 잡힌다.
#   공법   Ⅰ. 헌법소원심판청구서의 작성 (50점)   ← 로마자 번호 + 배점
#   형사법 "…검토보고서를, …변론요지서를 각 작성하되"  ← 문장 안, 번호·배점 없음
#   민사법 "…소장을 작성하시오."                      ← 과제 하나, 번호·배점 없음
# 그래서 번호가 아니라 **작성할 서면 종류**를 기준으로 찾는다. 기록형에서
# 요구하는 서면은 종류가 정해져 있어 이쪽이 훨씬 안정적이다.
DOCS = [
    '헌법소원심판청구서', '행정소장', '검토보고서', '검토의견서', '변론요지서',
    '항소이유서', '상고이유서', '준비서면', '答辯書', '답변서', '고소장', '공소장',
    '소장',   # 가장 짧아 마지막 — '행정소장'이 먼저 잡히도록
]
DOC_RE = re.compile('(' + '|'.join(DOCS) + ')')
# 배점이 붙어 있으면 같이 읽는다. 없으면 None.
POINTS_NEAR = re.compile(r'[（(]\s*(\d+)\s*점\s*[)）]')
# 번호는 아라비아·로마자 양쪽 다.
NUMBERED = re.compile(r'^\s*([ⅠⅡⅢⅣⅤ]|\d+)\s*[.．]\s*(.{0,60}?)\s*$', re.M)


def exam_key(filename):
    """('모의','2025','1') / ('변시','15','') / None"""
    n = filename.replace('_', ' ')
    m = MOCK.search(n)
    if m:
        return ('모의', m.group(1), m.group(2))
    m = BAR.search(n)
    if m:
        return ('변시', m.group(1), '')
    return None


def exam_id(subject, key):
    kind, a, b = key
    return f'{subject}_{kind}_{a}_{b}차_기록' if kind == '모의' else f'{subject}_변시_{a}회_기록'


def exam_label(subject, key):
    kind, a, b = key
    return f'{a}년 {b}차 {subject} 기록형' if kind == '모의' else f'제{a}회 변시 {subject} 기록형'


def pick(paths):
    """같은 회차에 파일이 여럿이면 가장 큰 것을 쓴다.

    '(배포용)'이 따로 있는 회차가 있는데, 내용이 잘린 쪽이 작다.
    """
    return max(paths, key=lambda p: p.stat().st_size)


def read(path):
    return io.open(path, encoding='utf-8', errors='replace').read()


def extract_tasks(problem_text):
    """문제 블록에서 '어떤 서면을 쓰라'는 과제 목록을 뽑는다.

    반환: (tasks, 문제블록, 근거)
    근거는 무엇을 보고 뽑았는지 — 화면에서 신뢰도를 알리는 데 쓴다.
    """
    m = PROBLEM_HEAD.search(problem_text)
    if not m:
        return [], None, 'none'
    body = problem_text[m.end():]
    nxt = NEXT_HEAD.search(body)
    block = (body[:nxt.start()] if nxt else body[:4000]).strip()

    # 같은 서면이 여러 번 언급돼도 과제는 하나다. 처음 나온 순서를 지킨다.
    seen, tasks = set(), []
    for mm in DOC_RE.finditer(block):
        doc = mm.group(1)
        # '행정소장'을 이미 잡았으면 뒤에 나오는 '소장'은 같은 서면을 가리킨다.
        # 부분문자열이면 새 과제로 세지 않는다.
        if doc in seen or any(doc in s for s in seen):
            continue
        seen.add(doc)
        # 배점은 서면 이름 뒤 40자 안에 붙어 있으면 그 값으로 본다.
        tail = block[mm.end():mm.end() + 40]
        pt = POINTS_NEAR.search(tail)
        tasks.append({
            'no': len(tasks) + 1,
            'title': doc,
            'points': int(pt.group(1)) if pt else None,
        })

    if not tasks:
        return [], block, 'none'
    src = 'points' if any(t['points'] for t in tasks) else 'document'
    return tasks, block, src


def build(subject):
    probs, rubs = defaultdict(list), defaultdict(list)
    for p in (RAW / subject / '문제' / '기록형').rglob('*.txt'):
        if p.stat().st_size == 0:
            continue
        k = exam_key(p.name)
        if k:
            probs[k].append(p)
    for p in (RAW / subject / '채점기준표' / '기록형').rglob('*.txt'):
        if p.stat().st_size == 0:
            continue
        k = exam_key(p.name)
        if k:
            rubs[k].append(p)

    (OUT / subject / 'exams').mkdir(parents=True, exist_ok=True)
    index, no_rubric, no_tasks = [], [], []

    for k in sorted(probs, key=lambda x: (x[0] != '변시', x[1], x[2])):
        eid = exam_id(subject, k)
        problem = clean_hwp(read(pick(probs[k])))
        rubric = clean_hwp(read(pick(rubs[k]))) if k in rubs else None
        tasks, problem_block, task_src = extract_tasks(problem)

        if rubric is None:
            no_rubric.append(eid)
        if not tasks:
            no_tasks.append(eid)

        io.open(OUT / subject / 'exams' / f'{eid}.json', 'w', encoding='utf-8', newline='').write(
            json.dumps({
                'id': eid,
                'label': exam_label(subject, k),
                'kind': k[0],
                'problemText': problem,
                'problemBlock': problem_block,
                'rubricText': rubric,
                'tasks': tasks,
                'taskSource': task_src,
            }, ensure_ascii=False, indent=1)
        )
        index.append({
            'id': eid,
            'label': exam_label(subject, k),
            'kind': k[0],
            'year': k[1],
            'round': k[2],
            'tasks': [{'no': t['no'], 'title': t['title'], 'points': t['points']} for t in tasks],
            'totalPoints': sum(t['points'] for t in tasks if t['points']) or None,
            'taskSource': task_src,
            'hasRubric': rubric is not None,
            'chars': len(problem),
        })

    io.open(OUT / subject / 'index.json', 'w', encoding='utf-8', newline='').write(
        json.dumps({'subject': subject, 'exams': index}, ensure_ascii=False, indent=1)
    )
    print(f'{subject}: {len(index)}건  채점기준표없음 {len(no_rubric)}  과제파싱실패 {len(no_tasks)}')
    if no_tasks:
        print(f'   과제 못 뽑음: {no_tasks[:6]}')
    return index


def main():
    if not RAW.exists():
        sys.exit(f'원본 폴더를 찾지 못했다: {RAW}\nRECORD_RAW 환경변수로 지정할 것.')
    OUT.mkdir(exist_ok=True)
    subjects = []
    for s in SUBJECTS:
        idx = build(s)
        subjects.append({'id': s, 'count': len(idx)})
    io.open(OUT / 'subjects.json', 'w', encoding='utf-8', newline='').write(
        json.dumps({'subjects': subjects}, ensure_ascii=False, indent=1)
    )
    print('완료 →', OUT)


if __name__ == '__main__':
    main()
