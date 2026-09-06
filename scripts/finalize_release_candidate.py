#!/usr/bin/env python3
"""Resolve public release identities into a v2 suite lock after publication."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from verify_release_candidate import validate_structure

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = ROOT / "release" / "0.2.0-candidate.yaml"


def read_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url, headers={"User-Agent": "meddeid-release-finalizer/1"}
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


def remote_sha256(url: str) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": "meddeid-release-finalizer/1"}
    )
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=90) as response:
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_component(name: str, component: dict[str, Any]) -> None:
    tag = str(component["tag"])
    output = subprocess.check_output(
        ["git", "ls-remote", component["repository"], f"refs/tags/{tag}^{{}}"],
        text=True,
    ).strip()
    if not output:
        raise RuntimeError(f"{name}: public annotated tag is unavailable: {tag}")
    component["commit"] = output.split()[0]
    if component.get("ecosystem") == "python":
        version = str(component["version"])
        pypi = read_json(f"https://pypi.org/pypi/{name}/{version}/json")
        hashes = {
            item["packagetype"]: item["digests"]["sha256"]
            for item in pypi["urls"]
        }
        component["wheel_sha256"] = hashes["bdist_wheel"]
        component["sdist_sha256"] = hashes["sdist"]


def verify_evidence(payload: dict[str, Any]) -> None:
    commit = payload["components"]["meddeid"]["commit"]
    for accelerator in ("mps", "tensorrt"):
        evidence = payload["accelerators"][accelerator]["evidence"]
        url = f"https://raw.githubusercontent.com/stighellemans/meddeid/{commit}/{evidence['path']}"
        actual = remote_sha256(url)
        if actual != evidence["sha256"]:
            raise RuntimeError(f"{accelerator} evidence hash differs at release commit")
    budget_ref = payload["image_size_budgets"]
    url = (
        "https://raw.githubusercontent.com/stighellemans/meddeid/"
        f"{commit}/{budget_ref['path']}"
    )
    if remote_sha256(url) != budget_ref["sha256"]:
        raise RuntimeError("image-size budget hash differs at release commit")


def resolve_container_digest(reference: str) -> str:
    output = subprocess.check_output(
        [
            "docker",
            "buildx",
            "imagetools",
            "inspect",
            reference,
            "--format",
            "{{json .Manifest.Digest}}",
        ],
        text=True,
    ).strip()
    digest = json.loads(output)
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise RuntimeError(f"could not resolve container digest for {reference}")
    return digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "release" / "0.2.0-resolved.yaml"
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="require every gate and emit released status",
    )
    parser.add_argument(
        "--write-suite-lock",
        action="store_true",
        help="write suite-lock.yaml; requires --release",
    )
    args = parser.parse_args()
    if args.write_suite_lock and not args.release:
        raise SystemExit("--write-suite-lock requires --release")

    payload = yaml.safe_load(args.candidate.read_text(encoding="utf-8"))
    validate_structure(payload, require_published=False)
    resolved = copy.deepcopy(payload)
    for name, component in resolved["components"].items():
        resolve_component(name, component)
    verify_evidence(resolved)
    for container in resolved["containers"].values():
        if container["release_action"] == "publish":
            container["digest"] = resolve_container_digest(container["reference"])
    resolved["accelerators"]["pytorch_cuda"]["availability"] = "ready"
    resolved["release_gates"]["public_pypi_artifacts"] = "passed"
    resolved["release_gates"]["public_container_digests"] = "passed"

    if args.release:
        pending = [
            name
            for name, state in resolved["release_gates"].items()
            if state != "passed"
        ]
        if pending:
            raise RuntimeError(f"cannot release while gates are pending: {pending}")
        resolved["status"] = "released"
        resolved["released_at"] = datetime.now(UTC).date().isoformat()
    validate_structure(resolved, require_published=args.release)

    output = ROOT / "suite-lock.yaml" if args.write_suite_lock else args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(resolved, sort_keys=False), encoding="utf-8")
    print(
        f"wrote verified {'release lock' if args.release else 'resolved candidate'}: {output}"
    )


if __name__ == "__main__":
    main()
