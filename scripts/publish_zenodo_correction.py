#!/usr/bin/env python3
"""Reserve and publish a verified corrected version of an existing Zenodo record."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


API_ROOT = "https://zenodo.org/api"
DEFAULT_TOKEN_PATH = Path.home() / ".config/zenodo/token"


def fail(message: str) -> None:
    raise RuntimeError(message)


def read_token(path: Path) -> str:
    token = os.environ.get("ZENODO_ACCESS_TOKEN", "").strip()
    if not token and path.is_file():
        token = path.read_text(encoding="utf-8").strip()
    if not token:
        fail(
            "Zenodo token unavailable; set ZENODO_ACCESS_TOKEN or write it to "
            f"{path}"
        )
    return token


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class Zenodo:
    def __init__(self, token: str) -> None:
        self.headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "meddeid-zenodo-correction/1",
        }

    def request(
        self,
        method: str,
        url: str,
        *,
        json_payload: dict[str, Any] | None = None,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        request_headers = dict(self.headers)
        request_headers.update(headers or {})
        if json_payload is not None:
            data = json.dumps(json_payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            url, data=data, headers=request_headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                body = response.read()
        except urllib.error.HTTPError as error:
            detail = error.read(1000).decode("utf-8", errors="replace")
            fail(
                f"Zenodo {method} {url} returned {error.code}: "
                f"{detail.replace(chr(10), ' ')}"
            )
        if not body:
            return None
        return json.loads(body)

    def deposition(self, record_id: int) -> dict[str, Any]:
        return self.request("GET", f"{API_ROOT}/deposit/depositions/{record_id}")

    def reserve_new_version(self, record_id: int) -> dict[str, Any]:
        current = self.deposition(record_id)
        draft_url = current.get("links", {}).get("latest_draft")
        if draft_url:
            draft = self.request("GET", draft_url)
            if not draft.get("submitted") and draft.get("state") != "done":
                return draft
        if current.get("submitted") or current.get("state") == "done":
            current = self.request(
                "POST", f"{API_ROOT}/deposit/depositions/{record_id}/actions/newversion"
            )
            draft_url = current.get("links", {}).get("latest_draft")
        if not draft_url:
            fail("Zenodo did not return a latest_draft URL")
        return self.request("GET", draft_url)


def doi_for(deposition: dict[str, Any]) -> str:
    metadata = deposition.get("metadata", {})
    reserved = metadata.get("prereserve_doi", {})
    doi = reserved.get("doi") or metadata.get("doi")
    if not isinstance(doi, str) or not doi.startswith("10.5281/zenodo."):
        fail("Zenodo draft has no valid reserved DOI")
    return doi


def concept_doi_for(deposition: dict[str, Any]) -> str:
    metadata = deposition.get("metadata", {})
    doi = metadata.get("conceptdoi")
    if not doi:
        concept_record_id = deposition.get("conceptrecid")
        if concept_record_id:
            doi = f"10.5281/zenodo.{concept_record_id}"
    if not isinstance(doi, str) or not doi.startswith("10.5281/zenodo."):
        fail("Zenodo draft has no valid concept DOI")
    return doi


def receipt(deposition: dict[str, Any], *, archive: Path | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "record_id": int(deposition["id"]),
        "version_doi": doi_for(deposition),
        "concept_doi": concept_doi_for(deposition),
        "record_url": deposition.get("links", {}).get("html"),
        "state": deposition.get("state"),
        "submitted": bool(deposition.get("submitted")),
    }
    if archive is not None:
        result.update(
            {
                "filename": archive.name,
                "bytes": archive.stat().st_size,
                "sha256": sha256_file(archive),
            }
        )
    return result


def load_metadata(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        fail(f"{path}: expected a top-level metadata object")
    if "doi" in metadata:
        fail(f"{path}: version DOI must be reserved by Zenodo, not supplied")
    # The legacy deposit endpoint currently rejects grant identifiers that it
    # returns itself. Keep the grant in the archived metadata and retain the
    # equivalent Sponsor contributor in the record metadata.
    if metadata.pop("grants", None):
        sponsors = {
            item.get("name")
            for item in metadata.get("contributors", [])
            if item.get("type") == "Sponsor"
        }
        if "Research Foundation Flanders (FWO)" not in sponsors:
            fail(f"{path}: grant omitted from API payload without Sponsor contributor")
    return metadata


def replace_files(
    client: Zenodo,
    draft: dict[str, Any],
    archive: Path,
    retained_names: set[str],
) -> dict[str, Any]:
    draft_id = int(draft["id"])
    files_url = f"{API_ROOT}/deposit/depositions/{draft_id}/files"
    inherited = client.request("GET", files_url)
    inherited_names = {str(item["filename"]) for item in inherited}
    missing_retained = retained_names - inherited_names
    if missing_retained:
        fail(f"requested inherited files are missing: {sorted(missing_retained)}")
    for item in inherited:
        if item["filename"] not in retained_names:
            client.request("DELETE", f"{files_url}/{item['id']}")

    bucket = draft.get("links", {}).get("bucket")
    if not isinstance(bucket, str):
        fail("Zenodo draft has no file bucket")
    with archive.open("rb") as handle:
        client.request(
            "PUT",
            f"{bucket}/{archive.name}",
            data=handle.read(),
            headers={"Content-Type": "application/octet-stream"},
        )

    refreshed = client.deposition(draft_id)
    files = refreshed.get("files", [])
    expected_names = retained_names | {archive.name}
    actual_names = {str(item.get("filename")) for item in files}
    if actual_names != expected_names:
        fail(
            "Zenodo draft files differ: "
            f"expected {sorted(expected_names)}, got {sorted(actual_names)}"
        )
    remote = next(item for item in files if item.get("filename") == archive.name)
    checksum = str(remote.get("checksum", "")).removeprefix("md5:")
    if checksum != md5_file(archive):
        fail("Zenodo archive MD5 differs after upload")
    if int(remote.get("filesize", -1)) != archive.stat().st_size:
        fail("Zenodo archive size differs after upload")
    return refreshed


def write_receipt(path: Path | None, payload: dict[str, Any]) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record-id", type=int, required=True)
    parser.add_argument("--expected-concept-doi", required=True)
    parser.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN_PATH)
    parser.add_argument("--receipt", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--reserve-only", action="store_true")
    mode.add_argument("--publish", action="store_true")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--expected-version-doi")
    parser.add_argument(
        "--retain-inherited-file",
        action="append",
        default=[],
        help="keep this exact file from the previous version (repeatable)",
    )
    args = parser.parse_args()

    client = Zenodo(read_token(args.token_file.expanduser()))
    draft = client.reserve_new_version(args.record_id)
    concept_doi = concept_doi_for(draft)
    if concept_doi != args.expected_concept_doi:
        fail(
            f"concept DOI differs: expected {args.expected_concept_doi}, got {concept_doi}"
        )

    if args.reserve_only:
        write_receipt(args.receipt, receipt(draft))
        return

    if args.archive is None or args.metadata is None or not args.expected_version_doi:
        parser.error(
            "--publish requires --archive, --metadata, and --expected-version-doi"
        )
    archive = args.archive.expanduser().resolve()
    metadata_path = args.metadata.expanduser().resolve()
    if not archive.is_file() or archive.suffix.lower() != ".zip":
        fail(f"archive is missing or is not a ZIP: {archive}")
    if doi_for(draft) != args.expected_version_doi:
        fail(
            f"reserved DOI differs: expected {args.expected_version_doi}, "
            f"got {doi_for(draft)}"
        )

    metadata = load_metadata(metadata_path)
    draft_id = int(draft["id"])
    draft = client.request(
        "PUT",
        f"{API_ROOT}/deposit/depositions/{draft_id}",
        json_payload={"metadata": metadata},
    )
    draft = replace_files(client, draft, archive, set(args.retain_inherited_file))
    before = receipt(draft, archive=archive)
    published = client.request(
        "POST", f"{API_ROOT}/deposit/depositions/{draft_id}/actions/publish"
    )
    after = receipt(published, archive=archive)
    if not after["submitted"] or after["version_doi"] != args.expected_version_doi:
        fail("Zenodo did not publish the expected reserved version")
    write_receipt(args.receipt, {"before_publish": before, "published": after})


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, urllib.error.URLError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
