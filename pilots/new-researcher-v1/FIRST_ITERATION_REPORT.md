# First-iteration researcher experience report

Date: 2026-08-10

## Verdict

The canonical-data, merge, subannotation, bundle, and metric layers are close
enough to demonstrate. The suite is **not yet a clean end-to-end experience for
a new external researcher**, primarily because primary-annotation saving
crashes, the public model reference is unavailable, and the training wrapper
does not implement its documented protocol and ends on an undeclared external
dependency.

Overall first-time-user score: **2/5**.

Final checkout health: **not green**. A fresh `scripts/verify_suite.py` run
failed while collecting `meddeid-language-nl` tests because
`meddeid_language_nl.date_pseudonyms` does not export the expected
`is_weak_date_shift` symbol. The initial suite verification passed before this
new component appeared in the staging workspace during the pilot.

## Pilot scope

- Six wholly synthetic Dutch clinical notes.
- 22 adjudicated primary PII spans across the canonical 15-label taxonomy.
- Two independent mock exports, with five documents containing deliberate
  boundary, label, or missing-span disagreements.
- 22 confirmed primary spans expanded to 92 core-PII subannotation segments.
- Oracle and deliberately degraded prediction sets.
- One one-epoch training plumbing run using the cached Dutch base encoder.
- macOS on Apple Silicon, Node 26, Python 3.12 in an isolated `uv` environment.

This pilot tests software plumbing and researcher ergonomics. It does not test
model quality, inter-annotator reliability, or the validity of a six-document
synthetic benchmark.

## Stage results

| Stage | Result | Ease | Notes |
|---|---|---:|---|
| Canonical dataset creation | Passed | 3/5 | Strict validation is useful, but researchers must author JSONL and offsets themselves; there is no TXT/CSV importer or project initializer. |
| Blank primary annotation | Partly passed | 2/5 | Query-based span creation was discoverable enough and persisted correctly, but every save crashed the UI. |
| Independent-export merge | Passed | 4/5 | Deterministic, transparent, and correctly preserved source filenames and disagreements. |
| UI adjudication | Partly passed | 1/5 | Correct gold was produced only with save/reload workarounds; unanimous spans were incorrectly marked pending. |
| Core-PII subannotation | Passed mechanically | 4/5 | Smoothest UI; all spans could be confirmed and autosaves worked. Auto-filled semantic categories still require genuine expert review. |
| Evaluation bundle | Passed | 5/5 | Bundle and SHA-256 manifest exported cleanly. |
| Metrics | Passed | 4/5 | Oracle scored 1.0; degraded predictions produced sensible lower metrics. A batch prediction command is missing. |
| Public-model inference | Blocked | 1/5 | Locked Hub repository `meddeid/meddeid-dutch-synth` returned 404. |
| Tiny training selection | Blocked late | 1/5 | Reached and completed an epoch on CPU, then failed on undeclared `span_annotations`. |
| Refit | Blocked early | 1/5 | Wrapper failed its own overlap guard because it did not forward full-refit flags. |
| Export and local inference | Passed with workarounds | 2/5 | Exported a bundle from the partial checkpoint; inference required Transformers `<5`. Output is intentionally meaningless. |
| Final suite verification | Failed | 1/5 | `meddeid-language-nl` test collection expects a missing `is_weak_date_shift` export. |

## Evaluation results

Oracle predictions:

```json
{
  "exact_f1": 1.0,
  "character_recall": 1.0,
  "core_pii_recall": 1.0
}
```

Deliberately degraded predictions:

```json
{
  "exact_precision": 0.7222222222222222,
  "exact_recall": 0.5909090909090909,
  "exact_f1": 0.65,
  "character_precision": 0.8771929824561403,
  "character_recall": 0.704225352112676,
  "core_pii_recall": 0.757085020242915
}
```

## Highest-priority improvements

### P0 — unblock a first external pilot

1. **Fix the primary UI save crash.** After the server successfully saves, the
   client reload path passes canonical `spans` data into code expecting
   `annotations`, causing `doc.annotations.map` to fail. Add an integration test
   that creates/applies a span, saves, and asserts the UI remains usable.
