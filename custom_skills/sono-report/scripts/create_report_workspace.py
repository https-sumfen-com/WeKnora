#!/usr/bin/env python3
"""Create a unique workspace for one SONO report generation run.

Usage:
  python scripts/create_report_workspace.py [--base-dir /app/report/]

Creates: <base-dir>/.work/report_<YYYYMMDD_HHMMSSffffff>_<pid>
Prints the workspace path to stdout.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

DEFAULT_BASE_DIR = "/app/report/"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create unique SONO report workspace")
    parser.add_argument("--base-dir", default=DEFAULT_BASE_DIR, help="Final report base directory")
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    work_root = base_dir / ".work"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
    work_dir = work_root / f"report_{stamp}_{os.getpid()}"
    work_dir.mkdir(parents=True, exist_ok=False)
    print(str(work_dir))


if __name__ == "__main__":
    main()
