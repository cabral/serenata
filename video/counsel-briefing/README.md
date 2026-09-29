# Counsel briefing video

A motion-graphics walkthrough of what Serenata Europa asks counsel and why.
It follows the instructions in [`docs/counsel/`](../../docs/counsel/) and adds
one thing they do not carry: the case for asking a lawyer at all.

**Status: draft, not sent.** Sending it is an external message and needs the
maintainer's explicit authorization ([`legal` skill](../../.claude/skills/legal/SKILL.md)).
Nothing in it is legal advice or a request that authorizes anything.

Runs about 9½ minutes at 150 words per minute, in thirteen scenes grouped into
seven chapters, so a reader can watch only the gate they are answering.

## Run it

Needs Node 22 or later and `ffmpeg` on the path. Run
`node scripts/hf.mjs browser ensure` once to fetch the headless Chrome that
HyperFrames renders with.

```
cd video/counsel-briefing
npm install

npm run script          # SCRIPT.md and out/captions.srt: read this first
npm run stills          # one PNG per beat in snapshots/: the storyboard
npm run check           # HyperFrames lint, layout, motion and contrast gates
npm run dev             # live preview in the browser
npm run render:draft    # quick MP4 in out/
npm run render          # delivery quality, out/counsel-briefing.mp4
npm run render:chapters # one MP4 per chapter in out/chapters/
```

Every command rebuilds first. `index.html` and `compositions/` are generated
and ignored; the sources are `src/`, `facts.json`, `questions.json` and
`direction.json`. For a reproducible container render, run
`node scripts/hf.mjs render --docker --strict --output out/counsel-briefing.mp4`.

## Where things are

| Path | What it is |
|---|---|
| `src/scenes/*.mjs` | One file per scene: the narration, one sentence per beat, and what the picture does while it is said |
| `src/qcard.mjs` | The question card every gate uses |
| `src/components.mjs`, `src/icons.mjs` | Odometer numbers, typed text, stripes, and pixel icons drawn as character grids |
| `src/theme.css` | Colours, type, label boxes. Tokens are listed in its header |
| `src/runtime.js` | Turns `data-a="pop"`-style attributes into Web Animations |
| `facts.json`, `questions.json` | Every number and question on screen, each with the document it comes from |
| `direction.json` | Pace, motion feel, camera push. The knobs for director's notes |
| `scripts/` | The generator, the storyboard script, the HyperFrames wrapper |

## Notes as a director

Change one value in `direction.json` and re-render, instead of describing the
change to a tool.

| Note | Knob |
|---|---|
| "Slow every zoom to 0.7x" | `camera.speed: 0.7` |
| "Less drift" or "no push at all" | `camera.push` (0.02 is a 2% scale over a scene; 0 turns it off) |
| "Snappier entrances" | raise `motion.speed` |
| "Smoother, less retro" | raise `motion.feel` from 15 towards 30 |
| "Talk faster" | `pace.wordsPerSecond` |
| "More air between lines" | `pace.beatPad` |
| "No captions" | `captions: false`, or `--no-captions` |

The hard cuts and stepped motion are deliberate: they come from the original
site's bitmap look, and `motion.feel` is how many steps a second the motion
uses.

## Address it to someone

This repository is public and names no one who has not confirmed their
involvement in writing, so the recipient lives in a file git ignores. Copy
`recipient.example.json` to `recipient.local.json`:

```json
{
  "name": "Ana",
  "whyYou": "You have advised on GDPR and on Swedish defamation law, which are the two regimes this turns on."
}
```

`name` becomes "Hello Ana." in the first line. `whyYou` adds a scene after
"Why counsel", spoken and shown, and should be one sentence in the maintainer's
voice about what makes this counsel the right person. Leave both empty for the
neutral version. Write only what the person has confirmed.

## Record the voice-over

