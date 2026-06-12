"""Stage 4: hypothesis classifiers over the normalised dataset.

One module per classifier. A classifier may not merge without its file in
``docs/hypotheses/``: a written, falsifiable hypothesis citing its
risk-indicator source, tests, and base rates measured on real historical
data. Classifiers read structured fields only (no free text, no NLP), run
offline, and are deterministic. Their output is statistical anomalies with
possible innocent explanations — never accusations.
"""
