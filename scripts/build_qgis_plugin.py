"""Build a QGIS ZIP on the target OS using its matching Python (developer only)."""

import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.suffix != ".zip":
        parser.error("--output must end in .zip")
    with tempfile.TemporaryDirectory() as directory:
        staging = Path(directory)
        plugin = staging / "rhinestone_search"
        shutil.copytree(
            ROOT / "qgis_plugin/rhinestone_search",
            plugin,
            ignore=shutil.ignore_patterns("__pycache__", "vendor", "bundle.json"),
        )
        requirements = staging / "requirements.txt"
        with requirements.open("w") as stream:
            subprocess.run(
                ["uv", "export", "--locked", "--no-dev", "--no-emit-project"],
                cwd=ROOT,
                stdout=stream,
                check=True,
            )
        vendor = plugin / "vendor"
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                sys.executable,
                "--target",
                str(vendor),
                "--no-deps",
                "-r",
                str(requirements),
            ],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", str(staging / "dist")],
            cwd=ROOT,
            check=True,
        )
        wheel = next((staging / "dist").glob("*.whl"))
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                sys.executable,
                "--target",
                str(vendor),
                "--no-deps",
                str(wheel),
            ],
            check=True,
        )
        (plugin / "bundle.json").write_text(
            json.dumps(
                {
                    "python": list(sys.version_info[:2]),
                    "platform": sys.platform,
                    "machine": platform.machine(),
                }
            ),
            encoding="utf-8",
        )
        shutil.copy(ROOT / "LICENSE", plugin / "LICENSE")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        shutil.make_archive(
            str(args.output.with_suffix("")), "zip", staging, "rhinestone_search"
        )
        print(args.output)


if __name__ == "__main__":
    main()
