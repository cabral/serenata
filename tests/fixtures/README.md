# Test fixtures

Offline inputs for the test suite; nothing here is fetched at test time.
Two kinds of fixture are allowed:

- obviously synthetic notices (impossible IDs, names like "EXAMPLE BODY"),
- real public notices reproduced byte-for-byte, named after their notice ID.

Never plausible-looking fabrications, and never anything containing a natural
person's name.

Still empty: the parse tests build their notices in memory, which keeps a
fixture and the test that reads it in one file. Committing a real sample package
is [open-work #7](../../docs/open-work.md#7-commit-a-small-sample-package-for-end-to-end-tests).