Read `SCRIPT.md` scene by scene and save `assets/vo/<scene-id>.wav` (`.mp3` and
`.m4a` work too), for example `assets/vo/s06-gate11-part-a.wav`. The build
measures each file with `ffprobe`, times the scene to it, spreads the beats by
word count, and adds the audio track. A scene with no recording keeps its
estimated timing. Recordings stay on the maintainer's machine until they decide
otherwise.

If a beat lands a second early or late against your voice, split or merge its
sentence in the scene file; the picture follows the sentence.

## What the video will and will not say

- **Every figure comes from the repository docs.** `facts.json` and
  `questions.json` give each number and question a `needle`, a literal string
  that must appear in the cited document. The build stops when one does not, and
  `tests/test_counsel_video.py` checks the same in CI. Change a count in the docs
  and the video refuses to build until it is updated.
- **Only published counts appear.** No notice ID, no organisation, no field
  value. The example flag on screen names its fields and leaves the values blank.
- **Flags are called anomalies** with possible innocent explanations, as
  everywhere else in the project.
- **The independence statement is on screen twice.** The look is borrowed from
  serenata.ai, so the README's line that this project is not affiliated with,
  endorsed by or run by Open Knowledge Brasil is repeated in the lineage scene and
  on the closing card.

## Look

Taken from [serenata.ai](https://www.serenata.ai) by reading its stylesheet and
logo, not by copying artwork: black ground, white text, Anonymous Pro
monospace, white label boxes with black text, big numerals, stripe groups,
a rising line, a blinking `_` cursor, pixel icons, and a wordmark in a pixel face
with a hard purple offset.

| Token | Value | Origin |
|---|---|---|
| ground, text | `#000`, `#fff` | site body |
| logo purple, logo white | `#681284`, `#e6e6e6` | sampled from the logo |
| deep purple | `#43007f` | site footer |
| lilac | `#bc68d1` | site links |
| coral, red | `#eb4a3b`, `#c72838` | site support bar, buttons |

The site's logo, its Open Knowledge Brasil and DigitalOcean marks, and its press
logos are not used. The wordmark here is typed in Pixelify Sans, so it does not
pass for the original.

## How it was made

The workflow follows a public write-up on getting professional motion graphics
from a model ([post](https://x.com/rexan_wong/status/2103707054108299437)):
a style to name rather than describe, a code-based renderer, brand and real
material in the prompt, a storyboard of stills before anything moves, then notes
in a director's words. What that meant here:

1. **Reference.** The reference is serenata.ai's own CEAP infographic, animated.
   No other reference video was supplied.
2. **Engine.** HyperFrames, because it renders HTML to MP4 and is Apache-2.0.
   Remotion is the other tool the post names and is not used: its licence is not
   open source, which [CLAUDE.md](../../CLAUDE.md) constraint 1 rules out.
   [ADR-0014](../../docs/adr/0014-counsel-video-toolchain.md) has the reasoning.
3. **Components.** A component library was not used. There is no product UI to
   show; the cards, tables and diagrams are drawn for this video.
4. **Brand and real material.** The palette and type above, and the real counts
   and questions from the counsel instructions.
5. **Storyboard.** `npm run stills` renders one frame per beat. Look at them
   before rendering; a still takes seconds to change.
6. **Notes.** `direction.json`, above.

## Dependencies and licences

`hyperframes` is the only dependency, pinned to an exact version. Animation uses
the browser's Web Animations API and no library. Fonts are Anonymous Pro and
Pixelify Sans under the SIL Open Font License, vendored in `assets/fonts/` with
their licence texts, so a render fetches nothing. `tests/test_counsel_video.py`
checks every package in the lockfile against an AGPL-compatible list.

The wrapper in `scripts/hf.mjs` turns off HyperFrames telemetry and update
checks and blanks `GEMINI_API_KEY`, so no frame of a legal briefing is sent to a
vision API. Do not run `hyperframes publish`, `cloud`, `lambda` or `cloudrun`:
they upload the project. Renders stay on the machine that made them.
