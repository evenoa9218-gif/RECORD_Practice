// 기록형 과제(서면) 목록과 서면별 배점을 원문에서 다시 읽어 바로잡는다.
//
// 왜: build_record_data.py 는 문제 블록에 등장하는 서면 이름을 전부 과제로 잡았다. 그래서
//   - 서면 이름 목록(DOCS)에 없는 서면이 빠졌다: 위헌법률심판제청신청서·의견서 (공법 2015-2 는 70점짜리 서면이 없었다)
//   - 설명에 스친 이름이 과제가 됐다: 형사 변시 3회 「공소장」, 민사 변시 12회 「답변서」
//   - 피고인 둘에게 같은 서면을 각각 쓰는 형사 문제가 한 과제로 합쳐졌다 (모의 2023-1 검토의견서 60+40)
//   - 배점은 서면 이름 뒤 40자 안에 있을 때만 읽어, 165회차 중 134회차가 비었다
// 배점이 비면 앱과 AI 채점이 100점 만점으로 매긴다. 변호사시험 기록형 만점은 민사법 175·공법 100·형사법 100이다.
//
// 과목마다 지시문 모양이 달라 규칙을 나눈다.
//   형사법: "피고인 김갑동에 대해서는 … 검토의견서를, 피고인 이을남에 대해서는 … 변론요지서를" → 피고인별 과제
//           배점: 채점기준표 → 해설서 머리글에서 「피고인 이름·서면」과 「(N점)」이 같은 줄에 있는 것
//   민사법: "…소장을 작성하시오" / "…답변서를 … 작성하시오" 의 서면 하나 = 175점
//   공법:   번호 항목(1. / 가. / (1)) 마다 서면 이름과 「(N점)」
// 확정 조건: 모든 과제 배점이 양의 정수이고 합이 과목 만점과 같을 것. 아니면 그 회차는 건드리지 않는다.
// 사람이 원문을 보고 정한 것은 OVERRIDE 에 근거와 함께 적는다.
//
//   node pipeline/fill_task_points.js            제안만 출력
//   node pipeline/fill_task_points.js --write    exams/*.json 과 index.json 에 기록 (원래 JSON 형식 그대로)

const fs = require('fs');
const path = require('path');

const DATA = path.join(__dirname, '..', 'data');
const WRITE = process.argv.includes('--write');
const ONLY = (process.argv.find((a) => a.startsWith('--only=')) || '').slice(7);
const FULL = { 민사법: 175, 공법: 100, 형사법: 100 };

// 긴 이름부터 — 「검토의견서」가 「의견서」로, 「행정소장」이 「소장」으로 잡히지 않게
const DOCS = ['위헌법률심판제청신청서', '헌법소원심판청구서', '권한쟁의심판청구서', '행정심판청구서',
  '집행정지신청서', '가처분신청서', '보석허가청구서', '검토보고서', '검토의견서', '변론요지서', '항소이유서', '상고이유서',
  '준비서면', '답변서', '의견서', '행정소장', '소장'];
const DOC_RE = new RegExp(DOCS.join('|'), 'g');
const PTS_RE = /[(（]\s*(?:배점\s*[:：]?\s*)?(\d{1,3})\s*점\s*[)）]/;

