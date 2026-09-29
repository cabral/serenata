import { a, esc, icon } from '../components.mjs';

const RULES = [
  {
    n: '01',
    title: 'No personal data',
    body: 'Dropped at ingestion, not stored and filtered later.',
    glyph: 'person',
  },
  {
    n: '02',
    title: 'Anomalies, not accusations',
    body: 'Every flag names possible innocent explanations and links to its source notice.',
    glyph: 'flag',
  },
  {
    n: '03',
    title: 'Same input, same bytes',
    body: 'No clock, no randomness, no network after fetch.',
    glyph: 'stack',
  },
];

const card = (r, i) =>
  `<div class="rule" style="left:${96 + i * 584}px" ${a('wipeY', { at: 0.1, dur: 0.6 })}>` +
  `<div class="rn pix">${r.n}</div>` +
  `<div class="ri">${icon(r.glyph, { px: 110, color: '#000', accent: 'var(--purple)' })}</div>` +
  `<div class="rt b up">${esc(r.title)}</div>` +
  `<div class="rb">${esc(r.body)}</div></div>`;

export default (c) => ({
  id: 's02-rules',
  chapterId: 'intro',
  chapter: 'The rules',
  title: 'The rules',
  css: `
    .s02 .rule { position: absolute; top: 260px; width: 560px; height: 470px; background: var(--soft); color: #000; padding: 30px 34px; }
    .s02 .rn { font-size: 74px; color: var(--purple); }
    .s02 .ri { position: absolute; right: 30px; top: 26px; }
    .s02 .rt { font-size: 46px; line-height: 1.08; margin: 44px 0 20px; }
    .s02 .rb { font-size: 35px; line-height: 1.25; }
    .s02 .six { position: absolute; left: 96px; top: 300px; width: 1500px; display: flex; flex-wrap: wrap; gap: 22px; }
    .s02 .band { position: absolute; left: 96px; top: 752px; width: 1728px; height: 112px; background: var(--purple); display: flex; align-items: center; justify-content: space-between; padding: 0 44px; }
  `,
  layer: () =>
    `<div class="s02"><div class="abs pix" style="left:96px;top:140px;font-size:74px" ${a('wipeX', { at: 0.2, dur: 0.6 })}>Six rules. Three matter here.</div></div>`,
  beats: [
    {
      say: `The project runs on six written rules. Three matter here.`,
      show: () =>
        `<div class="s02"><div class="six" data-stagger="0.35" data-at="0.8">` +
        [
          ['AGPL-3.0 licence', 'k'],
          ['No personal data', ''],
          ['Anomalies, not accusations', ''],
          ['Same input, same bytes', ''],
          ['Structured fields first', 'k'],
          ['Every classifier a documented hypothesis', 'k'],
        ]
          .map(([label, kind]) => `<span class="tag big ${kind}" data-a="cut">${esc(label)}</span>`)
          .join('') +
        `</div></div>`,
    },
    {
      say: `First, no personal data. Anything that could carry a person's name is dropped when the notice is read.`,
      stay: true,
      show: () => `<div class="s02">${card(RULES[0], 0)}</div>`,
    },
    {
      say: `Second, flags are anomalies, each with possible innocent explanations and a link to its source notice.`,
      stay: true,
      show: () => `<div class="s02">${card(RULES[1], 1)}</div>`,
    },
    {
      say: `Third, determinism: same input, same output, byte for byte.`,
      stay: true,
      show: () => `<div class="s02">${card(RULES[2], 2)}</div>`,
    },
    {
      say: `One line I'd like you to hold me to: the law decides what may be kept. My preferences don't.`,
      stay: true,
      show: () =>
        `<div class="s02"><div class="band" ${a('wipeX', { at: 0.1, dur: 0.6 })}>` +
        `<span class="pix" style="font-size:60px">${esc(c.f('lawDecides'))}</span>` +
        `<span style="font-size:28px;text-align:right;color:var(--soft)">Project rules,<br>constraint 2</span></div></div>`,
    },
  ],
});
