# Classifier hypotheses

One file per classifier, named after its module in `serenata/classify/`.
A classifier may not be merged without its file here. Each file must contain:

1. **Hypothesis** — one falsifiable paragraph: what pattern is anomalous and
   why it correlates with procurement risk.
2. **Source** — the documented risk indicator it implements, cited: ECA
   reports, OCP red flags, DIGIWHIST/Opentender literature.
3. **Method** — which structured eForms/TED fields, what test or threshold.
   No free text, no NLP, no network.
4. **Base rates** — measured on real historical data: how often it fires, on
   which population and period, and its known false-positive profile. A flag
   whose false-positive profile is unknown is not shippable.
5. **Limitations** — the innocent explanations a flag can have.

A flag is a statistical anomaly, never an accusation. These files are the
evidence for why an anomaly is worth a human verifier's time.
