#!/usr/bin/env python3
"""Prepare a documentation-only model release without changing model payloads."""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCEPTION = ROOT / "MEDDEID-PRIVATE-FINE-TUNING-EXCEPTION-1.0.txt"
MUTABLE = {
    "README.md",
    "NOTICE",
    "CHECKSUMS.sha256",
    "MEDDEID-PRIVATE-FINE-TUNING-EXCEPTION-1.0.txt",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file() and ".cache" not in path.relative_to(root).parts
    }


def write_checksums(root: Path) -> None:
    paths = files(root)
    included = {
        name: path
        for name, path in paths.items()
        if name not in {".gitattributes", "CHECKSUMS.sha256"}
    }
    lines = [f"{sha256_file(path)}  {name}" for name, path in sorted(included.items())]
    (root / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--readme", type=Path, required=True)
    parser.add_argument("--notice", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-weights-sha256", required=True)
    parser.add_argument("--expected-bundle-sha256", required=True)
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not source.is_dir():
        parser.error(f"source snapshot is missing: {source}")
    if output.exists():
        parser.error(f"output already exists: {output}")
    for required in (args.readme, args.notice, EXCEPTION):
        if not required.is_file():
            parser.error(f"required file is missing: {required}")

    shutil.copytree(source, output, ignore=shutil.ignore_patterns(".cache"))
    shutil.copy2(args.readme, output / "README.md")
    shutil.copy2(args.notice, output / "NOTICE")
    shutil.copy2(EXCEPTION, output / EXCEPTION.name)
    write_checksums(output)

    if sha256_file(output / "model.safetensors") != args.expected_weights_sha256:
        raise RuntimeError("model weights differ from the locked public release")
    if sha256_file(output / "bundle.json") != args.expected_bundle_sha256:
        raise RuntimeError("model bundle differs from the locked public release")

    source_files = files(source)
    output_files = files(output)
    for name, path in source_files.items():
        if name in MUTABLE:
            continue
        if name not in output_files or sha256_file(path) != sha256_file(output_files[name]):
            raise RuntimeError(f"immutable model payload differs: {name}")
    unexpected = set(output_files) - set(source_files) - {EXCEPTION.name}
    if unexpected:
        raise RuntimeError(f"unexpected files in corrected model: {sorted(unexpected)}")

    print(f"prepared documentation-only model correction: {output}")
    print(f"weights sha256: {args.expected_weights_sha256}")
    print(f"bundle sha256: {args.expected_bundle_sha256}")


if __name__ == "__main__":
    main()
