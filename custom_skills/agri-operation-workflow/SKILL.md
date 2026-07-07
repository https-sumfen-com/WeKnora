---
name: agri-operation-workflow
description: "Use whenever SONO Agent recommends farming operations, 农事操作, 农事建议, 作业安排, 施肥, 用药, 灌溉, 除草, 植保, or any action that may later become a farming record. Also use when accepting a user's selected operation, preparing add_farming_record draft parameters, returning the agri_material_usage_confirm form-panel, handling agri-material-usage form_submit, or creating the farming record through SONO-MCP."
---

# SONO Farming Operation Workflow

## Scope

Use this skill for the complete farming-operation loop:

```text
MCP-grounded recommendation -> user orders an operation -> prepare record draft
-> prefill material candidates from get_agri_input_list -> user confirms goodsList
-> call add_farming_record -> return creation result
```

This is a new workflow skill for farming-operation recommendation, material confirmation, and record creation.

## Script-First Payload Control

Use `scripts/agri_material_payload.py` for the fragile material payload steps. Do not hand-build or hand-merge panel, draft, or submit payloads when the script is available. The script output is the authority for `form_panel`, `pending_draft`, and `add_farming_record_args`.

Use `execute_skill_script` with this skill's script path:

```json
{
  "skill_name": "agri-operation-workflow",
  "script_path": "scripts/agri_material_payload.py",
  "args": ["build-panel"],
  "input": "<JSON>"
}
```

Do not use `python`, `python3`, or an absolute interpreter as `script_path`.

### build-panel

Use after `get_agri_input_list` returns and before sending the form panel. Input:

```json
{
  "operation_name": "中草药开花前追肥",
  "record_draft": {
    "cid": 2007,
    "base_id": 3,
    "plot_id": 130,
    "matter_id": 207,
    "operate_time": "2026-07-07 14:32",
    "area": 2.65
  },
  "inventory_rows": [],
  "usage_by_stock_record_id": { "29": 1.5 },
  "usage_by_stock_goods_id": {},
  "usage_by_goods_name": {},
  "default_per_mu_rate": 0
}
```

Output includes:

- `form_panel`: validated `form-panel` block with filtered `goodsList`.
- `selected_inventory_rows`: original inventory rows selected for the panel.
- `pending_draft`: assistant/backend state containing `record_draft` plus original `selected_inventory_rows`; keep this state outside the frontend `form-panel` block and recover it by conversation state or `sourceMessageId` when the user submits.

If `form_panel.goodsList` is empty, the frontend can still let the user add materials.

### build-submit

Use after the frontend returns `form_submit` and before `add_farming_record`. Input:

```json
{
  "submitted_goodsList": [],
  "pending_draft": {
    "record_draft": {},
    "selected_inventory_rows": []
  },
  "system_params": {
    "cid": 2014,
    "user_id": 48,
    "entity_id": 1,
    "dept_id": 0
  }
}
```

Output includes:

- `goodsList`: compact submit-ready material rows from user-confirmed UI fields plus computed `dosage`.
- `add_farming_record_args`: final submit input. Call `add_farming_record` with this object directly; do not rebuild it manually.

Submit output `goodsList` is compact and uses the frontend-confirmed fields:

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

`num` is the frontend-confirmed total material quantity. `dosage` is computed by the script as `num / record_draft.area * 1000`. Do not include `stock_goods`, `inventory_num`, `change_num`, `mu_usage`, `stock_record_id`, or raw inventory fields in the final submit-ready item.

If `record_draft` is missing, the script returns `ok: false` with `record_draft is required`. If required fields are missing, it returns `missing_fields`. If inventory rows are missing, recover them by re-calling `get_agri_input_list` or ask the user to reselect materials. Do not call `add_farming_record` with partial script output.

## Hard Rules

