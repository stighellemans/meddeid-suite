# Improving New-Language and New-Model Onboarding

Status: living engineering notes gathered while producing the combined English
GB/US synthetic corpus and model. This is an implementation backlog, not a
released-suite contract. Released suite locks must not change until an explicit
release milestone.

## Goal

Adding a language or regional profile should be a repeatable workflow with
strong resource provenance, safe synthetic generation, locale-aware review,
training, evaluation, and self-contained model export. It should not require
copying Dutch modules, editing locale-specific imports throughout the suite, or
inventing a new one-off production script.

## Findings from the English implementation

### 1. Separate language, region, dataset, and model concepts

The suite currently tends to conflate four different things:

- a language/locale profile (`en-GB`, `en-US`);
- a synthetic-generation profile;
- a training/evaluation dataset containing one or more profiles;
- a trained model bundle.

They should have separate contracts. A single model bundle must be
able to declare several supported profiles, for example:

```json
{
  "supported_profiles": ["en-GB", "en-US"],
  "default_profile": null,
  "profile_selection": "document-metadata-or-explicit"
}
```

This avoids creating a source-code component merely because the weights differ.
The model remains a self-contained exported artifact; language-specific rules
remain in language packs.

### 2. Make inference profile selection ergonomic

Users should not have to select both language and region on every call when the
input record or model already resolves it. The preferred order should be:

1. use canonical document metadata (`metadata.lang` or `language_profile`);
2. use an explicit API/CLI profile override;
3. use the bundle's single supported profile when only one exists;
4. fail with an actionable ambiguity error when several profiles remain.

Bare `en` should remain invalid for locale-sensitive date/address/identifier
post-processing. The error should list the model's supported choices. Automatic
language identification must not silently choose between GB and US because
short clinical notes often provide insufficient evidence and ambiguous dates
change meaning.

### 3. Generalise the model manifest for multi-profile weights

`meddeid-training` and bundle export should use one unversioned,
multi-profile contract. Language profiles are locale identifiers; package,
resource, schema, ruleset, and model versions remain independently pinned.

Required changes:

- training config accepts `language_profiles: [en-GB, en-US]`;
- dataset validation asserts every record belongs to an allowed profile;
- run metadata reports aggregate and per-profile metrics;
- export embeds every required language-pack manifest and version;
- inference chooses the correct post-processor per document;
- bundle verification tests both profiles and rejects bare `en`.

### 4. Replace locale imports with provider interfaces

Generation, judging, stability evaluation, date handling, and export validation
must not import Dutch functions directly. They should receive a resolved locale
provider exposing:

- date parsing and pseudonymisation;
- subannotation/post-processing;
- approved synthetic identifiers and phone validation;
- lookup values, structured records, sources, and manifests;
- locale-specific false-positive checks.

Installed entry-point discovery should be authoritative. Source-tree fallbacks
make a new language appear to work in development while failing after package
installation.

### 5. Promote LLM generation to a generic production contract

The deterministic English renderer is useful for smoke tests, but training data
needs the richer Dutch-style two-stage workflow. This should be a reusable suite
facility rather than language-specific scripts:

1. build a structured, provenance-bearing clinical case;
2. expose only typed PII placeholders to the authoring model;
3. let the model independently author clinical prose;
4. resolve placeholders locally to approved PII and exact Unicode offsets;
5. reject forbidden labels, missing placeholders, malformed output, and
   unapproved synthetic values;
6. retain the marked source, API response ID, token usage, model, prompt-contract
   version, and retry history.

Using value-free placeholders is safer than asking the model to repeat literal
PII inside paired markers: it removes an entire class of unmarked-value and
boundary errors while preserving independently authored documents.

The provider abstraction should support OpenAI Responses and future backends
without changing the dataset contract. Model name and reasoning effort must be
pinned in the generation manifest.

### 6. Make 500-document quality gates a first-class workflow

The suite should provide a generic `production-corpus` command with resumable,
immutable batches. Every batch should produce:

- structured cases;
- canonical annotated documents;
- retained placeholder/marked outputs;
- a failure ledger;
- exact, normalised, skeleton, and near-duplicate analysis;
- long repeated-phrase analysis;
- locale/document/style/label/hard-negative coverage;
- exact offset and taxonomy validation;
- API usage and estimated cost;
- a complete personal-review packet containing every document (with optional
  paginated or stratified views for navigation, never as a substitute for full
  review);
- a cryptographic manifest;
- a separate human/personal review sign-off.

Finalisation must refuse any batch without both an automated pass and an explicit
personal-review pass. A failed pilot must remain recorded as failed and must not
be eligible for training.

### 7. Add an independent clinical/editorial reviewer

Regex and offset checks cannot catch errors such as a malformed reference
interval, a UK-only medicine used as active US treatment, an implausible
age/condition combination, or a public library described as a referring
hospital. The production contract therefore needs a structured second review
with a strict schema covering:

- clinical accuracy and internal consistency;
- demographic plausibility;
- numbers, units, and reference intervals;
- locale-specific medication and administrative language;
- realistic organisation roles;
- hard-negative naturalness;
- language quality.

The review model is an additional gate, not the source of truth for offsets.
Every cited issue must quote text that actually occurs in the document. Direct
personal review of every document remains mandatory for a gold training corpus.
The suite should record per-document decisions, permit review in stable pages,
and prevent batch sign-off until every row has a decision. A stratified view is
still useful for early pilots, but must not be represented as full-batch review.

The automated batch audit must also verify that every accepted document retains
a clean review verdict, an empty unresolved-issue list, and a review response
ID. It is not sufficient for the generation loop to have requested review at
some point.

