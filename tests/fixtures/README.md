# Test fixtures

Offline inputs for the test suite; nothing here is fetched at test time.
Two kinds of fixture are allowed:

- obviously synthetic notices (impossible IDs, names like "EXAMPLE BODY"),
- real public notices reproduced byte-for-byte, named after their notice ID.

Never plausible-looking fabrications, and never anything containing a natural
person's name.

Still empty, and now for a smaller reason than before: the parse and normalise
tests build their notices in the file that reads them, which keeps a fixture and
its assertion together.

The package-shaped fixture that used to be missing lives in
[`data/sample/`](../../data/sample/), where `tests/test_sample_package.py` runs
the whole pipeline over it. Put a fixture here when it belongs to one test, and
there when it belongs to the pipeline.
