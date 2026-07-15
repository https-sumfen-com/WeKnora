# Irrigation Valve Duration Syntax Contract

Read this reference before returning the device-irrigation form or handling its submit. Material form details belong only to `form-panel.md`; do not copy them into this contract.

Prefer `scripts/irrigation_control_payload.py build-panel`. Send only its `form_syntax` and keep `pending_irrigation_draft` in trusted state.

## Assistant Syntax

The dedicated Syntax is:

```text
form irrigation-valve-duration
title 灌溉时长确认
autoOpen false
plot_name "示例地块"
average_soil_moisture 25.25
reason "土壤湿度偏低且近期无明显降雨"
data
  - valve_bank_id "31"
    valve_bank_title "阀门组A"
    duration_minutes 20
    selected true
```

Rules:

- The first line must be `form irrigation-valve-duration`; use `title 灌溉时长确认`, `autoOpen false`, and a required `data` section exactly as shown.
- Send the Syntax without a JSON wrapper, SSE event, Markdown explanation, or material-form fields.
- `plot_name`, `average_soil_moisture`, and `reason` are read-only evidence/context fields from the trusted panel draft. Keep `cid` and `plot_id` only in trusted state, not in visible Syntax.
- Each valve starts with `  - valve_bank_id ...`; its following fields use four spaces.
- `valve_bank_id` is a quoted decimal string and `valve_bank_title` comes from the server-returned valve list; neither is user-editable. Keep `run_status` only in trusted state.
- Only `selected` and `duration_minutes` are editable. `selected` is a boolean; `duration_minutes` is a positive integer.
- All int64 identifiers that cross JSON, form, or MCP boundaries must be canonical decimal strings. This includes `cid`, `plot_id`, plot-device IDs, and valve-bank IDs; never emit them as JSON numbers.
- Do not include `pending_irrigation_draft`, `sensor_analysis`, `plot_device_ids`, `plot_device_id_values`, `run_status`, token, or other system parameters in the visible Syntax.

## User Submit Message

Handle only a structured user message matching all three discriminator fields:

```json
{
  "type": "form_submit",
  "formType": "irrigation-valve-duration",
  "tag": "irrigation_valve_duration_confirm",
  "sourceMessageId": "assistant-message-id",
  "valveBanks": [
    {
      "valve_bank_id": "31",
      "duration_minutes": 20,
      "selected": true
    }
  ]
}
```

Validation:

- `type` must equal `form_submit`, `formType` must equal `irrigation-valve-duration`, and `tag` must equal `irrigation_valve_duration_confirm`.
- `valveBanks` must be a list with no duplicate `valve_bank_id` values.
- The submit must contain every candidate `valve_bank_id` from the trusted pending draft exactly once.
- Row order may differ from the pending draft; identity is checked as an exact set before selected rows keep their submitted execution order.
- Use `selected: false` to cancel execution; deleting a row does not cancel it.
- Every `valve_bank_id` must be a canonical positive decimal string present in the trusted `pending_irrigation_draft`; reject unknown IDs.
- `selected` must be a JSON boolean and `duration_minutes` must be a positive integer.
- At least one valve must remain selected.
- Recover the pending draft from trusted state or `sourceMessageId`; never trust the submit to supply `cid`, `plot_id`, valve titles, status, or sensor evidence.

Run `prepare-execution` with the recovered `pending_irrigation_draft` and the complete `submitted_form`. Its output is an execution draft only, not control authorization. The draft, fingerprint, and confirmation text bind and display the plot name, average soil moisture, irrigation reason, selected valve IDs/titles, and final durations. Show its confirmation text, preserve its `pending_execution_draft` and `draft_fingerprint`, and wait for another user turn.

The later confirmation must use `confirmation_source: "user_confirmed_irrigation_execution_draft"` and the matching fingerprint before `build-execution` may return `start_valve_bank_args`.
