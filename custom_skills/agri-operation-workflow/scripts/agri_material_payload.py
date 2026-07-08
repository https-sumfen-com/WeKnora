# -*- coding: utf-8 -*-
"""Build and validate agri material payloads for SONO farming records.

Commands read JSON from stdin and write JSON to stdout:
  build-panel   -> agri-material-usage Syntax + selected original rows
  build-submit  -> submit-ready add_farming_record input
"""

from __future__ import annotations

import copy
import json
import re
import sys
from datetime import datetime
from typing import Any


FERTILIZER_OP = ("施肥", "追肥", "基肥", "补肥", "营养")
FERTILIZER_MATERIAL = (
    "肥",
    "化肥",
    "有机肥",
    "复合肥",
    "氮",
    "磷",
    "钾",
    "尿素",
    "nitrogen",
    "phosphorus",
    "potassium",
    "fertilizer",
)
HERBICIDE_OP = ("除草", "草害")
HERBICIDE_MATERIAL = ("除草", "除草剂", "herbicide")
PESTICIDE_OP = ("用药", "植保", "病害", "虫害", "防治", "杀菌", "杀虫")
PESTICIDE_MATERIAL = (
    "农药",
    "药剂",
    "杀菌",
    "杀菌剂",
    "杀虫",
    "杀虫剂",
    "植保",
    "pesticide",
    "fungicide",
    "insecticide",
)
SEED_OP = ("播种", "补种")
SEED_MATERIAL = ("种子", "种衣", "包衣", "seed")


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _lower_text(value: Any) -> str:
    return _text(value).strip().lower()


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    lower = _lower_text(text)
    return any(_lower_text(needle) in lower for needle in needles)


