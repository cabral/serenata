# SPDX-License-Identifier: AGPL-3.0-only
"""Proposing links, and the records of a person deciding about them.

Two append-only logs live here and they answer different questions.

`judgments` is about a person-to-company match: is this élu that officer?
Constraint 3 says only a `confirmed` judgment can put such an edge into an
export.

`buyer_verification` is about a contract's buyer: is the SIRET on this contract
the commune DECP says it is? ADR-0007 and its Amendment 1
(`crony-eu/docs/adr/0007-consolidator-derived-attributes.md`) require that
separately, and say in as many words that a confirmed person-company match does
not confirm the buyer mapping. They are
different facts about different entities, decided on different evidence, and
collapsing them would let one person's answer stand in for another's question.
"""
