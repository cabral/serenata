# Corrections policy

**Nothing has been published yet.** This exists before the first finding rather
than after the first mistake, because a policy written while something is going
wrong is worth very little, and because deciding in advance how to be wrong is
part of deserving to be believed.

The project publishes statistical anomalies drawn from public procurement
notices. Some of them will be wrong. The question that matters is not whether
that happens but what happens next.

## The commitment

**Errors are corrected in place, with a dated note saying what changed. Nothing
is quietly deleted.**

A page that silently loses a claim is worse than one that never made it: a
reader who saw the original has no way to know it was withdrawn, and anyone
checking later finds a record that has been tidied. So a corrected finding keeps
its URL and carries its own history.

## What counts as an error

- **A flag that should not have fired.** The classifier misread the data, or the
  rule is wrong.
- **A wrong number.** A figure in a finding, a report, or a published dataset
  that does not match what the source says.
- **A superseded notice.** TED published a corrigendum or withdrew the notice a
  flag was raised against, so the thing the flag describes no longer stands.
  This is checked before publication and can still happen afterwards.
- **A misdescribed entity.** An organisation named as something it is not — most
  seriously, an entity that turns out to be a **natural person**. See below.
- **A broken link to a source.** A flag that cannot be checked against its notice
  has lost the property the whole project exists to provide.

Something being *unwelcome* is not an error. A correct, source-linked,
mechanically phrased statement stays up, and a request to remove one is answered
with the arithmetic behind it. Disagreement about what a pattern *means* is not
a correction either — flags are anomalies, and the finding will already say that
innocent explanations exist.

## How to report one

Open an issue: **[report a correction](https://github.com/cabral/serenata/issues/new)**.
Say which finding or figure, and what you believe the correct value is. A link
to the source notice is the fastest possible route to a fix.

Two exceptions that go elsewhere:

- **Personal data in published output** — that is a security report, and the
  route is [`SECURITY.md`](../SECURITY.md). Do not put the data in a public
  issue.
- **A legal threat, takedown demand, or data protection request** — that is not
  a correction and is not handled here. It goes to counsel. Sending one does not
  make the underlying question go away, and if there is a factual error inside
  it, that error still gets corrected on its own merits.

## What happens

| | |
|---|---|
| Acknowledged | within **five working days** |
| A finding that names an entity and is wrong | **withdrawn first**, corrected after |
| Everything else | corrected, or answered with why it is not an error |

Withdrawal before investigation is deliberate for anything naming a company or
an institution. The cost of a claim standing an extra week while someone checks
it is borne by the named party; the cost of taking it down early is borne by the
project. That asymmetry decides the order.

One person maintains this, unpaid, so those are honest aims and not guarantees.
If you hear nothing in five working days the report did not arrive — send it
again.

## Findings and datasets are corrected differently

**A finding** is a claim about someone. It is corrected in place: the erroneous
statement is struck or replaced, a dated note says what changed and why, and if
the finding was wrong at its core it is marked **withdrawn** rather than edited
into something it never said.

**A dataset** is a record. Published datasets are versioned, and a correction
produces a **new version** rather than a rewrite of the old one. Superseded
versions stay retrievable with a notice attached, because a finding published
from an earlier version has to remain checkable against the data it actually
used. Reproducibility is the reason this project can be trusted at all, and
quietly changing history under a published claim would destroy it.

So: findings get corrected, datasets get superseded, and both say so on their
face.

## The cases specific to this project

**An entity turns out to be a natural person.** eForms flags sole traders with
an indicator that is absent from 97% of organisation records, and absent means
"not provided", never "false" — so for most organisations this is genuinely
unknown ([open work
#11](open-work.md#11-decide-the-publication-rule-for-unknown-natural-person-status)).
If a named entity turns out to be a private individual, the finding comes down
**immediately and without waiting for confirmation of anything else**, and the
question of whether it should be republished is one for counsel rather than for
this policy.

**A classifier defect affects many findings at once.** Then every finding it
produced is withdrawn, not just the one that was reported. A rule that was wrong
once was wrong every time it fired, and correcting only the flagged instance
leaves the rest standing on a foundation already known to be bad. The classifier
does not publish again until the defect has a test that fails without the fix.

**The source itself was wrong.** If TED's own data was incorrect, the dataset
faithfully reflects what was published and is not itself in error — but a
finding resting on it can still be wrong, and is corrected on that basis. Where
the underlying notice needs fixing, that is the Publications Office's to do.

## The corrections log

Every correction is recorded in `docs/corrections/`, one file per correction,
with the date, what was claimed, what was actually true, and what changed as a
result. That directory does not exist yet because nothing has been published
yet. It will be created by the first correction, and if it stays empty for a
suspiciously long time, that is itself worth noticing.
