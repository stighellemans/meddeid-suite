#!/usr/bin/env python3
"""Validate the checked pilot, optionally running its complete training slice."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


SUITE = Path(__file__).resolve().parents[1]
PILOT = SUITE / "pilots" / "new-researcher-v1"
REPOS = SUITE / "repos"
MODEL_REVISION = "55c7858e91a53686bfd359d2653c8c6b8dabde89"


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def validate_checked_fixture() -> None:
    sys.path.insert(0, str(REPOS / "meddeid-core" / "src"))
    sys.path.insert(0, str(REPOS / "meddeid-eval" / "src"))
    from meddeid_core import validate_record
    from meddeid_eval.metrics import score_documents

    source = read_jsonl(PILOT / "01-source" / "annotations.jsonl")
    plain_texts = sorted(
        path.read_text(encoding="utf-8").rstrip("\n")
        for path in (PILOT / "00-plain-text").glob("*.txt")
    )
    require(len(plain_texts) == 6, "plain-text import fixture must contain six notes")
    require(
        plain_texts == sorted(row["text"] for row in source),
        "plain-text and canonical source fixtures differ",
    )

    canonical_paths = [
        PILOT / "01-source" / "annotations.jsonl",
        PILOT / "02-primary" / "annotator-a.jsonl",
        PILOT / "02-primary" / "annotator-b.jsonl",
        PILOT / "03-adjudication" / "annotations.jsonl",
        PILOT
        / "04-subannotation"
        / "evaluation-bundle"
        / "meddeid-dutch-synthetic-benchmark.jsonl",
        PILOT / "05-evaluation" / "degraded-predictions.jsonl",
    ]
    for path in canonical_paths:
        for line_number, record in enumerate(read_jsonl(path), 1):
            problems = validate_record(record)
            require(not problems, f"{path}:{line_number}: {problems}")

    adjudication_dir = PILOT / "03-adjudication"
    gold = read_jsonl(adjudication_dir / "annotations.jsonl")
    decisions = read_jsonl(adjudication_dir / "decisions.jsonl")
    manifest = json.loads((adjudication_dir / "manifest.json").read_text(encoding="utf-8"))
    pending = [
        item
        for row in gold
        for item in row.get("adjudication", {}).get("disagreements", [])
        if item.get("status") == "pending"
    ]
    unconfirmed = [span for row in gold for span in row["spans"] if not span.get("confirmed")]
    require(len(gold) == 6, "adjudication output must contain six documents")
    require(sum(len(row["spans"]) for row in gold) == 22, "expected 22 primary spans")
    require(not pending, "published adjudication output contains pending disagreements")
    require(not unconfirmed, "published adjudication output contains unconfirmed spans")
    require(
        all(row.get("completed") is True for row in gold),
        "every published document must have whole-text confirmation",
    )
    require(
        sum(item.get("disagreement_id") is not None for item in decisions) == 7,
        "expected seven persisted disagreement decisions",
    )
    require(
        sum(item.get("action") == "confirm_document" for item in decisions) == 6,
        "expected six persisted whole-document confirmations",
    )
    require(manifest["counts"]["resolved_disagreements"] == 7, "manifest decision count differs")
    require(
        manifest["hashes"]["annotations_sha256"]
        == sha256(adjudication_dir / "annotations.jsonl"),
        "adjudication annotation hash differs from its manifest",
    )
    require(
        manifest["hashes"]["decisions_sha256"]
        == sha256(adjudication_dir / "decisions.jsonl"),
        "adjudication decision hash differs from its manifest",
    )

    bundle_dir = PILOT / "04-subannotation" / "evaluation-bundle"
    benchmark_path = bundle_dir / "meddeid-dutch-synthetic-benchmark.jsonl"
    bundle_manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    counts = bundle_manifest["counts"]
    require(
        counts == {
            "documents": 6,
            "primary_gold_spans": 22,
            "core_pii_subannotations": 92,
        },
        f"unexpected subannotation bundle counts: {counts}",
    )
    require(
        bundle_manifest["hashes"]["source_annotations_sha256"]
        == sha256(adjudication_dir / "annotations.jsonl"),
        "subannotation bundle is not pinned to the current primary gold",
    )
    require(
        bundle_manifest["hashes"]["benchmark_sha256"] == sha256(benchmark_path),
        "benchmark hash differs from its manifest",
    )

    benchmark = read_jsonl(benchmark_path)
    degraded = read_jsonl(PILOT / "05-evaluation" / "degraded-predictions.jsonl")
    oracle_metrics = score_documents(benchmark, benchmark)
    degraded_metrics = score_documents(benchmark, degraded)
    require(oracle_metrics["exact_f1"] == 1.0, "oracle evaluation must have exact F1 1.0")
    require(
        degraded_metrics["exact_f1"] == 0.65,
        f"degraded exact F1 changed: {degraded_metrics['exact_f1']}",
    )

    pilot_config = yaml.safe_load((PILOT / "06-training" / "pilot.yaml").read_text())
    public_lock = SUITE / "suite-lock.yaml"
    if public_lock.exists():
        release_model = yaml.safe_load(public_lock.read_text(encoding="utf-8"))["model"]
        release_model_revision = release_model["revision"]
        release_model_public = True
    else:
        release = json.loads(
            (SUITE / "publication" / "HUGGING_FACE_PRIVATE_STAGING.json").read_text()
        )
        release_model_revision = release["repositories"]["model"]["revision"]
        release_model_public = release["repositories"]["model"]["visibility"] == "public"
    require(pilot_config["model_revision"] == MODEL_REVISION, "pilot model revision is stale")
    require(
        release_model_revision == MODEL_REVISION,
        "release metadata model revision is stale",
    )
    require(
        release_model_public,
        "release metadata does not mark the model public",
    )
    print(
        "checked pilot passed: 6 documents, 7/7 decisions resolved, "
        "22 confirmed primary spans, 92 reviewed subannotations"
    )


def run(command: list[str], *, env: dict[str, str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=SUITE, env=env, check=True)


def run_full_vertical_slice() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        str(REPOS / name / "src")
        for name in (
            "meddeid-core",
            "meddeid-language-nl",
            "meddeid-data",
            "meddeid-eval",
            "meddeid",
            "meddeid-training",
        )
    )
    env["TOKENIZERS_PARALLELISM"] = "false"
    env["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    env["HF_TOKEN"] = ""
    python = sys.executable
    training_entry = "from meddeid_training.cli import main; raise SystemExit(main())"
    data_entry = "from meddeid_data.cli import main; raise SystemExit(main())"
    inference_entry = "from meddeid.cli import main; raise SystemExit(main())"
    evaluation_entry = "from meddeid_eval.cli import main; raise SystemExit(main())"

    with tempfile.TemporaryDirectory(prefix="meddeid-new-researcher-") as temporary:
        output = Path(temporary)
        selection_run = output / "run-selection"
        selection = output / "selection.json"
        refit_run = output / "run-refit"
        exported_model = output / "exported-model"
        predictions = output / "predictions.jsonl"
        metrics = output / "metrics.json"
        config = PILOT / "06-training" / "pilot.yaml"

        project = output / "project"
        initial_assignment = project / "assignments" / "primary.jsonl"
        run(
            [
                python,
                "-c",
                data_entry,
                "project",
                "create",
                str(project),
                str(PILOT / "00-plain-text"),
                "--namespace",
                "new-researcher-pilot",
                "--language-profile",
                "nl-BE",
            ],
            env=env,
        )
        run(
            [
                python,
                "-c",
                inference_entry,
                "batch",
                str(project / "artifacts" / "annotations.jsonl"),
                "--output",
                str(initial_assignment),
                "--model",
                "stighellemans/meddeid-dutch-synth",
                "--revision",
                MODEL_REVISION,
                "--device",
                "cpu",
                "--quiet",
            ],
            env=env,
        )

        run(
            [
                python,
                "-c",
                training_entry,
                "select-epochs",
                "--config",
                str(config),
                "--data",
                str(PILOT / "06-training" / "prepared-selection"),
                "--run",
                str(selection_run),
                "--selection-output",
                str(selection),
            ],
            env=env,
        )
        run(
            [
                python,
                "-c",
                training_entry,
                "refit",
                "--config",
                str(config),
                "--data",
                str(PILOT / "06-training" / "prepared-refit"),
                "--run",
                str(refit_run),
                "--selection",
                str(selection),
            ],
            env=env,
        )
        run(
            [
                python,
                "-c",
                training_entry,
                "export",
                "--checkpoint",
                str(refit_run / "checkpoints" / "best.pt"),
                "--output",
                str(exported_model),
            ],
            env=env,
        )
        run(
            [
                python,
                "-c",
                inference_entry,
                "batch",
                str(PILOT / "01-source" / "annotations.jsonl"),
                "--output",
                str(predictions),
                "--model",
                str(exported_model),
                "--device",
                "cpu",
                "--quiet",
            ],
            env=env,
        )
        run(
            [
                python,
                "-c",
                evaluation_entry,
                "score",
                "--gold",
                str(
                    PILOT
                    / "04-subannotation"
                    / "evaluation-bundle"
                    / "meddeid-dutch-synthetic-benchmark.jsonl"
                ),
                "--predictions",
                str(predictions),
                "--output",
                str(metrics),
            ],
            env=env,
        )
        selection_payload = json.loads(selection.read_text(encoding="utf-8"))
        import_rows = read_jsonl(project / "artifacts" / "annotations.jsonl")
        initial_manifest = json.loads(
            initial_assignment.with_suffix(".jsonl.manifest.json").read_text(
                encoding="utf-8"
            )
        )
        batch_manifest = json.loads(
            predictions.with_suffix(".jsonl.manifest.json").read_text(encoding="utf-8")
        )
        metric_payload = json.loads(metrics.read_text(encoding="utf-8"))
        public_lock = SUITE / "suite-lock.yaml"
        if public_lock.exists():
            smoke = yaml.safe_load(public_lock.read_text(encoding="utf-8"))["smoke"]
            expected = float(smoke["exact_f1"]["target"])
            tolerance = float(smoke["exact_f1"]["tolerance"])
            require(
                abs(float(metric_payload["exact_f1"]) - expected) <= tolerance,
                "vertical-slice exact F1 is outside the locked tolerance: "
                f"expected {expected} +/- {tolerance}, found {metric_payload['exact_f1']}",
            )
        require(selection_payload["selected_epochs"] == 1, "pilot must select one epoch")
        require(len(import_rows) == 6, "project import did not create six canonical notes")
        require(
            initial_manifest["counts"]["processed"] == 6,
            "public-model initialization did not process six imported notes",
        )
        require(batch_manifest["counts"]["processed"] == 6, "batch did not process six notes")
        require(
            batch_manifest["counts"]["spans"] == 22,
            f"batch predicted {batch_manifest['counts']['spans']} spans instead of 22",
        )
        require(metric_payload["documents"] == 6, "evaluation did not score six notes")
        print(
            "full vertical slice passed: selection -> refit -> export -> "
            f"batch -> evaluation (exact_f1={metric_payload['exact_f1']:.6f})"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full",
        action="store_true",
        help="also run selection, refit, export, batch inference, and evaluation",
    )
    args = parser.parse_args()
    validate_checked_fixture()
    if args.full:
        run_full_vertical_slice()


if __name__ == "__main__":
    main()