// 사람이 원문을 읽고 정한 것 — 자동 규칙이 틀리거나 근거가 흩어진 회차 (2026-09-17 원문 대조)
// unknown:true 는 서면 목록만 확정하고 배점은 비워 둔다 — 근거가 없는데 나누어 적지 않는다.
const T = (title, points) => ({ title, points });
const OVERRIDE = {
  // ── 민사법 ──
  민사법_변시_3회_기록: { why: '문제 【문제 1. 소장 작성】(155점) 【문제 2. 답변서 작성】(20점)', tasks: [T('소장', 155), T('답변서', 20)] },
  민사법_모의_2013_2차_기록: { why: '지시문 "2. 문제 제시 : 답변서 작성" — 소장은 넘겨받은 기록일 뿐, 서면 하나', tasks: [T('답변서', 175)] },
  // ── 공법 ──
  공법_모의_2013_3차_기록: { why: '지시문 1.소장(배점 55점) 2.새 출국명령처분 반박 5줄(배점 10점) 3.답변서(배점 35점)', tasks: [T('소장', 55), T('새 처분 반박', 10), T('답변서', 35)] },
  공법_모의_2014_2차_기록: { why: '지시문 (1)위헌법률심판제청신청서 30 (2)헌법소원심판청구서 30 (3)원고 김보석 준비서면 20 (4)피고 경기도지사 준비서면 20', tasks: [T('위헌법률심판제청신청서', 30), T('헌법소원심판청구서', 30), T('준비서면(원고 김보석)', 20), T('준비서면(피고 경기도지사)', 20)] },
  공법_모의_2014_3차_기록: { why: '지시문 "소장을 작성하시오" 서면 하나 (50점·5점은 소장 안의 세부 배점)', tasks: [T('소장', 100)] },
  공법_모의_2015_1차_기록: { why: '문제 1.취소소송 소장작성 [50점] 2.검토보고서 작성(헌법소원 [30점], 국가배상 [20점])', tasks: [T('소장', 50), T('검토보고서', 50)] },
  공법_모의_2015_3차_기록: { why: '지시문 1.소장(배점 70점) 2.준비서면(배점 30점, 그중 사정판결 위헌성 20점)', tasks: [T('소장', 70), T('준비서면', 30)] },
  공법_모의_2017_3차_기록: { why: '지시문 가.소장(32점) 나.헌법소원심판청구서(50점) / 기준표 "❷문 (18점)" 준비서면', tasks: [T('소장', 32), T('헌법소원심판청구서', 50), T('준비서면', 18)] },
  공법_모의_2018_3차_기록: { why: '지시문·기준표 제1문 헌법소원심판청구서(40점) 제2문 검토보고서(10점) 제3문 소장(50점)', tasks: [T('헌법소원심판청구서', 40), T('검토보고서', 10), T('소장', 50)] },
  공법_모의_2019_1차_기록: { why: '기준표 제1문 헌법소원심판청구서(35점) 제2문 취소소송 소장(50점) 제3문 위헌법률심판제청신청서(15점)', tasks: [T('헌법소원심판청구서', 35), T('소장', 50), T('위헌법률심판제청신청서', 15)] },
  공법_모의_2019_3차_기록: { why: '지시문 1.소장(50점) 2.위헌법률심판제청신청서(50점)', tasks: [T('소장', 50), T('위헌법률심판제청신청서', 50)] },
  공법_모의_2026_1차_기록: { why: '지시문 행정소장의 작성(50점) 2.헌법소원심판청구서의 작성(50점)', tasks: [T('행정소장', 50), T('헌법소원심판청구서', 50)] },
  공법_변시_8회_기록: { why: '지시문 Ⅰ.행정소장(35점) 및 행정심판청구서(15점) Ⅱ.헌법소원심판청구서(50점)', tasks: [T('행정소장', 35), T('행정심판청구서', 15), T('헌법소원심판청구서', 50)] },
  // ── 형사법 ──
  형사법_모의_2014_3차_기록: { why: '지시문 "피고인에 대한 보석허가청구서를 작성하시오" 서면 하나', tasks: [T('보석허가청구서', 100)] },
  형사법_모의_2016_2차_기록: { why: '지시문 "피고인 김갑동의 변호인 … 보석허가청구서를 작성하시오" 서면 하나', tasks: [T('보석허가청구서(김갑동)', 100)] },
  형사법_모의_2017_3차_기록: { why: '기준표 "[검토의견서(55점)]" → 변론요지서 45', tasks: [T('검토의견서(김갑동)', 55), T('변론요지서(이을남)', 45)] },
  형사법_변시_2회_기록: { why: '해설 노수환 "피고인 이을해의 변호인 … 변론요지서를 작성하시오 (45 점)" → 김갑인 55', tasks: [T('변론요지서(김갑인)', 55), T('변론요지서(이을해)', 45)] },
  형사법_변시_3회_기록: { why: '해설 노수환 "피고인 이을남의 변호인 … 변론요지서를 작성하시오 (40 점)" → 검토의견서 60 ("공소장"은 주의사항 속 낱말)', tasks: [T('검토의견서(김갑동)', 60), T('변론요지서(이을남)', 40)] },
  형사법_변시_4회_기록: { why: '해설 노수환 "(김갑동의) 변호인 변호사 김힘찬의 변론요지서를 작성하시오 (50 점)" → 검토의견서 50', tasks: [T('변론요지서(김갑동)', 50), T('검토의견서(이을남)', 50)] },
  형사법_변시_5회_기록: { why: '해설 노수환 "(이을남) 변론요지서를 작성하시오 (45 점)" → 검토의견서 55', tasks: [T('검토의견서(김갑동)', 55), T('변론요지서(이을남)', 45)] },
  형사법_변시_8회_기록: { why: '해설 노수환 "검토의견서 (40 점)" → 이을남 보석허가청구서 60', tasks: [T('검토의견서(김갑동)', 40), T('보석허가청구서(이을남)', 60)] },
  형사법_변시_10회_기록: { why: '해설 노수환 "II. 변론요지서 (60 점)- 피고인 김을남" → 검토의견서 40', tasks: [T('검토의견서(김갑동)', 40), T('변론요지서(김을남)', 60)] },
  형사법_변시_14회_기록: { why: '해설 노수환 "검토의견서 (60 점)" "변론요지서 (40 점)"', tasks: [T('검토의견서(김갑동)', 60), T('변론요지서(이을남)', 40)] },
  // 서면은 확실하지만 배점 근거가 없다
  형사법_변시_1회_기록: { unknown: true, why: '지시문 김토건·이달수 각 변론요지서. 기준표 없음, 해설에 배점 표시 없음', tasks: [T('변론요지서(김토건)'), T('변론요지서(이달수)')] },
  형사법_변시_6회_기록: { unknown: true, why: '지시문 김갑동·이을남 각 검토의견서. 해설 배점이 책 편집용으로 나뉘고 OCR 깨짐(10/40, 40/8)', tasks: [T('검토의견서(김갑동)'), T('검토의견서(이을남)')] },
  형사법_변시_15회_기록: { unknown: true, why: '지시문 김갑동 검토의견서·이을남 변론요지서. 기준표·해설 없음', tasks: [T('검토의견서(김갑동)'), T('변론요지서(이을남)')] },
  형사법_모의_2020_2차_기록: { unknown: true, why: '기준표 서면 머리에 배점 없음. 항목 합 58+38=96 (60/40 로 보이나 확정 불가)', tasks: [T('검토의견서(김갑동)'), T('변론요지서(이을남)')] },
  형사법_모의_2021_2차_기록: { unknown: true, why: '기준표 서면 머리에 배점 없음. 항목 합 57+38=95 (60/40 로 보이나 확정 불가)', tasks: [T('검토의견서(김갑동)'), T('변론요지서(이을남)')] },
};

