"""Escaping by default.

Every page is assembled from text that came from somewhere: a document in this
repository, a measured figure, this module's own copy. The failure to prevent is
a stray ``<`` or ``&`` turning a sentence into markup, or a document edited next
month injecting some. So nothing is trusted unless it says it is: a plain ``str``
is escaped on the way in, and only an `Html` value, which something in this
package produced deliberately, passes through untouched.
"""

from __future__ import annotations

import html
from collections.abc import Iterable


class Html(str):
    """Text that is already HTML. Produced by this package, never by a document."""

    __slots__ = ()


def esc(value: object) -> Html:
    """``value`` as HTML: escaped unless it already is."""
    if isinstance(value, Html):
        return value
    return Html(html.escape(str(value), quote=True))


def join(parts: Iterable[object], sep: str = "") -> Html:
    """Concatenate ``parts``, escaping any that are not already HTML."""
    return Html(sep.join(esc(part) for part in parts))


def fill(template: str, /, **values: object) -> Html:
    """Substitute ``{name}`` in a template that is source code, not data.

    The template is trusted because it is a literal in this package. The values
    are not, and are escaped unless they are `Html`. A template with a literal
    brace doubles it, which the CSS and script (kept in ``static/``) never need.
    """
    return Html(template.format_map({name: esc(v) for name, v in values.items()}))
