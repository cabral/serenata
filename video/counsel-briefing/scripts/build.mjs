#!/usr/bin/env node
// Generates the HyperFrames composition (index.html), the reviewable script
// (SCRIPT.md) and captions (out/captions.srt) from src/scenes/*.mjs.
//
//   node scripts/build.mjs                  full video -> index.html, SCRIPT.md, out/
//   node scripts/build.mjs --script-only    SCRIPT.md and captions only
//   node scripts/build.mjs --only=gate-11   one chapter -> chapter-gate-11.html
//   node scripts/build.mjs --no-captions    leave burned-in captions out
//
// Timing comes from the narration: a beat lasts as long as its sentence takes
// to say at direction.json pace.wordsPerSecond. If assets/vo/<scene-id>.wav
// (or .mp3/.m4a) exists, that scene is timed to the recording instead.

import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { esc, chunk, words } from '../src/components.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const REPO = path.resolve(ROOT, '..', '..');
const argv = process.argv.slice(2);
const has = (name) => argv.includes(`--${name}`);
const opt = (name) => argv.find((x) => x.startsWith(`--${name}=`))?.split('=').slice(1).join('=');

const WIDTH = 1920;
const HEIGHT = 1080;

const readJson = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), 'utf8'));
const norm = (s) => s.replace(/\s+/g, ' ');
const fix = (x) => Number(x.toFixed(3));

// ---- 1. Every number and question on screen must be in the docs ------------

function verify(facts, questions) {
  const cache = new Map();
  const doc = (p) => {
    if (!cache.has(p)) cache.set(p, norm(fs.readFileSync(path.join(REPO, p), 'utf8')));
    return cache.get(p);
  };
  const missing = [];
  for (const [key, f] of Object.entries(facts)) {
    if (!doc(f.doc).includes(norm(f.needle))) missing.push(`fact ${key} (${f.doc}): ${f.needle}`);
  }
  for (const [gate, d] of Object.entries(questions.gates)) {
    for (const q of d.questions) {
      if (!doc(d.doc).includes(norm(q.needle))) missing.push(`question ${gate}/${q.id} (${d.doc}): ${q.needle}`);
    }
  }
  if (missing.length) {
    console.error(
      'The video cites text that is no longer in the repository docs. Update facts.json or\n' +
        'questions.json to match the docs (or the docs, if they are wrong), then rebuild:\n  ' +
        missing.join('\n  '),
    );
    process.exit(1);
  }
}

const factsFile = readJson('facts.json').facts;
const questions = readJson('questions.json');
verify(factsFile, questions);

// ---- 2. Context handed to every scene ---------------------------------------

const direction = readJson('direction.json');
const localRecipient = path.join(ROOT, 'recipient.local.json');
const recipient = JSON.parse(
  fs.readFileSync(fs.existsSync(localRecipient) ? localRecipient : path.join(ROOT, 'recipient.example.json'), 'utf8'),
);

const ctx = {
  /** A displayed number or phrase, by key in facts.json. */
  f: (key) => {
    if (!factsFile[key]) throw new Error(`unknown fact: ${key}`);
    return factsFile[key].display;
  },
  /** Questions of one gate, in order. */
  qs: (gate) => questions.gates[gate].questions,
  gate: (gate) => questions.gates[gate],
  r: {
    greeting: recipient.name ? `Hello ${recipient.name}.` : 'Hello.',
    whyYou: recipient.whyYou || '',
    hasWhyYou: Boolean(recipient.whyYou),
  },
  dir: direction,
};

// ---- 3. Load scenes ----------------------------------------------------------

const sceneDir = path.join(ROOT, 'src', 'scenes');
const sceneFiles = fs
  .readdirSync(sceneDir)
  .filter((f) => f.endsWith('.mjs'))
  .sort();

let defs = [];
for (const file of sceneFiles) {
  const mod = await import(pathToFileURL(path.join(sceneDir, file)).href);
  const def = mod.default(ctx);
  defs.push({ ...def, file });
}
const only = opt('only');
const allChapters = [...new Set(defs.map((d) => d.chapterId))];
if (only) {
  if (!allChapters.includes(only)) {
    console.error(`unknown chapter "${only}". Chapters: ${allChapters.join(', ')}`);
    process.exit(1);
  }
  defs = defs.filter((d) => d.chapterId === only);
}

// ---- 4. Timing ----------------------------------------------------------------

