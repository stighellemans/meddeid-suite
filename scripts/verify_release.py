#!/usr/bin/env python3
"""Verify the public MedDeID release lock against immutable services."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import subprocess
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "suite-lock.yaml"
SHA40 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
DOI = re.compile(r"10\.\d{4,9}/\S+")
PRIVATE_FINE_TUNING_EXCEPTION_PATH = (
    "MEDDEID-PRIVATE-FINE-TUNING-EXCEPTION-1.0.txt"
)


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_licensing_policy(lock: dict) -> None:
    licensing = lock.get("licensing")
    if licensing is None:
        return

    require(isinstance(licensing, dict), "licensing policy is missing")
    require(
        licensing.get("code_licence") == "AGPL-3.0-only",
        "code licence differs",
    )
    exception = licensing.get("private_fine_tuning_exception")
    require(isinstance(exception, dict), "private fine-tuning exception is missing")
    require(str(exception.get("version")) == "1.0", "exception version differs")
    require(
        exception.get("path") == PRIVATE_FINE_TUNING_EXCEPTION_PATH,
        "exception path differs",
    )
    require(
        exception.get("approval_status") == "approved",
        "exception lacks copyright-holder approval",
    )
    require(
        exception.get("adoption") == "express-artifact-notice",
        "exception adoption rule differs",
    )
    adopters = exception.get("adopters")
    require(
        isinstance(adopters, list)
        and adopters
        and all(isinstance(item, str) and item for item in adopters),
        "exception has no adopting artifacts",
    )
    exception_path = ROOT / PRIVATE_FINE_TUNING_EXCEPTION_PATH
    require(exception_path.is_file(), "exception file is missing")
    require(
        SHA256.fullmatch(str(exception.get("sha256", ""))) is not None,
        "exception has an invalid SHA-256",
    )
    require(
        sha256_file(exception_path) == exception["sha256"],
        "exception hash differs",
    )
    print("Private fine-tuning exception verified")


def verify_python_components(lock: dict) -> None:
    for name, component in lock["components"].items():
        if "wheel_sha256" not in component:
            continue
        version = str(component["version"])
        installed = importlib.metadata.version(name)
        require(
            installed == version, f"{name}: installed {installed}, locked {version}"
        )
        payload = read_json(f"https://pypi.org/pypi/{name}/{version}/json")
        hashes = {
            item["packagetype"]: item["digests"]["sha256"] for item in payload["urls"]
        }
        require(
            hashes.get("bdist_wheel") == component["wheel_sha256"],
            f"{name}: wheel hash differs",
        )
        require(
            hashes.get("sdist") == component["sdist_sha256"],
            f"{name}: sdist hash differs",
        )
    print("Python package versions and PyPI hashes verified")


def verify_git_components(lock: dict) -> None:
    tagged_repositories = {
        **lock["components"],
        **lock.get("study_software", {}),
    }
    for name, component in tagged_repositories.items():
        commit = str(component["commit"])
        require(SHA40.fullmatch(commit) is not None, f"{name}: invalid commit")
        output = subprocess.check_output(
            [
                "git",
                "ls-remote",
                component["repository"],
                f"refs/tags/{component['tag']}^{{}}",
            ],
            text=True,
        ).strip()
        if not output:
            output = subprocess.check_output(
                [
                    "git",
                    "ls-remote",
                    component["repository"],
                    f"refs/tags/{component['tag']}",
                ],
                text=True,
            ).strip()
        require(output, f"{name}: release tag is not public")
        resolved = output.split()[0]
        require(
            resolved == commit, f"{name}: tag resolves to {resolved}, locked {commit}"
        )
    print("GitHub release tags verified")


def verify_hugging_face(lock: dict) -> None:
    for name, dataset in lock["datasets"].items():
        revision = str(dataset["revision"])
        require(SHA40.fullmatch(revision) is not None, f"{name}: invalid Hub revision")
        url = (
            f"https://huggingface.co/datasets/{dataset['repository']}/resolve/"
            f"{revision}/{dataset['artifact']}?download=true"
        )
        require(
            remote_sha256(url) == dataset["sha256"], f"{name}: artifact hash differs"
        )
    if "models" in lock:
        for name, model in lock["models"].items():
            revision = str(model["revision"])
            require(
                SHA40.fullmatch(revision) is not None, f"{name}: invalid model revision"
            )
            api = read_json(
                f"https://huggingface.co/api/models/{model['repository']}/revision/"
                f"{revision}?blobs=true"
            )
            require(api["sha"] == revision, f"{name}: model revision differs")
            tag = str(model["tag"])
            tag_output = subprocess.check_output(
                [
                    "git",
                    "ls-remote",
                    f"https://huggingface.co/{model['repository']}",
                    f"refs/tags/{tag}",
                ],
                text=True,
            ).strip()
            require(tag_output, f"{name}: model tag is not public")
            require(
                tag_output.split()[0] == model["tag_revision"],
                f"{name}: model tag does not resolve to the locked tag revision",
            )
            require(
                DOI.fullmatch(str(model.get("doi", ""))) is not None,
                f"{name}: invalid model DOI",
            )
            siblings = {item["rfilename"]: item for item in api["siblings"]}
            weights = siblings[model["weights_artifact"]]
            lfs = weights.get("lfs") or {}
            if lfs.get("sha256"):
                require(
                    lfs["sha256"] == model["weights_sha256"],
                    f"{name}: weights hash differs",
                )
            else:
                weights_url = (
                    f"https://huggingface.co/{model['repository']}/resolve/"
                    f"{revision}/{model['weights_artifact']}?download=true"
                )
                require(
                    remote_sha256(weights_url) == model["weights_sha256"],
                    f"{name}: weights hash differs",
                )
            bundle_url = (
                f"https://huggingface.co/{model['repository']}/resolve/"
                f"{revision}/{model['bundle_artifact']}?download=true"
            )
            require(
                remote_sha256(bundle_url) == model["bundle_sha256"],
                f"{name}: bundle hash differs",
            )
            bundle = read_json(bundle_url)
            require(
                bundle["base_encoder"] == model["base_encoder"],
                f"{name}: base encoder differs",
            )
    else:
        model = lock["model"]
        model_url = (
            f"https://huggingface.co/{model['repository']}/resolve/"
            f"{model['revision']}/bundle.json?download=true"
        )
        bundle = read_json(model_url)
        require(
            bundle["base_encoder"] == model["base_encoder"],
            "model base encoder differs",
        )
    demo = lock["hosted_demo"]
    space = read_json(f"https://huggingface.co/api/spaces/{demo['repository']}")
    require(space["sha"] == demo["revision"], "hosted demo revision differs")
    require(space["private"] is False, "hosted demo is not public")
    collection = lock["hugging_face_collection"]
    collection_payload = read_json(
        f"https://huggingface.co/api/collections/{collection['slug']}"
    )
    collection_items = {
        item.get("item_id", item.get("id")) for item in collection_payload["items"]
    }
    require(
        demo["repository"] in collection_items,
        "hosted demo is absent from the collection",
    )
    print("Anonymous immutable Hugging Face artifacts and hosted demo verified")


def verify_npm(lock: dict) -> None:
    profiles = (
        lock["language_profiles"]
        if "language_profiles" in lock
        else {"nl": lock["language_profile"]}
    )
    for name, profile in profiles.items():
        require(
            profile["javascript_status"] == "published",
            f"{name}: JavaScript profile is not released",
        )
        package_name, version = profile["javascript_package"].rsplit("@", 1)
        encoded = package_name.replace("/", "%2f")
        payload = read_json(f"https://registry.npmjs.org/{encoded}/{version}")
        require(payload["version"] == version, f"{name}: npm profile version differs")
        require(payload["name"] == package_name, f"{name}: npm profile name differs")
        require(
            payload["gitHead"] == profile["javascript_git_head"],
            f"{name}: npm Git head differs",
        )
        require(
            payload["dist"]["shasum"] == profile["javascript_shasum"],
            f"{name}: npm shasum differs",
        )
        require(
            payload["dist"]["integrity"] == profile["javascript_integrity"],
            f"{name}: npm integrity digest differs",
        )
    print("npm language profiles verified")


def verify_triton_plans(lock: dict) -> None:
    for name, plan in lock.get("triton_plans", {}).items():
        reference = str(plan["reference"])
        repository = reference.rsplit(":", 1)[0]
        digest = str(plan["digest"])
        require(
            re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is not None,
            f"{name}: invalid Triton plan digest",
        )
        output = subprocess.check_output(
            ["oras", "manifest", "fetch", "--descriptor", f"{repository}@{digest}"],
            text=True,
        )
        descriptor = json.loads(output)
        require(descriptor.get("digest") == digest, f"{name}: artifact digest differs")
        manifest_output = subprocess.check_output(
            ["oras", "manifest", "fetch", f"{repository}@{digest}"], text=True
        )
        manifest = json.loads(manifest_output)
        require(
            manifest.get("artifactType")
            == "application/vnd.meddeid.triton-model-repository.v1",
            f"{name}: artifact type differs",
        )
        with tempfile.TemporaryDirectory(prefix="meddeid-plan-") as raw:
            destination = Path(raw)
            subprocess.check_call(
                [
                    "oras",
                    "pull",
                    f"{repository}@{digest}",
                    "--output",
                    str(destination),
                ],
                stdout=subprocess.DEVNULL,
            )
            archive_path = destination / "model-repository.tar.gz"
            require(archive_path.is_file(), f"{name}: plan archive is missing")
            with tarfile.open(archive_path, mode="r:gz") as archive:
                member = archive.extractfile("build-manifest.json")
                require(member is not None, f"{name}: build manifest is missing")
                build = json.load(member)

        model = lock["models"][plan["model"]]
        expected = {
            ("release", "suite_version"): plan["suite_version"],
            ("release", "meddeid_version"): plan["meddeid_version"],
            ("model", "id"): model["repository"],
            ("model", "revision"): plan["revision"],
            ("model", "bundle_sha256"): model["contract_sha256"],
            ("target", "id"): plan["target"],
        }
        for (section, field), value in expected.items():
            require(
                build.get(section, {}).get(field) == value,
                f"{name}: {section}.{field} differs",
            )
        require(
            set(build.get("model", {}).get("language_profiles", []))
            == set(plan["language_profiles"]),
            f"{name}: language profiles differ",
        )
    if lock.get("triton_plans"):
        print("TensorRT plan artifacts verified")


def verify_archive(lock: dict, *, allow_candidate: bool) -> None:
    archives = lock.get("archives")
    if archives is None:
        archives = {
            "dutch": {
                **lock["archive"],
                "filename": "meddeid-dutch-synthetic-data.zip",
                "sha256": lock["archive"]["archive_sha256"],
            }
        }
    for name, archive in archives.items():
        if archive["status"] != "published":
            require(allow_candidate, f"{name}: Zenodo archive is not published")
            print(f"{name}: Zenodo archive pending (release-candidate mode)")
            continue
        record = read_json(f"https://zenodo.org/api/records/{archive['record_id']}")
        require(record["doi"] == archive["version_doi"], f"{name}: Zenodo DOI differs")
        require(
            record["conceptdoi"] == archive["concept_doi"],
            f"{name}: Zenodo concept DOI differs",
        )
        require(
            record["status"] == "published", f"{name}: Zenodo record is not published"
        )
        files = {item["key"]: item for item in record["files"]}
        archive_file = files[archive["filename"]]
        require(
            remote_sha256(
                archive_file["links"].get("content", archive_file["links"]["self"])
            )
            == archive["sha256"],
            f"{name}: Zenodo archive hash differs",
        )
    print("Zenodo releases verified")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-candidate", action="store_true")
    parser.add_argument("--lock", type=Path, default=LOCK_PATH)
    args = parser.parse_args()
    lock = yaml.safe_load(args.lock.read_text(encoding="utf-8"))
    require(
        lock["lock_format"] in {"meddeid.suite-lock.v1", "meddeid.suite-lock.v2"},
        "unsupported lock format",
    )
    require(
        lock["status"] in {"release-candidate", "released"}, "invalid release status"
    )
    if lock["status"] != "released":
        require(args.allow_candidate, "suite lock is not released")
    verify_licensing_policy(lock)
    models = lock["models"] if "models" in lock else {"default": lock["model"]}
    for name, model in models.items():
        require(
            SHA256.fullmatch(model["weights_sha256"]) is not None,
            f"{name}: invalid model hash",
        )
    verify_python_components(lock)
    verify_git_components(lock)
    verify_hugging_face(lock)
    verify_triton_plans(lock)
    profiles = (
        lock["language_profiles"]
        if "language_profiles" in lock
        else {"nl": lock["language_profile"]}
    )
    if all(
        profile["javascript_status"] == "published" for profile in profiles.values()
    ):
        verify_npm(lock)
    else:
        require(args.allow_candidate, "npm profile is not published")
        print("npm language profile pending (release-candidate mode)")
    verify_archive(lock, allow_candidate=args.allow_candidate)
    print(f"valid MedDeID suite lock: {args.lock}")


if __name__ == "__main__":
    main()
