# -*- coding: utf-8 -*-
# @Time    : 2026/10/08 16:11
# @Author  : feidu
# @File    : survey_report.py
"""内部对话读取同一勘察报告，不要求plot_id或调用旧地块MCP。"""

import json
import sys

from survey_report_client import request_survey_report, get_report_evidence


def main() -> None:
    """以JSON明确区分受理、失败和报告完成，完成时返回现有展示协议。"""

    payload = json.load(sys.stdin)
    if payload.get("action") == "evidence":
        evidence = get_report_evidence(payload, payload["report_id"])
        snapshot = evidence["snapshot"]
        # 仅投影已冻结的值给模型，避免把大批矢量和HTML灌入对话。
        summary = {
            "report_id": evidence["report_id"],
            "survey_id": evidence["survey_id"],
            "snapshot_sha256": evidence["snapshot_sha256"],
            "name": snapshot["name"],
            "period": snapshot["period"],
            "as_of": snapshot.get("as_of"),
            "execution_policy": snapshot.get("execution_policy"),
            "remote_sensing": {
                "products": [
                    {
                        "business_date": item["business_date"],
                        "resolution_m": item["resolution_m"],
                        "composition_state": item["composition_state"],
                        "execution_mode": item["execution_mode"],
                        "ndvi": item.get("indices", {}).get("ndvi"),
                    }
                    for item in snapshot["r1"].get("products", [])
                ],
                "limitations": snapshot["r1"].get("limitations", []),
                "coverage": snapshot["r1"].get("coverage", []),
                "gaps": snapshot["r1"].get("gaps", []),
            },
            "crop_recognition": {
                key: snapshot["r2"].get(key)
                for key in (
                    "quality",
                    "class_summary",
                    "limitations",
                    "review_required",
                    "as_of",
                    "observation_context",
                )
            },
            "limitations": snapshot["limitations"],
        }
        summary["crop_recognition"]["model_version"] = (
            snapshot["r2"].get("model", {}).get("model_version")
        )
        summary["crop_recognition"]["candidates"] = [
            {
                key: f["properties"].get(key)
                for key in (
                    "instance_id",
                    "identification_status",
                    "predicted_crop_label",
                    "score",
                    "review_required",
                )
            }
            for f in snapshot["r2"].get("parcels", {}).get("features", [])
        ]
        analysis = evidence.get("analysis_evidence") or evidence.get(
            "monitoring_evidence"
        )
        if analysis:
            summary["analysis"] = {
                "status": analysis["status"],
                "source_scope": analysis.get("source_scope"),
                "sha256": analysis.get("sha256"),
                "scenario_start_date": analysis.get("sowing_date"),
                "growth_business_date": (analysis.get("growth") or {}).get(
                    "business_date"
                ),
                "risk_business_date": analysis.get("as_of"),
                "instruction": "气象、土壤、机理状态、异常与专项分析由服务端固定章节呈现，不重复改写；情景日期不是用户确认的播种事实。",
            }
        print(json.dumps(summary, ensure_ascii=False))
        return
    result = request_survey_report(payload)
    print(
        result["sono_report"]
        if result.get("sono_report")
        else json.dumps(result, ensure_ascii=False)
    )


if __name__ == "__main__":
    main()
