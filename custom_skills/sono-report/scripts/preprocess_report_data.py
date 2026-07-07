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
import csv
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

ID_LIKE_RE = re.compile(r"^(?:地块\s*)?(?:ID[:：]?\s*)?\d+$", re.IGNORECASE)
DISALLOWED_DATA_SOURCES = {"get_summary_base"}
DISALLOWED_REPORT_TYPES = {"base_report", "summary_report", "enterprise_report", "comprehensive_report"}
EMPTY_TEXT_VALUES = {"", "nan", "null", "none", "undefined", "nil", "n/a", "--", "-", "—", "无", "暂无", "未提供"}
MODULE_REPORT_TYPES = {
    "plot_growth_analysis",
    "plot_3d_phenotype",
    "plot_growth_dynamics",
    "plot_seedling_monitoring",
}
OVERALL_REPORT_TYPE = "overall_report"
OVERALL_MODULE_ORDER = [
    "plot_growth_analysis",
    "plot_3d_phenotype",
    "plot_growth_dynamics",
    "plot_seedling_monitoring",
]
CSV_TO_TREND_KEYS = {
    "DVS": "dvs",
    "LAI": "lai",
    "TAGP": "tagp",
    "WSO": "wso",
    "WLV": "wlv",
    "WST": "wst",
    "WRT": "wrt",
    "RD": "rd",
    "SM": "soilMoisture",
    "TRA": "tra",
    "EVS": "evs",
    "NuptakeTotal": "nUptakeTotal",
}
REQUIRED_TOP_LEVEL_DEFAULTS: dict[str, Any] = {
    "overview": {"kpis": []},
    "charts": {"biomassTrend": []},
    "weather": {"now": {}, "forecast": [], "alerts": []},
    "devices": {"summary": {}, "items": []},
    "wofost": {"phenology": [], "kpis": [], "waterBalance": [], "links": {}},
    "plots": [],
    "plotWarnings": [],
    "moduleReports": [],
    "recommendations": [],
    "emptyStates": [],
}


def is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return not (isinstance(value, float) and (math.isnan(value) or math.isinf(value)))
    if isinstance(value, str):
        return value.strip().lower() not in EMPTY_TEXT_VALUES
    if isinstance(value, list):
        return any(is_present(item) for item in value)
    if isinstance(value, dict):
        return any(is_present(item) for item in value.values())
    return True


def is_nan_like(value: Any) -> bool:
    return not is_present(value)


def parse_float(value: Any) -> float | None:
    if is_nan_like(value):
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def ensure_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def ensure_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def is_id_like(value: Any) -> bool:
    if not is_present(value):
        return False
    return bool(ID_LIKE_RE.match(str(value).strip()))


def text_from_any(value: Any) -> str:
    if not is_present(value):
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = [text_from_any(item) for item in value]
        return "；".join(part for part in parts if part)
    if isinstance(value, dict):
        for key in [
            "body",
            "content",
            "description",
            "message",
            "reason",
            "suggestion",
            "suggestions",
            "advice",
            "handle_suggestion",
            "recommendation",
            "remark",
            "value",
            "title",
            "label",
            "name",
        ]:
            text = text_from_any(value.get(key))
            if text:
                return text
    return str(value).strip()


