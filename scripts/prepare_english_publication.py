#!/usr/bin/env python3
"""Build reviewable Hugging Face and Zenodo artifacts for the English release."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any


SUITE = Path(__file__).resolve().parents[1]
ROOT = SUITE / "publication-english"
DATA_ROOT = SUITE / "repos/meddeid-data/data/english-production-v2/final"
SUBANNOTATION_ROOT = SUITE / "workspaces/english-synthetic-subannotations"
MODEL_RUN = (
    SUITE
    / "repos/meddeid-training/runs/english-gb-us-roberta-base-data-v2-final-20260826"
)
MODEL_EXPORT = MODEL_RUN / "export/meddeid-english-synth"
GUIDELINE = SUITE / "publication/guidelines/annotation-guidelines-en.pdf"
CC_LICENSE = SUITE / "publication/templates/huggingface/data-license/LICENSE"
AGPL_LICENSE = SUITE / "AGPL-3.0-only.txt"

EXPECTED = {
    "development_sha256": "ea77758db5f91dc992a23fc756e0d30958ba75750845fa78ec874bf96404fe45",
    "benchmark_sha256": "ac036c069a073886327c5847b9316cf116fe7d94dec21e242ccebff0beee1b25",
    "development_documents": 6700,
    "benchmark_documents": 300,
    "primary_spans": 1717,
    "subannotations": 7358,
    "model_weights_sha256": "545ebc71a235d471ba7f2fefca341704fe6aed33df4fb5b46ab9adef3e139bcc",
    "base_encoder_revision": "e2da8e2f811d1448a5b465c236feacd80ffbac7b",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_rows(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                yield line_number, json.loads(line)


def verify_document(path: Path, line_number: int, row: Any, *, nested: bool) -> tuple[str, str, int]:
    if not isinstance(row, dict):
        raise ValueError(f"{path}:{line_number}: row is not an object")
    document_id, text, spans = row.get("document_id"), row.get("text"), row.get("spans")
    if not isinstance(document_id, str) or not document_id:
        raise ValueError(f"{path}:{line_number}: missing document_id")
    if not isinstance(text, str) or not isinstance(spans, list):
        raise ValueError(f"{path}:{line_number}: invalid text/spans contract")
    language = (row.get("metadata") or {}).get("lang")
    if language not in {"en-GB", "en-US"}:
        raise ValueError(f"{path}:{line_number}: unsupported metadata.lang {language!r}")
    segment_count = 0
    for span_index, span in enumerate(spans):
        if not isinstance(span, dict):
            raise ValueError(f"{path}:{line_number}: spans[{span_index}] is not an object")
        begin, end = span.get("begin"), span.get("end")
        if not isinstance(begin, int) or not isinstance(end, int) or not 0 <= begin < end <= len(text):
            raise ValueError(f"{path}:{line_number}: spans[{span_index}] has invalid offsets")
        if span.get("text") != text[begin:end] or not isinstance(span.get("label"), str):
            raise ValueError(f"{path}:{line_number}: spans[{span_index}] text/label mismatch")
        segments = span.get("subannotations")
        if nested:
            if not isinstance(segments, list) or not segments:
                raise ValueError(f"{path}:{line_number}: spans[{span_index}] lacks subannotations")
            cursor = begin
            for segment_index, segment in enumerate(segments):
                sub_begin, sub_end = segment.get("begin"), segment.get("end")
                if sub_begin != cursor or not isinstance(sub_end, int) or not sub_begin < sub_end <= end:
                    raise ValueError(
                        f"{path}:{line_number}: spans[{span_index}].subannotations[{segment_index}] "
                        "does not form a contiguous partition"
                    )
                if segment.get("text") != text[sub_begin:sub_end] or not segment.get("category"):
                    raise ValueError(
                        f"{path}:{line_number}: spans[{span_index}].subannotations[{segment_index}] mismatch"
                    )
                cursor = sub_end
                segment_count += 1
            if cursor != end:
                raise ValueError(f"{path}:{line_number}: spans[{span_index}] partition is incomplete")
        elif segments is not None:
            raise ValueError(f"{path}:{line_number}: source primary span unexpectedly has subannotations")
    return document_id, language, segment_count


def verify_inputs() -> dict[str, Any]:
    development = DATA_ROOT / "development.jsonl"
    benchmark = DATA_ROOT / "benchmark.jsonl"
    enriched = SUBANNOTATION_ROOT / "evaluation-bundle/benchmark.jsonl"
    sub_manifest = SUBANNOTATION_ROOT / "evaluation-bundle/manifest.json"
    release = json.loads((DATA_ROOT / "benchmark-release.json").read_text(encoding="utf-8"))
    source_manifest = json.loads((DATA_ROOT / "manifest.json").read_text(encoding="utf-8"))
    bundle_manifest = json.loads(sub_manifest.read_text(encoding="utf-8"))

    if sha256_file(development) != EXPECTED["development_sha256"]:
        raise ValueError("development.jsonl differs from the frozen English final manifest")
    if sha256_file(benchmark) != EXPECTED["benchmark_sha256"]:
        raise ValueError("benchmark.jsonl differs from the human-validation release")
    if source_manifest.get("total_documents") != 7000 or release.get("status") != "human_validated":
        raise ValueError("English source release is not in the expected human-validated state")
    if bundle_manifest.get("hashes", {}).get("source_annotations_sha256") != EXPECTED["benchmark_sha256"]:
        raise ValueError("subannotation bundle is not pinned to the final benchmark")
    if bundle_manifest.get("counts") != {
        "documents": 300,
        "primary_gold_spans": 1717,
        "core_pii_subannotations": 7358,
    }:
        raise ValueError("subannotation bundle counts differ from the release contract")

    datasets: dict[str, dict[str, Any]] = {}
    ids_by_name: dict[str, set[str]] = {}
    for name, path, nested in (
        ("development", development, False),
        ("benchmark_primary", benchmark, False),
        ("benchmark", enriched, True),
    ):
        ids: set[str] = set()
        profiles: Counter[str] = Counter()
        spans = segments = 0
        for line_number, row in json_rows(path):
            document_id, profile, row_segments = verify_document(path, line_number, row, nested=nested)
            if document_id in ids:
                raise ValueError(f"{path}:{line_number}: duplicate document_id {document_id!r}")
            ids.add(document_id)
            profiles[profile] += 1
            spans += len(row["spans"])
            segments += row_segments
        ids_by_name[name] = ids
        datasets[name] = {
            "path": path,
            "documents": len(ids),
            "primary_spans": spans,
            "subannotations": segments,
            "profiles": dict(sorted(profiles.items())),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }

    if len(ids_by_name["development"]) != EXPECTED["development_documents"]:
        raise ValueError("unexpected English development document count")
    if len(ids_by_name["benchmark"]) != EXPECTED["benchmark_documents"]:
        raise ValueError("unexpected English benchmark document count")
    if ids_by_name["benchmark"] != ids_by_name["benchmark_primary"]:
        raise ValueError("enriched benchmark document IDs differ from the primary release")
    overlap = ids_by_name["development"] & ids_by_name["benchmark"]
    if overlap:
        raise ValueError(f"development/benchmark overlap: {sorted(overlap)[:5]}")
    if datasets["benchmark"]["primary_spans"] != EXPECTED["primary_spans"]:
        raise ValueError("unexpected English benchmark primary span count")
    if datasets["benchmark"]["subannotations"] != EXPECTED["subannotations"]:
        raise ValueError("unexpected English benchmark subannotation count")

    weights = MODEL_EXPORT / "model.safetensors"
    bundle = json.loads((MODEL_EXPORT / "bundle.json").read_text(encoding="utf-8"))
    metrics = json.loads((MODEL_RUN / "refit/train_metrics.json").read_text(encoding="utf-8"))
    if sha256_file(weights) != EXPECTED["model_weights_sha256"]:
        raise ValueError("English model weights differ from the final export")
    if bundle.get("base_encoder_revision") != EXPECTED["base_encoder_revision"]:
        raise ValueError("English model base encoder revision differs from the pinned revision")
    final_test = metrics.get("final_test") or {}
    if final_test.get("entity_spans_true") != EXPECTED["primary_spans"]:
        raise ValueError("final model evaluation is not tied to the 1,717-span benchmark")

    return {
        "datasets": datasets,
        "subannotation_manifest": {
            "path": sub_manifest,
            "bytes": sub_manifest.stat().st_size,
            "sha256": sha256_file(sub_manifest),
        },
        "confirmed_subannotations": {
            "path": SUBANNOTATION_ROOT / "subannotations.jsonl",
            "bytes": (SUBANNOTATION_ROOT / "subannotations.jsonl").stat().st_size,
            "sha256": sha256_file(SUBANNOTATION_ROOT / "subannotations.jsonl"),
        },
        "model": {
            "weights_sha256": sha256_file(weights),
            "source_bundle_sha256": sha256_file(MODEL_EXPORT / "bundle.json"),
            "checkpoint_sha256": sha256_file(MODEL_RUN / "refit/checkpoints/best.pt"),
            "train_metrics_sha256": sha256_file(MODEL_RUN / "refit/train_metrics.json"),
            "eval_sha256": sha256_file(MODEL_RUN / "refit/eval.json"),
            "final_test": {
                key: final_test[key]
                for key in ("entity_precision", "entity_recall", "entity_f1", "span_edit_total_ops")
            },
            "exact_span_test": final_test["evaluation_slices"]["overall"],
        },
    }


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def write_viewer(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open(encoding="utf-8") as src, destination.open("w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            row = json.loads(line)
            metadata = row.pop("metadata", None)
            row["metadata_json"] = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
            dst.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def portable_json(value: Any) -> Any:
    """Remove machine-specific absolute path prefixes from public metadata."""
    if isinstance(value, dict):
        return {key: portable_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [portable_json(item) for item in value]
    if isinstance(value, str) and value.startswith(str(SUITE)):
        return "${MEDDEID_SUITE}/" + Path(value).relative_to(SUITE).as_posix()
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def checksum_lines(root: Path) -> list[str]:
    return [
        f"{sha256_file(path)}  {path.relative_to(root).as_posix()}"
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "CHECKSUMS.sha256"
    ]


def write_checksums(root: Path) -> None:
    (root / "CHECKSUMS.sha256").write_text("\n".join(checksum_lines(root)) + "\n", encoding="utf-8")


def build_dataset_repo(target: Path, *, source: Path, template: str, split: str, provenance: dict[str, Path]) -> None:
    target.mkdir(parents=True)
    copy_file(ROOT / f"templates/huggingface/{template}.md", target / "README.md")
    copy_file(CC_LICENSE, target / "LICENSE")
    copy_file(source, target / f"source/{source.name}")
    write_viewer(source, target / f"data/{split}.jsonl")
    copy_file(GUIDELINE, target / "guidelines/annotation-guidelines-en.pdf")
    for name, path in provenance.items():
        copy_file(path, target / f"provenance/{name}")
    write_checksums(target)


def build_model_repo(target: Path, verified: dict[str, Any]) -> None:
    target.mkdir(parents=True)
    for path in MODEL_EXPORT.iterdir():
        if path.is_file() and path.name != "bundle.json":
            copy_file(path, target / path.name)
    bundle = portable_json(json.loads((MODEL_EXPORT / "bundle.json").read_text(encoding="utf-8")))
    metrics = portable_json(json.loads((MODEL_RUN / "refit/train_metrics.json").read_text(encoding="utf-8")))
    evaluation = portable_json(json.loads((MODEL_RUN / "refit/eval.json").read_text(encoding="utf-8")))
    write_json(target / "bundle.json", bundle)
    write_json(target / "train_metrics.json", metrics)
    write_json(target / "eval.json", evaluation)
    copy_file(ROOT / "templates/huggingface/model.md", target / "README.md")
    copy_file(ROOT / "templates/huggingface/MODEL_NOTICE", target / "NOTICE")
    copy_file(AGPL_LICENSE, target / "LICENSE")
    write_json(
        target / "MODEL_PROVENANCE.json",
        {
            "format": "meddeid.model-publication.v1",
            "repository": "stighellemans/meddeid-english-synth",
            "base_encoder": "FacebookAI/roberta-base",
            "base_encoder_revision": EXPECTED["base_encoder_revision"],
            "source_checkpoint_sha256": verified["model"]["checkpoint_sha256"],
            "source_bundle_sha256": verified["model"]["source_bundle_sha256"],
            "published_bundle_sha256": sha256_file(target / "bundle.json"),
            "weights_sha256": verified["model"]["weights_sha256"],
            "train_metrics_source_sha256": verified["model"]["train_metrics_sha256"],
            "eval_source_sha256": verified["model"]["eval_sha256"],
            "metadata_operation": "replace local absolute workspace prefixes with ${MEDDEID_SUITE}",
        },
    )
    write_checksums(target)


def deterministic_zip(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(path.relative_to(source.parent).as_posix(), (2026, 8, 27, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)


def build_zenodo(target: Path, verified: dict[str, Any]) -> Path:
    target.mkdir(parents=True)
    copy_file(DATA_ROOT / "development.jsonl", target / "data/meddeid-english-synthetic-corpus.jsonl")
    copy_file(
        SUBANNOTATION_ROOT / "evaluation-bundle/benchmark.jsonl",
        target / "data/meddeid-english-synthetic-benchmark.jsonl",
    )
    copy_file(DATA_ROOT / "benchmark.jsonl", target / "provenance/benchmark-primary-spans.jsonl")
    copy_file(SUBANNOTATION_ROOT / "subannotations.jsonl", target / "provenance/confirmed-subannotations.jsonl")
    copy_file(
        SUBANNOTATION_ROOT / "evaluation-bundle/manifest.json",
        target / "provenance/subannotation-bundle-manifest.json",
    )
    copy_file(GUIDELINE, target / "guidelines/annotation-guidelines-en.pdf")
    copy_file(CC_LICENSE, target / "LICENSE")
    copy_file(ROOT / "templates/zenodo/README.md", target / "README.md")
    copy_file(ROOT / "templates/zenodo/metadata.json", target / "metadata.json")
    write_json(target / "release-manifest.json", release_manifest(verified, include_local_paths=False))
    write_checksums(target)
    archive = target.parent / "meddeid-english-synthetic-data-v2.zip"
    deterministic_zip(target, archive)
    return archive


def release_manifest(verified: dict[str, Any], *, include_local_paths: bool) -> dict[str, Any]:
    def dataset_entry(name: str, repo: str, split: str) -> dict[str, Any]:
        item = verified["datasets"][name]
        result = {
            key: value for key, value in item.items() if key != "path"
        }
        if include_local_paths:
            result["source_path"] = str(item["path"].relative_to(SUITE))
        result["hugging_face"] = {"repository": repo, "split": split}
        return result

    return {
        "manifest_version": "meddeid.english-publication.v1",
        "status": "published",
        "prepared_date": "2026-08-27",
        "published_date": "2026-08-27",
        "owner": "stighellemans",
        "publication": {
            "zenodo": {
                "record": "https://zenodo.org/records/22129255",
                "version_doi": "10.5281/zenodo.22129255",
                "concept_doi": "10.5281/zenodo.22127863",
            },
            "hugging_face_revisions": {
                "stighellemans/meddeid-english-synthetic-corpus": "b93f735c88cda2ed77725c6a4f53e8124503073a",
                "stighellemans/meddeid-english-synthetic-benchmark": "36879b454408a86548cdcb6f82657a9434fa2b80",
                "stighellemans/meddeid-english-synth": "3e5139a749bd2e4f490a76571338108dbe6b1498",
                "spaces/stighellemans/meddeid-demo": "830fc3d3ffb97140dd7c5b633a7d4b210f55ac2b",
            },
        },
        "collection": {
            "slug": "stighellemans/meddeid-6a7ae47783f48f05c85170d0",
            "include": [
                "stighellemans/meddeid-english-synthetic-corpus",
                "stighellemans/meddeid-english-synthetic-benchmark",
                "stighellemans/meddeid-english-synth",
            ],
            "exclude": [],
            "policy": "include the English synthetic corpus, benchmark, and model",
        },
        "datasets": {
            "development": dataset_entry(
                "development", "stighellemans/meddeid-english-synthetic-corpus", "train"
            ),
            "benchmark": dataset_entry(
                "benchmark", "stighellemans/meddeid-english-synthetic-benchmark", "test"
            ),
            "benchmark_primary": {
                key: value
                for key, value in verified["datasets"]["benchmark_primary"].items()
                if key != "path"
            },
        },
        "subannotation_provenance": {
            key: ({k: v for k, v in value.items() if k != "path"})
            for key, value in (
                ("bundle_manifest", verified["subannotation_manifest"]),
                ("confirmed_subannotations", verified["confirmed_subannotations"]),
            )
        },
        "model": {
            "repository": "stighellemans/meddeid-english-synth",
            "base_encoder": "FacebookAI/roberta-base",
            "base_encoder_revision": EXPECTED["base_encoder_revision"],
            **verified["model"],
        },
        "licenses": {"datasets_and_guideline": "CC-BY-4.0", "model": "AGPL-3.0-only"},
        "release_blockers": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="verify inputs and refresh release-manifest.json without rebuilding artifacts",
    )
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if not args.manifest_only and output.exists() and any(output.iterdir()):
        parser.error(f"output directory must be empty: {output}")

    verified = verify_inputs()
    write_json(ROOT / "release-manifest.json", release_manifest(verified, include_local_paths=True))
    if args.manifest_only:
        build_path = output / "BUILD.json"
        if build_path.is_file():
            build = json.loads(build_path.read_text(encoding="utf-8"))
            build["status"] = "published"
            build["manifest_sha256"] = sha256_file(ROOT / "release-manifest.json")
            write_json(build_path, build)
        print("English publication manifest refreshed; source inputs verified")
        return

    output.mkdir(parents=True, exist_ok=True)
    hf_root = output / "huggingface"
    build_dataset_repo(
        hf_root / "meddeid-english-synthetic-corpus",
        source=DATA_ROOT / "development.jsonl",
        template="corpus",
        split="train",
        provenance={"source-manifest.json": DATA_ROOT / "manifest.json"},
    )
    build_dataset_repo(
        hf_root / "meddeid-english-synthetic-benchmark",
        source=SUBANNOTATION_ROOT / "evaluation-bundle/benchmark.jsonl",
        template="benchmark",
        split="test",
        provenance={
            "benchmark-primary-spans.jsonl": DATA_ROOT / "benchmark.jsonl",
            "benchmark-release.json": DATA_ROOT / "benchmark-release.json",
            "confirmed-subannotations.jsonl": SUBANNOTATION_ROOT / "subannotations.jsonl",
            "subannotation-bundle-manifest.json": SUBANNOTATION_ROOT / "evaluation-bundle/manifest.json",
        },
    )
    build_model_repo(hf_root / "meddeid-english-synth", verified)
    archive = build_zenodo(output / "zenodo/meddeid-english-synthetic-data-v2", verified)
    write_json(
        output / "BUILD.json",
        {
            "status": "published",
            "manifest_sha256": sha256_file(ROOT / "release-manifest.json"),
            "zenodo_archive": archive.relative_to(output).as_posix(),
            "zenodo_archive_sha256": sha256_file(archive),
        },
    )
    print(
        "English publication prepared: "
        f"development={EXPECTED['development_documents']}, "
        f"benchmark={EXPECTED['benchmark_documents']}, "
        f"primary_spans={EXPECTED['primary_spans']}, "
        f"subannotations={EXPECTED['subannotations']}"
    )
    print(f"output: {output}")
    print("draft only: no Hugging Face repository or Zenodo record was changed")


if __name__ == "__main__":
    main()
