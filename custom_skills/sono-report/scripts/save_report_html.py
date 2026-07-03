#!/usr/bin/env python3
"""Save generated SONO report HTML to the report output directory.

Usage:
  python scripts/save_report_html.py report.html report_data.json [--output-dir /app/report/]

The filename is: <plot-name>_<report-date>_<generated-time>.html
For plot/WOFOST/weather reports this script refuses plot_id-like names such as
"地块 23181" because user-facing report titles and filenames must use the real
plot name.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT_DIR = "/app/report/"
ID_LIKE_RE = re.compile(r"^(?:地块\s*)?(?:ID[:：]?\s*)?\d+$", re.IGNORECASE)
SAFE_CHARS_RE = re.compile(r"[^\w一-鿿.-]+", re.UNICODE)


def is_present(value: Any) -> bool:
    return value is not None and value != "" and value != "NaN"


def ensure_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def ensure_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def is_id_like(value: Any) -> bool:
    if not is_present(value):
        return False
    return bool(ID_LIKE_RE.match(str(value).strip()))


def first_text(*values: Any) -> str:
    for value in values:
        if is_present(value):
            text = str(value).strip()
            if text:
                return text
    return ""


def derive_plot_name(data: dict[str, Any]) -> str:
    meta = ensure_dict(data.get("meta"))
    plots = ensure_list(data.get("plots"))
    devices = ensure_dict(data.get("devices"))
    wofost = ensure_dict(data.get("wofost"))

    candidates: list[Any] = [meta.get("plotName"), meta.get("subjectName"), meta.get("name")]
    candidates.extend(ensure_dict(plot).get("name") for plot in plots)
    for item in ensure_list(devices.get("items")):
        candidates.append(ensure_dict(item).get("plotName"))
    candidates.extend([wofost.get("plotName"), wofost.get("plotNo")])

    for candidate in candidates:
        if is_present(candidate) and not is_id_like(candidate):
            return str(candidate).strip()
    return ""


def extract_date(value: str) -> str:
    match = re.search(r"\d{4}-\d{2}-\d{2}", value or "")
    return match.group(0) if match else ""


def report_date(data: dict[str, Any]) -> str:
    meta = ensure_dict(data.get("meta"))
    wofost = ensure_dict(data.get("wofost"))
    return (
        extract_date(first_text(meta.get("reportDate")))
        or extract_date(first_text(wofost.get("reportDate")))
        or extract_date(first_text(meta.get("periodEnd")))
        or extract_date(first_text(meta.get("generatedAt")))
        or datetime.now().strftime("%Y-%m-%d")
    )


def generated_time(data: dict[str, Any]) -> str:
    meta = ensure_dict(data.get("meta"))
    value = first_text(meta.get("generatedAt"))
    match = re.search(r"(\d{2}):(\d{2})(?::(\d{2}))?", value)
    if match:
        return "".join(part or "00" for part in match.groups())
    return datetime.now().strftime("%H%M%S")


def safe_filename_part(value: str) -> str:
    cleaned = SAFE_CHARS_RE.sub("_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    return cleaned[:80] or "sono-report"


def main() -> None:
    parser = argparse.ArgumentParser(description="Save generated SONO report HTML")
    parser.add_argument("html_file", help="Generated HTML file to save")
    parser.add_argument("report_data", help="Normalized REPORT_DATA JSON file")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Destination directory")
    args = parser.parse_args()

    html_path = Path(args.html_file)
    data_path = Path(args.report_data)
    data = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("REPORT_DATA must be a JSON object")

    plot_name = derive_plot_name(data)
    if not plot_name:
        raise SystemExit("Missing real plot name. Do not save reports with plot_id as the title or filename.")

    date_part = safe_filename_part(report_date(data))
    time_part = safe_filename_part(generated_time(data))
    name_part = safe_filename_part(plot_name)
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        raise SystemExit("--output-dir must be an absolute path, normally /app/report/")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{name_part}_{date_part}_{time_part}.html"
    output_path.write_text(html_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(str(output_path))


if __name__ == "__main__":
    main()
