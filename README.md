# MedDeID suite release coordinator

This repository pins and verifies the independently released components and
public artifacts that make up MedDeID. End users normally install an individual
component or follow the [public documentation](https://stighellemans.github.io/meddeid.github.io/);
they do not need this coordinator checkout.

## Public components

| Component | Purpose |
|---|---|
| [`meddeid`](https://github.com/stighellemans/meddeid) | Python API, CLI, batch inference, and HTTP service |
| [`meddeid-core`](https://github.com/stighellemans/meddeid-core) | Canonical schema, taxonomy, normalization, and validation |
| [`meddeid-language-nl`](https://github.com/stighellemans/meddeid-language-nl) | Dutch and `nl-BE` language capabilities |
| [`meddeid-data`](https://github.com/stighellemans/meddeid-data) | Project import, splits, and synthetic generation |
| [`meddeid-training`](https://github.com/stighellemans/meddeid-training) | Selection, refit, training, and bundle export |
| [`meddeid-eval`](https://github.com/stighellemans/meddeid-eval) | Metrics and stability analysis |
| [`meddeid-annotate`](https://github.com/stighellemans/meddeid-annotate) | Primary-span annotation |
| [`meddeid-curate`](https://github.com/stighellemans/meddeid-curate) | Optional multi-reviewer reconciliation |
| [`meddeid-subannotate`](https://github.com/stighellemans/meddeid-subannotate) | Gold-only core-PII subannotation |

`suite-lock.yaml` is the public release contract. It records package versions
and hashes, repository commits, container digests, model and dataset revisions,
the archival DOI, language/profile contracts, and smoke-test tolerances.

## Public release endpoints

- npm language capability: [`@meddeid/language-nl@0.1.0`](https://www.npmjs.com/package/@meddeid/language-nl)
- Hugging Face project collection: [MedDeID](https://huggingface.co/collections/stighellemans/meddeid)
- hosted non-clinical demo: [`stighellemans/meddeid-demo`](https://huggingface.co/spaces/stighellemans/meddeid-demo)
- versioned data and guideline archive: [Zenodo v2](https://doi.org/10.5281/zenodo.21992866)
- all archive versions: [Zenodo concept DOI](https://doi.org/10.5281/zenodo.21890964)

## Verify the release

Install the exact released Python packages, then run:

```bash
python -m pip install \
  'meddeid[server]==0.1.1' \
  'meddeid-data==0.2.1' \
  'meddeid-eval==0.2.1' \
  'meddeid-training[train]==0.1.1' \
  'PyYAML>=6'
python scripts/verify_release.py
python scripts/verify_new_researcher_pilot.py --full
```

GitHub Actions runs this from a clean Ubuntu environment and verifies the
released containers by immutable digest. The six-note fixture is wholly
synthetic and tests plumbing, not scientific model quality.

## Safety

Local execution reduces data movement but does not guarantee anonymity.
Clinical deployments require representative local validation, governance,
access controls, monitoring, and incident response. Never attach patient text,
credentials, or restricted artifacts to a public issue.

Code is licensed AGPL-3.0-only. Models, datasets, guidelines, and lookup
resources retain the terms recorded in `suite-lock.yaml` and their artifact
cards.