The English pilot also demonstrated why model review cannot replace personal
review. A clean structured verdict still missed a clinician used as both
referral recipient and signatory, a pneumonia note linked to a mental-health
hospital, malformed age grammar, and Markdown emphasis inside plain-text data.
Every personal rejection should therefore be converted into one or more of: a
deterministic validator, a typed dependency, a resource filter, a locale
mapping, or a new reviewer instruction. The rejection and the rule it caused
should remain linked in the audit trail.

Repeated typed placeholders need a nuanced contract. Real documents often
repeat the patient, clinician, or organisation in a header and footer, and all
occurrences must be annotated. Enforcing “exactly once” reduces realism. The
correct rule is: every required slot appears at least once; every repeated
occurrence becomes a span; and repeated values retain the same semantic role.
Role consistency belongs in the case dependency and review layer, while marker
accounting guarantees complete annotation.

The entity label alone is also not enough to render an identifier correctly.
Both an MRN and a report/accession number map to `ID:Patient`, but the clinical
text must not call a `REPORT-*` value an MRN or patient ID. Generation targets
should carry a semantic subtype such as `patient_mrn`, `report_id`,
`accession_id`, or `professional_id`, plus allowed display descriptors. Local
validation and independent review should check the descriptor beside every
identifier placeholder. They must also distinguish display semantics from the
fixed interoperability taxonomy: a patient-associated report/accession number
can be displayed correctly as a report ID while still mapping to the suite's
broader `ID:Patient` label.

Likewise, allowed recurrence needs explicit mutually exclusive clinical roles.
A laboratory validator may recur in a validation line and signature, but must
not silently become the ordering clinician. Referral authors must not become
their own addressees. The generic case contract should be able to declare these
role exclusions so they are deterministic rules rather than prompt-only advice.

Medication challenge generation must use token-aware or longest-specific-name
matching. Naive substring iteration can map `amoxicillin-clavulanate` to a
standalone amoxicillin dose, creating apparent duplicate therapy. This belongs
in a reusable medication normalisation/alias layer with locale-specific names,
not in ordered ad-hoc string replacements.

Author-facing placeholders should be short opaque tokens such as `[[PII_01]]`,
with label and semantic slot stored in the adjacent structured target. Long
delimiter-rich markers caused repeated transcription failures even though the
clinical prose was otherwise good. The local renderer can deterministically
expand the opaque token to the canonical label/slot and retain the raw marked
response for audit.

Locale derivation must replace every locale-owned metadata field, not only the
rendered address. A US case was found with a valid US address but an inherited
GB `address_region`. Add cross-field invariants (`address` ↔ region ↔ postcode/
ZIP ↔ profile) to case validation before any LLM call.

Clinical case seeds need typed dependencies between diagnosis, age, medication,
and risk context. Independent random sampling produced an anticoagulated
atrial-fibrillation patient under 65 with a documented CHA2DS2-VASc score of
zero. The reusable case layer should express eligibility constraints and reject
or resample incoherent combinations before authoring. Locale medication aliases
belong in the same layer (for example, an adult US asthma/COPD burst normally
uses `prednisone`, while GB prose normally uses `prednisolone`).

Document families also need mandatory PII dependencies. A laboratory report
without an available date target encouraged the author to invent an unmarked
specimen date, creating a harmful false-negative training example. Define
minimum slots per family (for a laboratory report: patient, date, record/report
identifier, and validator) and reject any full date, contact, identifier, or
other PII-looking value that was not supplied and annotated by the case.

Clinical review severity should be calibrated to the actual de-identification
objective. Objective contradictions, unsafe instructions, impossible scenarios,
and PII/locale/offset defects remain blocking. Reasonable alternative treatment
choices or debatable guideline nuance should be recorded as non-blocking notes,
otherwise clinical-editor preference can consume more generation budget than it
adds NER signal.

The first English checkpoint sharpened this rule further: the production gate
is primarily a gold-annotation gate, not a clinical-publication peer review.
Blocking personal-review findings are missing or wrong labels, incomplete span
boundaries, invented unlabelled PII, forbidden labels, artificial hard-negative
hints, duplicated or insufficiently diverse text, locale errors in identifying
forms, and formatting that makes the label role unusable. Clinical prose should
block only when it makes the identifying role ambiguous or renders the document
plainly unusable. This priority must be stated in the review UI so reviewers do
not spend corpus budget rewriting incidental treatment or service choices.

Credentials require explicit boundary accounting. If a supplied caregiver
target ends in `MD` but the author appends `, RN`, the added credential is part
of the caregiver mention yet falls outside the gold span. Validation should
reject any recognised credential immediately adjacent to a caregiver span
unless it is already contained in that span. The same principle applies to
titles, suffixes, and postnominals in every language pack.

Invented PII leakage checks must include more than full dates, explicit ages,
phones, and identifiers. The English checkpoint found an unsupplied birth year
(`born in 1955`) and unsupplied jurisdiction names (`Puerto Rico`, `United
States`). Language profiles should expose jurisdiction lexicons and birth-year
patterns so any occurrence outside an authorised span is rejected. Occurrences
inside an organisation or full-address span remain valid and must not be
double-annotated.

Numeric-review instructions must explicitly recalculate derived values. A model
review accepted a FeNa reported as 0.03% even though the four displayed inputs
yielded about 0.32%. Common derived clinical calculations can have lightweight
deterministic validators; uncommon ones should at least be recalculated by the
review model. Unresolved extraction/template artifacts such as `[date]` or
`[day of admission]` should always fail local validation.

