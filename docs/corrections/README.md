# Corrections

One file per correction, named `YYYY-MM-DD-slug.md`. Empty, because nothing has
been published yet and so nothing has been wrong yet.

[`corrections-policy.md`](../corrections-policy.md) is the policy this directory
implements. The short version: errors are corrected in place with a dated note,
and nothing is quietly deleted.

Keeping the record here rather than only in the corrected page is the point. A
reader can see every correction the project has ever made in one place, which is
a stronger claim to being trustworthy than never appearing to be wrong.

## Template

```markdown
# <what was wrong, in one line>

- Date reported: YYYY-MM-DD
- Date corrected: YYYY-MM-DD
- Reported by: <name, or "the project", or "anonymous" if asked>
- Affects: <the finding, dataset version, or report — with a link>

## What was published

The claim as it stood, quoted exactly. Not paraphrased: a reader checking this
later needs to see what they saw.

## What is actually true

The corrected fact, with its source notice linked.

## Why it happened

The cause, as specifically as it is known. "A classifier defect" is not a cause;
"the rule read the awarded amount without checking its status, so a withheld
value of `-1` was treated as a price" is.

## What changed as a result

The fix. If a classifier was at fault, the test that now fails without the fix.
If the finding was withdrawn rather than corrected, say so plainly here.
```

A correction that cannot fill in "why it happened" is not finished. The point of
the record is that the next one is less likely, and that needs a cause rather
than an apology.
