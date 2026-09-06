# Changelog

## Unreleased

## 0.2.0 - 2026-09-06

- Added one suite-wide declarative age-granularity policy and connected the
  active Dutch/English language profiles to central inference date replacement,
  safe placeholder defaults, configurable weak-shift warnings, and processing
  provenance.
- Added the suite-wide `meddeid` guided front door with explicit workflow
  branching while preserving every independent component CLI.
- Published the `meddeid-language-en` component with separate
  `en-GB` and `en-US` profiles and integrated those profiles into synthetic
  generation and locale-driven stability helpers.
- Published the English synthetic corpus, human-reviewed subannotated
  benchmark, synthetic model, shared Dutch/English demo, and citable Zenodo
  archive, and incorporated their immutable revisions into `suite-lock.yaml`.
- Removed profile-version suffixes from the active language-profile contracts
  and released `nl-NL` language and generation support.
- Released coordinated versions of every suite repository: Core 0.2.1,
  English and Dutch language packages 0.2.1, Data and Eval 0.4.0, Training
  0.2.1, and Annotate, Curate, Subannotate, and the legacy-site redirect 0.2.0.
- Tagged both Hugging Face model repositories as `v1.0.0` and recorded their
  version-specific DOIs, plus the exact deid-battery and Belgian-DEDUCE study
  revisions.
- Published the suite 0.2.0 release for `meddeid==0.3.0`, including
  separate minimal CPU, portable PyTorch CUDA, weight-free TensorRT gateway,
  and T4-specific TensorRT artifacts with immutable benchmark evidence.
- Reduced the normal GPU tuning surface to the `latency` and `throughput`
  serving profiles. Backend-specific batching, precision, transport,
  concurrency, and worker choices remain image defaults; advanced overrides
  are documented but absent from the quick deployment templates.
- Added per-runtime image-size budgets and framework-separation gates so an
  operator downloads only the CPU, portable CUDA, or target-specific
  TensorRT/gateway stack selected for their hardware.
- Added a v2 candidate lock, automated candidate validation, generic
  post-publication identity/digest resolution for every component, and a gate
  that prevents final suite-lock publication while any required check remains
  pending.

## 0.1.1 - 2026-08-18

- Updated the verified clean-install runtime from PyTorch 2.7.1 to 2.13.0 to
  eliminate the known vulnerabilities reported for the earlier runtime pin.

## 0.1.0 - 2026-08-18

- Published the first coordinated MedDeID suite release contract.
- Pinned all component repositories, Python distributions, containers, model,
  datasets, language profile, and archival identifiers.
- Published the optional Dutch JavaScript profile on npm, the hosted Hugging
  Face demo, and the canonical-metadata Zenodo v2 archive.
- Added a clean-install vertical-slice release gate over a synthetic fixture.