Formatting robustness must be an explicit corpus contract because the
manuscript's stability result shows formatting, not identity, is the dominant
failure axis. Independently authored training documents should cover full
names, first-name-only mentions, initials, first-name-plus-initial forms,
credentialed/titled caregivers, and lower/title/upper capitalisation; varied
locale-correct date and age formats; and telegraphic, narrative, structured,
bulleted, sparse, and dense document layouts. Do not create paired near-duplicate
training notes merely to perturb formatting. Keep the 300-document benchmark
independently authored, then generate name-source, name-capitalisation,
name-format, date-format, date-value, and age-format variants only inside the
stability evaluation, mirroring the manuscript protocol.

Every 500-document gate should quantify, and fail on regressions in, locale ×
document-family balance, style diversity per cell, condition diversity and
maximum prevalence, unique recombined patient names and addresses, lexical
four-gram diversity, required hard-negative families, PII source-slot format
coverage, date-format coverage, and past/contemporary/future date-value
coverage. Store one explicit pass/fail row per document and prevent batch
sign-off while any row is pending or failed; a batch-level “reviewed all” note
alone is not sufficient evidence.

Batch orchestration should bound complete author → local validation → model
review chains, not enqueue every author call against one shared FIFO semaphore.
The latter starved review calls behind hundreds of queued authors, delayed the
first durable checkpoint, and looked like an API outage. Use a bounded worker
pool, persist each accepted document immediately, and expose stage-level
progress and request-attempt cost records.

API cost must be treated as a corpus-level constraint, not inferred from the
number of accepted rows. Persist an attempt-level usage ledger immediately
after every author or reviewer response, including failed local-validation and
revision attempts, cache-write tokens, model, service tier, and the pinned
pricing snapshot. Report accepted-row cost separately from total attempted
cost. A second LLM review should be an optional targeted escalation: mandatory
deterministic validation plus recorded direct personal review can provide the
primary gate when blanket author-plus-review calls would exceed the corpus
budget.

Professional identifiers need regulator and role attributes, not only a locale
and entity label. For example, a GB GMC-format identifier must be linked to a
doctor and cannot be rendered as a nurse's registration. Language resources
should expose regulator, profession class, format, and synthetic/test status so
case construction can enforce the dependency before prompting.

Reviewer prompts must define taxonomy terms whose everyday meaning is
ambiguous. In MedDeID, `Name:Caregiver` is a healthcare clinician (including a
referring doctor or signatory), while relatives and informal carers are
`Name:Other`. Without that definition a reviewer rejected a correctly signed
referral as though the clinician were a family caregiver.

Formatting-aware review must not “correct” deliberately lowercase, uppercase,
first-name-only, or initial-only PII. Those variants are gold training signal,
not language errors. Review surrounding grammar and semantic role while
preserving the supplied span exactly. Relative-role prompts should also depend
on patient age so the author does not invent, for example, a living parent as
the active carer of a very old patient when an adult child, spouse, sibling, or
friend would be the natural choice.

Date-value robustness examples should be reviewed as pseudonymized calendar
shifts, not as historical fiction or forecasts. A modern note shifted to 1988
may still mention a modern medicine or service because real pseudonymization
changes the dates, not the surrounding care pathway. Review temporal intervals,
age/DOB consistency, and formatting; do not reject shifted examples for
period-specific availability.

Resume must use the already-written structured case manifest as authoritative.
Rebuilding cases after a resource filter or case-rule update can silently change
PII and invalidate previously accepted marked outputs. Validate the stored case
count/hash, then generate only missing document IDs. Any intentional case repair
needs a recorded migration and invalidation of affected authored documents.

Age and DOB must be generated with calendar arithmetic, not `age × 365 days`.
The latter drifts by leap days and produced a stored DOB whose completed age was
one year lower than the rendered age. Case validation should recompute age at
the encounter date and reject any mismatch before generation.

Age-condition dependencies need explicit lower and upper bounds for every
condition family whose default treatment makes age clinically material. A
16-year-old COPD-exacerbation case caused the author to resist a required adult
prednisolone regimen; COPD now has an adult/older-adult age constraint. Repair
this kind of case-construction error before spending repeated authoring
attempts, record the migration, and invalidate any already accepted output.

Direct review needs a recoverable document invalidation workflow. Archive the
accepted document and its marked source with a reason, remove both from the
active batch, attach the review feedback to the authoritative structured case,
and let resume re-author only that document. Preserve repeated invalidations so
the audit trail shows why each version was rejected. Regenerated rows must
return to `pending` personal-review status rather than inheriting an earlier
pass or fail decision.

Gold validation must reject invented numeric patient ages just as it rejects
invented dates. An author emitted an exact-looking age even when no
`Age_Birthdate` slot was selected, creating an unannotated false negative.
Detect explicit `aged N`, `N-year-old`, `N y/o`, and age-field forms outside an
age span while excluding legitimate gestational-age measurements. Prompts
should explicitly forbid numeric ages unless an age placeholder is supplied.

Retrospective rules must be applied to every previously signed batch, not only
future generations. The final English review found one repeated display habit
(`GMC GMC-TEST-…`), then used the new validator to identify and independently
reauthor every occurrence across the corpus. Any replacement returns to
`pending`, is read again, and invalidates the old quality-report and review
sign-off hashes. Corpus finalisation should perform this complete latest-rule
audit automatically and refuse stale sign-offs.

Validator findings must be traced back to their prompt or resource cause. A
legacy age instruction explicitly recommended `Patient: <age> patient`, which
made an age phrase look like the value of the Patient/name field. The corrected
contract keeps the actual name in `Patient:` and puts age in a separate natural
context line. Merely rejecting the outputs without repairing that instruction
would waste retries and allow the same defect into the next language.

Identifier targets need descriptor-aware rendering rules. A synthetic value
that already begins `GMC-TEST-` should be displayed after `GMC number:` or
`Professional identifier:`, never after a second bare `GMC`, and the identifier
must never substitute for the clinician name itself. Credentialed-name targets
likewise need to state that the placeholder already contains `MD` or `MBBS`, so
the author does not append an unannotated credential outside the gold span.

