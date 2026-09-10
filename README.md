# MedDeID suite release coordinator

This repository pins and verifies the independently released components and
public artifacts that make up MedDeID. End users normally install an individual
component or follow the [public documentation](https://stighellemans.github.io/meddeid/);
they do not need this coordinator checkout.

The prevalent cross-component workflows now use `meddeid` as a guided front
door:

```bash
python -m pip install 'meddeid[research]'
meddeid guide
meddeid workflow init TYPE WORKSPACE
meddeid workflow next WORKSPACE
```

This records scientific branches instead of inferring them from filenames or
installed tools. Component CLIs remain available independently. See the
[workflow CLI reference](https://stighellemans.github.io/meddeid/reference/workflow-cli/).

## Public components

| Component | Purpose |
|---|---|
| [`meddeid`](https://github.com/stighellemans/meddeid) | Python API, CLI, batch inference, and HTTP service |
| [`meddeid-core`](https://github.com/stighellemans/meddeid-core) | Canonical schema, taxonomy, normalization, validation, and suite-wide age policy |
| [`meddeid-language-nl`](https://github.com/stighellemans/meddeid-language-nl) | Strictly separated `nl-BE` and `nl-NL` language capabilities |
| [`meddeid-language-en`](https://github.com/stighellemans/meddeid-language-en) | Strictly separated `en-GB` and `en-US` language capabilities |
| [`meddeid-data`](https://github.com/stighellemans/meddeid-data) | Project import, splits, and synthetic generation |
| [`meddeid-training`](https://github.com/stighellemans/meddeid-training) | Selection, refit, training, and bundle export |
| [`meddeid-eval`](https://github.com/stighellemans/meddeid-eval) | Metrics and stability analysis |
| [`meddeid-annotate`](https://github.com/stighellemans/meddeid-annotate) | Primary-span annotation |
| [`meddeid-curate`](https://github.com/stighellemans/meddeid-curate) | Optional multi-reviewer reconciliation |
| [`meddeid-subannotate`](https://github.com/stighellemans/meddeid-subannotate) | Gold-only core-PII subannotation |
| [`meddeid.github.io`](https://github.com/stighellemans/meddeid.github.io) | Redirects legacy documentation URLs to the maintained site |

`suite-lock.yaml` is the public release contract. It records package versions
and hashes, repository commits, container digests, tagged model revisions and
DOIs, dataset revisions, archival DOIs, language/profile contracts, exact study
software revisions, and smoke-test tolerances.

The [suite 0.3.1 release lock](suite-lock.yaml) records `meddeid==0.4.2`,
the corrected CPU image, the compatible validated PyTorch CUDA image, a
weight-free TensorRT gateway and runtime, and model-specific T4 and Ampere+
plans for the public Dutch and English models. The lock records the image and
plan digests together and marks compatible GPU artifacts as reused. End
users choose hardware, model revision, and language profile; Compose resolves
the internal TensorRT parts. CPU, CUDA, and TensorRT remain separate downloads
so users do not receive frameworks for hardware they are not using. See the
[release runbook](RELEASE.md) and the retained
[resolved release record](release/0.3.1-resolved.yaml).

The Dutch and English model repositories have immutable `v1.0.1` tags and
version-specific Hugging Face DOIs. The English language component, synthetic
corpus, human-reviewed benchmark, and synthetic model are public and pinned in
the 0.3.1 lock. Bare `en` is not a valid profile selection.

## Public release endpoints

- English model: [`stighellemans/meddeid-english-synth`](https://huggingface.co/stighellemans/meddeid-english-synth)
- English model DOI: [10.57967/hf/10306](https://doi.org/10.57967/hf/10306)
- Dutch model: [`stighellemans/meddeid-dutch-synth`](https://huggingface.co/stighellemans/meddeid-dutch-synth)
- Dutch model DOI: [10.57967/hf/10304](https://doi.org/10.57967/hf/10304)
- English synthetic corpus: [`stighellemans/meddeid-english-synthetic-corpus`](https://huggingface.co/datasets/stighellemans/meddeid-english-synthetic-corpus)
- English human-reviewed benchmark: [`stighellemans/meddeid-english-synthetic-benchmark`](https://huggingface.co/datasets/stighellemans/meddeid-english-synthetic-benchmark)
- English data and guideline archive: [Zenodo v3](https://doi.org/10.5281/zenodo.22689857)
- npm Dutch language capability: [`@meddeid/language-nl`](https://www.npmjs.com/package/@meddeid/language-nl)
- npm English language capability: [`@meddeid/language-en`](https://www.npmjs.com/package/@meddeid/language-en)
- Hugging Face project collection: [MedDeID](https://huggingface.co/collections/stighellemans/meddeid)
- hosted non-clinical demo: [`stighellemans/meddeid-demo`](https://huggingface.co/spaces/stighellemans/meddeid-demo)
- Dutch data and guideline archive: [Zenodo v3](https://doi.org/10.5281/zenodo.22689856)
- all Dutch archive versions: [Zenodo concept DOI](https://doi.org/10.5281/zenodo.21890964)
- all English archive versions: [Zenodo concept DOI](https://doi.org/10.5281/zenodo.22127863)

## Verify the release

From the released coordinator checkout, install the exact locked Python
packages and run the public verifiers:

```bash
python -m pip install 'PyYAML>=6'
# Install ORAS 1.3 or later to verify the TensorRT plan artifacts.
python scripts/release_requirements.py > /tmp/meddeid-release-requirements.txt
python -m pip install --requirement /tmp/meddeid-release-requirements.txt
python scripts/verify_release.py
python scripts/verify_new_researcher_pilot.py --installed-packages --full
```

GitHub Actions runs this from a clean Ubuntu environment and verifies the
released containers by immutable digest. The six-note fixture is wholly
synthetic and tests plumbing, not scientific model quality.

## Safety

Local execution reduces data movement but does not guarantee anonymity.
Clinical deployments require representative local validation, governance,
access controls, monitoring, and incident response. Never attach patient text,
credentials, or restricted artifacts to a public issue.

## Licensing

Coordinator code is licensed AGPL-3.0-only with the MedDeID Private Fine-Tuning
Exception, version 1.0. The exception permits private training data and
resulting private fine-tuned weights to remain confidential; MedDeID code
modifications remain subject to AGPL-3.0-only. See `NOTICE` and
`MEDDEID-PRIVATE-FINE-TUNING-EXCEPTION-1.0.txt`. Components, models, datasets,
guidelines, and lookup resources retain the terms recorded in `suite-lock.yaml`
and their own notices or artifact cards.
