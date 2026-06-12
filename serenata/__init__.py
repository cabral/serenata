"""Serenata Europa: anomaly detection pipeline for EU public procurement data.

The pipeline is a chain of independently runnable stages::

    fetch -> parse -> normalise -> classify -> publish

The constraints binding every stage live in ``CLAUDE.md`` at the repository
root. The short version: fields that could name a natural person are dropped
at parse time, ``fetch`` is the only stage allowed network access, and every
stage is deterministic — same input and same code produce the same bytes.
"""