- Base every recommendation, material prefill, and record submission on SONO-MCP results, server/page context, or explicit user input.
- Before calling any SONO-MCP tool, load and follow the `call-mcp-tools` skill.
- Never invent `cid`, `base_id`, `plot_id`, `matter_id`, `operate_time`, `work_user`, material IDs, price, stock, unit, or usage.
- Use `get_agri_input_list` as the only material source. Do not use `get_formula_list`; the current frontend flow does not support formula selection.
- Do not return every item from `get_agri_input_list`. Filter material candidates by the confirmed farming operation type and MCP evidence.
- Use `get_farming_operation_list` to resolve operation choices and `matter_id`. Do not generate operation IDs from names.
- Default the operator to `user_id` when it is present. Use it as `work_user` and, when needed by the upstream payload, `tgzn_user_id`; do not ask the user for an operator when `user_id` is available.
- Keep the script-produced `pending_draft` across the panel round trip. It must contain the full record draft and original `get_agri_input_list` rows. The frontend panel `goodsList` is simplified for UI and must not be submitted directly to `add_farming_record`.
- Never let user-facing system parameters such as `token`, `terminal_id`, `cname`, or `entity_info_id` enter `add_farming_record_args`. Only use whitelisted context such as `cid`, `user_id`, `entity_id`, and nonzero `dept_id`.
- Never call `add_farming_record` with raw `selected_inventory_rows`. They still contain stock balance `num` and are not the compact frontend-confirmed submit contract.
- Call `add_farming_record` only after the user has explicitly confirmed creation/submission and all required draft fields are known.
- The `form-panel` block carries only `goodsList`. Do not put plot, address, operation, task, or old farming-form fields inside that block.
- When a recommended farming operation involves materials, compute a recommended total `num` for the frontend whenever there is a reasonable per-mu rate basis and known area. Check MCP results, relevant recommendation text, user conditions, knowledge-base/technical-standard evidence, and then the model's own agronomic experience.
- The model may use its own agronomic experience to recommend the internal per-mu rate when stronger sources are absent. Keep the resulting `num` conservative and editable. Use `num: 0` and `dosage: 0` only when no reasonable rate can be recommended or area is unavailable.

## Workflow

### 1. Recommend Farming Operations

Use this phase whenever the user asks what should be done, what farming actions are recommended, which operation to arrange, or asks for 农事建议 / 农事操作 / 作业安排. This phase should trigger the skill even before the user decides to submit a record.

1. Identify the target entity from context: `cid` or `tgzn_entity_id`, `base_id`, `plot_id`, crop/plot context, and time window.
2. Read facts using the smallest relevant SONO-MCP calls. Typical inputs are plot status, weather, warnings, and current context. Follow `call-mcp-tools` and do not scan tools.
3. If the answer needs actionable operation choices, call `get_farming_operation_list` and match returned operation names/IDs to the MCP-grounded need.
4. Present only operations supported by MCP evidence. For each option include the operation name, why it is recommended, the required confirmation data, and whether material confirmation will be needed.
5. If the recommended operation involves materials, also prepare the basis for recommended per-mu usage: MCP recommendation fields/text first, then relevant knowledge-base or technical-standard evidence, then model agronomic experience if stronger sources do not contain a rate.
6. If no returned operation matches the evidence, explain the gap and ask the user to choose an operation from the returned list instead of fabricating one.

### 2. User Orders an Operation

Use this phase when the user says to arrange, dispatch, execute, create, save, or submit a specific farming operation.

1. Treat this as preparation unless all data is complete and no material confirmation is required.
2. Resolve `matter_id` from the earlier recommendation or by calling `get_farming_operation_list`.
3. Build an internal `add_farming_record` draft from server/page context, earlier MCP results, and explicit user input:
   - company: `cid` or `tgzn_entity_id`
   - target: `base_id`, `plot_id`
   - operation: `matter_id`
   - time: explicit `operate_time`
   - person: default `work_user` to `user_id`; also set `tgzn_user_id` from `user_id` when the upstream payload needs it
   - optional real fields: `address`, `location`, `area`, `area_unit`, `plot_crop_id`, `tgzn_dept_id`
4. If any required draft field is missing, ask for that field. Do not open the material panel as a substitute for missing record fields.
5. If the operation requires or may use materials, call `get_agri_input_list` with `cid + base_id`.
6. Resolve recommended per-mu usage for candidate materials using `references/usage-recommendation.md`; `build-panel` converts it to frontend total `num` and computed `dosage` when area is known.
7. Run `scripts/agri_material_payload.py build-panel` with the current `record_draft` to filter inventory, normalize the frontend `goodsList`, and return `pending_draft`.
8. Store the whole script-produced `pending_draft`, keyed by conversation state or the assistant `sourceMessageId`; do not store only `selected_inventory_rows`.
9. Return the script-produced `form_panel` as the `agri_material_usage_confirm` block. Read `references/form-panel.md` before emitting the block.

### 3. Handle Material Confirmation

Use this phase when the user message contains:

```json
{
  "type": "form_submit",
  "formType": "agri-material-usage",
  "tag": "agri_material_usage_confirm"
}
```

