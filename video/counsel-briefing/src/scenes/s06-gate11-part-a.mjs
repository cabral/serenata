import { qcss, questionBeat, titleBeat } from '../qcard.mjs';

// Narration per question. The on-screen text comes from questions.json, which
// the build checks against docs/counsel/11-natural-person-status.md.
const SAY = {
  A1: `A1, the lawful basis. We propose legitimate interest. Does it hold for records of unknown status, and does the answer differ for the raw XML, the tables and the flags?`,
  A2: `A2. May I run counts-only queries to see how the indicator is spread by role and country? That count is itself processing I haven't been cleared to do.`,
  A3: `A3, retention. What period and deletion criteria apply to what we hold today, backups included? The September 2027 review date is not permission.`,
  A4: `A4. What does Article 14 require for data we collect indirectly, and does an exception apply?`,
  A5: `A5. Is a data protection impact assessment required?`,
  A6: `A6. Storage is local, with no third-party sync. That is policy, not an audited control. What is required?`,
  A7: `A7. How does a data-subject request reach the archive, tables, flags and backups, and how does an immutable archive give way to erasure?`,
};

const GLYPH = { A1: 'scales', A2: 'stack', A3: 'clock', A4: 'mail', A5: 'doc', A6: 'lock', A7: 'trash' };

const STAKES = {
  A1: [{ text: 'If no: data deleted or rebuilt narrower', kind: 'c' }],
  A2: [
    { text: 'If yes: a counts-only survey runs' },
    { text: 'If refused: threshold stays open', kind: 'k' },
  ],
  A3: [{ text: 'If short: data deleted or rebuilt', kind: 'c' }],
};

export default (c) => {
  const qs = c.qs('11').filter((q) => q.id.startsWith('A'));
  return {
    id: 's06-gate11-part-a',
    chapterId: 'gate-11',
    chapter: 'Gate 11 · Part A',
    title: 'Gate 11, part A: what may we hold today?',
    css: qcss,
    beats: [
      {
        say: `Gate 11 covers organisations whose status the notice doesn't tell us. Part A is about today, and I'd like it answered first.`,
        show: () =>
          titleBeat({
            kicker: 'Gate 11 · Unknown natural-person status',
            big: 'Part A',
            sub: 'What may we hold today?',
            tags: [
              { text: 'Clock running', kind: 'c' },
              { text: 'Seven questions', kind: 'k' },
              { text: c.f('partAFirst'), kind: 'p' },
            ],
            glyph: 'clock',
          }),
      },
      ...qs.map((q, i) => ({
        say: SAY[q.id],
        show: () =>
          questionBeat({
            gateLabel: 'Gate 11 · Part A',
            q,
            index: i,
            total: qs.length,
            glyph: GLYPH[q.id],
            stakes: STAKES[q.id],
          }),
      })),
    ],
  };
};