function pyDumps(v) {
  if (v === null || typeof v !== 'object') return JSON.stringify(v);
  if (Array.isArray(v)) return '[' + v.map(pyDumps).join(', ') + ']';
  return '{' + Object.keys(v).map((k) => JSON.stringify(k) + ': ' + pyDumps(v[k])).join(', ') + '}';
}
function dumpLike(raw, obj) {
  const m = raw.match(/^\{\r?\n([ \t]+)/);
  return (m ? JSON.stringify(obj, null, m[1]) : pyDumps(obj)) + (raw.endsWith('\n') ? '\n' : '');
}

const firstDoc = (s) => { DOC_RE.lastIndex = 0; const m = DOC_RE.exec(s || ''); return m ? m[0] : null; };

// 원문(기준표·해설) 줄 중 조건을 모두 만족하고 배점이 있는 첫 줄의 배점
function headPoints(texts, needles) {
  for (const [label, t] of texts) {
    if (!t) continue;
    for (const line of t.split('\n')) {
      if (line.length > 90) continue;
      if (!needles.every((n) => line.replace(/\s+/g, '').includes(n.replace(/\s+/g, '')))) continue;
      const m = line.match(PTS_RE) || line.match(/(\d{1,3})\s*점/);
      if (m) return { pts: +m[1], from: `${label}: ${line.trim().slice(0, 60)}` };
    }
  }
  return null;
}

// ── 형사법 ────────────────────────────────────────────────
function criminal(e) {
  const block = e.problemBlock || '';
  const tasks = [];
  // 피고인 이름: "피고인 김갑동에 대해서는 …", "피고인 백옥희의 변호인 …와 피고인 신미남의 …",
  // "피고인 김인천, 이수원의 변호인" (쉼표로 나열)
  const people = [];
  for (const m of block.matchAll(/피고인\s*((?:[가-힣]{3}\s*,\s*)*[가-힣]{3})(?=\s*(?:에\s*대|의|과|와|,|및))/g)) {
    for (const n of m[1].split(/\s*,\s*/)) if (!people.some((p) => p.who === n)) people.push({ who: n, at: m.index + m[0].length });
  }
  // 서면: 이름 뒤에 처음 나오는 서면. "A의 변호인 …와 B의 변호인 …의 변론요지서" 처럼 한 서면을 함께 가리키기도 한다.
  // 한 문장에서 변호인 한 명이 여럿을 맡으면("피고인 김인천, 이수원의 변호인 정명변으로서") 서면은 하나다.
  const shared = /피고인\s*[가-힣]{3}\s*,\s*[가-힣]{3}\s*의\s*변호인|피고인들에\s*대하여\s*변호인\s*변호사\s*[가-힣]{3}의/.test(block);
  if (!shared) {
    for (const p of people) {
      DOC_RE.lastIndex = p.at;
      const m = DOC_RE.exec(block);
      if (m) tasks.push({ who: p.who, title: m[0] });
    }
  }
  const texts = [['기준표', e.rubricText], ...((e.commentaries || []).map((c) => [`해설 ${c.author}`, c.text]))];
  // 이름 없는 서면 머리글 — "[ 변론요지서 (55점) ]" (피고인들 각 죄에 대해 서면 종류로 나뉜 문제)
  if (!tasks.length && !shared && e.rubricText) {
    const byDoc = [];
    for (const line of e.rubricText.split('\n')) {
      const m = line.match(/^\s*[\[【]?\s*(변론요지서|검토의견서|검토보고서)\s*[(（]\s*(\d{2,3})\s*점\s*[)）]\s*[\]】]?\s*$/);
      if (m && !byDoc.some((d) => d.title === m[1])) byDoc.push({ title: m[1], points: +m[2], from: `기준표: ${line.trim()}` });
    }
    if (byDoc.length >= 2 && byDoc.reduce((a, d) => a + d.points, 0) === FULL.형사법) return byDoc;
  }

  // 피고인별 최상위 머리글 — 「Ⅰ. 피고인 김갑동에 대하여(45점)」「[피고인 김갑동에 대한 변론요지서(50점)]」
  // 「I. 김갑동에 대한 검토의견서 (50 점)」. 세부 항목「(2점)」을 서면 배점으로 읽지 않게 15~85점만 본다.
  // 기준표가 있으면 기준표만, 없으면 해설서를 하나씩 — 출처를 섞지 않는다.
  const heads = new Map();
  for (const [label, t] of texts) {
    if (!t) continue;
    const found = new Map();
    for (const line of t.split('\n')) {
      if (line.length > 70) continue;
      // "Ⅰ. 피고인 김갑동에 대하여(45점)" / "I. 김갑동에 대한 검토의견서 (50 점)" / "1. 피고인 백옥희 【45점】" / "Ⅰ. 피고인 김갑동 (55점)"
      const m = line.match(/(?:피고인\s*)?([가-힣]{3})\s*에\s*(?:대한|대하여|대해)[^\n()（【]{0,20}[(（【]\s*(\d{2,3})\s*점\s*[)）】]/)
        || line.match(/^\s*(?:[IⅠⅡ]{1,2}|\d)\s*[.．]?\s*피고인\s*([가-힣]{3})\s*[(（【]\s*(\d{2,3})\s*점\s*[)）】]/);
      if (!m) continue;
      // 이름이 지시문의 피고인과 맞아야 한다(해설서의 "피고인 김갑동의 뇌물수수의 점" 같은 쟁점 머리를 막는다)
      if (people.length && !people.some((p) => p.who === m[1])) continue;
      const pts = +m[2];
      if (pts < 15 || pts > 85 || found.has(m[1])) continue;
      found.set(m[1], { pts, from: `${label}: ${line.trim().slice(0, 50)}` });
    }
    const sum = [...found.values()].reduce((a, x) => a + x.pts, 0);
    if (found.size >= 2 && sum === FULL.형사법) { for (const [k, v] of found) heads.set(k, v); break; }
    if (found.size && !heads.size) for (const [k, v] of found) heads.set(k, v);
  }

  if (tasks.length < 2 && heads.size >= 2) {
    // 지시문이 "피고인들에 대해서는 각각…" 이거나 한 사람만 이름을 댄 경우 — 머리글의 피고인으로 채운다
    const doc = (tasks[0] && tasks[0].title) || firstDoc(block);
    if (!doc) return null;
    const docOf = (who) => {
      const h = heads.get(who).from;
      return firstDoc(h) || (tasks.find((t) => t.who === who) || {}).title || doc;
    };
    tasks.length = 0;
    for (const who of heads.keys()) tasks.push({ who, title: docOf(who) });
  }
  if (!tasks.length) {
    const doc = firstDoc(block);
    if (!doc) return null;
    tasks.push({ who: null, title: doc });
  }
  for (const t of tasks) {
    const h = t.who && heads.get(t.who);
    if (h) { t.points = h.pts; t.from = h.from; }
  }
  return tasks.map((t) => ({ title: t.who ? `${t.title}(${t.who})` : t.title, points: t.points, from: t.from }));
}

// ── 민사법 ────────────────────────────────────────────────
function civil(e) {
  const block = e.problemBlock || '';
  // 작성을 명령하는 문장 안의 서면
  const orders = [...block.matchAll(/([^.。\n]{0,120}?)작성하시오/g)].map((m) => firstDoc(m[1])).filter(Boolean);
  const docs = [...new Set(orders)];
  if (docs.length !== 1) return docs.length ? docs.map((d) => ({ title: d })) : null;
  return [{ title: docs[0], points: FULL.민사법, from: '민사 기록형 만점(서면 하나)' }];
}

// ── 공법 ─────────────────────────────────────────────────
function publicLaw(e) {
  const block = e.problemBlock || '';
  // 최상위 번호 항목으로 나눈다: "1." "2." / "가." "나." / "(1)" "(2)" / "Ⅰ."
  const lines = block.split('\n');
  const items = [];
  let cur = null;
  const TOP = /^\s*(?:(\d{1,2})\s*[.．]|\((\d)\)|([가-하])\s*[.．]|([ⅠⅡⅢⅣ]))\s*/;
  for (const ln of lines) {
    const m = ln.match(TOP);
    if (m) { cur = { text: ln }; items.push(cur); } else if (cur) cur.text += '\n' + ln;
  }
  const out = [];
  for (const it of items) {
    const pm = it.text.match(new RegExp(PTS_RE.source, 'g'));
    if (!pm) continue;
    const doc = firstDoc(it.text);
    if (!doc) continue;
    const pts = +pm[pm.length - 1].match(/(\d{1,3})\s*점/)[1];
    const same = out.find((o) => o.title === doc);
    if (same) { same.points += pts; same.from += ` + ${pts}`; } else out.push({ title: doc, points: pts, from: `지시문 (${pts}점)` });
  }
  if (out.length) return out;
  const doc = firstDoc(block);
  return doc ? [{ title: doc }] : null;
}

// ── 실행 ─────────────────────────────────────────────────
const rows = [];
const indexCache = {};
for (const subj of Object.keys(FULL)) {
  const dir = path.join(DATA, subj, 'exams');
  const idxPath = path.join(DATA, subj, 'index.json');
  const idxRaw = fs.readFileSync(idxPath, 'utf8');
  const idx = JSON.parse(idxRaw);
  indexCache[subj] = { idxPath, idxRaw, idx, dirty: false };
  for (const f of fs.readdirSync(dir).sort()) {
    const p = path.join(dir, f);
    const raw = fs.readFileSync(p, 'utf8');
    const e = JSON.parse(raw);
    if (ONLY && !e.id.includes(ONLY)) continue;
    const full = FULL[subj];
    let prop = OVERRIDE[e.id] ? OVERRIDE[e.id].tasks.map((t) => ({ ...t, from: OVERRIDE[e.id].why })) :
      subj === '형사법' ? criminal(e) : subj === '민사법' ? civil(e) : publicLaw(e);
    if (!prop || !prop.length) { rows.push({ id: e.id, ok: false, old: e.tasks, why: '과제를 못 읽음' }); continue; }
    const unknown = !!(OVERRIDE[e.id] && OVERRIDE[e.id].unknown);
    // 하나만 비면 만점에서 뺀 나머지
    const miss = prop.filter((t) => !(t.points > 0));
    if (!unknown && miss.length === 1) {
      const rest = full - prop.reduce((a, t) => a + (t.points > 0 ? t.points : 0), 0);
      if (rest > 0) { miss[0].points = rest; miss[0].from = '만점에서 뺀 나머지'; }
    }
    if (prop.length === 1 && !(prop[0].points > 0)) { prop[0].points = full; prop[0].from = '과목 만점(서면 하나)'; }
    const sum = prop.reduce((a, t) => a + (t.points > 0 ? t.points : 0), 0);
    // unknown: 서면 목록만 확정(배점은 비움). 그래도 기록한다 — 틀린 서면 목록을 두는 것보다 낫다.
    const ok = unknown ? prop.every((t) => !(t.points > 0)) : prop.every((t) => t.points > 0) && sum === full;
    // ⚠ 번호는 옛 과제의 것을 이어 쓴다. 앱이 답안 초안을 「회차::t{번호}」로 저장하므로, 가운데에
    //    새 서면이 끼어 번호가 밀리면 이미 써 둔 헌법소원 초안이 가처분신청서 칸에 뜬다.
    //    같은 서면(이름이 같거나 "검토의견서" → "검토의견서(김갑동)")은 옛 번호, 새 서면은 뒷번호.
    const oldTasks = e.tasks || [];
    const usedNo = new Set();
    let nextNo = Math.max(0, ...oldTasks.map((t) => t.no));
    const newTasks = prop.map((t) => {
      const base = t.title.replace(/\(.*\)$/, '');
      const o = oldTasks.find((x) => !usedNo.has(x.no) && (x.title === t.title || x.title === base));
      const no = o ? o.no : ++nextNo;
      usedNo.add(no);
      return { no, title: t.title, points: t.points > 0 ? t.points : null };
    });
    const same = JSON.stringify(newTasks) === JSON.stringify((e.tasks || []).map((t) => ({ no: t.no, title: t.title, points: t.points })));
    rows.push({ id: e.id, ok, same, sum, full, old: e.tasks, prop });
    if (ok && !same && WRITE) {
      e.tasks = newTasks.map((t, i) => ({ ...t, pointsSource: unknown ? `배점 미확정 — ${prop[i].from}` : prop[i].from }));
      e.taskSource = 'fill_task_points';
      fs.writeFileSync(p, dumpLike(raw, e));
      const ent = idx.exams.find((x) => x.id === e.id);
      if (ent) {
        ent.tasks = newTasks;
        ent.totalPoints = unknown ? null : sum;
        ent.taskSource = 'fill_task_points';
        indexCache[subj].dirty = true;
      }
    }
  }
}
if (WRITE) for (const c of Object.values(indexCache)) if (c.dirty) fs.writeFileSync(c.idxPath, dumpLike(c.idxRaw, c.idx));

const fmtOld = (ts) => (ts || []).map((t) => `${t.title}(${t.points ?? '-'})`).join('+') || '(없음)';
const fmtNew = (ps) => ps.map((t) => `${t.title}(${t.points ?? '?'})`).join('+');
let nOk = 0, nChange = 0;
for (const r of rows) {
  if (r.ok) nOk++;
  if (r.ok && !r.same) nChange++;
  const mark = !r.ok ? '✗' : r.same ? '=' : '✓';
  console.log(`${mark} ${r.id.padEnd(24)} ${fmtOld(r.old)}  →  ${r.prop ? fmtNew(r.prop) : r.why}${r.ok ? '' : `  [합 ${r.sum}/${r.full}]`}`);
  if (process.argv.includes('--why') && r.prop) for (const t of r.prop) console.log(`      · ${t.title}: ${t.from || '-'}`);
}
console.log(`\n확정 ${nOk}/${rows.length} (바뀌는 회차 ${nChange}) · 보류 ${rows.length - nOk}`);
console.log(WRITE ? '기록했다.' : '제안만 했다. 기록하려면 --write');
