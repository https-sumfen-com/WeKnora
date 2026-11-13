# -*- coding: utf-8 -*-
# @Time    : 2026/10/8 21:13
# @Author  : feidu
# @File    : survey_report_binding.py
"""整体报告与勘察证据的固定关联，防止对话重试遗漏勘察参数。"""

import json
from pathlib import Path
import re
from typing import Any
from uuid import UUID


def _binding_path(output_dir: Path, report_no: str) -> Path:
    if re.fullmatch(r"[0-9a-f]{32}", report_no) is None:
        raise ValueError(
            "Report number must contain 32 lowercase hexadecimal characters"
        )
    return output_dir / ".survey-bindings" / (report_no + ".json")


def save_binding(output_dir: Path, report_no: str, values: dict[str, str]) -> None:
    """请求后端前写入不可重绑定的关联；不保存凭据或科学数值。"""

    path = _binding_path(output_dir, report_no)
    binding = {
        key: str(values[key])
        for key in (
            "survey_report_id",
            "survey_snapshot_sha256",
            "cid",
            "entity-id",
            "entity-info-id",
        )
    }
    binding["survey_report_id"] = str(UUID(binding["survey_report_id"]))
    if values.get("plot_id"):
        binding["plot_id"] = str(int(values["plot_id"]))
    if re.fullmatch(r"[0-9a-f]{64}", binding["survey_snapshot_sha256"]) is None:
        raise ValueError("Survey snapshot SHA-256 is invalid")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(binding, stream, ensure_ascii=False)


def load_binding(output_dir: Path, report_no: str) -> dict[str, str] | None:
    """兼容没有勘察关联的旧整体报告；存在的关联不能被参数覆盖。"""

    if not report_no:
        return None
    path = _binding_path(output_dir, report_no)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def validate_binding(binding: dict[str, str], report_id: str, scope: dict) -> str:
    for key in ("cid", "entity-id", "entity-info-id"):
        if str(scope[key]) != binding[key]:
            raise ValueError("Report scope differs from its fixed survey binding")
    if report_id and str(UUID(report_id)) != binding["survey_report_id"]:
        raise ValueError("Survey report differs from its fixed report binding")
    if binding.get("plot_id") and str(scope.get("plot_id")) != binding["plot_id"]:
        raise ValueError("Plot differs from its fixed report binding")
    return binding["survey_report_id"]


def require_canonical_survey_section(data: dict[str, Any]) -> None:
    """科学结论仅由固定章节渲染；主题关键词不属于科学断言。"""

    def texts(value: Any):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for child in value.values():
                yield from texts(child)
        elif isinstance(value, list):
            for child in value:
                yield from texts(child)

    for key, value in data.items():
        if key in {"meta", "surveyEvidence"}:
            continue
        if key == "paper" and isinstance(value, dict):
            # 关键词只是索引标签；正文中的勘察结论仍须通过原有拦截。
            value = {name: item for name, item in value.items() if name != "keywords"}
        if any(
            re.search(r"\bR[12]\b|勘察", item, re.IGNORECASE) for item in texts(value)
        ):
            raise ValueError(
                "R1/R2 content must appear only in the canonical survey section; "
                "remove survey claims from model-authored report fields"
            )