Resource normalization needs a recorded display-only case migration. TIGER
route data included interstate forms such as `I- 710`; runtime generation now
renders `I-710` while preserving the locked source record and provenance. When
such a defect is discovered after authorship, migrate the authoritative case,
archive the old document, and reauthor it—do not silently patch text and offsets
in the accepted dataset.

Replacement review must be recursive. A regenerated document can fix its
original PII issue yet introduce an unrelated generation fragment such as
`JSImport` or `deset?`. Keep every invalidated version, convert recurring
artifacts into deterministic guards, and reread the newest descendant until it
passes both the latest validator set and direct review.

### 8. Add typed, weighted, linked resource sampling

Flat `lookup_values()` is insufficient for production generation. Uniform
sampling exposed several real but contextually unsuitable tail values and could
pair a street, locality, and postcode from different regions. The generator
needs a shared sampler that:

- samples by published weight/rank when available;
- permits a controlled long-tail fraction;
- filters malformed display values without mutating the resource asset;
- links streets, localities, postcodes, institutions, states/nations, and phone
  formats by region;
- retains source IDs and resource-record attributes on the case;
- supports a reviewed common-occupation view for natural clinical prose;
- composes synthetic non-healthcare organisations from sourced locality tokens
  and declared suffix rules when a tiny public list would cause repetition.

Resource manifests should distinguish publisher records, curated runtime views,
and synthetic recombination rules.

Publisher-valid display values are not automatically generation-ready. ODS site
records can name an elective surgical hub or a parenthesised assessment service;
CMS may preserve catalogue forms such as `HOSPITAL,THE`. Keep those source rows
unchanged for provenance, but make the runtime view explicitly filter or map
display traps. Facility sampling must also depend on setting: an emergency note,
inpatient discharge, or ward handover needs an acute hospital/infirmary, whereas
a clinic note, referral, or laboratory request may plausibly use a medical
centre or outpatient service.

A name containing “hospital” is still not enough to prove an acute setting.
Community hospitals, elective hubs, trial sites, liaison services, and qualified
sub-units repeatedly passed simple string filters. Resource adapters should
retain an explicit facility capability (`acute`, `emergency`, `inpatient`,
`outpatient`, `laboratory`, `mental_health`, and so on) derived from official
attributes or a reviewed runtime curation. Until that exists, a conservative
major-acute view is safer than uniform sampling from all ODS sites.

### 9. Add a locale-aware clinical scenario catalogue

Clinical facts cannot be sampled independently of document type, patient age,
or locale. The reusable case contract should encode:

- plausible age ranges;
- applicable care settings and document families;
- symptoms, findings, investigations, medications, and units;
- locale-specific terminology and medication substitutions;
- optional specialty and acuity;
- compatible hard-negative families.

It should also encode temporal relations, not just isolated dates. If a record
contains an encounter date, a follow-up date, and a relative interval, the case
builder must derive the interval from the two dates so an authoring model cannot
produce “in two weeks” next to an appointment nine weeks later.

GB and US cases must use different clinical random seeds and must not be paired
variants of a shared case backbone. Shared machinery is fine; shared documents
or cloned fact plans are not.

### 10. Treat difficult false positives as planned clinical content

Hard negatives should be selected from a coverage matrix and integrated into a
plausible clinical context. They must not appear in artificial paragraphs such
as “unrelated terms” or “not an identifier.” Selection should be conditional:

- a cardiac-monitor model belongs in a monitored cardiac encounter, not a
  routine musculoskeletal laboratory report;
- a SNOMED code must match the clinical concept it encodes;
- an eponym or gene variant should occur in an appropriate diagnostic context;
- a medication and dose must be plausible for the locale and patient;
- impossible dates can appear as rejected data-entry values;
- times, measurements, scores, durations, roles, and LOINC codes should be
  naturally embedded in their usual sections.

Batch reports should count required hard-negative families and the final corpus
should include dedicated challenge slices for low-frequency cases.

Pilot review showed that requiring several fixed challenge strings in every
document damages realism. The reusable selector should normally choose one
clinically endogenous challenge, then use dedicated condition-linked cases for
rare eponyms, terminology codes, gene variants, devices, and invalid data-entry
values. Coverage is a batch/corpus property, not a reason to overload each note.

Hard-negative validation must also reject explicit label hints such as “is not
a patient identifier,” “not PII,” or “included only as a test example.” A gene
variant, terminology code, device model, score, measurement, or impossible date
is useful only when its clinical context makes it naturally confusable; a
disclaimer converts a difficult negative into an artificial shortcut.

Label coverage also has document-family constraints. Caregiver localities fit a
referral header; relative localities fit emergency-contact or discharge fields;
pathologist names and report IDs fit laboratory reports. A global rotating label
schedule can meet numeric coverage while making the prose visibly synthetic.
The case contract should publish allowed and dependent label groups per document
family (for example, caregiver ID normally depends on caregiver name).

Approved synthetic identifiers need separate `display_prefix`, `annotated_value`,
and provenance fields. A literal value such as `NPI-TEST-...` may be safely
non-assignable but is not realistic inside a final US report. The English pilot
instead uses the numeric NPI check-digit example published by CMS and keeps the
`NPI:` descriptor outside the annotated span. This pattern should be reusable
for every locale's official examples.

### 11. Preserve an attempt-level cost and failure ledger

Cost accounting based only on accepted documents underreports spend when a
clinical reviewer rejects a draft or marker validation triggers a retry. The
generic backend should retain, for every authoring and review request:

