import { a, esc, icon, tag } from '../components.mjs';
import { qcss, questionBeat, titleBeat } from '../qcard.mjs';

const SAY = {
  B1: `B1. May a flag point at a notice when the natural-person status of the organisations in it is unknown?`,
  B3: `B3. Sole traders win public contracts, so for suppliers I propose holding everything until entity resolution exists. Is anything short of a register lookup acceptable?`,
  B4: `B4. A flag carries a bid count, a market baseline and a link to the notice on TED. The notice names the buyer. Is linking different from naming, under GDPR and Swedish förtal?`,
  B5: `B5. Small aggregate cells can point at one notice by elimination. Our floor of 50 is statistical. Do we need an identifiability floor too?`,
  B6: `B6. If one organisation carries two contradictory indicators, I propose treating it as a natural person. Is erring toward suppression right?`,
};

const box = (label, lines, { at, dark = false } = {}) =>
  `<div class="fbox ${dark ? 'dk' : ''}" ${a('wipeY', { at, dur: 0.5 })}>` +
  `<div class="fh up b">${esc(label)}</div>` +
  lines.map((l) => `<div class="fl">${esc(l)}</div>`).join('') +
  `</div>`;

// Question cards render outside the scene's own wrapper, so scope them here.
const scoped = (html) => `<div class="s07">${html}</div>`;

