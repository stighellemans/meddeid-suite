# New-researcher pilot runbook

This is a plumbing test over six invented Dutch notes. It is intentionally too
small for scientific conclusions. Run every command from the `meddeid-suite`
directory.

## 1. Create a clean local environment

```bash
export MEDDEID_SUITE="$PWD"
export MEDDEID_PILOT_WORK="$(mktemp -d /tmp/meddeid-pilot.XXXXXX)"

python3.12 -m venv "$MEDDEID_PILOT_WORK/.venv"
source "$MEDDEID_PILOT_WORK/.venv/bin/activate"
python -m pip install --upgrade pip
python -m pip install \
  ./repos/meddeid-core \
  ./repos/meddeid-language-nl \
  ./repos/meddeid-eval \
  './repos/meddeid[server]' \
  ./repos/meddeid-data \
  './repos/meddeid-training[train]'

npm ci --prefix repos/meddeid-annotate
npm ci --prefix repos/meddeid-curate
npm ci --prefix repos/meddeid-subannotate
```

The Python packages are installed through their package metadata, not exposed
as sibling `src/` directories. Text and inference stay local; only the public
model bundle is downloaded.

## 2. Import plain text and initialize primary annotation

```bash
meddeid-data project create \
  "$MEDDEID_PILOT_WORK/project" \
  "$MEDDEID_SUITE/pilots/new-researcher-v1/00-plain-text" \
  --namespace new-researcher-pilot \
  --language-profile nl-BE

meddeid-data validate \
  "$MEDDEID_PILOT_WORK/project/artifacts/annotations.jsonl"

meddeid batch \
  "$MEDDEID_PILOT_WORK/project/artifacts/annotations.jsonl" \
  --output "$MEDDEID_PILOT_WORK/project/assignments/primary.jsonl" \
  --model stighellemans/meddeid-dutch-synth \
  --revision 55c7858e91a53686bfd359d2653c8c6b8dabde89 \
  --device cpu
```

Expected result: six canonical documents, a private source-ID map under the
project's gitignored `private/` directory, and six model-initialized assignment
records. The pinned public weights have SHA-256
`791c6b2135274d548a0ee0c8759055be3eac2ac6245977b7faaf992a664f4780`.

## 3. Review and save the primary assignment

```bash
MEDDEID_ANNOTATIONS_PATH="$MEDDEID_PILOT_WORK/project/assignments/primary.jsonl" \
  npm --prefix repos/meddeid-annotate run dev
```

Open `http://localhost:5180`. Correct, add, or delete the model spans; confirm
each span and complete every document. Single save, save-all, autosave, and
reset/reload persistence are covered by the browser regression test.

For a single-reviewer training path, the completed assignment can go directly
to subannotation. For two independent reviewers, package each completed export:

```bash
meddeid-data project package-annotation \
  "$MEDDEID_PILOT_WORK/project" reviewer-a.jsonl \
  --annotation-set-id new-researcher-a --annotator-id reviewer-a

meddeid-data project package-annotation \
  "$MEDDEID_PILOT_WORK/project" reviewer-b.jsonl \
  --annotation-set-id new-researcher-b --annotator-id reviewer-b
```

## 4. Optional two-reviewer curation

```bash
npm --prefix repos/meddeid-curate run dev
```

Open `http://localhost:5183`, enter a pseudonymous curator ID, and upload the two
packaged JSONL/manifest pairs. Resolve every disagreement and confirm the whole
text of every document before selecting **Publish gold**.

Pending disagreements are normal immediately after importing two differing
annotation sets: they are the work queue. They are not valid in the published
handoff. Publication is blocked until every disagreement has a persisted
decision, every primary span is confirmed, and every document has whole-text
confirmation.

The checked fixture demonstrates the finished state:

- 6 confirmed documents;
- 7 of 7 disagreements resolved;
- 22 confirmed primary spans;
- `annotations.jsonl` SHA-256
  `af77e700a00f4f006d1af5f69781689d8ae657c9e8edbb7a1d42684939816346`.

Maintainers can rebuild that fixture through the real store APIs, with no JSON
rewriting:

```bash
node pilots/new-researcher-v1/regenerate-curation.mjs
```

## 5. Subannotate and export the benchmark