function voiceFor(id) {
  for (const ext of ['wav', 'mp3', 'm4a']) {
    const file = path.join(ROOT, 'assets', 'vo', `${id}.${ext}`);
    if (!fs.existsSync(file)) continue;
    const probe = spawnSync(
      process.env.HYPERFRAMES_FFPROBE_PATH || 'ffprobe',
      ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', file],
      { encoding: 'utf8' },
    );
    const seconds = parseFloat(probe.stdout);
    if (!Number.isFinite(seconds)) {
      console.error(`could not read the length of ${file}; is ffprobe installed?`);
      process.exit(1);
    }
    return { file: path.relative(ROOT, file).split(path.sep).join('/'), seconds };
  }
  return null;
}

const { wordsPerSecond, leadIn, beatPad, tail } = direction.pace;

function plan(list) {
  let cursor = 0;
  return list.map((def) => {
    const vo = voiceFor(def.id);
    const lead = def.lead ?? leadIn;
    const totalWords = def.beats.reduce((n, b) => n + (b.say ? words(b.say) : 0), 0);
    let at = lead;
    const beats = def.beats.map((b) => {
      const w = b.say ? words(b.say) : 0;
      let dur;
      if (w && vo) dur = (vo.seconds * w) / totalWords;
      else if (w) dur = w / wordsPerSecond + beatPad;
      else dur = b.min ?? 2;
      dur = Math.max(dur, b.min ?? 0);
      // Boundaries are rounded once and shared, so a beat ends exactly where the
      // next begins: a millisecond of overlap can land on a frame and show two.
      const start = fix(at);
      at += dur;
      const beat = { ...b, words: w, rel: start, dur: fix(fix(at) - start) };
      return beat;
    });
    const dur = fix(Math.max(at + (def.tail ?? tail), def.min ?? 0));
    const scene = { ...def, vo, lead, start: fix(cursor), dur, beats };
    cursor += dur;
    return scene;
  });
}

const scenes = plan(defs);
const total = fix(scenes.reduce((n, s) => n + s.dur, 0));

// ---- 5. Emit the compositions ---------------------------------------------------
// The root holds only hosts. Every scene, the captions and the frame furniture
// are sub-compositions in compositions/. A scene file is timed relative to
// itself, so a chapter render reuses it at a different start.

const clock = (s) => {
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
};

const subFile = (id, style, body, script = '') => `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"></head>
<body>
<!-- Generated by scripts/build.mjs from src/. Edit the sources, not this file. -->
<template>
<style>
#${id} { position: absolute; inset: 0; }
${style}
</style>
<div id="${id}" data-composition-id="${id}" data-width="${WIDTH}" data-height="${HEIGHT}" data-t0="0">
${body}
</div>
${script ? `<script>${script}</script>` : ''}
</template>
</body>
</html>
`;

const runMotion = (id) => `window.__serenataMotion(document.getElementById(${JSON.stringify(id)}));`;

function sceneFile(s) {
  const layer = s.layer ? s.layer({ dur: s.dur, start: 0 }) : '';
  const beats = s.beats
    .map((b, i) => {
      const dur = b.stay ? fix(s.dur - b.rel) : b.dur;
      const inner = b.show ? b.show({ dur, sceneLeft: fix(s.dur - b.rel), start: b.rel, index: i }) : '';
      return (
        `<div id="${s.id}-b${String(i).padStart(2, '0')}" class="clip beat" data-start="${b.rel}" ` +
        `data-duration="${dur}" data-track-index="${2 + i}" data-t0="${b.rel}">${inner}</div>`
      );
    })
    .join('\n');
  const body =
    `<div class="cam" data-a="push" data-at="0" data-dur="${s.dur}">\n<div class="layer">${layer}</div>\n${beats}\n</div>\n` +
    `<div class="chap"><span class="tag k">${esc(s.chapter)}</span></div>`;
  return subFile(s.id, s.css || '', body, runMotion(s.id));
}

function captionClips(list) {
  const out = [];
  let n = 0;
  for (const s of list) {
    for (const b of s.beats) {
      if (!b.say) continue;
      const pieces = chunk(b.say);
      const wTotal = pieces.reduce((k, p) => k + words(p), 0);
      let t = fix(s.start + b.rel);
      let spent = 0;
      for (const p of pieces) {
        spent += words(p);
        const end = fix(s.start + b.rel + (b.dur * spent) / wTotal);
        out.push({ text: p, start: t, dur: fix(end - t), id: `cap-${String(n).padStart(3, '0')}` });
        n += 1;
        t = end;
      }
    }
  }
  return out;
}

