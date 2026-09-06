# MedDeID suite 0.2.0 release runbook

This release coordinates new versions of every suite repository. It publishes
`meddeid==0.3.0` plus four deliberately separate runtime artifacts: CPU,
PyTorch CUDA, the weight-free TensorRT gateway, and the T4-specific TensorRT
server. It also records the newly released supporting packages, browser
applications, legacy-site redirects, tagged model revisions and DOIs, and
study-software revisions. The checked candidate is
[`release/0.2.0-candidate.yaml`](release/0.2.0-candidate.yaml).

Do not combine the runtime images. Separate artifacts keep each download free
of frameworks for hardware the operator is not using. The one normal
performance control is `MEDDEID_SERVING_PROFILE=latency|throughput`; image
identity selects the backend and its benchmarked precision, batching,
transport, worker, and admission defaults.

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

## 2. Bring up a clean T4 release runner

The repository currently requires a self-hosted runner labeled `linux`, `x64`,
`nvidia`, and `t4-sm75`. Use a clean Azure `Standard_NC4as_T4_v3` VM with a
supported Ubuntu image, current NVIDIA driver, Docker Engine, and NVIDIA
Container Toolkit. Register it as an ephemeral repository runner so it accepts
only one job, then destroy the VM after retaining the Actions evidence. Never
reuse a host containing clinical data or unrelated credentials.

Before dispatch, all of these must succeed on the VM:

```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:13.3.1-base-ubuntu24.04 nvidia-smi
git clone https://github.com/stighellemans/meddeid.git
cd meddeid
./deploy/preflight_triton_host.sh t4-sm75 0
```

The GitHub account used to create an ephemeral/JIT repository runner needs
repository Administration write permission. Runner registration material is a
short-lived secret; do not place it in cloud-init, a repository, shell history,
or an Actions artifact.

## 3. Re-run both hardware gates from the final commit

Merge the candidate to `main`, record its commit, and dispatch both workflows
with publication disabled. Their checkout SHA must equal the intended
`v0.3.0` commit.

```bash
gh workflow run pytorch-cuda.yml \
  --repo stighellemans/meddeid \
  --ref main \
  -f image_version=0.3.0

gh workflow run triton-gpu-validation.yml \
  --repo stighellemans/meddeid \
  --ref main \
  -f gpu_target=t4-sm75 \
  -f image_version=0.3.0 \
  -f publish_image=false
```

The gates require real CUDA execution, HTTP smoke tests, CPU/CUDA/TensorRT
semantic parity, comparable cold start/throughput/latency/size/memory reports,
hardening checks, and vulnerability review. Check the run SHA and downloaded
evidence before marking the exact-commit GPU and runner gates `passed`.

## 4. Publish the MedDeID runtime release

Confirm that all four tag-triggered workflows can see an online clean T4
runner. Then tag the reviewed `meddeid` commit. The supporting component tags
recorded in the candidate must already be public and verified.

```bash
cd repos/meddeid
git tag -s v0.3.0 -m "meddeid 0.3.0"
git push origin v0.3.0
```

The tag triggers PyPI, multi-platform CPU, PyTorch CUDA, and the ready T4
TensorRT/gateway publication paths. A queued or failed GPU job is a partial
release and blocks suite publication.

## 5. Resolve and smoke-test public artifacts

After every workflow succeeds, resolve every component tag, all public PyPI
hashes, checked accelerator evidence, and every registry digest into a new
file:

```bash
python scripts/finalize_release_candidate.py \
  --candidate release/0.2.0-candidate.yaml \
  --output release/0.2.0-resolved.yaml
```

Install the resolved package line in a clean environment and pull each image by
its recorded digest. Run the three browser applications, CPU, and CUDA smoke
checks and re-run semantic parity against the pulled T4 server/gateway pair.
Confirm that OCI labels name the expected versions and exact source/model
revisions, and verify each published provenance attestation. Exercise rollback
by digest. Only then mark `pulled_artifact_smoke` as `passed` in the resolved
candidate.

## 6. Finalize the suite lock

All release gates must read `passed`. The finalizer refuses to emit a released
lock otherwise:

```bash
python scripts/finalize_release_candidate.py \
  --candidate release/0.2.0-resolved.yaml \
  --release \
  --write-suite-lock
python scripts/verify_release_candidate.py \
  --candidate suite-lock.yaml \
  --require-published
python scripts/verify_release.py
python scripts/verify_new_researcher_pilot.py \
  --lock release/0.2.0-resolved.yaml \
  --installed-packages \
  --full
```

Commit the released lock, changelog, and release evidence; tag the coordinator
as `v0.2.0` only after its public-release workflow succeeds. The release notes
must call the TensorRT plan T4-specific, identify A10G/L4 as build-on-request,
recommend CUDA for portable NVIDIA deployments and native MPS for Apple
silicon, and state that benchmark results are synthetic comparative evidence.