1. Read `goodsList` from the submitted JSON.
2. Validate the list using `references/form-panel.md`.
3. Recover the script-produced `pending_draft` from the panel creation round. The frontend does not resend plot, operation, time, or original inventory rows.
4. Run `scripts/agri_material_payload.py build-submit` with the submitted list, recovered `pending_draft`, and current `system_params`.
5. If original inventory rows are missing from the draft, call `get_agri_input_list` again with `cid + base_id`, put the returned rows into `pending_draft.selected_inventory_rows`, then rerun `build-submit`.
6. If `record_draft` is missing or `missing_fields` is returned, ask for/recover the missing operation, plot, base, or time fields. Do not call `add_farming_record`.
7. If unmatched materials remain, ask the user to reselect unmatched materials.
8. Call `add_farming_record` with script-produced `add_farming_record_args` directly. Do not manually merge frontend `goodsList` into the draft after the script returns.
9. Return the creation result using real fields from the MCP response. Use the `call-mcp-tools` reference `tool-farming-record.md` before summarizing success or failure.

## Material Mapping

Read the `call-mcp-tools` reference `tool-agri-input-list.md`, this skill's `references/material-selection.md`, this skill's `references/usage-recommendation.md`, and this skill's `references/form-panel.md` when preparing material candidates.

Map inventory rows conservatively:

```text
goods_name      = row.stock_goods.name || row.name
stock_goods_id  = row.stock_goods.id
stock_record_id = row.id
is_formula      = 0
num             = total material quantity = recommended per-mu usage * record_draft.area; fallback 0 only when no reasonable rate or area is available
price           = Number(row.price || row.stock_goods.price || 0)
unit            = row.stock_goods.unit || ""
dosage          = num / record_draft.area * 1000
```

Do not include a row in recommended `goodsList` if `goods_name` is empty, `stock_goods_id` is missing, or the row does not match the operation type. If no confident candidates exist, return `goodsList: []`; the frontend can show an empty panel and let the user add materials.

On submit, `scripts/agri_material_payload.py build-submit` keeps only the compact submit fields:

```text
goods_name      = submitted goods_name
stock_goods_id  = submitted stock_goods_id
is_formula      = submitted is_formula || 0
num             = submitted total num
price           = submitted price
unit            = submitted unit || ""
dosage          = num / record_draft.area * 1000
```

Do not replace the script-produced item with the original inventory row after this step.

## Required References

- `references/form-panel.md`: frontend block and `form_submit` contract.
- `references/record-draft.md`: draft lifecycle and `add_farming_record` merge rules.
- `references/material-selection.md`: operation-aware material filtering rules.
- `references/usage-recommendation.md`: evidence-backed per-mu rate and frontend `num/dosage` recommendation rules.
- `references/goodslist-submit.md`: validate original inventory rows and build compact `add_farming_record.goodsList`.
- `scripts/agri_material_payload.py`: deterministic build/validation for form-panel and submit-ready goodsList.
- `call-mcp-tools`: MCP tool selection and parameter discipline.
- `call-mcp-tools` reference `tool-agri-input-list.md`: material list source fields.
- `call-mcp-tools` reference `tool-farming-operation-list.md`: operation list and `matter_id`.
- `call-mcp-tools` reference `tool-farming-record.md`: creation result handling.

## Completion Checklist

- Recommendation used MCP evidence and did not invent an operation.
- `matter_id` came from `get_farming_operation_list` or prior MCP-backed context.
- Materials came only from filtered `get_agri_input_list` results; `get_formula_list` was not used and full inventory was not returned by default.
- The whole script-produced `pending_draft` was preserved from panel creation to form submission.
- Script-produced `add_farming_record_args` was used directly; no manual final payload merge was performed.
- Submit-ready `goodsList` used only `goods_name`, `stock_goods_id`, `is_formula`, `num`, `price`, `unit`, and computed `dosage`; frontend `num` was not replaced by inventory balance.
- `scripts/agri_material_payload.py` was used for `build-panel` and `build-submit` when materials were involved.
- `form-panel` used tag `agri_material_usage_confirm` and formType `agri-material-usage`.
- Material-related recommendations attempted a per-mu rate recommendation, using model agronomic experience when stronger sources lacked a rate; frontend `num/dosage` fell back to `0` only when no reasonable rate or area was available.
- Operator defaults to `user_id` when available.
- `add_farming_record` was not called until user confirmation and required draft fields were complete.
