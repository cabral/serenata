#!/usr/bin/env node
// The storyboard step: one still per beat, taken late in the beat so every
// entrance has settled. Look at these before rendering anything; changing a
// still costs seconds, changing a render costs minutes.
//
//   npm run stills                     every beat of every scene -> snapshots/
//   npm run stills -- --scene=s06      only scenes whose id starts with s06

import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const filter = process.argv.find((a) => a.startsWith('--scene='))?.split('=')[1] ?? '';
const timeline = JSON.parse(fs.readFileSync(path.join(ROOT, 'out', 'timeline.json'), 'utf8'));

const times = [];
const labels = [];
for (const s of timeline.scenes) {
  if (!s.id.startsWith(filter)) continue;
  s.beats.forEach((b, i) => {
    times.push((s.start + b.rel + Math.max(b.dur * 0.85, Math.min(b.dur - 0.1, 1.8))).toFixed(2));
    labels.push(`${s.id}#${i}`);
  });
}
if (!times.length) {
  console.error(`no beats match "${filter}"`);
  process.exit(1);
}

const out = path.join(ROOT, 'snapshots');
fs.rmSync(out, { recursive: true, force: true });
const result = spawnSync(
  process.execPath,
  [path.join(ROOT, 'scripts', 'hf.mjs'), 'snapshot', '--no-end', '--at', times.join(','), '--describe', 'false'],
  { cwd: ROOT, stdio: 'inherit' },
);
if (result.status !== 0) process.exit(result.status ?? 1);

fs.writeFileSync(path.join(out, 'index.txt'), labels.map((l, i) => `${String(i).padStart(2, '0')}  ${times[i]}s  ${l}`).join('\n') + '\n');
console.log(`\n${times.length} stills in snapshots/ (index.txt maps them to scenes and beats)`);
