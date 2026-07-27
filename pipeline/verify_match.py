# -*- coding: utf-8 -*-
"""매칭이 실제로 맞는지 내용으로 교차검증.

회차 머리글이 잡혔다고 내용까지 맞다는 보장은 없다 — OCR이 숫자를 흘리면
12회 해설이 13회에 붙을 수 있다. 그래서 **시험 문제에만 나오는 고유명사**를
뽑아 해설 블록에 실제로 등장하는지 본다.

기록형은 당사자 이름이 회차마다 다르다(김갑동·이을남·이태연…). 그 이름이
해설에 없으면 다른 회차가 붙었다는 뜻이다.
"""
import io
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work' / 'casebook'
DATA = ROOT / 'data'

# 한글 인명(2~4자) + 기관/처분명 후보
NAME = re.compile(r'[가-힣]{2,4}(?=(?:은|는|이|가|을|를|에게|의|과|와|씨|\s|,|\.))')
# 어디에나 나오는 말은 지문 구실을 못 한다.
STOP = set('''
피고 원고 피고인 검사 변호인 법원 판결 사건 소송 청구 처분 신청 증거 진술 조서
서울 지방 고등 대법원 검찰청 경찰서 주식회사 대표 이사 사람 경우 사실 내용 관련
다음 이상 이하 기타 별지 첨부 참고 작성 제출 기재 확인 요청 결정 명령 통지 위반
당사 해당 각각 모두 그것 이것 저것 때문 이유 목적 방법 결과 문제 답안 해설 정답
'''.split())


def distinctive(text, k=12):
    """이 문서에만 자주 나오는 이름 후보."""
    c = Counter(w for w in NAME.findall(text) if w not in STOP and len(w) >= 3)
    return [w for w, n in c.most_common(k * 3) if n >= 2][:k]


def main():
    rows, summary = [], Counter()
    for subj in ['공법', '민사법', '형사법']:
        bf = WORK / f'blocks_{subj}.json'
        if not bf.exists():
            continue
        blocks = json.load(io.open(bf, encoding='utf-8'))
        for eid, items in sorted(blocks.items()):
            ef = DATA / subj / 'exams' / f'{eid}.json'
            if not ef.exists():
                continue
            exam = json.load(io.open(ef, encoding='utf-8'))
            keys = distinctive(exam.get('problemText') or '')
            for it in items:
                if not keys:
                    verdict, hit, ratio = 'unknown', 0, 0.0
                else:
                    hit = sum(1 for k in keys if k in it['text'])
                    ratio = hit / len(keys)
                    verdict = ('ok' if ratio >= 0.5 else
                               'weak' if ratio >= 0.25 else 'mismatch')
                summary[verdict] += 1
                rows.append({
                    'subject': subj, 'examId': eid, 'author': it['author'],
                    'pages': it['pageCount'], 'keys': len(keys),
                    'hits': hit, 'ratio': round(ratio, 2), 'verdict': verdict,
                })

    rows.sort(key=lambda r: (r['verdict'] != 'mismatch', r['ratio']))
    io.open(WORK / 'match_report.json', 'w', encoding='utf-8', newline='').write(
        json.dumps(rows, ensure_ascii=False, indent=1))

    print('판정:', dict(summary))
    print('\n-- 의심스러운 것부터 --')
    for r in rows[:14]:
        print(f"  [{r['verdict']:8}] {r['examId']:26} {r['author']:4} "
              f"{r['pages']:3}쪽 지문 {r['hits']}/{r['keys']}")


if __name__ == '__main__':
    main()
