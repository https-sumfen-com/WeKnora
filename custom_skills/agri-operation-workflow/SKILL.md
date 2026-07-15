---
name: agri-operation-workflow
description: "Use when SONO Agent recommends farming operations/农事操作/农事建议/作业安排, handles device operations/设备操作, soil moisture/土壤湿度, irrigation decisions/灌溉判断 or SHUM, recommends materials or usage/推荐农资/推荐用量/用量推荐/农资用量/亩用量/总用量 for 施肥/用药/植保/除草, returns form agri-material-usage or irrigation-valve-duration Syntax, handles either form_submit, or safely prepares/calls add_farming_record or start_valve_bank through SONO-MCP."
---

# SONO Farming Operation Workflow

## Scope

Use this skill for the complete farming-operation loop:

```text
MCP-grounded recommendation -> user orders an operation -> prepare record draft
-> prefill material candidates from get_agri_input_list -> user confirms goodsList
-> user confirms record creation -> call add_farming_record -> return creation result
```

This is a new workflow skill for farming-operation recommendation, material confirmation, and record creation.

Use it also for the guarded device-assisted irrigation loop:

```text
get_plot_device_list -> exact SHUM analysis -> plot and weather evidence
-> irrigation decision -> one batched valve lookup -> duration form
-> execution draft -> later user confirmation -> ordered valve starts
```

## Script-First Payload Control

Use `scripts/agri_material_payload.py` for the fragile material payload steps. Do not hand-build or hand-merge panel, draft, or submit payloads when the script is available. The script output is the authority for `form_syntax`, `pending_draft`, and `add_farming_record_args`.

Use `scripts/irrigation_control_payload.py` for every irrigation payload transition. Its four commands are:

- `analyze-sensors`: validate exact `SHUM` readings and produce authoritative `sensor_analysis`, `plot_device_ids`, and internal `plot_device_id_values`.
- `build-panel`: revalidate the complete `sensor_analysis` and produce authoritative `form_syntax` plus `pending_irrigation_draft`.
- `prepare-execution`: validate the irrigation form submit and produce authoritative `pending_execution_draft`, `draft_fingerprint`, and confirmation text.
- `build-execution`: bind a later user confirmation to the trusted pending draft and produce authoritative ordered `start_valve_bank_args`.

Do not hand-build or merge irrigation form or execution payloads. Preserve the complete script-produced pending state across turns.

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

Use after `get_agri_input_list` returns and before sending the material confirmation Syntax. Input:

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

- `form_syntax`: frontend-visible `form agri-material-usage` Syntax with filtered material rows. Send this Syntax text directly; do not wrap it in JSON.
- `selected_inventory_rows`: original inventory rows selected for the panel.
- `pending_draft`: assistant/backend state containing `record_draft` plus original `selected_inventory_rows`; keep this state outside the frontend-visible Syntax and recover it by conversation state or `sourceMessageId` when the user submits.

If no material candidates are selected, `form_syntax` still contains `data` with no `-` items; the frontend can still let the user add materials.

### build-submit

Use after the frontend returns `form_submit`, or after a no-material operation receives final creation confirmation, and before `add_farming_record`. Input:

