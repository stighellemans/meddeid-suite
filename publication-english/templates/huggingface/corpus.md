---
language:
- en
license: cc-by-4.0
pretty_name: MedDeID English synthetic clinical corpus
task_categories:
- token-classification
tags:
- medical
- de-identification
- synthetic
- en-GB
- en-US
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train.jsonl
---

# MedDeID English synthetic clinical corpus

This repository contains 6,700 synthetic English clinical documents with
character-offset de-identification spans: 3,350 `en-GB` and 3,350 `en-US`
documents. It contains no real patient notes or personal information. The
complete corpus was used to train
[`meddeid-english-synth`](https://huggingface.co/stighellemans/meddeid-english-synth).

## Split policy

All records are exposed in one `train` split. There is no publisher-defined
validation split. Users who tune a model must create and report their own
development partition. The separate
[`meddeid-english-synthetic-benchmark`](https://huggingface.co/datasets/stighellemans/meddeid-english-synthetic-benchmark)
must not be used for training, model selection, prompt development, threshold
selection, or post-processing development when reporting benchmark results.

```python
from datasets import load_dataset

corpus = load_dataset(
    "stighellemans/meddeid-english-synthetic-corpus",
    split="train",
)
```

## Record contract

Each row uses the canonical MedDeID document schema:

- `document_id`: stable synthetic identifier;
- `text`: synthetic clinical document;
- `spans`: primary PII spans with absolute, half-open Unicode-code-point offsets;
- `metadata_json`: the lossless JSON serialization of generation metadata,
  including the exact `en-GB` or `en-US` profile.

The unchanged authoritative source remains available as
`source/development.jsonl`. The viewer copy represents only `metadata` as the
string column `metadata_json` because the source metadata is intentionally
heterogeneous. Decoding the string reconstructs the original metadata object.

The 14 annotation labels are `Address_Location:Caregiver`,
`Address_Location:Other`, `Address_Location:Patient`, `Age_Birthdate`,
`Contactdetails`, `Date`, `ID:Caregiver`, `ID:Patient`, `Name:Caregiver`,
`Name:Other`, `Name:Patient`, `Organization:Healthcare`,
`Organization:Other`, and `Profession`.

## Creation, intended use, and limitations

The documents combine synthetic clinical cases with synthetic UK- and US-style
identity and administrative fields. Public institutions may appear as context,
but person, contact, address, and identifier combinations are synthetic.

The corpus is intended for de-identification research and model development.
Synthetic text does not reproduce every specialty, institution, writing style,
identifier format, or documentation error. Results on these documents do not
establish performance or safety on real clinical notes. Local validation and a
separate disclosure-risk assessment remain necessary.

## Integrity and project context

`CHECKSUMS.sha256` covers the viewer copy, unchanged source, source manifest,
guideline, card, and licence. The applicable English annotation guideline is
included under `guidelines/`.

Developed by Stig Hellemans, Tom Stroobants, Elyne Scheurwegs, Pieter Meysman,
Philippe Jorens, and Kris Laukens at the University of Antwerp and Antwerp
University Hospital (UZA), with support from Research Foundation Flanders
(FWO), grant 1SA3226N.

## Citation

Please cite both the archived dataset version and the accompanying paper.

```bibtex
@dataset{hellemans2026meddeidenglishdata,
  author    = {Hellemans, Stig and Stroobants, Tom and Scheurwegs, Elyne and Meysman, Pieter and Jorens, Philippe and Laukens, Kris},
  title     = {MedDeID English synthetic clinical corpus, benchmark and annotation guideline},
  year      = {2026},
  publisher = {Zenodo},
  version   = {v1},
  doi       = {10.5281/zenodo.22127864},
  url       = {https://doi.org/10.5281/zenodo.22127864}
}
```

### Accompanying paper (forthcoming)

Hellemans, S., Stroobants, T., Scheurwegs, E., Meysman, P., Jorens, P., and
Laukens, K. *MedDeID for locally deployable clinical text de-identification
with real or synthetic training data.* Manuscript in preparation. The final
publication details and DOI will be added here when available.

## Licence

The dataset and included guideline are licensed under CC BY 4.0.
