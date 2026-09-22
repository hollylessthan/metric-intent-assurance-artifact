#!/usr/bin/env python3
"""Verify migrated sealed artifact files against their frozen SHA-256 bindings."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def verify_curated_bundle(repo_root: Path, sealed_root: Path, outer_manifest: dict) -> dict:
    bundle_root = sealed_root / "mia-public-sealed-evidence"
    bundle_manifest_path = bundle_root / "BUNDLE_MANIFEST.json"
    expected_bundle = outer_manifest["curated_public_bundle"]

    mismatches = []
    missing = []

    expected_manifest_sha = expected_bundle.get("bundle_manifest_sha256")
    if expected_manifest_sha and sha256(bundle_manifest_path) != expected_manifest_sha:
        mismatches.append({
            "path": rel(bundle_manifest_path, repo_root),
            "expected": expected_manifest_sha,
            "observed": sha256(bundle_manifest_path),
        })

    bundle_manifest = json.loads(bundle_manifest_path.read_text(encoding="utf-8"))
    files = bundle_manifest.get("files", [])
    if bundle_manifest.get("file_count") != len(files):
        mismatches.append({
            "path": rel(bundle_manifest_path, repo_root),
            "expected": f"file_count={bundle_manifest.get('file_count')}",
            "observed": f"listed_files={len(files)}",
        })

    checked = 0
    for item in files:
        path = bundle_root / item["path"]
        if not path.exists():
            missing.append(rel(path, repo_root))
            continue
        observed = sha256(path)
        checked += 1
        if observed != item["sha256"]:
            mismatches.append({
                "path": rel(path, repo_root),
                "expected": item["sha256"],
                "observed": observed,
            })

    expected_payload_count = expected_bundle.get("payload_file_count")
    if expected_payload_count is not None and len(files) != expected_payload_count:
        mismatches.append({
            "path": rel(bundle_manifest_path, repo_root),
            "expected": f"payload_file_count={expected_payload_count}",
            "observed": f"payload_file_count={len(files)}",
        })

    readme = bundle_root / "README.md"
    expected_readme_sha = expected_bundle.get("bundle_readme_sha256")
    if expected_readme_sha:
        if not readme.exists():
            missing.append(rel(readme, repo_root))
        elif sha256(readme) != expected_readme_sha:
            mismatches.append({
                "path": rel(readme, repo_root),
                "expected": expected_readme_sha,
                "observed": sha256(readme),
            })

    return {
        "status": "pass" if not missing and not mismatches else "fail",
        "mode": "curated_bundle",
        "checked_files": checked,
        "missing_files": missing,
        "mismatches": mismatches,
    }


def verify_legacy_layout(repo_root: Path, sealed_root: Path, manifest: dict, require_all: bool) -> dict:
    checked = 0
    missing = []
    mismatches = []

    for artifact in manifest["artifacts"]:
        artifact_dir = sealed_root / artifact["name"]
        for relative, expected in artifact.get("safe_files", {}).items():
            path = artifact_dir / relative
            if not path.exists():
                missing.append(rel(path, repo_root))
                continue
            observed = sha256(path)
            checked += 1
            if observed != expected:
                mismatches.append({
                    "path": rel(path, repo_root),
                    "expected": expected,
                    "observed": observed,
                })

    status = "pass"
    if mismatches or (require_all and missing):
        status = "fail"

    return {
        "status": status,
        "mode": "workflow_artifact_layout",
        "checked_files": checked,
        "missing_files": missing,
        "mismatches": mismatches,
        "require_all": require_all,
    }


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
        help="Fail if any manifest-declared file is absent.",
    )
    args = parser.parse_args()

    root = args.repo_root.resolve()
    sealed = (root / args.sealed_root).resolve() if not args.sealed_root.is_absolute() else args.sealed_root
    manifest = json.loads((root / "SEALED_ARTIFACT_MANIFEST.json").read_text(encoding="utf-8"))

    bundle_manifest = sealed / "mia-public-sealed-evidence" / "BUNDLE_MANIFEST.json"
    if bundle_manifest.exists():
        report = verify_curated_bundle(root, sealed, manifest)
    else:
        report = verify_legacy_layout(root, sealed, manifest, args.require_all)

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