- case/document ID and attempt number;
- response ID, model, prompt-contract version, and timestamp;
- input, cached-input, output, and reasoning token counts;
- estimated price using a pinned price-table version;
- outcome category (accepted, validation rejection, reviewer rejection, API
  failure, or superseded retry).

The batch cost report should sum the attempt ledger, while accepted-document
metadata can continue to retain the final successful request. Historical
failures should remain inspectable but must not make a successfully retried
document look absent.

Accepted artifacts must also pin the exact authoring contract used for that
attempt: ordered PII targets, hard-negative targets, prompt-contract version,
and case-contract version. Compact placeholders such as `[[PII_02]]` are
positional, so re-expanding an old marked document with a newer sampler can
silently reinterpret its label and value. Revalidation must use the targets
stored with the accepted response; new sampler rules apply prospectively. A
regression test should mutate the current sampler after rendering and prove that
the stored artifact still validates under its original contract.

### 12. Standardise corpus finalisation and sealed benchmarks

The suite should natively construct a deterministic, checksum-pinned split while
stratifying by locale and document family. For this English milestone:

- development: 6,700 documents, 3,350 per profile;
- sealed benchmark: 300 documents, 150 per profile and 25 per document family;
- total: 7,000 independently authored documents.

No normalised text, PII-normalised skeleton, or near duplicate may cross the
development/benchmark boundary. Epoch selection must never read the benchmark.
Final refit uses all development data and evaluates the sealed benchmark once.

### 13. Make training orchestration profile-aware

Training should accept the multi-profile dataset without pretending it has one
post-processing locale. Keep the existing RoBERTa token-classification
architecture and allow `FacebookAI/roberta-base` as the base encoder.

The standard workflow should be:

1. deterministic train/validation partition inside the 6,700 development set;
2. epoch-selection run without benchmark access;
3. full-development refit for the selected epoch count;
4. one sealed 300-document benchmark evaluation;
5. per-profile, per-label, boundary, and difficult-false-positive metrics;
6. export one local bundle declaring both English profiles.

Training data and model metrics should retain generation-batch provenance so a
bad batch can be traced or excluded without rebuilding the entire corpus.

### 14. Add reusable tests for every new language

A new language/profile should pass one shared conformance suite:

- entry-point installation and discovery;
- manifest/resource agreement across Python and JavaScript;
- deterministic resource rebuilds and drift audits;
- exact Unicode offsets and idempotent post-processing;
- approved phone/identifier generation;
- no forbidden generated labels;
- locale date/address/identifier positive and negative fixtures;
- LLM placeholder round trips;
- all document families, allowed labels, and hard-negative families;
- duplicate and cross-locale leakage checks;
- wheel, sdist, npm, training, export, and inference smoke tests.

The conformance suite should be parameterised by profile rather than copied into
each language repository.

### 15. Make paediatric coverage a first-class corpus contract

An unconstrained adult-oriented age sampler does not produce useful paediatric
coverage. The first English production batch demonstrated the failure mode: it
contained only five under-18 cases out of 500, all adolescents, and four of the
five rendered documents had no `Age_Birthdate` span. A generic language/model
onboarding workflow must therefore measure clinical age coverage rather than
assuming that random age selection is adequate.

For the remaining English batches, each 250-document locale block now contains
exactly 41 paediatric cases: 5 infants, 8 children aged 1-4, 12 aged 5-11, and
16 aged 12-17. The finished 7,000-document corpus must contain at least 1,050
paediatric documents, with at least 525 in each locale. The sealed benchmark
reserves 24 paediatric documents per
locale, four in every locale/document-family cell: one infant, one age 1-4, one
age 5-11, and one age 12-17. Its infant selection deliberately spans day-,
week-, and month-based age formats in each locale.

The reusable case contract should distinguish:

- completed years from the displayed age value and unit;
- neonatal, infant, early-childhood, school-age, and adolescent clinical stages;
- day-, week-, month-, year-, and date-of-birth display variants;
- exact DOB consistency for every age precision;
- age-appropriate conditions, settings, guardian roles, consent/assent, and
  confidentiality conventions;
- measurements, gestational duration, symptom duration, doses, scores, and
  developmental descriptions that resemble ages but must remain unlabelled.

Every paediatric generated document must contain an explicit `Age_Birthdate`
target. Non-laboratory cases should normally include a parent/guardian or other
appropriate adult contact. Under-16 cases must not be assigned an occupation
merely to achieve label coverage. Fixed adult medication doses must not be used
as paediatric hard negatives when no weight is available.

Batch QC should report age bands, display units, document families, clinical
conditions, age source slots, and the number of paediatric documents with a
rendered age signal for each locale. Personal review must explicitly check that
the age signal, guardian/relative role, and surrounding age context make the
`Age_Birthdate` label meaningful. Review should not expand into judging
incidental treatment choices that do not affect PII detection.

### 16. Turn review discoveries into prospective PII-context validators

Batch 2 showed that a document can have exact marker replacement and correct
offsets while the labelled value is still embedded in a poor linguistic
context. Examples included a contextual age without a patient subject,
duplicated age-group wording, and a measurement hard negative with its unit
noun repeated. Once a reviewer finds such a class, the correction must include
a regression test and validator so every earlier and future document is checked,
not merely a one-off replacement.

The reusable gate should therefore include checks for:

- subjectless, article-mismatched, punctuation-broken, or duplicated age
  constructions around `Age_Birthdate` spans;
- incompatible record fields, such as a non-date marker placed under `Date:`;
- duplicated nouns or prepositions around difficult-negative values;
- generation instructions or test-disclaimer language leaking into the text;
- source-resource fragments ending in dangling apostrophes, hyphens, or other
  joiners before names are sampled;
- consistency between displayed DOB/age precision and structured encounter
  metadata.

