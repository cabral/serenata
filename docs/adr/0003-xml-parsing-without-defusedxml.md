# ADR-0003: Parse notice XML with the standard library, refusing DTDs

- Status: accepted
- Date: 2026-09-01
- Enforced by: `tests/test_survey.py::TestDoctypeIsRefused`,
  `tests/test_eforms_xml_guard.py::TestXmlInputGuard`
- Amended: 2026-09-02 — see [Amendment](#amendment-2026-09-02-the-refusal-had-to-cover-the-whole-prolog)
- Amended: 2026-09-05 — see [encoding bypass and claim limits](#amendment-2026-09-05-bomless-encodings-and-claim-limits)

> Historical rationale follows. The 2026-09-05 amendment supersedes the absolute
> security and streaming-memory claims below, including those in the first
> amendment. They are retained to make the correction visible, not as current
> guarantees.

## Context

The pipeline ingests XML written by third parties. TED publishes the notices,
but contracting authorities across 27 member states author them, so the bytes
are not ours and are not the Publications Office's either. `defusedxml` is the
conventional mitigation for hostile XML in Python, and the question is whether
it should become a runtime dependency.

The conventional answer assumes the standard library is broadly unsafe. Measured
against Python 3.12.14, that is not what it is:

| Attack | `xml.etree.ElementTree` |
|---|---|
| Internal entity expansion ("billion laughs") | **vulnerable** — amplification works |
| External entity, local file exfiltration (XXE) | already blocked — `undefined entity` |
| External DTD retrieval (SSRF) | already blocked — no fetch attempted |

ElementTree installs no external entity handler, so there is no path to reading
a local file or reaching the network. The single real exposure is denial of
service through entity amplification, against a batch pipeline we run ourselves.

Two further facts decided it.

**No real notice uses a DTD.** Across the 3,190 notices in OJ S 157/2026, zero
contain `<!DOCTYPE` and zero contain `<!ENTITY`. eForms is validated against an
XSD; a DTD has no legitimate reason to appear.

**`defusedxml` is dormant.** Its last stable release is 0.7.1, March 2021.
`0.8.0rc2` has stood unreleased since September 2023. This project has one
runtime dependency, runs `pip-audit` weekly, and trades on being auditable.

## Decision

Parse with the standard library. Refuse any notice carrying a document type
declaration, checked across the whole prolog before each chunk is parsed — see
the amendment below for why the emphasis is on *whole*. Do not add
`defusedxml`.

Refusing DTDs closes entity amplification completely — no entity can be declared
without one — in a few lines a reviewer can read, rather than by trusting a
package no one has released in five years. It is also *stricter* than
`defusedxml`'s own default, which permits DTDs (`forbid_dtd=False`) and blocks
only entities.

Parse as a stream and discard each element once its path is recorded. This was
adopted for a reason that is not security at all, and matters more: **one real
notice in that package is 40 MB, 1,569 times the 25 KB median**, and a
whole-tree parse of it cost 161 MB, four times the file itself. Streaming it
costs 0.5 MB, and the full 205 MB package surveys in 4.4 MB peak. Bounded
parsing also caps what any amplification could cost, which makes the DTD refusal
a second line rather than the only one.

## Consequences

- One runtime dependency remains (`httpx`). Nothing dormant enters the tree.
- A legitimate notice that ever carried a DTD would be refused. It is counted
  and reported rather than aborting a run, so the survey and the pipeline stay
  usable and the refusal is visible.
- Memory tracks the deepest element rather than the document, so a notice larger
  than the 40 MB one already seen does not threaten the run. That bound is on
  the XML tree, which is what this decision governs; a stage is additionally
  bounded by whatever it keeps. The survey keeps counts and peaks at 4.3 MB,
  while parse keeps every value it extracts and peaks at 89 MB on the same
  package. Both are streaming; neither holds the document.
- Streaming code is harder to read than `fromstring`. The comments earn that
  back by saying why; the measurements above are the justification.
- We inherit expat's behaviour. If a future Python changed ElementTree's
  external entity handling, this decision would need rechecking — the assertions
  in `tests/test_survey.py` fail loudly if the DTD refusal stops working, but no
  test here asserts XXE stays blocked upstream.

## What would change this

- **Switching to `lxml`.** It resolves external entities under configurations
  ElementTree does not, which reopens XXE and SSRF. `lxml` would require
  revisiting this ADR, not merely swapping an import.
- **Ingesting XML no publisher schema-validates.** TED validates eForms before
  publication; a source without that step has a materially different profile.
- **TED publishing notices that legitimately carry DTDs.** Then the refusal
  costs real data and the trade has to be re-argued.
- **`defusedxml` returning to active maintenance**, if the balance ever shifts.

## Amendment, 2026-09-02: the refusal had to cover the whole prolog

This ADR's central claim — that refusing DTDs "closes entity amplification
completely" — was **false as first implemented**, and a code review caught it
with a working probe.

The refusal scanned the first 8,192 bytes. A notice whose prolog opens with a
comment longer than that pushes its declaration past the window, and it was then
parsed with entity expansion live: a 3-byte entity reference expanded to 1,000
characters, trivially extendable. A UTF-16 document evaded the check too, since
the scan compares ASCII bytes.

The claim is worth keeping, so the implementation was made to earn it. The XML
specification permits a document type declaration only before the root element,
so `serenata.eforms.PrologGuard` scans **every byte read until the root opens**,
carrying the tail of each chunk into the next so a declaration split across two
reads is still seen, and stops scanning once the root element starts — which
keeps the cost bounded on the 40 MB notice this ADR was written around.
Encodings the scan cannot read are refused rather than scanned wrongly.

Two things worth recording beyond the fix. The hole was in the *guarantee*, not
the technique: streaming, no `defusedxml`, and refusing DTDs were all still the
right calls, and the decision stands unchanged. And the survey shared the same
weakness through the same helper, so both stages were fixed together and both
have a regression test — a security control living in one place was what made
that a single fix rather than two.

## Amendment, 2026-09-05: BOMless encodings and claim limits

**Measured bypass.** On Python 3.12.14, `stream_elements` expanded a small
internal entity in both BOMless UTF-16 byte orders. The synthetic input was
`<!DOCTYPE x [<!ENTITY harmless "SYNTHETIC_ENTITY">]><x>&harmless;</x>`, encoded
as `utf-16-le` or `utf-16-be`; each produced the end-element text
`SYNTHETIC_ENTITY`. The initial regression failed for both encodings before the
fix. The previous guard checked only BOMs present in the first read, not BOMless
encoding signatures; a short first read could also split a BOM. The September 2
statement that unscannable encodings were refused was therefore incomplete.
This probe demonstrates internal entity expansion, not external-entity access,
network retrieval, or resource exhaustion.

**Decision.** Retain ElementTree and the shared prolog scan, without a new
dependency. Before the first parser feed, collect at least four opening bytes
or reach EOF, even on short reads. Reject a prefix containing NUL or beginning
with neither ASCII `<`/XML whitespace nor a complete UTF-8 BOM. This rejects
UTF-16/32 with or without BOMs and non-ASCII starts such as the EBCDIC XML
signature. Valid UTF-8 remains supported, including split BOMs and multibyte
characters. This is an ASCII-compatible input gate, not full UTF-8 validation:
parser-supported ASCII-compatible declared encodings remain possible.

Continue scanning before each feed until the root start event, retaining the
overlap that detects `<!DOCTYPE` across reads. This is a conservative byte scan,
not an XML lexer; marker-like text in a scanned comment or chunk can also cause
refusal. Regression tests cover both UTF-16 byte orders, UTF-32, BOMs, BOMless
signatures, short reads, UTF-8, EOF, and exact header/later-chunk DTD splits.
For the UTF-16/32 cases, a feed spy verifies rejection before any parser feed.

**Limits and correction.** The earlier claims that DTD refusal closes
amplification "completely", that streaming caps amplification, and that memory
tracks only depth were too broad. Clearing completed elements releases subtrees;
it does not bound text or attribute sizes, parser buffering, nesting, or values
retained by consumers. The historical memory measurements describe those inputs,
not an adversarial resource limit. This change adds no memory, time, or input-size
budget. The earlier external-entity table is not revalidated here and does not
establish a universal guarantee. Revisit on parser/runtime changes, a need for
non-ASCII-compatible XML, or before claiming broader hostile-input protection.
