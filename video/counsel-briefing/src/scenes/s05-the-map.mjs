import { a, esc, num, tag } from '../components.mjs';

export default (c) => {
  const g11 = c.qs('11').length;
  const g14 = c.qs('14').length;
  if (g11 + g14 !== 21) throw new Error(`expected 21 numbered questions, found ${g11 + g14}`);

  const tiles = [
    { x: 96, gate: 'Gate 11', n: String(g11), unit: 'questions', title: c.gate('11').title, kind: '' },
    { x: 700, gate: 'Gate 14', n: String(g14), unit: 'questions', title: c.gate('14').title, kind: '' },
    { x: 1304, gate: 'Gate 15', n: '4', unit: 'open points, not drafted', title: c.gate('15').title, kind: 'k' },
  ];
  const tile = (t, i) =>
    `<div class="gt ${t.kind}" style="left:${t.x}px" ${a('wipeY', { at: 0.15 + i * 0.4, dur: 0.55 })}>` +
    `<div class="gg up b">${esc(t.gate)}</div>` +
    `<div class="gn" style="font-size:150px">${num(t.n, { at: 0.5 + i * 0.4 })}</div>` +
    `<div class="gu">${esc(t.unit)}</div>` +
    `<div class="gh up b">${esc(t.title)}</div></div>`;

  return {
    id: 's05-the-map',
    chapterId: 'why',
    chapter: 'The questions',
    title: 'The map',
    css: `
      .s05 .gt { position: absolute; top: 150px; width: 520px; height: 440px; background: var(--soft); color: #000; padding: 28px 32px; }
      .s05 .gt.k { background: transparent; color: var(--soft); outline: 4px solid var(--soft); outline-offset: -4px; }
      .s05 .gg { font-size: 34px; letter-spacing: .04em; }
      .s05 .gn { margin-top: 10px; }
      .s05 .gu { font-size: 32px; margin-top: 4px; }
      .s05 .gh { font-size: 36px; line-height: 1.12; margin-top: 22px; }
      .s05 .part { position: absolute; top: 720px; width: 840px; height: 150px; padding: 20px 26px; }
    `,
    beats: [
      {
        say: `Two questionnaires are drafted and a third gate is not. Between them, ${g11 + g14} numbered questions.`,
        stay: true,
        show: () =>
          `<div class="s05">${tiles.map(tile).join('')}` +
          `<div class="abs" style="left:96px;top:620px">${tag(`${g11} + ${g14} = ${g11 + g14} numbered questions`, { kind: 'p', at: 2.2, cls: 'big' })}</div></div>`,
      },
      {
        say: `Each drafted set splits into what we hold today and what we do next. Please start with today; in gate 11 you can stop there.`,
        stay: true,
        show: () =>
          `<div class="s05">` +
          `<div class="part box c" style="left:96px;background:var(--coral);color:#000;top:720px;height:150px" ${a('wipeX', { at: 0.2, dur: 0.5 })}>` +
          `<div class="b up" style="font-size:36px">Part A: what we hold today</div><div style="font-size:30px">Clock running. Answer first.</div></div>` +
          `<div class="part box" style="left:984px;top:720px;height:150px;background:transparent;color:var(--soft);outline:4px solid var(--soft);outline-offset:-4px" ${a('wipeX', { at: 0.8, dur: 0.5 })}>` +
          `<div class="b up" style="font-size:36px">Part B: what comes next</div><div style="font-size:30px">Publication in gate 11; the rule going forward in gate 14.</div></div>` +
          `</div>`,
      },
    ],
  };
};
