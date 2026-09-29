import { a, esc, icon } from '../components.mjs';
import { qcss, questionBeat, titleBeat } from '../qcard.mjs';

// [column, key of the fact holding its address-shaped count, values shaped like a person's own].
// The person-shaped counts are the second number in the same table rows the
// facts cite, so the build's fact check covers both.
const COLUMNS = [
  ['lot.description', 'colLotDescription', 77],
  ['procedure.description', 'colProcedureDescription', 45],
  ['organisation.street', 'colStreet', 6],
  ['organisation.website', 'colWebsite', 5],
  ['organisation.company_ids', 'colCompanyIds', 4],
  ['organisation.name', 'colName', 1],
  ['organisation.city', 'colCity', 1],
];

const OPTIONS = [
  {
    n: '1',
    name: 'Reject the value',
    body: 'Store a status saying we suppressed it. Cost: a city name is lost when a publisher put an address in it.',
  },
  {
    n: '2',
    name: 'Redact the match',
    body: 'Keep the text, remove the address. Cost: the dataset holds rewritten source text, and a missed variant stays in.',
  },
  {
    n: '3',
    name: 'Hold for review',
    body: 'A person looks at each row. Cost: 427 is a small share and a large queue, and it does not scale.',
  },
  {
    n: '4',
    name: 'Drop the two description columns',
    body: 'By path. No pattern, no judgement about a value. Removes 359 of the 427. Cost: free text we do not read.',
  },
];

const SAY = {
  A1: `A1. Is holding these values acceptable while a rule is pending, and for how long?`,
  A2: `A2. For values already held: delete, rebuild, or something else? And how does the immutable raw archive yield?`,
  A3: `A3. May I scan for telephone-shaped strings, counts only, to size the problem?`,
  A4: `A4. Do Articles 14 and 35 change because these values are incidental?`,
  B1: `B1. Which option is adequate, or which combination?`,
  B2: `B2. If it's a pattern, is an email-shaped one enough when it misses names and phone numbers?`,
  B3: `B3. Does dropping a column change the linkability analysis?`,
  B4: `B4. Is suppressing what a public authority published a matter of law, or of my preference? My rules say the law decides. I'm asking for the law.`,
};

const GLYPH = { A1: 'stack', A2: 'trash', A3: 'mail', A4: 'doc', B1: 'grid', B2: 'brackets', B3: 'flag', B4: 'scales' };

const STAKES = {
  A2: [{ text: 'If rebuild or delete: every measurement is redone', kind: 'c' }],
  A3: [{ text: 'If refused: 427 stays a lower bound', kind: 'k' }],
  B1: [
    { text: 'Option 4: two paths join the drop list', kind: 'p' },
    { text: 'Two model columns removed, dataset rebuilt', kind: 'k' },
  ],
};

