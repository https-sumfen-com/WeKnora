# -*- coding: utf-8 -*-
# @Time    : 2026/10/08 16:11
# @Author  : feidu
# @File    : survey_report_client.py
"""两个报告Skill共用的勘察API适配器，不计算或改写科学指标。"""

import json
import os
from pathlib import Path
from typing import Any
from urllib import error, request
from uuid import UUID

DEFAULT_API_BASE_URL = "https://api.sumfen.com/mlgrowth"
_BUSINESS_API_KEY_FILE = Path("/app/config/credentials/mlgrowth-survey-api-key")


def _business_key() -> str:
    """优先使用受控环境；本地沙箱过滤环境时读取固定只读凭据挂载。"""

    key = os.environ.get("MLGROWTH_BUSINESS_API_KEY")
    if not key:
        try:
            key = _BUSINESS_API_KEY_FILE.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            key = None
    if not key:
        raise ValueError("MLGrowth business API access is not configured")
    return key


def _headers(payload: dict[str, Any]) -> dict[str, str]:
    """业务密钥仅取服务端环境，不接受模型输入中的密钥。"""

    key = _business_key()
    return {"Content-Type": "application/json", "X-MLGrowth-Business-Key": key}


def _scope(payload: dict[str, Any]) -> dict[str, int]:
    """将会话旧字段映射到统一请求字段，不让模型输入覆盖服务端密钥。"""
    values = {
        "company_id": payload.get("company_id", payload.get("cid")),
        "entity_id": payload.get("entity_id", payload.get("entity-id")),
        "entity_info_id": payload.get("entity_info_id", payload.get("entity-info-id")),
    }
    if any(value is None for value in values.values()):
        raise ValueError("company_id, entity_id and entity_info_id are required")
    return {name: int(value) for name, value in values.items()}



def api_json(
    payload: dict[str, Any], method: str, path: str, body: dict | None = None
) -> dict:
    """只访问配置的勘察API，错误不回显密钥或远端敏感响应。"""

    base = os.environ.get("MLGROWTH_SURVEY_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip(
        "/"
    )
    data = (
        None
        if body is None
        else json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
    )
    operation = request.Request(
        base + path, data=data, headers=_headers(payload), method=method
    )
    try:
        with request.urlopen(operation, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise ValueError("Field survey API returned HTTP %s" % exc.code) from exc
    if not isinstance(result, dict):
        raise ValueError("Field survey API returned invalid JSON")
    return result


def request_survey_report(payload: dict[str, Any]) -> dict:
    """区域首次创建或按survey_id读取；计算未完成时明确返回受理状态。"""

    report_type = payload.get("report_type", "field_survey")
    if report_type not in {"field_survey", "r1", "r2"}:
        raise ValueError("Unsupported field survey report type")
    if payload.get("survey_id"):
        survey_id = str(UUID(str(payload["survey_id"])))
        survey = api_json(payload, "GET", "/api/v1/field-surveys/%s" % survey_id)
    else:
        body = {
            "geometry": payload["geometry"], **_scope(payload),
            "name": payload.get("name") or payload.get("plot_name") or "区域勘察",
            "provider_name": payload.get("provider_name") or "区域勘察",
            "site_id": int(payload.get("site_id", 0)),
        }
        survey = api_json(payload, "POST", "/api/v1/field-surveys", body)
        survey_id = survey["survey_id"]
    # 三种标题都使用完整冻结快照，必须等待环境与专项分析检查点完成。
    ready = survey["status"] == "completed" and survey.get("analysis_ready", False)
    if not ready:
        return {
            "ok": survey["status"] != "failed",
            "status": survey["status"],
            "survey_id": survey_id,
            "r1_ready": survey["r1_ready"],
            "r2_ready": survey["r2_ready"],
            "analysis_ready": survey.get("analysis_ready", False),
            "progress_percent": survey.get("progress_percent"),
            "progress_stage": survey.get("progress_stage"),
            "progress_detail": survey.get("progress_detail"),
            "history_ready": survey.get("history_ready", False),
            "history_completed_years": survey.get("history_completed_years", 0),
            "report_url": None,
            "error_message": survey.get("error_message"),
        }
    report = api_json(
        payload,
        "POST",
        "/api/v1/field-surveys/%s/reports" % survey_id,
        {"report_type": report_type},
    )
    return {
        "ok": True,
        "status": "completed",
        **report,
        "sono_report": "<sono-report>%s</sono-report>" % report["report_url"],
    }


def get_report_evidence(payload: dict[str, Any], report_id: str) -> dict:
    """按固定报告ID取冻结快照与同源HTML，整体报告不另写科学渲染逻辑。"""

    path = "/api/v1/field-survey-reports/%s/data" % UUID(report_id)
    return api_json(payload, "GET", path)


def append_survey_evidence(html: str, evidence: dict[str, Any]) -> str:
    """服务端章节进入既有结果正文插槽；禁止在body末尾追加另一张报告。"""

    fragment = evidence["html_fragment"]
    slot = "<!-- SONO_CANONICAL_RESULTS -->"
    if html.count(slot) != 1 or 'class="survey-report"' not in fragment:
        raise ValueError("Report HTML or field survey fragment is invalid")
    return html.replace(slot, fragment + evidence.get("monitoring_html_fragment", ""))
