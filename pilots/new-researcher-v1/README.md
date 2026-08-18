# MedDeID new-researcher pilot v1

This folder records a first-time-user walkthrough of the public MedDeID
research pipeline using six wholly synthetic Dutch clinical notes. It contains
no real patient or caregiver data.

- `RUNBOOK.md` is the current copy-paste tutorial and verification path.
- `FIRST_ITERATION_REPORT.md` records results and prioritized improvements.

## Dataset

- `00-plain-text/`: the six import-ready UTF-8 notes.
- `01-source/annotations.jsonl`: canonical unannotated input.
- `02-primary/annotator-a.jsonl`: first independent primary annotation.
- `02-primary/annotator-b.jsonl`: second independent primary annotation with
  deliberate missing, label, and boundary disagreements.
- `03-adjudication/`: merge outputs and the adjudicated primary gold.
- `04-subannotation/`: core-PII subannotation and evaluation bundle.
- `05-evaluation/`: prediction records and metric output.
- `06-training/`: tiny split/handoff artifacts. These exercise plumbing only;
  six documents cannot produce a scientifically useful model.

The current checked handoff has 7/7 disagreements resolved, 22/22 primary spans
confirmed, and 92 reviewed core-PII segments. Run
`python scripts/verify_new_researcher_pilot.py` from the suite root for the
fast integrity gate, or add `--full` for the actual training/inference slice.

## Safety

All people, identifiers, institutions, addresses, and contact details in this
pilot are invented for testing.
