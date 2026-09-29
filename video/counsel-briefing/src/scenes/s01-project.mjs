import { a, esc, icon, num, tag } from '../components.mjs';

const STAGES = [
  { name: 'Fetch', glyph: 'download' },
  { name: 'Parse', glyph: 'brackets' },
  { name: 'Normalise', glyph: 'grid' },
  { name: 'Classify', glyph: 'flag' },
  { name: 'Publish', glyph: 'globe' },
];

export default (c) => ({
  id: 's01-project',
  chapterId: 'intro',
  chapter: 'The project',
  title: 'The project',
  css: `
    .s01 .docs { position: absolute; left: 1120px; top: 170px; display: grid; grid-template-columns: repeat(6, 96px); gap: 22px; color: var(--soft); }
    .s01 .stage { position: absolute; top: 200px; width: 280px; height: 320px; background: var(--soft); color: #000; padding: 26px 0 0; text-align: center; }
    .s01 .stage .ico { margin: 0 auto 18px; }
    .s01 .stage .nm { font: 700 46px/1 var(--pix); text-transform: uppercase; }
    .s01 .arrow { position: absolute; top: 320px; color: var(--lilac); }
    .s01 .stat { position: absolute; top: 170px; font-size: 170px; line-height: 1; }
    .s01 .stat .rule { height: 6px; background: var(--soft); margin-bottom: 26px; transform-origin: left center; }
    .s01 .stat .lbl { margin-top: 28px; font-size: 30px; line-height: 1.1; }
    .s01 .stat .dsc { margin-top: 22px; font-size: 34px; line-height: 1.25; color: var(--grey); }
    .s01 .card { position: absolute; background: var(--soft); color: #000; padding: 34px 40px; }
    .s01 .field { display: flex; justify-content: space-between; border-bottom: 3px solid #000; padding: 14px 0 8px; font-size: 38px; }
    .s01 .field:last-child { border-bottom: 0; }
  `,
  beats: [
    {
      say: `TED, the EU's procurement journal, publishes around ${c.f('tedPerYear')} notices a year, in a machine-readable format called eForms since late 2024.`,
      show: () =>
        `<div class="s01">` +
        `<div class="abs" style="left:96px;top:190px;font-size:222px">${num(c.f('tedPerYear'), { at: 0.2, step: 0.12 })}</div>` +
        `<div class="abs" style="left:100px;top:450px">${tag('Notices a year on TED', { at: 1.4, cls: 'big' })}</div>` +
        `<div class="abs" style="left:100px;top:560px;font-size:40px;max-width:900px" ${a('fade', { at: 1.9 })}>Machine-readable eForms since late 2024. Older notices use legacy TED schemas.</div>` +
        `<div class="docs" data-stagger="0.06" data-at="0.8">` +
        Array.from({ length: 18 }, () => `<div ${a('pop', { dur: 0.25 })}>${icon('doc', { px: 96 })}</div>`).join('') +
        `</div></div>`,
    },
    {
      say: `The pipeline has five stages. Only the first touches the network, and it keeps the raw XML exactly as fetched.`,
      show: () => {
        const x = (i) => 96 + i * 362;
        return (
          `<div class="s01">` +
          STAGES.map(
            (s, i) =>
              `<div class="stage" style="left:${x(i)}px" ${a('wipeY', { at: 0.15 + i * 0.28, dur: 0.45 })}>` +
              `${icon(s.glyph, { px: 150, color: '#000', accent: 'var(--purple)' })}<div class="nm">${s.name}</div></div>` +
              (i < 4 ? `<div class="arrow" style="left:${x(i) + 296}px" ${a('cut', { at: 0.5 + i * 0.28 })}>${icon('arrow', { px: 52 })}</div>` : ''),
          ).join('') +
          `<div class="abs" style="left:96px;top:570px;width:560px">` +
          `${tag('Only stage on the network', { kind: 'c', at: 1.9 })}` +
          `<div style="margin-top:18px;font-size:34px" ${a('fade', { at: 2.3 })}>Raw XML archived as fetched. Never edited afterwards.</div></div>` +
          `<div class="abs" style="left:${x(4)}px;top:570px">${tag('Nothing published', { kind: 'k', at: 3.4 })}</div>` +
          `<div class="abs" style="left:96px;top:760px;font-size:34px;color:var(--grey);max-width:1500px" ${a('fade', { at: 3 })}>Each stage runs and tests on its own. Every derived record keeps a reference back to its source notice.</div>` +
          `</div>`
        );
      },
    },
    {
      say: `So far it has read five publication days: ${c.f('notices')} notices, ${c.f('rows')} rows in twelve tables, identical bytes on every run.`,
      show: () =>
        `<div class="s01">` +
        `<div class="stat" style="left:96px;width:660px"><div class="rule" ${a('bar', { at: 0.1, dur: 0.6 })}></div>${num(c.f('notices'), { at: 0.3 })}<div class="lbl">${tag('Notices', { at: 1.3 })}</div><div class="dsc" ${a('fade', { at: 1.8 })}>All parsed. Anything unreadable is reported.</div></div>` +
        `<div class="stat" style="left:800px;width:780px"><div class="rule" ${a('bar', { at: 0.2, dur: 0.6 })}></div>${num(c.f('rows'), { at: 0.6 })}<div class="lbl">${tag('Rows', { at: 1.6 })}</div><div class="dsc" ${a('fade', { at: 2.1 })}>Parquet files, queried with DuckDB.</div></div>` +
        `<div class="stat" style="left:1620px;width:204px"><div class="rule" ${a('bar', { at: 0.3, dur: 0.6 })}></div>${num(c.f('tables'), { at: 0.9 })}<div class="lbl">${tag('Tables', { at: 1.9 })}</div><div class="dsc" ${a('fade', { at: 2.4 })}>One documented model.</div></div>` +
        `<div class="abs" style="left:96px;top:640px;display:flex;gap:16px;flex-wrap:wrap">${tag('Five publication days, March to September 2026', { kind: 'k', at: 2.8 })}${tag('Same input, same bytes', { kind: 'p', at: 3.2 })}</div>` +
        `</div>`,
    },
    {
      say: `One classifier found ${c.f('flags')} flags among ${c.f('lotOutcomes')} lot outcomes. A flag is a statistical anomaly with possible innocent explanations, linked to its source notice. None is published.`,
      show: () =>
        `<div class="s01">` +
        `<div class="abs" style="left:96px;top:150px;font-size:300px">${num(c.f('flags'), { at: 0.2 })}</div>` +
        `<div class="abs" style="left:100px;top:470px">${tag('Flags', { at: 1.2, cls: 'big' })}</div>` +
        `<div class="abs" style="left:100px;top:570px;font-size:40px" ${a('fade', { at: 1.5 })}>from ${esc(c.f('lotOutcomes'))} lot outcomes,<br>one rule, none published</div>` +
        `<div class="card" style="left:980px;top:160px;width:800px" ${a('wipeX', { at: 0.6, dur: 0.6 })}>` +
        `<div class="b up" style="font-size:34px;margin-bottom:8px">What a flag carries</div>` +
        `<div class="field"><span>bid count</span><span class="grey">value</span></div>` +
        `<div class="field"><span>market baseline</span><span class="grey">value</span></div>` +
        `<div class="field"><span>link to the notice on TED</span><span class="grey">URL</span></div>` +
        `<div style="margin-top:22px">${tag('Statistical anomaly, not an accusation', { kind: 'p', at: 2.4 })}</div>` +
        `</div></div>`,
    },
    {
      say: `It succeeds Operação Serenata de Amor, which I co-founded in Brazil in ${c.f('lineage')}. It is independent, with no affiliation to or endorsement from Open Knowledge Brasil.`,
      show: () =>
        `<div class="s01">` +
        `<div class="abs" style="left:96px;top:170px">${tag('Lineage', { kind: 'k', at: 0.1 })}</div>` +
        `<div class="abs pix" style="left:96px;top:260px;font-size:80px;width:1728px;white-space:nowrap" ${a('wipeX', { at: 0.3, dur: 0.6 })}>Operação Serenata de Amor, ${esc(c.f('lineage'))}</div>` +
        `<div class="abs pix" style="left:96px;top:420px;font-size:80px;width:1728px;white-space:nowrap;color:var(--lilac)" ${a('wipeX', { at: 0.9, dur: 0.6 })}>Serenata Europa, independent</div>` +
        `<div class="box p abs" style="left:96px;top:610px;width:1500px;font-size:36px" ${a('up', { at: 1.8 })}>Not affiliated with, endorsed by, or run by Open Knowledge Brasil.</div>` +
        `</div>`,
    },
  ],
});
