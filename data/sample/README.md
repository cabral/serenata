# Committed sample data

`data/` is a gitignored workspace for fetched raw XML and generated Parquet.
This directory is the one committed exception: a tiny sample of notices for
end-to-end tests. The same rules as `tests/fixtures/` apply — obviously
synthetic notices or accurately reproduced real public ones, never
plausible-looking fabrications, never anything containing a natural person's
name. Empty until the pipeline can read it.
