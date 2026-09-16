# SPDX-License-Identifier: AGPL-3.0-only
"""Links between office holders, companies and public money, checked by a person.

The pipeline proposes candidate links from official open data; a person confirms
every person-to-company link before it can appear in any output. Nothing is
published. `crony-eu/CLAUDE.md` is the constraint list and `scope.md` at the
repository root is the scope.

Stage order, each reading only the stage before it:

    fetch -> stage -> match -> review -> flag -> export

Fetching is the only networked stage. Everything below it runs offline and
byte-identically (constraint 4).
"""

from __future__ import annotations

#: Written into every run id and every manifest, so a staged file says which
#: version of this code produced it.
__version__ = "0.1.0"
