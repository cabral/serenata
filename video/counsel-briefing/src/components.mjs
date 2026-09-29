// Small building blocks shared by the scenes. Each returns an HTML string.
// Motion is declared on the element with data-a="<preset>" (see runtime.js);
// `at` is seconds from the start of the enclosing beat or scene layer.

export { icon } from './icons.mjs';

export const esc = (s) =>
  String(s)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');

const n = (v) => Number(v).toFixed(3);

/** Attribute string for a motion preset. */
export function a(preset, { at = 0, dur, ...rest } = {}) {
  let out = `data-a="${preset}" data-at="${n(at)}"`;
  if (dur !== undefined) out += ` data-dur="${n(dur)}"`;
  for (const [k, v] of Object.entries(rest)) out += ` data-${k}="${esc(v)}"`;
  return out;
}

/**
 * A number that rolls into place digit by digit, like an odometer. Only digits
 * move; separators and signs are static. Needs a monospaced face so columns line up.
 */
export function num(text, { at = 0, step = 0.09, dur = 0.9, cls = '' } = {}) {
  let i = 0;
  let out = '';
  for (const ch of String(text)) {
    if (/\d/.test(ch)) {
      const strip = '0123456789'
        .repeat(2)
        .split('')
        .map((d) => `<i>${d}</i>`)
        .join('');
      out +=
        `<span class="dg" data-layout-allow-overflow><span class="strip" ${a('roll', { at: at + i * step, dur, digit: ch })}>` +
        `${strip}</span></span>`;
      i += 1;
    } else {
      out += `<span class="ch">${esc(ch)}</span>`;
    }
  }
  return `<span class="num ${cls}" role="img" aria-label="${esc(text)}">${out}</span>`;
}

/** Text typed one character at a time. Monospaced face only: width is counted in `ch`. */
export function typed(text, { at = 0, cps = 24, cls = '' } = {}) {
  const chars = [...String(text)].length;
  return `<span class="typed ${cls}" style="--n:${chars}" ${a('type', { at, dur: chars / cps, n: chars })}>${esc(text)}</span>`;
}

/** A blinking underscore, as in "CEAP_" on the original infographic. */
export function cursor({ at = 0, until = 20, cls = '' } = {}) {
  return `<span class="cur ${cls}" data-layout-allow-overlap ${a('cursor', { at, dur: until })}>_</span>`;
}

/** A small label box. kind: '' (white), 'p' (purple), 'c' (coral), 'k' (outline). */
export function tag(text, { kind = '', at = 0, anim = 'pop', cls = '' } = {}) {
  return `<span class="tag ${kind} ${cls}" ${a(anim, { at })}>${esc(text)}</span>`;
}

/** Vertical rules in a group, the stripe motif from the infographic. */
export function stripes({ count = 5, h = 160, w = 8, gap = 10, cls = '', at = 0 } = {}) {
  let bars = '';
  for (let i = 0; i < count; i += 1) {
    bars += `<i style="width:${w}px;height:${h}px;margin-right:${gap}px" ${a('barY', { at: at + i * 0.06, dur: 0.3 })}></i>`;
  }
  return `<span class="stripes ${cls}">${bars}</span>`;
}

/** Split a sentence into caption-sized pieces at punctuation, at most `max` words each. */
export function chunk(sentence, max = 13) {
  const words = sentence.trim().split(/\s+/).filter(Boolean);
  const out = [];
  let cur = [];
  const flush = () => {
    if (cur.length) out.push(cur.join(' '));
    cur = [];
  };
  for (const w of words) {
    cur.push(w);
    const atBreak = /[,;:.?!]$/.test(w);
    if (cur.length >= max || (atBreak && cur.length >= 5)) flush();
  }
  flush();
  // Fold a tiny tail back into the previous piece.
  if (out.length > 1 && out[out.length - 1].split(' ').length < 3) {
    const tail = out.pop();
    out[out.length - 1] += ` ${tail}`;
  }
  return out;
}

export const words = (s) => s.trim().split(/\s+/).filter(Boolean).length;
