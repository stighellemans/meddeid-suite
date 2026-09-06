#!/usr/bin/env python3
"""Print exact clean-install requirements for the active public suite lock."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--lock", type=Path, default=ROOT / "suite-lock.yaml")
args = parser.parse_args()
lock = yaml.safe_load(args.lock.read_text(encoding="utf-8"))
components = lock["components"]

if lock["lock_format"] == "meddeid.suite-lock.v1":
    requirements = [
        f"meddeid[server]=={components['meddeid']['version']}",
        f"meddeid-data=={components['meddeid-data']['version']}",
        f"meddeid-eval=={components['meddeid-eval']['version']}",
        f"meddeid-training[train]=={components['meddeid-training']['version']}",
    ]
elif lock["lock_format"] == "meddeid.suite-lock.v2":
    requirements = [f"meddeid[research]=={components['meddeid']['version']}"]
    requirements.extend(
        f"{name}=={component['version']}"
        for name, component in components.items()
        if name != "meddeid" and component.get("ecosystem") == "python"
    )
else:
    raise SystemExit(f"unsupported lock format: {lock['lock_format']}")

runtime = lock["runtime"]
requirements.extend(
    [
        f"torch=={runtime['torch']}",
        f"transformers=={runtime['transformers']}",
        f"numpy=={runtime['numpy']}",
        f"scikit-learn=={runtime['scikit_learn']}",
    ]
)
print("\n".join(requirements))