export default (c) => {
  const qs = c.qs('11').filter((q) => q.id.startsWith('B'));
  const q = Object.fromEntries(qs.map((x) => [x.id, x]));
  const rail = (id, glyph) => ({ gateLabel: 'Gate 11 · Part B', q: q[id], index: qs.findIndex((x) => x.id === id), total: qs.length, glyph });

  // B4: what we publish against what the authority already published.
  const linkFigure =
    `<div class="lk">` +
    box('Our flag', ['bid count', 'market baseline', 'URL'], { at: 1.6 }) +
    `<div class="lka" ${a('cut', { at: 2.4 })}>${icon('arrow', { px: 64 })}</div>` +
    box('The notice on TED', ['names the buyer', 'carries contact details we drop'], { at: 2.0, dark: true }) +
    `</div>` +
    `<div class="lkn" ${a('fade', { at: 2.8 })}>${tag('No organisation reference of any kind', { kind: 'p' })}</div>`;

  // B5: a small cell points at one notice.
  const cells =
    `<div class="cells">` +
    [120, 120, 120, 84, 120, 120, 44, 120]
      .map((s, i) => `<i style="width:${s}px;height:${s}px" class="${s === 44 ? 'hot' : ''}" ${a('pop', { at: 1.6 + i * 0.1, dur: 0.25 })}></i>`)
      .join('') +
    `</div>` +
    `<div class="lkn" ${a('fade', { at: 2.8 })}>A small cell points at one notice.</div>`;

  return {
    id: 's07-gate11-part-b',
    chapterId: 'gate-11',
    chapter: 'Gate 11 · Part B',
    title: 'Gate 11, part B: may a flag point at such a record?',
    css:
      qcss +
      `
      .s07 .fbox { width: 430px; background: var(--soft); color: #000; padding: 20px 24px; border: 4px solid #000; }
      .s07 .fbox.dk { background: #000; color: var(--soft); border-color: #000; outline: 4px solid #000; }
      .s07 .fh { font-size: 30px; margin-bottom: 8px; }
      .s07 .fl { font-size: 32px; padding: 6px 0; border-top: 3px solid currentColor; }
      .s07 .lk { display: flex; align-items: center; gap: 22px; }
      .s07 .lka { color: var(--purple); }
      .s07 .lkn { margin-top: 20px; font-size: 32px; }
      .s07 .cells { display: flex; align-items: flex-end; gap: 18px; height: 130px; }
      .s07 .cells i { display: block; background: #000; }
      .s07 .cells i.hot { background: var(--coral); }
      .s07 .def { position: absolute; left: 600px; top: 140px; width: 1224px; padding: 26px 46px; }
      .s07 .def .dh { font-size: 36px; margin-bottom: 14px; }
      .s07 .def ul { list-style: none; display: grid; grid-template-columns: repeat(4, 1fr); gap: 0 22px; font-size: 30px; line-height: 1.2; }
      .s07 .def li { padding: 8px 0 4px; border-top: 3px solid #000; }
      .s07 .def .src { margin-top: 12px; font-size: 28px; color: #444; }
      .s07 .def .ask { margin-top: 16px; padding-top: 14px; border-top: 4px solid #000; font-size: 31px; line-height: 1.25; font-weight: 700; }
      .s07 .exc { position: absolute; top: 620px; width: 396px; height: 250px; outline: 4px dashed var(--soft); outline-offset: -4px; padding: 20px 26px; }
      .s07 .exc .eh { font-size: 32px; line-height: 1.1; }
      .s07 .exc .es { font-size: 24px; margin-top: 12px; color: var(--grey); line-height: 1.25; }
      .s07 .exc .eq { position: absolute; right: 18px; top: 16px; color: var(--coral); }
      .s07 .lane2 { position: absolute; left: 600px; width: 1224px; height: 200px; padding: 26px 40px; }
      .s07 .lane2 .lt { font-size: 40px; }
      .s07 .lane2 .ls { font-size: 32px; margin-top: 8px; }
      .s07 .lane2 .li { position: absolute; right: 36px; top: 30px; }
    `,
    beats: [
      {
        say: `Part B is publication. Without an answer, our default is no.`,
        show: () =>
          titleBeat({
            kicker: 'Gate 11 · Unknown natural-person status',
            big: 'Part B',
            sub: 'May a flag point at such a record?',
            tags: [
              { text: 'Default without an answer: no', kind: 'c' },
              { text: 'Six questions', kind: 'k' },
              { text: 'Can wait for Part A', kind: 'k' },
            ],
            glyph: 'lock',
          }),
      },
      { say: SAY.B1, show: () => scoped(questionBeat({ ...rail('B1', 'flag') })) },
      {
        say: `B2. A buyer is a contracting authority: the State, local authorities, bodies governed by public law, or associations of them. I propose that can't include a natural person. Please scope three exceptions: utilities, subsidised contracts and voluntary notices.`,
        show: (t) =>
          `<div class="s07">` +
          `<div class="qrail"><div class="qgate">Gate 11 · Part B</div><div class="qid pix">B2</div>` +
          `<div class="qticks">${qs.map((x, i) => `<i class="${i === 1 ? 'on' : i < 1 ? 'done' : ''}"></i>`).join('')}</div></div>` +
          `<div class="def box" ${a('wipeX', { at: 0.15, dur: 0.5 })}>` +
          `<div class="dh up b">A buyer is a contracting authority</div>` +
          `<ul data-stagger="${(t.dur * 0.06).toFixed(2)}" data-at="${(t.dur * 0.27).toFixed(2)}">` +
          ['The State', 'Regional or local authorities', 'Bodies governed by public law', 'Associations of these']
            .map((t) => `<li data-a="cut">${esc(t)}</li>`)
            .join('') +
          `</ul><div class="src">${esc(c.f('directive'))}</div>` +
          `<div class="ask" ${a('fade', { at: t.dur * 0.62, dur: 0.5 })}>${esc(q.B2.text)}</div></div>` +
          [
            { x: 600, h: 'Utilities', s: `${c.f('directiveUtilities')}: holders of special or exclusive rights`, at: t.dur * 0.72 },
            { x: 1016, h: 'Subsidised contracts', s: `${c.f('directiveSubsidised')}: bodies that are not contracting authorities`, at: t.dur * 0.72 + t.dur * 0.085 },
            { x: 1432, h: 'Voluntary notices', s: 'Published below threshold: no definitional floor', at: t.dur * 0.72 + t.dur * 0.17 },
          ]
            .map(
              (e) =>
                `<div class="exc" style="left:${e.x}px" ${a('pop', { at: e.at })}>` +
                `<div class="eq">${icon('question', { px: 64, color: 'var(--coral)' })}</div>` +
                `<div class="eh up b">${esc(e.h)}</div><div class="es">${esc(e.s)}</div></div>`,
            )
            .join('') +
          `</div>`,
      },
      {
        say: `That clears the entity question only, not the personal data in retained fields.`,
        show: () =>
          `<div class="s07">` +
          `<div class="qrail"><div class="qgate">Gate 11 · Part B</div><div class="qid pix">B2</div><div class="qgate" style="color:var(--soft);font-size:32px">Continued</div></div>` +
          `<div class="lane2 box" style="top:150px" ${a('wipeX', { at: 0.15, dur: 0.5 })}>` +
          `<div class="lt up b">The entity question</div><div class="ls">Is the buyer a legal person? B2 answers this.</div>` +
          `<div class="li">${icon('check', { px: 100, color: '#000' })}</div></div>` +
          `<div class="lane2 box p" style="top:390px" ${a('wipeX', { at: 0.6, dur: 0.5 })}>` +
          `<div class="lt up b">The stored row</div><div class="ls">Retained fields can still hold personal data. That is gate 14.</div>` +
          `<div class="li">${icon('question', { px: 100, color: '#fff' })}</div></div>` +
          `<div class="abs" style="left:600px;top:640px;display:flex;gap:14px;flex-wrap:wrap;width:1224px">` +
          tag('If accepted: 96 flags publishable, subject to every other gate', { kind: 'p', at: 1.4 }) +
          tag('If refused: aggregate data notes only', { kind: 'c', at: 1.8 }) +
          `</div></div>`,
      },
      { say: SAY.B3, show: () => scoped(questionBeat({ ...rail('B3', 'briefcase'), stakes: [{ text: 'Costs nothing today: no supplier classifier exists', kind: 'k' }] })) },
      { say: SAY.B4, show: () => scoped(questionBeat({ ...rail('B4', 'doc'), figure: linkFigure })) },
      {
        say: SAY.B5,
        show: () => scoped(questionBeat({ ...rail('B5', 'stack'), figure: cells, stakes: [{ text: 'If answered: a minimum cell size enters the code', kind: 'p' }] })),
      },
      {
        say: SAY.B6,
        show: () => scoped(questionBeat({ ...rail('B6', 'person'), stakes: [{ text: 'If confirmed: a parse-stage fix, synthetic tests only', kind: 'k' }] })),
      },
    ],
  };
};
