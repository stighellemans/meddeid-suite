---
language:
- en
license: cc-by-4.0
pretty_name: MedDeID English synthetic clinical benchmark
task_categories:
- token-classification
tags:
- medical
- de-identification
- synthetic
- benchmark
- en-GB
- en-US
configs:
- config_name: default
  data_files:
  - split: test
    path: data/test.jsonl
---

# MedDeID English synthetic clinical benchmark

This is a fixed, human-validated benchmark containing 300 synthetic English
clinical documents: 150 `en-GB` and 150 `en-US`. It contains 1,717 primary PII
spans and 7,358 confirmed core-PII subannotation segments. It contains no real
patient notes or personal information.

Use the entire `test` split only for final evaluation:

```python
from datasets import load_dataset

benchmark = load_dataset(
    "stighellemans/meddeid-english-synthetic-benchmark",
    split="test",
)
```

Do not use the benchmark for training, validation, early stopping,
hyperparameter or threshold selection, prompt or rule development, or choosing
among candidate models whose final performance will be reported on it.

## Human review and subannotations

Every document and every identifying span in this benchmark was reviewed by a
human. After the main spans were finalised, their contents were reviewed a
second time at a finer level and divided into 7,358 subannotations.

Subannotations describe what is inside a larger identifying span. A name can be
split into given name, family name, initials and formatting; an address into
street, house number, municipality and postcode; and a date into day, month and
year. Every character inside a reviewed span is accounted for.

This finer layer helps answer a question that ordinary span-level evaluation
cannot: did a system remove the identifying content itself while preserving as
much surrounding non-identifying text as possible? It can distinguish a missed
surname from harmless punctuation, and an exact redaction from one that removes
additional clinical context. In the dataset, these pieces are stored under the
relevant primary span as `subannotations`.

## Models evaluated on this benchmark

The complete manuscript comparison is shown below. Recall is calculated over
the identifying annotation characters. The metadata-enabled condition applies
the same optional patient/caregiver-name recovery step to every system. Values
in parentheses are document-clustered 95% bootstrap confidence intervals.
Higher recall and lower non-PII redaction are better.

| Model or system | Recall, no metadata (%) | Recall, patient/caregiver metadata (%) | Non-PII redaction with metadata (%) |
|---|---:|---:|---:|
| [meddeid-english-synth](https://huggingface.co/stighellemans/meddeid-english-synth) | **99.96 (99.89–100.00)** | **99.96 (99.89–100.00)** | **0.009 (0.002–0.017)** |
| [GLiNER Multilingual PII](https://huggingface.co/urchade/gliner_multi_pii-v1) | 90.27 (88.99–91.42) | 90.59 (89.33–91.75) | 1.831 (1.663–2.001) |
| [OBI RoBERTa i2b2](https://huggingface.co/obi/deid_roberta_i2b2) | 86.64 (85.59–87.70) | 86.73 (85.68–87.78) | 0.194 (0.154–0.237) |
| [OpenMed SuperClinical 434M](https://huggingface.co/OpenMed/OpenMed-PII-SuperClinical-Large-434M-v1) | 75.10 (73.32–76.81) | 75.12 (73.34–76.83) | 0.480 (0.400–0.563) |
| [UCSF Philter](https://github.com/BCHSI/philter-ucsf) | 70.83 (69.45–72.20) | 70.94 (69.56–72.30) | 0.986 (0.899–1.076) |
| [OpenMed Multilingual Privacy Filter](https://huggingface.co/OpenMed/privacy-filter-multilingual) | 64.26 (62.04–66.45) | 69.45 (67.41–71.48) | 0.347 (0.292–0.405) |
| [OpenAI Privacy Filter](https://huggingface.co/openai/privacy-filter) | 64.38 (61.62–67.17) | 68.45 (65.89–71.01) | 0.051 (0.029–0.076) |

These results use the fixed `human-validated-v1` benchmark release. The
`meddeid-english-synth` result is an in-domain synthetic pipeline check, not
external or clinical validation.

## Intended use and limitations

This benchmark supports reproducible comparison of English clinical-text
de-identification systems. Its two locale profiles permit separate reporting
for UK- and US-style synthetic contexts. Synthetic-benchmark performance must
not be interpreted as performance on real clinical notes or as proof that
output is anonymous. Deployments require representative local validation.

## Integrity and project context

`CHECKSUMS.sha256` covers every repository file. See the
[annotation guideline](guidelines/annotation-guidelines-en.pdf) used for this
benchmark.

Developed by Stig Hellemans, Tom Stroobants, Elyne Scheurwegs, Pieter Meysman,
Philippe Jorens, and Kris Laukens at the University of Antwerp and Antwerp
University Hospital (UZA), with support from Research Foundation Flanders
(FWO), grant 1SA3226N.

## Citation

Please cite both the archived dataset version and the accompanying paper.

### Dataset

Hellemans, S., Stroobants, T., Scheurwegs, E., Meysman, P., Jorens, P., and
Laukens, K. (2026). *MedDeID English synthetic clinical corpus, benchmark and
annotation guideline* (v1) [Dataset]. Zenodo.
[https://doi.org/10.5281/zenodo.22127864](https://doi.org/10.5281/zenodo.22127864)

### Accompanying paper (forthcoming)

Hellemans, S., Stroobants, T., Scheurwegs, E., Meysman, P., Jorens, P., and
Laukens, K. *MedDeID for locally deployable clinical text de-identification
with real or synthetic training data.* Manuscript in preparation. The final
publication details and DOI will be added here when available.

## Licence

The benchmark and included guideline are licensed under CC BY 4.0.
