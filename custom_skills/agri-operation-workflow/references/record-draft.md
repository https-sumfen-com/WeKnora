# Farming Record Draft Lifecycle

Read this reference before preparing or submitting `add_farming_record`.

## Draft Sources

Build the draft only from:

- server/session/gateway context
- current page route or locked base/plot context
- SONO-MCP tool results
- explicit user input
- the user's submitted material `goodsList`

Do not infer missing IDs, area, time, operator, address, or material usage from model knowledge.

## Required Draft Fields

Before calling `add_farming_record`, verify:

- company identity: `cid` or `tgzn_entity_id`
- target identity: `base_id` and `plot_id` when the operation is plot-bound
- operation identity: `matter_id`
- operation time: explicit `operate_time`
- operator: default to `user_id` when present; send it as `work_user` and also as `tgzn_user_id` when required by upstream
- materials: confirmed `goodsList` when the operation uses agricultural materials

Optional fields may be passed only when known: `address`, `location`, `area`, `area_unit`, `plot_crop_id`, `tgzn_dept_id`.

## Preparation Phase

When the user orders an operation:

1. Resolve `matter_id` from `get_farming_operation_list` or prior confirmed operation context.
2. Collect known draft fields from context and user input.
3. If material confirmation is needed, query `get_agri_input_list` and return the form panel.
4. Do not call `add_farming_record` yet unless the user has already explicitly confirmed all required fields and no material panel is needed.

## Submit Phase

When `form_submit` returns:

1. Validate the submitted `goodsList`.
2. Merge the list into the pending draft.
3. If the draft is missing any required non-material field, ask for the missing field and keep the confirmed materials in context.
4. If complete, call `add_farming_record`.

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

If `user_id` is available in server/session/gateway context, use it as the default operator. Do not ask the user to choose an operator unless the user explicitly wants a different operator or `user_id` is missing.

## Result Handling

After `add_farming_record` returns:

- Treat a returned object with a valid `id` as successful creation.
- Tell the user whether creation succeeded and show the record ID.
- Summarize only real returned fields such as plot name, crop batch, operation ID/name, time, area, address, and confirmed materials.
- If payload is empty but the call reports success, say that it was submitted but no record details were returned.
- Do not expose internal tokens, gateway fields, raw request payloads, or debug JSON.
