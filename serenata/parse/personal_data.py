"""Which source fields may never reach an intermediate record.

`docs/personal-data.md` is the authority; this module is that document in
executable form, and `tests/test_personal_data.py` fails if the two disagree.
Read the document for the reasoning behind each entry — it is a legal
constraint (constraint 2), and the reasoning is the part that has to survive.

Two rules, because the data needs two.

**Dropped outright.** Four subtrees whose contents are personal data wherever
they appear. Matched structurally, on a path's segments, rather than against an
enumerated list of leaves: a field TED adds inside `cac:Contact` next year is
then dropped on arrival rather than on discovery. Erring toward dropping is the
documented instruction, and a containment test is how it is kept true without
anyone re-reading the schema.

**Suppressed for a natural person.** eForms lets an organisation *be* a natural
person — a sole trader — and flags it with `efbc:NaturalPersonIndicator`. Where
that flag is true, values that are ordinary company data for every other
organisation become personal data: the name is the person's own, and the
registration identifier can be their national identity number. Those values are
suppressed while the organisation's opaque intra-notice key is kept, so the
record is anonymised rather than deleted.

The indicator is absent from about 90% of notices, and absent is "not provided",
not "false". That gap is real, is not resolvable from the XML, and is filed as
open-work #11 — a publication question, not an ingestion one.
"""

from __future__ import annotations

#: A path passing through any of these carries personal data regardless of
#: which leaf it ends at. Contact blocks name a human to telephone; a UBO *is*
#: a natural person; a technical committee person is a named evaluator.
DROPPED_SEGMENTS = frozenset(
    {
        "cac:Contact",
        "efac:UltimateBeneficialOwner",
        "cac:TechnicalCommitteePerson",
    }
)

#: Free prose written by the publisher to explain why a field was withheld. It
#: can embed a name, and constraint 5 keeps the pipeline to structured fields,
#: so there is no use here to weigh against the risk. The rest of the
#: FieldsPrivacy block is coded and is kept.
DROPPED_SUFFIXES = ("efac:FieldsPrivacy/efbc:ReasonDescription",)

#: The element that says an organisation is a natural person. Kept, and not
#: personal data itself: it is the only in-band signal the rule below can use.
NATURAL_PERSON_INDICATOR = "efbc:NaturalPersonIndicator"

#: Paths within an ``efac:Organization`` that identify it. Suppressed when that
#: organisation is flagged as a natural person. ``cac:PartyIdentification`` is
#: deliberately absent: it is a notice-scoped token (``ORG-0001``) that names
#: nobody, and keeping it preserves the structure the dataset is built on.
IDENTIFYING_ORGANISATION_PREFIXES = (
    "efac:Company/cac:PartyName",
    "efac:Company/cac:PartyLegalEntity",
    "efac:Company/cac:PostalAddress",
    "efac:TouchPoint/cac:PartyName",
    "efac:TouchPoint/cac:PostalAddress",
)


def is_dropped(path: str) -> bool:
    """True if ``path`` may never be read into an intermediate record.

    ``path`` is a namespace-prefixed element path as ``serenata.survey.paths``
    produces them. Consulted *before* a value is read: dropping means never
    constructing, not constructing and then removing.
    """
    if DROPPED_SEGMENTS.intersection(path.split("/")):
        return True
    return path.endswith(DROPPED_SUFFIXES)


def suppressed_for_natural_person(path_within_organisation: str) -> bool:
    """True if this path identifies the organisation it sits in.

    ``path_within_organisation`` is relative to an ``efac:Organization``
    element, so ``efac:Company/cac:PartyName/cbc:Name`` rather than the whole
    path from the notice root. Consulted only for an organisation whose
    ``efbc:NaturalPersonIndicator`` is true; an absent indicator is not a false
    one and does not trigger this.
    """
    return path_within_organisation.startswith(IDENTIFYING_ORGANISATION_PREFIXES)
