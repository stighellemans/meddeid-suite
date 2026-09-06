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
DEFAULT_CANDIDATE = ROOT / "release" / "0.2.0-candidate.yaml"
RELEASED_LOCK = ROOT / "suite-lock.yaml"
SHA40 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
DOI = re.compile(r"10\.\d{4,9}/\S+")
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
    "a10g-sm86": "on-request",
    "l4-sm89": "on-request",
}
EXPECTED_SIZE_BUDGETS = {
    "meddeid-api-cpu": "cpu",
    "meddeid-api-cuda": "pytorch-cuda",
    "meddeid-triton-gateway": "tensorrt-gateway",
    "meddeid-triton-t4-sm75": "tensorrt-server",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


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


def validate_structure(payload: dict[str, Any], *, require_published: bool) -> None:
    require(
        payload.get("lock_format") == "meddeid.suite-lock.v2", "unsupported lock format"
    )
    allowed_status = {"release-candidate", "released"}
    require(payload.get("status") in allowed_status, "invalid release status")
    if require_published:
        require(payload["status"] == "released", "lock is not released")

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
        require(model.get("tag") == "v1.0.0", f"{name}: model tag differs")
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
        require(
            summary["parity"]["passed"] is True, f"{accelerator} parity did not pass"
        )
        require(
            summary["parity"]["semantic_differences"] == 0,
            f"{accelerator} parity differs",
        )

    catalog_ref = payload["accelerators"]["tensorrt"]["target_catalog"]
    catalog = json.loads((meddeid / catalog_ref["path"]).read_text(encoding="utf-8"))
    actual_targets = {item["id"]: item["release_status"] for item in catalog["targets"]}
    require(actual_targets == EXPECTED_TARGETS, "local TensorRT target catalog differs")

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
