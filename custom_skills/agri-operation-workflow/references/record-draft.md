# Farming Record Draft Lifecycle

Read this reference before preparing or submitting `add_farming_record`.

## Draft Sources

Build the draft only from:

- server/session/gateway context
- current page route or locked base/plot context
- SONO-MCP tool results
- explicit user input
- the user's submitted material `goodsList`
- the original `get_agri_input_list` inventory rows selected for the material Syntax
- the script-produced `pending_draft` from `scripts/agri_material_payload.py build-panel`

Do not infer missing IDs, area, operator, address, inventory, price, unit, or total material quantity from model knowledge. If `operate_time` is missing, use current local time to the minute. If `operate_time` is date-only (`YYYY-MM-DD`), preserve that date and append the current `HH:mm`; if it includes seconds, submit only to minute precision. Model agronomic experience may be used only to recommend the internal per-mu rate before converting it to editable frontend `num`.

## Required Draft Fields

Before calling `add_farming_record`, verify:

- company identity: `cid` or `tgzn_entity_id`
- target identity: `base_id` and `plot_id` when the operation is plot-bound
- operation identity: `matter_id`
- operation time: explicit `operate_time`; if missing, default to current local time formatted to minutes (`YYYY-MM-DD HH:mm`); date-only values must be expanded to `YYYY-MM-DD HH:mm`
- operator: default to `user_id` when present; send it as `work_user` and also as `tgzn_user_id` when required by upstream
- materials: submit-ready `goodsList` with compact script-produced fields when the operation uses agricultural materials
- area: required when materials are submitted, because `dosage = num / area * 1000`
- human confirmation: `add_farming_record` must not be called until the user explicitly confirms creating the farming record

Optional fields may be passed only when known: `address`, `location`, `area_unit`, `plot_crop_id`, `tgzn_dept_id`. `area` is optional only when no material `goodsList` is being submitted.

The operation-order message and the final record-creation confirmation must be two separate user turns.

## User-Facing Confirmation Draft

When asking the user to confirm creation, show only fields that are meaningful to the user, such as operation, base/plot, time, area, address/location, and confirmed materials.

Do not display `work_user`, `tgzn_user_id`, or `user_id` in the user-facing confirmation draft. The operator defaults to the current conversation user and is usually only a numeric ID, so keep it in the internal payload only.

## Preparation Phase

When the user orders an operation:

1. Resolve `matter_id` from `get_farming_operation_list` or prior confirmed operation context.
2. Collect known draft fields from context and user input.
3. If material confirmation is needed, query `get_agri_input_list`, run `scripts/agri_material_payload.py build-panel`, keep the whole script-produced `pending_draft`, and return only the script-produced `form_syntax` to the frontend.
4. If no material confirmation is needed, store the draft, show or summarize the real user-meaningful draft fields, and ask the user whether to create the farming record. Do not show the default operator ID. End the turn after asking.
5. Do not call `add_farming_record` or run `build-submit` during preparation. Phrases such as "下达", "安排", or "执行这个农事操作" choose the operation and prepare the draft; they do not replace final creation confirmation.

## Submit Phase

When `form_submit` returns:

1. Validate the submitted `goodsList`.
2. Recover the `pending_draft` from the panel creation round. It must contain both `record_draft` and original `selected_inventory_rows`.
3. Run `scripts/agri_material_payload.py build-submit` with the submitted list, `pending_draft`, whitelisted `system_params`, and either the original material confirmation `submitted_form` or `record_creation_confirmed: true`.
4. If original inventory rows are unavailable, re-query `get_agri_input_list`, put the returned rows in `pending_draft.selected_inventory_rows`, and rerun the script.
5. If the script returns `missing_fields` or `record_draft is required`, ask for or recover the missing non-material field and keep the confirmed materials in context.
6. If the script returns `requires_user_confirmation`, ask the user to confirm creation and do not call `add_farming_record`.
7. If complete, call `add_farming_record` with script-produced `add_farming_record_args` directly.

For no-material operations, run `build-submit` only after the user confirms the prepared draft in a later user turn, with `submitted_goodsList: []`, `original_inventory_rows: []`, `record_creation_confirmed: true`, `draft_was_shown_to_user: true`, and `confirmation_source: "user_confirmed_prepared_draft"`.

## add_farming_record Payload

Use the field names expected by the `call-mcp-tools` skill:

```json
{
  "cid": 2007,
  "plot_id": 130,
  "base_id": 3,
  "matter_id": 207,
  "operate_time": "2026-07-07 14:32",
  "address": "known address only",
  "location": "known lng,lat only",
  "area": 2.65,
  "area_unit": "亩",
  "goodsList": [],
  "work_user": 73,
  "tgzn_user_id": 73,
  "tgzn_entity_id": 1,
  "tgzn_dept_id": 1
}
```

Omit unknown optional fields. Do not send placeholders such as `0`, `unknown`, empty coordinates, or guessed dates unless the upstream contract explicitly defines that value as valid.

`goodsList` in this payload must not be raw inventory rows. It must be the compact script-produced list containing only `goods_name`, `stock_goods_id`, `is_formula`, `num`, `price`, `unit`, and computed `dosage`. `num` is the frontend-confirmed total quantity. `goods_name`, `stock_goods_id`, `price`, and `unit` come from the frontend when present, otherwise from the matched MCP inventory row. `dosage` is computed from `num / area * 1000`.

If `user_id` is available in server/session/gateway context, use it as the default operator. Do not ask the user to choose an operator unless the user explicitly wants a different operator or `user_id` is missing.

Do not pass raw system fields such as `token`, `terminal_id`, `cname`, or `entity_info_id` into `add_farming_record`. `scripts/agri_material_payload.py build-submit` only maps whitelisted system values: `cid`, `user_id` to `work_user` / `tgzn_user_id`, `entity_id` to `tgzn_entity_id`, and nonzero `dept_id` to `tgzn_dept_id`.

## Result Handling

After `add_farming_record` returns:

- Treat a returned object with a valid `id` as successful creation.
- Tell the user whether creation succeeded and show the record ID.
- Summarize only real returned fields such as plot name, crop batch, operation ID/name, time, area, address, and confirmed materials.
- If payload is empty but the call reports success, say that it was submitted but no record details were returned.
- Do not expose internal tokens, gateway fields, raw request payloads, or debug JSON.
