# Farming Record Draft Lifecycle

Read this reference before preparing or submitting `add_farming_record`.

## Draft Sources

Build the draft only from:

- server/session/gateway context
- current page route or locked base/plot context
- SONO-MCP tool results
- explicit user input
- the user's submitted material `goodsList`
- the original `get_agri_input_list` inventory rows selected for the form panel
- the script-produced `pending_draft` from `scripts/agri_material_payload.py build-panel`

Do not infer missing IDs, area, time, operator, address, inventory, price, unit, or total material quantity from model knowledge. Model agronomic experience may be used only to recommend the internal per-mu rate before converting it to editable frontend `num`.

## Required Draft Fields

Before calling `add_farming_record`, verify:

- company identity: `cid` or `tgzn_entity_id`
- target identity: `base_id` and `plot_id` when the operation is plot-bound
- operation identity: `matter_id`
- operation time: explicit `operate_time`
- operator: default to `user_id` when present; send it as `work_user` and also as `tgzn_user_id` when required by upstream
- materials: submit-ready `goodsList` with compact frontend-confirmed fields when the operation uses agricultural materials
- area: required when materials are submitted, because `dosage = num / area * 1000`

Optional fields may be passed only when known: `address`, `location`, `area_unit`, `plot_crop_id`, `tgzn_dept_id`. `area` is optional only when no material `goodsList` is being submitted.

## Preparation Phase

When the user orders an operation:

1. Resolve `matter_id` from `get_farming_operation_list` or prior confirmed operation context.
2. Collect known draft fields from context and user input.
3. If material confirmation is needed, query `get_agri_input_list`, run `scripts/agri_material_payload.py build-panel`, keep the whole script-produced `pending_draft`, and return only the simplified `form_panel` to the frontend.
4. Do not call `add_farming_record` yet unless the user has already explicitly confirmed all required fields and no material panel is needed.

## Submit Phase

When `form_submit` returns:

1. Validate the submitted `goodsList`.
2. Recover the `pending_draft` from the panel creation round. It must contain both `record_draft` and original `selected_inventory_rows`.
3. Run `scripts/agri_material_payload.py build-submit` with the submitted list, `pending_draft`, and whitelisted `system_params`.
4. If original inventory rows are unavailable, re-query `get_agri_input_list`, put the returned rows in `pending_draft.selected_inventory_rows`, and rerun the script.
5. If the script returns `missing_fields` or `record_draft is required`, ask for or recover the missing non-material field and keep the confirmed materials in context.
6. If complete, call `add_farming_record` with script-produced `add_farming_record_args` directly.

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

`goodsList` in this payload must not be raw inventory rows. It must be the compact script-produced list containing only `goods_name`, `stock_goods_id`, `is_formula`, `num`, `price`, `unit`, and computed `dosage`. `num` is the frontend-confirmed total quantity. `dosage` is computed from `num / area * 1000`.

If `user_id` is available in server/session/gateway context, use it as the default operator. Do not ask the user to choose an operator unless the user explicitly wants a different operator or `user_id` is missing.

Do not pass raw system fields such as `token`, `terminal_id`, `cname`, or `entity_info_id` into `add_farming_record`. `scripts/agri_material_payload.py build-submit` only maps whitelisted system values: `cid`, `user_id` to `work_user` / `tgzn_user_id`, `entity_id` to `tgzn_entity_id`, and nonzero `dept_id` to `tgzn_dept_id`.

## Result Handling

After `add_farming_record` returns:

- Treat a returned object with a valid `id` as successful creation.
- Tell the user whether creation succeeded and show the record ID.
- Summarize only real returned fields such as plot name, crop batch, operation ID/name, time, area, address, and confirmed materials.
- If payload is empty but the call reports success, say that it was submitted but no record details were returned.
- Do not expose internal tokens, gateway fields, raw request payloads, or debug JSON.
