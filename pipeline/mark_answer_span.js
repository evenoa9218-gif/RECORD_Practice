/**
 * 해설(commentaries)에서 **모범답안이 시작하는 지점**을 표시한다.
 *
 *   node pipeline/mark_answer_span.js [--write]
 *
 * 왜 필요한가. 해설서는 회차마다 문제와 사건기록을 앞에 다시 싣는다. 정연석 민사는
 * 앞 3만 자, 노수환 형사는 앞 4만 자가 재수록이다(형사는 두 번 실리기도 한다).
 * AI 채점 워커는 근거 글자 수에 상한이 있어, 앞에서부터 자르면 정작 채점 기준인
 * 모범답안이 통째로 잘려 나갔다 — 2026-09-17 민사 13회 실채점에서 모델이 해설과
 * 정반대로 감점해 드러났다.
 *
 * 찾는 방법은 제목이 아니라 **중복**이다. 스캔 OCR 이라 "모범답안", "Ⅰ. 피고인 ○○에
 * 대한 변론요지서" 같은 표제는 회차마다 다르게 깨져 정규식으로는 절반도 못 잡는다.
 * 대신 재수록 구간은 problemText 와 글자가 겹치므로, 12자 조각이 얼마나 겹치는지를
 * 1,000자 블록마다 재서 마지막 겹침 블록 다음을 답안 시작으로 본다.
 * 경계는 일부러 조금 앞에 잡힌다 — 답안을 자르는 것보다 재수록 꼬리를 남기는 쪽이 낫다.
 */
const fs = require('fs');
const path = require('path');

const DATA = path.join(__dirname, '..', 'data');
const SUBJECTS = ['공법', '민사법', '형사법'];
const WRITE = process.argv.includes('--write');

const N = 12;          // 겹침을 재는 글자 조각 길이
const BLOCK = 1000;    // 판정 단위(정규화 후 글자 수)
const HIT = 0.35;      // 이 비율 넘게 겹치면 재수록으로 본다

const isWord = (ch) => /[가-힣0-9A-Za-z]/.test(ch);

function answerAt(text, problem) {
  if (!text || !problem) return 0;
  // 정규화 좌표 → 원본 좌표 대응표. 공백·문장부호는 OCR 마다 달라 빼고 센다.
  const map = [];
  let normed = '';
  for (let i = 0; i < text.length; i++) {
    if (isWord(text[i])) { normed += text[i]; map.push(i); }
  }
  let pnorm = '';
  for (let i = 0; i < problem.length; i++) if (isWord(problem[i])) pnorm += problem[i];
  const set = new Set();
  for (let i = 0; i + N <= pnorm.length; i++) set.add(pnorm.substr(i, N));

  let last = -1;
  for (let b = 0; b * BLOCK < normed.length; b++) {
    const seg = normed.substr(b * BLOCK, BLOCK);
    let found = 0, total = 0;
    for (let j = 0; j + N <= seg.length; j += 5) { total++; if (set.has(seg.substr(j, N))) found++; }
    if (total && found / total >= HIT) last = b;
  }
  if (last < 0) return 0;
  const start = (last + 1) * BLOCK;
  // 재수록이 끝까지 이어진 것처럼 잡히면(= 해설이 통째로 문제 재수록이면) 표시하지 않는다.
  if (start >= normed.length * 0.95) return 0;
  return map[start] ?? 0;
}

let changed = 0, files = 0;
for (const subj of SUBJECTS) {
  const dir = path.join(DATA, subj, 'exams');
  for (const f of fs.readdirSync(dir)) {
    const file = path.join(dir, f);
    const raw = fs.readFileSync(file, 'utf8');
    const exam = JSON.parse(raw);
    if (!exam.commentaries?.length) continue;
    let touched = false;
    for (const c of exam.commentaries) {
      const at = answerAt(c.text || '', exam.problemText || '');
      if (c.answerAt !== at) { c.answerAt = at; touched = true; }
      const cut = (c.text || '').length - at;
      console.log(
        `${exam.id.padEnd(24)} ${(c.author || '').slice(0, 4).padEnd(4)}`
        + ` 전체 ${String((c.text || '').length).padStart(6)}`
        + ` 답안시작 ${String(at).padStart(6)}  채점에 쓸 ${String(cut).padStart(6)}자`
        + (at === 0 ? '  (재수록 없음)' : ''),
      );
    }
    files++;
    if (touched && WRITE) {
      // 원래 형식(들여쓰기 1칸)을 그대로 지킨다.
      fs.writeFileSync(file, JSON.stringify(exam, null, 1));
      changed++;
    }
  }
}
console.log(`\n해설 있는 회차 ${files}건, ${WRITE ? `${changed}건 기록함` : '미리보기(--write 로 반영)'}`);
