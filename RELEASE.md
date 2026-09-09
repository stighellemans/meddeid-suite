# MedDeID suite 0.3.0 release runbook

This release coordinates new versions of every suite repository. It publishes
`meddeid==0.4.0`, CPU and PyTorch CUDA images, a weight-free TensorRT gateway
and runtime, and separate T4 and Ampere+ plans for the public Dutch and English models. It
also records the newly released supporting packages, browser
applications, legacy-site redirects, tagged model revisions and DOIs, and
study-software revisions. The checked candidate is
[`release/0.3.0-candidate.yaml`](release/0.3.0-candidate.yaml).

Do not combine the runtime images or put model plans inside them. Separate
artifacts keep each download free of frameworks and weights the operator is not
using. End users select hardware, model revision, and language profile;
release metadata connects those choices to the correct internal artifacts.

## 1. Freeze and validate the candidate

Only `repos/meddeid` is source for the current inference, API, gateway,
scheduler, and deployment behavior. Every other suite repository has its own
reviewed, tested, and signed release tag; those repositories do not define or
override the MedDeID runtime behavior.

```bash
python scripts/verify_release_candidate.py --local

cd repos/meddeid
uv sync --extra dev
uv run pytest -q
uv run --with build --with twine python -m build
uv run --with build --with twine python -m twine check dist/*
uv run --with-requirements site/requirements-docs.txt \
  python site/scripts/check_docs.py
uv run --with-requirements site/requirements-docs.txt \
  mkdocs build --strict --config-file site/mkdocs.yml
```

Update the three local test/build/documentation gates to `passed` only after
those exact commands succeed on the final candidate commit.

## 2. Prepare the two release GPU hosts

Use one clean Azure T4 host for the tag-triggered CUDA publication gate and one
clean Verda A100 host for both Ampere+ plan candidates. The T4 runner uses the
labels `linux`, `x64`, `nvidia`, and `t4-sm75`. The A100 runner uses `linux`,
`x64`, `nvidia`, and `ampere-plus`; keep it registered while the Dutch and
English jobs run sequentially and until the exact validated runtime and gateway
images are promoted. Never reuse a host containing clinical data or unrelated
credentials, and do not rent a second Ampere GPU for redundant testing.

Before dispatch, all of these must succeed on the VM:

```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:13.3.1-base-ubuntu24.04 nvidia-smi
git clone https://github.com/stighellemans/meddeid.git
cd meddeid
./deploy/preflight_triton_host.sh <t4-sm75-or-ampere-plus> 0
```

The GitHub account used to create a repository runner needs repository
Administration write permission. Runner registration material is a short-lived
secret; do not place it in cloud-init, a repository, shell history, or an
Actions artifact.

## 3. Run the final Ampere+ gates from the reviewed commit

Merge the candidate to `main`, record its commit, and dispatch the two Ampere+
plan-only jobs sequentially. Their checkout SHA must equal the intended
`v0.4.0` commit. The retained T4 candidate runs are `34285602671` (Dutch) and
`34285605174` (English), both from the runtime-equivalent commit
`14dc3db3f75fbcc0bacbae4b64e4dc9b404e0e80`.

```bash
gh workflow run triton-gpu-validation.yml \
  --repo stighellemans/meddeid \
  --ref main \
  -f gpu_target=ampere-plus \
  -f model_key=dutch_synthetic \
  -f image_version=0.4.0 \
  -f validation_scope=plan-only

gh workflow run triton-gpu-validation.yml \
  --repo stighellemans/meddeid \
  --ref main \
  -f gpu_target=ampere-plus \
  -f model_key=english_synthetic \
  -f image_version=0.4.0 \
  -f validation_scope=plan-only
```

The plan-only gate requires real TensorRT execution, 300-document CPU/TensorRT
comparison, startup and HTTP checks, hardening, vulnerability review, and
retained model repositories. Semantic differences are report-only; technical
errors remain blocking. Check each run SHA and downloaded evidence before
marking the Ampere+ and exact-commit gates `passed`.

## 4. Publish the MedDeID runtime release

Confirm that the tag-triggered CUDA workflow can see one online clean T4 runner
and that the Verda A100 runner remains online. Then tag the reviewed `meddeid` commit. The
supporting component tags recorded in the candidate must already be public and
verified.

```bash
cd repos/meddeid
git tag -s v0.4.0 -m "meddeid 0.4.0"
git push origin v0.4.0
```

The tag triggers PyPI, multi-platform CPU, and PyTorch CUDA publication. After
those gates and both Ampere+ candidates succeed, dispatch the two promotion
workflows from `v0.4.0`: `publish-triton-images.yml` with the two Ampere+ run
IDs, and `publish-triton-plans.yml` with the two retained T4 run IDs plus the
two Ampere+ run IDs. These workflows publish the exact validated bytes and
refuse to overwrite an existing tag. A queued or failed job is a partial
release and blocks suite publication.

## 5. Resolve and smoke-test public artifacts

After every workflow succeeds, install ORAS 1.3 or later and resolve every
component tag, all public PyPI hashes, checked accelerator evidence, container
digest, and TensorRT plan digest into a new file:

```bash
python scripts/finalize_release_candidate.py \
  --candidate release/0.3.0-candidate.yaml \
  --output release/0.3.0-resolved.yaml
```

Install the resolved package line in a clean environment and pull each image by
its recorded digest. Run the three browser applications, CPU, and CUDA smoke
checks and run pulled-artifact smoke checks against all four plans with the
shared runtime/gateway pair on their matching T4 and Ampere+ hosts.
Confirm that OCI labels name the expected versions and exact source/model
revisions, and verify each published provenance attestation. Exercise rollback
by digest. Only then mark `pulled_artifact_smoke` as `passed` in the resolved
candidate.

## 6. Finalize the suite lock

All release gates must read `passed`. The finalizer refuses to emit a released
lock otherwise:

```bash
python scripts/finalize_release_candidate.py \
  --candidate release/0.3.0-resolved.yaml \
  --release \
  --write-suite-lock
python scripts/verify_release_candidate.py \
  --candidate suite-lock.yaml \
  --require-published
python scripts/verify_release.py
python -m pip install 'meddeid-training[train]==0.3.0'
python scripts/verify_new_researcher_pilot.py \
  --lock release/0.3.0-resolved.yaml \
  --installed-packages \
  --full
```

Commit the released lock, changelog, and release evidence; tag the coordinator
as `v0.3.0` only after its public-release workflow succeeds. The release notes
must distinguish the exact T4 and hardware-compatible Ampere+ plans, identify
named A10G/L4 plans as optional specialized builds, recommend CUDA when no
released plan matches and native MPS for Apple
silicon, and state that benchmark results are synthetic comparative evidence.
