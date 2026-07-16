#!/usr/bin/env python3
"""Build and send a SONO report-generation POST request.

Preferred execute_skill_script usage:
  script_path: scripts/request_report.py
  input: <JSON containing query, user_id, plot_id, cid, entity-id, entity-info-id, plot_name>

The script generates report_no, infers report_type from the user query,
builds the required headers and JSON body, POSTs to the hard-coded default
endpoint, and prints exactly `<sono-report>{url}</sono-report>` by default so the
agent can return the required frontend format verbatim.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from typing import Any
from urllib import error, request

PUBLIC_REPORT_BASE_URL = "https://sonoagi.com/report/"
# TODO: Replace this placeholder with the production report-generation POST endpoint.
DEFAULT_REPORT_ENDPOINT = "https://api.sumfen.com/api/support/llm/reports/common"
DEFAULT_AGENT_ID = "builtin-wiki-fixer"
REQUEST_TIMEOUT_SECONDS = 60

REPORT_TYPE_CN_NAMES = {
    "overall_report": "整体地块报告",
    "plot_growth_analysis": "长势分析",
    "plot_3d_phenotype": "三维表型",
    "plot_growth_dynamics": "生长动态（wofost）",
    "plot_seedling_monitoring": "苗情监控",
}

REPORT_TYPE_KEYWORDS = [
    ("plot_seedling_monitoring", ("苗情监控", "苗情", "出苗", "幼苗", "苗期")),
    ("plot_growth_dynamics", ("生长动态", "wofost", "生长模拟", "动态报告")),
    ("plot_3d_phenotype", ("三维表型", "3d表型", "3d 表型", "三维", "表型")),
    ("plot_growth_analysis", ("长势分析", "长势", "生长势")),
    ("overall_report", ("整体地块报告", "整体报告", "地块报告", "综合报告", "总览报告")),
]

REPORT_TYPE_ALIASES = {
    "overall_report": "overall_report",
    "整体地块报告": "overall_report",
    "整体报告": "overall_report",
    "地块报告": "overall_report",
    "plot_growth_analysis": "plot_growth_analysis",
    "长势分析": "plot_growth_analysis",
    "plot_3d_phenotype": "plot_3d_phenotype",
    "三维表型": "plot_3d_phenotype",
    "plot_growth_dynamics": "plot_growth_dynamics",
    "生长动态": "plot_growth_dynamics",
    "生长动态（wofost）": "plot_growth_dynamics",
    "生长动态(wofost)": "plot_growth_dynamics",
    "wofost": "plot_growth_dynamics",
    "plot_seedling_monitoring": "plot_seedling_monitoring",
    "苗情监控": "plot_seedling_monitoring",
}


class InputError(SystemExit):
    """Raised for user/actionable input problems."""


def read_input(args: argparse.Namespace) -> dict[str, Any]:
    if args.input_json:
        raw = args.input_json
    elif args.input_file:
        with open(args.input_file, "r", encoding="utf-8") as f:
            raw = f.read()
    else:
        raw = sys.stdin.buffer.read().decode("utf-8")

    if not raw.strip():
        raise InputError("Input JSON is required via stdin, --input-json, or --input-file")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InputError(f"Input is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise InputError("Input JSON must be an object")
    return payload


def first_present(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return ""


def normalize_report_type(value: str) -> str:
    report_type = REPORT_TYPE_ALIASES.get(value.strip())
    if not report_type:
        report_type = REPORT_TYPE_ALIASES.get(value.strip().lower())
    if not report_type:
        supported = ", ".join(REPORT_TYPE_CN_NAMES)
        raise InputError(f"Unsupported report_type: {value}. Supported: {supported}")
    return report_type


def infer_report_type(query: str) -> str:
    normalized_query = query.lower().replace(" ", "")
    for report_type, keywords in REPORT_TYPE_KEYWORDS:
        for keyword in keywords:
            if keyword.lower().replace(" ", "") in normalized_query:
                return report_type
    supported = "、".join(f"{cn}({code})" for code, cn in REPORT_TYPE_CN_NAMES.items())
    raise InputError(f"Cannot infer report_type from query. Supported report types: {supported}")


def require_fields(payload: dict[str, Any]) -> dict[str, str]:
    values = {
        "query": first_present(payload, "query", "user_query", "userQuestion"),
        "tgzn_user_id": first_present(payload, "tgzn_user_id", "user_id", "userId", "user-id"),
        "plot_id": first_present(payload, "plot_id", "plotId", "plot-id"),
        "cid": first_present(payload, "cid"),
        "entity-id": first_present(payload, "entity-id", "entity_id", "entityId"),
        "entity-info-id": first_present(payload, "entity-info-id", "entity_info_id", "entityInfoId"),
        "plot_name": first_present(payload, "plot_name", "plotName", "plot-name"),
        "agent_id": first_present(payload, "agent_id", "agentId") or DEFAULT_AGENT_ID,
    }
    missing = [key for key, value in values.items() if key != "agent_id" and not value]
    if missing:
        raise InputError("Missing required fields: " + ", ".join(missing))

    explicit_report_type = first_present(payload, "report_type", "reportType", "report-type")
    values["report_type"] = normalize_report_type(explicit_report_type) if explicit_report_type else infer_report_type(values["query"])
    values["report_type_cn_name"] = REPORT_TYPE_CN_NAMES[values["report_type"]]
    values["title"] = f"{values['plot_name']}【{values['report_type_cn_name']}】"
    return values


def build_query(values: dict[str, str], report_no: str, report_url: str) -> str:
    return "\n".join([
        "##用户问题",
        values["query"],
        "",
        "##Skill访问机制",
        "- force_skill: sono-report",
        "- route_stage: backend_internal_report_render",
        "- forbidden_skills: sono-report-request, agri-operation-workflow",
        f"- final_response: <sono-report>{report_url}</sono-report>",
        "- instruction: 本次内部对话必须调用 sono-report skill 生成并保存报告；禁止回调 sono-report-request；禁止调用 agri-operation-workflow。生成完成后只返回 final_response 指定格式。",
        "",
        "##系统参数",
        f"- plot_id: {values['plot_id']}",
        f"- cid: {values['cid']}",
        f"- entity-id: {values['entity-id']}",
        f"- entity-info-id: {values['entity-info-id']}",
        f"- plot_name: {values['plot_name']}",
        f"- report_type: {values['report_type']}",
        f"- report_no: {report_no}",
        f"- report_url: {report_url}",
    ])


def extract_report_url(response_json: Any, fallback_url: str) -> str:
    if not isinstance(response_json, dict):
        return fallback_url

    candidates = [
        response_json.get("report_url"),
        response_json.get("reportUrl"),
        response_json.get("url"),
        response_json.get("file"),
    ]
    data = response_json.get("data")
    if isinstance(data, dict):
        candidates.extend([
            data.get("report_url"),
            data.get("reportUrl"),
            data.get("url"),
            data.get("file"),
        ])

    for candidate in candidates:
        if candidate is None:
            continue
        text = str(candidate).strip()
        if not text:
            continue
        if text.startswith("http://") or text.startswith("https://"):
            return text
        return PUBLIC_REPORT_BASE_URL + text.lstrip("/")
    return fallback_url


def post_json(endpoint: str, headers: dict[str, str], body: dict[str, Any]) -> tuple[int, Any]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = request.Request(endpoint, data=data, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            status = int(resp.status)
            response_text = resp.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Report request failed with HTTP {exc.code}: {response_text[:500]}") from exc
    except error.URLError as exc:
        raise SystemExit(f"Report request failed: {exc.reason}") from exc

    if not response_text.strip():
        return status, {}
    try:
        return status, json.loads(response_text)
    except json.JSONDecodeError:
        return status, {"raw": response_text}


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a SONO report-generation POST request")
    parser.add_argument("--endpoint", default=DEFAULT_REPORT_ENDPOINT, help="Report-generation POST endpoint; defaults to the hard-coded DEFAULT_REPORT_ENDPOINT")
    parser.add_argument("--input-json", help="Input JSON string; prefer stdin for larger payloads")
    parser.add_argument("--input-file", help="Path to input JSON file")
    parser.add_argument("--json-output", action="store_true", help="Manual debugging only: print full JSON instead of the required sono-report tag")
    args = parser.parse_args()

    endpoint = args.endpoint.strip()
    if not (endpoint.startswith("http://") or endpoint.startswith("https://")):
        raise InputError("Report endpoint must be an HTTP(S) URL")

    payload = read_input(args)
    values = require_fields(payload)
    report_no = uuid.uuid4().hex
    report_url = f"{PUBLIC_REPORT_BASE_URL}{report_no}.html"

    headers = {
        "Content-Type": "application/json",
        "plot-id": values["plot_id"],
        "cid": values["cid"],
        "entity-id": values["entity-id"],
        "entity-info-id": values["entity-info-id"],
    }
    body = {
        "related_id": int(values["plot_id"]),
        "report_no": report_no,
        "report_url": report_url,
        "agent_id": values["agent_id"],
        "query": build_query(values, report_no, report_url),
        "tgzn_user_id": int(values["tgzn_user_id"]),
        "title": values["title"],
        "report_type": values["report_type"],
    }

    status, response_json = post_json(endpoint, headers, body)
    final_report_url = extract_report_url(response_json, report_url)
    sono_report = f"<sono-report>{final_report_url}</sono-report>"

    result = {
        "ok": True,
        "status": status,
        "report_no": report_no,
        "report_url": final_report_url,
        "sono_report": sono_report,
        "response": response_json,
    }
    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(sono_report)


if __name__ == "__main__":
    main()
