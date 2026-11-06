#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STEPS = [f"step{index}.py" for index in range(1, 8)]


def main():
    (ROOT / "data").mkdir(parents=True, exist_ok=True)
    for step in STEPS:
        print(f"\n=== {step} ===", flush=True)
        result = subprocess.run(
            [sys.executable, str(ROOT / "pipeline" / step)], cwd=ROOT
        )
        if result.returncode:
            return result.returncode
    if "--validate" in sys.argv[1:]:
        print("\n=== validate.py ===", flush=True)
        return subprocess.run(
            [sys.executable, str(ROOT / "pipeline" / "validate.py")], cwd=ROOT
        ).returncode
    print(
        "\nAll 27 data CSVs regenerated. "
        "Run `python3 pipeline/validate.py` to check them."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
