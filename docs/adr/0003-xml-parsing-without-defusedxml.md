# ADR-0003: Parse notice XML with the standard library, refusing DTDs

- Status: accepted
- Date: 2026-09-01

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
declaration, checked against the prolog before parsing begins. Do not add
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
  than the 40 MB one already seen does not threaten the run.
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
