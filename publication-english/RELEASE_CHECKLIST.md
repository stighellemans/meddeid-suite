# English publication checklist

## Verified content

- [x] 6,700 development documents and 300 benchmark documents are disjoint.
- [x] `en-GB` and `en-US` each contribute 3,350 development and 150 benchmark documents.
- [x] All 300 benchmark documents completed primary human validation.
- [x] All 1,717 primary spans have a confirmed contiguous subannotation partition.
- [x] The enriched benchmark contains 7,358 core-PII subannotation segments.
- [x] The final model export is pinned to `FacebookAI/roberta-base` revision `e2da8e2f811d1448a5b465c236feacd80ffbac7b`.
- [x] The final benchmark was evaluated once after epoch selection and full-data refit.
- [x] Dataset and model repository cards, checksums, provenance, and Zenodo metadata were staged and verified.

## Before upload

- [x] Review the three generated Hub cards and the exact repository names.
- [x] Review the reported benchmark metrics and wording.
- [x] Confirm CC BY 4.0 for data/guideline and AGPL-3.0-only for the model.
- [x] Include the English synthetic training corpus and subannotated benchmark
      in the existing MedDeID Collection; do not add the English model.

## Staged release

- [x] Create all three Hugging Face repositories privately.
- [x] Upload the generated folders and record immutable commit SHAs.
- [x] Verify anonymous downloads after making the repositories public.
- [x] Verify both Dataset Viewer schemas after Hub processing completes (6,700
      corpus rows and 300 benchmark rows).
- [x] Download the model into an empty cache and run both `en-GB` and `en-US`
      smoke inference with the public `meddeid==0.2.0` runtime.
- [x] Create and preview the Zenodo draft; record concept DOI `10.5281/zenodo.22127863`
      and version DOI `10.5281/zenodo.22127864`.
- [x] Publish the two datasets, model, and Zenodo record after final review.
- [x] Add the English synthetic corpus and subannotated benchmark—but not the
      English model—to the MedDeID Collection. Add the final paper when available.

No checklist item authorizes publication automatically.
