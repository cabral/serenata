# Maintainer scripts

Scripts run by hand, by someone updating the repository. **Nothing here is part
of the pipeline**, and nothing in `serenata/` imports from this directory.

That separation is the point rather than tidiness. Constraint 4 says fetching is
the only networked stage, and `tests/test_constraints.py` enforces it over
`serenata/` — so a script that needs the network to *produce* something the
pipeline reads lives out here, and what it writes is committed data the pipeline
reads offline.

| Script | What it writes | When to run it |
|---|---|---|
| [`generate_sdk_privacy.py`](generate_sdk_privacy.py) | `serenata/normalise/sdk_privacy.py` | When the eForms SDK gains a privacy code, or when notices start declaring an SDK version it was not generated against |

## Running one

```
uv run python tools/generate_sdk_privacy.py
uv run ruff format serenata/normalise/sdk_privacy.py
git diff
```

Review the diff. These scripts write files that are read as authoritative, so an
unexplained change to one is a reason to stop, not to commit. Each script fails
loudly rather than writing something it cannot justify — `generate_sdk_privacy.py`
refuses to write at all if the SDK versions it checks disagree about which field
a code withholds.