const captions = captionClips(scenes);
const withCaptions = direction.captions !== false && !has('no-captions');

const captionsFile = () =>
  subFile(
    'captions',
    '',
    captions
      .map(
        (c) =>
          `<div id="${c.id}" class="clip caption-cue" data-start="${c.start}" data-duration="${c.dur}" data-track-index="1">` +
          `<div class="capbox"><span>${esc(c.text)}</span></div></div>`,
      )
      .join('\n'),
  );

const hudFile = () =>
  subFile(
    'hud',
    '',
    `<div class="hud-mark">Serenata Europa</div>\n<div class="hud-prog"><i data-a="grow" data-at="0" data-dur="${total}"></i></div>`,
    runMotion('hud'),
  );

const host = (id, src, start, dur, track, kind = '') =>
  `<div id="host-${id}" data-composition-id="${id}" data-composition-src="${src}" data-start="${start}" ` +
  `data-duration="${dur}" data-track-index="${track}" ${kind ? `data-track-kind="${kind}" ` : ''}` +
  `data-width="${WIDTH}" data-height="${HEIGHT}" data-no-timeline></div>`;

function rootPage(suffix) {
  const css = fs.readFileSync(path.join(ROOT, 'src', 'theme.css'), 'utf8');
  const runtime = fs.readFileSync(path.join(ROOT, 'src', 'runtime.js'), 'utf8');
  const hosts = [
    ...scenes.map((s) => host(s.id, `compositions/${s.id}.html`, s.start, s.dur, 1)),
    ...(withCaptions ? [host('captions', `compositions/captions${suffix}.html`, 0, total, 2, 'captions')] : []),
    host('hud', `compositions/hud${suffix}.html`, 0, total, 3),
    ...scenes.filter((s) => s.vo).map(
      (s) =>
        `<audio id="${s.id}-vo" src="${s.vo.file}" data-start="${fix(s.start + s.lead)}" ` +
        `data-duration="${fix(s.vo.seconds)}" data-track-index="40"></audio>`,
    ),
  ];
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=${WIDTH}, height=${HEIGHT}">
<title>Serenata Europa: briefing for counsel</title>
<!-- Generated by scripts/build.mjs from src/. Edit the sources, not this file. -->
<style>
${css}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="${total}" data-width="${WIDTH}" data-height="${HEIGHT}" data-no-timeline>
${hosts.join('\n')}
</div>
<script id="direction" type="application/json">${JSON.stringify(direction)}</script>
<script>
${runtime}
</script>
</body>
</html>
`;
}

// ---- 6. Script for reading and recording --------------------------------------

const decode = (s) =>
  s
    .replaceAll('&lt;', '<')
    .replaceAll('&gt;', '>')
    .replaceAll('&quot;', '"')
    .replaceAll('&#39;', "'")
    .replaceAll('&amp;', '&');

function screenText(html) {
  const text = html
    .replace(/<style[\s\S]*?<\/style>/g, ' ')
    .replace(/<svg[\s\S]*?<\/svg>/g, ' ')
    .replace(/<span class="num[^"]*" role="img" aria-label="([^"]*)">/g, ' $1 ')
    .replace(/<span class="dg">[\s\S]*?<\/span><\/span>/g, ' ')
    .replace(/<span class="ch">[\s\S]*?<\/span>/g, ' ')
    .replace(/<[^>]+>/g, ' ');
  return decode(text).replace(/\s+/g, ' ').trim();
}

function scriptMarkdown(list) {
  const narrationWords = list.reduce((n, s) => n + s.beats.reduce((k, b) => k + b.words, 0), 0);
  const lines = [
    '# Script: briefing for counsel',
    '',
    '<!-- Generated by `npm run script` from src/scenes/. Edit the scene files, not this one. -->',
    '',
    `Runtime at the current pace: **${clock(total)}**. Narration: **${narrationWords} words**, ` +
      `timed at ${wordsPerSecond} words per second (${Math.round(wordsPerSecond * 60)} per minute).`,
    '',
    'Each narration line is one beat; the picture changes with it. Numbers and questions on screen are ' +
      'checked against the repository docs when the video is built (`facts.json`, `questions.json`).',
    'To record: read the lines in order, one file per scene, into `assets/vo/<scene-id>.wav`. ' +
      'The build then times each scene to the recording.',
    '',
  ];
  list.forEach((s, i) => {
    lines.push(`## ${String(i).padStart(2, '0')}. ${s.title}`, '');
    lines.push(
      `Scene id \`${s.id}\` · chapter ${s.chapter} · ${clock(s.start)} to ${clock(s.start + s.dur)} ` +
        `(${s.dur.toFixed(1)} s)`,
      '',
    );
    const layerText = s.layer ? screenText(s.layer({ dur: s.dur, start: s.start })) : '';
    if (layerText) lines.push(`On screen throughout: ${layerText}`, '');
    s.beats.forEach((b) => {
      const at = clock(s.start + b.rel);
      if (b.say) lines.push(`**${at}** ${b.say}`);
      else lines.push(`**${at}** _(no narration, ${b.dur.toFixed(1)} s)_`);
      const shown = b.show ? screenText(b.show({ dur: b.dur, sceneLeft: 0, start: 0, index: 0 })) : '';
      if (shown) lines.push(`> On screen: ${shown}`);
      lines.push('');
    });
  });
  return lines.join('\n');
}

