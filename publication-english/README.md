# MedDeID English publication workspace

This directory defines the local, review-first release package for the English
synthetic dataset, fixed benchmark, and model. Source datasets, annotations,
and weights remain authoritative in their existing repositories and workspace.
The preparation script verifies and copies them; it never uploads or publishes.

## Build

The benchmark subannotation bundle must exist first:

```bash
MEDDEID_DATA_DIR="$PWD/workspaces/english-synthetic-subannotations" \
  npm --prefix repos/meddeid-subannotate run bundle
python scripts/prepare_english_publication.py
```

The build refuses a non-empty output directory. It creates:

- `dist/huggingface/meddeid-english-synthetic-corpus`;
- `dist/huggingface/meddeid-english-synthetic-benchmark`;
- `dist/huggingface/meddeid-english-synth`;
- `dist/zenodo/meddeid-english-synthetic-data-v2.zip`.

## Public targets

- dataset `stighellemans/meddeid-english-synthetic-corpus`;
- dataset `stighellemans/meddeid-english-synthetic-benchmark`;
- model `stighellemans/meddeid-english-synth`;
- one separate Zenodo data record for the corpus, benchmark, provenance, and
  English guideline.

Collection policy: add the English synthetic corpus, subannotated benchmark and
synthetic-trained English model to the existing MedDeID Collection.

The Zenodo data record remains separate from model weights and software. The
published version DOI is
[`10.5281/zenodo.22129255`](https://doi.org/10.5281/zenodo.22129255); the
concept DOI is `10.5281/zenodo.22127863`.

See `RELEASE_RUNBOOK.md` for the exact private-staging, verification, and
coordinated public-release commands.
