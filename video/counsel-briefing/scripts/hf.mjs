#!/usr/bin/env node
// Runs the pinned HyperFrames CLI from node_modules with telemetry and update
// checks off. This project handles legal material; nothing about a render
// should phone home. Cross-platform: no shell, no `env` prefix.

import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const bin = path.join(ROOT, 'node_modules', 'hyperframes', 'bin', 'hyperframes.mjs');

const result = spawnSync(process.execPath, [bin, ...process.argv.slice(2)], {
  cwd: ROOT,
  stdio: 'inherit',
  env: {
    ...process.env,
    HYPERFRAMES_NO_TELEMETRY: '1',
    DO_NOT_TRACK: '1',
    HYPERFRAMES_NO_UPDATE_CHECK: '1',
    HYPERFRAMES_NO_FEEDBACK: '1',
    HYPERFRAMES_SKIP_SKILLS: '1',
    // Never send frames of a legal briefing to a third-party vision API.
    GEMINI_API_KEY: '',
  },
});
process.exit(result.status ?? 1);
