import { a, cursor, esc, typed } from '../components.mjs';

export default (c) => ({
  id: 's12-close',
  chapterId: 'answers',
  chapter: 'Until then',
  title: 'Close',
  css: `
    .s12 .ln { position: absolute; left: 96px; font: 700 100px/1 var(--mono); text-transform: uppercase; }
    .s12 .disc { position: absolute; left: 96px; width: 1728px; padding: 18px 30px; font-size: 32px; line-height: 1.25; }
  `,
  beats: [
    {
      say: `Until you answer, nothing is published, the drop list stands, and nothing widens what we store.`,
      show: (t) =>
        `<div class="s12">` +
        `<div class="ln" style="top:230px">${typed('> Nothing is published', { at: 0.4, cps: 22 })}</div>` +
        `<div class="ln" style="top:380px">${typed('> The drop list stands', { at: 2.2, cps: 22 })}</div>` +
        `<div class="ln" style="top:530px">${typed('> Nothing widens what is stored', { at: 4, cps: 22 })}${cursor({ at: 4, until: t.dur })}</div></div>`,
    },
    {
      say: `Everything here is written down in the repository's counsel folder, with the numbers and their sources. These are questionnaires, not legal advice, and they authorise nothing until you answer and I record the decision. Thank you.`,
      show: (t) =>
        `<div class="s12">` +
        `<div class="abs wordmark" style="left:96px;top:150px;font-size:150px;line-height:.95" ${a('wipeX', { at: 0.1, dur: 0.6 })}>Serenata Europa${cursor({ at: 0.9, until: t.dur })}</div>` +
        `<div class="abs" style="left:100px;top:330px;font-size:44px" ${a('fade', { at: 0.9 })}>github.com/cabral/serenata &nbsp; docs/counsel/</div>` +
        `<div class="disc box" style="top:460px" ${a('wipeX', { at: 1.4, dur: 0.5 })}><b class="up">Questionnaires, not legal advice, and not authorization.</b> A completed instruction becomes authority only when counsel has answered it and an authorized human has recorded the decision.</div>` +
        `<div class="disc box p" style="top:620px" ${a('wipeX', { at: 2.2, dur: 0.5 })}>Independent project. Not affiliated with, endorsed by, or run by Open Knowledge Brasil.</div>` +
        `<div class="abs grey" style="left:100px;top:775px;font-size:30px;max-width:1600px" ${a('fade', { at: 3 })}>Notice data: © European Union, source TED (ted.europa.eu), reused under Commission Decision 2011/833/EU. Code: AGPL-3.0. Findings and datasets: CC BY 4.0.</div></div>`,
    },
  ],
});
