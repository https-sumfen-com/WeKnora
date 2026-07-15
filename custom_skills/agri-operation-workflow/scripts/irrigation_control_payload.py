# -*- coding: utf-8 -*-
"""Build deterministic irrigation form and execution payloads."""

from __future__ import annotations

import json
import math
import sys
from typing import Any


def _finite_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number):
        return None
    return int(number) if number.is_integer() else number


def _clean_number(value: int | float) -> int | float:
    number = float(value)
    return int(number) if number.is_integer() else number


def _positive_int(value: Any) -> int | None:
    number = _finite_number(value)
    if not isinstance(number, int) or number <= 0:
        return None
    return number


def analyze_sensors(payload: dict[str, Any]) -> dict[str, Any]:
    devices = payload.get("devices")
    if not isinstance(devices, list):
        return {"ok": False, "errors": ["devices must be a list"]}

    readings: list[dict[str, Any]] = []
    plot_device_ids: list[int] = []
    seen_ids: set[int] = set()

    for item in devices:
        if not isinstance(item, dict):
            continue
        plot_device_id = _positive_int(item.get("id"))
        if plot_device_id is None:
            continue
        device = item.get("device")
        if not isinstance(device, dict):
            continue
        device_data = device.get("device_data")
        if not isinstance(device_data, list):
            continue

        value: int | float | None = None
        for row in device_data:
            if not isinstance(row, dict) or row.get("key") != "SHUM":
                continue
            candidate = _finite_number(row.get("value"))
            if candidate is not None:
                value = candidate
                break
        if value is None:
            continue

        readings.append(
            {
                "plot_device_id": plot_device_id,
                "sensor_name": str(item.get("name") or device.get("name") or ""),
                "value": value,
            }
        )
        if plot_device_id not in seen_ids:
            seen_ids.add(plot_device_id)
            plot_device_ids.append(plot_device_id)

    average = (
        None
        if not readings
        else _clean_number(sum(row["value"] for row in readings) / len(readings))
    )
    return {
        "ok": True,
        "has_valid_shum": bool(readings),
        "sensor_readings": readings,
        "average_soil_moisture": average,
        "plot_device_ids": plot_device_ids,
        "plot_device_ids_csv": ",".join(map(str, plot_device_ids)),
    }


def _validated_valve_banks(value: Any) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(value, list):
        return [], ["valve_banks must be a list"]

    banks: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_ids: set[int] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"valve_banks[{index}] must be an object")
            continue

        bank_id = _positive_int(item.get("id"))
        title = item.get("title")
        valid_title = isinstance(title, str) and bool(title.strip())
        item_valid = True
        if bank_id is None:
            errors.append(f"valve_banks[{index}].id must be a positive integer")
            item_valid = False
        elif bank_id in seen_ids:
            errors.append(f"duplicate valve bank id: {bank_id}")
            item_valid = False
        else:
            seen_ids.add(bank_id)
        if not valid_title:
            errors.append(f"valve_banks[{index}].title is required")
            item_valid = False
        if "run_status" not in item:
            errors.append(f"valve_banks[{index}].run_status is required")
            item_valid = False

        if item_valid:
            banks.append(
                {
                    "id": bank_id,
                    "run_status": item["run_status"],
                    "title": title,
                }
            )
    return banks, errors


