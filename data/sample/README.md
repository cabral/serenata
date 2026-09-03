# Committed sample data

`data/` is a gitignored workspace for fetched raw XML and generated Parquet.
This directory is the one committed exception: a small package of notices that
`tests/test_sample_package.py` runs the whole pipeline over — archive layer,
parse, normalise, Parquet, and a DuckDB query — so that something in CI reads a
package rather than a notice built inside the test that reads it.

## What is here

`20260817_157/` is a package as TED delivers one: members under a single
directory named for the publication day and issue. The tests pack it into
`202600157.tar.gz` at run time. Anyone can do the same by hand:

```
tar czf 202600157.tar.gz -C data/sample 20260817_157
uv run serenata normalise 202600157.tar.gz --out /tmp/sample-dataset
```

That command **exits 1 and names two notices it would not write**, which is the
behaviour being demonstrated rather than a fault: the sample carries a legacy
notice and a damaged one on purpose. Four notices become 33 rows.

| Member | What it is | What it covers |
|---|---|---|
| `00000001_2026.xml` | contract notice | a lot, two organisations, a title in two languages, two places of performance, two contracting-system codes on one lot; a `cac:Contact` block that must never reach a record; and **two contact addresses typed into fields that are not contact fields** — a city and a lot description — which the drop list cannot catch and `docs/dataset-shape.md` counts |
| `00000002_2026.xml` | contract award notice | a lot result, its winning tenders and settled contract; **a withheld bid count** published as the code `unpublished` with the number `-1`, declared by `rec-sub-cou` and `rec-sub-typ` as real notices declare it; **a withheld amount** published as `-1` and declared by `win-ten-val`; privacy blocks at three different scopes, one of which names a field this model has no column for |
| `00000003_2026.xml` | contract award notice | carries the **same `cbc:ID` as `00000002_2026.xml`** under a different publication number, which is what two notices in OJ S 157/2026 do. Anything keyed on the notice UUID merges them |
| `00000004_2026.xml` | contract award notice | an organisation flagged `efbc:NaturalPersonIndicator`, whose identifying values are suppressed while its opaque key is kept, and an `efac:UltimateBeneficialOwner` subtree, which is dropped outright |
| `000005_2026.xml` | legacy TED notice | six digits in the name, `TED_EXPORT` at the root: refused rather than parsed, because the legacy field mappings have never been measured |
| `00000006_2026.xml` | a damaged document | an unclosed root element. One bad notice must be reported by name and must not cost the other five |

## Why these notices are synthetic

`tests/fixtures/README.md` allows two kinds of fixture: obviously synthetic
notices, or real public ones reproduced accurately and named after their notice
id. This sample takes the first option, deliberately.

A contact name, e-mail and telephone number appear in **99.9%** of real notices
(`docs/personal-data.md`). Committing a real notice to a public repository, to
test that the pipeline removes personal data, would put the personal data in the
repository permanently — and redacting one first makes it neither accurate nor
synthetic, which is the one thing the fixture rules refuse. So these are
invented documents that are structurally faithful: impossible publication
numbers, `EXAMPLE` names, and every value that stands where a person's data
would stand spelled `MUST-NEVER-APPEAR` or `DROPPED-CONTACT-VALUE`, so a test
can assert on it without anyone inventing a name.

**What that leaves unproven** is honest and worth stating: no test reads a
notice TED actually published, so a change in what TED emits would not fail this
build. `docs/known-issues.md` records which of this project's published figures
are generated from real archives and which were measured by hand.

## Why XML rather than a `.tar.gz`

[open-work #7](../../docs/open-work.md#7-commit-a-small-sample-package-for-end-to-end-tests)
asked for a committed tarball. The notices are committed unpacked instead,
because a fixture is only worth having if a reviewer can read it: a diff that
changes one line of one notice is reviewable, and a diff that changes a
compressed archive is a new binary nobody can check. The tests pack it in one
line, so what the pipeline receives is identical either way.

The same rules apply as `tests/fixtures/`: never plausible-looking fabrications
— nothing here could be mistaken for a real finding — and never a natural
person's name.