These are annotation and false-positive-context checks. They should block the
batch. Incidental clinical plausibility that cannot change a PII label, span, or
negative example should remain non-blocking.

### 17. Calibrate text length against the existing corpus before spending tokens

The Dutch training data contain 6,493 texts with a mean of 186.8 words, median
of 175, and 90th percentile of 256. English Batch 2 has a mean of 297.6 words,
median of 305.5, and range of 207-465. Future language onboarding should compute
this comparison automatically before changing prompt length. Once the new
corpus already covers both compact and longer formats, more tokens are better
spent on independently authored documents, label diversity, difficult
negatives, and formatting variation than on uniformly increasing length.

### 18. Treat documentation shape as a measured corpus dimension

Independent authorship is necessary for diversity, but it does not guarantee
that an LLM will write like a clinician entering an EHR. English Batch 3 was
fully authored as whole documents and 359/500 documents (71.8%) used compact,
structured, minimal-EHR, handover, specialist-report, or longitudinal formats.
The remaining 141/500 (28.2%) used narrative-scribe or patient-facing-letter
formats. Direct review found the PII contexts usable, but the overall prose was
still cleaner and more explanatory than routine documentation needs to be.

From Batch 4, deterministic style weighting raises documentation-native shapes
to 439/500 planned cases (87.8%) and reduces narrative/patient-facing shapes to
61/500 (12.2%). The prompt now explicitly permits terse fragments, selective
abbreviations, compact field blocks, omitted subjects where grammatical in note
style, uneven section lengths, and mixed line layouts. Referral and genuinely
patient-facing letters retain prose where that is the native document form.

The first rendered Batch 4 audit showed why the requested style label is not an
adequate quality measure. All 500 texts had at least one record-style field
line, but only 121/500 (24.2%) contained list-like lines, compared with
3,470/6,493 (53.4%) in the Dutch training corpus under the same heuristic. The
English texts also remained about 43% longer under a simple space-delimited
count. Direct inspection found some `handover-note` and `compact-clinician`
outputs that were headings wrapped around polished paragraphs rather than
actual handover or compact chart language.

For Batch 5 onward, the raw-note profiles therefore have mandatory structural
contracts, not merely descriptive names. Compact notes require terse field,
problem, result, or action lines; handovers require a recognisable priority and
action flow; structured records require a real field block plus compact
entries; and minimal EHR notes prohibit long prose paragraphs. Their requested
lengths were shortened to 100-250 words by profile, while formal letters and
specialist reports retain complete prose where it is authentic. The generic
production floor must also vary by style: a universal 170-word minimum silently
prevents realistic short EHR notes and wastes generation budget.

Future onboarding should:

- define style distributions per document family rather than sample every
  available style uniformly;
- distinguish physician notes, nursing documentation, laboratory reports, and
  correspondence instead of treating all clinical text as polished prose;
- report style counts at each 500-document checkpoint;
- compare sentence completeness, heading density, field-row density, line
  length, abbreviations, bullets, and whitespace patterns with the reference
  corpus;
- preserve full-document authorship while varying the formatting surface; and
- keep clinical coherence sufficient for authentic PII context without using
  review time to perfect incidental medical detail.

Formatting variation must remain prospective and deterministic enough to audit.
The goal is not random corruption: each variant should resemble a plausible
documentation workflow and retain exact Unicode offsets.

### 19. Type resource semantics more narrowly than the public label

Batch 6 exposed a limitation of value-free placeholders: the authoring model
correctly knew that a target was `Organization:Other`, but did not know whether
the locally inserted value was a school, town council, housing authority,
transit authority, library, senior centre, or sports club. This produced valid
offsets around semantically implausible phrases such as a young child attending
a transit authority as a school. The issue is not the public taxonomy; it is a
missing private rendering subtype.

Every generation target should therefore carry both the interoperable label and
a narrower non-identifying semantic kind, for example:

- `other_organization.school`;
- `other_organization.employer`;
- `other_organization.family_support`;
- `other_organization.housing_service`;
- `other_organization.transport_service`;
- `other_organization.community_program`.

The authoring model may receive that kind and an age-specific usage constraint
without receiving the literal PII value. Local validation can then reject a
civic or adult-service organisation described as a child's school/daycare or
independent affiliation. The same principle applies to identifiers, healthcare
organisation roles, address subtypes, professional credentials, and relative
relationships.

The checkpoint also confirmed that personal review must be recursive. A first
regeneration can satisfy the original validator yet reveal a related wording
class, such as `the patient, aged 43, reviewed on the ward` without the copula
`was`, or a credentialled name immediately concatenated with stray text. The
correct response is to expand the rule, re-run it across every earlier signed
batch, archive all newly failing documents, regenerate only those documents,
re-read the replacements, and refresh the sign-off. Batch sign-off hashes
should be verified during finalisation rather than merely stored.

Operationally, generation also needs an exclusive per-batch writer lock and an
actual spend ledger. A prior overlapping-writer incident consumed API budget
without producing additional accepted documents. The reusable runner should
refuse a second writer, distinguish accepted-corpus estimated cost from actual
attempt spend, and show both at every checkpoint.

The production orchestrator must also be fail-fast at the corpus level. A
shell or task loop that advances to the next batch after a non-zero generator
exit can defeat the human assumption that there is only one active writer:
per-batch locks prevent corruption, but they do not prevent two different
batches from spending concurrently. The suite should provide one resumable
corpus command that owns a global production lock, stops on the first failed
batch, and records the exact batch and command that require resumption. Ad-hoc
loops must use fail-fast execution and must never launch a repair while an
earlier writer is still alive.