def _quoted(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _render_form_syntax(pending: dict[str, Any]) -> str:
    lines = [
        "form irrigation-valve-duration",
        "tag irrigation_valve_duration_confirm",
        f"cid {pending['cid']}",
        f"plot_id {pending['plot_id']}",
        f"plot_name {_quoted(pending['plot_name'])}",
        f"average_soil_moisture {pending['average_soil_moisture']}",
        f"reason {_quoted(pending['reason'])}",
        "valveBanks",
    ]
    for bank in pending["valve_banks"]:
        lines.extend(
            [
                f"  - valve_bank_id {bank['id']}",
                f"    title {_quoted(bank['title'])}",
                f"    run_status {_quoted(bank['run_status'])}",
                "    selected true",
                "    duration_minutes "
                f"{bank['recommended_duration_minutes']}",
            ]
        )
    return "\n".join(lines) + "\n"


def build_panel(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("valve_banks") == []:
        return {
            "ok": False,
            "errors": ["no valve banks returned"],
            "fallback_to_farming_operation": True,
        }
    if payload.get("irrigation_needed") is not True:
        return {
            "ok": False,
            "errors": ["irrigation_needed must be true"],
        }

    banks, errors = _validated_valve_banks(payload.get("valve_banks"))
    cid = _positive_int(payload.get("cid"))
    plot_id = _positive_int(payload.get("plot_id"))
    average = _finite_number(payload.get("average_soil_moisture"))
    reason = str(payload.get("reason") or "").strip()
    duration = _positive_int(payload.get("recommended_duration_minutes"))
    if cid is None:
        errors.append("cid must be a positive integer")
    if plot_id is None:
        errors.append("plot_id must be a positive integer")
    if average is None:
        errors.append("average_soil_moisture must be finite")
    if not reason:
        errors.append("reason is required")
    if duration is None:
        errors.append("recommended_duration_minutes must be a positive integer")
    if errors:
        return {"ok": False, "errors": errors}

    pending = {
        "cid": cid,
        "plot_id": plot_id,
        "plot_name": str(payload.get("plot_name") or "").strip(),
        "average_soil_moisture": average,
        "reason": reason,
        "valve_banks": [
            {**bank, "recommended_duration_minutes": duration} for bank in banks
        ],
    }
    return {
        "ok": True,
        "form_syntax": _render_form_syntax(pending),
        "pending_irrigation_draft": pending,
    }


def _pending_valve_index(
    pending: dict[str, Any],
) -> tuple[int | None, dict[int, dict[str, Any]] | None]:
    cid = _positive_int(pending.get("cid"))
    source_banks = pending.get("valve_banks")
    if cid is None or not isinstance(source_banks, list) or not source_banks:
        return None, None

    index: dict[int, dict[str, Any]] = {}
    for bank in source_banks:
        if not isinstance(bank, dict):
            return None, None
        bank_id = _positive_int(bank.get("id"))
        title = bank.get("title")
        if (
            bank_id is None
            or bank_id in index
            or not isinstance(title, str)
            or not title.strip()
        ):
            return None, None
        index[bank_id] = bank
    return cid, index


def prepare_execution(payload: dict[str, Any]) -> dict[str, Any]:
    pending = payload.get("pending_irrigation_draft")
    if not isinstance(pending, dict):
        return {"ok": False, "errors": ["pending_irrigation_draft is required"]}
    cid, source_by_id = _pending_valve_index(pending)
    if cid is None or source_by_id is None:
        return {"ok": False, "errors": ["pending irrigation draft is invalid"]}

    submitted = payload.get("submitted_form")
    if not isinstance(submitted, dict):
        return {"ok": False, "errors": ["submitted_form is required"]}
    expected_triple = {
        "type": "form_submit",
        "formType": "irrigation-valve-duration",
        "tag": "irrigation_valve_duration_confirm",
    }
    errors = [
        f"submitted_form.{key} must equal {_quoted(expected)}"
        for key, expected in expected_triple.items()
        if submitted.get(key) != expected
    ]
    submitted_banks = submitted.get("valveBanks")
    if not isinstance(submitted_banks, list):
        errors.append("submitted_form.valveBanks must be a list")
        return {"ok": False, "errors": errors}

    selected_banks: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for index, item in enumerate(submitted_banks):
        if not isinstance(item, dict):
            errors.append(f"submitted valveBanks[{index}] must be an object")
            continue
        bank_id = _positive_int(item.get("valve_bank_id"))
        if bank_id is None:
            errors.append(
                f"valve_bank_id must be a positive integer at index {index}"
            )
            continue
        if bank_id in seen_ids:
            errors.append(f"duplicate valve_bank_id: {bank_id}")
            continue
        seen_ids.add(bank_id)
        source = source_by_id.get(bank_id)
        if source is None:
            errors.append(f"unknown valve_bank_id: {bank_id}")
            continue

        selected = item.get("selected")
        if not isinstance(selected, bool):
            errors.append(f"selected must be boolean for valve_bank_id: {bank_id}")
            continue
        duration = _positive_int(item.get("duration_minutes"))
        if duration is None:
            errors.append(
                "duration_minutes must be a positive integer for "
                f"valve_bank_id: {bank_id}"
            )
            continue
        if selected:
            selected_banks.append(
                {
                    "id": bank_id,
                    "title": source["title"],
                    "duration_minutes": duration,
                }
            )

    if not selected_banks:
        errors.append("at least one valve bank must be selected")
    if errors:
        return {"ok": False, "errors": errors}

    execution_draft = {
        "cid": cid,
        "plot_id": pending.get("plot_id"),
        "plot_name": pending.get("plot_name", ""),
        "valve_banks": selected_banks,
    }
    details = "；".join(
        f"{bank['title']} {bank['duration_minutes']} 分钟" for bank in selected_banks
    )
    confirmation_text = f"即将执行灌溉：{details}。请确认是否执行。"
    return {
        "ok": True,
        "requires_execution_confirmation": True,
        "confirmation_text": confirmation_text,
        "execution_draft": execution_draft,
        "pending_execution_draft": execution_draft,
    }


def build_execution(payload: dict[str, Any]) -> dict[str, Any]:
    confirmed = (
        payload.get("execution_confirmed") is True
        and payload.get("draft_was_shown_to_user") is True
        and payload.get("confirmation_source")
        == "user_confirmed_irrigation_execution_draft"
    )
    if not confirmed:
        return {
            "ok": False,
            "errors": [
                "irrigation execution requires a separate confirmation after "
                "the draft is shown"
            ],
            "requires_execution_confirmation": True,
        }

    draft = payload.get("pending_execution_draft")
    if not isinstance(draft, dict):
        return {"ok": False, "errors": ["pending_execution_draft is required"]}
    cid = _positive_int(draft.get("cid"))
    selected = draft.get("valve_banks")
    if cid is None or not isinstance(selected, list) or not selected:
        return {"ok": False, "errors": ["pending execution draft is invalid"]}

    args: list[dict[str, int]] = []
    seen_ids: set[int] = set()
    for bank in selected:
        bank_id = _positive_int(bank.get("id")) if isinstance(bank, dict) else None
        duration = (
            _positive_int(bank.get("duration_minutes"))
            if isinstance(bank, dict)
            else None
        )
        if bank_id is None or duration is None or bank_id in seen_ids:
            return {
                "ok": False,
                "errors": ["pending execution valve is invalid"],
            }
        seen_ids.add(bank_id)
        args.append({"cid": cid, "id": bank_id, "auto_off_minutes": duration})
    return {"ok": True, "start_valve_bank_args": args}


COMMANDS = {
    "analyze-sensors": analyze_sensors,
    "build-panel": build_panel,
    "prepare-execution": prepare_execution,
    "build-execution": build_execution,
}


def _read_stdin_json() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("input JSON must be an object")
    return data


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in COMMANDS:
        print(
            "usage: irrigation_control_payload.py "
            "{analyze-sensors|build-panel|prepare-execution|build-execution}",
            file=sys.stderr,
        )
        return 2
    try:
        result = COMMANDS[argv[1]](_read_stdin_json())
    except Exception as exc:  # noqa: BLE001 - CLI always emits structured errors.
        result = {"ok": False, "errors": [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
