#!/usr/bin/env python3
"""Validate the next MedDeID suite lock without publishing anything."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import tomllib
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = ROOT / "release" / "0.3.1-candidate.yaml"
RELEASED_LOCK = ROOT / "suite-lock.yaml"
SHA40 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
DOI = re.compile(r"10\.\d{4,9}/\S+")
MODEL_TAG = re.compile(r"v\d+\.\d+\.\d+")
PRIVATE_FINE_TUNING_EXCEPTION_VERSION = "1.0"
PRIVATE_FINE_TUNING_EXCEPTION_PATH = (
    "MEDDEID-PRIVATE-FINE-TUNING-EXCEPTION-1.0.txt"
)
FIRST_EXCEPTION_RELEASE = (0, 2, 1)
EXPECTED_COMPONENTS = {
    "meddeid",
    "meddeid-core",
    "meddeid-language-en",
    "meddeid-language-nl",
    "meddeid-data",
    "meddeid-eval",
    "meddeid-training",
    "meddeid-annotate",
    "meddeid-curate",
    "meddeid-subannotate",
    "meddeid.github.io",
}
EXPECTED_TARGETS = {
    "t4-sm75": "ready",
    "ampere-plus": "ready",
    "a10g-sm86": "on-request",
    "l4-sm89": "on-request",
}
EXPECTED_SIZE_BUDGETS = {
    "meddeid-api-cpu": "cpu",
    "meddeid-api-cuda": "pytorch-cuda",
    "meddeid-triton-gateway": "tensorrt-gateway",
    "meddeid-triton-runtime": "tensorrt-server",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)



def require_parity_evidence(parity: dict[str, Any], accelerator: str) -> None:
    require(parity["passed"] is True, f"{accelerator} comparison did not pass its policy")
    differences = parity["semantic_differences"]
    difference_count = len(differences) if isinstance(differences, list) else differences
    require(type(difference_count) is int and difference_count >= 0,
            f"{accelerator} invalid semantic difference count")
    if difference_count:
        require(parity.get("semantic_policy") == "report-only",
                f"{accelerator} differences require explicit report-only policy")
        require(parity.get("complete") is True and parity.get("model_identity_matches") is True
                and parity.get("errors") == [] and parity.get("strict_passed") is False,
                f"{accelerator} report-only evidence must be complete, identity-matched and error-free")
        require(isinstance(parity.get("semantic_summary"), dict),
                f"{accelerator} report-only evidence needs discrepancy totals")


def version_tuple(value: str) -> tuple[int, ...]:
    require(
        re.fullmatch(r"\d+(?:\.\d+)*", value) is not None, f"invalid version: {value}"
    )
    return tuple(int(part) for part in value.split("."))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"{path}: top level must be a mapping")
    return payload


def validate_licensing_policy(payload: dict[str, Any]) -> None:
    """Validate a private-training exception only when a release adopts one."""

    licensing = payload.get("licensing")
    if licensing is None:
        return

    require(isinstance(licensing, dict), "licensing policy is missing")
    require(
        licensing.get("code_licence") == "AGPL-3.0-only",
        "code licence differs",
    )
    exception = licensing.get("private_fine_tuning_exception")
    require(isinstance(exception, dict), "private fine-tuning exception is missing")
    require(
        str(exception.get("version")) == PRIVATE_FINE_TUNING_EXCEPTION_VERSION,
        "private fine-tuning exception version differs",
    )
    require(
        exception.get("path") == PRIVATE_FINE_TUNING_EXCEPTION_PATH,
        "private fine-tuning exception path differs",
    )
    require(
        exception.get("approval_status") == "approved",
        "private fine-tuning exception lacks copyright-holder approval",
    )
    require(
        exception.get("adoption") == "express-artifact-notice",
        "private fine-tuning exception adoption rule differs",
    )
    adopters = exception.get("adopters")
    require(
        isinstance(adopters, list)
        and adopters
        and all(isinstance(item, str) and item for item in adopters),
        "private fine-tuning exception has no adopting artifacts",
    )

    exception_path = ROOT / PRIVATE_FINE_TUNING_EXCEPTION_PATH
    require(exception_path.is_file(), "private fine-tuning exception file is missing")
    recorded_sha256 = str(exception.get("sha256", ""))
    require(
        SHA256.fullmatch(recorded_sha256) is not None,
        "private fine-tuning exception has an invalid SHA-256",
    )
    require(
        sha256_file(exception_path) == recorded_sha256,
        "private fine-tuning exception hash differs",
    )


def validate_structure(payload: dict[str, Any], *, require_published: bool) -> None:
    require(
        payload.get("lock_format") == "meddeid.suite-lock.v2", "unsupported lock format"
    )
    allowed_status = {"release-candidate", "released"}
    require(payload.get("status") in allowed_status, "invalid release status")
    if require_published:
        require(payload["status"] == "released", "lock is not released")

    validate_licensing_policy(payload)

    released = load(RELEASED_LOCK)
    candidate_version = version_tuple(str(payload["suite_version"]))
    released_version = version_tuple(str(released["suite_version"]))
    require(
        candidate_version >= released_version, "candidate predates the released lock"
    )
    if candidate_version == released_version:
        require(
            released.get("status") == "released",
            "same-version public lock is not released",
        )
    require(set(payload["components"]) == EXPECTED_COMPONENTS, "component set differs")

    for name, component in payload["components"].items():
        action = component.get("release_action")
        require(action in {"publish", "reuse"}, f"{name}: invalid release action")
        require(
            component.get("tag") == f"v{component.get('version')}",
            f"{name}: tag/version mismatch",
        )
        commit = component.get("commit")
        if action == "reuse" or require_published:
            require(
                isinstance(commit, str) and SHA40.fullmatch(commit) is not None,
                f"{name}: invalid commit",
            )
        elif commit is not None:
            require(
                SHA40.fullmatch(str(commit)) is not None,
                f"{name}: invalid candidate commit",
            )
        if component.get("ecosystem") == "python":
            for field in ("wheel_sha256", "sdist_sha256"):
                value = component.get(field)
                if action == "reuse" or require_published:
                    require(
                        isinstance(value, str) and SHA256.fullmatch(value) is not None,
                        f"{name}: invalid {field}",
                    )
                elif value is not None:
                    require(
                        SHA256.fullmatch(str(value)) is not None,
                        f"{name}: invalid {field}",
                    )

    for name, container in payload["containers"].items():
        action = container.get("release_action")
        require(action in {"publish", "reuse"}, f"{name}: invalid release action")
        digest = container.get("digest")
        if action == "reuse" or require_published:
            require(
                isinstance(digest, str) and DIGEST.fullmatch(digest) is not None,
                f"{name}: invalid digest",
            )
        elif digest is not None:
            require(
                DIGEST.fullmatch(str(digest)) is not None, f"{name}: invalid digest"
            )
        if action == "publish":
            require(
                container.get("size_budget_key") == EXPECTED_SIZE_BUDGETS.get(name),
                f"{name}: image-size budget differs",
            )

    plans = payload.get("triton_plans")
    require(isinstance(plans, dict) and plans, "Triton plan set is missing")
    for name, plan in plans.items():
        action = plan.get("release_action")
        require(action in {"publish", "reuse"}, f"{name}: invalid release action")
        digest = plan.get("digest")
        if action == "reuse" or require_published:
            require(
                isinstance(digest, str) and DIGEST.fullmatch(digest) is not None,
                f"{name}: invalid artifact digest",
            )
        elif digest is not None:
            require(
                DIGEST.fullmatch(str(digest)) is not None,
                f"{name}: invalid artifact digest",
            )
        if action == "publish":
            require(
                plan.get("suite_version") == payload["suite_version"],
                f"{name}: suite version differs",
            )
            require(
                plan.get("meddeid_version")
                == payload["components"]["meddeid"]["version"],
                f"{name}: MedDeID version differs",
            )
        model_name = plan.get("model")
        require(model_name in payload["models"], f"{name}: unknown model")
        if action == "publish":
            require(
                plan.get("revision") == payload["models"][model_name]["revision"],
                f"{name}: model revision differs",
            )
        else:
            require(
                SHA40.fullmatch(str(plan.get("revision", ""))) is not None,
                f"{name}: reused plan has no immutable model revision",
            )
        profiles = plan.get("language_profiles")
        require(
            isinstance(profiles, list)
            and profiles
            and all(isinstance(item, str) and item for item in profiles),
            f"{name}: language profiles are missing",
        )
        require(
            isinstance(plan.get("reference"), str)
            and plan["reference"].startswith("ghcr.io/"),
            f"{name}: invalid OCI artifact reference",
        )
        if plan.get("hardware") == "ampere-plus":
            require(
                plan.get("target") == "ampere-plus",
                f"{name}: Ampere+ target differs",
            )

    budget_ref = payload["image_size_budgets"]
    require(
        SHA256.fullmatch(str(budget_ref["sha256"])) is not None,
        "invalid image-size budget hash",
    )

    for section in ("models", "datasets"):
        for name, artifact in payload[section].items():
            require(
                SHA40.fullmatch(str(artifact["revision"])) is not None,
                f"{name}: invalid Hub revision",
            )
            hash_fields = [key for key in artifact if key.endswith("sha256")]
            require(hash_fields, f"{name}: no SHA-256 evidence")
            for field in hash_fields:
                require(
                    SHA256.fullmatch(str(artifact[field])) is not None,
                    f"{name}: invalid {field}",
                )

    for name, model in payload["models"].items():
        require(
            MODEL_TAG.fullmatch(str(model.get("tag", ""))) is not None,
            f"{name}: model tag differs",
        )
        require(
            SHA40.fullmatch(str(model.get("tag_revision", ""))) is not None,
            f"{name}: invalid model tag revision",
        )
        require(
            DOI.fullmatch(str(model.get("doi", ""))) is not None,
            f"{name}: invalid model DOI",
        )

    study_software = payload.get("study_software", {})
    require(
        set(study_software) == {"deid-battery", "belgian-deduce"},
        "study software set differs",
    )
    for name, component in study_software.items():
        require(
            SHA40.fullmatch(str(component.get("commit", ""))) is not None,
            f"{name}: invalid study-software commit",
        )
        require(component.get("tag"), f"{name}: study-software tag is missing")

    profiles = payload["language_profiles"]
    require(set(profiles) == {"en", "nl"}, "English and Dutch profiles are required")
    require(
        set(profiles["en"]["ids"]) == {"en-GB", "en-US"}, "English profile IDs differ"
    )
    require(
        set(profiles["nl"]["ids"]) == {"nl-BE", "nl-NL"}, "Dutch profile IDs differ"
    )
    for name, profile in profiles.items():
        require(
            profile["javascript_status"] == "published",
            f"{name}: JavaScript package is not public",
        )
        require(
            SHA40.fullmatch(str(profile["javascript_git_head"])) is not None,
            f"{name}: invalid npm Git head",
        )

    targets = payload["accelerators"]["tensorrt"]["targets"]
    require(targets == EXPECTED_TARGETS, "TensorRT publication catalog differs")
    require(
        payload["accelerators"]["mps"]["availability"] == "ready-native",
        "MPS readiness differs",
    )
    cuda_availability = payload["accelerators"]["pytorch_cuda"]["availability"]
    if require_published:
        require(cuda_availability == "ready", "released CUDA artifact is not ready")
    else:
        require(
            cuda_availability in {"release-candidate", "ready"},
            "CUDA readiness differs",
        )

    gates = payload["release_gates"]
    require(
        all(value in {"passed", "pending"} for value in gates.values()),
        "invalid release-gate state",
    )
    if require_published:
        pending = [name for name, value in gates.items() if value != "passed"]
        require(not pending, f"released lock retains pending gates: {pending}")


def validate_local(payload: dict[str, Any]) -> None:
    meddeid = ROOT / payload["source_policy"]["primary_checkout"]
    require((meddeid / ".git").is_dir(), "meddeid source checkout is unavailable")
    with (meddeid / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    version = str(payload["components"]["meddeid"]["version"])
    require(
        pyproject["project"]["version"] == version, "meddeid pyproject version differs"
    )
    init_text = (meddeid / "src/meddeid/__init__.py").read_text(encoding="utf-8")
    require(
        f'__version__ = "{version}"' in init_text, "meddeid runtime version differs"
    )
    citation = yaml.safe_load((meddeid / "CITATION.cff").read_text(encoding="utf-8"))
    require(str(citation["version"]) == version, "meddeid citation version differs")
    changelog = (meddeid / "CHANGELOG.md").read_text(encoding="utf-8")
    require(f"## [{version}]" in changelog, "meddeid changelog has no release entry")

    core_commit = payload["components"]["meddeid-core"]["commit"]
    en_commit = payload["components"]["meddeid-language-en"]["commit"]
    nl_commit = payload["components"]["meddeid-language-nl"]["commit"]
    for relative in ("Dockerfile", "deploy/triton-gateway.Dockerfile"):
        text = (meddeid / relative).read_text(encoding="utf-8")
        for commit in (core_commit, en_commit, nl_commit):
            require(
                commit in text,
                f"{relative}: released dependency commit {commit} is absent",
            )

    for accelerator in ("mps", "tensorrt"):
        evidence = payload["accelerators"][accelerator]["evidence"]
        path = meddeid / evidence["path"]
        require(path.is_file(), f"missing {accelerator} evidence: {path}")
        require(
            sha256_file(path) == evidence["sha256"],
            f"{accelerator} evidence hash differs",
        )
        summary = json.loads(path.read_text(encoding="utf-8"))
        require_parity_evidence(summary["parity"], accelerator)

    catalog_ref = payload["accelerators"]["tensorrt"]["target_catalog"]
    catalog = json.loads((meddeid / catalog_ref["path"]).read_text(encoding="utf-8"))
    actual_targets = {item["id"]: item["release_status"] for item in catalog["targets"]}
    require(actual_targets == EXPECTED_TARGETS, "local TensorRT target catalog differs")

    release_catalog_path = meddeid / "deploy/triton/release.json"
    require(release_catalog_path.is_file(), "local Triton release catalog is missing")
    release_catalog = json.loads(release_catalog_path.read_text(encoding="utf-8"))
    published_plans = [
        plan
        for plan in payload["triton_plans"].values()
        if plan["release_action"] == "publish"
    ]
    provenance_plan = published_plans[0] if published_plans else next(
        iter(payload["triton_plans"].values())
    )
    require(
        release_catalog.get("suite_version") == provenance_plan["suite_version"],
        "local Triton release catalog has a different suite version",
    )
    require(
        release_catalog.get("meddeid_version")
        == provenance_plan["meddeid_version"],
        "local Triton release catalog has a different MedDeID version",
    )
    require(
        release_catalog.get("images", {}).get("gateway")
        == payload["containers"]["meddeid-triton-gateway"]["reference"],
        "local Triton gateway reference differs",
    )
    runtime_references = set(
        release_catalog.get("images", {}).get("runtimes", {}).values()
    )
    require(
        runtime_references
        == {payload["containers"]["meddeid-triton-runtime"]["reference"]},
        "local Triton runtime reference differs",
    )
    local_plans = {
        (item.get("model_key"), item.get("hardware")): item
        for item in release_catalog.get("plans", [])
    }
    require(
        len(local_plans) == len(payload["triton_plans"]),
        "local Triton plan catalog differs",
    )
    for name, plan in payload["triton_plans"].items():
        local = local_plans.get((plan["model"], plan["hardware"]))
        require(local is not None, f"{name}: absent from local Triton release catalog")
        require(local.get("target") == plan["target"], f"{name}: target differs")
        require(
            local.get("model") == payload["models"][plan["model"]]["repository"],
            f"{name}: model repository differs",
        )
        require(
            local.get("bundle_sha256")
            == payload["models"][plan["model"]]["contract_sha256"],
            f"{name}: bundle contract differs",
        )
        for field in ("revision", "language_profiles", "artifact"):
            expected = plan["reference"] if field == "artifact" else plan[field]
            require(local.get(field) == expected, f"{name}: {field} differs")
        benchmark = local.get("benchmark", {})
        dataset_name = f"{plan['model']}_benchmark"
        dataset = payload["datasets"][dataset_name]
        require(
            benchmark.get("dataset") == dataset["repository"],
            f"{name}: benchmark dataset differs",
        )
        require(
            benchmark.get("revision") == dataset["revision"],
            f"{name}: benchmark revision differs",
        )
        require(
            benchmark.get("file") == dataset["artifact"],
            f"{name}: benchmark file differs",
        )

    budget_ref = payload["image_size_budgets"]
    budget_path = meddeid / budget_ref["path"]
    require(budget_path.is_file(), f"missing image-size budgets: {budget_path}")
    require(
        sha256_file(budget_path) == budget_ref["sha256"],
        "image-size budget hash differs",
    )

    excluded = set(payload["source_policy"]["dirty_worktrees_excluded"])
    dirty: set[str] = set()
    repos = ROOT / "repos"
    for repo in repos.iterdir():
        if not (repo / ".git").is_dir() or repo.name == "meddeid":
            continue
        result = subprocess.check_output(
            ["git", "-C", str(repo), "status", "--porcelain"], text=True
        )
        if result.strip():
            dirty.add(repo.name)
    unexpected = dirty - excluded
    require(
        not unexpected,
        f"dirty component worktrees are not explicitly excluded: {sorted(unexpected)}",
    )
    stale = excluded - dirty
    if stale:
        print(f"note: exclusions currently clean or unavailable: {sorted(stale)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument(
        "--local", action="store_true", help="also check the nested source worktrees"
    )
    parser.add_argument("--require-published", action="store_true")
    args = parser.parse_args()
    payload = load(args.candidate)
    validate_structure(payload, require_published=args.require_published)
    if args.local:
        validate_local(payload)
    print(f"valid MedDeID suite candidate: {args.candidate}")


if __name__ == "__main__":
    main()
