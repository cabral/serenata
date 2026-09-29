import { a, esc, icon, num, tag } from '../components.mjs';

export default (c) => {
  const tiles = [
    { x: 96, y: 150, n: c.f('rows'), what: 'rows held today, in 12 tables', ask: 'Kept, rebuilt narrower or deleted: gate 11, A1 and A3' },
    { x: 976, y: 150, n: c.f('flags'), what: 'flags, none published', ask: 'Publishable or not: gate 11, B2' },
    { x: 96, y: 500, n: c.f('addressShaped'), what: 'address-shaped values in retained fields', ask: 'Rejected, redacted, held or dropped: gate 14' },
    { x: 976, y: 500, n: c.f('beneficialOwners'), what: 'beneficial-owner leaf elements dropped in one day', ask: 'Analysed, or never: gate 15' },
  ];
  const tile = (t, i) =>
    `<div class="wt" style="left:${t.x}px;top:${t.y}px" ${a('wipeX', { at: 0.2 + i * 0.4, dur: 0.5 })}>` +
    `<div class="wn">${num(t.n, { at: 0.5 + i * 0.4, step: 0.07 })}</div>` +
    `<div class="ww">${esc(t.what)}</div><div class="wa">${esc(t.ask)}</div></div>`;

  const lands = [
    { glyph: 'brackets', head: 'A line in the drop list', sub: "the parser's drop list and docs/personal-data.md, changed together" },
    { glyph: 'doc', head: 'A decision record', sub: 'an ADR, and the record at the foot of each instruction' },
    { glyph: 'check', head: 'A test', sub: 'synthetic fixtures for every case, never real notices' },
    { glyph: 'trash', head: 'A deletion or a rebuild', sub: 'of what we hold, with a deadline and an owner' },
  ];
  const landing = (l, i) =>
    `<div class="ld" style="left:${96 + i * 436}px" ${a('wipeY', { at: 0.2 + i * 0.5, dur: 0.5 })}>` +
    `<div class="li">${icon(l.glyph, { px: 120, color: '#000', accent: 'var(--purple)' })}</div>` +
    `<div class="lh up b">${esc(l.head)}</div><div class="ls">${esc(l.sub)}</div></div>`;

  return {
    id: 's10-what-waits',
    chapterId: 'answers',
    chapter: 'Your answers',
    title: 'What waits on your answers',
    css: `
      .s10 .wt { position: absolute; width: 848px; height: 322px; background: var(--soft); color: #000; padding: 26px 36px; }
      .s10 .wt .wn { font-size: 112px; color: var(--purple); }
      .s10 .wt .ww { font-size: 38px; line-height: 1.15; margin-top: 12px; font-weight: 700; }
      .s10 .wt .wa { font-size: 31px; line-height: 1.2; margin-top: 12px; color: #333; }
      .s10 .ld { position: absolute; top: 200px; width: 412px; height: 500px; background: var(--soft); color: #000; padding: 26px 28px; }
      .s10 .ld .lh { font-size: 40px; line-height: 1.1; margin: 26px 0 16px; }
      .s10 .ld .ls { font-size: 31px; line-height: 1.25; overflow-wrap: anywhere; }
      .s10 .big { position: absolute; left: 96px; top: 250px; font-size: 176px; width: 1728px; }
    `,
    beats: [
      {
        say: `Here is what waits on your answers.`,
        min: 6.5,
        show: () => `<div class="s10">${tiles.map(tile).join('')}</div>`,
      },
      {
        say: `Each answer lands somewhere concrete: the drop list, a decision record, a test, or a deletion.`,
        show: () => `<div class="s10">${lands.map(landing).join('')}</div>`,
      },
      {
        say: `A no is a result too. The code changes, the data shrinks, and the decision is recorded.`,
        show: () =>
          `<div class="s10"><div class="big pix" ${a('wipeX', { at: 0.15, dur: 0.7 })}>A no is <span class="lilac">a result.</span></div>` +
          `<div class="abs" style="left:96px;top:640px;display:flex;gap:16px">${tag('The code changes', { kind: 'k', at: 3 })}${tag('The data shrinks', { kind: 'k', at: 5 })}${tag('The decision is recorded', { kind: 'p', at: 7 })}</div></div>`,
      },
    ],
  };
};