Use either the completed single-reviewer assignment or the curated output. The
checked two-reviewer path is:

```bash
MEDDEID_DATA_DIR="$MEDDEID_PILOT_WORK/subannotation" \
MEDDEID_ANNOTATIONS_PATH="$MEDDEID_SUITE/pilots/new-researcher-v1/03-adjudication/annotations.jsonl" \
  npm --prefix repos/meddeid-subannotate run dev
```

Open `http://localhost:5181`, review every generated segment, confirm every
primary span, and export:

```bash
MEDDEID_DATA_DIR="$MEDDEID_PILOT_WORK/subannotation" \
  npm --prefix repos/meddeid-subannotate run bundle
```

The checked bundle contains 6 documents, 22 primary spans, and 92 reviewed
core-PII segments. Its benchmark SHA-256 is
`0cea3c59236e6a0711659173179543a770c1d995fe4c64382cd568710f44460b`,
and its manifest pins the adjudication hash above. Maintainers can migrate the
checked reviewed segments onto regenerated gold with:

```bash
node pilots/new-researcher-v1/regenerate-subannotation.mjs
```

## 6. Score a prediction file

```bash
meddeid-eval score \
  --gold pilots/new-researcher-v1/04-subannotation/evaluation-bundle/meddeid-dutch-synthetic-benchmark.jsonl \
  --predictions pilots/new-researcher-v1/05-evaluation/degraded-predictions.jsonl \
  --output "$MEDDEID_PILOT_WORK/degraded-metrics.json"
```

The frozen degraded fixture has exact F1 `0.65`; scoring the benchmark against
itself gives `1.0` for exact F1, character recall, and core-PII recall.

## 7. Run selection, refit, export, batch inference, and evaluation

```bash
export TOKENIZERS_PARALLELISM=false

meddeid-train select-epochs \
  --config pilots/new-researcher-v1/06-training/pilot.yaml \
  --data pilots/new-researcher-v1/06-training/prepared-selection \
  --run "$MEDDEID_PILOT_WORK/run-selection" \
  --selection-output "$MEDDEID_PILOT_WORK/selection.json"

meddeid-train refit \
  --config pilots/new-researcher-v1/06-training/pilot.yaml \
  --data pilots/new-researcher-v1/06-training/prepared-refit \
  --run "$MEDDEID_PILOT_WORK/run-refit" \
  --selection "$MEDDEID_PILOT_WORK/selection.json"

meddeid-train export \
  --checkpoint "$MEDDEID_PILOT_WORK/run-refit/checkpoints/best.pt" \
  --output "$MEDDEID_PILOT_WORK/exported-model"

meddeid batch \
  pilots/new-researcher-v1/01-source/annotations.jsonl \
  --output "$MEDDEID_PILOT_WORK/predictions.jsonl" \
  --model "$MEDDEID_PILOT_WORK/exported-model" \
  --device cpu

meddeid-eval score \
  --gold pilots/new-researcher-v1/04-subannotation/evaluation-bundle/meddeid-dutch-synthetic-benchmark.jsonl \
  --predictions "$MEDDEID_PILOT_WORK/predictions.jsonl" \
  --output "$MEDDEID_PILOT_WORK/metrics.json"
```

Epoch selection intentionally has an empty test split. Refit uses the selected
epoch count and evaluates the sealed test set once. The CPU pilot disables
worker processes for portability. The verified run selects one epoch, exports
a self-contained bundle, and predicts 22 spans over six notes. The release lock
treats exact F1 `0.90 +/- 0.10` as a plumbing tolerance; this toy score is not a
model-quality claim.

## 8. Run the regression gates

The quick gate validates canonical records, publication completeness, persisted
decisions, hashes, bundle lineage, frozen metrics, and the pinned public model:

```bash
python scripts/verify_new_researcher_pilot.py
```

The full gate additionally performs plain-text project import, public-model
initialization, actual selection, refit, export, batch inference, and scoring in
a temporary workspace:

```bash
python scripts/verify_new_researcher_pilot.py --full
```

Run the UI persistence path separately:

```bash
npm --prefix repos/meddeid-annotate run test:browser
```

`FIRST_ITERATION_REPORT.md` is retained as the historical record of the original
failed pilot. It does not describe the current state.
