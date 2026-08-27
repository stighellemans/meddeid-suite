# MedDeID English synthetic data v1

This archive contains 6,700 synthetic English clinical documents for model
development, a separate 300-document human-validated synthetic benchmark, and
the English MedDeID annotation guideline. It contains no real patient notes or
personal information.

## Contents

- `data/meddeid-english-synthetic-corpus.jsonl`: 6,700 development documents
  (3,350 `en-GB`, 3,350 `en-US`);
- `data/meddeid-english-synthetic-benchmark.jsonl`: 300 benchmark documents
  (150 per locale), 1,717 primary spans, and 7,358 confirmed nested
  subannotation segments;
- `provenance/`: frozen primary spans, confirmed subannotation decisions, and
  the bundle manifest that pins their hashes and profile routing;
- `guidelines/annotation-guidelines-en.pdf`: applicable annotation guideline;
- `release-manifest.json` and `CHECKSUMS.sha256`: release identity and hashes.

Primary and nested spans use absolute, half-open `[begin, end)` offsets in
Unicode code points. Nested subannotations form a complete contiguous partition
of their owning primary span.

The development corpus and benchmark are disjoint. The benchmark must not be
used for training, validation, early stopping, prompt or rule development, or
model selection when reporting final benchmark results.

Verify all extracted files from the archive root with:

```bash
sha256sum --check CHECKSUMS.sha256
```

The data and guideline are licensed under CC BY 4.0. Synthetic data does not
represent every property of real clinical documentation; local validation and
a separate privacy assessment remain necessary.