2. **Publish or correct the locked public model.** The README and suite lock
   currently reference a Hub repository that returns 404.
3. **Remove or declare the hidden `span-annotations` training dependency.** The
   staged training package completes an epoch and then imports
   `span_annotations.evaluation`, which is absent from its package metadata and
   from the public suite contract.
4. **Make `refit` implement the documented protocol.** It must pass at least
   `--final-epoch-is-best` (which disables early stopping) and must perform the
   declared one-time test evaluation. The current wrapper treats refit like
   selection and fails when validation is folded into training.
5. **Restore a green suite verification after adding `meddeid-language-nl`.**
   Align the public date-pseudonym API and its tests, and require the complete
   verification command before publishing a suite lock.

### P1 — make results trustworthy

6. **Forward every supported training config value.** The wrapper ignored
   `head_warmup_epochs`, both learning rates, weight decay, warmup ratio,
   early-stopping settings, and selection metric. The run therefore used
   different settings from the YAML displayed to the researcher.
7. **Keep the test set untouched during epoch selection.** Add
   `--skip-test-evaluation` automatically for `select-epochs`; the current
   command reads and evaluates `test.jsonl`.
8. **Add a device/backend option.** Automatic MPS selection failed because the
   attention kernel did not support training dropout. Researchers need
   `--device auto|cpu|mps|cuda` and/or an eager-attention fallback.
9. **Cap Transformers to the supported major version or update the tokenizer
   adapter.** `transformers>=4.45` resolved to 5.x, but inference calls the
   removed `prepare_for_model` API. `transformers>=4.45,<5` worked.
10. **Export the actual training window contract.** The pilot trained with
   `max_length: 128` and `overlap: 32`, while `meddeid-train export` silently
   wrote its defaults, 512 and 64. Export should read the checkpoint/run config
   or require explicit matching values.
11. **Gate adjudication completion.** Saving currently marks a document
    `adjudicated` even when the stored disagreement entries remain `pending`.
    Persist accept/reject/replacement decisions and block freezing until all are
    resolved.
12. **Do not classify unanimous spans as missing suggestions.** The merge emits
    only disputed candidates to `suggestions.jsonl`, but the UI interprets every
    accepted span absent from that file as `missing_from_suggestions`.
13. **Validate frozen primary gold in subannotation.** The next stage accepted
    records whose document status was adjudicated but whose disagreement items
    were still pending and whose UI-added primary spans had `confirmed:false`.

### P2 — reduce researcher setup burden

14. Add `meddeid project init`, importers for TXT/CSV, and an explicit manifest
    schema with a validator and deterministic split command.
15. Add a batch inference command that consumes canonical document JSONL and
    emits prediction JSONL directly compatible with `meddeid-eval`.
16. Align environment-variable names: primary annotation still uses `DEID_*`,
    while subannotation uses `MEDDEID_*`.
17. Add one top-level tutorial with copy-paste commands, expected outputs, and a
    tiny downloadable smoke-test fixture like this pilot.
18. Align documented checkpoint paths with reality: the trainer writes
    `run/checkpoints/best.pt`, while the README example refers to
    `run-refit/best_model.pt`.

## What already works well

- Canonical labels, offsets, and schema validation caught malformed data early.
- The merge is deterministic and never silently chooses between annotators.
- The annotation UI exposes exact query and batch-creation tools.
- The subannotation UI provides complete coverage, autosave, progress, and
  deterministic initialization.
- Evaluation-bundle hashing is clear and reproducible.
- Metric outputs reacted correctly to intentionally degraded predictions.
- Once dependencies and compatibility were manually resolved, exported local
  model artifacts could be loaded by the inference CLI.

## Recommended second iteration

Fix the four P0 items, add an end-to-end CI fixture using these six documents,
then repeat the pilot from a clean machine/container with no personal source
repositories available. The acceptance criterion should be one documented
command per stage, no manual JSON rewriting, no page reloads after saves, no
undeclared imports, and a downloadable public model pinned by revision and
checksum.