def first_text(*values: Any) -> str:
    for value in values:
        text = text_from_any(value)
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
    priority_rank = {"high": 0, "danger": 0, "red": 0, "mid": 1, "medium": 1, "warn": 1, "amber": 1, "low": 2}
    seen: set[tuple[str, str]] = set()
    normalized: list[dict[str, Any]] = []
    for raw in ensure_list(data.get("recommendations")):
        item = raw if isinstance(raw, dict) else {"body": raw}
        title = first_text(item.get("title"), item.get("label"), item.get("badge"), "农事建议")
        body = first_text(
            item.get("body"),
            item.get("content"),
            item.get("description"),
            item.get("message"),
            item.get("reason"),
            item.get("suggestion"),
            item.get("suggestions"),
            item.get("advice"),
            item.get("handle_suggestion"),
            item.get("recommendation"),
            item.get("remark"),
            raw if not isinstance(raw, dict) else "",
        )
        if not body:
            continue
        key = (title, body[:80])
        if key in seen:
            continue
        seen.add(key)
        priority = first_text(item.get("priority"), item.get("level"), "low").lower()
        if priority not in priority_rank:
            priority = "low"
        badge = first_text(item.get("badge"), {"high": "紧急", "danger": "紧急", "mid": "注意", "medium": "注意", "warn": "注意", "low": "建议"}.get(priority, "建议"))
        normalized.append({
            "priority": priority,
            "badge": badge,
            "title": title,
            "body": body,
            "source": first_text(item.get("source")),
        })
    normalized.sort(key=lambda item: priority_rank.get(item.get("priority", "low"), 2))
    data["recommendations"] = normalized[:8]


def normalize_paper(data: dict[str, Any]) -> None:
    paper = ensure_dict(data.get("paper"))
    for key in ["keywords", "methods", "findings", "discussion", "conclusions", "limitations", "appendixLinks"]:
        value = paper.get(key)
        if value is None:
            paper[key] = []
        elif isinstance(value, list):
            paper[key] = value
        else:
            paper[key] = [value]
    if not isinstance(paper.get("abstract"), str):
        paper["abstract"] = first_text(paper.get("abstract"))
    data["paper"] = paper


def normalize_report_type_and_subtype(data: dict[str, Any]) -> None:
    meta = ensure_dict(data.get("meta"))
    report_type = first_text(meta.get("reportType"), "plot_report")
    subtype = first_text(meta.get("reportSubtype"), meta.get("report_type"), meta.get("type"))

    if report_type in MODULE_REPORT_TYPES:
        subtype = report_type
        report_type = "plot_module_report"
    elif report_type == OVERALL_REPORT_TYPE:
        subtype = OVERALL_REPORT_TYPE
        report_type = "plot_overall_report"
    elif subtype in MODULE_REPORT_TYPES:
        report_type = "plot_module_report"
    elif subtype == OVERALL_REPORT_TYPE:
        report_type = "plot_overall_report"

    meta["reportType"] = report_type
    if subtype:
        meta["reportSubtype"] = subtype
    elif report_type == "plot_overall_report":
        meta["reportSubtype"] = OVERALL_REPORT_TYPE
    data["meta"] = meta


def module_sort_key(module: dict[str, Any]) -> tuple[int, str]:
    module_type = first_text(module.get("type"), module.get("reportType"))
    if module_type in OVERALL_MODULE_ORDER:
        return (OVERALL_MODULE_ORDER.index(module_type), module_type)
    return (len(OVERALL_MODULE_ORDER), module_type)


def normalize_module_reports(data: dict[str, Any]) -> None:
    meta = ensure_dict(data.get("meta"))
    subtype = first_text(meta.get("reportSubtype"))
    modules: list[dict[str, Any]] = []
    for raw in ensure_list(data.get("moduleReports")):
        module = ensure_dict(raw)
        module_type = first_text(module.get("type"), module.get("reportType"))
        if not module_type:
            continue
        module["type"] = module_type
        modules.append(module)

    if subtype in MODULE_REPORT_TYPES:
        modules = [module for module in modules if first_text(module.get("type")) == subtype]
    elif subtype == OVERALL_REPORT_TYPE or meta.get("reportType") == "plot_overall_report":
        modules = [module for module in modules if first_text(module.get("type")) in OVERALL_MODULE_ORDER]
        modules.sort(key=module_sort_key)
    data["moduleReports"] = modules


def wofost_csv_path() -> Path:
    custom_skills_dir = Path(__file__).resolve().parents[2]
    return custom_skills_dir / "sono-mcp" / "wofost-daily-report.csv"


