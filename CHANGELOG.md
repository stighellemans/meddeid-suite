# Changelog

## Unreleased

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
  benchmark, synthetic model, shared Dutch/English demo, and citable Zenodo v1
  archive. The next coordinated suite release will incorporate their immutable
  revisions into `suite-lock.yaml`.
- Removed profile-version suffixes from the active language-profile contracts
  and added local `nl-NL` language and generation support. No public release,
  model bundle, suite lock, or generated corpus has been updated.

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
