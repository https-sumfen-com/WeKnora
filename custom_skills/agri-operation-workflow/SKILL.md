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

This is a new workflow skill. Do not use or inherit `plant-agent-response-contract`.

## Hard Rules

- Base every recommendation, material prefill, and record submission on SONO-MCP results, server/page context, or explicit user input.
- Before calling any SONO-MCP tool, load and follow the `call-mcp-tools` skill.
- Never invent `cid`, `base_id`, `plot_id`, `matter_id`, `operate_time`, `work_user`, material IDs, price, stock, unit, or usage.
- Use `get_agri_input_list` as the only material source. Do not use `get_formula_list`; the current frontend flow does not support formula selection.
- Do not return every item from `get_agri_input_list`. Filter material candidates by the confirmed farming operation type and MCP evidence.
- Use `get_farming_operation_list` to resolve operation choices and `matter_id`. Do not generate operation IDs from names.
- Default the operator to `user_id` when it is present. Use it as `work_user` and, when needed by the upstream payload, `tgzn_user_id`; do not ask the user for an operator when `user_id` is available.
- Call `add_farming_record` only after the user has explicitly confirmed creation/submission and all required draft fields are known.
- The `form-panel` block carries only `goodsList`. Do not put plot, address, operation, task, or old farming-form fields inside that block.
- If material usage is not returned by MCP or provided by the user, set `mu_usage: 0` and let the user confirm. Do not create nonzero dosage recommendations from model knowledge.

## Workflow

### 1. Recommend Farming Operations

Use this phase whenever the user asks what should be done, what farming actions are recommended, which operation to arrange, or asks for 农事建议 / 农事操作 / 作业安排. This phase should trigger the skill even before the user decides to submit a record.

1. Identify the target entity from context: `cid` or `tgzn_entity_id`, `base_id`, `plot_id`, crop/plot context, and time window.
2. Read facts using the smallest relevant SONO-MCP calls. Typical inputs are plot status, weather, warnings, and current context. Follow `call-mcp-tools` and do not scan tools.
3. If the answer needs actionable operation choices, call `get_farming_operation_list` and match returned operation names/IDs to the MCP-grounded need.
4. Present only operations supported by MCP evidence. For each option include the operation name, why it is recommended, the required confirmation data, and whether material confirmation will be needed.
5. If no returned operation matches the evidence, explain the gap and ask the user to choose an operation from the returned list instead of fabricating one.

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
6. Filter the returned inventory by operation type before preparing the panel. Read `references/material-selection.md`; never pass the full inventory list through by default.
7. Normalize the filtered rows to the frontend `goodsList` shape and return an `agri_material_usage_confirm` form panel. Read `references/form-panel.md` before emitting the block.

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
3. Merge the confirmed `goodsList` into the pending `add_farming_record` draft from the conversation/backend state. The frontend does not resend old farming-form fields.
4. If the draft cannot be recovered, ask for the missing operation/plot/time fields. Do not call `add_farming_record` with only `goodsList`.
5. Call `add_farming_record` only after the draft and confirmed `goodsList` are complete.
6. Return the creation result using real fields from the MCP response. Use the `call-mcp-tools` reference `tool-farming-record.md` before summarizing success or failure.

## Material Mapping

Read the `call-mcp-tools` reference `tool-agri-input-list.md`, this skill's `references/material-selection.md`, and this skill's `references/form-panel.md` when preparing material candidates.

Map inventory rows conservatively:

```text
goods_name      = row.stock_goods.name || row.name
stock_goods_id  = row.stock_goods.id
stock_record_id = row.id
is_formula      = 0
mu_usage        = explicit MCP/user usage, otherwise 0
price           = Number(row.price || row.stock_goods.price || 0)
unit            = row.stock_goods.unit || ""
dosage          = Number(row.stock_goods.number21921) only if returned; never treat dosage/specification as mu_usage
```

Do not include a row in recommended `goodsList` if `goods_name` is empty, `stock_goods_id` is missing, or the row does not match the operation type. If no confident candidates exist, return `goodsList: []`; the frontend can show an empty panel and let the user add materials.

## Required References

- `references/form-panel.md`: frontend block and `form_submit` contract.
- `references/record-draft.md`: draft lifecycle and `add_farming_record` merge rules.
- `references/material-selection.md`: operation-aware material filtering rules.
- `call-mcp-tools`: MCP tool selection and parameter discipline.
- `call-mcp-tools` reference `tool-agri-input-list.md`: material list source fields.
- `call-mcp-tools` reference `tool-farming-operation-list.md`: operation list and `matter_id`.
- `call-mcp-tools` reference `tool-farming-record.md`: creation result handling.

## Completion Checklist

- Recommendation used MCP evidence and did not invent an operation.
- `matter_id` came from `get_farming_operation_list` or prior MCP-backed context.
- Materials came only from filtered `get_agri_input_list` results; `get_formula_list` was not used and full inventory was not returned by default.
- `form-panel` used tag `agri_material_usage_confirm` and formType `agri-material-usage`.
- `goodsList` is a complete array and `mu_usage` is `0` unless supported by MCP/user input.
- Operator defaults to `user_id` when available.
- `add_farming_record` was not called until user confirmation and required draft fields were complete.