```json
{
  "record_creation_confirmed": true,
  "draft_was_shown_to_user": true,
  "confirmation_source": "user_confirmed_prepared_draft",
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

- `goodsList`: compact submit-ready material rows from user-confirmed UI fields, matched MCP material metadata when needed, and computed `dosage`.
- `add_farming_record_args`: final submit input. Call `add_farming_record` with this object directly; do not rebuild it manually.

`record_creation_confirmed` is required before the script returns `add_farming_record_args`. Set it to `true` only after the user explicitly confirms record creation, or pass the validated frontend `submitted_form` when it is an `agri-material-usage` confirmation submit. For no-material records, `record_creation_confirmed: true` is not sufficient by itself; also pass `draft_was_shown_to_user: true` and `confirmation_source: "user_confirmed_prepared_draft"` after a separate user reply confirms the prepared draft. If confirmation is missing, the script returns `requires_user_confirmation: true`; ask the user to confirm and do not call `add_farming_record`.

Submit output `goodsList` is compact and follows the `add_farming_record` contract:

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

`num` is the frontend-confirmed total material quantity. `goods_name`, `stock_goods_id`, `price`, and `unit` use frontend values when present; if any of them are missing, the script may fill them only from the matched original `get_agri_input_list` row. `dosage` is computed by the script as `num / record_draft.area * 1000`. Do not include `stock_goods`, `inventory_num`, `change_num`, `mu_usage`, `stock_record_id`, or raw inventory fields in the final submit-ready item.

If `record_draft` is missing, the script returns `ok: false` with `record_draft is required`. If required fields are missing, it returns `missing_fields`. If inventory rows are missing, recover them by re-calling `get_agri_input_list` or ask the user to reselect materials. Do not call `add_farming_record` with partial script output.

## Hard Rules

- Base every recommendation, material prefill, and record submission on SONO-MCP results, server/page context, or explicit user input.
- Before calling any SONO-MCP tool, load and follow the `call-mcp-tools` skill.
- Never invent `cid`, `base_id`, `plot_id`, `matter_id`, `work_user`, material IDs, price, stock, unit, or usage. If `operate_time` is missing, default it to the current local time formatted to minutes (`YYYY-MM-DD HH:mm`). If it is date-only (`YYYY-MM-DD`), preserve that date and append the current `HH:mm`; if it includes seconds, submit only to minute precision.
- Use `get_agri_input_list` as the only material source. Do not use `get_formula_list`; the current frontend flow does not support formula selection.
- Do not return every item from `get_agri_input_list`. Filter material candidates by the confirmed farming operation type and MCP evidence.
- Use `get_farming_operation_list` to resolve operation choices and `matter_id`. Do not generate operation IDs from names.
- Default the operator to `user_id` when it is present. Use it as `work_user` and, when needed by the upstream payload, `tgzn_user_id`; do not ask the user for an operator when `user_id` is available.
- Do not display `work_user`, `tgzn_user_id`, or `user_id` in the user-facing confirmation draft. The operator is an internal default from the current conversation user; showing only the numeric ID confuses the user.
- Keep the script-produced `pending_draft` across the panel round trip. It must contain the full record draft and original `get_agri_input_list` rows. The frontend Syntax is simplified for UI and must not be submitted directly to `add_farming_record`.
- Never let user-facing system parameters such as `token`, `terminal_id`, `cname`, or `entity_info_id` enter `add_farming_record_args`. Only use whitelisted context such as `cid`, `user_id`, `entity_id`, and nonzero `dept_id`.
- Never call `add_farming_record` with raw `selected_inventory_rows`. They still contain stock balance `num` and are not the compact frontend-confirmed submit contract.
- Call `add_farming_record` only after the user has explicitly confirmed record creation/submission and all required draft fields are known. Operation ordering phrases such as "下达", "安排", or "执行这个农事操作" start draft preparation; they are not enough to create the record unless the user is responding to a final creation confirmation.
- The operation-order message and the final record-creation confirmation must be two separate user turns.
- Never call `add_farming_record`, `build-submit`, or any MCP creation tool in the same assistant turn that receives the user's operation order.
- Do not set `record_creation_confirmed: true`, `draft_was_shown_to_user: true`, or `confirmation_source: "user_confirmed_prepared_draft"` while handling the operation-order turn. Set them only when handling the later user reply that confirms the displayed draft.
- For operations that do not require material confirmation, show or summarize the prepared record draft and ask whether to create the farming record. Hide internal operator fields from that confirmation text. Wait for the user's confirmation before running `build-submit` with `record_creation_confirmed: true`.
- The frontend-visible material recommendation must be `form agri-material-usage` Syntax only. Do not output `schemaVersion`, `blocks`, `kind`, `form-panel`, JSON wrappers, SSE JSON events, Markdown explanation, plot, address, operation, task, or old farming-form fields in that Syntax.
- When a recommended farming operation involves materials, compute a recommended total `num` for the frontend whenever there is a reasonable per-mu rate basis and known area. Check MCP results, relevant recommendation text, user conditions, knowledge-base/technical-standard evidence, and then the model's own agronomic experience.
- The model may use its own agronomic experience to recommend the internal per-mu rate when stronger sources are absent. Keep the resulting `num` conservative and editable. Use `num: 0` and `dosage: 0` only when no reasonable rate can be recommended or area is unavailable.
- Use the device-assisted sequence only for a known `cid` and `plot_id`: `get_plot_device_list` -> exact `SHUM` extraction -> `get_plot_info` + `get_weather` -> explicit irrigation-necessity decision -> one `get_valve_bank_by_device` call -> dedicated irrigation form -> separate confirmation -> ordered `start_valve_bank` calls.
- Accept soil-moisture telemetry only when `key == "SHUM"`; similar names, labels, and case variants are not substitutes. Use the first finite exact match per device and the outer device-list `id`.
- Never call `get_valve_bank_by_device` unless the authoritative sensor analysis has valid readings and irrigation is explicitly judged necessary. Pass `plot_device_ids` as the script-produced comma-separated string; do not send internal `plot_device_id_values`.
- Call `get_valve_bank_by_device` once for the whole comma-separated ID string. Treat its `payload[]` as the server-deduplicated valve-bank list.
- Before displaying the irrigation form, run `build-panel` so the entire `sensor_analysis` is revalidated. Do not trust a bare average or a manually reconstructed analysis object.
- If the batch valve lookup returns no valve banks, do not display the valve form and do not call a valve control tool. Fall back to `get_farming_operation_list` and offer an ordinary farming-operation workflow.
- The frontend-visible irrigation confirmation must use only the dedicated `form irrigation-valve-duration` Syntax described in `references/irrigation-form.md`.
- Never call `start_valve_bank` in the same assistant turn that receives the irrigation form submit.
- The form-submit turn may only run `prepare-execution`, preserve the trusted `pending_execution_draft` and `draft_fingerprint`, display the execution draft, and ask for confirmation. Run `build-execution` only after another user turn explicitly confirms that displayed draft.
- Execute script-produced `start_valve_bank_args` in order. On the first failure, stop and mark all later calls skipped. Do not automatically call `stop_valve_bank` to compensate for valves that already started; report succeeded, failed, and skipped valves explicitly.

## Workflow

### 1. Recommend Farming Operations

Use this phase whenever the user asks what should be done, what farming actions are recommended, which operation to arrange, or asks for 农事建议 / 农事操作 / 作业安排 / 推荐农资 / 推荐用量 / 农资用量 / 亩用量 / 总用量. This phase should trigger the skill even before the user decides to submit a record.

1. Identify the target entity from context: `cid` or `tgzn_entity_id`, `base_id`, `plot_id`, crop/plot context, and time window.
2. Read facts using the smallest relevant SONO-MCP calls. Typical inputs are plot status, weather, warnings, and current context. Follow `call-mcp-tools` and do not scan tools.
3. If the answer needs actionable operation choices, call `get_farming_operation_list` and match returned operation names/IDs to the MCP-grounded need.
4. Present only operations supported by MCP evidence. For each option include the operation name, why it is recommended, the required confirmation data, and whether material confirmation will be needed.
5. If the recommended operation involves materials, also prepare the basis for recommended per-mu usage: MCP recommendation fields/text first, then relevant knowledge-base or technical-standard evidence, then model agronomic experience if stronger sources do not contain a rate.
6. If no returned operation matches the evidence, explain the gap and ask the user to choose an operation from the returned list instead of fabricating one.

### 2. User Orders an Operation

Use this phase when the user says to arrange, dispatch, execute, create, save, or submit a specific farming operation.

1. Treat this as preparation. Do not call `add_farming_record`, do not run `build-submit`, and do not set any creation-confirmed flags in this phase.
2. Resolve `matter_id` from the earlier recommendation or by calling `get_farming_operation_list`.
3. Build an internal `add_farming_record` draft from server/page context, earlier MCP results, and explicit user input:
   - company: `cid` or `tgzn_entity_id`
   - target: `base_id`, `plot_id`
   - operation: `matter_id`
   - time: explicit `operate_time`; if missing, `build-submit` defaults it to the current local time to the minute; if date-only, it appends the current `HH:mm`
   - person: default `work_user` to `user_id`; also set `tgzn_user_id` from `user_id` when the upstream payload needs it
   - optional real fields: `address`, `location`, `area`, `area_unit`, `plot_crop_id`, `tgzn_dept_id`
4. If any required draft field is missing, ask for that field. Do not open the material panel as a substitute for missing record fields.
5. If the operation requires or may use materials, call `get_agri_input_list` with `cid + base_id`.
6. For material operations, resolve recommended per-mu usage for candidate materials using `references/usage-recommendation.md`; `build-panel` converts it to frontend total `num` and computed `dosage` when area is known.
7. For material operations, run `scripts/agri_material_payload.py build-panel` with the current `record_draft` to filter inventory, normalize the frontend material rows into `form_syntax`, and return `pending_draft`.
8. For material operations, store the whole script-produced `pending_draft`, keyed by conversation state or the assistant `sourceMessageId`; do not store only `selected_inventory_rows`.
9. For material operations, return only the script-produced `form_syntax` text to the frontend. Read `references/form-panel.md` before emitting the Syntax. Do not wrap it in JSON.
10. If the operation does not require material confirmation, store the draft, summarize the real user-meaningful draft fields to the user, and ask whether to create the farming record. Do not show `work_user`, `tgzn_user_id`, or `user_id`; keep them only in internal submit args. End the turn after asking. Do not run `build-submit` until a later user turn confirms the displayed draft.

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
4. Run `scripts/agri_material_payload.py build-submit` with the submitted list, recovered `pending_draft`, current `system_params`, and either the original `submitted_form` or `record_creation_confirmed: true`.
5. If original inventory rows are missing from the draft, call `get_agri_input_list` again with `cid + base_id`, put the returned rows into `pending_draft.selected_inventory_rows`, then rerun `build-submit`.
6. If `record_draft` is missing or `missing_fields` is returned, ask for/recover the missing operation, plot, base, or time fields. Do not call `add_farming_record`.
7. If unmatched materials remain, ask the user to reselect unmatched materials.
8. If `requires_user_confirmation` is returned, ask the user to confirm creation and do not call `add_farming_record`.
9. Call `add_farming_record` with script-produced `add_farming_record_args` directly. Do not manually merge frontend `goodsList` into the draft after the script returns.
10. Return the creation result using real fields from the MCP response. Use the `call-mcp-tools` reference `tool-farming-record.md` before summarizing success or failure.

### 4. Handle No-Material Record Confirmation

Use this phase when the operation draft is complete, no material confirmation panel is needed, and the user confirms creating the farming record after seeing the prepared draft.

1. Recover the stored draft from the preparation phase.
2. Verify this is a later user turn after the draft was shown. If the same user message both ordered the operation and asked to create it, return to Phase 2 and ask for confirmation instead of creating the record.
3. Run `scripts/agri_material_payload.py build-submit` with `submitted_goodsList: []`, `original_inventory_rows: []`, the recovered draft, current `system_params`, `record_creation_confirmed: true`, `draft_was_shown_to_user: true`, and `confirmation_source: "user_confirmed_prepared_draft"`.
4. If `requires_user_confirmation` is returned, ask the user to confirm creation again and do not call `add_farming_record`.
5. If `missing_fields` is returned, ask for or recover the missing fields and then ask for final creation confirmation again.
6. Call `add_farming_record` only with script-produced `add_farming_record_args`.

### 5. Device-Assisted Irrigation Control

Use this phase for 设备操作, 土壤湿度, 灌溉判断, `SHUM`, `irrigation-valve-duration`, or guarded `start_valve_bank` execution.

1. Call `get_plot_device_list` for the known `cid + plot_id`, then run `scripts/irrigation_control_payload.py analyze-sensors` on its full device list.
2. If the script reports no valid exact `SHUM`, explain that device evidence is insufficient and stop the device-control path.
3. Call `get_plot_info` and `get_weather`. Judge whether irrigation is necessary using the sensor average first, then plot/crop evidence, then recent and forecast rain/weather. Set `irrigation_needed: true` only when that combined evidence supports irrigation.
4. If irrigation is not necessary or remains uncertain, explain the evidence and do not query or control valves.
5. When irrigation is necessary, call `get_valve_bank_by_device` exactly once with `plot_device_ids` equal to the script-produced comma-separated string. Use the returned deduplicated `payload[]` as `valve_banks`.
6. If no valve banks are returned, call `get_farming_operation_list` and fall back to recommending/preparing an ordinary irrigation farming operation; do not fabricate valve IDs.
7. Run `build-panel` with the complete `sensor_analysis`, evidence-backed reason, positive recommended duration, and returned valves. Preserve `pending_irrigation_draft` and send only its `form_syntax`. Read `references/irrigation-control.md` and `references/irrigation-form.md` first.
8. When the matching form submit arrives, run `prepare-execution`. Preserve the trusted `pending_execution_draft` and `draft_fingerprint`, show `confirmation_text`, and end the turn without calling `start_valve_bank`.
9. On a later user turn that confirms the displayed draft, run `build-execution` with `execution_confirmed: true`, `draft_was_shown_to_user: true`, `confirmation_source: "user_confirmed_irrigation_execution_draft"`, and the matching `confirmed_draft_fingerprint`.
10. Call `start_valve_bank` once per script-produced argument object, in list order. Stop after the first failed or unconfirmed result, skip the rest, never perform an automatic compensating close, and report the partial execution accurately.

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

Do not include a row in recommended Syntax if `goods_name` is empty, `stock_goods_id` is missing, or the row does not match the operation type. If no confident candidates exist, return Syntax with `data` and no `-` items; the frontend can show an empty panel and let the user add materials.

On submit, `scripts/agri_material_payload.py build-submit` keeps only the compact submit fields:

```text
goods_name      = submitted goods_name when non-empty, otherwise matched inventory name
stock_goods_id  = submitted stock_goods_id when valid, otherwise matched stock_goods.id
is_formula      = submitted is_formula || 0
num             = submitted total num
price           = submitted price when provided, otherwise matched inventory price or matched stock_goods.price
unit            = submitted unit when provided, otherwise matched stock_goods.unit or ""
dosage          = num / record_draft.area * 1000
```

Do not replace the script-produced item with the original inventory row after this step. The matched inventory row is only for MCP grounding and missing metadata fallback; never use inventory balance `num` as submitted `num`.

## Required References

- `references/form-panel.md`: frontend Syntax and `form_submit` contract.
- `references/record-draft.md`: draft lifecycle and `add_farming_record` merge rules.
- `references/material-selection.md`: operation-aware material filtering rules.
- `references/usage-recommendation.md`: evidence-backed per-mu rate and frontend `num/dosage` recommendation rules.
- `references/goodslist-submit.md`: validate original inventory rows and build compact `add_farming_record.goodsList`.
- `references/irrigation-control.md`: exact sensor analysis, evidence order, batch valve lookup, confirmation gate, and partial-execution rules.
- `references/irrigation-form.md`: dedicated irrigation Syntax, submit JSON, editable fields, and validation.
- `scripts/agri_material_payload.py`: deterministic build/validation for material Syntax and submit-ready goodsList.
- `scripts/irrigation_control_payload.py`: deterministic sensor, form, draft-binding, and valve execution payloads.
- `call-mcp-tools`: MCP tool selection and parameter discipline.
- `call-mcp-tools` reference `tool-agri-input-list.md`: material list source fields.
- `call-mcp-tools` reference `tool-farming-operation-list.md`: operation list and `matter_id`.
- `call-mcp-tools` reference `tool-farming-record.md`: creation result handling.

## Completion Checklist

Use only the checklist for the branch actually executed. The device-irrigation branch does not require material selection or farming-record creation.

### Farming-record branch checklist

- Recommendation used MCP evidence and did not invent an operation.
- `matter_id` came from `get_farming_operation_list` or prior MCP-backed context.
- Materials came only from filtered `get_agri_input_list` results; `get_formula_list` was not used and full inventory was not returned by default.
- The whole script-produced `pending_draft` was preserved from panel creation to form submission.
- Script-produced `add_farming_record_args` was used directly; no manual final payload merge was performed.
- Submit-ready `goodsList` used only `goods_name`, `stock_goods_id`, `is_formula`, `num`, `price`, `unit`, and computed `dosage`; frontend `num` was not replaced by inventory balance, and any metadata fallback came only from the matched MCP inventory row.
- `scripts/agri_material_payload.py` was used for `build-panel` and `build-submit` when materials were involved.
- Frontend recommendation used `form agri-material-usage` Syntax only, with no JSON wrapper or `form-panel` block.
- Material-related recommendations attempted a per-mu rate recommendation, using model agronomic experience when stronger sources lacked a rate; frontend `num/dosage` fell back to `0` only when no reasonable rate or area was available.
- Operator defaults to `user_id` when available.
- User-facing confirmation drafts did not display `work_user`, `tgzn_user_id`, or `user_id`.
- `add_farming_record` was not called until final record-creation confirmation and required draft fields were complete; no-material operations used `record_creation_confirmed: true`, `draft_was_shown_to_user: true`, and `confirmation_source: "user_confirmed_prepared_draft"` only after the user confirmed the prepared draft in a separate user turn.

### Device-irrigation branch checklist

- Irrigation used the first finite exact `SHUM` per device, retained the authoritative full `sensor_analysis`, and passed only the script-produced comma-separated `plot_device_ids` to one batch valve lookup.
- The form submit included every candidate `valve_bank_id` from the trusted pending irrigation draft exactly once; unselected candidates remained present with `selected: false`.
- The irrigation form submit only prepared and displayed an execution draft; a later user confirmation with matching `draft_fingerprint` was required before ordered valve starts.
- Valve starts stopped on the first failure, later calls were skipped, and no automatic compensating close was attempted.
