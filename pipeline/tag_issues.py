# -*- coding: utf-8 -*-
"""해설 텍스트에서 쟁점을 찾아 회차에 태깅.

## 왜 해설을 보는가

기록 전문은 회차당 1.5~9만 자인데 대부분이 진술조서·판결문 같은 **사실관계**다.
쟁점은 거기 적혀 있지 않다. 반면 해설은 "표현의 자유(과잉금지·명확성), 원고적격,
제소기간, 재량권 한계" 식으로 쟁점을 이미 정리해 놓았다. 같은 결과를 훨씬
적은 분량으로 얻는다.

## 왜 LLM을 쓰지 않는가

쟁점 ID는 네 앱을 잇는 척추다(CASE_Practice `docs/ARCHITECTURE.md` 3절).
새로 지어내면 선택형·사례형과 연결이 끊긴다. 그래서 **사례형이 이미 발급한
레지스트리(PUB/CRI/CIV 1,454개)의 이름과 별칭을 해설에서 찾는** 방식으로 한다.
결정론적이고, 비용이 들지 않고, ID가 자동으로 정합한다.

레지스트리에 없는 쟁점은 잡히지 않는다. 그건 후보로 따로 보고한다 —
ID 발급은 사례형 레지스트리(정본)를 건드리는 일이라 여기서 함부로 하지 않는다.
"""
import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
WORK = ROOT / 'work'
# 사례형 저장소의 쟁점 레지스트리가 정본이다.
CASE = Path(__file__).resolve().parents[2] / 'CASE_Practice' / 'data'

SUBJECTS = ['공법', '민사법', '형사법']

# 2자 키워드는 일반 문장에도 흔해 오탐이 크다("배당", "상계", "자백"…).
MIN_KEY_LEN = 3
# 해설에 이만큼은 나와야 그 회차의 쟁점으로 본다. 1회는 배경 언급일 수 있다.
MIN_HITS = 2


def norm(s):
    """공백을 지운다. 레지스트리는 '재판의전제성', 본문은 '재판의 전제성'이고
    OCR은 글자 사이에 공백을 더 끼워 넣는다."""
    return re.sub(r'\s+', '', s)


def load_registry(subject):
    f = CASE / f'issues_{subject}.json'
    if not f.exists():
        sys.exit(f'쟁점 레지스트리가 없다: {f}')
    reg = json.load(io.open(f, encoding='utf-8'))
    keys = []          # (정규화키, issueId)
    meta = {}
    for it in reg['issues']:
        meta[it['id']] = {'id': it['id'], 'label': it['label'],
                          'path': it.get('path') or [], 'aliases': it.get('aliases') or []}
        for k in [it['label']] + (it.get('aliases') or []):
            nk = norm(k)
            if len(nk) >= MIN_KEY_LEN:
                keys.append((nk, it['id']))
    # 긴 키를 먼저 본다 — '취소소송의원고적격'이 '원고적격'보다 구체적이다.
    keys.sort(key=lambda x: -len(x[0]))
    return keys, meta


def tag_subject(subject):
    keys, meta = load_registry(subject)
    idx_file = DATA / subject / 'index.json'
    index = json.load(io.open(idx_file, encoding='utf-8'))

    by_issue = defaultdict(list)
    issue_hits = Counter()
    tagged = untagged = 0
    per_exam = []

    for e in index['exams']:
        ef = DATA / subject / 'exams' / f"{e['id']}.json"
        exam = json.load(io.open(ef, encoding='utf-8'))
        comms = exam.get('commentaries') or []
        if not comms:
            exam['issueIds'] = []
            io.open(ef, 'w', encoding='utf-8', newline='').write(
                json.dumps(exam, ensure_ascii=False, indent=1))
            e['issueIds'] = []
            untagged += 1
            continue

        blob = norm('\n'.join(c['text'] for c in comms))
        found = Counter()
        for nk, iid in keys:
            n = blob.count(nk)
            if n:
                found[iid] += n

        ids = [i for i, n in found.most_common() if n >= MIN_HITS]
        exam['issueIds'] = ids
        io.open(ef, 'w', encoding='utf-8', newline='').write(
            json.dumps(exam, ensure_ascii=False, indent=1))
        e['issueIds'] = ids
        for i in ids:
            by_issue[i].append(e['id'])
            issue_hits[i] += 1
        tagged += 1
        per_exam.append(len(ids))

    # 이 과목의 기록형에 실제로 나온 쟁점만 레지스트리로 낸다.
    issues = []
    for iid, cnt in issue_hits.most_common():
        m = dict(meta[iid])
        m['examCount'] = cnt
        issues.append(m)
    io.open(DATA / f'issues_{subject}.json', 'w', encoding='utf-8', newline='').write(
        json.dumps({'subject': subject, 'prefix': issues[0]['id'][:3] if issues else None,
                    'count': len(issues), 'issues': issues}, ensure_ascii=False, indent=1))

    index['byIssue'] = {k: v for k, v in sorted(by_issue.items())}
    io.open(idx_file, 'w', encoding='utf-8', newline='').write(
        json.dumps(index, ensure_ascii=False, indent=1))

    avg = sum(per_exam) / len(per_exam) if per_exam else 0
    print(f'{subject}: 해설 있는 {tagged}회차 태깅 (없어서 건너뜀 {untagged})'
          f' · 쟁점 {len(issues)}종 · 회차당 평균 {avg:.1f}개')
    return per_exam


def main():
    WORK.mkdir(exist_ok=True)
    for s in SUBJECTS:
        tag_subject(s)


if __name__ == '__main__':
    main()
