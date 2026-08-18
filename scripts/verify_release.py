#!/usr/bin/env python3
"""Verify the public MedDeID release lock against immutable services."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "suite-lock.yaml"
SHA40 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def read_json(url: str) -> dict:
    for attempt in range(3):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "meddeid-release-verifier/1"}
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def remote_sha256(url: str) -> str:
    for attempt in range(3):
        try:
            digest = hashlib.sha256()
            request = urllib.request.Request(
                url, headers={"User-Agent": "meddeid-release-verifier/1"}
            )
            with urllib.request.urlopen(request, timeout=180) as response:
                while chunk := response.read(1024 * 1024):
                    digest.update(chunk)
            return digest.hexdigest()
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def verify_python_components(lock: dict) -> None:
    for name, component in lock["components"].items():
        if "wheel_sha256" not in component:
            continue
        version = str(component["version"])
        installed = importlib.metadata.version(name)
        require(installed == version, f"{name}: installed {installed}, locked {version}")
        payload = read_json(f"https://pypi.org/pypi/{name}/{version}/json")
        hashes = {item["packagetype"]: item["digests"]["sha256"] for item in payload["urls"]}
        require(hashes.get("bdist_wheel") == component["wheel_sha256"], f"{name}: wheel hash differs")
        require(hashes.get("sdist") == component["sdist_sha256"], f"{name}: sdist hash differs")
    print("Python package versions and PyPI hashes verified")


def verify_git_components(lock: dict) -> None:
    for name, component in lock["components"].items():
        commit = str(component["commit"])
        require(SHA40.fullmatch(commit) is not None, f"{name}: invalid commit")
        output = subprocess.check_output(
            ["git", "ls-remote", component["repository"], f"refs/tags/{component['tag']}^{{}}"],
            text=True,
        ).strip()
        require(output, f"{name}: release tag is not public")
        resolved = output.split()[0]
        require(resolved == commit, f"{name}: tag resolves to {resolved}, locked {commit}")
    print("GitHub release tags verified")


def verify_hugging_face(lock: dict) -> None:
    for name, dataset in lock["datasets"].items():
        revision = str(dataset["revision"])
        require(SHA40.fullmatch(revision) is not None, f"{name}: invalid Hub revision")
        url = (
            f"https://huggingface.co/datasets/{dataset['repository']}/resolve/"
            f"{revision}/{dataset['artifact']}?download=true"
        )
        require(remote_sha256(url) == dataset["sha256"], f"{name}: artifact hash differs")
    model = lock["model"]
    model_url = (
        f"https://huggingface.co/{model['repository']}/resolve/"
        f"{model['revision']}/bundle.json?download=true"
    )
    bundle = read_json(model_url)
    require(bundle["base_encoder"] == model["base_encoder"], "model base encoder differs")
    demo = lock["hosted_demo"]
    space = read_json(f"https://huggingface.co/api/spaces/{demo['repository']}")
    require(space["sha"] == demo["revision"], "hosted demo revision differs")
    require(space["private"] is False, "hosted demo is not public")
    collection = lock["hugging_face_collection"]
    collection_payload = read_json(f"https://huggingface.co/api/collections/{collection['slug']}")
    collection_items = {item.get("item_id", item.get("id")) for item in collection_payload["items"]}
    require(demo["repository"] in collection_items, "hosted demo is absent from the collection")
    print("Anonymous immutable Hugging Face artifacts and hosted demo verified")


def verify_npm(lock: dict) -> None:
    profile = lock["language_profile"]
    require(profile["javascript_status"] == "published", "Dutch JavaScript profile is not released")
    package_name, version = profile["javascript_package"].rsplit("@", 1)
    encoded = package_name.replace("/", "%2f")
    payload = read_json(f"https://registry.npmjs.org/{encoded}/{version}")
    require(payload["version"] == version, "npm profile version differs")
    require(payload["name"] == package_name, "npm profile name differs")
    require(payload["gitHead"] == profile["javascript_git_head"], "npm profile Git head differs")
    require(payload["dist"]["shasum"] == profile["javascript_shasum"], "npm shasum differs")
    require(
        payload["dist"]["integrity"] == profile["javascript_integrity"],
        "npm integrity digest differs",
    )
    print("npm language profile verified")


def verify_archive(lock: dict, *, allow_candidate: bool) -> None:
    archive = lock["archive"]
    if archive["status"] != "published":
        require(allow_candidate, "Zenodo schema-v2 archive is not published")
        print("Zenodo schema-v2 archive pending (release-candidate mode)")
        return
    record = read_json(f"https://zenodo.org/api/records/{archive['record_id']}")
    require(record["doi"] == archive["version_doi"], "Zenodo DOI differs")
    require(record["conceptdoi"] == archive["concept_doi"], "Zenodo concept DOI differs")
    require(record["status"] == "published", "Zenodo record is not published")
    files = {item["key"]: item for item in record["files"]}
    archive_file = files["meddeid-dutch-synthetic-data.zip"]
    require(
        remote_sha256(archive_file["links"].get("content", archive_file["links"]["self"]))
        == archive["archive_sha256"],
        "Zenodo archive hash differs",
    )
    print("Zenodo release verified")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-candidate", action="store_true")
    args = parser.parse_args()
    lock = yaml.safe_load(LOCK_PATH.read_text(encoding="utf-8"))
    require(lock["lock_format"] == "meddeid.suite-lock.v1", "unsupported lock format")
    require(lock["status"] in {"release-candidate", "released"}, "invalid release status")
    if lock["status"] != "released":
        require(args.allow_candidate, "suite lock is not released")
    require(SHA256.fullmatch(lock["model"]["weights_sha256"]) is not None, "invalid model hash")
    verify_python_components(lock)
    verify_git_components(lock)
    verify_hugging_face(lock)
    if lock["language_profile"]["javascript_status"] == "published":
        verify_npm(lock)
    else:
        require(args.allow_candidate, "npm profile is not published")
        print("npm language profile pending (release-candidate mode)")
    verify_archive(lock, allow_candidate=args.allow_candidate)
    print(f"valid MedDeID suite lock: {LOCK_PATH}")


if __name__ == "__main__":
    main()
