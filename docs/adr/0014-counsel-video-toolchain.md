# ADR-0014: The counsel briefing video is built with HyperFrames

- Status: proposed — isolated under `video/`; the pipeline's stack is unchanged
- Date: 2026-09-29
- Enforced by: `tests/test_counsel_video.py::TestToolchain` for the pinned engine, the licence allowlist over the lockfile and the ban on hosted services, and `tests/test_counsel_video.py::TestEverythingOnScreenIsInTheDocs` for every figure and question the video shows

## Context

The counsel instructions in [`docs/counsel/`](../counsel/) are questionnaires.
A narrated walkthrough makes the asks easier to take in and carries the one
argument they omit, why counsel is needed at all. It is motion graphics, so it
needs a renderer, and CLAUDE.md fixes the pipeline's stack as Python with `uv`.

Constraint 1 requires every dependency to be AGPL-3.0 compatible. The tool most
often named for programmatic video, Remotion, ships under a custom licence: free
for individuals, non-profits and companies of up to three people, a paid company
licence above that, and no right to relicense. That is source-available, not open
source. GSAP, the default animation runtime in most HTML video templates, reports
its licence as "Standard 'no charge' license", also bespoke. HyperFrames is
Apache-2.0 and can drive animation through the browser's Web Animations API,
which needs no library.

## Decision

Build the video with HyperFrames, pinned to an exact version, and animate only
with the Web Animations API. Keep it in `video/counsel-briefing/`, a
self-contained Node project that nothing in `serenata/` imports and CI does not
build. Scenes are generated from source files; every number and question shown
is a literal that must appear in the cited document; the recipient's name lives
in an ignored local file, because this repository is public.

## Consequences

- Rendering needs Node 22 and `ffmpeg`. Neither is part of `uv sync`, and CI
  does not render, so a render failure is found by whoever renders.
- The lockfile contains sharp's prebuilt libvips, LGPL-3.0-or-later, which the
  AGPL accepts. It is fetched at install time and never distributed by this
  repository. `pip-audit` does not cover the npm tree, so its advisories are
  checked by whoever updates the pin.
- The look reuses the palette, type and layout habits of serenata.ai and none of
  its logos or partner marks. The README's independence statement is repeated on
  screen, because the resemblance would otherwise suggest an affiliation.
- The video is a draft. Sending it to counsel is an external message that needs
  the maintainer's authorization, and it authorizes nothing itself.

## Revisit triggers

- HyperFrames changes licence, stops being published, or a package in the
  lockfile falls outside the allowlist.
- Someone wants the video rendered in CI. Node would then enter CI, and that
  needs its own decision.
- Counsel asks for a document instead. The scene data would generate it, and the
  video would stop being the primary form.
- The video needs more than one maintainer's attention. It then belongs in its
  own repository, not this one.
