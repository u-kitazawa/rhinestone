"""Audit every registry package/version in uv.lock (Python >=3.11 tooling)."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import tomllib


def locked_requirements(lock):
    packages = set()
    for package in lock["package"]:
        source = package["source"]
        if "registry" in source:
            packages.add((package["name"], package["version"]))
        elif source != {"editable": "."} or package["name"] != "rhinestone":
            raise ValueError("Unverifiable non-registry dependency in uv.lock")
    if not packages:
        raise ValueError("No registry dependencies in uv.lock")
    return packages


def audit_status(report, expected, returncode):
    dependencies = report["dependencies"]
    actual = {(item["name"], item["version"]) for item in dependencies}
    if actual != expected or any("skip_reason" in item for item in dependencies):
        raise ValueError("Incomplete dependency audit")
    findings = sum(len(item["vulns"]) for item in dependencies)
    if returncode != (1 if findings else 0):
        raise ValueError("Auditor failed without a consistent complete report")
    return findings


def requirement_batches(packages):
    batches = []
    for name, version in sorted(packages):
        for batch in batches:
            if name not in batch:
                batch[name] = version
                break
        else:
            batches.append({name: version})
    return [set(batch.items()) for batch in batches]


def main():
    root = Path(__file__).resolve().parents[1]
    try:
        subprocess.run(["uv", "lock", "--check"], cwd=root, check=True)
        packages = locked_requirements(tomllib.loads((root / "uv.lock").read_text()))
        reports = []
        findings = 0
        for batch in requirement_batches(packages):
            report, count = audit_batch(root, batch)
            reports.append(report)
            findings += count
        if findings:
            print(json.dumps(reports, indent=2))
            print(f"VULNERABILITIES: {findings} known findings", file=sys.stderr)
            return 1
        print(f"AUDIT PASSED: {len(packages)} locked package/version pairs")
        return 0
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as exc:
        print(
            f"AUDIT INCOMPLETE (tool/network/lock/report error): {exc}", file=sys.stderr
        )
        return 2


def audit_batch(root, packages):
    # pip-audit rejects different versions of one name in a single invocation.
    # Split alternatives into batches instead of discarding any locked version.
    with tempfile.TemporaryDirectory() as directory:
        requirements = Path(directory) / "requirements.txt"
        report_path = Path(directory) / "audit.json"
        # No markers: audit all Python/platform alternatives and dev dependencies,
        # including multiple locked versions, without resolving or installing them.
        requirements.write_text(
            "".join(f"{name}=={version}\n" for name, version in sorted(packages))
        )
        result = subprocess.run(
            [
                "uv",
                "tool",
                "run",
                "--from",
                "pip-audit==2.10.1",
                "pip-audit",
                "--requirement",
                str(requirements),
                "--no-deps",
                "--disable-pip",
                "--strict",
                "--progress-spinner",
                "off",
                "--timeout",
                "30",
                "--format",
                "json",
                "--output",
                str(report_path),
            ],
            cwd=root,
            check=False,
            timeout=240,
        )
        report = json.loads(report_path.read_text())
        findings = audit_status(report, packages, result.returncode)
        return report, findings


if __name__ == "__main__":
    sys.exit(main())