const stamp = (s, sep) => {
  const ms = Math.round(s * 1000);
  const h = String(Math.floor(ms / 3600000)).padStart(2, '0');
  const m = String(Math.floor((ms % 3600000) / 60000)).padStart(2, '0');
  const sec = String(Math.floor((ms % 60000) / 1000)).padStart(2, '0');
  return `${h}:${m}:${sec}${sep}${String(ms % 1000).padStart(3, '0')}`;
};

function srt(list) {
  return (
    captions
      .map((c, i) => `${i + 1}\n${stamp(c.start, ',')} --> ${stamp(c.start + c.dur, ',')}\n${c.text}\n`)
      .join('\n') + '\n'
  );
}

// ---- 7. Write -----------------------------------------------------------------

const outDir = path.join(ROOT, 'out');
fs.mkdirSync(outDir, { recursive: true });

if (!only) {
  fs.writeFileSync(path.join(ROOT, 'SCRIPT.md'), scriptMarkdown(scenes));
}
fs.writeFileSync(path.join(outDir, `captions${only ? `-${only}` : ''}.srt`), srt(scenes));
fs.writeFileSync(
  path.join(outDir, `timeline${only ? `-${only}` : ''}.json`),
  JSON.stringify(
    {
      total,
      chapters: allChapters,
      scenes: scenes.map((s) => ({
        id: s.id,
        chapterId: s.chapterId,
        start: s.start,
        dur: s.dur,
        beats: s.beats.map((b) => ({ rel: b.rel, dur: b.dur, mid: fix(s.start + b.rel + b.dur / 2) })),
      })),
    },
    null,
    2,
  ),
);

if (!has('script-only')) {
  const compDir = path.join(ROOT, 'compositions');
  const suffix = only ? `-${only}` : '';
  if (!only) {
    fs.rmSync(compDir, { recursive: true, force: true });
    // HyperFrames wants one root composition per project: clear chapter roots a
    // chapter render may have left behind.
    for (const name of fs.readdirSync(ROOT)) {
      if (/^chapter-[a-z0-9-]+\.html$/.test(name)) fs.rmSync(path.join(ROOT, name));
    }
  }
  fs.mkdirSync(compDir, { recursive: true });
  for (const s of scenes) fs.writeFileSync(path.join(compDir, `${s.id}.html`), sceneFile(s));
  if (withCaptions) fs.writeFileSync(path.join(compDir, `captions${suffix}.html`), captionsFile());
  fs.writeFileSync(path.join(compDir, `hud${suffix}.html`), hudFile());
  const file = only ? `chapter-${only}.html` : 'index.html';
  fs.writeFileSync(path.join(ROOT, file), rootPage(suffix));
  console.log(`wrote ${file} and ${scenes.length + 1 + (withCaptions ? 1 : 0)} compositions`);
}

const narrationWords = scenes.reduce((n, s) => n + s.beats.reduce((k, b) => k + b.words, 0), 0);
console.log(
  `${scenes.length} scenes, ${captions.length} caption pieces, ${narrationWords} words, ` +
    `runtime ${clock(total)} (${total.toFixed(1)} s)` +
    (scenes.some((s) => s.vo) ? ', timed to recordings where present' : ''),
);
