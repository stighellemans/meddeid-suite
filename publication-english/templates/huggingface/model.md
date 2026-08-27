---
language:
- en
license: agpl-3.0
library_name: meddeid
pipeline_tag: token-classification
base_model: FacebookAI/roberta-base
tags:
- medical
- de-identification
- privacy
- synthetic-data
- en-GB
- en-US
datasets:
- stighellemans/meddeid-english-synthetic-corpus
---

# meddeid-english-synth

`meddeid-english-synth` is a clinical-text de-identification model for explicit
`en-GB` and `en-US` runtime profiles. It predicts character-offset PII spans and
is packaged with its tokenizer, configuration, labels, and MedDeID bundle
contract. No real patient notes were used for training.

## Intended use

The model is a research and local-deployment starting point for detecting
identifying information in English clinical text. It does not make text
anonymous by itself, cannot guarantee that every identifier is removed, and
requires validation for the target institution and use case. Sensitive text
should be processed inside the user's governance boundary, not in a public
demonstration service.

## Use with MedDeID

```bash
pip install meddeid
```

Select the relevant locale explicitly:

```python
from meddeid import Deidentifier

engine = Deidentifier.from_pretrained(
    "stighellemans/meddeid-english-synth",
    language_profile="en-GB",  # or en-US
    device="cpu",
)
result = engine("Patient Alex Example attended on 27 August 2026.")
print(result.spans)
print(result.deid_text)
```

For an air-gapped installation, pre-stage the immutable repository revision:

```bash
hf download stighellemans/meddeid-english-synth \
  --revision YOUR_PINNED_COMMIT \
  --local-dir ./meddeid-english-synth
```

## Architecture and training

The model uses `FacebookAI/roberta-base` pinned at revision
`e2da8e2f811d1448a5b465c236feacd80ffbac7b`, with separate BIO and 14-way
entity classification heads. It processes overlapping 512-token windows with a
64-token overlap.

Epoch selection used a held-out partition of the synthetic development corpus.
The deliverable model was reinitialised from the pinned base encoder and refit
for four epochs on all 6,700 development documents. The fixed 300-document
benchmark was evaluated once after selection and refitting.

## Benchmark results

On the human-validated English synthetic benchmark, the model-native typed
entity evaluation produced precision 99.19%, recall 99.48%, and F1 99.33%
(1,717 gold spans). The strict exact-boundary-and-label slice produced
precision 99.01%, recall 99.30%, and F1 99.16%. Exact-slice F1 was 99.07% for
`en-GB` and 99.24% for `en-US`.

### Comparison with other systems

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

These are synthetic-benchmark point estimates. They are not estimates of
performance on real clinical notes or another institution.

## Predicted labels

The model predicts `Address_Location:Caregiver`, `Address_Location:Other`,
`Address_Location:Patient`, `Age_Birthdate`, `Contactdetails`, `Date`,
`ID:Caregiver`, `ID:Patient`, `Name:Caregiver`, `Name:Other`, `Name:Patient`,
`Organization:Healthcare`, `Organization:Other`, and `Profession`.

## Limitations

- Training and public evaluation data are synthetic.
- Coverage of specialties, institutions, dialects, styles, and identifier
  formats is incomplete.
- Locale selection does not replace institution-specific validation.
- The model can miss identifiers and remove clinically meaningful text.
- Threshold, decoder, software, and post-processing changes can change results.

## Reproducibility and files

- `model.safetensors`: weights;
- `bundle.json`: labels, windowing, base revision, and locale profiles;
- `config.json` and tokenizer files: self-contained encoder assets;
- `train_metrics.json` and `eval.json`: selection/refit and benchmark metrics;
- `MODEL_PROVENANCE.json` and `CHECKSUMS.sha256`: provenance and integrity.

Machine-specific absolute path prefixes in the run metadata are replaced with
the portable `${MEDDEID_SUITE}` marker. Numeric results and configuration
values are unchanged. Reproducible use should pin the immutable Hub commit.

## Project, citation, and licence

Developed by Stig Hellemans, Tom Stroobants, Elyne Scheurwegs, Pieter Meysman,
Philippe Jorens, and Kris Laukens at the University of Antwerp and Antwerp
University Hospital (UZA), with support from Research Foundation Flanders
(FWO), grant 1SA3226N.

### Model

```bibtex
@software{hellemans_2026_meddeid_english_synth,
  author    = {Hellemans, Stig and Stroobants, Tom and Scheurwegs, Elyne and Meysman, Pieter and Jorens, Philippe and Laukens, Kris},
  title     = {meddeid-english-synth},
  year      = {2026},
  publisher = {Hugging Face},
  url       = {https://huggingface.co/stighellemans/meddeid-english-synth}
}
```

### Benchmark dataset

Hellemans, S., Stroobants, T., Scheurwegs, E., Meysman, P., Jorens, P., and
Laukens, K. (2026). *MedDeID English synthetic clinical corpus, benchmark and
annotation guideline* (v1) [Dataset]. Zenodo.
[https://doi.org/10.5281/zenodo.22127864](https://doi.org/10.5281/zenodo.22127864)

### Accompanying paper (forthcoming)

Hellemans, S., Stroobants, T., Scheurwegs, E., Meysman, P., Jorens, P., and
Laukens, K. *MedDeID for locally deployable clinical text de-identification
with real or synthetic training data.* Manuscript in preparation. The final
publication details and DOI will be added here when available.

The model bundle is licensed under AGPL-3.0-only. The upstream RoBERTa base
model remains subject to its own terms and attribution requirements.
