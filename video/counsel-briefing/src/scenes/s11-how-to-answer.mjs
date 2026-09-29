import { a, esc, icon, tag } from '../components.mjs';

// The seven rows of the decision record at the foot of every counsel
// instruction (docs/automation/handoffs.md).
const ROWS = [
  'Decision status and provenance',
  'Bounded scope',
  'Permitted and prohibited actions',
  'Expiry and reassessment',
  'Implementation conditions',
  'Existing holdings',
  'Completion evidence',
];

export default (c) => {
  const table = (mode, t) =>
    `<div class="s11"><div class="dt">` +
    ROWS.map((r, i) => {
      const enter = mode === 'first' ? a('wipeX', { at: 0.3 + i * 0.35, dur: 0.4 }) : a('cut', { at: 0 });
      const sweep = mode === 'sweep' ? `<i class="hl" ${a('bar', { at: 0.4 + (i * (t.dur - 1.8)) / ROWS.length, dur: 0.5 })}></i>` : '';
      return (
        `<div class="dr" style="top:${i * 92}px" ${enter}>${sweep}` +
        `<span class="rn pix">${i + 1}</span><span class="rl up b">${esc(r)}</span>` +
        `<span class="rs">${tag('Unresolved', { kind: 'c', anim: 'cut', at: mode === 'first' ? 0.6 + i * 0.35 : 0 })}</span></div>`
      );
    }).join('') +
    `</div></div>`;

  return {
    id: 's11-how-to-answer',
    chapterId: 'answers',
    chapter: 'Your answers',
    title: 'How to answer',
    css: `
      .s11 .dt { position: absolute; left: 96px; top: 150px; width: 1728px; height: 650px; }
      .s11 .dr { position: absolute; left: 0; width: 1728px; height: 80px; border-top: 3px solid var(--rule); display: flex; align-items: center; }
      .s11 .dr .rn { position: relative; z-index: 1; width: 90px; font-size: 48px; color: var(--lilac); }
      .s11 .dr .rl { font-size: 38px; flex: 1; position: relative; z-index: 1; }
      .s11 .dr .rs { position: relative; z-index: 1; }
      .s11 .dr .hl { position: absolute; left: 0; top: 4px; width: 100%; height: 72px; background: var(--deep); transform-origin: left center; }
    `,
    beats: [
      {
        say: `Answer in whatever form suits you. I'll transcribe it into a decision record with seven rows.`,
        show: () => table('first'),
      },
      {
        say: `It records who decided and on what advice, the scope, what is allowed and prohibited, when it expires, what the code must change, what happens to existing holdings, and the evidence it was done.`,
        show: (t) => table('sweep', t),
      },
      {
        say: `Your advice itself stays private. The repository carries only a screened summary.`,
        show: () =>
          `<div class="s11"><div class="abs" style="left:96px;top:190px;color:var(--lilac)" ${a('pop', { at: 0.1 })}>${icon('lock', { px: 220 })}</div>` +
          `<div class="abs" style="left:400px;top:210px;display:flex;flex-direction:column;gap:22px">` +
          tag('Detailed advice: a restricted channel', { kind: 'p', cls: 'big', at: 0.5 }) +
          tag('The repository: a screened summary only', { kind: 'k', cls: 'big', at: 1.3 }) +
          `</div>` +
          `<div class="abs grey" style="left:96px;top:560px;font-size:36px;max-width:1500px" ${a('fade', { at: 2.2 })}>${esc(c.f('privateAdvice'))}. Until an authenticated decision exists, the affected work stays on hold.</div></div>`,
      },
    ],
  };
};
