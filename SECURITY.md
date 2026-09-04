# Security

This project reads public procurement notices and publishes derived data. The
most serious thing that can go wrong here is not a crash — it is **personal data
reaching output that should not carry any**. That is treated as a security
report and takes priority over everything else on this page.

## Reporting

Use GitHub's private vulnerability reporting:
**[open a report](https://github.com/cabral/serenata/security/advisories/new)**.
It is private to the maintainer until an advisory is published, so nothing is
disclosed by the act of reporting it.

**Please do not open a public issue** for a security report, and in particular
do not paste the personal data you found into one — that publishes it a second
time, to a wider audience. Describe where it is; that is enough to find it.

If you have no GitHub account, there is currently no other route, which is a
real gap and is recorded as such rather than glossed over. Until the project has
a domain of its own, GitHub is the only channel that does not mean publishing a
personal address.

## What counts, in priority order

**1. Personal data in published output.** A contact name, e-mail address,
telephone number, or anything identifying a natural person, appearing in a
published dataset, a generated report, a flag, or this repository. This is the
constraint the whole pipeline is built around
([`personal-data.md`](docs/personal-data.md)), and the design is meant to make
it impossible rather than unlikely — so an instance of it is a design failure,
not a slip, and is worth reporting even if it looks minor.

The response is **remove first, investigate second.** The output comes down or
is regenerated before anyone works out how it got there.

Known and already recorded: the drop list matches element *paths*, so it cannot
catch a publisher who types a contact address into a field that is not a contact
field. 46 such values were measured in one publication day. That gap is
[open work](docs/open-work.md#14-decide-what-to-do-about-personal-data-in-fields-that-are-not-contact-fields)
awaiting counsel, so a report of that specific shape confirms a known problem
rather than uncovering a new one — still worth sending, and it will be answered
with what is already known.

**2. A way to make the pipeline produce wrong output.** A crafted notice that
causes a wrong flag, a mis-parse, or output that disagrees with its source. The
project's whole claim is that a flag can be checked against the notice it came
from, so anything breaking that link matters.

**3. Ordinary vulnerabilities.** Code execution, resource exhaustion, dependency
issues, anything in the fetch stage's handling of what TED returns. Note that
XML entity expansion is already refused
([ADR-0003](docs/adr/0003-xml-parsing-without-defusedxml.md)) and the pipeline
runs offline downstream of fetch — but if either of those turns out not to hold,
that is exactly the report worth having.

## What to expect

One person maintains this, unpaid. So, honestly:

- An acknowledgement **within five working days**. If you have not heard back,
  the report did not arrive — send it again rather than assuming it was ignored.
- For personal data in output: the output is withdrawn or regenerated **as soon
  as it is confirmed**, before any analysis of cause.
- For everything else: a fix or a written explanation of why not, and an advisory
  if one is warranted.
- Credit in the advisory and the changelog if you want it, and none if you do not.

There is **no bug bounty**. The project has no money. Nothing here is an
invitation to test against live systems.

## Out of scope

- **TED itself.** Notices, the API, the daily packages, and their content belong
  to the Publications Office of the European Union, not to this project. If a
  notice contains personal data that should not be there, that is TED's to fix —
  though telling us too is useful, because it tells us our drop list has a hole.
- **Denial of service against TED.** This project fetches politely and rate-limits
  itself by design; do not test that claim by attacking a public service.
- **Findings that are wrong but not sensitive.** Those are corrections, and they
  have their own route: [`docs/corrections-policy.md`](docs/corrections-policy.md).

## Good-faith research

Report a problem you found while reading the code, running the pipeline on your
own machine, or reading published output, and this project will not pursue you
for it. That is a statement of intent from a one-person project, not a legal
safe-harbour instrument — if you need a formal one, ask before you start and it
can be discussed.
