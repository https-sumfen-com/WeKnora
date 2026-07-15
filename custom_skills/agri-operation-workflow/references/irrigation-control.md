# Device-Assisted Irrigation Control

Read this reference for soil-moisture analysis, the irrigation decision, valve discovery, the execution-confirmation gate, and partial execution reporting. Use `irrigation-form.md` for the dedicated frontend Syntax and submit fields.

## 1. Analyze Exact Soil-Moisture Readings

Call `get_plot_device_list` with the known `cid + plot_id`, then pass its complete returned device list to:

```text
scripts/irrigation_control_payload.py analyze-sensors
```

The script output is authoritative. Extraction follows these rules:

- A telemetry row is soil moisture only when `key == "SHUM"`. Do not match `shum`, a localized `name`, or another moisture-looking key.
- For each device, use the first exact `SHUM` row whose value is a finite number.
- Use the device-list item's outer `id` as its plot-device association ID; never use nested `device.id`.
- Deduplicate repeated outer IDs in first-occurrence order. Across repeated items for one ID, keep the first finite exact `SHUM` encountered; after one valid reading is selected, later duplicates do not contribute another reading or another average weight.
- `plot_device_ids` is a comma-separated string such as `"16,21,35"`. The internal ordered identifier list is `plot_device_id_values`.
- Despite its legacy name, `plot_device_id_values` contains canonical decimal strings such as `["16", "21", "35"]`. Every int64 identifier in JSON, form, trusted pending state, or MCP arguments remains a decimal string so JavaScript JSON round trips cannot round large IDs.
- If `has_valid_shum` is false, do not continue to a valve lookup or control action.

Do not reduce the script result to a bare average. Preserve the complete `sensor_analysis`, including `ok`, `has_valid_shum`, `sensor_readings`, `average_soil_moisture`, `plot_device_ids`, and `plot_device_id_values`. `build-panel` must revalidate all of those fields, recompute the average from readings, and verify both ID representations before it can emit form state.

## 2. Decide Whether Irrigation Is Necessary

After valid sensor analysis, gather only the evidence needed for this coordinated workflow:

1. Treat the exact `SHUM` average and per-device readings as the primary current water-status evidence.
2. Call `get_plot_info` for crop, growth stage, plot condition, and current agronomic advice.
3. Call `get_weather` for recent/current conditions and forecast rain that could remove or delay the need.
4. Set `irrigation_needed: true` only when the combined evidence supports irrigation. Record a concise evidence-backed `reason` and a conservative positive `recommended_duration_minutes`.

If evidence says irrigation is unnecessary or remains uncertain, explain that decision and stop before valve discovery. Never treat a low-looking number alone as universal authorization because crop, stage, sensor context, and forecast rain matter.

## 3. Discover Valve Banks in One Batch

Call get_valve_bank_by_device exactly once with the authoritative IDs:

```json
{
  "cid": "2007",
  "plot_device_ids": "16,21,35"
}
```

The `plot_device_ids` input is a comma-separated string. Do not loop over IDs, do not send `plot_device_id_values`, and do not make one tool call per device. The returned `payload[]` is the service's already-deduplicated valve-bank list; keep its order and validate each `id`, `title`, and `run_status` through `build-panel`.

When `payload[]` is empty, do not display a valve form and do not call `start_valve_bank`. Call `get_farming_operation_list` and fall back to the ordinary farming-operation path so the user can arrange an irrigation record/task without device control.

## 4. Build the Form and Preserve Trusted State

Run `build-panel` only with:

- known positive `cid` and `plot_id`;
- the complete unmodified script-produced `sensor_analysis`;
- `irrigation_needed: true` and the evidence-backed `reason`;
- a positive `recommended_duration_minutes`;
- the server-returned valve-bank list.

Send only the returned `form_syntax` to the frontend and retain the complete `pending_irrigation_draft` in trusted conversation/backend state. Do not expose pending state in the Syntax and do not recreate it from the later user submit.

## 5. Separate Submit from Execution Confirmation

On a matching irrigation form submit, run `prepare-execution`. It validates submitted valve IDs against the trusted irrigation draft, applies the user-edited selections/durations, and returns:

- `confirmation_text` to show to the user;
- `pending_execution_draft` to keep in trusted state;
- a deterministic `draft_fingerprint` binding `cid`, `plot_id`, ordered valve IDs, and durations.

The fingerprint binds `cid`, `plot_id`, `plot_name`, `average_soil_moisture`, `reason`, and every ordered selected valve ID/title/final duration. The `pending_execution_draft` and confirmation text carry and display the same plot, moisture, reason, valve, and duration facts. The fingerprint is version binding, not authentication; the application must protect pending state. Show the execution draft and end the assistant turn. A separate later user reply must confirm that displayed draft.

Only then run `build-execution` with all of:

```json
{
  "execution_confirmed": true,
  "draft_was_shown_to_user": true,
  "confirmation_source": "user_confirmed_irrigation_execution_draft",
  "confirmed_draft_fingerprint": "<matching draft_fingerprint>",
  "pending_execution_draft": {}
}
```

Never call `start_valve_bank` in the same assistant turn that receives the irrigation form submit. If any confirmation field, trusted draft, or fingerprint match is missing, ask for confirmation again and do not control a valve.

## 6. Execute in Order and Report Partial Results

Use the script-produced `start_valve_bank_args` directly and call `start_valve_bank` in list order. Its `cid` and `id` values are decimal strings accepted by SONO's FlexibleInt64 contract; do not coerce them to JavaScript numbers. For each call, require an upstream response that explicitly confirms success.

At the first failure, error, empty/unconfirmed response, or interruption:

1. Stop; do not call any later valve in the list.
2. Record earlier confirmed starts as succeeded, the current valve as failed/unconfirmed, and all remaining valves as skipped.
3. Do not automatically call `stop_valve_bank` for already-started valves. Automatic compensating close could undo an action the user approved and is not authorized by this workflow.
4. Report the partial result with valve titles/IDs and durations, plus the real error or unconfirmed status without exposing internal credentials or URLs.
