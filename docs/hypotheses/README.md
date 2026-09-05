# Classifier hypotheses

One file per classifier, named after its module in `serenata/classify/`.
A classifier may not be merged without its file here. Each file must contain:

1. **Hypothesis** — one falsifiable paragraph: what pattern is anomalous and
   why it correlates with procurement risk.
2. **Source** — the documented risk indicator it implements, cited: ECA
   reports, OCP red flags, DIGIWHIST/Opentender literature.
3. **Method** — which structured eForms/TED fields, what test or threshold.
   No free text, no NLP, no network.
4. **Base rates** — measured on real historical data: how often it fires, on
   which population and period, and its known false-positive profile. A flag
   whose false-positive profile is unknown is not shippable.
5. **Limitations** — the innocent explanations a flag can have.

A flag is a statistical anomaly, never an accusation. These files are the
evidence for why an anomaly is worth a human verifier's time.

## Mechanical admission

[The constraint tests](../../tests/test_constraints.py) discover implemented
classifiers by their module-level `RULE`, `RULE_VERSION`, and `flags` contract.
Each needs the matching hypothesis and a nonempty companion SQL file. An
implemented hypothesis cannot be `scoped`, `rejected`, or unmeasured; nonempty
base-rate prose alone is not measurement metadata.

Keep one `Status:` line and one `## Measurement metadata` section containing
exactly one fenced `toml` block. The
[single-bid hypothesis](single_bid_in_segment.md#measurement-metadata) is an
actual historical record, not a template of numbers to copy. The block has two
tables, with all fields required and unknown fields rejected:

- `admission`: `current_rule_version` must equal the classifier's literal
   positive-integer `RULE_VERSION`. `current_measurement` is `measured` only
   when the recorded measurement version matches; otherwise it must be `pending`.
- `measurement`: `rule_version`, `measured_on`, `period_start`, `period_end`,
   `package_ids`, `query_file`, `query_revision`, and the seven counts below.
   Versions are positive integers. Dates are unquoted TOML local dates and must
   satisfy `period_start <= period_end <= measured_on`. These are explicit
   corpus bounds, not necessarily exact observed publication extrema.
   `package_ids` is a nonempty, sorted, unique list of TED daily-package IDs in
   `yyyynnnnn` format, with a nonzero issue and years inside the period.
- Counts: `notice_count` is the corpus notice total; `population_count` is the
   positive number of eligible observational units; `population_notice_count`
   is their distinct notice count. `covered_count` and `uncovered_count` partition
   that population into units with and without a usable baseline.
   `flagged_count` cannot exceed coverage; `flagged_notice_count` cannot exceed
   either flags or population notices, and is zero exactly when flags are zero.
   All counts are nonnegative integers, not strings, fractions, or booleans.
- `query_file` names the companion SQL file beside the hypothesis, without a
   directory. `query_revision` is the full 40-character Git commit identifying
   the measured SQL. A current measurement may instead use `working-tree` while
   its code and query are reviewed together. Historical evidence must pin a
   commit, since the current companion query may implement a different version.

| Implemented status | Measurement accepted by local developer tests |
|---|---|
| `measured` | Matches current `RULE_VERSION` |
| `building` | Matches current version, or historical evidence with current measurement explicitly `pending` |
| `live` | Matches current `RULE_VERSION`; human release and publication gates still apply |

**Before merge, every implemented classifier must have a measurement matching
its current `RULE_VERSION`, including `building` rules.** CI enforces this with
`uv run --locked pytest --cov-fail-under=95 --require-current-measurements`.
Default local developer tests omit this option so explicitly pending work can
be tested offline; passing them is not merge readiness. The mandatory pre-merge
gate validates the recorded metadata without reading real datasets or running
measurement queries. It can also be run separately with
`uv run --locked pytest tests/test_constraints.py::TestClassifierHypotheses --require-current-measurements`.

An eligibility or threshold change invalidates the old measurement **for the
new version**, not its historical record. Keep that record labelled with its
measured version, set status to `building` and current measurement to `pending`,
then remeasure **before merge**, not merely before release. Do not relabel
historical counts as new evidence. The single-bid rule went through this cycle
for versions 2 and 3: its 96 flags are recorded as a version-3 measurement
because version 3 was rerun to produce them, not because an earlier version had
measured something close.

**This gate checks metadata sanity, not truth or approval.** It does not read
real data, rerun SQL, verify that a Git revision contains the claimed query,
resolve issue IDs to exact publication dates, or prove that the recorded counts
came from the stated corpus. Nor does it establish falsifiability, sensitivity,
false-positive rates, legal clearance, or permission to merge, release or publish.
Those remain review and measurement obligations even when the tests pass;
explicit human authorization is still required.