def _stock_goods(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("stock_goods")
    return value if isinstance(value, dict) else {}


def _row_name(row: dict[str, Any]) -> str:
    goods = _stock_goods(row)
    return _text(goods.get("name") or row.get("name")).strip()


def _row_type_and_name(row: dict[str, Any]) -> str:
    goods = _stock_goods(row)
    return " ".join(
        part
        for part in (
            _text(goods.get("type")),
            _text(goods.get("name")),
            _text(row.get("name")),
        )
        if part
    )


def _operation_category(operation_name: str) -> str | None:
    if _contains_any(operation_name, FERTILIZER_OP):
        return "fertilizer"
    if _contains_any(operation_name, HERBICIDE_OP):
        return "herbicide"
    if _contains_any(operation_name, PESTICIDE_OP):
        return "pesticide"
    if _contains_any(operation_name, SEED_OP):
        return "seed"
    return None


def _row_matches_category(row: dict[str, Any], category: str | None) -> bool:
    if category is None:
        return False
    text = _row_type_and_name(row)
    if category == "fertilizer":
        return _contains_any(text, FERTILIZER_MATERIAL)
    if category == "herbicide":
        return _contains_any(text, HERBICIDE_MATERIAL)
    if category == "pesticide":
        return _contains_any(text, PESTICIDE_MATERIAL)
    if category == "seed":
        return _contains_any(text, SEED_MATERIAL)
    return False


def _to_number(value: Any, default: float = 0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean_number(value: Any) -> int | float:
    number = round(_to_number(value), 6)
    if number.is_integer():
        return int(number)
    return number


def _record_area(payload: dict[str, Any]) -> float:
    return _to_number(_record_draft(payload).get("area"))


def _total_num_from_per_mu(per_mu: Any, area: float) -> int | float:
    if area <= 0:
        return 0
    return _clean_number(_to_number(per_mu) * area)


def _dosage_from_total_num(total_num: Any, area: float) -> int | float:
    if area <= 0:
        return 0
    return _clean_number(_to_number(total_num) / area * 1000)


def _has_required_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return False
        try:
            return float(stripped) != 0
        except ValueError:
            return True
    if isinstance(value, (int, float)):
        return value != 0
    return True


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _id_key(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _usage_for_row(row: dict[str, Any], payload: dict[str, Any]) -> int | float:
    usage_by_record = payload.get("usage_by_stock_record_id") or {}
    usage_by_goods = payload.get("usage_by_stock_goods_id") or {}
    usage_by_name = payload.get("usage_by_goods_name") or {}
    goods = _stock_goods(row)
    row_id = _id_key(row.get("id"))
    goods_id = _id_key(goods.get("id"))
    name = _row_name(row)

    if row_id and row_id in usage_by_record:
        return _clean_number(usage_by_record[row_id])
    if goods_id and goods_id in usage_by_goods:
        return _clean_number(usage_by_goods[goods_id])
    if name and name in usage_by_name:
        return _clean_number(usage_by_name[name])
    if "default_per_mu_rate" in payload:
        return _clean_number(payload.get("default_per_mu_rate"))
    # Backward compatibility for older saved draft inputs. New skill docs use
    # default_per_mu_rate and frontend-facing num/dosage.
    if "default_mu_usage" in payload:
        return _clean_number(payload.get("default_mu_usage"))
    return 0


def _panel_item(row: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any] | None:
    goods = _stock_goods(row)
    name = _row_name(row)
    goods_id = goods.get("id")
    if not name or goods_id in (None, "", 0):
        return None

    area = _record_area(payload)
    per_mu_usage = _usage_for_row(row, payload)
    total_num = _total_num_from_per_mu(per_mu_usage, area)
    item: dict[str, Any] = {
        "goods_name": name,
        "stock_goods_id": goods_id,
        "is_formula": 0,
        "num": total_num,
        "price": _clean_number(row.get("price", goods.get("price", 0))),
        "unit": _text(goods.get("unit")),
        "dosage": _dosage_from_total_num(total_num, area),
    }
    if row.get("id") not in (None, ""):
        item["stock_record_id"] = row.get("id")
    return item


def _syntax_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(_clean_number(value))

    text = _text(value)
    if text == "" or any(char.isspace() for char in text) or '"' in text:
        return json.dumps(text, ensure_ascii=False)
    return text


def _render_form_syntax(
    title: Any, auto_open: Any, goods_list: list[dict[str, Any]]
) -> str:
    lines = [
        "form agri-material-usage",
        f"title {_syntax_value(title or '补全信息')}",
        f"autoOpen {_syntax_value(bool(auto_open))}",
        "data",
    ]
    field_order = (
        "goods_name",
        "stock_goods_id",
        "is_formula",
        "num",
        "price",
        "unit",
        "dosage",
        "stock_record_id",
    )
    for item in goods_list:
        first = True
        for field in field_order:
            if field not in item:
                continue
            prefix = "  - " if first else "    "
            lines.append(f"{prefix}{field} {_syntax_value(item[field])}")
            first = False
    return "\n".join(lines) + "\n"


def build_panel(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("inventory_rows") or []
    if not isinstance(rows, list):
        return {"ok": False, "errors": ["inventory_rows must be an array"]}

    category = _operation_category(_text(payload.get("operation_name")))
    selected_rows: list[dict[str, Any]] = []
    goods_list: list[dict[str, Any]] = []
    limit = int(payload.get("limit") or 8)

    for row in rows:
        if not isinstance(row, dict):
            continue
        if not _row_matches_category(row, category):
            continue
        item = _panel_item(row, payload)
        if item is None:
            continue
        selected_rows.append(copy.deepcopy(row))
        goods_list.append(item)
        if len(goods_list) >= limit:
            break

    pending_draft = {
        "record_draft": copy.deepcopy(_record_draft(payload)),
        "selected_inventory_rows": copy.deepcopy(selected_rows),
    }
    title = payload.get("title") or "补全信息"
    auto_open = payload.get("autoOpen", False)

    return {
        "ok": True,
        "operation_category": category,
        "form_syntax": _render_form_syntax(title, auto_open, goods_list),
        "selected_inventory_rows": selected_rows,
        "pending_draft": pending_draft,
    }


def _normalize_name(value: Any) -> str:
    return "".join(_lower_text(value).split())


def _index_rows(rows: list[Any]) -> dict[str, dict[str, dict[str, Any]]]:
    index: dict[str, dict[str, dict[str, Any]]] = {
        "record": {},
        "goods": {},
        "name": {},
    }
    for row in rows:
        if not isinstance(row, dict):
            continue
        goods = _stock_goods(row)
        row_id = _id_key(row.get("id"))
        goods_id = _id_key(goods.get("id"))
        name = _normalize_name(_row_name(row))
        if row_id:
            index["record"][row_id] = row
        if goods_id and goods_id not in index["goods"]:
            index["goods"][goods_id] = row
        if name and name not in index["name"]:
            index["name"][name] = row
    return index


def _match_original(
    submitted: dict[str, Any], index: dict[str, dict[str, dict[str, Any]]]
) -> dict[str, Any] | None:
    record_id = _id_key(submitted.get("stock_record_id"))
    goods_id = _id_key(submitted.get("stock_goods_id"))
    name = _normalize_name(submitted.get("goods_name"))
    if record_id and record_id in index["record"]:
        return index["record"][record_id]
    if goods_id and goods_id in index["goods"]:
        return index["goods"][goods_id]
    if name and name in index["name"]:
        return index["name"][name]
    return None


def _confirmed_quantity(submitted: dict[str, Any], area: float) -> int | float:
    for key in ("num", "change_num"):
        if key in submitted:
            return _clean_number(submitted.get(key))
    if "mu_usage" in submitted and area > 0:
        return _clean_number(_to_number(submitted.get("mu_usage")) * area)
    if "mu_usage" in submitted:
        return _clean_number(submitted.get("mu_usage"))
    return 0


def _row_price(row: dict[str, Any]) -> Any:
    goods = _stock_goods(row)
    if row.get("price") not in (None, ""):
        return row.get("price")
    return goods.get("price", 0)


def _submitted_value(submitted: dict[str, Any], key: str) -> Any:
    if key not in submitted:
        return None
    value = submitted.get(key)
    if value == "":
        return None
    return value


def _frontend_submit_item(
    submitted: dict[str, Any], original: dict[str, Any], area: float
) -> dict[str, Any]:
    goods = _stock_goods(original)
    total_num = _confirmed_quantity(submitted, area)
    goods_name = _text(submitted.get("goods_name")).strip() or _row_name(original)
    stock_goods_id = submitted.get("stock_goods_id")
    if not _has_required_value(stock_goods_id):
        stock_goods_id = goods.get("id")
    price = _submitted_value(submitted, "price")
    if price is None:
        price = _row_price(original)
    unit = _text(submitted.get("unit")).strip()
    if "unit" not in submitted or submitted.get("unit") is None:
        unit = _text(goods.get("unit")).strip()
    return {
        "goods_name": goods_name,
        "stock_goods_id": _clean_number(stock_goods_id),
        "is_formula": _clean_number(submitted.get("is_formula", 0)),
        "num": total_num,
        "price": _clean_number(price),
        "unit": unit,
        "dosage": _dosage_from_total_num(total_num, area),
    }


def _merged_submit_item(
    original: dict[str, Any],
    submitted: dict[str, Any],
    allow_price_override: bool,
    area: float,
) -> dict[str, Any]:
    return _frontend_submit_item(submitted, original, area)


def _pending_draft(payload: dict[str, Any]) -> dict[str, Any]:
    return _dict_or_empty(payload.get("pending_draft"))


def _record_draft(payload: dict[str, Any]) -> dict[str, Any]:
    pending = _pending_draft(payload)
    return copy.deepcopy(
        _dict_or_empty(payload.get("record_draft"))
        or _dict_or_empty(pending.get("record_draft"))
        or _dict_or_empty(payload.get("add_farming_record_draft"))
    )


def _system_params(payload: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(_dict_or_empty(payload.get("system_params")))


def _submitted_goods_list(payload: dict[str, Any]) -> Any:
    submitted_form = _dict_or_empty(payload.get("submitted_form"))
    if "submitted_goodsList" in payload:
        return payload.get("submitted_goodsList")
    if "goodsList" in payload:
        return payload.get("goodsList")
    if "goodsList" in submitted_form:
        return submitted_form.get("goodsList")
    return []


def _is_confirmed_value(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return _lower_text(value) in {
            "1",
            "true",
            "yes",
            "confirmed",
            "confirm",
            "确认",
            "已确认",
            "用户已确认",
        }
    return False


def _submitted_form_confirms_materials(payload: dict[str, Any]) -> bool:
    submitted_form = _dict_or_empty(payload.get("submitted_form"))
    return (
        _lower_text(submitted_form.get("type")) == "form_submit"
        and _lower_text(submitted_form.get("formType")) == "agri-material-usage"
        and _lower_text(submitted_form.get("tag")) == "agri_material_usage_confirm"
    )


def _no_material_draft_review_confirmed(payload: dict[str, Any]) -> bool:
    confirmation_source = _lower_text(payload.get("confirmation_source"))
    return _is_confirmed_value(payload.get("draft_was_shown_to_user")) and confirmation_source in {
        "user_confirmed_prepared_draft",
        "user_confirmed_prepared_record_draft",
    }


def _record_creation_confirmation_error(
    payload: dict[str, Any], submitted: list[Any]
) -> str | None:
    if _submitted_form_confirms_materials(payload):
        return None

    if _is_confirmed_value(payload.get("record_creation_confirmed")):
        confirmed = True
    else:
        confirmed = _is_confirmed_value(payload.get("user_confirmed_record_creation"))

    if not confirmed:
        return "record_creation_confirmed is required before add_farming_record"

    if submitted:
        return None

    if _no_material_draft_review_confirmed(payload):
        return None

    return (
        "no-material record creation requires a separate user confirmation "
        "after the draft is shown"
    )


def _original_inventory_rows(payload: dict[str, Any]) -> Any:
    pending = _pending_draft(payload)
    if "original_inventory_rows" in payload:
        return payload.get("original_inventory_rows")
    if "selected_inventory_rows" in payload:
        return payload.get("selected_inventory_rows")
    if "selected_inventory_rows" in pending:
        return pending.get("selected_inventory_rows")
    return []


def _set_from_system(
    args: dict[str, Any],
    args_key: str,
    system_params: dict[str, Any],
    system_key: str,
) -> None:
    if _has_required_value(args.get(args_key)):
        return
    value = system_params.get(system_key)
    if _has_required_value(value):
        args[args_key] = value


def _current_minute_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _normalize_operate_time(value: Any) -> str:
    text = _text(value).strip()
    now_minute = datetime.now().strftime("%H:%M")
    if not text:
        return _current_minute_time()

    date_only = re.fullmatch(r"(\d{4}-\d{2}-\d{2})", text)
    if date_only:
        return f"{date_only.group(1)} {now_minute}"

    minute = re.match(r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})", text)
    if minute:
        return f"{minute.group(1)} {minute.group(2)}"

    return text


def _build_record_args(
    payload: dict[str, Any], rebuilt_goods_list: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[str]]:
    record_draft = _record_draft(payload)
    system_params = _system_params(payload)
    args = copy.deepcopy(record_draft)

    for key in (
        "token",
        "cname",
        "terminal_id",
        "entity_info_id",
        "submitted_goodsList",
        "original_inventory_rows",
        "selected_inventory_rows",
        "pending_draft",
    ):
        args.pop(key, None)

    _set_from_system(args, "cid", system_params, "cid")
    _set_from_system(args, "work_user", system_params, "user_id")
    _set_from_system(args, "tgzn_user_id", system_params, "user_id")
    _set_from_system(args, "tgzn_entity_id", system_params, "entity_id")
    _set_from_system(args, "tgzn_dept_id", system_params, "dept_id")

    args["operate_time"] = _normalize_operate_time(args.get("operate_time"))

    if not _has_required_value(args.get("tgzn_dept_id")):
        args.pop("tgzn_dept_id", None)

    args["goodsList"] = rebuilt_goods_list

    required_fields = payload.get("required_fields") or [
        "cid",
        "base_id",
        "plot_id",
        "matter_id",
        "operate_time",
        "work_user",
    ]
    missing = [
        field
        for field in required_fields
        if not _has_required_value(args.get(field))
    ]
    return args, missing


def build_submit(payload: dict[str, Any]) -> dict[str, Any]:
    submitted = _submitted_goods_list(payload)
    originals = _original_inventory_rows(payload)
    if not isinstance(submitted, list):
        return {"ok": False, "errors": ["submitted_goodsList must be an array"]}
    if not isinstance(originals, list):
        return {"ok": False, "errors": ["original_inventory_rows must be an array"]}
    if not _record_draft(payload):
        return {"ok": False, "errors": ["record_draft is required"]}

    index = _index_rows(originals)
    errors: list[str] = []
    rebuilt: list[dict[str, Any]] = []
    allow_price_override = bool(payload.get("allow_price_override"))
    area = _record_area(payload)

    for item in submitted:
        if not isinstance(item, dict):
            errors.append("submitted goods item must be an object")
            continue
        original = _match_original(item, index)
        if original is None:
            label = item.get("stock_record_id") or item.get("stock_goods_id") or item.get("goods_name")
            errors.append(f"cannot match original inventory row for {label}")
            continue
        rebuilt.append(_merged_submit_item(original, item, allow_price_override, area))

    if errors:
        return {"ok": False, "errors": errors}
    if submitted and area <= 0:
        return {
            "ok": False,
            "errors": ["missing required record field: area"],
            "missing_fields": ["area"],
        }

    record_args, missing = _build_record_args(payload, rebuilt)
    if missing:
        return {
            "ok": False,
            "errors": [
                f"missing required record field: {field}" for field in missing
            ],
            "missing_fields": missing,
        }
    confirmation_error = _record_creation_confirmation_error(payload, submitted)
    if confirmation_error:
        return {
            "ok": False,
            "errors": [confirmation_error],
            "requires_user_confirmation": True,
            "confirmation_prompt": "请确认是否创建该农事记录。",
        }
    return {
        "ok": True,
        "goodsList": rebuilt,
        "add_farming_record_args": record_args,
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
    if len(argv) != 2 or argv[1] not in {"build-panel", "build-submit"}:
        print(
            "usage: agri_material_payload.py {build-panel|build-submit}",
            file=sys.stderr,
        )
        return 2

    try:
        payload = _read_stdin_json()
        if argv[1] == "build-panel":
            result = build_panel(payload)
        else:
            result = build_submit(payload)
    except Exception as exc:  # noqa: BLE001 - CLI should return structured errors.
        result = {"ok": False, "errors": [str(exc)]}

    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
