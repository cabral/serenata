# Maintainer scripts

Scripts for maintaining the repository, run by a maintainer or an explicitly
authorized external controller. **Nothing here is part of the pipeline**, and
nothing in `serenata/` imports from this directory.

That separation is the point rather than tidiness. Constraint 4 says fetching is
the only networked stage, and `tests/test_constraints.py` enforces it over
`serenata/` — so a script that needs the network to *produce* something the
pipeline reads lives out here, and what it writes is committed data the pipeline
reads offline.

| Script | Output | When to run it |
|---|---|---|
| [`generate_sdk_privacy.py`](generate_sdk_privacy.py) | `serenata/normalise/sdk_privacy.py` | When the eForms SDK gains a privacy code, or when notices start declaring an SDK version it was not generated against |
| [merge_guard.py](merge_guard.py) | Read-only eligibility/hold reports only; no GitHub writes or merge execution | External read-only evaluation under the [automation procedure](../docs/automation/README.md); repository policy disabled |

## Running the SDK generator

```
uv run python tools/generate_sdk_privacy.py
uv run ruff format serenata/normalise/sdk_privacy.py
git diff
```

Review the diff. The generator writes a file read as authoritative, so an
unexplained change is a reason to stop, not to commit. It refuses to write if the
SDK versions it checks disagree about which field a code withholds.

The eligibility checker is different: its HTTP client permits only bodyless GETs
and rejects other requests before connection. `revalidate()` only rereads policy
and evidence; legacy `--merge` is rejected with `merge_execution_not_implemented`
before access, and `--lock` no longer exists. There is no write switch. An enabled
external policy permits evaluation only, using repository-scoped Contents,
Metadata, Actions, Pull requests and Administration read permissions. Reports
grant no action authority. The manual workflow's disabled policy and default
token lacking Administration read cannot become a working evaluation setup by
merely flipping the policy. Hosted compatibility and any future executor remain
separate, unresolved work described in the automation procedure.