Replacement review is recursive rather than a one-pass exception workflow.
Repairing one rejected document can expose a new, related validator class in
the replacement, so replacements need the same full automated audit and direct
read as original documents. Any new validator discovered during that read must
be applied retrospectively to all signed batches before production advances.

Age and relationship compatibility belongs in structured case construction,
not only in prompt instructions or final-text regexes. The case schema should
encode patient age bands, plausible child/parent relationships, and profession
seniority constraints; samplers should make invalid combinations impossible.
Text validators remain useful as defence in depth, but should not be the first
place the suite learns that a 19-year-old cannot have an adult child or hold an
advanced-career occupation.

### 20. Separate best-checkpoint selection from early-stopping tolerance

The English epoch-selection run exposed an important orchestration detail. It
trained for eight epochs and produced its highest absolute exact-span F1 at
epoch 8, but retained epoch 5 because the same `min_delta=0.001` threshold was
used both to reset patience and to decide whether a checkpoint was "best".
Epoch 8 was only 0.00070 higher (roughly two additional exact spans among
3,566), while epoch 5 had the better validation loss, so epoch 5 remains a
defensible robust selection. The contract should nevertheless make the policy
explicit rather than letting one parameter silently implement two decisions.

Training orchestration should:

- save the absolute best checkpoint under the declared selection metric;
- use `min_delta` only to decide whether an improvement is large enough to
  reset early-stopping patience;
- report both the absolute-best epoch and the meaningful-improvement reference
  epoch when they differ;
- describe epochs as complete dataset passes and also report optimizer updates,
  microbatches, windows, and document exposures so users do not confuse five
  epochs with five gradient steps;
- treat `epochs` as a maximum ceiling, never as an expected target;
- retain the complete epoch curve and exact span counts, not only rounded F1;
- restart refit from the pinned base encoder for the selected count rather than
  continuing the selection checkpoint; and
- keep benchmark loading structurally impossible during selection.

If a maximum-epoch ceiling changes substantially, warmup must not silently
become much longer merely because it is expressed as a fraction of the maximum.
Prefer an explicit warmup-step or warmup-epoch contract, or report the resolved
step count before training begins.

## Recommended repository boundaries

The transferable workflow should assign each concern to one repository and
avoid language-specific copies of orchestration code:

- `meddeid-core`: canonical schemas for profile references, typed generation
  targets, provenance, batch state, review decisions, and model/dataset
  manifests;
- `meddeid-language-*`: locale resources, normalisation, parsing,
  pseudonymisation, approved synthetic identifiers, locale validators, and
  optional scenario vocabulary—not corpus orchestration;
- `meddeid-data`: generic case construction, LLM backend adapters, placeholder
  rendering, validation, batch locking/resume, review/invalidation, cost
  accounting, diversity gates, finalisation, and deterministic split creation;
- `meddeid-training`: generic selection/refit protocol, profile-aware dataset
  validation, auditable checkpoint policy, and self-contained export inputs;
- `meddeid-eval`: per-profile/per-label slices, hard-negative evaluation,
  boundary analysis, and independently generated formatting-stability variants;
- `meddeid`: bundle loading, ergonomic per-document profile resolution, and
  inference; and
- `meddeid-suite`: a thin onboarding scaffold, cross-repository conformance
  runner, development inventory, release checklist, and released locks.

The target user journey should be one documented state machine rather than a
collection of bespoke scripts:

1. scaffold a language package and one or more regional profiles;
2. fetch, build, audit, and lock resources;
3. validate the language pack with shared conformance fixtures;
4. create and estimate a corpus plan before spending API budget;
5. generate resumable 500-document batches with automatic and personal gates;
6. finalise a checksum-pinned development set and sealed benchmark;
7. run epoch selection, full-development refit, and one benchmark evaluation;
8. export and locally verify a multi-profile model bundle; and
9. update suite locks only in an explicit release operation.

Every command should print its resolved unversioned locales, independently
pinned artifact versions, source hashes,
output directory, next valid command, and whether it can spend money or expose
the sealed benchmark before doing work.

## Implementation order

1. **Completed:** finish and validate the English production corpus with the
   current local implementation.
2. **In progress:** the quality/diversity and semantic-type contracts are now
   generic; extract the remaining placeholder renderer, sampler, review state,
   and batch manifest from the English runner.
3. **Completed locally:** multi-profile training/run metadata, absolute-best
   checkpointing, independent stopping tolerance, single benchmark access, and
   standard evaluation slices.
4. **Completed locally:** multi-profile model export/inference and documented
   profile resolution using the clean multi-profile bundle contract.
5. Remove remaining direct Dutch imports and source-tree discovery fallbacks.
6. Add the cross-language conformance suite and onboarding documentation.

## Concrete meaning of the reusable production runner

The proposed `meddeid-data` orchestrator is not another authoring model and it
does not change how a note is written. It is the one command that remembers
where a paid production run is and permits only the next safe transition for
each document:

```text
planned case
  -> author attempt saved
  -> automatic PII/offset/negative validation
  -> optional model review saved
  -> personal decision saved
  -> 500-document batch audit and sign-off
  -> immutable final corpus
```

For example, after a terminal or API failure it should see that documents
1-347 are already accepted, retain every paid attempt in the cost ledger, and
resume at 348. If document 219 is later rejected, it archives that accepted
version, creates a replacement attempt for the same planned slot, re-runs all
gates, and invalidates the old sign-off until the replacement is personally
approved. A corpus-wide writer lock prevents another command from starting a
different paid batch at the same time. The current English implementation does
most of this, but the state transitions live in an English-specific script;
the recommendation is to expose them once for every new language.

## Why structured resource and case records matter

A flat list can answer only “pick a street” or “pick a hospital.” It cannot
reliably answer “pick a street, locality, postcode, hospital, identifier format,
and profession that belong together in this region and setting.” Structured
records retain the information required for that decision:

```json
{
  "value": "display spelling",
  "normalized": "lookup spelling",
  "weight": 127,
  "regions": ["Scotland"],
  "source_ids": ["publisher-release-id"],
  "attributes": {"kind": "acute_hospital"}
}
```

This has five practical benefits:

1. regionally impossible combinations can be prevented during sampling;
2. common and rare forms can be sampled deliberately instead of uniformly;
3. an odd generated value can be traced to its publisher and source release;
4. a resource update can be diffed by region/category rather than as an opaque
   changed text file; and
5. private semantic types such as `patient_mrn`,
   `laboratory_accession_id`, and `other_organization.school` can control
   surrounding wording without becoming public model labels.

The public lookup API can still return a flat list of values for callers that
do not need these properties. The structure is for correct generation,
auditing, and reproducibility, not additional complexity in ordinary inference.

## What is already shared conformance and what is not

Many required checks already exist, but they are not yet one shared,
parameterized conformance suite. At present:

- `meddeid-language-en` and `meddeid-language-nl` each have their own profiles,
  post-processing, date, identifier, and resource tests;
- `meddeid-eval stability` already provides reusable name/date perturbation and
  locale-provider tests;
- `meddeid`, `meddeid-training`, and the language packages have installation,
  bundle, export, and profile tests in their own repositories; and
- the English production script has its own placeholder, hard-negative,
  duplicate, pediatric, and 500-document gate tests.

What is missing is a single profile descriptor and runner that invokes the same
required tests for every new package, plus common wheel/sdist/npm and cross-
repository smoke tests. Without that layer, a new language author can omit a
category accidentally because copied local tests do not advertise the gap.

## Implemented reusable contracts (2026-08-21)

- `meddeid-data.corpus_quality` now exposes a language-neutral diversity
  contract covering profile/document-family balance, public labels, private
  semantic subtypes, pediatric ages, hard negatives, date periods, native note
  shapes, surface formats, four-gram diversity, and exact/skeleton/near
  duplicates. The English 500-document audit embeds this report while retaining
  its stricter local checks.
- `meddeid-data.semantic_types` resolves explicit private semantic types and
  provides a conservative source-slot fallback for the existing English
  corpus. These values do not alter the 14-label training head.
- `meddeid-training` now saves the absolute maximum of the declared selection
  metric, uses `min_delta` only for patience, reports both reference epochs,
  records microbatches/optimizer updates/document exposures, evaluates the
  benchmark no more than once, and emits locale, label, boundary, native-style,
  pediatric, and hard-negative slices.
- `meddeid` now has a directly tested profile-selection function and documents
  the user-facing priority: document metadata, explicit load-time default,
  single-profile bundle default, then an ambiguity error. Bare `en` remains
  invalid.

## Implemented onboarding workflow hardening (2026-08-26)

- `meddeid-core.onboarding` now defines dependency-free locale references,
  private generation targets, append-only attempt records, content-bound review
  decisions, and batch manifests. `ProfileRef` accepts `en_GB`, canonicalizes
  it to `en-GB`, and rejects both bare `en` and versioned locale identifiers
  such as `en-GB@1`; `GenerationTarget` permits only the ordered 14-label model
  taxonomy and rejects `Anonymize_Other`.
- `meddeid-data production` now provides immutable production plans,
  corpus-wide writer locking, attempt-level cost ceilings, validated batch
  registration, shared diversity audits, document review, sign-off, and
  deterministic sealed finalization. Paid authoring is selected through the
  `meddeid.production_backends` entry-point group; the current English/Luna
  implementation is one backend rather than a branch in the state engine.
- The production adapter can contribute its stricter locale audit and
  regeneration behavior while the state engine retains the common contract.
  Manual replacements and regenerations archive the prior content, invalidate
  all derived approvals, and preserve the attempt ledger. Cost reporting uses
  all author/reviewer API attempts—including failed and superseded calls—and
  projects the next batch from observed spend before starting it.
- English personal-review decisions are migrated to and stored with the exact
  canonical document SHA-256. Changing a document invalidates the decision;
  finalization rechecks quality-report and review-decision hashes instead of
  trusting a previously written sign-off file.
- Guided workflow templates are structurally validated for duplicate IDs,
  references, dependency cycles, command options, action shapes, and output
  declarations. The four onboarding workflows use an action-adapter registry,
  and passing quality, conformance, checkpoint, interface, and split contracts
  receive semantic output validation in addition to existence and SHA checks.
- The language scaffold now creates Python entry-point registration, separate
  JavaScript profile exports, per-profile manifests, resource command
  boundaries, source-lock instructions, Python/JavaScript tests, attribution
  files, and package metadata. Conformance imports each runtime profile and
  performs isolated wheel/sdist and npm pack checks when the tools are present.
- Model-checkpoint onboarding now reads the actual training metadata and tensor
  heads, comparing supported profiles, base encoder/revision, label order, and
  benchmark-access count against the requested bundle. The standard training
  command rejects epoch counts outside 1–30 while retaining absolute-best
  checkpoint selection and independent early-stopping tolerance.

The direct gold-annotation review remains a personal acceptance gate. Automated
checks should make that review faster and more focused, but they must not claim
to replace it.

## Decisions that should remain unchanged

- The canonical suite taxonomy remains 15 labels.
- Synthetic BERT training generation uses the exact 14-label
  `BERT_ENTITY_LABELS` sequence and rejects `Anonymize_Other`.
- Bare `en` remains ambiguous.
- GB and US rules/resources remain strictly separated even when one model is
  trained on both.
- A new weights bundle does not require a new source-code component.
- Released locks are updated only as part of an explicit release milestone.
