#!/usr/bin/env node
// One MP4 per chapter, for a reader who wants only the gate they are answering.
//
//   npm run render:chapters                     delivery quality
//   npm run render:chapters -- --quality draft  quick check
//   npm run render:chapters -- --only=gate-14   one chapter

import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const opt = (name, fallback) => args.find((a) => a.startsWith(`--${name}=`))?.split('=')[1] ?? fallback;
const quality = args.includes('--quality') ? args[args.indexOf('--quality') + 1] : opt('quality', 'delivery');
const only = opt('only');

const run = (script, extra) => {
  const r = spawnSync(process.execPath, [path.join(ROOT, 'scripts', script), ...extra], { cwd: ROOT, stdio: 'inherit' });
  if (r.status !== 0) process.exit(r.status ?? 1);
};

// The full build writes out/timeline.json, which lists the chapters in order.
run('build.mjs', []);
const { chapters } = JSON.parse(fs.readFileSync(path.join(ROOT, 'out', 'timeline.json'), 'utf8'));
const dir = path.join(ROOT, 'out', 'chapters');
fs.mkdirSync(dir, { recursive: true });

chapters.forEach((id, i) => {
  if (only && id !== only) return;
  const out = path.join('out', 'chapters', `${String(i + 1).padStart(2, '0')}-${id}.mp4`);
  run('build.mjs', [`--only=${id}`]);
  const root = path.join(ROOT, `chapter-${id}.html`);
  try {
    run('hf.mjs', ['render', '-c', `chapter-${id}.html`, '--quality', quality, '--output', out]);
  } finally {
    // Two root compositions in one project fail `npm run check`.
    fs.rmSync(root, { force: true });
  }
});
