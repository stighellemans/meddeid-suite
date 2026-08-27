# English release runbook

Run commands from the `meddeid-suite` directory. The local build is already
complete; rebuild only after an intentional source change and into an empty
output directory.

## 1. Final local review

Review:

- `publication-english/dist/huggingface/meddeid-english-synthetic-corpus/README.md`;
- `publication-english/dist/huggingface/meddeid-english-synthetic-benchmark/README.md`;
- `publication-english/dist/huggingface/meddeid-english-synth/README.md`;
- `publication-english/dist/zenodo/meddeid-english-synthetic-data-v1/metadata.json`;
- `publication-english/RELEASE_CHECKLIST.md`.

The account currently configured for the Hugging Face CLI should be checked
before any write:

```bash
hf auth whoami
```

## 2. Private Hugging Face staging

Create the three repositories privately:

```bash
hf repos create stighellemans/meddeid-english-synthetic-corpus \
  --type dataset --private
hf repos create stighellemans/meddeid-english-synthetic-benchmark \
  --type dataset --private
hf repos create stighellemans/meddeid-english-synth \
  --type model --private
```

Upload one local folder per repository:

```bash
hf upload stighellemans/meddeid-english-synthetic-corpus \
  publication-english/dist/huggingface/meddeid-english-synthetic-corpus . \
  --type dataset --commit-message "Stage MedDeID English synthetic corpus v1"

hf upload stighellemans/meddeid-english-synthetic-benchmark \
  publication-english/dist/huggingface/meddeid-english-synthetic-benchmark . \
  --type dataset --commit-message "Stage MedDeID English synthetic benchmark v1"

hf upload stighellemans/meddeid-english-synth \
  publication-english/dist/huggingface/meddeid-english-synth . \
  --type model --commit-message "Stage MedDeID English model v1"
```

Record the immutable commit SHA returned for each repository. Inspect the cards,
files, licences, and model metadata while all repositories remain private.

## 3. Zenodo draft

Create a new dataset upload in Zenodo and use the values from
`publication-english/dist/zenodo/meddeid-english-synthetic-data-v1/metadata.json`.
Upload only:

`publication-english/dist/zenodo/meddeid-english-synthetic-data-v1.zip`

Preview the draft and verify the title, six creators and ORCIDs, affiliations,
FWO grant, CC BY 4.0 licence, version `v1`, and public visibility. Reserve the
DOI if the final cards should cite it. Record both the concept DOI and version
DOI in `publication-english/release-manifest.json` before rebuilding the final
artifacts.

## 4. Pre-publication checks

- Download each private Hub repository to a fresh directory and compare the
  generated `CHECKSUMS.sha256`.
- Run local smoke inference from the downloaded model with both `en-GB` and
  `en-US`.
- Confirm that the Hub Dataset Viewer exposes 6,700 `train` rows and 300 `test`
  rows after public visibility is enabled.
- Confirm that no local absolute path appears in any public file.
- Complete every applicable item in `RELEASE_CHECKLIST.md`.

## 5. Coordinated public release

After explicit final approval, make the repositories public:

```bash
hf repos settings stighellemans/meddeid-english-synthetic-corpus \
  --type dataset --public
hf repos settings stighellemans/meddeid-english-synthetic-benchmark \
  --type dataset --public
hf repos settings stighellemans/meddeid-english-synth \
  --type model --public
```

Publish the reviewed Zenodo draft in the same release window. Then record the
three immutable Hub revisions, Zenodo identifiers, archive checksum, and release
date in the manifest. Add the English synthetic corpus and subannotated
benchmark to the existing MedDeID Collection, together with the final paper.
Keep `stighellemans/meddeid-english-synth` outside the Collection as a standalone
public model repository.

Publishing changes public external state and should be a separate, explicit
action from preparing or staging the artifacts.
