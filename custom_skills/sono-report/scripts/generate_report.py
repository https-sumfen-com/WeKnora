#!/usr/bin/env python3
"""End-to-end SONO plot report generator.

Preferred execute_skill_script usage:
  script_path: scripts/generate_report.py
  input: <REPORT_DATA JSON>
  args: ["--output-dir", "/app/report/", "--strict", "--report-no", "...", "--report-url", "..."]

This script reads REPORT_DATA from stdin (or --input-json/--input-file), creates a
unique workspace, normalizes the data, renders template.html, saves the final
HTML under the output directory, posts report status when report_no is provided,
and prints a JSON result.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, request
from urllib.parse import quote, unquote, urlparse

DEFAULT_OUTPUT_DIR = "/app/report/"
PUBLIC_REPORT_BASE_URL = "https://sonoagi.com/report/"
DEFAULT_STATUS_ENDPOINT = "https://api.sumfen.com/api/support/llm/reports/common/status"
REQUEST_TIMEOUT_SECONDS = 60
STATUS_SUCCESS = "1"
STATUS_FAILURE = "2"


class ReportGenerationError(RuntimeError):
    """Raised for report-generation failures that should mark the report failed."""


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
        raise ReportGenerationError("\n".join(message))
    return result.stdout.strip()


def read_input(args: argparse.Namespace) -> str:
    if args.input_json:
        return args.input_json
    if args.input_file:
        return Path(args.input_file).read_text(encoding="utf-8")
    stdin_bytes = sys.stdin.buffer.read()
    if stdin_bytes.strip():
        return stdin_bytes.decode("utf-8")
    raise ReportGenerationError("REPORT_DATA JSON is required via stdin, --input-json, or --input-file")


def create_workspace(output_dir: Path) -> Path:
    work_root = output_dir / ".work"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
    work_dir = work_root / f"report_{stamp}_{os.getpid()}"
    work_dir.mkdir(parents=True, exist_ok=False)
    return work_dir


def require_http_url(value: str, label: str) -> str:
    text = value.strip()
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ReportGenerationError(f"{label} must be an HTTP(S) URL")
    return text


def derive_report_filename(report_no: str, report_url: str) -> str:
    parsed = urlparse(report_url.strip())
    decoded_path = unquote(parsed.path or "")
    path_segments = [segment for segment in decoded_path.split("/") if segment]
    if any(segment in {".", ".."} for segment in path_segments):
        raise ReportGenerationError("report_url path must not contain path traversal")
    raw_name = path_segments[-1] if path_segments else ""
    filename = raw_name or f"{report_no}.html"
    if not filename:
        raise ReportGenerationError("Cannot derive output filename from report_url or report_no")
    if "/" in filename or "\\" in filename:
        raise ReportGenerationError("Derived report filename must not contain path separators")
    if filename in {".", ".."} or ".." in filename:
        raise ReportGenerationError("Derived report filename must not contain path traversal")
    if Path(filename).name != filename:
        raise ReportGenerationError("Derived report filename must be a plain filename")
    if not filename.lower().endswith(".html"):
        raise ReportGenerationError("Derived report filename must end with .html")
    return filename


def status_headers(args: argparse.Namespace) -> dict[str, str] | None:
    status_values = [args.report_no, args.report_url, args.plot_id, args.cid, args.entity_id, args.entity_info_id]
    if not any(status_values):
        return None
    missing = []
    if not args.report_no:
        missing.append("--report-no")
    if not args.report_url:
        missing.append("--report-url")
    if not args.plot_id:
        missing.append("--plot-id")
    if not args.cid:
        missing.append("--cid")
    if not args.entity_id:
        missing.append("--entity-id")
    if not args.entity_info_id:
        missing.append("--entity-info-id")
    if missing:
        raise ReportGenerationError("Missing required status/report parameters: " + ", ".join(missing))
    return {
        "Content-Type": "application/json",
        "plot-id": str(args.plot_id).strip(),
        "cid": str(args.cid).strip(),
        "entity-id": str(args.entity_id).strip(),
        "entity-info-id": str(args.entity_info_id).strip(),
    }


def post_status(endpoint: str, headers: dict[str, str], report_no: str, status: str) -> tuple[int, Any]:
    endpoint = require_http_url(endpoint, "status endpoint")
    body = {"report_no": report_no, "status": status}
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = request.Request(endpoint, data=data, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            response_status = int(resp.status)
            response_text = resp.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace")
        raise ReportGenerationError(f"Report status update failed with HTTP {exc.code}: {response_text[:500]}") from exc
    except error.URLError as exc:
        raise ReportGenerationError(f"Report status update failed: {exc.reason}") from exc

    if not response_text.strip():
        return response_status, {}
    try:
        return response_status, json.loads(response_text)
    except json.JSONDecodeError:
        return response_status, {"raw": response_text}


def generate(args: argparse.Namespace, headers: dict[str, str] | None) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        raise ReportGenerationError("--output-dir must be an absolute path, normally /app/report/")

    raw = read_input(args)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReportGenerationError(f"REPORT_DATA input is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ReportGenerationError("REPORT_DATA must be a JSON object")

    report_url = require_http_url(args.report_url, "--report-url") if args.report_url else ""
    output_filename = derive_report_filename(args.report_no, report_url) if args.report_no or args.report_url else ""

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

    save_cmd = [
        sys.executable,
        str(script_dir / "save_report_html.py"),
        str(generated_path),
        str(normalized_path),
        "--output-dir",
        str(output_dir),
    ]
    if output_filename:
        save_cmd.extend(["--output-filename", output_filename])
    save_stdout = run_step(save_cmd, "save")

    final_path = save_stdout.splitlines()[-1].strip()
    final_file = Path(final_path).name
    public_url = report_url or PUBLIC_REPORT_BASE_URL + quote(final_file)
    sono_report = f"<sono-report>{public_url}</sono-report>"

    status_result: dict[str, Any] | None = None
    if headers and args.report_no:
        status_code, status_response = post_status(args.status_endpoint, headers, args.report_no, STATUS_SUCCESS)
        status_result = {"status_code": status_code, "response": status_response}

    result = {
        "ok": True,
        "work_dir": str(work_dir),
        "normalized_data": str(normalized_path),
        "generated_html": str(generated_path),
        "final_html": final_path,
        "file": final_file,
        "public_url": public_url,
        "sono_report": sono_report,
    }
    if args.report_no:
        result["report_no"] = args.report_no
    if status_result is not None:
        result["status_update"] = status_result
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and save a SONO plot report from REPORT_DATA JSON")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Final report directory")
    parser.add_argument("--template", default="template.html", help="HTML template path, relative to skill root by default")
    parser.add_argument("--strict", action="store_true", help="Enable strict plot-report validation")
    parser.add_argument("--input-json", help="REPORT_DATA JSON string; prefer stdin for large payloads")
    parser.add_argument("--input-file", help="Existing REPORT_DATA JSON file")
    parser.add_argument("--report-no", help="Pre-created report number from sono-report-request")
    parser.add_argument("--report-url", help="Pre-created public report URL from sono-report-request")
    parser.add_argument("--plot-id", help="plot-id header value for report status callback")
    parser.add_argument("--cid", help="cid header value for report status callback")
    parser.add_argument("--entity-id", help="entity-id header value for report status callback")
    parser.add_argument("--entity-info-id", help="entity-info-id header value for report status callback")
    parser.add_argument("--status-endpoint", default=DEFAULT_STATUS_ENDPOINT, help="Report status callback endpoint")
    args = parser.parse_args()

    headers: dict[str, str] | None = None
    try:
        headers = status_headers(args)
        result = generate(args, headers)
    except Exception as exc:
        failure_update_error = ""
        if headers and args.report_no:
            try:
                post_status(args.status_endpoint, headers, args.report_no, STATUS_FAILURE)
            except Exception as status_exc:  # noqa: BLE001 - include callback failure in script error
                failure_update_error = f"; failure status update also failed: {status_exc}"
        raise SystemExit(f"{exc}{failure_update_error}") from exc

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
