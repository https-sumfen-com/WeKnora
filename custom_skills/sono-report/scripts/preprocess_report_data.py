#!/usr/bin/env python3
"""Normalize SONO report data before rendering HTML.

Usage:
  python scripts/preprocess_report_data.py input.json output.json [--strict]

The input/output object is the REPORT_DATA contract documented in SKILL.md.
This script performs deterministic normalization only; it never fabricates
business facts. In strict mode it fails when a plot report has only plot_id-like
names and no real plot name.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

ID_LIKE_RE = re.compile(r"^(?:地块\s*)?(?:ID[:：]?\s*)?\d+$", re.IGNORECASE)
DISALLOWED_DATA_SOURCES = {"get_summary_base"}
DISALLOWED_REPORT_TYPES = {"base_report", "summary_report", "enterprise_report", "comprehensive_report"}


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

    candidates: list[Any] = [
        meta.get("plotName"),
        meta.get("subjectName"),
        meta.get("name"),
    ]
    if plots:
        candidates.extend(ensure_dict(plot).get("name") for plot in plots)
    for item in ensure_list(devices.get("items")):
        candidates.append(ensure_dict(item).get("plotName"))
    candidates.extend([wofost.get("plotName"), wofost.get("plotNo")])

    for candidate in candidates:
        if is_present(candidate) and not is_id_like(candidate):
            return str(candidate).strip()
    return ""


def report_date(data: dict[str, Any]) -> str:
    meta = ensure_dict(data.get("meta"))
    wofost = ensure_dict(data.get("wofost"))
    value = first_text(meta.get("reportDate"), wofost.get("reportDate"), meta.get("periodEnd"), meta.get("generatedAt"))
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    if match:
        return match.group(0)
    return datetime.now().strftime("%Y-%m-%d")


def normalize_recommendations(data: dict[str, Any]) -> None:
    priority_rank = {"high": 0, "danger": 0, "mid": 1, "medium": 1, "warn": 1, "low": 2}
    seen: set[tuple[str, str]] = set()
    normalized: list[dict[str, Any]] = []
    for raw in ensure_list(data.get("recommendations")):
        item = ensure_dict(raw)
        title = first_text(item.get("title"), "农事建议")
        body = first_text(item.get("body"), item.get("content"))
        if not body:
            continue
        key = (title, body[:80])
        if key in seen:
            continue
        seen.add(key)
        priority = first_text(item.get("priority"), "low").lower()
        if priority not in priority_rank:
            priority = "low"
        badge = first_text(item.get("badge"), {"high": "紧急", "mid": "注意", "low": "建议"}.get(priority, "建议"))
        normalized.append({
            "priority": priority,
            "badge": badge,
            "title": title,
            "body": body,
            "source": first_text(item.get("source")),
        })
    normalized.sort(key=lambda item: priority_rank.get(item.get("priority", "low"), 2))
    data["recommendations"] = normalized[:5]


def normalize(data: dict[str, Any], strict: bool = False) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    meta = ensure_dict(data.get("meta"))
    data["meta"] = meta

    meta.setdefault("title", "地块报告")
    meta.setdefault("reportType", "plot_report")
    meta.setdefault("dataSources", [])
    if not isinstance(meta.get("dataSources"), list):
        meta["dataSources"] = [str(meta.get("dataSources"))]
    meta["dataSources"] = [str(source) for source in meta.get("dataSources", []) if is_present(source)]

    report_type = first_text(meta.get("reportType"), "plot_report")
    if report_type in DISALLOWED_REPORT_TYPES:
        raise SystemExit(f"sono-report only supports plot-based reports; disallowed reportType: {report_type}")
    disallowed_sources = sorted(set(meta["dataSources"]) & DISALLOWED_DATA_SOURCES)
    if disallowed_sources:
        raise SystemExit(f"sono-report only supports plot-based MCP sources; remove: {', '.join(disallowed_sources)}")
    if strict and "get_plot_info" not in meta["dataSources"]:
        raise SystemExit("plot reports must include get_plot_info so the report is grounded in a real plot")

    plot_name = derive_plot_name(data)
    title = first_text(meta.get("title"), "地块报告")
    subject = first_text(meta.get("subjectName"))

    if plot_name:
        meta["plotName"] = plot_name
        meta["subjectName"] = plot_name
    else:
        message = "plot report needs a real plot name from get_plot_info.payload.name or user input; do not use plot_id"
        if strict or is_id_like(subject):
            raise SystemExit(message)
        warnings.append(message)
        meta["subjectName"] = subject or title

    meta["reportDate"] = report_date(data)
    if not is_present(meta.get("generatedAt")):
        meta["generatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for key, default in {
        "overview": {"kpis": []},
        "charts": {"biomassTrend": []},
        "weather": {"now": None, "forecast": [], "alerts": []},
        "devices": {"summary": {}, "items": []},
        "wofost": {"phenology": [], "kpis": [], "waterBalance": [], "links": {}},
    }.items():
        if not isinstance(data.get(key), dict):
            data[key] = default

    data["plots"] = ensure_list(data.get("plots"))
    data["plotWarnings"] = ensure_list(data.get("plotWarnings"))
    data["moduleReports"] = ensure_list(data.get("moduleReports"))
    data["emptyStates"] = ensure_list(data.get("emptyStates"))
    normalize_recommendations(data)
    return data, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize SONO report REPORT_DATA JSON")
    parser.add_argument("input", help="Input REPORT_DATA JSON file")
    parser.add_argument("output", help="Output normalized REPORT_DATA JSON file")
    parser.add_argument("--strict", action="store_true", help="Fail if plot name is missing or title is plot_id-like")
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("REPORT_DATA must be a JSON object")
    normalized, warnings = normalize(data, strict=args.strict)
    Path(args.output).write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    for warning in warnings:
        print(f"WARNING: {warning}")
    print(args.output)


if __name__ == "__main__":
    main()
