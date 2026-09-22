#!/usr/bin/env python3
"""Verify migrated sealed artifact files against SEALED_ARTIFACT_MANIFEST.json."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--sealed-root",
        type=Path,
        default=Path("evidence/sealed"),
        help="Root containing migrated sealed files.",
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Fail if any manifest-declared safe file is absent.",
    )
    args = parser.parse_args()

    root = args.repo_root.resolve()
    sealed = (root / args.sealed_root).resolve() if not args.sealed_root.is_absolute() else args.sealed_root
    manifest = json.loads((root / "SEALED_ARTIFACT_MANIFEST.json").read_text(encoding="utf-8"))

    checked = 0
    missing = []
    mismatches = []

    for artifact in manifest["artifacts"]:
        artifact_dir = sealed / artifact["name"]
        for relative, expected in artifact.get("safe_files", {}).items():
            path = artifact_dir / relative
            if not path.exists():
                missing.append(path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path))
                continue
            observed = sha256(path)
            checked += 1
            if observed != expected:
                mismatches.append({
                    "path": path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path),
                    "expected": expected,
                    "observed": observed,
                })

    status = "pass"
    if mismatches or (args.require_all and missing):
        status = "fail"

    report = {
        "status": status,
        "checked_files": checked,
        "missing_files": missing,
        "mismatches": mismatches,
        "require_all": args.require_all,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
