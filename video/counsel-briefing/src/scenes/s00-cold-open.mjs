import { a, cursor, tag, typed } from '../components.mjs';
import { stripes } from '../components.mjs';

export default (c) => ({
  id: 's00-cold-open',
  chapterId: 'intro',
  chapter: 'Intro',
  title: 'Cold open',
  css: `
    .s00-tags { position: absolute; left: 96px; top: 800px; display: flex; gap: 14px; flex-wrap: wrap; width: 1700px; }
    .s00-tags .tag { font-size: 26px; }
  `,
  layer: () =>
    `<svg class="abs" style="left:0;top:0" width="1920" height="1080" viewBox="0 0 1920 1080" aria-hidden="true">` +
    `<path d="M0 860L300 740L640 790L940 620L1260 670L1580 430L1920 310" fill="none" stroke="var(--purple)" ` +
    `stroke-width="16" pathLength="1" stroke-dasharray="1" ${a('draw', { at: 0.3, dur: 4.5 })}/></svg>` +
    `<div class="abs" style="right:96px;top:640px;color:var(--soft)">${stripes({ count: 5, h: 230, w: 10, gap: 16, at: 0.6 })}</div>`,
  beats: [
    {
      say: `${c.r.greeting} I'm Felipe Cabral. I'm building an open pipeline that reads public procurement notices from across the EU.`,
      show: (t) =>
        `<div class="abs" style="left:96px;top:340px;font:700 150px/1 var(--mono)">` +
        `${typed('WHAT MAY WE KEEP?', { at: 0.4, cps: 14 })}${cursor({ at: 0.4, until: t.dur })}</div>`,
    },
    {
      say: `It holds data I'm not sure I'm allowed to keep, and tests can't settle that.`,
      stay: true,
      show: (t) =>
        `<div class="abs wordmark" style="left:96px;top:170px;font-size:250px">` +
        `<div ${a('wipeX', { at: 0.1, dur: 0.6 })}>Serenata</div>` +
        `<div ${a('wipeX', { at: 0.45, dur: 0.6 })}>Europa${cursor({ at: 1.1, until: t.sceneLeft })}</div></div>` +
        `<div class="abs" style="left:100px;top:700px;font-size:46px">${tag('Briefing for counsel', { at: 1.2, cls: 'big' })}</div>`,
    },
    {
      say: `This video is the full list of what I need from a lawyer, and what each answer changes.`,
      stay: true,
      show: () =>
        `<div class="s00-tags">` +
        ['What we hold', 'Why counsel', 'Gate 11', 'Gate 14', 'Gate 15', 'Your answers']
          .map((label, i) => tag(label, { kind: 'k', at: 0.3 + i * 0.35, anim: 'cut' }))
          .join('') +
        `</div>`,
    },
  ],
});
