// The question card used by every gate: a rail on the left (gate, id, progress
// ticks) and a white label box on the right holding the question, in the style
// of the white callout boxes on the original infographic.

import { a, esc, tag, icon } from './components.mjs';

export const qcss = `
.qrail { position: absolute; left: 96px; top: 140px; width: 460px; }
.qrail .qgate { font-size: 28px; text-transform: uppercase; color: var(--grey); letter-spacing: .06em; }
.qrail .qid { font-size: 250px; line-height: 1.12; color: var(--soft); text-shadow: 9px 9px 0 var(--purple); margin: 22px 0 22px; }
.qrail .qticks { display: flex; flex-wrap: wrap; gap: 10px; width: 420px; }
.qrail .qticks i { display: block; width: 32px; height: 32px; border: 3px solid var(--soft); }
.qrail .qticks i.done { background: var(--soft); }
.qrail .qticks i.on { background: var(--lilac); border-color: var(--lilac); }
.qrail .qicon { margin-top: 40px; color: var(--lilac); }
.qcard { position: absolute; left: 600px; top: 150px; width: 1224px; min-height: 560px; padding: 40px 50px 110px; }
.qcard .qlabel { font-size: 46px; border-bottom: 4px solid #000; padding-bottom: 14px; margin-bottom: 26px; }
.qcard .qtext { font-size: 43px; line-height: 1.3; }
.qcard.nostakes { padding-bottom: 44px; }
.qcard.fig .qtext { font-size: 38px; }
.qcard .qfig { margin-top: 26px; }
.qcard .qstakes { position: absolute; left: 50px; right: 50px; bottom: 30px; display: flex; gap: 14px; flex-wrap: wrap; }
.qcard .qstakes .tag { font-size: 26px; }
`;

/**
 * One question. `stakes` are short tags saying what the answer changes; each is
 * taken from the "what each answer changes" tables in docs/counsel/.
 */
export function questionBeat({ gateLabel, q, index, total, glyph, stakes = [], figure = '' }) {
  const ticks = Array.from({ length: total }, (_, i) => `<i class="${i === index ? 'on' : i < index ? 'done' : ''}"></i>`).join('');
  const stakeHtml = stakes.length
    ? `<div class="qstakes">${stakes.map((s, i) => tag(s.text, { kind: s.kind ?? 'p', at: 1.3 + i * 0.35 })).join('')}</div>`
    : '';
  return (
    `<div class="qrail">` +
    `<div class="qgate" ${a('cut', { at: 0.05 })}>${esc(gateLabel)}</div>` +
    `<div class="qid pix" ${a('pop', { at: 0.1 })}>${esc(q.id)}</div>` +
    `<div class="qticks" ${a('cut', { at: 0.3 })}>${ticks}</div>` +
    (glyph ? `<div class="qicon" ${a('pop', { at: 0.5 })}>${icon(glyph, { px: 120, color: 'currentColor' })}</div>` : '') +
    `</div>` +
    `<div class="qcard box ${stakes.length ? '' : 'nostakes'} ${figure ? 'fig' : ''}" ${a('wipeX', { at: 0.15, dur: 0.5 })}>` +
    `<div class="qlabel up b" ${a('cut', { at: 0.6 })}>${esc(q.label)}</div>` +
    `<div class="qtext" ${a('fade', { at: 0.75, dur: 0.5 })}>${esc(q.text)}</div>` +
    (figure ? `<div class="qfig">${figure}</div>` : '') +
    stakeHtml +
    `</div>`
  );
}

/** A full-width title card that opens a gate or a part. */
export function titleBeat({ kicker, big, sub, tags = [], glyph }) {
  return (
    `<div class="abs" style="left:96px;top:150px;width:1300px">` +
    `<div class="grey up" style="font-size:32px;letter-spacing:.08em" ${a('cut', { at: 0.1 })}>${esc(kicker)}</div>` +
    `<div class="pix" style="font-size:210px;margin:18px 0 22px;color:var(--soft);text-shadow:9px 9px 0 var(--purple)" ${a('wipeX', { at: 0.25, dur: 0.6 })}>${esc(big)}</div>` +
    `<div class="up b" style="font-size:52px;line-height:1.15;max-width:1250px" ${a('up', { at: 0.8 })}>${esc(sub)}</div>` +
    `</div>` +
    `<div class="abs" style="left:96px;top:700px;display:flex;gap:16px;flex-wrap:wrap;width:1500px">` +
    tags.map((t, i) => tag(t.text, { kind: t.kind ?? '', at: 1.2 + i * 0.3 })).join('') +
    `</div>` +
    (glyph
      ? `<div class="abs" style="right:120px;top:190px;color:var(--lilac)" ${a('pop', { at: 0.9 })}>${icon(glyph, { px: 300 })}</div>`
      : '')
  );
}
