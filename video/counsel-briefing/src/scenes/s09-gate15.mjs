import { a, esc, num, tag } from '../components.mjs';
import { titleBeat } from '../qcard.mjs';

export default (c) => {
  const qs = c.qs('15');
  const line = (q, i) =>
    `<div class="g15q" ${a('wipeX', { at: 0.15 + i * 0.5, dur: 0.5 })}>` +
    `<div class="qn pix">${esc(q.id)}</div><div class="qb"><div class="ql up b">${esc(q.label)}</div><div class="qt">${esc(q.text)}</div></div></div>`;

  const share = Number(c.f('beneficialOwners').replace(/,/g, '')) / Number(c.f('leafRemovals').replace(/,/g, ''));

  return {
    id: 's09-gate15',
    chapterId: 'gate-15',
    chapter: 'Gate 15',
    title: 'Gate 15: beneficial ownership',
    css: `
      .s09 .g15 { position: absolute; left: 96px; top: 140px; width: 1728px; display: flex; flex-direction: column; gap: 16px; }
      .s09 .g15q { position: relative; width: 1728px; min-height: 132px; background: var(--soft); color: #000; display: flex; }
      .s09 .g15q .qn { flex: none; width: 130px; background: var(--purple); color: #fff; font-size: 80px; display: flex; align-items: center; justify-content: center; }
      .s09 .g15q .qb { padding: 14px 30px 16px; }
      .s09 .g15q .ql { font-size: 30px; }
      .s09 .g15q .qt { font-size: 36px; line-height: 1.15; margin-top: 4px; }
      .s09 .track { position: absolute; left: 96px; top: 640px; width: 1500px; height: 44px; background: #1a1a1a; }
      .s09 .track i { display: block; height: 100%; background: var(--lilac); transform-origin: left center; }
    `,
    beats: [
      {
        say: `Gate 15 isn't drafted yet, and nothing is blocked on it. I'm listing it so the trade is visible.`,
        show: () =>
          titleBeat({
            kicker: 'Gate 15 · Beneficial ownership',
            big: 'Gate 15',
            sub: 'May we analyse it at all?',
            tags: [
              { text: 'Not yet drafted', kind: 'c' },
              { text: 'Not blocking anything', kind: 'k' },
              { text: 'Four open points', kind: 'k' },
            ],
            glyph: 'person',
          }),
      },
      {
        say: `Beneficial owners are natural people by definition. We drop the whole subtree: ${c.f('beneficialOwners')} of the ${c.f('leafRemovals')} leaf elements removed from one publication day.`,
        show: () =>
          `<div class="s09">` +
          `<div class="abs" style="left:96px;top:170px;font-size:240px">${num(c.f('beneficialOwners'), { at: 0.2 })}</div>` +
          `<div class="abs" style="left:100px;top:440px;font-size:42px;max-width:1300px" ${a('fade', { at: 1.4 })}>of ${esc(c.f('leafRemovals'))} leaf elements removed from one publication day are beneficial owners: identifiers, names, nationality, residence.</div>` +
          `<div class="track"><i style="width:${(share * 100).toFixed(2)}%" ${a('bar', { at: 2, dur: 0.8 })}></i></div>` +
          `<div class="abs" style="left:96px;top:710px">${tag('The whole subtree stays dropped', { kind: 'p', at: 3 })}</div>` +
          `</div>`,
      },
      {
        say: `Is any analysis available at all? Is a yes-or-no relation, two suppliers declaring an owner in common with no name stored, legally different from storing the owner?`,
        show: () => `<div class="s09"><div class="g15">${qs.slice(0, 2).map(line).join('')}</div></div>`,
      },
      {
        say: `May any of it be published? Does nationality change the risk? If the answer is no, I want it recorded as no.`,
        show: () =>
          `<div class="s09"><div class="g15">${qs
            .slice(0, 4)
            .map((q, i) => (i < 2 ? line(q, i).replace(/data-a="wipeX" data-at="[^"]*"/, 'data-a="cut" data-at="0.000"') : line({ ...q }, i).replace(/data-at="[^"]*"/, `data-at="${(0.2 + (i - 2) * 1.6).toFixed(3)}"`)))
            .join('')}</div>` +
          `<div class="abs" style="left:96px;top:800px">${tag('If no: record it as a decision', { kind: 'p', at: 4 })}</div></div>`,
      },
    ],
  };
};