export default (c) => {
  const values = COLUMNS.map(([name, key, person]) => ({ name, total: Number(c.f(key)), person }));
  const sumTotal = values.reduce((n, v) => n + v.total, 0);
  const sumPerson = values.reduce((n, v) => n + v.person, 0);
  if (sumTotal !== Number(c.f('addressShaped'))) throw new Error(`column counts sum to ${sumTotal}, not ${c.f('addressShaped')}`);
  if (sumPerson !== Number(c.f('personShaped'))) throw new Error(`person-shaped counts sum to ${sumPerson}, not ${c.f('personShaped')}`);
  if (values[0].total + values[1].total !== Number(c.f('inDescriptions'))) throw new Error('description columns do not sum to the documented figure');

  const max = Math.max(...values.map((v) => v.total));
  const W = 560;
  const rows = values
    .map((v, i) => {
      const w = Math.round((v.total / max) * W);
      const wp = Math.round((v.person / max) * W);
      const desc = i < 2;
      return (
        `<div class="row" style="top:${i * 76}px">` +
        `<div class="nm ${desc ? 'lilac b' : ''}">${esc(v.name)}</div>` +
        `<div class="trk"><i class="bar tot ${desc ? 'd' : ''}" style="width:${w}px" ${a('bar', { at: 0.4 + i * 0.25, dur: 0.6 })}></i>` +
        `<i class="bar per" style="width:${Math.max(wp, 6)}px" ${a('bar', { at: 0.8 + i * 0.25, dur: 0.5 })}></i></div>` +
        `<div class="vl" ${a('cut', { at: 1 + i * 0.25 })}>${v.total}<span class="grey"> / ${v.person}</span></div></div>`
      );
    })
    .join('');

  const qs = c.qs('14');
  const rail = (q, i) => ({
    gateLabel: `Gate 14 · Part ${q.id[0]}`,
    q,
    index: i,
    total: qs.length,
    glyph: GLYPH[q.id],
    stakes: STAKES[q.id],
  });

  // Cards already shown come back instantly; the new one wipes in.
  const optionCard = (o, i, fresh) =>
    `<div class="opt ${i === 3 ? 'pick' : ''}" style="left:${96 + i * 436}px" ${fresh ? a('wipeY', { at: 0.15, dur: 0.55 }) : a('cut', { at: 0 })}>` +
    `<div class="on pix">${o.n}</div><div class="onm up b">${esc(o.name)}</div><div class="ob">${esc(o.body)}</div></div>`;

  const upTo = (k) => `<div class="s08">${OPTIONS.slice(0, k + 1).map((o, i) => optionCard(o, i, i === k)).join('')}</div>`;

  return {
    id: 's08-gate14',
    chapterId: 'gate-14',
    chapter: 'Gate 14',
    title: 'Gate 14: personal data where it should not be',
    css:
      qcss +
      `
      .s08 .chart { position: absolute; left: 96px; top: 170px; width: 1250px; height: 560px; }
      .s08 .row { position: absolute; left: 0; width: 1250px; height: 60px; }
      .s08 .nm { position: absolute; left: 0; top: 10px; font-size: 32px; width: 520px; }
      .s08 .trk { position: absolute; left: 540px; top: 8px; height: 44px; width: 570px; }
      .s08 .trk .bar { position: absolute; left: 0; top: 0; height: 44px; }
      .s08 .trk .tot { background: var(--soft); }
      .s08 .trk .tot.d { background: var(--lilac); }
      .s08 .trk .per { background: var(--coral); height: 22px; top: 11px; }
      .s08 .vl { position: absolute; left: 1120px; top: 8px; font-size: 36px; font-weight: 700; white-space: nowrap; }
      .s08 .vh { position: absolute; left: 96px; top: 128px; width: 1250px; font-size: 26px; color: var(--grey); text-transform: uppercase; letter-spacing: .04em; }
      .s08 .vh span { position: absolute; }
      .s08 .side { position: absolute; left: 1400px; top: 170px; width: 424px; }
      .s08 .side .sn { font-size: 120px; }
      .s08 .side .sl { font-size: 32px; margin: 6px 0 30px; }
      .s08 .legend { position: absolute; left: 96px; top: 760px; display: flex; gap: 14px; flex-wrap: wrap; width: 1300px; }
      .s08 .opt { position: absolute; top: 160px; width: 412px; height: 620px; background: var(--soft); color: #000; padding: 28px 30px; }
      .s08 .opt.pick { background: var(--purple); color: #fff; }
      .s08 .opt .on { font-size: 84px; color: var(--purple); }
      .s08 .opt.pick .on { color: var(--lilac); }
      .s08 .opt .onm { font-size: 40px; line-height: 1.1; margin: 24px 0 18px; }
      .s08 .opt .ob { font-size: 33px; line-height: 1.26; }
      .s08 .path { position: absolute; left: 96px; width: 780px; padding: 26px 34px; }
      .s08 .path .pt { font-size: 28px; opacity: .7; }
      .s08 .path .pv { font-size: 46px; font-weight: 700; margin-top: 6px; }
      .s08 .path .ps { font-size: 32px; margin-top: 8px; }
    `,
    beats: [
      {
        say: `Gate 14 is a different problem. Our drop list works by element path, so it can't catch a publisher who types an email address into a description.`,
        show: (t) =>
          titleBeat({
            kicker: 'Gate 14 · Retained fields',
            big: 'Gate 14',
            sub: 'Personal data where it should not be',
            tags: [],
            glyph: 'mail',
          }) +
          `<div class="s08">` +
          `<div class="path box" style="top:640px" ${a('wipeX', { at: 1.4, dur: 0.5 })}><div class="pt up">Dropped by path</div><div class="pv">cac:Contact</div><div class="ps">Never reaches a record.</div></div>` +
          `<div class="path box p" style="top:640px;left:930px" ${a('wipeX', { at: 2.4, dur: 0.5 })}><div class="pt up">Retained, not a contact field</div><div class="pv">lot.description</div><div class="ps">A publisher can type anything here.</div></div>` +
          `</div>`,
      },
      {
        say: `Across five days, ${c.f('addressShaped')} values in seven retained columns look like email addresses. ${c.f('personShaped')} look like a person's own. ${c.f('inDescriptions')} sit in two free-text description columns that no classifier reads.`,
        show: () =>
          `<div class="s08"><div class="vh"><span style="left:0">Column</span><span style="left:1024px">Total / own</span></div><div class="chart">${rows}</div>` +
          `<div class="side">` +
          `<div class="sn pix" ${a('pop', { at: 0.6 })}>${esc(c.f('addressShaped'))}</div><div class="sl" ${a('fade', { at: 0.9 })}>address-shaped values, five days</div>` +
          `<div class="sn pix" style="color:var(--coral)" ${a('pop', { at: 1.6 })}>${esc(c.f('personShaped'))}</div><div class="sl" ${a('fade', { at: 1.9 })}>shaped like a person's own</div>` +
          `<div class="sn pix lilac" ${a('pop', { at: 2.6 })}>${esc(c.f('inDescriptions'))}</div><div class="sl" ${a('fade', { at: 2.9 })}>in the two description columns</div></div>` +
          `<div class="legend"><span class="tag" ${a('cut', { at: 3.4 })}>Total address-shaped</span><span class="tag c" ${a('cut', { at: 3.6 })}>Of which shaped like a person's own</span><span class="tag k" ${a('cut', { at: 3.8 })}>Pattern counts, not an inventory</span></div></div>`,
      },
      {
        say: `There are four options. Reject the value and record that we suppressed it.`,
        show: () => upTo(0),
      },
      {
        say: `Redact the match and keep the rest.`,
        show: () => upTo(1),
      },
      {
        say: `Hold the row for human review.`,
        show: () => upTo(2),
      },
      {
        say: `Or drop the two description columns by path, with no pattern and no judgement about a value. I think that fits best, and I'd like you to test it.`,
        show: () => upTo(3),
      },
      ...qs.map((q, i) => ({ say: SAY[q.id], show: () => questionBeat(rail(q, i)) })),
    ],
  };
};