def load_wofost_daily_csv() -> list[dict[str, float]]:
    path = wofost_csv_path()
    if not path.exists():
        return []
    rows: list[dict[str, float]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for index, raw in enumerate(reader, start=1):
            row: dict[str, float] = {"__index__": float(index)}
            for csv_key, report_key in CSV_TO_TREND_KEYS.items():
                number = parse_float(raw.get(csv_key))
                if number is not None:
                    row[report_key] = number
                    if report_key == "wso":
                        row["twso"] = number
            if any(key in row for key in CSV_TO_TREND_KEYS.values()):
                rows.append(row)
    return rows


def sample_rows(rows: list[dict[str, float]], max_points: int = 12) -> list[dict[str, float]]:
    if len(rows) <= max_points:
        return rows
    if max_points <= 1:
        return [rows[-1]]
    step = (len(rows) - 1) / (max_points - 1)
    sampled: list[dict[str, float]] = []
    seen: set[int] = set()
    for i in range(max_points):
        index = round(i * step)
        if index not in seen:
            sampled.append(rows[index])
            seen.add(index)
    return sampled


def valid_values(rows: list[dict[str, float]], key: str) -> list[float]:
    return [float(row[key]) for row in rows if key in row]


def latest_valid(rows: list[dict[str, float]], key: str) -> float | None:
    for row in reversed(rows):
        if key in row:
            return float(row[key])
    return None


def min_valid(rows: list[dict[str, float]], key: str) -> float | None:
    values = valid_values(rows, key)
    return min(values) if values else None


def max_valid(rows: list[dict[str, float]], key: str) -> float | None:
    values = valid_values(rows, key)
    return max(values) if values else None


def fmt_number(value: float | None, digits: int = 2) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def derive_dvs_stage(dvs: float | None) -> str:
    if dvs is None:
        return "模型阶段未明"
    if dvs < 0:
        return "播种后、出苗前"
    if dvs < 1:
        return "出苗后至开花前，营养生长期"
    if dvs < 2:
        return "开花后至成熟前，产量形成/灌浆期"
    return "成熟或接近模型终止阶段"


def metric(label: str, value: float | None, unit: str = "", sub: str = "模型模拟") -> dict[str, str] | None:
    rendered = fmt_number(value)
    if not rendered:
        return None
    item = {"label": label, "value": rendered, "sub": sub}
    if unit:
        item["unit"] = unit
    return item


def build_growth_dynamics_module(rows: list[dict[str, float]]) -> dict[str, Any] | None:
    if not rows:
        return None
    latest_dvs = latest_valid(rows, "dvs")
    max_lai = max_valid(rows, "lai")
    latest_lai = latest_valid(rows, "lai")
    latest_tagp = latest_valid(rows, "tagp")
    latest_wso = latest_valid(rows, "wso")
    min_sm = min_valid(rows, "soilMoisture")
    latest_sm = latest_valid(rows, "soilMoisture")
    latest_rd = latest_valid(rows, "rd")
    latest_n = latest_valid(rows, "nUptakeTotal")
    stage = derive_dvs_stage(latest_dvs)

    sampled = []
    for row in sample_rows(rows, 12):
        index = int(row.get("__index__", 0))
        item: dict[str, Any] = {"label": f"模型日{index}"}
        for key in ["dvs", "lai", "tagp", "wso", "twso", "soilMoisture", "rd", "nUptakeTotal", "tra", "evs"]:
            if key in row:
                item[key] = round(float(row[key]), 4)
        sampled.append(item)

    table_rows = []
    for row in sample_rows(rows, 8):
        index = int(row.get("__index__", 0))
        table_rows.append({
            "label": f"模型日{index}",
            "dvs": fmt_number(row.get("dvs")),
            "lai": fmt_number(row.get("lai")),
            "tagp": fmt_number(row.get("tagp")),
            "wso": fmt_number(row.get("wso")),
            "soilMoisture": fmt_number(row.get("soilMoisture"), 3),
            "rd": fmt_number(row.get("rd")),
        })

    analysis_items: list[dict[str, str]] = []
    if latest_dvs is not None:
        analysis_items.append({
            "title": "生育阶段推进",
            "body": f"DVS 最新有效值约为 {fmt_number(latest_dvs)}，模型判定作物处于“{stage}”。该判断来自 WOFOST 日序列模拟结果。",
            "level": "green",
        })
    if max_lai is not None or latest_lai is not None:
        parts = []
        if max_lai is not None:
            parts.append(f"LAI 最大值约为 {fmt_number(max_lai)}")
        if latest_lai is not None:
            parts.append(f"最新有效值约为 {fmt_number(latest_lai)}")
        analysis_items.append({
            "title": "冠层发育过程",
            "body": "，".join(parts) + "，可用于判断模型模拟的冠层扩展与后期衰减过程。",
            "level": "blue",
        })
    if latest_tagp is not None or latest_wso is not None:
        parts = []
        if latest_tagp is not None:
            parts.append(f"TAGP 最新有效值约为 {fmt_number(latest_tagp)}")
        if latest_wso is not None:
            parts.append(f"WSO 最新有效值约为 {fmt_number(latest_wso)}")
        analysis_items.append({
            "title": "生物量积累",
            "body": "，".join(parts) + "，反映模型模拟的地上生物量与贮藏器官干物重累积。",
            "level": "green",
        })
    if latest_sm is not None or min_sm is not None:
        level = "amber" if (latest_sm is not None and latest_sm < 0.2) or (min_sm is not None and min_sm < 0.2) else "green"
        parts = []
        if latest_sm is not None:
            parts.append(f"SM 最新有效值约为 {fmt_number(latest_sm, 3)}")
        if min_sm is not None:
            parts.append(f"最低有效值约为 {fmt_number(min_sm, 3)}")
        analysis_items.append({
            "title": "水分过程与胁迫关注",
            "body": "，".join(parts) + "。若持续低于 0.20，应结合墒情监测与灌溉记录进行现场复核。",
            "level": level,
        })

    metrics = [
        metric("最新 DVS", latest_dvs),
        metric("最大 LAI", max_lai),
        metric("最新 TAGP", latest_tagp),
        metric("最新 WSO", latest_wso),
        metric("最低 SM", min_sm, sub="模型模拟/水分过程"),
        metric("最新 RD", latest_rd),
        metric("最新氮素吸收", latest_n),
    ]

    return {
        "type": "plot_growth_dynamics",
        "title": "地块生长动态模型分析",
        "conclusion": "基于 WOFOST 日序列模型模拟结果，对作物生育阶段、冠层扩展、生物量积累、土壤水分及氮素吸收过程进行结构化分析。",
        "metrics": [item for item in metrics if item],
        "trendSeries": sampled,
        "analysisItems": analysis_items,
        "sections": [
            {
                "title": "模型数据说明",
                "items": [
                    "数据来自 wofost-daily-report.csv，属于生长动态（plot_growth_dynamics）报告。",
                    "该 CSV 不含日历日期，图表以模型日/序列编号标注，不编造观测日期。",
                    "所有 DVS、LAI、生物量、水分与氮素指标均按模型模拟/预测口径解释。",
                ],
            }
        ],
        "tables": [
            {
                "title": "WOFOST 代表性模型日摘要",
                "headers": ["label", "dvs", "lai", "tagp", "wso", "soilMoisture", "rd"],
                "rows": table_rows,
            }
        ],
        "source": "wofost-daily-report.csv",
    }


def upsert_growth_dynamics_module(data: dict[str, Any], module: dict[str, Any]) -> None:
    modules = ensure_list(data.get("moduleReports"))
    for index, existing in enumerate(modules):
        item = ensure_dict(existing)
        if first_text(item.get("type")) == "plot_growth_dynamics":
            merged = dict(module)
            for key, value in item.items():
                if is_present(value) or isinstance(value, (list, dict)):
                    merged[key] = value
            if not ensure_list(item.get("trendSeries")):
                merged["trendSeries"] = module.get("trendSeries", [])
            if not ensure_list(item.get("metrics")):
                merged["metrics"] = module.get("metrics", [])
            if not ensure_list(item.get("analysisItems")):
                merged["analysisItems"] = module.get("analysisItems", [])
            if not ensure_list(item.get("tables")):
                merged["tables"] = module.get("tables", [])
            modules[index] = merged
            data["moduleReports"] = modules
            return
    modules.append(module)
    data["moduleReports"] = modules


def enrich_growth_dynamics_from_wofost_csv(data: dict[str, Any]) -> None:
    meta = ensure_dict(data.get("meta"))
    subtype = first_text(meta.get("reportSubtype"))
    should_enrich = subtype == "plot_growth_dynamics" or subtype == OVERALL_REPORT_TYPE or meta.get("reportType") == "plot_overall_report"
    if not should_enrich:
        return
    rows = load_wofost_daily_csv()
    module = build_growth_dynamics_module(rows)
    if not module:
        return
    upsert_growth_dynamics_module(data, module)
    charts = ensure_dict(data.get("charts"))
    charts.setdefault("biomassTrend", [])
    if not ensure_list(charts.get("biomassTrend")):
        charts["biomassTrend"] = [
            {
                "label": row.get("label"),
                "tagp": row.get("tagp"),
                "twso": row.get("twso", row.get("wso")),
                "lai": row.get("lai"),
                "sm": row.get("soilMoisture"),
            }
            for row in ensure_list(module.get("trendSeries"))
        ]
    data["charts"] = charts


def clean_empty_values(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            child = clean_empty_values(item)
            if is_present(child):
                cleaned[key] = child
        return cleaned if cleaned else None
    if isinstance(value, list):
        cleaned_list = []
        for item in value:
            child = clean_empty_values(item)
            if is_present(child):
                cleaned_list.append(child)
        return cleaned_list if cleaned_list else None
    if isinstance(value, str):
        text = value.strip()
        return text if is_present(text) else None
    return value if is_present(value) else None


def clean_table(table: dict[str, Any]) -> dict[str, Any] | None:
    headers = [text_from_any(header) for header in ensure_list(table.get("headers")) if text_from_any(header)]
    rows = ensure_list(table.get("rows"))
    cleaned_rows: list[Any] = []
    for row in rows:
        cleaned = clean_empty_values(row)
        if is_present(cleaned):
            cleaned_rows.append(cleaned)
    if not cleaned_rows:
        return None
    result = dict(table)
    if headers:
        result["headers"] = headers
    result["rows"] = cleaned_rows
    return result


def clean_report_data(data: dict[str, Any]) -> dict[str, Any]:
    cleaned = clean_empty_values(data)
    result = cleaned if isinstance(cleaned, dict) else {}
    result["meta"] = ensure_dict(result.get("meta"))
    result["paper"] = ensure_dict(result.get("paper"))
    for key, default in REQUIRED_TOP_LEVEL_DEFAULTS.items():
        if key not in result:
            result[key] = default.copy() if isinstance(default, dict) else list(default)

    for module in ensure_list(result.get("moduleReports")):
        if not isinstance(module, dict):
            continue
        tables = []
        for table in ensure_list(module.get("tables")):
            if isinstance(table, dict):
                cleaned_table = clean_table(table)
                if cleaned_table:
                    tables.append(cleaned_table)
        if tables:
            module["tables"] = tables
        else:
            module.pop("tables", None)
    return result


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
    normalize_report_type_and_subtype(data)
    meta = ensure_dict(data.get("meta"))

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

    for key, default in REQUIRED_TOP_LEVEL_DEFAULTS.items():
        if isinstance(default, dict):
            if not isinstance(data.get(key), dict):
                data[key] = default.copy()
        elif not isinstance(data.get(key), list):
            data[key] = list(default)

    normalize_module_reports(data)
    enrich_growth_dynamics_from_wofost_csv(data)
    normalize_module_reports(data)
    normalize_paper(data)
    normalize_recommendations(data)
    data = clean_report_data(data)
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
