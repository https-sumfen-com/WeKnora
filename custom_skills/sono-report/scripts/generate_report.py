#!/usr/bin/env python3
"""End-to-end SONO plot report generator.

Preferred execute_skill_script usage:
  script_path: scripts/generate_report.py
  input: <REPORT_DATA JSON>
  args: ["--output-dir", "/app/report/", "--strict"]

This script reads REPORT_DATA from stdin (or --input-json/--input-file), creates a
unique workspace, normalizes the data, renders template.html, saves the final
HTML under the output directory, and prints a JSON result.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

DEFAULT_OUTPUT_DIR = "/app/report/"
PUBLIC_REPORT_BASE_URL = "https://sonoagi.com/report/"


def run_step(cmd: list[str], step: str) -> str:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace", capture_output=True, env=env)
    if result.returncode != 0:
        message = [f"{step} failed with exit code {result.returncode}"]
        if result.stdout.strip():
            message.append(f"stdout: {result.stdout.strip()}")
        if result.stderr.strip():
            message.append(f"stderr: {result.stderr.strip()}")
        raise SystemExit("\n".join(message))
    return result.stdout.strip()


def read_input(args: argparse.Namespace) -> str:
    if args.input_json:
        return args.input_json
    if args.input_file:
        return Path(args.input_file).read_text(encoding="utf-8")
    stdin_bytes = sys.stdin.buffer.read()
    if stdin_bytes.strip():
        return stdin_bytes.decode("utf-8")
    raise SystemExit("REPORT_DATA JSON is required via stdin, --input-json, or --input-file")


def create_workspace(output_dir: Path) -> Path:
    work_root = output_dir / ".work"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
    work_dir = work_root / f"report_{stamp}_{os.getpid()}"
    work_dir.mkdir(parents=True, exist_ok=False)
    return work_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and save a SONO plot report from REPORT_DATA JSON")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Final report directory")
    parser.add_argument("--template", default="template.html", help="HTML template path, relative to skill root by default")
    parser.add_argument("--strict", action="store_true", help="Enable strict plot-report validation")
    parser.add_argument("--input-json", help="REPORT_DATA JSON string; prefer stdin for large payloads")
    parser.add_argument("--input-file", help="Existing REPORT_DATA JSON file")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        raise SystemExit("--output-dir must be an absolute path, normally /app/report/")

    raw = read_input(args)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"REPORT_DATA input is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit("REPORT_DATA must be a JSON object")

    skill_root = Path(__file__).resolve().parents[1]
    script_dir = skill_root / "scripts"
    template_path = Path(args.template)
    if not template_path.is_absolute():
        template_path = skill_root / template_path

    work_dir = create_workspace(output_dir)
    input_path = work_dir / "input-report-data.json"
    normalized_path = work_dir / "normalized-report-data.json"
    generated_path = work_dir / "generated-report.html"
    input_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")

    preprocess_cmd = [sys.executable, str(script_dir / "preprocess_report_data.py"), str(input_path), str(normalized_path)]
    if args.strict:
        preprocess_cmd.append("--strict")
    run_step(preprocess_cmd, "preprocess")

    run_step([
        sys.executable,
        str(script_dir / "render_report_html.py"),
        str(template_path),
        str(normalized_path),
        str(generated_path),
    ], "render")

    save_stdout = run_step([
        sys.executable,
        str(script_dir / "save_report_html.py"),
        str(generated_path),
        str(normalized_path),
        "--output-dir",
        str(output_dir),
    ], "save")
    final_path = save_stdout.splitlines()[-1].strip()
    final_file = Path(final_path).name
    public_url = PUBLIC_REPORT_BASE_URL + quote(final_file)
    sono_report = f"<sono-report>{public_url}</sono-report>"

    print(json.dumps({
        "ok": True,
        "work_dir": str(work_dir),
        "normalized_data": str(normalized_path),
        "generated_html": str(generated_path),
        "final_html": final_path,
        "file": final_file,
        "public_url": public_url,
        "sono_report": sono_report,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
