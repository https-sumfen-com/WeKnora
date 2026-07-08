# Submit-Ready goodsList

Read this reference before calling `add_farming_record`.

Prefer `scripts/agri_material_payload.py build-submit`. Hand-merge only when script execution is unavailable.

## Final Item Contract

Each submit-ready item must contain only these fields:

```json
{
  "goods_name": "高钾肥",
  "stock_goods_id": 5,
  "is_formula": 0,
  "num": 2.65,
  "price": 12.8,
  "unit": "",
  "dosage": 1000
}
```

Field source:

- `goods_name`: frontend submitted value; if missing, use the matched `get_agri_input_list` row name.
- `stock_goods_id`: frontend submitted value; if missing, use matched `stock_goods.id`.
- `is_formula`: frontend submitted value, default `0`.
- `num`: frontend submitted total material quantity.
- `price`: frontend submitted material price; if missing, use matched inventory/material price.
- `unit`: frontend submitted material unit; if not provided, use matched material unit or `""`.
- `dosage`: computed by script as `num / record_draft.area * 1000`.

Do not include `stock_record_id`, `mu_usage`, `change_num`, `inventory_num`, `stock_goods`, raw inventory `id`, raw inventory `name`, or raw inventory `num` in the final submit-ready item.

## Required Flow

1. When building the panel, run `scripts/agri_material_payload.py build-panel` and keep the whole script-produced `pending_draft`.
2. `pending_draft` must contain both the current `record_draft` and original selected `get_agri_input_list` rows.
3. When the user submits, pass the submitted list plus `pending_draft` into `scripts/agri_material_payload.py build-submit`.
4. The script matches submitted materials to original inventory rows by `stock_record_id`, then `stock_goods_id`, then normalized name.
5. Matching validates MCP grounding and provides fallback metadata for missing `goods_name`, `stock_goods_id`, `price`, or `unit`. The final `num` still comes from the frontend submitted item, and `dosage` is computed.
6. If `record_draft.area` is missing or zero, do not call `add_farming_record`; area is required to compute `dosage`.
7. `build-submit` must receive either the validated material confirmation `submitted_form` or `record_creation_confirmed: true` before it can return `add_farming_record_args`.
8. If the script returns `requires_user_confirmation`, ask the user to confirm creating the farming record and do not call `add_farming_record`.
9. Send script-produced `add_farming_record_args` directly to `add_farming_record`.

For no-material operations, `record_creation_confirmed: true` is not enough by itself. The operation-order message and the final record-creation confirmation must be two separate user turns. Never call `add_farming_record`, `build-submit`, or any MCP creation tool in the same assistant turn that receives the user's operation order. Only after the draft has been shown and the user confirms it in a later turn may `build-submit` include `draft_was_shown_to_user: true` and `confirmation_source: "user_confirmed_prepared_draft"`.

## Missing Draft Recovery

If original inventory rows are not in the conversation/backend draft:

1. Call `get_agri_input_list` again with the same `cid + base_id`.
2. Rematch submitted items by `stock_record_id`, then `stock_goods_id`, then exact/normalized material name.
3. If a submitted material still cannot be matched, do not call `add_farming_record`; ask the user to reselect the material so the system can recover the upstream inventory row.

If `record_draft` itself is missing, do not reconstruct it from `goodsList`. Recover the earlier draft from conversation/backend state or ask for the missing operation, plot, base, time, and area fields.

## Forbidden

- Do not submit raw inventory rows to `add_farming_record`.
- Do not copy inventory balance `num` into the final `num`.
- Do not use matched inventory metadata to overwrite frontend-provided values.
- Do not calculate `dosage` from stock balance, package specification, price, or model knowledge.
- Do not pass `token`, `terminal_id`, `cname`, or `entity_info_id` into `add_farming_record`.
- Do not manually combine `goodsList` with stale or partial record fields after `build-submit`; use `add_farming_record_args`.
- Do not call `add_farming_record` from a complete no-material draft unless the user has confirmed record creation in a later turn and `build-submit` was run with `record_creation_confirmed: true`, `draft_was_shown_to_user: true`, and `confirmation_source: "user_confirmed_prepared_draft"`.

## Example

Submitted UI item:

```json
{
  "goods_name": "高钾肥",
  "stock_goods_id": 5,
  "stock_record_id": 29,
  "is_formula": 0,
  "num": 2.65,
  "price": 12.8,
  "unit": ""
}
```

With `record_draft.area = 2.65`, submit-ready item:

```json
{
  "goods_name": "高钾肥",
  "stock_goods_id": 5,
  "is_formula": 0,
  "num": 2.65,
  "price": 12.8,
  "unit": "",
  "dosage": 1000
}
```
