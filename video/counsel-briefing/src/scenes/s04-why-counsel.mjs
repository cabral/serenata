import { a, esc, icon, tag } from '../components.mjs';

const COLS = [
  {
    head: 'Code decides',
    kind: '',
    x: 96,
    lines: ['Which paths to drop', 'That a run repeats byte for byte', 'That tests pass on fixtures'],
  },
  {
    head: 'I decide',
    kind: '',
    x: 680,
    lines: ['What to build next', 'What the README says', 'Whether to ask'],
  },
  {
    head: 'Only counsel decides',
    kind: 'p',
    x: 1264,
    lines: [
      'The lawful basis',
      'How long we may keep it',
      'Whether a link is a name: GDPR, förtal',
      'Whether an immutable archive can yield to erasure',
      'Whether "the authority published it" is enough by itself',
    ],
  },
];

export default (c) => {
  const col = (i, from = 0) =>
    `<div class="wc" style="left:${COLS[i].x}px" data-stagger="0.55" data-at="${from}">` +
    COLS[i].lines.map((l) => `<div class="wl ${i === 2 ? 'hot' : ''}" data-a="left" data-dur="0.4">${esc(l)}</div>`).join('') +
    `</div>`;
  const head = (i, at) =>
    `<div class="wh" style="left:${COLS[i].x}px" ${a('wipeX', { at, dur: 0.5 })}>` +
    `<span class="tag ${COLS[i].kind}">${esc(COLS[i].head)}</span></div>`;

  const beats = [
    {
      say: `Tests can show that a rule drops the paths it says it drops. They can't show that what remains is lawful to hold.`,
      show: () => `<div class="s04">${head(0, 0.2)}${col(0, 0.8)}</div>`,
      stay: false,
    },
    {
      say: `I can decide what to build next. I can't decide the lawful basis, how long to keep the data, or whether a link to a public notice counts as naming someone under GDPR and Swedish defamation law.`,
      show: () =>
        `<div class="s04">${head(0, 0)}${col(0, 0)}${head(1, 0.2)}${col(1, 0.8)}${head(2, 3.4)}${col(2, 4.2)}</div>`,
    },
    {
      say: `Publishing is blocked for four other reasons, so it can wait. Holding can't, because it's happening today. That is why I'm asking you to start with what we hold now.`,
      show: () =>
        `<div class="s04">` +
        `<div class="abs" style="right:96px;top:150px;color:var(--lilac)" ${a('pop', { at: 0.1 })}>${icon('clock', { px: 110 })}</div>` +
        `<div class="lane" style="top:170px"><div class="lbl">${tag('Holding', { at: 0.1, cls: 'big' })}</div>` +
        `<div class="track"><i class="bar hold" ${a('bar', { at: 0.4, dur: 2.6 })}></i></div>` +
        `<div class="note" ${a('fade', { at: 1.2 })}>Risk accrues every day the corpus is held. That is happening today.</div></div>` +
        `<div class="lane" style="top:500px"><div class="lbl">${tag('Publishing', { at: 3.2, cls: 'big' })}</div>` +
        `<div class="track"><i class="bar pub" ${a('bar', { at: 3.6, dur: 0.6 })}></i></div>` +
        `<div class="note" ${a('fade', { at: 4.2 })}>Risk accrues only at publication, and publication is blocked by ${esc(c.f('fourOtherBlocks'))} other open gates.</div>` +
        `<div class="nothing">${tag('Nothing published', { kind: 'c', at: 4.8 })}</div></div>` +
        `</div>`,
    },
  ];

  if (c.r.hasWhyYou) {
    beats.push({
      say: c.r.whyYou,
      show: () =>
        `<div class="s04"><div class="abs" style="left:96px;top:170px">${tag('Why you', { kind: 'p', at: 0.1, cls: 'big' })}</div>` +
        `<div class="box abs" style="left:96px;top:290px;width:1500px;font-size:46px;line-height:1.3" ${a('wipeX', { at: 0.4, dur: 0.6 })}>${esc(c.r.whyYou)}</div></div>`,
    });
  }

  return {
    id: 's04-why-counsel',
    chapterId: 'why',
    chapter: 'Why counsel',
    title: 'Why counsel',
    css: `
      .s04 .wh { position: absolute; top: 150px; }
      .s04 .wc { position: absolute; top: 250px; width: 540px; }
      .s04 .wl { font-size: 35px; line-height: 1.2; padding: 14px 0 14px 18px; border-left: 6px solid var(--rule); margin-bottom: 14px; }
      .s04 .wl.hot { border-left-color: var(--lilac); }
      .s04 .wh .tag { font-size: 40px; }
      .s04 .lane { position: absolute; left: 96px; width: 1728px; }
      .s04 .lane .lbl { margin-bottom: 16px; }
      .s04 .lane .nothing { position: absolute; right: 0; top: 4px; }
      .s04 .track { height: 74px; background: #141414; }
      .s04 .bar { display: block; height: 100%; }
      .s04 .bar.hold { width: 100%; background: var(--coral); }
      .s04 .bar.pub { width: 6%; margin-left: 94%; background: var(--soft); }
      .s04 .note { margin-top: 18px; font-size: 36px; max-width: 1200px; }
    `,
    beats,
  };
};
