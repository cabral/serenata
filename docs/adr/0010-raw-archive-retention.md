# ADR-0010: Raw archive retention and an unresolved lawful basis

- Status: amended — structural suppression retained; lawful basis and retention unresolved
- Date: 2026-09-03
- Amendment: 2026-09-05
- Enforced by: nothing mechanical — it is a policy. The structural-drop measurement is checked by
  `tests/test_dropped.py::TestItsOneClaim`

## Context

[ADR-0002](0002-fetch-daily-bulk-packages.md) settled *what* the raw archive is
— whole publication days, fetched byte-for-byte, immutable, the ground truth
every flag traces back to. The archive holds personal data: contact details
appear in **99.9%** of the measured notices. The one-day
[dropped-fields report](../dropped-fields.md) counts **32,135 leaf removals,
3.6% of the package's leaves**. That measures specified structural drops, not
the absence of personal data downstream.

**Amendment, 2026-09-05.** The original decision overstated both the legal basis
and the privacy boundary. Its claims that personal data existed only in the
archive, that a downstream leak was impossible and that erasure concerned the
archive alone are withdrawn and corrected here. This amendment records limits;
it is not counsel approval, legal advice or a compliance certification.

The five-day [dataset-shape report](../dataset-shape.md) documents **427
email/address-shaped values in retained columns**, **139 personal-address-shaped**,
with **359 in descriptions**. These patterns are neither a full inventory nor a
legal classification of each value. Explicit-natural-person Company/TouchPoint
`WebsiteURI` suppression is now fixed in code, but stored datasets have not been
rebuilt. The natural-person indicator is absent from about 90% of notices, and
opaque notice-scoped keys remain linkable to the public source. Structural
suppression is not anonymisation.

The [GDPR on EUR-Lex](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng), checked
2026-09-05, supplies the relevant distinctions:

- **Articles 4(1)–(2) and Recital 26:** collection, storage, structuring and use
  are processing; indirect identifiability includes means reasonably likely to
  be used by the controller or another person. Removing a name is insufficient
  when source linkage can identify the person.
- **Articles 5 and 6:** a lawful basis, necessity, minimisation, transparency,
  storage limitation and security are required for private holdings too.
- **Article 14:** indirect collection raises information duties, subject to
  specific exceptions and safeguards, not a general public-source exemption.

The [TED legal notice](https://ted.europa.eu/en/legal-notice) allows reuse unless
otherwise noted and flags additional rights for identifiable individuals and
third-party material. [Decision 2011/833/EU, Article 4](https://eur-lex.europa.eu/eli/dec/2011/833/oj/eng)
preserves data-protection obligations. TED's own legal basis and retention policy
do not transfer to this project.

## Decision

**Keep structural suppression at parse. Do not treat this ADR as authorisation
for current processing or for publication. Counsel review remains unresolved.**

- **Purpose and proposed basis.** Reproducible procurement analysis is the
  proposed legitimate interest under Article 6(1)(f), not an established basis.
  Necessity, less intrusive alternatives, reasonable expectations and risks to
  data subjects need a documented assessment with counsel. People in notices
  are not limited to professional contact points. Current raw archives, derived
  records and source-linked flags all belong in that assessment.
- **Minimisation.** Tests establish specified path suppression, not anonymity.
  Retained-field leakage and unknown natural-person status remain open. Any
  changed policy needs documented scope, code, tests and remediation of existing
  copies; this amendment does not relax the no-personal-data constraint.
- **Retention.** The original proposal tied retention to published datasets,
  with annual review and deletion when no published derivative needed a package.
  It did not establish a period for today's unpublished holdings. Counsel must
  assess those holdings now and define necessary periods, review/deletion
  criteria and treatment of derived copies and backups. The original first
  annual review date, **2027-09-03**, is not permission to retain until then or
  to defer this assessment. Record the outcome in
  [known issues](../known-issues.md); retention compliance is not demonstrated.
- **Transparency and DPIA.** Article 14 information, timing and any claimed
  exception need assessment and documentation. An Article 14(5)(b) exception
  would require safeguards including making information publicly available.
  Whether Article 35 requires a DPIA is unresolved; none is claimed completed.
- **Security.** Local, gitignored storage and no third-party synchronisation
  remain policy requirements, not audited guarantees. Compression and checksums
  are not confidentiality controls. Access, backup and incident-response
  arrangements need assessment for raw and derived data alike.
- **Rights and incidents.** Data-subject requests require escalation across all
  affected holdings, not just the archive. This ADR decides neither an erasure
  exemption nor how immutability must yield to a valid request. Article 33
  requires breach documentation and notification to the supervisory authority
  without undue delay and, where feasible, within 72 hours of awareness, unless
  risk to rights and freedoms is unlikely. Article 34 requires communication to
  affected people without undue delay where high risk is likely, subject to its
  paragraph 3 exceptions. A breach assessment cannot wait for publication.

## Consequences

- **Release stays blocked.** No raw archive, normalised dataset or flag is
  cleared for publication. Nonpublication limits dissemination, not processing
  obligations; current holdings require review rather than a future launch check.
- **No full-fidelity derived fork is authorised.** The implemented classifier
  does not need contact names or beneficial-owner data. Structural drop counts
  support minimisation work; they do not prove all retained data necessary or
  anonymous, or that the current archive retention is lawful.
- **Beneficial ownership stays dropped.** Its possible use remains
  [open-work #15](../open-work.md#15-decide-whether-beneficial-ownership-can-be-analysed-at-all).
  An aggregate or opaque key is not automatically anonymous and grants no
  permission to reconstruct dropped identities.
- **No remediation is claimed by this amendment.** Existing datasets were not
  rebuilt, holdings were not deleted, and no counsel assessment or certification
  was obtained. The remaining work is in
  [open-work #11](../open-work.md#11-decide-the-publication-rule-for-unknown-natural-person-status)
  and [#14](../open-work.md#14-decide-what-to-do-about-personal-data-in-fields-that-are-not-contact-fields).

## What would change this

- A counsel-reviewed lawful-basis, retention, transparency and DPIA decision,
  recorded with its scope and required changes in a dated amendment or successor.
- A data-subject request, security incident or new leakage evidence requiring
  immediate reassessment; annual review is not a reason to wait.
- A classifier needing a dropped field, a new source or proposed publication:
  each requires a fresh assessment, not reliance on this unresolved proposal.
